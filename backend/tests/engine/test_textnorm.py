"""Unit tests for textnorm: metadata-only changes strip equal, wording changes do not."""
from __future__ import annotations

import pytest

from app.engine.textnorm import normalize, strip_metadata
from app.regulatory.ingestion.normalize import normalize_for_diff

_RULE = (
    "(a) A utility shall file the report with the commission each year. "
    "(b) The commission may extend the deadline for good cause."
)


def _iac(authority: str, affected: str, body: str = _RULE, tail: str = "") -> str:
    return f"Authority: {authority} Affected: {affected} {body}{tail}"


def _strip(text: str, source: str) -> str:
    return strip_metadata(normalize(text, source), source)


def test_normalize_wraps_normalize_for_diff():
    raw = "Sec. 4.  (a) A  utility shall file. (Commission; filed Mar 3, 1990: 13 IR 1016)"
    assert normalize(raw, "iac") == normalize_for_diff(raw, "iac")
    assert normalize(raw, "IAC") == normalize_for_diff(raw, "iac")


# --- metadata-only changes: must strip equal --------------------------------

def test_authority_statute_ref_change_equal():
    a = _iac("IC 8-1-1-3 ; IC 8-1-1-5", "IC 8-1")
    b = _iac("IC 8-1-1-3 ; IC 8-1-1-5 ; IC 8-1-2-42", "IC 8-1-2.6-1.5 ; IC 8-1-32.5-4")
    assert normalize(a, "iac") != normalize(b, "iac")
    assert _strip(a, "iac") == _strip(b, "iac") == _RULE


def test_authority_removed_entirely_equal():
    a = _iac("IC 13-14-8 ; IC 13-14-9 ; IC 13-15-1-2", "IC 13-11-2")
    assert _strip(a, "iac") == _strip(_RULE, "iac")


def test_dangling_errata_tail_equal():
    a = _iac("IC 8-1-1-3", "IC 8-1") + " *Copies are available for review."
    b = a + " ; errata filed Jun 3, 2025, 1:59 p.m.: 20250618-IR-326250285ACA )"
    assert normalize(a, "iac") != normalize(b, "iac")
    assert _strip(a, "iac") == _strip(b, "iac")


def test_din_string_equal():
    a = "(a) The rule applies. 20240101-IR-170230001RFA"
    b = "(a) The rule applies. 20250601-IR-170240381RFA"
    assert _strip(a, "iac") == _strip(b, "iac") == "(a) The rule applies."


def test_cfr_source_note_equal():
    body = "(a) The owner shall submit the report within 30 days."
    a = body + " [Order 91, 45 FR 46363, July 10, 1980]"
    b = body + " [Order 91, 45 FR 46363, July 10, 1980; 91 FR 1234, Jan. 5, 2026]"
    assert _strip(a, "cfr") == _strip(b, "cfr") == body


def test_cfr_note_with_editorial_boilerplate_equal():
    body = "(a) The owner shall submit the report within 30 days."
    note = (
        " [58 FR 3650, Jan. 11, 1993] Editorial Note: For Federal Register citations "
        "affecting 35.13, see the List of CFR Sections Affected, which appears in the "
        "Finding Aids section of the printed volume and at www.govinfo.gov."
    )
    assert _strip(body + note, "cfr") == body
    assert _strip(body + " [58 FR 3650, Jan. 11, 1993] ", "cfr") == body


def test_cfr_note_in_middle_of_text_stripped():
    a = "(a) First rule. [60 FR 100, Jan. 2, 1995] (b) Second rule."
    assert _strip(a, "cfr") == "(a) First rule. (b) Second rule."


# --- substantive changes: must stay different --------------------------------

@pytest.mark.parametrize(
    "old,new",
    [
        ("shall file", "may file"),
        ("within 30 days", "within 60 days"),
        ("not later than April 30", "not later than July 31"),
        ("A utility shall file", "A utility shall not file"),
    ],
)
@pytest.mark.parametrize("source", ["iac", "cfr"])
def test_one_word_substantive_change_differs(old, new, source):
    a = _iac("IC 8-1-1-3", "IC 8-1", f"(a) {old} the report.") if source == "iac" else f"(a) {old} the report. [1 FR 2, Jan. 1, 2000]"
    b = _iac("IC 8-1-1-3", "IC 8-1", f"(a) {new} the report.") if source == "iac" else f"(a) {new} the report. [1 FR 2, Jan. 1, 2000]"
    assert _strip(a, source) != _strip(b, source)


def test_inline_statute_reference_in_body_kept():
    a = _iac("IC 8-1-1-3", "IC 8-1", "(a) Comply with IC 8-1-2-4 each year.")
    b = _iac("IC 8-1-1-3", "IC 8-1", "(a) Comply with IC 8-1-2-5 each year.")
    assert _strip(a, "iac") != _strip(b, "iac")


def test_repeal_notice_still_differs_from_text():
    a = _iac("IC 8-1-1-3", "IC 8-1")
    b = "(Repealed by Utility Commission; filed May 22, 2025: 20250618-IR-326240318FRA)"
    assert _strip(a, "iac") != _strip(b, "iac")
    assert "Repealed" in _strip(b, "iac")


# --- edge cases ---------------------------------------------------------------

def test_unknown_source_returns_text_stripped():
    assert strip_metadata("  Authority: IC 1-2 body [1 FR 2]  ", "other") == "Authority: IC 1-2 body [1 FR 2]"
    assert strip_metadata("  text ", "") == "text"


def test_empty_and_case_insensitive():
    assert strip_metadata("", "iac") == ""
    assert strip_metadata(_iac("IC 1-2", "IC 3-4"), "IAC") == _RULE


def test_idempotent_and_deterministic():
    for src, text in [("iac", _iac("IC 1-2", "IC 3-4", tail=" 20250618-IR-326240318FRA")),
                      ("cfr", "(a) Rule text. [58 FR 3650, Jan. 11, 1993]")]:
        once = _strip(text, src)
        assert strip_metadata(once, src) == once
        assert _strip(text, src) == once
