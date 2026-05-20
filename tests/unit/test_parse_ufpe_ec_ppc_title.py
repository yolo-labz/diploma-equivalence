"""Title-collection regression tests for the UFPE EC PPC parser.

Covers two title-bleed bugs that produced 28 garbage entries in the
2026-05-08 match report:

1. Column-header rows ("Código  Nome  Nº. de Créditos  ...") leaking into
   collected titles because the multi-word lowercase string didn't match
   any TITLE_BANLIST entry verbatim.
2. Period-suffix digits ("Cálculo Diferencial e Integral 2") being
   stripped by an over-eager [^\\d]{3,}? quantifier in the
   META_*_WITH_TITLE regexes, collapsing all four Cálculo variants into
   one indistinguishable title.
"""

from __future__ import annotations

from diploma_equivalence.infrastructure.ingest.parse_ufpe_ec_ppc import (
    META_LEGACY_WITH_TITLE_RE,
    META_PREFIX_BARE_RE,
    META_PREFIX_WITH_TITLE_RE,
    collect_title,
    is_title_line,
    parse,
)


class TestIsTitleLine:
    def test_accepts_simple_title(self):
        assert is_title_line("    Fundamentos de Programação")

    def test_accepts_title_below_with_indent(self):
        assert is_title_line("              Imperativa")

    def test_rejects_empty(self):
        assert not is_title_line("")
        assert not is_title_line("   ")

    def test_rejects_too_short(self):
        assert not is_title_line("X")
        assert not is_title_line(" ab")

    def test_rejects_exact_banlist_entry(self):
        assert not is_title_line("Pré-requisitos")
        assert not is_title_line("código")

    def test_rejects_column_header_row(self):
        # Real-world bleed source: full table header on one line.
        line = "Código                            Nome                                                    Nº. de Créditos     C. H. Global    Período"
        assert not is_title_line(line)

    def test_rejects_subheader_with_double_space(self):
        # Whitespace variant — must collapse before banlist check.
        assert not is_title_line("       Teórica            Prática")

    def test_rejects_pre_requisitos_row(self):
        line = "    Pré-requisitos                                  Co-Requisitos                                                Requisitos C.H."
        assert not is_title_line(line)

    def test_rejects_carga_horaria_subheader(self):
        assert not is_title_line(
            "                                                           Carga Horária Semanal"
        )

    def test_rejects_universidade_header(self):
        assert not is_title_line("                          UNIVERSIDADE FEDERAL DE PERNAMBUCO")

    def test_rejects_diretoria_header(self):
        assert not is_title_line(
            "                               DIRETORIA DE DESENVOLVIMENTO DO ENSINO"
        )


class TestCollectTitle:
    def _block(self) -> list[str]:
        # Mimics the layout around line 8782 of the real PPC source.
        return [
            "                          UNIVERSIDADE FEDERAL DE PERNAMBUCO",
            "                         PRÓ-REITORIA PARA ASSUNTOS ACADÊMICOS",
            "                               DIRETORIA DE DESENVOLVIMENTO DO ENSINO",
            "",
            "",
            " PROGRAMA DE COMPONENTE CURRICULAR",
            "",
            " DADOS DO COMPONENTE",
            "",
            "                                                                    Carga Horária",
            "   Código                           Nome                                                       Nº. de Créditos    C. H. Global     Período",
            "                                                           Teórica                  Prática",
            "              Fundamentos de Programação",
            "     CIN                                                     45                      15               3                60            2",
            "              Imperativa",
            "",
            "    Pré-requisitos                                  Co-Requisitos                                                Requisitos C.H.",
            " EMENTA",
        ]

    def test_glues_title_above_and_below_meta(self):
        block = self._block()
        meta_idx = 13  # CIN ... 45 15 3 60 2
        assert collect_title(block, meta_idx) == "Fundamentos de Programação Imperativa"

    def test_does_not_bleed_column_header_above(self):
        block = self._block()
        meta_idx = 13
        title = collect_title(block, meta_idx)
        assert "Código" not in title
        assert "Nome" not in title
        assert "C. H." not in title
        assert "Teórica" not in title

    def test_does_not_bleed_pre_requisitos_below(self):
        block = self._block()
        meta_idx = 13
        title = collect_title(block, meta_idx)
        assert "Pré-requisitos" not in title
        assert "Co-Requisitos" not in title

    def test_stops_at_empty_line_below(self):
        # Title-below = "Imperativa" then empty line (block index 15).
        # Must stop at empty rather than continue walking into pré-req row.
        block = self._block()
        title = collect_title(block, 13)
        assert title.endswith("Imperativa")


class TestMetaRegexPreservesPeriodDigit:
    def test_legacy_with_title_keeps_trailing_period_number(self):
        line = "MA027      Cálculo Diferencial e Integral 2               60                                       4                60            2"
        m = META_LEGACY_WITH_TITLE_RE.match(line)
        assert m is not None, "regex should match a legacy + title + numbers row"
        assert m.group("title").strip() == "Cálculo Diferencial e Integral 2"
        assert m.group("code") == "MA027"

    def test_legacy_with_title_distinct_period_variants(self):
        rows = [
            "MA026      Cálculo Diferencial e Integral 1               60     0     4    60    1",
            "MA027      Cálculo Diferencial e Integral 2               60     0     4    60    2",
            "MA128      Cálculo Diferencial e Integral 3               60     0     4    60    3",
            "MA129      Cálculo Diferencial e Integral 4               60     0     4    60    4",
        ]
        titles = []
        for r in rows:
            m = META_LEGACY_WITH_TITLE_RE.match(r)
            assert m is not None, f"failed on row: {r!r}"
            titles.append(m.group("title").strip())
        assert len(set(titles)) == 4, "each Cálculo variant should produce a distinct title"

    def test_prefix_with_title_simple(self):
        line = "CIN       Introdução à Programação                         45                15                 3                  60           1"
        m = META_PREFIX_WITH_TITLE_RE.match(line)
        assert m is not None
        assert m.group("title").strip() == "Introdução à Programação"
        assert m.group("prefix") == "CIN"

    def test_prefix_bare_still_matches_when_no_title(self):
        line = "     CIN                                                     45                      15               3                60            2"
        m = META_PREFIX_BARE_RE.match(line)
        assert m is not None
        assert m.group("prefix") == "CIN"


class TestParseEndToEndOnSyntheticBlock:
    def test_full_block_parses_clean_title(self):
        text = "\n".join(
            [
                "                          UNIVERSIDADE FEDERAL DE PERNAMBUCO",
                "                         PRÓ-REITORIA PARA ASSUNTOS ACADÊMICOS",
                "                               DIRETORIA DE DESENVOLVIMENTO DO ENSINO",
                "",
                " PROGRAMA DE COMPONENTE CURRICULAR",
                "",
                "    STATUS DO COMPONENTE (Marque um X na opção)",
                "",
                "    X      OBRIGATÓRIO                                     ELETIVO                                               OPTATIVO",
                "",
                " DADOS DO COMPONENTE",
                "",
                "                                                                    Carga Horária",
                "   Código                           Nome                                                       Nº. de Créditos    C. H. Global     Período",
                "                                                           Teórica                  Prática",
                "              Fundamentos de Programação",
                "     CIN                                                     45                      15               3                60            2",
                "              Imperativa",
                "",
                "    Pré-requisitos                                  Co-Requisitos                                                Requisitos C.H.",
                " EMENTA",
                "Conceito de variáveis em linguagens de programação imperativas.",
                " OBJETIVO (S) DO COMPONENTE",
            ]
        )
        out = parse(text)
        assert len(out) == 1
        d = out[0]
        assert d.title == "Fundamentos de Programação Imperativa"
        assert "Código" not in d.title
        assert "Pré-requisitos" not in d.title
        assert d.prefix == "CIN"
        assert d.ch_total == 60
        assert d.periodo == 2
        assert d.type == "OBRIGATORIO"
