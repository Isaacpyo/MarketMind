"""The serving recommender: popularity → content → ALS, blended by how much we know.

Everything here works in *catalogue index space* (0..n_products-1). The same object is used
by the API and by offline evaluation, so the metrics on the admin page measure exactly the
code path shoppers hit.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import numpy.typing as npt

from marketmind.recsys.als import AlsModel
from marketmind.recsys.content import ContentModel
from marketmind.recsys.metrics import top_k, zscore

Strategy = Literal["popularity", "cold_start", "hybrid"]
Source = Literal["popularity", "content", "als"]
ComponentName = Literal["popularity", "content", "als", "hybrid"]

# Below this many distinct items, collaborative signals are too noisy to lead.
DEFAULT_WARM_THRESHOLD = 3
COLD_START_CONTENT_WEIGHT = 0.7


@dataclass(frozen=True)
class Catalog:
    product_ids: list[str]
    titles: list[str]
    categories: list[str]
    popularity: npt.NDArray[np.float64]
    index: dict[str, int] = field(init=False)

    def __post_init__(self) -> None:
        n = len(self.product_ids)
        if not (len(self.titles) == len(self.categories) == len(self.popularity) == n):
            raise ValueError("catalogue columns must have equal length")
        object.__setattr__(self, "index", {pid: i for i, pid in enumerate(self.product_ids)})

    def __len__(self) -> int:
        return len(self.product_ids)


@dataclass(frozen=True)
class ScoredItem:
    index: int
    score: float
    source: Source
    anchor: int | None = None


@dataclass(frozen=True)
class RecommendationResult:
    strategy: Strategy
    items: list[ScoredItem]


class HybridRecommender:
    def __init__(
        self,
        catalog: Catalog,
        content: ContentModel,
        als: AlsModel | None = None,
        *,
        warm_threshold: int = DEFAULT_WARM_THRESHOLD,
    ) -> None:
        if content.n_items != len(catalog):
            raise ValueError("content model and catalogue disagree on size")
        self.catalog = catalog
        self.content = content
        self.als = als
        self.warm_threshold = warm_threshold
        self.hybrid_weight = als.config.hybrid_weight if als else 0.0
        # Map catalogue index -> ALS item index (-1 when the model has never seen the product).
        self._als_index = np.full(len(catalog), -1, dtype=np.int64)
        if als is not None:
            for als_idx, pid in enumerate(als.item_ids):
                cat_idx = catalog.index.get(pid)
                if cat_idx is not None:
                    self._als_index[cat_idx] = als_idx

    # --- components ------------------------------------------------------------------------

    def popularity_scores(self) -> npt.NDArray[np.float64]:
        return np.log1p(self.catalog.popularity.astype(np.float64))

    def content_scores(self, history: Sequence[int], values: Sequence[float]) -> npt.NDArray[np.float64]:
        return self.content.profile_scores(history, values)

    def als_scores(self, history: Sequence[int], values: Sequence[float]) -> npt.NDArray[np.float64]:
        """ALS scores mapped into catalogue space; NaN for products unknown to the model."""
        out = np.full(len(self.catalog), np.nan, dtype=np.float64)
        if self.als is None:
            return out
        mapped = [(int(self._als_index[h]), v) for h, v in zip(history, values, strict=True)]
        known = [(i, v) for i, v in mapped if i >= 0]
        if not known:
            return out
        raw = self.als.score_user([i for i, _ in known], [v for _, v in known])
        has = self._als_index >= 0
        out[has] = raw[self._als_index[has]]
        return out

    def component_scores(
        self, name: ComponentName, history: Sequence[int], values: Sequence[float]
    ) -> npt.NDArray[np.float64]:
        if name == "popularity":
            return self.popularity_scores()
        if name == "content":
            return self.content_scores(history, values)
        if name == "als":
            return self.als_scores(history, values)
        return self.score(history, values)[1]

    # --- blending --------------------------------------------------------------------------

    def strategy_for(self, n_items: int) -> Strategy:
        if n_items == 0:
            return "popularity"
        if n_items < self.warm_threshold or self.als is None:
            return "cold_start"
        return "hybrid"

    def score(
        self, history: Sequence[int], values: Sequence[float]
    ) -> tuple[Strategy, npt.NDArray[np.float64], dict[Source, npt.NDArray[np.float64]]]:
        """Blend component z-scores; returns (strategy, blended scores, weighted parts)."""
        strategy = self.strategy_for(len(history))
        parts: dict[Source, npt.NDArray[np.float64]]
        if strategy == "popularity":
            parts = {"popularity": zscore(self.popularity_scores())}
        elif strategy == "cold_start":
            w = COLD_START_CONTENT_WEIGHT
            parts = {
                "content": w * zscore(self.content_scores(history, values)),
                "popularity": (1 - w) * zscore(self.popularity_scores()),
            }
        else:
            w = self.hybrid_weight
            parts = {
                "als": w * zscore(self.als_scores(history, values)),
                "content": (1 - w) * zscore(self.content_scores(history, values)),
            }
        blended = np.sum(list(parts.values()), axis=0)
        return strategy, blended, parts

    def recommend(
        self,
        history: Sequence[int],
        values: Sequence[float],
        k: int,
        exclude: Sequence[int] = (),
    ) -> RecommendationResult:
        strategy, blended, parts = self.score(history, values)
        picked = top_k(blended, k, exclude=list(exclude) + list(history))
        names = list(parts)
        stacked = np.vstack([parts[name] for name in names])
        sources: list[Source] = [names[int(stacked[:, i].argmax())] for i in picked]
        content_picks = [i for i, s in zip(picked, sources, strict=True) if s == "content"]
        anchors = dict(zip(content_picks, self.content.anchors(content_picks, list(history)), strict=True))
        items = [
            ScoredItem(index=i, score=float(blended[i]), source=src, anchor=anchors.get(i))
            for i, src in zip(picked, sources, strict=True)
        ]
        return RecommendationResult(strategy=strategy, items=items)

    # --- item-to-item ----------------------------------------------------------------------

    def similar_items(self, index: int, k: int) -> list[ScoredItem]:
        sims = self.content.similarity_to(index)
        return [
            ScoredItem(index=i, score=float(sims[i]), source="content", anchor=index)
            for i in top_k(sims, k, exclude=[index])
            if sims[i] > 0
        ]

    def also_bought(self, index: int, k: int) -> list[ScoredItem]:
        """Items with similar ALS factors; falls back to content when ALS can't help."""
        als_idx = int(self._als_index[index])
        if self.als is None or als_idx < 0:
            return self.similar_items(index, k)
        raw = self.als.item_similarity(als_idx)
        sims = np.full(len(self.catalog), np.nan, dtype=np.float64)
        has = self._als_index >= 0
        sims[has] = raw[self._als_index[has]]
        return [
            ScoredItem(index=i, score=float(sims[i]), source="als", anchor=index)
            for i in top_k(sims, k, exclude=[index])
        ]

    def trending(self, k: int, category: str | None = None, exclude: Sequence[int] = ()) -> list[ScoredItem]:
        scores = self.popularity_scores()
        if category is not None:
            mask = np.array([c != category for c in self.catalog.categories])
            scores = np.where(mask, -np.inf, scores)
        return [
            ScoredItem(index=i, score=float(scores[i]), source="popularity")
            for i in top_k(scores, k, exclude=exclude)
        ]
