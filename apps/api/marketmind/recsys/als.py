"""Collaborative filtering with implicit's Alternating Least Squares."""

from __future__ import annotations

import io
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass

# implicit warns (and slows down) if OpenBLAS spins up its own thread pool.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np
import numpy.typing as npt
from implicit.cpu.als import AlternatingLeastSquares
from scipy.sparse import csr_matrix


@dataclass(frozen=True)
class AlsConfig:
    factors: int = 64
    regularization: float = 0.05
    alpha: float = 1.0
    iterations: int = 20
    hybrid_weight: float = 0.5

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def fit_als(
    user_items: csr_matrix, config: AlsConfig, threads: int = 1, random_state: int = 42
) -> AlternatingLeastSquares:
    model = AlternatingLeastSquares(
        factors=config.factors,
        regularization=config.regularization,
        alpha=config.alpha,
        iterations=config.iterations,
        num_threads=threads,
        random_state=random_state,
    )
    model.fit(user_items, show_progress=False)
    return model


class AlsModel:
    """Serving wrapper: only item factors are persisted.

    User vectors are recomputed on every request from the shopper's *current* events
    (`recalculate_user`), so the feed responds to browsing immediately, and shoppers who
    signed up after the last training run still get collaborative recommendations.
    """

    def __init__(
        self, item_ids: Sequence[str], item_factors: npt.NDArray[np.float32], config: AlsConfig
    ) -> None:
        if len(item_ids) != item_factors.shape[0]:
            raise ValueError("item_ids and item_factors disagree")
        self.item_ids = list(item_ids)
        self.config = config
        self._model = AlternatingLeastSquares(
            factors=item_factors.shape[1],
            regularization=config.regularization,
            alpha=config.alpha,
            num_threads=1,
        )
        self._model.item_factors = np.ascontiguousarray(item_factors, dtype=np.float32)
        norms = np.linalg.norm(self._model.item_factors, axis=1)
        norms[norms == 0] = 1.0
        self._normalized = self._model.item_factors / norms[:, None]

    @classmethod
    def from_fitted(
        cls, model: AlternatingLeastSquares, item_ids: Sequence[str], config: AlsConfig
    ) -> AlsModel:
        return cls(item_ids, np.asarray(model.item_factors, dtype=np.float32), config)

    @property
    def item_factors(self) -> npt.NDArray[np.float32]:
        factors: npt.NDArray[np.float32] = self._model.item_factors
        return factors

    @property
    def n_items(self) -> int:
        return len(self.item_ids)

    def user_vector(self, item_indices: Sequence[int], values: Sequence[float]) -> npt.NDArray[np.float32]:
        n = len(item_indices)
        row = csr_matrix(
            (
                np.asarray(values, dtype=np.float32),
                np.asarray(item_indices, dtype=np.int32),
                np.array([0, n], dtype=np.int32),
            ),
            shape=(1, self.n_items),
        )
        vector: npt.NDArray[np.float32] = self._model.recalculate_user(0, row)
        return vector

    def score_user(self, item_indices: Sequence[int], values: Sequence[float]) -> npt.NDArray[np.float64]:
        if len(item_indices) == 0:
            return np.zeros(self.n_items, dtype=np.float64)
        vector = self.user_vector(item_indices, values)
        return np.asarray(self.item_factors @ vector, dtype=np.float64)

    def item_similarity(self, index: int) -> npt.NDArray[np.float64]:
        """Cosine similarity between item factor vectors ("customers also bought")."""
        return np.asarray(self._normalized @ self._normalized[index], dtype=np.float64)

    # --- persistence --------------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        buffer = io.BytesIO()
        np.savez_compressed(
            buffer, item_ids=np.array(self.item_ids, dtype=str), item_factors=self.item_factors
        )
        return buffer.getvalue()

    @classmethod
    def from_bytes(cls, payload: bytes, config: AlsConfig) -> AlsModel:
        with np.load(io.BytesIO(payload), allow_pickle=False) as data:
            item_ids = [str(x) for x in data["item_ids"]]
            factors = np.asarray(data["item_factors"], dtype=np.float32)
        return cls(item_ids, factors, config)
