#!/usr/bin/env python3
r"""Parse UFPE Engenharia Eletrônica perfil 4506 PDF into per-discipline JSON.

Input  : pdftotext -layout output of perfil 4506 PDF.
Output : research/ementas/ufpe-ee/json/<CODE>.json + index.json

Each block in the source PDF looks like:

    PERÍODO: 1º
    COMPONENTE CURRICULAR                            TIPO    CH TEÓRICA CH PRÁTICA  CH TOTAL  CRÉDITOS
    MA026- CALCULO DIFERENCIAL E INTEGRAL 1          OBRIG     60          0          60       4.0
    PRÉ-REQUISITO: ...
    CO-REQUISITO:  ...
    [EQUIVALÊNCIA: ...]
    EMENTA:        TEXT...
                   (continuation lines, indented)

Strategy: stream lines, recognise discipline header by leading `^[A-Z]{2}\d{3}-`,
then accumulate the typed sections until next header or PERÍODO marker.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TXT = Path("/tmp/ufpe-ee-perfil.txt")
OUT_DIR = ROOT / "research" / "ementas" / "ufpe-ee" / "json"
RAW_DIR = ROOT / "research" / "ementas" / "ufpe-ee" / "raw"

HEADER_RE = re.compile(
    r"^\s*([A-Z]{2}\d{3})-\s*(.+?)\s+(OBRIG|ELETIVO)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s*$"
)
PERIODO_RE = re.compile(r"^\s*PERÍODO:\s*(\d+)º")
SECTION_RE = re.compile(r"^\s*(PRÉ-REQUISITO|CO-REQUISITO|EQUIVALÊNCIA|EMENTA):\s*(.*)$")


@dataclass
class Discipline:
    code: str
    title: str
    type: str  # OBRIG | ELETIVO
    ch_teorica: int
    ch_pratica: int
    ch_total: int
    creditos: float
    periodo: int | None = None
    pre_requisito: str = ""
    co_requisito: str = ""
    equivalencia: str = ""
    ementa: str = ""

    @property
    def filename(self) -> str:
        return f"{self.code}.json"


def parse(text: str) -> list[Discipline]:
    out: list[Discipline] = []
    cur: Discipline | None = None
    cur_section: str | None = None  # 'pre_requisito' | 'co_requisito' | 'equivalencia' | 'ementa'
    periodo: int | None = None

    section_attr = {
        "PRÉ-REQUISITO": "pre_requisito",
        "CO-REQUISITO": "co_requisito",
        "EQUIVALÊNCIA": "equivalencia",
        "EMENTA": "ementa",
    }

    def flush():
        nonlocal cur, cur_section
        if cur is not None:
            # Normalize whitespace in accumulated text fields.
            for f in ("pre_requisito", "co_requisito", "equivalencia", "ementa"):
                v = getattr(cur, f)
                v = re.sub(r"\s+", " ", v).strip()
                setattr(cur, f, v)
            out.append(cur)
        cur = None
        cur_section = None

    for raw in text.splitlines():
        line = raw.rstrip()

        m_per = PERIODO_RE.match(line)
        if m_per:
            periodo = int(m_per.group(1))
            continue

        m_hdr = HEADER_RE.match(line)
        if m_hdr:
            flush()
            cur = Discipline(
                code=m_hdr.group(1),
                title=m_hdr.group(2).strip(),
                type=m_hdr.group(3),
                ch_teorica=int(m_hdr.group(4)),
                ch_pratica=int(m_hdr.group(5)),
                ch_total=int(m_hdr.group(6)),
                creditos=float(m_hdr.group(7)),
                periodo=periodo,
            )
            cur_section = None
            continue

        if cur is None:
            continue

        m_sec = SECTION_RE.match(line)
        if m_sec:
            cur_section = section_attr[m_sec.group(1)]
            tail = m_sec.group(2).strip()
            if tail:
                setattr(cur, cur_section, (getattr(cur, cur_section) + " " + tail).strip())
            continue

        # Continuation line: append to current section if any, ignore page chrome.
        if cur_section and line.strip():
            # Skip page footers and curricular observation lines that drift in.
            if "SIG@UFPE" in line or "Página " in line:
                continue
            setattr(cur, cur_section, (getattr(cur, cur_section) + " " + line.strip()).strip())

    flush()
    return out


def main(argv: list[str]) -> int:
    src = Path(argv[1]) if len(argv) > 1 else DEFAULT_TXT
    if not src.exists():
        print(f"missing input: {src}", file=sys.stderr)
        return 2
    text = src.read_text(encoding="utf-8")
    disciplines = parse(text)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Persist raw text alongside JSON for diff/audit.
    (RAW_DIR / "perfil-4506.txt").write_text(text, encoding="utf-8")

    index = []
    for d in disciplines:
        (OUT_DIR / d.filename).write_text(
            json.dumps(asdict(d), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        index.append(
            {
                "code": d.code,
                "title": d.title,
                "type": d.type,
                "periodo": d.periodo,
                "ch_total": d.ch_total,
                "creditos": d.creditos,
                "has_ementa": bool(d.ementa),
            }
        )

    (OUT_DIR / "index.json").write_text(
        json.dumps(
            {
                "source": "UFPE Engenharia Eletrônica perfil 4506-1 (PRACAD, 15/05/2021)",
                "perfil": "4506",
                "count": len(disciplines),
                "with_ementa": sum(1 for x in index if x["has_ementa"]),
                "disciplines": index,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"parsed {len(disciplines)} disciplines, {sum(1 for x in index if x['has_ementa'])} with ementa"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
