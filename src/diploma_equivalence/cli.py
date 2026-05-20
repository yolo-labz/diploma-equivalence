"""CLI: load → embed → match → report.

Usage:
  uv run diploma-equivalence-match --source UC --target UFPE
  uv run diploma-equivalence-match --source UFPE --target UC
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from diploma_equivalence.application.embed.service import EmbeddingService
from diploma_equivalence.application.match.service import MatchService
from diploma_equivalence.domain.models import Institution, MatchReport
from diploma_equivalence.infrastructure.adapters.embed import SentenceTransformersEmbedder
from diploma_equivalence.infrastructure.adapters.loader import load_all
from diploma_equivalence.infrastructure.adapters.vector_store import InMemoryVectorStore

LOG = logging.getLogger(__name__)


def _institution(s: str) -> Institution:
    s = s.upper()
    if s in ("UC", "COIMBRA"):
        return Institution.UC
    if s in ("UFPE", "PERNAMBUCO"):
        return Institution.UFPE
    raise ValueError(f"unknown institution: {s}")


def _format_report(report: MatchReport, top_n: int = 5) -> str:
    lines: list[str] = []
    lines.append(
        f"# Auto-Match Report: {report.source_institution.value} → {report.target_institution.value}"
    )
    lines.append(f"Generated: {datetime.now(UTC).isoformat()}")
    lines.append(f"Source units: {len(report.matches) + len(report.unmatched_source)}")
    lines.append(
        f"Target units: {len({m.target.code for m in report.matches}) + len(report.unmatched_target)}"
    )
    lines.append(f"Matches (threshold ≥ 0.0): {len(report.matches)}")
    lines.append("")

    lines.append("## Top Matches")
    lines.append("| # | Source | Target | Score | Explanation |")
    lines.append("|---|--------|--------|-------|-------------|")
    sorted_matches = sorted(report.matches, key=lambda m: m.score, reverse=True)
    for i, m in enumerate(sorted_matches[:top_n], 1):
        lines.append(
            f"| {i} | {m.source.title} ({m.source.code}) | "
            f"{m.target.title} ({m.target.code}) | "
            f"{m.score:.3f} | {m.explanation or '—'} |"
        )

    if report.unmatched_source:
        lines.append("")
        lines.append(f"## Unmatched Source ({len(report.unmatched_source)})")
        for u in sorted(report.unmatched_source, key=lambda x: x.title):
            lines.append(f"- {u.title} ({u.code})")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="diploma-equivalence match pipeline")
    ap.add_argument(
        "--source",
        type=_institution,
        default=Institution.UFPE,
        help="Source institution (UC or UFPE)",
    )
    ap.add_argument(
        "--target",
        type=_institution,
        default=Institution.UC,
        help="Target institution (UC or UFPE)",
    )
    ap.add_argument(
        "--model", default="intfloat/multilingual-e5-large", help="sentence-transformers model"
    )
    ap.add_argument("--top-k", type=int, default=3, help="candidates per unit")
    ap.add_argument("--threshold", type=float, default=0.0, help="minimum cosine similarity")
    ap.add_argument("--device", default="cpu", help="embedding device (cpu, cuda, mps)")
    ap.add_argument(
        "--vault",
        default=None,
        help="path to vault project dir (default: ~/Documents/Notes/1. Projects/Diploma-Equivalence)",
    )
    ap.add_argument(
        "--output",
        "-o",
        default=None,
        help="write report to file (default: stdout)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="output raw JSON instead of markdown",
    )
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    LOG.info("loading ementas from vault ...")
    all_units = load_all(args.vault)
    source_units = [u for u in all_units if u.institution == args.source]
    target_units = [u for u in all_units if u.institution == args.target]
    LOG.info("source=%d target=%d", len(source_units), len(target_units))

    if not source_units or not target_units:
        LOG.error("need at least one unit per institution")
        return 1

    LOG.info("loading embedding model: %s", args.model)
    encoder = SentenceTransformersEmbedder(model_name=args.model, device=args.device)
    store = InMemoryVectorStore()

    embed_svc = EmbeddingService(encoder)
    match_svc = MatchService(encoder, store)

    LOG.info("indexing %d target units ...", len(target_units))
    target_emb = embed_svc.embed(target_units)
    store.index(target_units, target_emb)

    LOG.info("scoring %d source units ...", len(source_units))
    report = match_svc.find_matches(
        source_units=source_units,
        target_units=target_units,
        top_k=args.top_k,
        threshold=args.threshold,
    )

    if args.json_output:
        out = _report_to_dict(report)
        output = json.dumps(out, ensure_ascii=False, indent=2)
    else:
        output = _format_report(report, top_n=len(report.matches))

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        LOG.info("report written to %s", args.output)
    else:
        print(output)

    return 0


def _report_to_dict(report: MatchReport) -> dict:
    return {
        "source": report.source_institution.value,
        "target": report.target_institution.value,
        "generated_at": datetime.now(UTC).isoformat(),
        "matches": [
            {
                "source_code": m.source.code,
                "source_title": m.source.title,
                "target_code": m.target.code,
                "target_title": m.target.title,
                "score": round(m.score, 4),
                "explanation": m.explanation,
            }
            for m in report.matches
        ],
        "unmatched_source": [{"code": u.code, "title": u.title} for u in report.unmatched_source],
        "unmatched_target": [{"code": u.code, "title": u.title} for u in report.unmatched_target],
    }


if __name__ == "__main__":
    raise SystemExit(main())
