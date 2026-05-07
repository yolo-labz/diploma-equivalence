#!/usr/bin/env python3
"""Parse UFPE Engenharia da Computação new-perfil PPC into per-discipline JSON.

Source: ppc-perfil-novo-2024_1.pdf (Drive id 1g4B-soixymLsen3E97miV-xnYY1_k7KZ),
hosted at secgrad.cin.ufpe.br/EngenhariaComp/. pdftotext -layout output.

Per-discipline layout (the 148 EMENTA blocks):

    DADOS DO COMPONENTE
                                          Carga Horária
       Código        Nome              Teórica  Prática   Créd   CHg    Período
                Fundamentos de Programação                                       <- title-above
       CIN                                  45      15       3      60      2    <- meta-row (no title!)
                Imperativa                                                       <- title-below
       ...
    EMENTA
    <ementa free-text>
    OBJETIVO (S) DO COMPONENTE / METODOLOGIA / BIBLIOGRAFIA ...

The "Código" column shows only the department prefix (CIN/DEE/DF/DMAT) for
new-perfil components, OR a full legacy code (FI007/MA026/EL390) for inherited
components. The discipline name lives on the line(s) ABOVE and/or BELOW the
prefix-and-numbers row, never on the same line.

Mapping prefix-only ementas back to legacy IF/MA/ES/ET codes is done via
ANEXO X (Tabela de Equivalência), parsed separately as a name → legacy-codes
map and joined by best-effort name match.

Output:
  research/ementas/ufpe-ec/json/<slug>.json   (one per discipline)
  research/ementas/ufpe-ec/json/index.json
  research/ementas/ufpe-ec/json/equivalence.json
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path.home() / "Documents" / "Notes" / "1. Projects" / "Diploma-Equivalence"
DEFAULT_TXT = Path("/tmp/ufpe-ec-pdfs/ppc-perfil-novo-2024_1.txt")
OUT_DIR = ROOT / "research" / "ementas" / "ufpe-ec" / "json"
RAW_DIR = ROOT / "research" / "ementas" / "ufpe-ec" / "raw"

EMENTA_MARK = re.compile(r"^\s*EMENTA\s*$")

NEXT_SECTION = re.compile(
    r"^\s*(OBJETIVO|METODOLOGIA|AVAL|CONTE[ÚU]DO|BIBLIOGRAF|COMPET|CENTRO"
    r"|ASSINATURA|UNIVERSIDADE|PR[ÓO]-REITORIA|DIRETORIA|PROGRAMA DE COMPONENTE"
    r"|TIPO DE COMPONENTE|STATUS DO COMPONENTE|DADOS DO COMPONENTE)"
)
STATUS_RE = re.compile(r"\b(OBRIGAT[ÓO]RIO|ELETIVO|OPTATIVO)\b")

# Department prefix (no name on same line). Title is on neighbouring lines.
# 5–6 numbers: CHt CHp Créd CHg [Período]
META_PREFIX_BARE_RE = re.compile(
    r"^\s*(?P<prefix>CIN|DEE|DF|DMAT|DEINFO|DCC|DEL|DEQ|DEM|DEMEC|DEM-E|DLET|DECO)\s+"
    r"(?P<cht>\d+)\s+(?P<chp>\d+)\s+(?P<cred>\d+(?:[.,]\d+)?)\s+(?P<chg>\d+)"
    r"(?:\s+(?P<per>\d+))?\s*$"
)
# Legacy code path — same style: code may be alone with numbers, name above/below.
META_LEGACY_BARE_RE = re.compile(
    r"^\s*(?P<code>[A-Z]{2}\d{3,4})\s+"
    r"(?P<cht>\d+)\s+(?P<chp>\d+)\s+(?P<cred>\d+(?:[.,]\d+)?)\s+(?P<chg>\d+)"
    r"(?:\s+(?P<per>\d+))?\s*$"
)
# Sometimes the title DOES sit on the same line (no wrap); keep the "with-title"
# variants as fallback.
META_PREFIX_WITH_TITLE_RE = re.compile(
    r"^\s*(?P<prefix>CIN|DEE|DF|DMAT|DEINFO|DCC|DEL|DEQ|DEM|DEMEC|DEM-E|DLET|DECO)\s+"
    r"(?P<title>[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç][^\d]{3,}?)\s+"
    r"(?P<cht>\d+)\s+(?P<chp>\d+)\s+(?P<cred>\d+(?:[.,]\d+)?)\s+(?P<chg>\d+)"
    r"(?:\s+(?P<per>\d+))?\s*$"
)
META_LEGACY_WITH_TITLE_RE = re.compile(
    r"^\s*(?P<code>[A-Z]{2}\d{3,4})\s+"
    r"(?P<title>[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç][^\d]{3,}?)\s+"
    r"(?P<cht>\d+)\s+(?P<chp>\d+)\s+(?P<cred>\d+(?:[.,]\d+)?)\s+(?P<chg>\d+)"
    r"(?:\s+(?P<per>\d+))?\s*$"
)

# A line is plausibly part of a wrapped title when:
#   - non-empty after strip
#   - starts with a letter
#   - contains no digits
#   - is not a section header / table header / status word
TITLE_LINE_RE = re.compile(r"^\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç][^\d]*$")
TITLE_BANLIST = {
    "código",
    "codigo",
    "nome",
    "carga horária",
    "teórica",
    "prática",
    "obrigatório",
    "obrigatorio",
    "eletivo",
    "optativo",
    "pré-requisitos",
    "pre-requisitos",
    "co-requisitos",
    "co-requisito",
    "requisitos c.h.",
    "ementa",
    "objetivo",
    "metodologia",
    "avaliação",
    "avaliacao",
    "bibliografia básica",
    "bibliografia basica",
    "bibliografia complementar",
    "conteúdo programático",
    "conteudo programatico",
    "competências desejadas",
    "competencias desejadas",
    "centro de informática",
    "dados do componente",
    "dados do componente curricular",
    "tipo de componente",
    "status do componente",
    "tipo de componente curricular",
    "programa de componente",
    "carga horária total",
    "período",
    "periodo",
    "marque um x na opção",
    "marque um x na opcao",
    "x",
    "(s) do componente",
    "diretoria",
    "diretoria de planejamento e desenvolvimento acadêmico",
    "diretoria de planejamento e desenvolvimento academico",
    "pró-reitoria",
    "pro-reitoria",
    "universidade federal de pernambuco",
}


@dataclass
class Discipline:
    code: str | None  # legacy code if metadata row carried one
    prefix: str | None  # department prefix (CIN/DEE/...) otherwise
    title: str
    type: str  # OBRIGATORIO | ELETIVO | OPTATIVO | UNKNOWN
    ch_teorica: int | None
    ch_pratica: int | None
    ch_total: int | None
    creditos: float | None
    periodo: int | None
    ementa: str
    legacy_equiv_codes: list[str] = field(default_factory=list)
    source_line: int = 0


def slugify(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_only = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-").lower()
    return ascii_only[:80] or "unknown"


def is_title_line(ln: str) -> bool:
    s = ln.strip()
    if not s or len(s) < 3:
        return False
    if s.lower() in TITLE_BANLIST:
        return False
    # Skip pure punctuation / X markers / single letters.
    return bool(TITLE_LINE_RE.match(ln))


def collect_title(lines: list[str], meta_idx: int) -> str:
    """Title may sit on line above, below, or both. Glue them in document order."""
    parts: list[str] = []
    # Look up to 2 lines above the meta-row.
    above = []
    for j in range(meta_idx - 1, max(meta_idx - 4, -1), -1):
        ln = lines[j]
        if not ln.strip():
            continue
        if is_title_line(ln):
            above.append(ln.strip())
            continue
        break
    parts.extend(reversed(above))
    # Look up to 2 lines below.
    for j in range(meta_idx + 1, min(meta_idx + 4, len(lines))):
        ln = lines[j]
        if not ln.strip():
            continue
        if is_title_line(ln):
            parts.append(ln.strip())
            continue
        break
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def find_status(lines: list[str], meta_idx: int) -> str:
    """Find STATUS DO COMPONENTE line marked with X above the metadata row."""
    for j in range(meta_idx - 1, max(meta_idx - 30, -1), -1):
        ln = lines[j]
        if "STATUS DO COMPONENTE" in ln:
            # Status is on the SAME line OR the next non-empty line below.
            for k in range(j, min(j + 4, len(lines))):
                ln2 = lines[k]
                if "X" not in ln2:
                    continue
                # The first status word that appears AFTER an X is the chosen one.
                xpos = ln2.find("X")
                tail = ln2[xpos + 1 :]
                m = STATUS_RE.search(tail)
                if m:
                    return m.group(1).replace("Ó", "O")
            break
    return "UNKNOWN"


def parse(text: str) -> list[Discipline]:
    lines = text.splitlines()
    out: list[Discipline] = []

    ementa_idxs = [i for i, ln in enumerate(lines) if EMENTA_MARK.match(ln)]

    for idx in ementa_idxs:
        meta = None
        meta_kind = ""
        meta_idx = -1
        # Walk back ~30 lines to the most recent metadata-row.
        for j in range(idx - 1, max(idx - 35, -1), -1):
            ln = lines[j]
            for rx, kind in (
                (META_LEGACY_WITH_TITLE_RE, "legacy_with_title"),
                (META_LEGACY_BARE_RE, "legacy_bare"),
                (META_PREFIX_WITH_TITLE_RE, "prefix_with_title"),
                (META_PREFIX_BARE_RE, "prefix_bare"),
            ):
                m = rx.match(ln)
                if m:
                    meta = m
                    meta_kind = kind
                    meta_idx = j
                    break
            if meta is not None:
                break

        if meta is None:
            continue

        # Resolve title.
        if meta_kind in ("legacy_with_title", "prefix_with_title"):
            title = re.sub(r"\s+", " ", meta.group("title")).strip()
        else:
            title = collect_title(lines, meta_idx)

        # Skip entries with empty/garbage title.
        if not title or len(title) < 3:
            continue

        status = find_status(lines, meta_idx)

        # Collect ementa text.
        ementa_lines: list[str] = []
        for k in range(idx + 1, min(idx + 80, len(lines))):
            ln = lines[k]
            if NEXT_SECTION.match(ln):
                break
            if ln.strip():
                ementa_lines.append(ln.strip())
        ementa_text = re.sub(r"\s+", " ", " ".join(ementa_lines)).strip()

        code = meta.group("code") if "legacy" in meta_kind else None
        prefix = meta.group("prefix") if "prefix" in meta_kind else None

        d = Discipline(
            code=code,
            prefix=prefix,
            title=title,
            type=status,
            ch_teorica=int(meta.group("cht")),
            ch_pratica=int(meta.group("chp")),
            ch_total=int(meta.group("chg")),
            creditos=float(meta.group("cred").replace(",", ".")),
            periodo=int(meta.group("per")) if meta.group("per") else None,
            ementa=ementa_text,
            source_line=meta_idx + 1,
        )
        out.append(d)

    return out


# ---------------------------------------------------------------------------
# ANEXO X. Tabela de Equivalência parser.
#
# Layout (confirmed at lines ~7853–7969 of source .txt):
#
#   CIN   Matemática Discreta p Computação    60   IF670   Matemática Discreta p Computação    75
#   CIN   Fundamentos de Programação          60
#         Imperativa                                IF669   Introdução à Programação           120
#   CIN   Laboratório de Programação 2        30
#   CIN   Sistemas Digitais                   60
#                                                  IF675   Sistemas Digitais                  75
#   CIN   Laboratório de Sistemas Digitais    30
#
# Key fact: legacy codes (IF___, MA___, ES___, ET___, EL___, FI___) appear in
# the RIGHT-HAND column. The same legacy code may be paired with one OR several
# CIN rows (when several new components collapsed from one legacy component).
# We collect every CIN-row name → legacy_codes association by tracking the
# current "open" CIN row(s) until a legacy code line resolves them.
# ---------------------------------------------------------------------------
def parse_equivalence(text: str) -> dict[str, list[str]]:
    lines = text.splitlines()
    start = end = None
    for i, ln in enumerate(lines):
        if "ANEXO X" in ln and "Equival" in ln:
            start = i
            break
    if start is None:
        return {}
    for i in range(start + 1, len(lines)):
        if re.match(r"^\s*ANEXO [IVX]+\.", lines[i]):
            end = i
            break
    end = end or len(lines)

    code_re = re.compile(r"\b([A-Z]{2}\d{3,4})\b")
    # CIN row: starts with prefix, then name (text, no leading digit), then CH.
    cin_row = re.compile(
        r"^\s*(?P<prefix>CIN|DEE|DF|DMAT)\s+"
        r"(?P<name>[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç][^\d]+?)\s+"
        r"(?P<ch>\d+)"
    )
    # Continuation row: indented title fragment, no prefix, may carry a legacy
    # code further right.
    cont_row = re.compile(r"^\s+(?P<frag>[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç][^\d]+?)(?:\s+\d|$)")

    mapping: dict[str, list[str]] = {}
    open_names: list[str] = []  # list of new-name keys awaiting a legacy code

    for raw in lines[start:end]:
        ln = raw.rstrip()
        if not ln.strip():
            continue
        # 1) Is this a CIN row? Open a new name.
        m_cin = cin_row.match(ln)
        if m_cin:
            name_parts = [m_cin.group("name").strip()]
            # If the same line ALSO has a legacy code on the right, resolve immediately.
            tail = ln[m_cin.end() :]
            tail_codes = code_re.findall(tail)
            if tail_codes:
                key = name_parts[0].lower()
                mapping.setdefault(key, [])
                for c in tail_codes:
                    if c not in mapping[key]:
                        mapping[key].append(c)
            else:
                open_names.append(name_parts[0])
            continue
        # 2) Continuation: maybe extends the most recent open name AND/OR carries
        # a legacy code that resolves all currently open names.
        codes = code_re.findall(ln)
        # Strip the legacy-code half to get the title fragment, if any.
        # Simpler: use cont_row to grab the fragment if line starts with text.
        m_cont = cont_row.match(ln)
        if m_cont and open_names:
            # Append the continuation fragment to the LAST open name.
            frag = m_cont.group("frag").strip()
            # Only append if it's not the legacy-name (legacy-names sit AFTER
            # the legacy code; if the line matches "<frag> ... <CODE> <name>" the
            # frag belongs to the new name on the LEFT).
            # Heuristic: if line's first non-space token is the fragment AND no
            # CIN/DEE prefix, treat as continuation.
            open_names[-1] = (open_names[-1] + " " + frag).strip()
        if codes:
            for name in open_names:
                key = name.lower().strip()
                mapping.setdefault(key, [])
                for c in codes:
                    if c not in mapping[key]:
                        mapping[key].append(c)
            open_names = []
    return mapping


def main(argv: list[str]) -> int:
    src = Path(argv[1]) if len(argv) > 1 else DEFAULT_TXT
    if not src.exists():
        print(f"missing input: {src}", file=sys.stderr)
        return 2

    text = src.read_text(encoding="utf-8")
    disciplines = parse(text)
    equivalence = parse_equivalence(text)

    # Cross-reference: best-effort name match, both directions.
    for d in disciplines:
        key = d.title.lower().strip()
        codes = equivalence.get(key, [])
        if not codes:
            # Substring match (either direction), longest match wins.
            best_k, best_len = None, 0
            for k in equivalence:
                if (k in key or key in k) and len(k) > best_len:
                    best_k, best_len = k, len(k)
            if best_k:
                codes = equivalence[best_k]
        d.legacy_equiv_codes = codes

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "ppc-perfil-novo-2024_1.txt").write_text(text, encoding="utf-8")

    # Dedup by (title, periodo).
    seen: dict[tuple[str, int | None], Discipline] = {}
    for d in disciplines:
        k = (d.title.lower(), d.periodo)
        if k not in seen:
            seen[k] = d
    deduped = list(seen.values())

    # Clear stale per-discipline files from previous parser runs.
    for f in OUT_DIR.glob("*.json"):
        f.unlink()

    index = []
    for d in deduped:
        slug = slugify(d.title) or (d.code or "unknown")
        fname = f"{slug}.json"
        (OUT_DIR / fname).write_text(
            json.dumps(asdict(d), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        index.append(
            {
                "slug": slug,
                "code": d.code,
                "prefix": d.prefix,
                "title": d.title,
                "type": d.type,
                "periodo": d.periodo,
                "ch_total": d.ch_total,
                "creditos": d.creditos,
                "has_ementa": bool(d.ementa),
                "legacy_equiv_codes": d.legacy_equiv_codes,
            }
        )

    ementa_blocks = sum(1 for ln in text.splitlines() if EMENTA_MARK.match(ln))

    (OUT_DIR / "index.json").write_text(
        json.dumps(
            {
                "source": "UFPE Engenharia da Computação new-perfil PPC",
                "source_url": "https://secgrad.cin.ufpe.br/EngenhariaComp/",
                "drive_id": "1g4B-soixymLsen3E97miV-xnYY1_k7KZ",
                "filename": "ppc-perfil-novo-2024_1.pdf",
                "ementa_blocks_in_pdf": ementa_blocks,
                "anchored": len(disciplines),
                "deduped": len(deduped),
                "with_ementa": sum(1 for x in index if x["has_ementa"]),
                "with_legacy_codes": sum(1 for x in index if x["legacy_equiv_codes"]),
                "disciplines": index,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    (OUT_DIR / "equivalence.json").write_text(
        json.dumps(
            {
                "source_section": "ANEXO X. Tabela de Equivalência",
                "count": len(equivalence),
                "mapping": equivalence,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"ementa blocks: {ementa_blocks}; "
        f"anchored {len(disciplines)}; "
        f"unique {len(deduped)}; "
        f"with-ementa {sum(1 for x in index if x['has_ementa'])}; "
        f"legacy-mapped {sum(1 for x in index if x['legacy_equiv_codes'])}; "
        f"equivalence entries {len(equivalence)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
