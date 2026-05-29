"""Unit tests for the Test-1 validation harness.

Uses a deterministic bag-of-words ``FakeEncoder`` (L2-normalized so the store's
dot-product == cosine) + the real ``InMemoryVectorStore`` — exercises the harness
logic with zero model download.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import ClassVar

import pytest

from diploma_equivalence.domain.models import CourseUnit, DisciplineType, Institution
from diploma_equivalence.evaluation.ground_truth import (
    GroundTruth,
    GroundTruthEntry,
    load_ground_truth,
)
from diploma_equivalence.evaluation.harness import evaluate
from diploma_equivalence.evaluation.metrics import compute_metrics
from diploma_equivalence.infrastructure.adapters.vector_store import InMemoryVectorStore


class FakeEncoder:
    """Bag-of-words → L2-normalized vector. Shared vocabulary ⇒ high cosine."""

    _VOCAB: ClassVar[list[str]] = [
        "algebra",
        "linear",
        "geometria",
        "calculo",
        "redes",
        "seguranca",
        "comunicacoes",
        "opticas",
        "sistemas",
        "circuitos",
        "eletronica",
    ]

    @property
    def dimension(self) -> int:
        return len(self._VOCAB)

    def encode(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            toks = t.lower().replace("á", "a").replace("ó", "o").replace("ç", "c").split()
            vec = [1.0 if w in toks else 0.0 for w in self._VOCAB]
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


def _uc(code: str, title: str) -> CourseUnit:
    return CourseUnit(Institution.UC, code, title, DisciplineType.OBRIGATORIO, syllabus=title)


def _ufpe(code: str, title: str) -> CourseUnit:
    return CourseUnit(Institution.UFPE, code, title, DisciplineType.OBRIGATORIO, syllabus=title)


@pytest.fixture
def units() -> tuple[list[CourseUnit], list[CourseUnit]]:
    source = [  # UC (João's Coimbra degree)
        _uc("8688", "algebra linear geometria"),
        _uc("90680", "redes seguranca comunicacoes"),
        _uc("86690", "comunicacoes opticas sistemas"),
    ]
    target = [  # UFPE (revalidation destination)
        _ufpe("MA046", "algebra linear"),
        _ufpe("IF987", "redes seguranca sistemas"),
        _ufpe("CIN-OPT", "comunicacoes opticas"),
        _ufpe("DISTRACT", "circuitos eletronica"),
    ]
    return source, target


def test_evaluate_perfect_matches_pass(units):
    source, target = units
    gt = GroundTruth(
        source_institution="UC",
        target_institution="UFPE",
        entries=(
            GroundTruthEntry("8688", frozenset({"MA046"})),
            GroundTruthEntry("90680", frozenset({"IF987"})),
            GroundTruthEntry("86690", frozenset({"CIN-OPT"})),
        ),
    )
    report = evaluate(
        source, target, gt, FakeEncoder(), InMemoryVectorStore(), k=3, pass_ratio=0.75
    )
    assert report.metrics.n == 3
    assert report.metrics.hit_at_k == pytest.approx(1.0)
    assert report.metrics.passed is True
    assert all(q.hit_rank == 1 for q in report.queries)  # true target is rank-1
    assert "PASS" in report.to_markdown()


def test_evaluate_partial_below_threshold_fails(units):
    source, target = units
    # k=1 so only the rank-1 target counts. Only 8688→MA046 is rank-1; the other
    # two answer keys are not the top hit → hit@1 = 1/3 < 0.75 → FAIL verdict.
    gt = GroundTruth(
        "UC",
        "UFPE",
        (
            GroundTruthEntry("8688", frozenset({"MA046"})),  # rank-1 → hit
            GroundTruthEntry("90680", frozenset({"DISTRACT"})),  # rank-1 is IF987 → miss
            GroundTruthEntry("86690", frozenset({"NONEXISTENT"})),  # absent → miss
        ),
    )
    report = evaluate(source, target, gt, FakeEncoder(), InMemoryVectorStore(), k=1)
    assert report.metrics.hit_at_k == pytest.approx(1 / 3)
    assert report.metrics.passed is False


def test_evaluate_skips_absent_source_codes(units):
    source, target = units
    gt = GroundTruth(
        "UC",
        "UFPE",
        (
            GroundTruthEntry("8688", frozenset({"MA046"})),
            GroundTruthEntry("DOES-NOT-EXIST", frozenset({"MA046"})),
        ),
    )
    report = evaluate(source, target, gt, FakeEncoder(), InMemoryVectorStore(), k=3)
    assert report.skipped_source_codes == ["DOES-NOT-EXIST"]
    assert report.metrics.n == 1


def test_compute_metrics_mrr_and_precision():
    # query1: true target at rank 2; query2: true target at rank 1
    per_query = [
        (["A", "TRUE", "B"], frozenset({"TRUE"})),
        (["TRUE", "C"], frozenset({"TRUE"})),
    ]
    m = compute_metrics(per_query, k=3, pass_ratio=0.75)
    assert m.hit_at_k == pytest.approx(1.0)
    assert m.mrr == pytest.approx((0.5 + 1.0) / 2)  # 1/2 + 1/1, averaged
    assert m.passed is True


def test_compute_metrics_empty_raises():
    with pytest.raises(ValueError):
        compute_metrics([], k=5)


def test_load_ground_truth_sample_file():
    sample = Path(__file__).parents[2] / "testdata" / "eval" / "ground-truth.sample.json"
    gt = load_ground_truth(sample)
    assert gt.source_institution and gt.target_institution
    assert len(gt.entries) >= 1
    assert all(e.acceptable_target_codes for e in gt.entries)


def test_load_ground_truth_rejects_malformed(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"pairs": [{"source_code": "X", "acceptable_target_codes": []}]}))
    with pytest.raises(ValueError):
        load_ground_truth(bad)
