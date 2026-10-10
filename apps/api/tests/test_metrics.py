from __future__ import annotations

import numpy as np
import pytest

from marketmind.recsys.metrics import catalog_coverage, precision_at_k, recall_at_k, top_k, zscore


def test_precision_counts_hits_in_top_k_only() -> None:
    assert precision_at_k([1, 2, 3, 4], {2, 4, 9}, k=2) == 0.5
    assert precision_at_k([1, 2, 3, 4], {2, 4, 9}, k=4) == 0.5
    assert precision_at_k([5, 6], {1}, k=2) == 0.0


def test_precision_divides_by_k_even_when_list_is_short() -> None:
    assert precision_at_k([1], {1}, k=10) == pytest.approx(0.1)


def test_recall_normalises_by_achievable_hits() -> None:
    # 2 relevant items, both found in top 10 -> perfect recall.
    assert recall_at_k([3, 1, 2], {1, 2}, k=10) == 1.0
    # 20 relevant items but only k=5 slots: 5 hits is the best possible.
    assert recall_at_k(list(range(5)), set(range(20)), k=5) == 1.0
    assert recall_at_k([0, 99], {0, 1, 2, 3}, k=2) == 0.5


@pytest.mark.parametrize("fn", [precision_at_k, recall_at_k])
def test_metrics_handle_empty_relevant_and_reject_bad_k(fn: object) -> None:
    assert fn([1, 2], set(), k=2) == 0.0  # type: ignore[operator]
    with pytest.raises(ValueError, match="k must be positive"):
        fn([1], {1}, k=0)  # type: ignore[operator]


def test_catalog_coverage() -> None:
    assert catalog_coverage([[0, 1], [1, 2]], n_items=10) == pytest.approx(0.3)
    assert catalog_coverage([], n_items=10) == 0.0
    assert catalog_coverage([[1]], n_items=0) == 0.0


def test_top_k_orders_by_score_and_respects_exclusions() -> None:
    scores = np.array([0.1, 0.9, 0.5, 0.9, -1.0])
    assert top_k(scores, 3) == [1, 3, 2]  # tie broken by index
    assert top_k(scores, 3, exclude=[1]) == [3, 2, 0]
    assert top_k(scores, 10, exclude=[0, 1, 2, 3]) == [4]


def test_top_k_skips_nan_and_negative_infinity() -> None:
    scores = np.array([np.nan, 1.0, -np.inf, 0.5])
    assert top_k(scores, 4) == [1, 3]


def test_zscore_standardises_and_floors_unknowns() -> None:
    z = zscore(np.array([1.0, 2.0, 3.0, np.nan]))
    assert z[:3].mean() == pytest.approx(0.0)
    assert z[:3].std() == pytest.approx(1.0)
    assert z[3] == pytest.approx(z[:3].min())


def test_zscore_of_constant_or_empty_signal_is_zero() -> None:
    assert np.all(zscore(np.array([2.0, 2.0])) == 0)
    assert np.all(zscore(np.array([np.nan, np.nan])) == 0)
