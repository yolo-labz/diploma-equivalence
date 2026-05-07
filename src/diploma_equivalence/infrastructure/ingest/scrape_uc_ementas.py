#!/usr/bin/env python3
"""
scrape_uc_ementas.py — fetch curricular units (ementas) for a Universidade de
Coimbra programme and persist them as raw HTML + structured JSON.

Empirically validated against:
  https://apps.uc.pt/courses/PT/programme/8922/2024-2025?id_branch=21062
  (Licenciatura em Engenharia Eletrotécnica e de Computadores — LEEC)

URL grammar (PT route — EN 404s for these ids):

  Programme branch (lists units):
    https://apps.uc.pt/courses/PT/programme/<course_id>/<year>?id_branch=<branch_id>

  Curricular unit page (the ementa):
    https://apps.uc.pt/courses/PT/unit/<unit_id>/<branch_id>/<year>?common_core=true&type=ram&id=<course_id>

Sections found on a unit page (h-tags, observed on unit 8124):
  - <h-tag>: unit title (first heading)
  - "Conhecimentos de Base Recomendados"
  - "Métodos de Ensino"
  - "Resultados de Aprendizagem"
  - "Estágio(s)"
  - "Programa"                  ← canonical ementa body
  - "Docente(s) responsável(eis)"
  - "Métodos de Avaliação"
  - "Bibliografia"

Usage:
  python3 scrape_uc_ementas.py \\
    --course-id 8922 --branch-id 21062 --year 2024-2025 \\
    --raw-dir ../research/ementas/uc-leec/raw \\
    --json-dir ../research/ementas/uc-leec/json

Politeness:
  - 1.0 s sleep between unit fetches (configurable via --sleep).
  - Identifies via custom User-Agent including a contact mailbox.
  - Refuses to overwrite cached raw HTML unless --refresh is passed.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar
from urllib.parse import urljoin

import requests

LOG = logging.getLogger("scrape_uc_ementas")

USER_AGENT = (
    "DiplomaEquivalenceDiscovery/0.1 "
    "(+https://github.com/phsb5321/Notes; pedro@home301server.com.br) "
    "research-scraper"
)

UNIT_HREF_RE = re.compile(r"/courses/PT/unit/(?P<unit_id>\d+)/(?P<branch_id>\d+)/(?P<year>[\d-]+)")


# ---------------------------------------------------------------------------
# HTML helpers (stdlib only — keeps the scraper installable without bs4)
# ---------------------------------------------------------------------------


class _SectionExtractor(HTMLParser):
    """
    Walks the UC unit page and records (heading_text, body_text) pairs.

    UC pages put each section as:
        <h?>Heading</h?>
        ...arbitrary block markup...
        <h?>Next Heading</h?>
    so we accumulate text between heading boundaries.
    """

    HEADING_TAGS: ClassVar[set[str]] = {"h1", "h2", "h3", "h4", "h5", "h6"}
    SKIP_TAGS: ClassVar[set[str]] = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[tuple[str, str]] = []
        self._current_heading: str | None = None
        self._current_buffer: list[str] = []
        self._in_heading = False
        self._heading_buffer: list[str] = []
        self._skip_depth = 0

    # ---- handlers --------------------------------------------------------

    def handle_starttag(self, tag: str, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in self.HEADING_TAGS:
            self._flush_section()
            self._in_heading = True
            self._heading_buffer = []
        elif tag in {"br", "p", "li", "tr", "div"}:
            self._current_buffer.append("\n")

    def handle_endtag(self, tag: str):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in self.HEADING_TAGS and self._in_heading:
            self._current_heading = " ".join("".join(self._heading_buffer).split())
            self._in_heading = False
            self._heading_buffer = []

    def handle_data(self, data: str):
        if self._skip_depth > 0:
            return
        if self._in_heading:
            self._heading_buffer.append(data)
        else:
            self._current_buffer.append(data)

    # ---- finalisation ----------------------------------------------------

    def _flush_section(self) -> None:
        if self._current_heading is not None:
            body = "\n".join(
                line.strip() for line in "".join(self._current_buffer).splitlines() if line.strip()
            )
            self.sections.append((self._current_heading, body))
        self._current_buffer = []

    def close(self) -> None:  # type: ignore[override]
        self._flush_section()
        super().close()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Unit:
    unit_id: str
    course_id: str
    branch_id: str
    year: str
    url: str
    title: str
    sections: dict[str, str]
    fetched_at: str  # ISO-8601


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.5"})
    return s


def fetch_branch_units(
    session: requests.Session, course_id: str, branch_id: str, year: str
) -> list[tuple[str, str]]:
    """Returns [(unit_id, absolute_url), ...] in document order, deduplicated."""
    url = f"https://apps.uc.pt/courses/PT/programme/{course_id}/{year}?id_branch={branch_id}"
    LOG.info("Fetching programme branch: %s", url)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for m in UNIT_HREF_RE.finditer(resp.text):
        unit_id = m.group("unit_id")
        if unit_id in seen:
            continue
        seen.add(unit_id)
        absolute = urljoin(
            "https://apps.uc.pt/",
            f"/courses/PT/unit/{unit_id}/{branch_id}/{year}"
            f"?common_core=true&type=ram&id={course_id}",
        )
        out.append((unit_id, absolute))
    LOG.info("Branch %s/%s yielded %d distinct units", course_id, branch_id, len(out))
    return out


def parse_unit_html(html: str) -> tuple[str, dict[str, str]]:
    parser = _SectionExtractor()
    parser.feed(html)
    parser.close()
    title = parser.sections[0][0] if parser.sections else ""
    sections: dict[str, str] = {}
    for heading, body in parser.sections[1:]:
        # Last writer wins on duplicate headings, but UC pages are unique in practice.
        sections[heading] = body
    return title, sections


def fetch_unit(
    session: requests.Session,
    unit_id: str,
    branch_id: str,
    course_id: str,
    year: str,
    raw_dir: Path,
    refresh: bool,
) -> Unit:
    raw_path = raw_dir / f"unit-{unit_id}.html"
    if raw_path.exists() and not refresh:
        LOG.debug("Cache hit %s", raw_path)
        html = raw_path.read_text(encoding="utf-8")
        # Synthesise a fetched_at marker from mtime so cached results stay reproducible.
        fetched_at = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime(raw_path.stat().st_mtime))
    else:
        url = (
            f"https://apps.uc.pt/courses/PT/unit/{unit_id}/{branch_id}/{year}"
            f"?common_core=true&type=ram&id={course_id}"
        )
        LOG.info("Fetching unit %s", url)
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        html = resp.text
        raw_path.write_text(html, encoding="utf-8")
        fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    title, sections = parse_unit_html(html)
    return Unit(
        unit_id=unit_id,
        course_id=course_id,
        branch_id=branch_id,
        year=year,
        url=(
            f"https://apps.uc.pt/courses/PT/unit/{unit_id}/{branch_id}/{year}"
            f"?common_core=true&type=ram&id={course_id}"
        ),
        title=title,
        sections=sections,
        fetched_at=fetched_at,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--course-id", required=True, help="UC course id, e.g. 8922 (LEEC)")
    p.add_argument("--branch-id", required=True, help="UC branch id, e.g. 21062")
    p.add_argument("--year", required=True, help="Academic year, e.g. 2024-2025")
    p.add_argument("--raw-dir", required=True, type=Path, help="Where to persist raw HTML")
    p.add_argument("--json-dir", required=True, type=Path, help="Where to persist parsed JSON")
    p.add_argument("--sleep", type=float, default=1.0, help="Seconds between unit fetches")
    p.add_argument("--refresh", action="store_true", help="Re-download even if cached")
    p.add_argument("--limit", type=int, default=0, help="Stop after N units (0 = all)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.json_dir.mkdir(parents=True, exist_ok=True)

    session = _session()
    units = fetch_branch_units(session, args.course_id, args.branch_id, args.year)
    if args.limit:
        units = units[: args.limit]

    summary: list[dict] = []
    for i, (unit_id, _url) in enumerate(units, start=1):
        try:
            unit = fetch_unit(
                session,
                unit_id=unit_id,
                branch_id=args.branch_id,
                course_id=args.course_id,
                year=args.year,
                raw_dir=args.raw_dir,
                refresh=args.refresh,
            )
        except requests.HTTPError as e:
            LOG.error("HTTP error on unit %s: %s", unit_id, e)
            continue

        out_path = args.json_dir / f"unit-{unit_id}.json"
        out_path.write_text(
            json.dumps(asdict(unit), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary.append(
            {
                "unit_id": unit.unit_id,
                "title": unit.title,
                "section_keys": sorted(unit.sections.keys()),
                "programa_chars": len(unit.sections.get("Programa", "")),
                "url": unit.url,
            }
        )
        LOG.info(
            "  [%d/%d] %s — %s (Programa: %d chars)",
            i,
            len(units),
            unit.unit_id,
            unit.title,
            len(unit.sections.get("Programa", "")),
        )
        time.sleep(args.sleep)

    index_path = args.json_dir / "_index.json"
    index_path.write_text(
        json.dumps(
            {
                "course_id": args.course_id,
                "branch_id": args.branch_id,
                "year": args.year,
                "count": len(summary),
                "units": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    LOG.info("Wrote index %s (%d units)", index_path, len(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
