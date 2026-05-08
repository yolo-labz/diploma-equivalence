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
# 1-5 numbers: CHt CHp Créd CHg [Período]. Some fields may be blank (single digit for CH total, etc).
META_PREFIX_BARE_RE = re.compile(
    r"^\s*(?P<prefix>CIN|DEE|DF|DMAT|DEINFO|DCC|DEL|DEQ|DEM|DEMEC|DEM-E|DLET|DECO)\s+"
    r"(?:(?P<cht>\d+)\s+)?"
    r"(?:(?P<chp>\d+)\s+)?"
    r"(?:(?P<cred>\d+(?:[.,]\d+)?)\s+)?"
    r"(?P<chg>\d+)"
    r"(?:\s+(?P<per>\d+))?\s*$"
)
# Legacy code path — same style: code may be alone with numbers, name above/below.
META_LEGACY_BARE_RE = re.compile(
    r"^\s*(?P<code>[A-Z]{2}\d{3,4})\s+"
    r"(?:(?P<cht>\d+)\s+)?"
    r"(?:(?P<chp>\d+)\s+)?"
    r"(?:(?P<cred>\d+(?:[.,]\d+)?)\s+)?"
    r"(?P<chg>\d+)"
    r"(?:\s+(?P<per>\d+))?\s*$"
)
# Sometimes the title DOES sit on the same line (no wrap); keep the "with-title"
# variants as fallback. Title may contain digits (e.g. "Cálculo Diferencial e
# Integral 2") — we delimit it from the number columns by requiring a
# 2+-space gap followed by a digit.
META_PREFIX_WITH_TITLE_RE = re.compile(
    r"^\s*(?P<prefix>CIN|DEE|DF|DMAT|DEINFO|DCC|DEL|DEQ|DEM|DEMEC|DEM-E|DLET|DECO)\s+"
    r"(?P<title>[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç].+?)\s{2,}"
    r"(?:(?P<cht>\d+)\s+)?"
    r"(?:(?P<chp>\d+)\s+)?"
    r"(?:(?P<cred>\d+(?:[.,]\d+)?)\s+)?"
    r"(?P<chg>\d+)"
    r"(?:\s+(?P<per>\d+))?\s*$"
)
META_LEGACY_WITH_TITLE_RE = re.compile(
    r"^\s*(?P<code>[A-Z]{2}\d{3,4})\s+"
    r"(?P<title>[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç].+?)\s{2,}"
    r"(?:(?P<cht>\d+)\s+)?"
    r"(?:(?P<chp>\d+)\s+)?"
    r"(?:(?P<cred>\d+(?:[.,]\d+)?)\s+)?"
    r"(?P<chg>\d+)"
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
    # Column header fragments that get picked up as title text
    "nº. de créditos",
    "no. de creditos",
    "nº de créditos",
    "no de creditos",
    "c. h. global",
    "ch global",
    "carga horária semanal",
    "código nome",
    "codigo nome",
    "c.h. global",
    "período teórica prática",
    "teórica prática",
    "tópicos avançados em",
}

# Substring fragments that flag a line as a column-header / boilerplate row,
# regardless of whether the line is an exact match for any TITLE_BANLIST entry.
# Used by is_title_line() with a normalized-whitespace lowercase comparison so
# multi-word header rows like
#   "Código  Nome  Nº. de Créditos  C. H. Global  Período"
# are rejected even when they don't match any banlist entry verbatim.
HEADER_FRAGMENTS: tuple[str, ...] = (
    "código nome",
    "codigo nome",
    "nº. de créditos",
    "no. de creditos",
    "nº de créditos",
    "no de creditos",
    "c. h. global",
    "c.h. global",
    "ch global",
    "carga horária semanal",
    "carga horária",
    "carga horaria",
    "período teórica",
    "periodo teorica",
    "teórica prática",
    "teorica pratica",
    "pré-requisitos",
    "pre-requisitos",
    "co-requisitos",
    "co-requisito",
    "requisitos c.h.",
    "marque um x",
    "dados do componente",
    "tipo de componente",
    "status do componente",
    "programa de componente",
    "diretoria de planejamento",
    "diretoria de desenvolvimento",
    "pró-reitoria",
    "pro-reitoria",
    "universidade federal",
    "centro de informática",
    "centro de informatica",
)


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
    s_norm = re.sub(r"\s+", " ", s).lower()
    if s_norm in TITLE_BANLIST:
        return False
    if any(frag in s_norm for frag in HEADER_FRAGMENTS):
        return False
    # Skip pure punctuation / X markers / single letters.
    return bool(TITLE_LINE_RE.match(ln))


def collect_title(lines: list[str], meta_idx: int) -> str:
    """Title may sit on line above, below, or both. Glue them in document order.

    Stops at the first empty line in either direction so that out-of-band
    rows (column headers above the title block, pré-requisitos rows below
    the title block) cannot bleed into the title.
    """
    parts: list[str] = []
    above: list[str] = []
    for j in range(meta_idx - 1, max(meta_idx - 4, -1), -1):
        ln = lines[j]
        if not ln.strip():
            break
        if is_title_line(ln):
            above.append(ln.strip())
            continue
        break
    parts.extend(reversed(above))
    for j in range(meta_idx + 1, min(meta_idx + 4, len(lines))):
        ln = lines[j]
        if not ln.strip():
            break
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
            ch_teorica=int(meta.group("cht")) if meta.group("cht") else None,
            ch_pratica=int(meta.group("chp")) if meta.group("chp") else None,
            ch_total=int(meta.group("chg")),
            creditos=float(meta.group("cred").replace(",", ".")) if meta.group("cred") else None,
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
    # Skip TOC-level ANEXO entries — find the one with actual table content.
    for i, ln in enumerate(lines):
        if "QUADRO DE EQUIVALÊNCIA" in ln:
            start = i - 1  # ANEXO X line is right above
            break
    if start is None:
        return {}
    for i in range(start + 1, len(lines)):
        ln = lines[i]
        if re.match(r"^\s*ANEXO [IVX]+\.", ln) or re.match(r"^\s*TABELA DE EQUIVAL", ln):
            end = i
            break
    end = end or len(lines)

    code_re = re.compile(r"\b([A-Z]{2}\d{3,4})\b")
    dept_prefixes = r"CIN|DEE|DF|DMAT|DCC|DEL|DEQ|DEM|DEMEC|DEM-E|DLET|DECO|DEINFO"

    # CIN/prefix row: prefix, optional name, then CH.
    # Some rows have only prefix+CH (name wraps from later lines).
    cin_row_ch_only = re.compile(rf"^\s*(?P<prefix>{dept_prefixes})\s+(?P<ch>\d+)(?:\s|$)")
    cin_row_with_name = re.compile(
        rf"^\s*(?P<prefix>{dept_prefixes})\s+"
        r"(?P<name>[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç][^\d]{3,}?)\s{2,}"
        r"(?P<ch>\d+)"
    )

    mapping: dict[str, list[str]] = {}
    name_buf: list[str] = []  # accumulating new-perfil name parts
    pending_legacy: list[str] = []  # legacy codes that need to resolve
    in_name = False  # whether we're inside a new-perfil name accumulation

    for raw in lines[start:end]:
        ln = raw.rstrip()
        if not ln.strip():
            if in_name and name_buf:
                name_buf.append(" ")  # blank line = word separator
            continue

        codes_on_line = code_re.findall(ln)
        has_prefix = bool(re.match(rf"^\s*(?:{dept_prefixes})\s+", ln))

        if has_prefix:
            # Flush previous entry before opening a new one.
            if in_name and name_buf:
                key = " ".join(name_buf).strip()
                key = re.sub(r"\s+", " ", key).lower()
                if key and pending_legacy:
                    mapping.setdefault(key, [])
                    for c in pending_legacy:
                        if c not in mapping[key]:
                            mapping[key].append(c)
                elif codes_on_line:
                    # self-contained: name + CH + legacy code on same line
                    m_name = cin_row_with_name.match(ln)
                    if m_name and codes_on_line:
                        key = m_name.group("name").strip().lower()
                        mapping.setdefault(key, [])
                        for c in codes_on_line:
                            if c not in mapping[key]:
                                mapping[key].append(c)

            name_buf = []
            pending_legacy = []
            in_name = False

            # Try name+CH first, then CH-only.
            m_name = cin_row_with_name.match(ln)
            if m_name:
                name_buf.append(m_name.group("name").strip())
                in_name = True
                # Legacy codes on same line?
                tail = ln[m_name.end() :]
                tail_codes = code_re.findall(tail)
                if tail_codes:
                    key = m_name.group("name").strip().lower()
                    mapping.setdefault(key, [])
                    for c in tail_codes:
                        if c not in mapping[key]:
                            mapping[key].append(c)
                    in_name = False
                    name_buf = []
                else:
                    pending_legacy = []
            else:
                m_ch = cin_row_ch_only.match(ln)
                if m_ch:
                    in_name = True
                    name_buf = []
                    pending_legacy = codes_on_line or []
            continue

        # Not a prefix row — could be name continuation or legacy-code-only.
        if codes_on_line and not has_prefix:
            if in_name:
                pending_legacy.extend(codes_on_line)
            # Legacy-only row potentially flushes everything
            if pending_legacy:
                continue

        # Text fragment — accumulate into the current name.
        if in_name and not codes_on_line:
            frag = ln.strip().rstrip(".")
            if frag and re.match(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç]", frag):
                name_buf.append(frag)
        elif in_name and codes_on_line:
            # line has both text fragment and codes — name continuation
            frag = ln.strip().rstrip(".")
            if frag and re.match(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç]", frag):
                name_buf.append(frag)

    # Flush last entry.
    if in_name and name_buf and pending_legacy:
        key = " ".join(name_buf).strip()
        key = re.sub(r"\s+", " ", key).lower()
        if key:
            mapping.setdefault(key, [])
            for c in pending_legacy:
                if c not in mapping[key]:
                    mapping[key].append(c)

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
