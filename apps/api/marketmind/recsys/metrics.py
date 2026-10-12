"""Ranking metrics and score utilities."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.floating]


def precision_at_k(recommended: Sequence[int], relevant: Collection[int], k: int) -> float:
    """Fraction of the top-k recommendations the user actually interacted with."""
    if k <= 0:
        raise ValueError("k must be positive")
    if not relevant:
        return 0.0
    hits = sum(1 for item in recommended[:k] if item in relevant)
    return hits / k


def recall_at_k(recommended: Sequence[int], relevant: Collection[int], k: int) -> float:
    """Hits divided by the best achievable number of hits, ``min(k, |relevant|)``.

    Normalising by ``min(k, |relevant|)`` (as `implicit` does) keeps recall at 1.0 for a
    perfect ranking even when a user has more held-out items than k.
    """
    if k <= 0:
        raise ValueError("k must be positive")
    if not relevant:
        return 0.0
    hits = sum(1 for item in recommended[:k] if item in relevant)
    return hits / min(k, len(relevant))


def catalog_coverage(recommendation_lists: Iterable[Iterable[int]], n_items: int) -> float:
    """Share of the catalogue that appears in at least one user's recommendations."""
    if n_items <= 0:
        return 0.0
    seen: set[int] = set()
    for recs in recommendation_lists:
        seen.update(recs)
    return len(seen) / n_items


def zscore(scores: FloatArray) -> npt.NDArray[np.float64]:
    """Standardise scores so components on different scales can be blended.

    NaNs (items a component knows nothing about) are mapped to the component's minimum so
    they never outrank items it actually scored.
    """
    x = np.asarray(scores, dtype=np.float64)
    finite = np.isfinite(x)
    if not finite.any():
        return np.zeros_like(x)
    mean = x[finite].mean()
    std = x[finite].std()
    z = (x - mean) / std if std > 0 else np.zeros_like(x)
    z[~finite] = z[finite].min() if std > 0 else 0.0
    return z


def top_k(scores: FloatArray, k: int, exclude: Iterable[int] = ()) -> list[int]:
    """Indices of the k highest scores, best first, skipping excluded indices."""
    s = np.array(scores, dtype=np.float64, copy=True)
    excluded = list(exclude)
    if excluded:
        s[excluded] = -np.inf
    s[np.isnan(s)] = -np.inf
    available = int(np.isfinite(s).sum())
    k = min(k, available)
    if k <= 0:
        return []
    candidates = np.argpartition(-s, k - 1)[:k]
    # Stable tie-break on index keeps results deterministic.
    ordered = candidates[np.lexsort((candidates, -s[candidates]))]
    return [int(i) for i in ordered]
