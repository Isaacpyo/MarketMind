from __future__ import annotations

import numpy as np
import pytest

from marketmind.recsys.interactions import (
    EVENT_WEIGHTS,
    InteractionData,
    aggregate_user_events,
    build_interaction_data,
    confidence,
)
from marketmind.recsys.split import temporal_holdout


def test_purchase_outweighs_many_views_after_compression() -> None:
    assert EVENT_WEIGHTS["purchase"] > EVENT_WEIGHTS["add_to_cart"] > EVENT_WEIGHTS["view"]
    one_purchase = confidence(EVENT_WEIGHTS["purchase"])
    five_views = confidence(5 * EVENT_WEIGHTS["view"])
    assert one_purchase > five_views


def test_aggregate_user_events_sums_weights_and_tracks_strongest_signal() -> None:
    profile = aggregate_user_events(
        [
            {"product_id": "10001", "type": "view"},
            {"product_id": "10001", "type": "add_to_cart"},
            {"product_id": "10002", "type": "view"},
            {"product_id": "10003", "type": "unknown"},
        ],
        cart_product_ids=["10009"],
    )
    assert profile.weights == {"10001": 5.0, "10002": 1.0}
    assert profile.strongest == {"10001": "add_to_cart", "10002": "view"}
    assert profile.exclude == {"10001", "10002", "10009"}
    assert profile.size == 2


def test_build_interaction_data_aggregates_pairs_and_ignores_unknown_items() -> None:
    rows = [
        ("u1", "A", "view", 30.0),
        ("u1", "A", "purchase", 10.0),
        ("u2", "B", "view", 5.0),
        ("u2", "Z", "purchase", 1.0),  # not in the catalogue
    ]
    data = build_interaction_data(rows, ["A", "B"])
    assert data.user_ids == ["u1", "u2"]
    assert data.n_items == 2
    assert len(data) == 2
    matrix = data.matrix().toarray()
    assert matrix[0, 0] == pytest.approx(np.log1p(9.0))
    assert matrix[1, 1] == pytest.approx(np.log1p(1.0))
    # First-seen timestamp is kept for the temporal split.
    assert sorted(data.first_ts.tolist()) == [5.0, 10.0]


def _data_for(n_items_per_user: dict[str, int]) -> InteractionData:
    rows = []
    for user, n in n_items_per_user.items():
        for i in range(n):
            rows.append((user, f"I{i}", "purchase", float(i)))
    universe = [f"I{i}" for i in range(max(n_items_per_user.values()))]
    return build_interaction_data(rows, universe)


def test_temporal_holdout_holds_out_latest_items_per_user() -> None:
    data = _data_for({"heavy": 10, "light": 3})
    split = temporal_holdout(data, holdout_fraction=0.2, min_items=5)
    heavy = data.user_ids.index("heavy")
    # Items I8 and I9 were interacted with last.
    assert split.test_items == {heavy: frozenset({8, 9})}
    assert split.n_test == 2
    assert int((~split.train_mask).sum()) == 2


def test_temporal_holdout_always_leaves_train_and_test_items() -> None:
    data = _data_for({"u": 5})
    split = temporal_holdout(data, holdout_fraction=0.9, min_items=5)
    assert split.n_test == 4
    assert int(split.train_mask.sum()) == 1


def test_temporal_holdout_validates_fraction() -> None:
    data = _data_for({"u": 5})
    with pytest.raises(ValueError, match="holdout_fraction"):
        temporal_holdout(data, holdout_fraction=1.0)
