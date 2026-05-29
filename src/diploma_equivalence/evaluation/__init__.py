"""Validation harness for the equivalence matcher (discovery Test 1).

Spec 019 / design-thinking `05-test-validation-plan.md`, Test 1 — riskiest
assumption: does the embedding matcher rank the human-equivalent target course
unit inside the top-K for each known equivalence pair?

The harness is encoder-agnostic (it talks to ``EmbeddingPort`` /
``VectorStorePort``), so the real run uses ``multilingual-e5-large`` while tests
use a deterministic fake encoder — no model download required to exercise the logic.
"""

from diploma_equivalence.evaluation.ground_truth import GroundTruthEntry, load_ground_truth
from diploma_equivalence.evaluation.harness import EvalReport, QueryEval, evaluate
from diploma_equivalence.evaluation.metrics import EvalMetrics, compute_metrics

__all__ = [
    "EvalMetrics",
    "EvalReport",
    "GroundTruthEntry",
    "QueryEval",
    "compute_metrics",
    "evaluate",
    "load_ground_truth",
]
