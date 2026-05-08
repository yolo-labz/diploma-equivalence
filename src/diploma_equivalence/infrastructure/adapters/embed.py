"""Sentence-transformers adapter for the EmbeddingPort."""

from __future__ import annotations

import logging

from diploma_equivalence.domain.models import EmbeddingPort

LOG = logging.getLogger(__name__)


class SentenceTransformersEmbedder(EmbeddingPort):
    def __init__(self, model_name: str = "intfloat/multilingual-e5-large", device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        LOG.info("loading %s on %s ...", self._model_name, self._device)
        self._model = SentenceTransformer(self._model_name, device=self._device)
        self._dimension = self._model.get_sentence_embedding_dimension()
        LOG.info("loaded. dim=%d", self._dimension)

    @property
    def dimension(self) -> int:
        self._load()
        assert self._dimension is not None
        return self._dimension

    def encode(self, texts: list[str]) -> list[list[float]]:
        self._load()
        assert self._model is not None
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 10,
        )
        return [e.tolist() for e in embeddings]
