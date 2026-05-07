#!/usr/bin/env python3
"""Extract UFPE Engenharia da Computação discipline codes from the secgrad
Google Sites code list (HTML with embedded JSON metadata).

Input  : raw HTML of https://secgrad.cin.ufpe.br/EngenhariaComp/codigos-das-disciplinas
Output : research/ementas/ufpe-ec/json/codes.json

The code list does not contain ementa text — only codes + titles + nature
(OBRIGATÓRIO/ELETIVO). Ementa resolution happens in a follow-up pass against
SIG@UFPE / cin.ufpe.br.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path.home() / "Documents" / "Notes" / "1. Projects" / "Diploma-Equivalence"
DEFAULT_HTML = Path("/tmp/ufpe-ec-codigos.html")
OUT_DIR = ROOT / "research" / "ementas" / "ufpe-ec" / "json"
RAW_DIR = ROOT / "research" / "ementas" / "ufpe-ec" / "raw"

# `XX### - TITLE OBRIGATÓRIO` or `... ELETIVO` patterns embedded in the HTML.
ENTRY_RE = re.compile(
    r"\b([A-Z]{2}\d{3})\s*[-–]\s*([^<>\n\r]+?)\s+(OBRIGAT[ÓO]RIO|ELETIV[OA])\b",
    re.IGNORECASE,
)
CODE_RE = re.compile(r"\b([A-Z]{2}\d{3})\b")


def parse(html: str) -> list[dict]:
    seen: dict[str, dict] = {}
    for m in ENTRY_RE.finditer(html):
        code = m.group(1).upper()
        title = re.sub(r"\s+", " ", m.group(2)).strip(" -–|")
        nature = m.group(3).upper().replace("OBRIGATORIO", "OBRIGATÓRIO")
        if code in seen:
            continue
        seen[code] = {
            "code": code,
            "title": title,
            "type": "OBRIG" if "OBRIG" in nature else "ELETIVO",
        }

    # Surface any code present without a clean title/nature match, so we can
    # follow up manually instead of silently dropping.
    for m in CODE_RE.finditer(html):
        code = m.group(1).upper()
        if code not in seen:
            seen[code] = {"code": code, "title": "", "type": "UNKNOWN"}

    return sorted(seen.values(), key=lambda d: d["code"])


def main(argv: list[str]) -> int:
    src = Path(argv[1]) if len(argv) > 1 else DEFAULT_HTML
    if not src.exists():
        print(f"missing input: {src}", file=sys.stderr)
        return 2
    html = src.read_text(encoding="utf-8", errors="replace")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "codigos-das-disciplinas.html").write_text(html, encoding="utf-8")

    entries = parse(html)
    matched = [e for e in entries if e["type"] != "UNKNOWN"]
    unknown = [e for e in entries if e["type"] == "UNKNOWN"]

    out = {
        "source": "https://secgrad.cin.ufpe.br/EngenhariaComp/codigos-das-disciplinas",
        "count": len(entries),
        "with_metadata": len(matched),
        "unknown": [e["code"] for e in unknown],
        "disciplines": entries,
    }
    (OUT_DIR / "codes.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"extracted {len(entries)} codes ({len(matched)} with metadata, {len(unknown)} bare)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
