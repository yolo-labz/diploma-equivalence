"""Embedding pipeline: generate vector representations from ementa text."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from diploma_equivalence.domain.models import CourseUnit, EmbeddingPort


class EmbeddingService:
    """Application service: orchestrate embedding generation."""

    def __init__(self, encoder: EmbeddingPort) -> None:
        self._encoder = encoder

    def embed(self, units: list[CourseUnit]) -> list[list[float]]:
        if not units:
            return []
        texts = [unit.syllabus or f"{unit.title}. {unit.institution}" for unit in units]
        return self._encoder.encode(texts)

    @property
    def dimension(self) -> int:
        return self._encoder.dimension
