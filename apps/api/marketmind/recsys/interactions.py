"""Turning raw implicit-feedback events into a user × item matrix."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy.sparse import csr_matrix

# How strongly each signal says "this user likes this item". Purchases dominate, but a
# cluster of views still moves the needle for shoppers who haven't bought anything yet.
EVENT_WEIGHTS: Mapping[str, float] = {
    "view": 1.0,
    "rec_click": 2.0,
    "add_to_cart": 4.0,
    "purchase": 8.0,
}


def event_weight(event_type: str) -> float:
    return EVENT_WEIGHTS.get(event_type, 0.0)


def confidence(total_weight: npt.ArrayLike) -> npt.NDArray[np.float32]:
    """Compress summed weights so a hundred views can't drown out one purchase."""
    return np.log1p(np.asarray(total_weight, dtype=np.float64)).astype(np.float32)


@dataclass(frozen=True)
class UserProfile:
    """One shopper's aggregated interactions, as used at serving time."""

    weights: dict[str, float]
    strongest: dict[str, str]
    exclude: frozenset[str]

    @property
    def size(self) -> int:
        return len(self.weights)


def aggregate_user_events(
    events: Iterable[Mapping[str, object]], cart_product_ids: Iterable[str] = ()
) -> UserProfile:
    weights: dict[str, float] = {}
    strongest: dict[str, str] = {}
    for event in events:
        pid = str(event["product_id"])
        etype = str(event["type"])
        w = event_weight(etype)
        if w <= 0:
            continue
        weights[pid] = weights.get(pid, 0.0) + w
        if w > event_weight(strongest.get(pid, "")):
            strongest[pid] = etype
    # Anything the shopper has touched is excluded from their feed, plus their cart.
    exclude = frozenset(weights) | frozenset(cart_product_ids)
    return UserProfile(weights=weights, strongest=strongest, exclude=exclude)


@dataclass(frozen=True)
class InteractionData:
    """Aggregated (user, item) interactions over a fixed item universe."""

    user_ids: list[str]
    item_ids: list[str]
    users: npt.NDArray[np.int32]
    items: npt.NDArray[np.int32]
    values: npt.NDArray[np.float32]
    first_ts: npt.NDArray[np.float64]

    @property
    def n_users(self) -> int:
        return len(self.user_ids)

    @property
    def n_items(self) -> int:
        return len(self.item_ids)

    def __len__(self) -> int:
        return len(self.values)

    def matrix(self, mask: npt.NDArray[np.bool_] | None = None) -> csr_matrix:
        users, items, values = self.users, self.items, self.values
        if mask is not None:
            users, items, values = users[mask], items[mask], values[mask]
        return csr_matrix((values, (users, items)), shape=(self.n_users, self.n_items), dtype=np.float32)


def build_interaction_data(
    rows: Iterable[tuple[str, str, str, float]], item_universe: Sequence[str]
) -> InteractionData:
    """Aggregate raw (user_id, product_id, event_type, unix_ts) rows.

    Products outside ``item_universe`` (e.g. delisted) are ignored. The first timestamp per
    pair is kept so the evaluation split can hold out each user's most recent discoveries.
    """
    item_index = {pid: i for i, pid in enumerate(item_universe)}
    totals: dict[tuple[str, int], list[float]] = {}
    for user_id, product_id, event_type, ts in rows:
        item = item_index.get(product_id)
        w = event_weight(event_type)
        if item is None or w <= 0:
            continue
        key = (user_id, item)
        entry = totals.get(key)
        if entry is None:
            totals[key] = [w, ts]
        else:
            entry[0] += w
            entry[1] = min(entry[1], ts)

    user_ids = sorted({user for user, _ in totals})
    user_index = {uid: i for i, uid in enumerate(user_ids)}
    n = len(totals)
    users = np.empty(n, dtype=np.int32)
    items = np.empty(n, dtype=np.int32)
    weights = np.empty(n, dtype=np.float64)
    first_ts = np.empty(n, dtype=np.float64)
    for row, ((user, item), (w, ts)) in enumerate(totals.items()):
        users[row] = user_index[user]
        items[row] = item
        weights[row] = w
        first_ts[row] = ts
    return InteractionData(
        user_ids=user_ids,
        item_ids=list(item_universe),
        users=users,
        items=items,
        values=confidence(weights),
        first_ts=first_ts,
    )
