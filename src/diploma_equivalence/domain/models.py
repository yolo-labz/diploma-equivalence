"""Domain models and ports (hexagonal architecture).

This layer defines what the system IS, not how it works.
Infrastructure adapters implement these ports.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Protocol


class DisciplineType(enum.StrEnum):
    OBRIGATORIO = "OBRIGATORIO"
    ELETIVO = "ELETIVO"
    OPTATIVO = "OPTATIVO"


class Institution(enum.StrEnum):
    UC = "Universidade de Coimbra"
    UFPE = "Universidade Federal de Pernambuco"


@dataclass(frozen=True, slots=True)
class CourseUnit:
    """A single course unit (disciplina/materia) from a university curriculum."""

    institution: Institution
    code: str
    title: str
    type: DisciplineType
    ch_theoretical: int | None = None
    ch_practical: int | None = None
    ch_total: int | None = None
    credits: int | None = None
    period: int | None = None
    syllabus: str | None = None  # ementa
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MatchResult:
    """A ranked match between a source and target course unit."""

    source: CourseUnit
    target: CourseUnit
    score: float  # 0..1, higher = better match
    explanation: str | None = None


@dataclass(frozen=True, slots=True)
class MatchReport:
    """A full equivalence report for one degree program."""

    source_institution: Institution
    target_institution: Institution
    source_program: str
    target_program: str
    matches: list[MatchResult]
    unmatched_source: list[CourseUnit]
    unmatched_target: list[CourseUnit]
    generated_at: str


class EmbeddingPort(Protocol):
    """Port: generate vector embeddings from text."""

    def encode(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimension(self) -> int: ...


class VectorStorePort(Protocol):
    """Port: store and retrieve vectors by similarity."""

    def index(self, units: list[CourseUnit], embeddings: list[list[float]]) -> None: ...

    def search(self, embedding: list[float], top_k: int) -> list[tuple[CourseUnit, float]]: ...


class CourseUnitRepository(Protocol):
    """Port: persist and query course units."""

    def save_many(self, units: list[CourseUnit]) -> None: ...

    def list_by_institution(self, institution: Institution) -> list[CourseUnit]: ...

    def find_by_code(self, institution: Institution, code: str) -> CourseUnit | None: ...


class IngestPort(Protocol):
    """Port: fetch raw ementa data from external sources."""

    def fetch(self) -> list[dict[str, Any]]: ...
