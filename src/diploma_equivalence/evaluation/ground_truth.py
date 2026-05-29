"""Ground-truth schema + loader for the equivalence-matcher validation.

A ground-truth file is the human-decided answer key: for each SOURCE course unit
(e.g. a Universidade de Coimbra discipline João took), which TARGET course unit(s)
(e.g. UFPE disciplines) a qualified human evaluator deemed equivalent.

This is exactly the data Test 1 needs and is currently the project's critical gap
(the matcher runs, but its accuracy is unmeasured against real revalidação outcomes).
Collect it from: João's own revalidação verdict (n=1), CITi-recruited UFPE Eng
students (cohort B), and any real cases surfaced via the UFPE secretariat.

JSON format (see ``testdata/eval/ground-truth.sample.json``)::

    {
      "source_institution": "UC",
      "target_institution": "UFPE",
      "notes": "free text — provenance of these decisions",
      "pairs": [
        {
          "source_code": "8688",
          "source_title": "Álgebra Linear e Geometria Analítica",
          "acceptable_target_codes": ["MA046"],
          "decided_by": "UFPE evaluator | student-validator | applicant",
          "confidence": "granted | likely | guess"
        }
      ]
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GroundTruthEntry:
    """One human-decided equivalence: source unit -> acceptable target unit(s)."""

    source_code: str
    acceptable_target_codes: frozenset[str]
    source_title: str = ""
    decided_by: str = ""
    confidence: str = "guess"  # granted | likely | guess


@dataclass(frozen=True, slots=True)
class GroundTruth:
    source_institution: str
    target_institution: str
    entries: tuple[GroundTruthEntry, ...]
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("ground truth has no pairs")


def load_ground_truth(path: str | Path) -> GroundTruth:
    """Parse + validate a ground-truth JSON file.

    Raises ``ValueError`` on a malformed file rather than silently degrading —
    a bad answer key would produce meaningless metrics, so fail loud.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    pairs = raw.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError(f"{path}: missing/empty 'pairs' array")

    entries: list[GroundTruthEntry] = []
    seen: set[str] = set()
    for i, p in enumerate(pairs):
        code = str(p.get("source_code", "")).strip()
        targets = [str(c).strip() for c in p.get("acceptable_target_codes", []) if str(c).strip()]
        if not code:
            raise ValueError(f"{path}: pair #{i} missing source_code")
        if not targets:
            raise ValueError(f"{path}: pair #{i} ({code}) has no acceptable_target_codes")
        if code in seen:
            raise ValueError(f"{path}: duplicate source_code {code!r}")
        seen.add(code)
        entries.append(
            GroundTruthEntry(
                source_code=code,
                acceptable_target_codes=frozenset(targets),
                source_title=str(p.get("source_title", "")),
                decided_by=str(p.get("decided_by", "")),
                confidence=str(p.get("confidence", "guess")),
            )
        )

    return GroundTruth(
        source_institution=str(raw.get("source_institution", "")),
        target_institution=str(raw.get("target_institution", "")),
        entries=tuple(entries),
        notes=str(raw.get("notes", "")),
    )
