"""CLI runner for the Test-1 validation harness (real data + real model).

Mirrors ``cli.py``'s loader/adapter wiring, but instead of producing a match
report it scores the matcher against a human ground-truth answer key and emits
the Test-1 verdict. Exits non-zero on FAIL so it can gate a build-spec decision.

    diploma-eval --vault . --source UC --target UFPE \
        --ground-truth testdata/eval/ground-truth.sample.json \
        --k 5 --pass-ratio 0.75 --out research/ementas/test1-RESULTS.md
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from diploma_equivalence.domain.models import Institution
from diploma_equivalence.evaluation.ground_truth import load_ground_truth
from diploma_equivalence.evaluation.harness import evaluate

LOG = logging.getLogger(__name__)


def _institution(s: str) -> Institution:
    for inst in Institution:
        if s.upper() in (inst.name, inst.value.upper()):
            return inst
    raise ValueError(f"unknown institution: {s}")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Test-1 embedding-match validation harness")
    ap.add_argument("--vault", default=".", help="dir the loader reads ementas from")
    ap.add_argument(
        "--source", type=_institution, default=Institution.UC, help="source institution"
    )
    ap.add_argument(
        "--target", type=_institution, default=Institution.UFPE, help="target institution"
    )
    ap.add_argument("--ground-truth", required=True, help="path to ground-truth JSON answer key")
    ap.add_argument("--k", type=int, default=5, help="top-K cutoff (Test 1 uses 5)")
    ap.add_argument(
        "--pass-ratio", type=float, default=0.75, help="hit@k threshold to PASS (3/4=0.75)"
    )
    ap.add_argument("--model", default="intfloat/multilingual-e5-large", help="embedding model")
    ap.add_argument("--device", default="cpu", help="cpu | cuda | mps")
    ap.add_argument("--out", default="", help="write RESULTS.md here (default: stdout only)")
    args = ap.parse_args(argv)

    # Imported lazily so the (heavy) model adapter loads only on a real run, not at import.
    from diploma_equivalence.infrastructure.adapters.embed import SentenceTransformersEmbedder
    from diploma_equivalence.infrastructure.adapters.loader import load_all
    from diploma_equivalence.infrastructure.adapters.vector_store import InMemoryVectorStore

    gt = load_ground_truth(args.ground_truth)
    all_units = load_all(args.vault)
    source_units = [u for u in all_units if u.institution == args.source]
    target_units = [u for u in all_units if u.institution == args.target]
    if not source_units or not target_units:
        LOG.error(
            "need >=1 unit per institution (source=%d target=%d)",
            len(source_units),
            len(target_units),
        )
        return 2

    LOG.info("loading model %s ...", args.model)
    encoder = SentenceTransformersEmbedder(model_name=args.model, device=args.device)
    report = evaluate(
        source_units,
        target_units,
        gt,
        encoder,
        InMemoryVectorStore(),
        k=args.k,
        pass_ratio=args.pass_ratio,
    )

    LOG.info("\n%s", report.metrics.summary())
    if args.out:
        Path(args.out).write_text(report.to_markdown(), encoding="utf-8")
        LOG.info("wrote %s", args.out)

    return 0 if report.metrics.passed else 1


if __name__ == "__main__":
    sys.exit(main())
