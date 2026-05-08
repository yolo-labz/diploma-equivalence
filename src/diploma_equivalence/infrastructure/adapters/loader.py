"""Load CourseUnit objects from vault JSON directories.

Supports three source formats:
  - UFPE EE: index.json + per-code JSON files with ementa field
  - UFPE EC: index.json + per-slug JSON files with ementa field
  - UC (LEEC/MEEC): _index.json + per-unit JSON files with sections.Programa
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from diploma_equivalence.domain.models import CourseUnit, DisciplineType, Institution

LOG = logging.getLogger(__name__)


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_ufpe_ee(vault_root: str | None = None) -> list[CourseUnit]:
    root = Path(vault_root or _default_vault()) / "research/ementas/ufpe-ee/json"
    index = _load_json(root / "index.json")
    units: list[CourseUnit] = []

    for entry in index["disciplines"]:
        code = entry.get("code")
        if not code:
            continue
        detail_path = root / f"{code}.json"
        ementa = ""
        if detail_path.exists():
            detail = _load_json(detail_path)
            ementa = detail.get("ementa", "")

        units.append(
            CourseUnit(
                institution=Institution.UFPE,
                code=str(code),
                title=entry.get("title", ""),
                type=_map_type(entry.get("type", "UNKNOWN")),
                ch_total=entry.get("ch_total"),
                credits=entry.get("creditos"),
                period=entry.get("periodo"),
                syllabus=ementa,
            )
        )

    LOG.info("ufpe-ee: %d units loaded", len(units))
    return units


def load_ufpe_ec(vault_root: str | None = None) -> list[CourseUnit]:
    root = Path(vault_root or _default_vault()) / "research/ementas/ufpe-ec/json"
    index = _load_json(root / "index.json")
    units: list[CourseUnit] = []

    for entry in index["disciplines"]:
        slug = entry.get("slug", "")
        code = entry.get("code") or entry.get("prefix")
        if not code:
            code = slug

        detail_path = root / f"{slug}.json"
        ementa = ""
        if detail_path.exists():
            detail = _load_json(detail_path)
            ementa = detail.get("ementa", "")

        units.append(
            CourseUnit(
                institution=Institution.UFPE,
                code=str(code),
                title=entry.get("title", ""),
                type=_map_type(entry.get("type", "UNKNOWN")),
                ch_total=entry.get("ch_total"),
                credits=entry.get("creditos"),
                period=entry.get("periodo"),
                syllabus=ementa,
            )
        )

    LOG.info("ufpe-ec: %d units loaded", len(units))
    return units


def load_uc(programme: str, vault_root: str | None = None) -> list[CourseUnit]:
    root = Path(vault_root or _default_vault()) / f"research/ementas/uc-{programme}/json"
    index = _load_json(root / "_index.json")
    units: list[CourseUnit] = []

    for entry in index["units"]:
        unit_id = entry.get("unit_id", "")
        detail_path = root / f"unit-{unit_id}.json"
        ementa = ""
        if detail_path.exists():
            detail = _load_json(detail_path)
            sections = detail.get("sections", {})
            if isinstance(sections, dict):
                ementa = sections.get("Programa", "")

        units.append(
            CourseUnit(
                institution=Institution.UC,
                code=str(unit_id),
                title=entry.get("title", ""),
                type=DisciplineType.OBRIGATORIO,  # UC index doesn't expose type
                period=entry.get("periodo"),
                syllabus=ementa,
            )
        )

    LOG.info("uc-%s: %d units loaded", programme, len(units))
    return units


def load_all(vault_root: str | None = None) -> list[CourseUnit]:
    return [
        *load_ufpe_ee(vault_root),
        *load_ufpe_ec(vault_root),
        *load_uc("leec", vault_root),
        *load_uc("meec", vault_root),
    ]


def _map_type(raw: object) -> DisciplineType:
    s = str(raw).upper()
    if "OBRIG" in s or "OBRIGATORIO" in s:
        return DisciplineType.OBRIGATORIO
    if "ELETIV" in s or "ELECTIV" in s:
        return DisciplineType.ELETIVO
    if "OPT" in s:
        return DisciplineType.OPTATIVO
    return DisciplineType.ELETIVO


def _default_vault() -> str:
    return str(Path.home() / "Documents/Notes/1. Projects/Diploma-Equivalence")
