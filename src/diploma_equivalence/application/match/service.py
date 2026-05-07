"""Match pipeline: compare source and target course units via embeddings."""

from __future__ import annotations

from diploma_equivalence.domain.models import (
    CourseUnit,
    EmbeddingPort,
    Institution,
    MatchReport,
    MatchResult,
    VectorStorePort,
)


class MatchService:
    """Application service: score cross-institution equivalence via nearest-neighbor."""

    def __init__(self, encoder: EmbeddingPort, store: VectorStorePort) -> None:
        self._encoder = encoder
        self._store = store

    def find_matches(
        self,
        source_units: list[CourseUnit],
        target_units: list[CourseUnit],
        top_k: int = 3,
        threshold: float = 0.0,
    ) -> MatchReport:
        self._store.index(
            target_units, self._encoder.encode([u.syllabus or u.title for u in target_units])
        )

        matches: list[MatchResult] = []
        unmatched: list[CourseUnit] = []

        for source in source_units:
            query = self._encoder.encode([source.syllabus or source.title])[0]
            candidates = self._store.search(query, top_k)
            best_target, best_score = max(candidates, key=lambda c: c[1], default=(None, -1.0))
            if best_target is not None and best_score >= threshold:
                explanation = self._explain(source, best_target, best_score)
                matches.append(
                    MatchResult(
                        source=source, target=best_target, score=best_score, explanation=explanation
                    )
                )
            else:
                unmatched.append(source)

        target_codes = {r.target.code for r in matches}
        unmatched_target = [t for t in target_units if t.code not in target_codes]

        return MatchReport(
            source_institution=source_units[0].institution if source_units else Institution.UFPE,
            target_institution=target_units[0].institution if target_units else Institution.UC,
            source_program="",
            target_program="",
            matches=matches,
            unmatched_source=unmatched,
            unmatched_target=unmatched_target,
            generated_at="",
        )

    @staticmethod
    def _explain(source: CourseUnit, target: CourseUnit, score: float) -> str:
        ch_match = (
            source.ch_total and target.ch_total and abs(source.ch_total - target.ch_total) <= 30
        )
        ch_note = "CH" if ch_match else ""
        return f"Semantic similarity: {score:.2f}. {ch_note}".strip()
