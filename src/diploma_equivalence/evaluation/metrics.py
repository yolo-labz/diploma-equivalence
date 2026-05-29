"""Retrieval metrics + the Test-1 build/no-build verdict.

Per design-thinking ``05-test-validation-plan.md``: the green-light rule is
"actual-granting target appears in top-K for >= PASS_RATIO of cases". The original
plan used top-5 over n=4 cases (>= 3/4). Both K and the pass ratio are parameters
here so the rule can scale with cohort size without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvalMetrics:
    n: int  # number of evaluated ground-truth pairs
    k: int  # top-K cutoff
    hit_at_k: float  # fraction with >=1 acceptable target in top-K
    mrr: float  # mean reciprocal rank of the first acceptable target (0 if absent)
    precision_at_k: float  # mean (acceptable in top-K) / K
    pass_ratio: float  # threshold for the Test-1 verdict
    passed: bool  # hit_at_k >= pass_ratio

    def summary(self) -> str:
        verdict = (
            "PASS ✅ → greenlight build spec 020"
            if self.passed
            else "FAIL ❌ → revisit model/schema/weighting before code"
        )
        return (
            f"n={self.n}  k={self.k}  hit@{self.k}={self.hit_at_k:.2%}  "
            f"MRR={self.mrr:.3f}  P@{self.k}={self.precision_at_k:.2%}  "
            f"(threshold hit@{self.k}>={self.pass_ratio:.0%})  {verdict}"
        )


def _first_hit_rank(ranked_target_codes: list[str], acceptable: frozenset[str]) -> int | None:
    """1-based rank of the first acceptable target in the ranked list, or None."""
    for i, code in enumerate(ranked_target_codes, start=1):
        if code in acceptable:
            return i
    return None


def compute_metrics(
    per_query: list[tuple[list[str], frozenset[str]]],
    k: int = 5,
    pass_ratio: float = 0.75,
) -> EvalMetrics:
    """Compute hit@k / MRR / precision@k + the Test-1 verdict.

    ``per_query``: one ``(ranked_target_codes, acceptable_target_codes)`` per
    ground-truth source. ``ranked_target_codes`` is the matcher's ranking
    (best-first); it is truncated to K here defensively.
    """
    n = len(per_query)
    if n == 0:
        raise ValueError("no queries to evaluate")
    if k < 1:
        raise ValueError("k must be >= 1")

    hits = 0
    rr_sum = 0.0
    prec_sum = 0.0
    for ranked, acceptable in per_query:
        topk = ranked[:k]
        rank = _first_hit_rank(topk, acceptable)
        if rank is not None:
            hits += 1
            rr_sum += 1.0 / rank
        prec_sum += sum(1 for c in topk if c in acceptable) / k

    hit_at_k = hits / n
    return EvalMetrics(
        n=n,
        k=k,
        hit_at_k=hit_at_k,
        mrr=rr_sum / n,
        precision_at_k=prec_sum / n,
        pass_ratio=pass_ratio,
        passed=hit_at_k >= pass_ratio,
    )
