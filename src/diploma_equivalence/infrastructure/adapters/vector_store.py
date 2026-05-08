"""In-memory vector store adapter for the VectorStorePort.

For v1: brute-force cosine similarity over pre-computed embeddings.
Replace with pgvector adapter when Postgres is provisioned.
"""

from __future__ import annotations

import numpy as np

from diploma_equivalence.domain.models import CourseUnit, VectorStorePort

LOG = __import__("logging").getLogger(__name__)


class InMemoryVectorStore(VectorStorePort):
    def __init__(self) -> None:
        self._units: list[CourseUnit] = []
        self._matrix: np.ndarray | None = None

    def index(self, units: list[CourseUnit], embeddings: list[list[float]]) -> None:
        self._units = list(units)
        self._matrix = np.array(embeddings, dtype=np.float32)

    def search(self, embedding: list[float], top_k: int) -> list[tuple[CourseUnit, float]]:
        if self._matrix is None or len(self._matrix) == 0:
            return []
        query = np.array(embedding, dtype=np.float32).reshape(1, -1)
        scores = np.dot(self._matrix, query.T).flatten()
        indices = np.argsort(scores)[::-1][:top_k]
        results: list[tuple[CourseUnit, float]] = []
        for idx in indices:
            results.append((self._units[idx], float(scores[idx])))
        return results
