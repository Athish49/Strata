"""
Task 1.3.2: Citation parser adapter — unit tests.

Table-driven tests covering:
  - Standard IAC forms
  - Decimal sections
  - Range expansion
  - Rule-level references
  - External citations (IC, CFR)
  - Bracketed form
  - find_citation_spans
"""

from decimal import Decimal

import pytest

from app.company_ingest.enrich.citations_grammar import (
    ParsedCitation,
    find_citation_spans,
    parse_citation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def one(raw: str) -> ParsedCitation:
    """Assert parse_citation returns exactly one result and return it."""
    result = parse_citation(raw)
    assert len(result) == 1, f"Expected 1 result for {raw!r}, got {len(result)}"
    return result[0]


# ===========================================================================
# 1. Standard IAC forms
# ===========================================================================

class TestStandardIAC:
    def test_basic_section(self):
        pc = one("170 IAC 4-1-16")
        assert pc.source_system == "iac"
        assert pc.title == 170
        assert pc.article == "4-1"
        assert pc.section == Decimal("16")
        assert pc.rule == "4-1-16"
        assert pc.granularity == "section"
        assert pc.normalized_key == "170 IAC 4-1-16"
        assert pc.rule_key == "170 IAC 4-1"
        assert pc.subsection_path == ""

    def test_327_title(self):
        pc = one("327 IAC 2-1-3")
        assert pc.source_system == "iac"
        assert pc.title == 327
        assert pc.article == "2-1"
        assert pc.section == Decimal("3")
        assert pc.normalized_key == "327 IAC 2-1-3"
        assert pc.rule_key == "327 IAC 2-1"

    def test_610_title(self):
        pc = one("610 IAC 1-5-1")
        assert pc.title == 610
        assert pc.article == "1-5"
        assert pc.normalized_key == "610 IAC 1-5-1"

    def test_large_section_number(self):
        pc = one("170 IAC 4-1-100")
        assert pc.section == Decimal("100")
        assert pc.normalized_key == "170 IAC 4-1-100"

    def test_citation_raw_preserved(self):
        raw = "170 IAC 4-1-16"
        pc = one(raw)
        assert pc.citation_raw == raw

    def test_raw_with_leading_trailing_space(self):
        pc = one("  170 IAC 4-1-16  ")
        assert pc.normalized_key == "170 IAC 4-1-16"


# ===========================================================================
# 2. Subsection forms
# ===========================================================================

class TestSubsectionIAC:
    def test_single_subsection(self):
        pc = one("170 IAC 4-1-16(b)")
        assert pc.granularity == "subsection"
        assert pc.subsection_path == "(b)"
        assert pc.normalized_key == "170 IAC 4-1-16"
        assert pc.section == Decimal("16")

    def test_double_subsection(self):
        pc = one("170 IAC 4-1-16(b)(2)")
        assert pc.granularity == "subsection"
        assert pc.subsection_path == "(b)(2)"
        assert pc.normalized_key == "170 IAC 4-1-16"

    def test_triple_subsection(self):
        pc = one("170 IAC 4-1-16(b)(2)(i)")
        assert pc.subsection_path == "(b)(2)(i)"
        assert pc.granularity == "subsection"

    def test_subsection_does_not_affect_rule_key(self):
        pc = one("170 IAC 4-1-16(b)(2)")
        assert pc.rule_key == "170 IAC 4-1"
        assert pc.rule == "4-1-16"

    def test_subsection_does_not_affect_article(self):
        pc = one("327 IAC 2-1-3(a)")
        assert pc.article == "2-1"
        assert pc.subsection_path == "(a)"


# ===========================================================================
# 3. Decimal sections
# ===========================================================================

class TestDecimalSections:
    def test_decimal_section(self):
        pc = one("170 IAC 4-1-16.5")
        assert pc.section == Decimal("16.5")
        assert pc.normalized_key == "170 IAC 4-1-16.5"
        assert pc.rule == "4-1-16.5"

    def test_decimal_article_part(self):
        pc = one("327 IAC 2-6.1-7")
        assert pc.article == "2-6.1"
        assert pc.section == Decimal("7")
        assert pc.normalized_key == "327 IAC 2-6.1-7"
        assert pc.rule_key == "327 IAC 2-6.1"

    def test_decimal_sorts_correctly_16_before_165(self):
        pc16 = one("170 IAC 4-1-16")
        pc165 = one("170 IAC 4-1-16.5")
        assert pc16.section < pc165.section

    def test_decimal_sorts_correctly_165_before_17(self):
        pc165 = one("170 IAC 4-1-16.5")
        pc17 = one("170 IAC 4-1-17")
        assert pc165.section < pc17.section

    def test_decimal_ordering_chain(self):
        secs = [one(f"170 IAC 4-1-{s}").section for s in ["16", "16.5", "17"]]
        assert secs == sorted(secs)
        assert secs[0] < secs[1] < secs[2]

    def test_decimal_section_with_subsection(self):
        pc = one("170 IAC 4-1-16.5(a)")
        assert pc.section == Decimal("16.5")
        assert pc.subsection_path == "(a)"
        assert pc.granularity == "subsection"

    def test_decimal_normalized_key_no_trailing_zero(self):
        pc = one("170 IAC 4-1-16.50")
        # Decimal("16.50").normalize() → Decimal("16.5")
        assert pc.normalized_key == "170 IAC 4-1-16.5"


# ===========================================================================
# 4. Range expansion
# ===========================================================================

class TestRangeExpansion:
    def test_through_range_count(self):
        results = parse_citation("170 IAC 4-1-4 through 4-1-14")
        assert len(results) == 11

    def test_through_range_sections(self):
        results = parse_citation("170 IAC 4-1-4 through 4-1-14")
        sections = sorted(pc.section for pc in results)
        assert sections == [Decimal(str(i)) for i in range(4, 15)]

    def test_through_range_source_system(self):
        results = parse_citation("170 IAC 4-1-4 through 4-1-14")
        assert all(pc.source_system == "iac" for pc in results)

    def test_through_range_article_consistent(self):
        results = parse_citation("170 IAC 4-1-4 through 4-1-14")
        assert all(pc.article == "4-1" for pc in results)

    def test_through_range_granularity(self):
        results = parse_citation("170 IAC 4-1-4 through 4-1-14")
        assert all(pc.granularity == "section" for pc in results)

    def test_dotdot_range_count(self):
        results = parse_citation("170 IAC 4-1-4..4-1-14")
        assert len(results) == 11

    def test_dotdot_range_sections(self):
        results = parse_citation("170 IAC 4-1-4..4-1-14")
        sections = sorted(pc.section for pc in results)
        assert sections == [Decimal(str(i)) for i in range(4, 15)]

    def test_dotdot_range_with_spaces(self):
        results = parse_citation("170 IAC 4-1-4 .. 4-1-14")
        assert len(results) == 11

    def test_small_range_2_items(self):
        results = parse_citation("170 IAC 4-1-5 through 4-1-6")
        assert len(results) == 2
        sections = {pc.section for pc in results}
        assert sections == {Decimal("5"), Decimal("6")}

    def test_single_section_range(self):
        results = parse_citation("170 IAC 4-1-7 through 4-1-7")
        assert len(results) == 1
        assert results[0].section == Decimal("7")

    def test_range_normalized_keys(self):
        results = parse_citation("170 IAC 4-1-4 through 4-1-6")
        nks = {pc.normalized_key for pc in results}
        assert "170 IAC 4-1-4" in nks
        assert "170 IAC 4-1-5" in nks
        assert "170 IAC 4-1-6" in nks


# ===========================================================================
# 5. Rule-level references
# ===========================================================================

class TestRuleLevelIAC:
    def test_two_part_is_rule_level(self):
        pc = one("170 IAC 4-9")
        assert pc.granularity == "rule"
        assert pc.section is None
        assert pc.rule is None

    def test_rule_level_article(self):
        pc = one("170 IAC 4-9")
        assert pc.article == "4-9"

    def test_rule_level_normalized_key(self):
        pc = one("170 IAC 4-9")
        assert pc.normalized_key == "170 IAC 4-9"

    def test_rule_level_rule_key_equals_normalized_key(self):
        pc = one("170 IAC 4-9")
        assert pc.rule_key == pc.normalized_key

    def test_rule_level_title(self):
        pc = one("327 IAC 2-1")
        assert pc.title == 327
        assert pc.article == "2-1"
        assert pc.granularity == "rule"

    def test_rule_level_decimal_article(self):
        pc = one("327 IAC 2-6.1")
        assert pc.article == "2-6.1"
        assert pc.granularity == "rule"
        assert pc.normalized_key == "327 IAC 2-6.1"


# ===========================================================================
# 6. Bracketed form
# ===========================================================================

class TestBracketedForm:
    def test_basic_bracketed(self):
        results = parse_citation("Commission Rule 16 [170 IAC 4-1-16]")
        assert len(results) == 1
        pc = results[0]
        assert pc.source_system == "iac"
        assert pc.normalized_key == "170 IAC 4-1-16"

    def test_bracketed_raw_preserved(self):
        raw = "Commission Rule 16 [170 IAC 4-1-16]"
        pc = parse_citation(raw)[0]
        assert pc.citation_raw == raw

    def test_bracketed_subsection(self):
        results = parse_citation("See [170 IAC 4-1-16(b)(2)]")
        assert len(results) == 1
        pc = results[0]
        assert pc.subsection_path == "(b)(2)"
        assert pc.granularity == "subsection"

    def test_bracketed_rule_level(self):
        results = parse_citation("per [170 IAC 4-9]")
        assert len(results) == 1
        pc = results[0]
        assert pc.granularity == "rule"

    def test_bracketed_cfr(self):
        results = parse_citation("federal standard [40 CFR 112]")
        assert len(results) == 1
        assert results[0].source_system == "cfr"


# ===========================================================================
# 7. IC citations
# ===========================================================================

class TestIC:
    def test_basic_ic(self):
        pc = one("IC 8-1-2-121")
        assert pc.source_system == "ic"
        assert pc.title is None
        assert pc.article == "8-1-2"
        assert pc.section == Decimal("121")
        assert pc.normalized_key == "IC 8-1-2-121"
        assert pc.rule_key == "IC 8-1-2"

    def test_ic_granularity(self):
        pc = one("IC 8-1-2-121")
        assert pc.granularity == "section"

    def test_ic_rule_field(self):
        pc = one("IC 8-1-2-121")
        assert pc.rule == "8-1-2-121"

    def test_ic_different_parts(self):
        pc = one("IC 14-22-2-1")
        assert pc.article == "14-22-2"
        assert pc.section == Decimal("1")
        assert pc.normalized_key == "IC 14-22-2-1"


# ===========================================================================
# 8. CFR citations
# ===========================================================================

class TestCFR:
    def test_cfr_no_decimal(self):
        pc = one("40 CFR 112")
        assert pc.source_system == "cfr"
        assert pc.title == 40
        assert pc.section == Decimal("112")
        assert pc.normalized_key == "40 CFR 112"

    def test_cfr_decimal(self):
        pc = one("29 CFR 1910.269")
        assert pc.source_system == "cfr"
        assert pc.title == 29
        assert pc.section == Decimal("1910.269")
        assert pc.normalized_key == "29 CFR 1910.269"

    def test_cfr_rule_key(self):
        pc = one("40 CFR 112")
        assert pc.rule_key == "40 CFR"

    def test_cfr_article_is_none(self):
        pc = one("40 CFR 112")
        assert pc.article is None


# ===========================================================================
# 9. U.S.C. citations
# ===========================================================================

class TestUSC:
    def test_usc_with_section_symbol(self):
        pc = one("42 U.S.C. § 7401")
        assert pc.source_system == "usc"
        assert pc.title == 42
        assert pc.section == Decimal("7401")
        assert pc.normalized_key == "42 U.S.C. 7401"

    def test_usc_without_symbol(self):
        pc = one("42 U.S.C. 7401")
        assert pc.source_system == "usc"
        assert pc.section == Decimal("7401")


# ===========================================================================
# 10. find_citation_spans
# ===========================================================================

class TestFindCitationSpans:
    def test_single_iac_span(self):
        text = "Pursuant to 170 IAC 4-1-16 the utility must..."
        spans = find_citation_spans(text)
        assert len(spans) == 1
        start, end, raw = spans[0]
        assert raw == "170 IAC 4-1-16"
        assert text[start:end] == raw

    def test_multiple_citations_in_sentence(self):
        text = "See 170 IAC 4-1-16 and IC 8-1-2-121 and 40 CFR 112."
        spans = find_citation_spans(text)
        raws = [s[2] for s in spans]
        assert any("170 IAC" in r for r in raws)
        assert any("IC 8" in r for r in raws)
        assert any("40 CFR" in r for r in raws)

    def test_span_offsets_correct(self):
        text = "See 170 IAC 4-1-16 for details."
        spans = find_citation_spans(text)
        assert len(spans) >= 1
        start, end, raw = spans[0]
        assert text[start:end] == raw

    def test_no_citations_empty_string(self):
        assert find_citation_spans("") == []

    def test_no_citations_plain_text(self):
        assert find_citation_spans("No citations here whatsoever.") == []

    def test_iac_range_is_one_span(self):
        text = "Refer to 170 IAC 4-1-4 through 4-1-14 for requirements."
        spans = find_citation_spans(text)
        assert len(spans) == 1
        assert "through" in spans[0][2]

    def test_ic_span(self):
        text = "Under IC 8-1-2-121 the commission may..."
        spans = find_citation_spans(text)
        assert len(spans) == 1
        assert spans[0][2] == "IC 8-1-2-121"

    def test_cfr_span(self):
        text = "Comply with 40 CFR 112 requirements."
        spans = find_citation_spans(text)
        assert any("40 CFR 112" in s[2] for s in spans)

    def test_subsection_included_in_span(self):
        text = "As required by 170 IAC 4-1-16(b)(2) utilities must..."
        spans = find_citation_spans(text)
        assert len(spans) >= 1
        # The span raw text should include the subsection
        combined = " ".join(s[2] for s in spans)
        assert "4-1-16" in combined

    def test_four_citations_in_one_sentence(self):
        text = (
            "Per 170 IAC 4-1-16 and 327 IAC 2-1-3 "
            "see also IC 8-1-2-121 and 40 CFR 112."
        )
        spans = find_citation_spans(text)
        assert len(spans) == 4


# ===========================================================================
# 11. External standards
# ===========================================================================

class TestExternalStandards:
    def test_ieee_standard(self):
        pc = one("IEEE C37.90")
        assert pc.source_system == "external_standard"

    def test_ansi_standard(self):
        pc = one("ANSI/IEEE C37.90")
        assert pc.source_system == "external_standard"

    def test_astm_standard(self):
        pc = one("ASTM D877")
        assert pc.source_system == "external_standard"

    def test_nfpa_standard(self):
        pc = one("NFPA 70")
        assert pc.source_system == "external_standard"


# ===========================================================================
# 12. Edge cases and robustness
# ===========================================================================

class TestEdgeCases:
    def test_unknown_returns_result(self):
        results = parse_citation("some random text")
        assert len(results) == 1
        assert results[0].source_system == "unknown"

    def test_empty_string(self):
        results = parse_citation("")
        assert len(results) == 1
        assert results[0].source_system == "unknown"

    def test_section_decimal_type(self):
        pc = one("170 IAC 4-1-16")
        assert isinstance(pc.section, Decimal)

    def test_section_comparison_with_decimal(self):
        pc = one("170 IAC 4-1-16")
        assert pc.section == Decimal("16")
        assert pc.section < Decimal("17")
        assert pc.section > Decimal("15")

    def test_rule_level_section_is_none(self):
        pc = one("170 IAC 4-9")
        assert pc.section is None
        assert pc.rule is None

    def test_section_level_has_rule(self):
        pc = one("170 IAC 4-1-16")
        assert pc.rule is not None
        assert pc.rule == "4-1-16"

    def test_multiple_citations_in_raw_returns_first_iac(self):
        # Raw string with embedded IAC: should parse as IAC
        raw = "per Commission Rule [170 IAC 4-1-16]"
        results = parse_citation(raw)
        assert results[0].source_system == "iac"
        assert results[0].normalized_key == "170 IAC 4-1-16"
