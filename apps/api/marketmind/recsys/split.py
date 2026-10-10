"""Train/test splitting for offline evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from marketmind.recsys.interactions import InteractionData


@dataclass(frozen=True)
class HoldoutSplit:
    train_mask: npt.NDArray[np.bool_]
    test_items: dict[int, frozenset[int]]

    @property
    def n_test(self) -> int:
        return sum(len(items) for items in self.test_items.values())


def temporal_holdout(
    data: InteractionData, holdout_fraction: float = 0.2, min_items: int = 5
) -> HoldoutSplit:
    """Hold out each eligible user's most recent ``holdout_fraction`` of items.

    A temporal split is stricter than a random one: the model must predict what a
    shopper discovers *next*, not fill random gaps in their history. Users with fewer
    than ``min_items`` items keep everything in train.
    """
    if not 0 < holdout_fraction < 1:
        raise ValueError("holdout_fraction must be in (0, 1)")

    n = len(data)
    train_mask = np.ones(n, dtype=bool)
    if n == 0:
        return HoldoutSplit(train_mask=train_mask, test_items={})

    # Sort by user, then time, then item id for a deterministic tie-break.
    order = np.lexsort((data.items, data.first_ts, data.users))
    sorted_users = data.users[order]
    starts = np.flatnonzero(np.r_[True, sorted_users[1:] != sorted_users[:-1]])
    counts = np.diff(np.r_[starts, n])

    test_items: dict[int, frozenset[int]] = {}
    for start, count in zip(starts, counts, strict=True):
        if count < min_items:
            continue
        n_train = int(np.ceil(count * (1 - holdout_fraction)))
        n_train = min(max(n_train, 1), count - 1)
        held_rows = order[start + n_train : start + count]
        train_mask[held_rows] = False
        user = int(sorted_users[start])
        test_items[user] = frozenset(int(i) for i in data.items[held_rows])
    return HoldoutSplit(train_mask=train_mask, test_items=test_items)
