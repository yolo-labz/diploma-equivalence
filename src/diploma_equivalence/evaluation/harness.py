"""Run the equivalence matcher against a ground-truth answer key (Test 1).

Bypasses ``MatchService.find_matches`` on purpose: that collapses to the single
best target per source, but Test 1 needs the full **top-K** ranking to ask
"is the human-equivalent target anywhere in the top K?". So we drive the
``EmbeddingPort`` + ``VectorStorePort`` directly (same adapters the product uses).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from diploma_equivalence.evaluation.metrics import EvalMetrics, compute_metrics

if TYPE_CHECKING:
    from diploma_equivalence.domain.models import CourseUnit, EmbeddingPort, VectorStorePort
    from diploma_equivalence.evaluation.ground_truth import GroundTruth


@dataclass(frozen=True, slots=True)
class QueryEval:
    source_code: str
    source_title: str
    acceptable_target_codes: frozenset[str]
    ranked_target_codes: list[str]  # matcher's top-K (best-first)
    hit_rank: int | None  # 1-based rank of first acceptable target, or None


@dataclass(frozen=True, slots=True)
class EvalReport:
    metrics: EvalMetrics
    queries: list[QueryEval]
    skipped_source_codes: list[str] = field(default_factory=list)  # GT codes absent from source set

    def to_markdown(self) -> str:
        m = self.metrics
        lines = [
            "# Test 1 — Embedding-match validation results",
            "",
            f"- **Verdict:** {'PASS ✅' if m.passed else 'FAIL ❌'}  "
            f"(hit@{m.k} = {m.hit_at_k:.2%}, threshold ≥ {m.pass_ratio:.0%})",
            f"- **n** = {m.n} ground-truth pairs · **MRR** = {m.mrr:.3f} · "
            f"**precision@{m.k}** = {m.precision_at_k:.2%}",
        ]
        if self.skipped_source_codes:
            lines.append(
                f"- ⚠️ skipped {len(self.skipped_source_codes)} GT code(s) "
                f"absent from the source set: {', '.join(self.skipped_source_codes)}"
            )
        lines += ["", "| source | hit rank | acceptable | top-K returned |", "|---|---|---|---|"]
        for q in self.queries:
            rank = str(q.hit_rank) if q.hit_rank else "— miss"
            lines.append(
                f"| `{q.source_code}` {q.source_title[:30]} | {rank} | "
                f"{', '.join(sorted(q.acceptable_target_codes))} | "
                f"{', '.join(q.ranked_target_codes)} |"
            )
        return "\n".join(lines) + "\n"


def evaluate(
    source_units: list[CourseUnit],
    target_units: list[CourseUnit],
    ground_truth: GroundTruth,
    encoder: EmbeddingPort,
    store: VectorStorePort,
    k: int = 5,
    pass_ratio: float = 0.75,
) -> EvalReport:
    """Index targets, run top-K retrieval for each ground-truth source, score it."""
    if not target_units:
        raise ValueError("no target units to index")

    store.index(target_units, encoder.encode([u.syllabus or u.title for u in target_units]))
    source_by_code = {u.code: u for u in source_units}

    queries: list[QueryEval] = []
    skipped: list[str] = []
    per_query: list[tuple[list[str], frozenset[str]]] = []

    for entry in ground_truth.entries:
        src = source_by_code.get(entry.source_code)
        if src is None:
            skipped.append(entry.source_code)
            continue
        query_vec = encoder.encode([src.syllabus or src.title])[0]
        candidates = store.search(query_vec, k)  # list[(CourseUnit, score)], best-first
        ranked_codes = [unit.code for unit, _ in candidates]
        rank = next(
            (i for i, c in enumerate(ranked_codes, start=1) if c in entry.acceptable_target_codes),
            None,
        )
        queries.append(
            QueryEval(
                source_code=entry.source_code,
                source_title=entry.source_title or src.title,
                acceptable_target_codes=entry.acceptable_target_codes,
                ranked_target_codes=ranked_codes,
                hit_rank=rank,
            )
        )
        per_query.append((ranked_codes, entry.acceptable_target_codes))

    if not per_query:
        raise ValueError("no ground-truth source codes matched the provided source units")

    metrics = compute_metrics(per_query, k=k, pass_ratio=pass_ratio)
    return EvalReport(metrics=metrics, queries=queries, skipped_source_codes=skipped)
