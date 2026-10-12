"""Process-wide holder for the live catalogue and recommender model."""

from __future__ import annotations

import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from marketmind.db import Db
from marketmind.recsys.als import AlsConfig, AlsModel
from marketmind.recsys.content import ContentModel, product_text
from marketmind.recsys.hybrid import DEFAULT_WARM_THRESHOLD, Catalog, HybridRecommender


@dataclass(frozen=True)
class LoadedModel:
    als: AlsModel
    version: str
    trained_at: datetime
    config: AlsConfig


class EngineNotReadyError(RuntimeError):
    pass


def build_catalog(products: Iterable[Mapping[str, Any]]) -> Catalog:
    docs = sorted(products, key=lambda p: str(p["_id"]))
    return Catalog(
        product_ids=[str(p["_id"]) for p in docs],
        titles=[str(p["title"]) for p in docs],
        categories=[str(p["category"]) for p in docs],
        popularity=np.array([float(p.get("popularity", 0)) for p in docs], dtype=np.float64),
    )


class RecommenderEngine:
    """Swaps in new catalogues/models atomically; readers grab one consistent snapshot."""

    def __init__(self, warm_threshold: int = DEFAULT_WARM_THRESHOLD) -> None:
        self.warm_threshold = warm_threshold
        self._lock = threading.Lock()
        self._catalog: Catalog | None = None
        self._content: ContentModel | None = None
        self._model: LoadedModel | None = None
        self._recommender: HybridRecommender | None = None

    @property
    def ready(self) -> bool:
        return self._recommender is not None

    @property
    def model(self) -> LoadedModel | None:
        return self._model

    @property
    def recommender(self) -> HybridRecommender:
        recommender = self._recommender
        if recommender is None:
            raise EngineNotReadyError("catalogue not loaded yet")
        return recommender

    def load_catalog(self, products: Iterable[Mapping[str, Any]]) -> None:
        catalog = build_catalog(products)
        if len(catalog) == 0:
            return
        content = ContentModel([product_text(t) for t in catalog.titles])
        with self._lock:
            self._catalog, self._content = catalog, content
            self._rebuild()

    def reload_catalog(self, db: Db) -> None:
        self.load_catalog(db.products.find({}, {"title": 1, "category": 1, "popularity": 1}))

    def set_model(self, model: LoadedModel | None) -> None:
        with self._lock:
            self._model = model
            self._rebuild()

    def _rebuild(self) -> None:
        if self._catalog is None or self._content is None:
            return
        self._recommender = HybridRecommender(
            self._catalog,
            self._content,
            self._model.als if self._model else None,
            warm_threshold=self.warm_threshold,
        )
