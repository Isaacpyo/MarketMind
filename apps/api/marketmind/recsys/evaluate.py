"""Offline evaluation of every recommender component on a holdout split."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix

from marketmind.recsys.hybrid import ComponentName, HybridRecommender
from marketmind.recsys.metrics import catalog_coverage, precision_at_k, recall_at_k, top_k


@dataclass(frozen=True)
class ComponentMetrics:
    precision: float
    recall: float
    coverage: float


@dataclass(frozen=True)
class Evaluation:
    k: int
    users_evaluated: int
    models: dict[str, ComponentMetrics]


def evaluate(
    recommender: HybridRecommender,
    train: csr_matrix,
    test_items: Mapping[int, frozenset[int]],
    *,
    k: int = 10,
    max_users: int | None = 2000,
    seed: int = 0,
    components: Sequence[ComponentName] = ("popularity", "content", "als", "hybrid"),
) -> Evaluation:
    """Score each component for every held-out user and average precision/recall@k.

    ``train`` rows are in the recommender's catalogue index space. Items the user already
    has in train are excluded from their ranking, exactly as at serving time.
    """
    users = sorted(test_items)
    if max_users is not None and len(users) > max_users:
        rng = np.random.default_rng(seed)
        users = sorted(int(u) for u in rng.choice(users, size=max_users, replace=False))

    wanted = [c for c in components if c != "als" or recommender.als is not None]
    results: dict[str, ComponentMetrics] = {}
    n_items = len(recommender.catalog)
    for name in wanted:
        precisions: list[float] = []
        recalls: list[float] = []
        lists: list[list[int]] = []
        for user in users:
            row = train[user]
            history = [int(i) for i in row.indices]
            values = [float(v) for v in row.data]
            scores = recommender.component_scores(name, history, values)
            recs = top_k(scores, k, exclude=history)
            relevant = test_items[user]
            precisions.append(precision_at_k(recs, relevant, k))
            recalls.append(recall_at_k(recs, relevant, k))
            lists.append(recs)
        results[name] = ComponentMetrics(
            precision=float(np.mean(precisions)) if precisions else 0.0,
            recall=float(np.mean(recalls)) if recalls else 0.0,
            coverage=catalog_coverage(lists, n_items),
        )
    return Evaluation(k=k, users_evaluated=len(users), models=results)
