"""Content-based similarity: TF-IDF over product text."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer


class ContentModel:
    """Cosine similarity between products based on their text.

    Rows of the TF-IDF matrix are L2-normalised, so a dot product is a cosine similarity.
    Building it for ~1k products takes milliseconds, so it is rebuilt at startup rather
    than persisted.
    """

    def __init__(self, texts: Sequence[str]) -> None:
        if not texts:
            raise ValueError("ContentModel needs at least one product")
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            strip_accents="unicode",
            stop_words="english",
            # Terms on more than half the catalogue ("set", "of") carry no signal.
            max_df=0.5 if len(texts) > 10 else 1.0,
        )
        self.matrix: csr_matrix = self.vectorizer.fit_transform(texts).tocsr()

    @property
    def n_items(self) -> int:
        return int(self.matrix.shape[0])

    def similarity_to(self, index: int) -> npt.NDArray[np.float64]:
        """Cosine similarity of every product to ``index``."""
        sims = (self.matrix @ self.matrix[index].T).toarray().ravel()
        return np.asarray(sims, dtype=np.float64)

    def profile_scores(self, indices: Sequence[int], weights: Sequence[float]) -> npt.NDArray[np.float64]:
        """Similarity of every product to the weighted centroid of a shopper's items."""
        if len(indices) == 0:
            return np.zeros(self.n_items, dtype=np.float64)
        w = np.asarray(weights, dtype=np.float64)
        rows = self.matrix[list(indices)]
        centroid = rows.T @ (w / w.sum())
        return np.asarray(self.matrix @ centroid, dtype=np.float64).ravel()

    def anchors(self, candidates: Sequence[int], history: Sequence[int]) -> list[int]:
        """For each candidate, the history item it is most similar to (for "because you…")."""
        if not history or not candidates:
            return [history[0] if history else -1 for _ in candidates]
        sims = (self.matrix[list(candidates)] @ self.matrix[list(history)].T).toarray()
        best = sims.argmax(axis=1)
        return [int(history[b]) for b in best]


def product_text(title: str) -> str:
    """Text fed to TF-IDF.

    Only the title is used: adding the category name made every product in a big
    category look alike and cut content precision@10 on the holdout from 0.066 to 0.057.
    """
    return title
