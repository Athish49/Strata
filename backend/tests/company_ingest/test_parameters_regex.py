"""Tests for task 4.1.2 — parameters_regex.enrich_parameters.

Non-corpus tests: at least 40 cases covering true positives, exclusions,
kind detection, qualifier detection, day_type, and counting.

Corpus tests (@pytest.mark.corpus): deselect with -m "not corpus".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.company_ingest.constants import DayType, ParameterKind
from app.company_ingest.enrich.parameter_entry import ParameterEntry
from app.company_ingest.enrich.parameters_regex import enrich_parameters
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.parse.text import normalize, sha256_text
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_unit(
    text: str,
    local_id: str = "T-1",
    citations: list[Any] | None = None,
) -> ClauseUnit:
    """Build a minimal ClauseUnit for testing."""
    return ClauseUnit(
        version_id="v1",
        doc_id="DOC",
        clause_id=f"DOC:{local_id}",
        local_id=local_id,
        parent_clause_id=None,
        unit_kind="section",
        heading_path=[],
        section_kind="other",
        ordinal=0,
        char_start=0,
        char_end=len(text),
        line_start=0,
        text_raw=text,
        text_norm=normalize(text),
        text_sha256=sha256_text(text),
        citations=citations if citations is not None else [],
    )


# A stub citation object — any truthy value satisfies "≥1 citation present".
_STUB_CITATION = object()


def run(text: str, local_id: str = "T-1", citations: list[Any] | None = None) -> list[ParameterEntry]:
    """Run enrich_parameters on a single unit and return its parameters."""
    unit = make_unit(text, local_id=local_id, citations=citations)
    ctx = RunContext()
    enrich_parameters([unit], ctx)
    return unit.parameters


# ---------------------------------------------------------------------------
# True positives — basic extraction
# ---------------------------------------------------------------------------


class TestTruePositives:
    def test_within_10_business_days(self):
        params = run("Respond within 10 business days.")
        assert len(params) >= 1
        p = params[0]
        assert p.kind == ParameterKind.PERIOD
        assert p.value_num == 10.0
        assert p.unit == "business_day"
        assert p.qualifier == "within"
        assert p.day_type == DayType.BUSINESS

    def test_30_day_notice_period(self):
        params = run("Provide a 30-day notice period.")
        assert len(params) >= 1
        p = params[0]
        assert p.value_num == 30.0
        assert p.unit == "day"
        assert p.kind == ParameterKind.PERIOD

    def test_fourteen_parenthetical_calendar_days(self):
        # Parenthetical digit wins over the word number.
        params = run("Submit within fourteen (14) calendar days.")
        assert len(params) >= 1
        p = params[0]
        assert p.value_num == 14.0
        assert p.unit == "calendar_day"
        assert p.day_type == DayType.CALENDAR

    def test_dollar_amount(self):
        params = run("Pay a $45.00 fee.")
        assert len(params) >= 1
        p = params[0]
        assert p.kind == ParameterKind.AMOUNT
        assert p.unit == "usd"
        assert p.value_num == 45.0

    def test_comma_separated_customers(self):
        params = run("Affects 2,500 customers in the service area.")
        assert len(params) >= 1
        p = params[0]
        assert p.value_num == 2500.0
        assert p.unit == "customer"

    def test_no_later_than_qualifier(self):
        params = run("Submit no later than 90 days after the event.")
        assert len(params) >= 1
        p = params[0]
        assert p.qualifier == "not_more_than"

    def test_at_least_24_hours(self):
        params = run("Provide at least 24 hours of advance notice.")
        assert len(params) >= 1
        p = params[0]
        assert p.qualifier == "at_least"
        assert p.day_type == DayType.HOURS
        assert p.unit == "hour"

    def test_retain_records_record_retention(self):
        params = run("The company shall retain records for 7 years.")
        assert len(params) >= 1
        # Find the years parameter
        years_params = [p for p in params if p.unit == "year"]
        assert len(years_params) >= 1
        assert years_params[0].kind == ParameterKind.RECORD_RETENTION

    def test_exceeds_threshold(self):
        params = run("When usage exceeds 100 gallons per month.")
        assert len(params) >= 1
        gallons = [p for p in params if p.unit == "gallon"]
        assert len(gallons) >= 1
        assert gallons[0].kind == ParameterKind.THRESHOLD

    def test_annually_no_number_skipped(self):
        # "annually" alone has no number, so nothing should be extracted.
        params = run("Reports are submitted annually.")
        # No numeric match possible without a number
        time_params = [p for p in params if p.unit in ("year", "month")]
        assert len(time_params) == 0

    def test_every_30_days_frequency(self):
        params = run("Submit every 30 days.")
        assert len(params) >= 1
        p = params[0]
        assert p.kind == ParameterKind.FREQUENCY
        assert p.value_num == 30.0
        assert p.unit == "day"

    def test_percent(self):
        params = run("10% of customers qualify.")
        assert len(params) >= 1
        pct = [p for p in params if p.unit == "percent"]
        assert len(pct) >= 1
        assert pct[0].value_num == 10.0


# ---------------------------------------------------------------------------
# Exclusion tests (with citations so the bare pass is active)
# ---------------------------------------------------------------------------


class TestExclusions:
    def test_phone_suffix_excluded(self):
        # "555-1234" — phone suffix; no parameters should be extracted from it.
        params = run("Call 555-1234 for assistance.", citations=[_STUB_CITATION])
        phone_params = [p for p in params if p.value_num in (555.0, 1234.0)]
        assert len(phone_params) == 0

    def test_obl_id_excluded(self):
        params = run("See obligation OBL-2024-0042 for details.", citations=[_STUB_CITATION])
        id_params = [p for p in params if p.value_num in (2024.0, 42.0, 2024042.0)]
        assert len(id_params) == 0

    def test_form_id_excluded(self):
        # "RPL-DCC-F-042" — compound form ID; digits not extracted.
        params = run("Complete form RPL-DCC-F-042.", citations=[_STUB_CITATION])
        form_params = [p for p in params if p.value_num == 42.0]
        assert len(form_params) == 0

    def test_sheet_number_excluded(self):
        params = run("Refer to Sheet No. 4 of the tariff.", citations=[_STUB_CITATION])
        sheet_params = [p for p in params if p.value_num == 4.0]
        assert len(sheet_params) == 0

    def test_version_string_excluded(self):
        params = run("Policy v2.1 applies.", citations=[_STUB_CITATION])
        ver_params = [p for p in params if p.value_num in (2.0, 1.0, 2.1)]
        assert len(ver_params) == 0

    def test_bare_number_no_citation_excluded(self):
        # "3 notices" with no citation: bare pass is skipped entirely.
        params = run("3 notices were issued.")
        assert len(params) == 0

    def test_bare_number_with_citation_extracted(self):
        # "3" with citation present: bare pass runs and extracts it.
        params = run("3 notices were issued.", citations=[_STUB_CITATION])
        bare = [p for p in params if p.value_num == 3.0 and p.unit is None]
        assert len(bare) >= 1

    def test_full_phone_number_excluded(self):
        params = run("Call 317-555-1234 for help.", citations=[_STUB_CITATION])
        phone_params = [p for p in params if p.value_num in (317.0, 555.0, 1234.0)]
        assert len(phone_params) == 0

    def test_800_number_excluded(self):
        params = run("Contact us at 1-800-555-1234.", citations=[_STUB_CITATION])
        phone_params = [p for p in params if p.value_num in (800.0, 555.0, 1234.0)]
        assert len(phone_params) == 0


# ---------------------------------------------------------------------------
# Kind detection
# ---------------------------------------------------------------------------


class TestKindDetection:
    def test_due_within_deadline(self):
        # "due" in context → DEADLINE even though "within" implies PERIOD
        params = run("Payment is due within 5 business days.")
        assert len(params) >= 1
        p = params[0]
        assert p.kind == ParameterKind.DEADLINE

    def test_at_least_kv_threshold(self):
        # at_least qualifier + non-time unit → THRESHOLD
        params = run("Voltage must be at least 10 kV.")
        assert len(params) >= 1
        kv_params = [p for p in params if p.unit == "kv"]
        assert len(kv_params) >= 1
        assert kv_params[0].kind == ParameterKind.THRESHOLD
        assert kv_params[0].qualifier == "at_least"

    def test_prior_to_qualifier(self):
        params = run("Submit prior to 30 days before the deadline.")
        assert len(params) >= 1
        p = params[0]
        assert p.qualifier == "prior_to"

    def test_not_less_than_maps_to_at_least(self):
        params = run("Maintain not less than 15 days of reserve.")
        assert len(params) >= 1
        p = params[0]
        assert p.qualifier == "at_least"

    def test_exactly_qualifier(self):
        params = run("Hold exactly 60 days of inventory.")
        assert len(params) >= 1
        p = params[0]
        assert p.qualifier == "exactly"

    def test_after_qualifier(self):
        params = run("File after 30 days of receipt.")
        assert len(params) >= 1
        p = params[0]
        assert p.qualifier == "after"

    def test_keep_record_retention(self):
        params = run("Keep all records for 3 years.")
        assert len(params) >= 1
        years = [p for p in params if p.unit == "year"]
        assert len(years) >= 1
        assert years[0].kind == ParameterKind.RECORD_RETENTION

    def test_greater_than_threshold(self):
        params = run("If load is greater than 50 customers.")
        assert len(params) >= 1
        cust = [p for p in params if p.unit == "customer"]
        assert len(cust) >= 1
        assert cust[0].kind == ParameterKind.THRESHOLD

    def test_every_frequency(self):
        params = run("Submit every 30 days.")
        assert len(params) >= 1
        p = [p for p in params if p.unit == "day"][0]
        assert p.kind == ParameterKind.FREQUENCY

    def test_per_frequency(self):
        params = run("Usage is measured per month.")
        # "per" triggers frequency, but "month" has no preceding number.
        # Nothing should be extracted without a number.
        month_with_num = [p for p in params if p.unit == "month" and p.value_num is not None]
        assert len(month_with_num) == 0


# ---------------------------------------------------------------------------
# Unit / value extraction
# ---------------------------------------------------------------------------


class TestValueExtraction:
    def test_word_number_five_hundred_meters(self):
        params = run("Install five hundred meters of cable.")
        assert len(params) >= 1
        m_params = [p for p in params if p.unit == "meter"]
        assert len(m_params) >= 1
        assert m_params[0].value_num == 500.0

    def test_word_number_twenty_five_percent(self):
        params = run("Reduce by twenty-five percent.")
        assert len(params) >= 1
        pct = [p for p in params if p.unit == "percent"]
        assert len(pct) >= 1
        assert pct[0].value_num == 25.0

    def test_word_number_two_years(self):
        params = run("Valid for two years.")
        assert len(params) >= 1
        p = [p for p in params if p.unit == "year"][0]
        assert p.value_num == 2.0

    def test_comma_number_1000_gallons(self):
        params = run("Store 1,000 gallons on site.")
        assert len(params) >= 1
        p = [p for p in params if p.unit == "gallon"][0]
        assert p.value_num == 1000.0

    def test_plain_1000_gallons(self):
        # Plain "1000" (no comma) should also work.
        params = run("Store 1000 gallons on site.")
        assert len(params) >= 1
        p = [p for p in params if p.unit == "gallon"][0]
        assert p.value_num == 1000.0

    def test_minutes_day_type_hours(self):
        params = run("Respond within 45 minutes.")
        assert len(params) >= 1
        p = [p for p in params if p.unit == "minute"][0]
        assert p.day_type == DayType.HOURS

    def test_months_day_type_na(self):
        params = run("Review every 3 months.")
        assert len(params) >= 1
        p = [p for p in params if p.unit == "month"][0]
        assert p.day_type == DayType.N_A

    def test_kva_unit(self):
        params = run("System rated at 25 kva.")
        assert len(params) >= 1
        p = [p for p in params if p.unit == "kva"][0]
        assert p.value_num == 25.0

    def test_parenthetical_digit_wins(self):
        # ten (10) → 10, not words_to_number("ten") which is also 10 but via paren
        params = run("Give ten (10) business days notice.")
        assert len(params) >= 1
        p = params[0]
        assert p.value_num == 10.0

    def test_dollar_comma_amount(self):
        params = run("The fee is $1,200.00.")
        assert len(params) >= 1
        p = [p for p in params if p.unit == "usd"][0]
        assert p.value_num == 1200.0

    def test_working_days_day_type(self):
        params = run("Complete within 5 working days.")
        assert len(params) >= 1
        p = params[0]
        assert p.unit == "working_day"
        assert p.day_type == DayType.WORKING

    def test_miles_unit(self):
        params = run("Service area extends 100 miles.")
        assert len(params) >= 1
        p = [p for p in params if p.unit == "mile"][0]
        assert p.value_num == 100.0


# ---------------------------------------------------------------------------
# Verification and provenance
# ---------------------------------------------------------------------------


class TestVerificationAndProvenance:
    def test_verified_true_for_regex_match(self):
        # All regex matches should be verified since they come from exact text.
        params = run("Respond within 10 business days.")
        assert len(params) >= 1
        assert all(p.verified for p in params)

    def test_method_is_regex(self):
        params = run("Submit within 30 days.")
        assert len(params) >= 1
        assert all(p.method == "regex" for p in params)

    def test_value_source_is_none(self):
        params = run("Pay a $50.00 deposit.")
        assert len(params) >= 1
        assert all(p.value_source is None for p in params)

    def test_span_offsets_correct(self):
        text = "Submit within 30 days."
        params = run(text)
        assert len(params) >= 1
        p = params[0]
        assert text[p.span_start:p.span_end] == p.value_text

    def test_ctx_counts_parameters_found(self):
        unit = make_unit("Respond within 10 business days.")
        ctx = RunContext()
        enrich_parameters([unit], ctx)
        assert ctx.stats.get("parameters_found", 0) >= 1

    def test_ctx_counts_parameters_verified(self):
        unit = make_unit("Respond within 10 business days.")
        ctx = RunContext()
        enrich_parameters([unit], ctx)
        assert ctx.stats.get("parameters_verified", 0) >= 1

    def test_multiple_units(self):
        units = [
            make_unit("Complete within 5 business days."),
            make_unit("Pay a $100.00 fee."),
        ]
        ctx = RunContext()
        enrich_parameters(units, ctx)
        assert ctx.stats.get("parameters_found", 0) >= 2

    def test_empty_text_skipped(self):
        unit = make_unit("")
        ctx = RunContext()
        enrich_parameters([unit], ctx)
        assert unit.parameters == []
        assert ctx.stats.get("parameters_found", 0) == 0

    def test_no_false_duplicate(self):
        # "within 10 business days" should produce exactly one parameter,
        # not one from dollar pass + one from main pass.
        params = run("Submit within 10 business days.")
        bus_day = [p for p in params if p.unit == "business_day"]
        assert len(bus_day) == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_hyphen_separator_30_day(self):
        params = run("A 30-day notice is required.")
        assert len(params) >= 1
        p = params[0]
        assert p.value_num == 30.0
        assert p.unit == "day"

    def test_not_more_than_qualifier(self):
        params = run("Bill not more than 5 months in arrears.")
        assert len(params) >= 1
        p = [p for p in params if p.unit == "month"][0]
        assert p.qualifier == "not_more_than"

    def test_business_day_preferred_over_plain_day(self):
        # "business days" should not produce a plain "day" match as well.
        params = run("Respond within 10 business days.")
        units_found = [p.unit for p in params]
        assert "business_day" in units_found
        # plain "day" should NOT appear as a separate entry for the same span
        day_only = [p for p in params if p.unit == "day"]
        business_day = [p for p in params if p.unit == "business_day"]
        # If both exist, they must be at different positions
        if day_only and business_day:
            for d in day_only:
                for b in business_day:
                    # Spans must not overlap
                    assert d.span_end <= b.span_start or d.span_start >= b.span_end

    def test_percent_symbol(self):
        params = run("The rate is 5%.")
        assert len(params) >= 1
        pct = [p for p in params if p.unit == "percent"]
        assert len(pct) >= 1
        assert pct[0].value_num == 5.0

    def test_clause_local_id_not_extracted(self):
        # If local_id equals matched text, skip it.
        params = run("Section 42 requirements.", local_id="42", citations=[_STUB_CITATION])
        bare_42 = [p for p in params if p.value_num == 42.0 and p.unit is None]
        assert len(bare_42) == 0


# ---------------------------------------------------------------------------
# Corpus tests
# ---------------------------------------------------------------------------


@pytest.mark.corpus
def test_corpus_all_verified(tmp_path):
    """All regex parameters extracted from the on-disk corpus are verified."""
    from pathlib import Path
    import importlib
    import sys

    corpus_dir = Path(__file__).parent.parent.parent / "corpus"
    if not corpus_dir.exists():
        pytest.skip("Corpus directory not found")

    # Import the segmenter lazily — not available on CI
    try:
        from app.company_ingest.parse.markdown_segmenter import segment_markdown
    except ImportError:
        pytest.skip("markdown_segmenter not available")

    ctx = RunContext()
    all_units: list[ClauseUnit] = []

    for doc_path in sorted(corpus_dir.glob("**/*.md"))[:12]:
        text_content = doc_path.read_text()
        units = segment_markdown(text_content, doc_id=doc_path.stem, version_id="test")
        all_units.extend(units)

    enrich_parameters(all_units, ctx)

    total = sum(len(u.parameters) for u in all_units)
    unverified = sum(
        1 for u in all_units for p in u.parameters if not p.verified
    )

    assert unverified == 0, f"{unverified} unverified parameters found"
    assert total >= 50, f"Expected ≥50 parameters total, got {total}"


@pytest.mark.corpus
def test_corpus_parameter_count(tmp_path):
    """At least 50 parameters extracted across the corpus documents."""
    from pathlib import Path

    corpus_dir = Path(__file__).parent.parent.parent / "corpus"
    if not corpus_dir.exists():
        pytest.skip("Corpus directory not found")

    try:
        from app.company_ingest.parse.markdown_segmenter import segment_markdown
    except ImportError:
        pytest.skip("markdown_segmenter not available")

    ctx = RunContext()
    all_units: list[ClauseUnit] = []

    for doc_path in sorted(corpus_dir.glob("**/*.md"))[:12]:
        text_content = doc_path.read_text()
        units = segment_markdown(text_content, doc_id=doc_path.stem, version_id="test")
        all_units.extend(units)

    enrich_parameters(all_units, ctx)

    total = ctx.stats.get("parameters_found", 0)
    assert total >= 50, f"Expected ≥50 parameters total, got {total}"
