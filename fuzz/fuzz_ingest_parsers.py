"""Atheris fuzz target for the ingest parsers (untrusted HTML / PDF-text input).

Run: `uv sync --frozen --only-group fuzz && PYTHONPATH=src uv run --no-sync python fuzz/fuzz_ingest_parsers.py -max_total_time=60`.
The parsers are pure functions over text, so any exception is a bug.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

with atheris.instrument_imports(include=["diploma_equivalence"]):
    from diploma_equivalence.infrastructure.ingest import (
        extract_ufpe_ec_codes,
        parse_ufpe_ec_ppc,
        parse_ufpe_ee_perfil,
        scrape_uc_ementas,
    )


def test_one_input(data: bytes) -> None:
    text = atheris.FuzzedDataProvider(data).ConsumeUnicodeNoSurrogates(len(data))
    extract_ufpe_ec_codes.parse(text)
    parse_ufpe_ec_ppc.parse(text)
    parse_ufpe_ec_ppc.parse_equivalence(text)
    parse_ufpe_ee_perfil.parse(text)
    # Known stdlib behaviour: html.parser asserts on a malformed marked section such as
    # `<![br`. Raised by CPython, not by this repo's code.
    with contextlib.suppress(AssertionError):
        scrape_uc_ementas.parse_unit_html(text)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
