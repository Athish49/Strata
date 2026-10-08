"""Unit tests for normalize_for_diff: cosmetic changes normalize equal, wording changes do not."""
from __future__ import annotations

import pytest

from app.regulatory.ingestion.normalize import normalize_for_diff

_BODY = (
    "Sec. 4. (a) A utility shall file the report with the commission each year. "
    "(b) The commission may extend the deadline for good cause."
)
_FOOTER_OLD = (
    "(Indiana Utility Regulatory Commission; 170 IAC 1-1-4; filed Mar 3, 1990, 4:00 p.m.: "
    "13 IR 1016; readopted filed Sep 5, 2013, 10:09 a.m.: 20131009-IR-170130182RFA)"
)
_READOPT = "readopted filed Sep 12, 2025, 11:43 a.m.: 20251001-IR-170240381RFA"


def _iac(a: str, b: str) -> tuple[str, str]:
    return normalize_for_diff(a, "iac"), normalize_for_diff(b, "iac")


def _footer_with(extra: str) -> str:
    return _FOOTER_OLD[:-1] + extra + ")"


# --- cosmetic pairs: must normalize equal -----------------------------------

_READOPTION_PAIRS = [
    # appended readoption entry, plain footer at end
    (f"{_BODY} {_FOOTER_OLD}", f"{_BODY} {_footer_with('; ' + _READOPT)}"),
    # same, with a trailing NOTE after the footer
    (f"{_BODY} {_FOOTER_OLD} NOTE: Transferred from the Board by P.L.249-2019.",
     f"{_BODY} {_footer_with('; ' + _READOPT)} NOTE: Transferred from the Board by P.L.249-2019."),
    # errata entry appended
    (f"{_BODY} {_FOOTER_OLD}",
     f"{_BODY} {_footer_with('; errata filed Dec 31, 2024, 11:23 a.m.: 20250108-IR-170240264ACA')}"),
    # readoption plus a DIN-spaced IR code in the old entry
    (f"{_BODY} {_FOOTER_OLD.replace('IR-170130', 'IR- 170130')}",
     f"{_BODY} {_footer_with('; ' + _READOPT)}"),
    # footer with a nested parenthetical
    (f"{_BODY} (Agency; 170 IAC 1-1-4; filed Mar 3, 1990: 13 IR 1016 (eff Jan 1, 1991))",
     f"{_BODY} (Agency; 170 IAC 1-1-4; filed Mar 3, 1990: 13 IR 1016 (eff Jan 1, 1991); {_READOPT})"),
    # footer where the old section had no modern IR code at all
    (f"{_BODY} (Agency; 170 IAC 1-1-4; filed Mar 3, 1990, 4:00 p.m.: 13 IR 1016)",
     f"{_BODY} (Agency; 170 IAC 1-1-4; filed Mar 3, 1990, 4:00 p.m.: 13 IR 1016; {_READOPT})"),
    # multi-section body: readoption on the first sub-section's footer
    (f"{_BODY} {_FOOTER_OLD} Sec. 5. A utility shall keep records. {_FOOTER_OLD}",
     f"{_BODY} {_footer_with('; ' + _READOPT)} Sec. 5. A utility shall keep records. {_FOOTER_OLD}"),
    # S2 gains the section marker that S1 lacks
    (f"(a) A utility shall file the report. {_FOOTER_OLD}",
     f"Sec. 4. (a) A utility shall file the report. {_footer_with('; ' + _READOPT)}"),
    # readoption stamp with space after IR-
    (f"{_BODY} {_FOOTER_OLD}",
     f"{_BODY} {_footer_with('; readopted filed Sep 12, 2025: 20251001-IR- 170240381RFA')}"),
    # whitespace and line-break differences
    (f"{_BODY} {_FOOTER_OLD}",
     f"{_BODY.replace('. (b)', '.\n\n(b)')}   {_footer_with('; ' + _READOPT)}"),
    # several readoption entries appended at once
    (f"{_BODY} {_FOOTER_OLD}",
     f"{_BODY} {_footer_with('; ' + _READOPT + '; readopted filed Oct 1, 2025: 20251101-IR-170250001RFA')}"),
]


@pytest.mark.parametrize("old,new", _READOPTION_PAIRS)
def test_readoption_only_pairs_normalize_equal(old, new):
    assert old != new
    a, b = _iac(old, new)
    assert a == b


def test_readoption_pair_count():
    assert len(_READOPTION_PAIRS) >= 10


@pytest.mark.parametrize(
    "old,new",
    [
        ("see 170 IAC 4-3- 12 for details", "see 170 IAC 4-3-12 for details"),
        ("effective 20100623-IR- 170090792FRA here", "effective 20100623-IR-170090792FRA here"),
        ("The fee is fifty- four dollars.", "The fee is fifty-four dollars."),
        ("per P.L.101- 549 requirements", "per P.L.101-549 requirements"),
        ("Designation A - 3 applies", "Designation A -3 applies"),
    ],
)
def test_din_spacing_variants_normalize_equal(old, new):
    a, b = _iac(old, new)
    assert a == b


def test_cfr_source_note_extension_is_cosmetic():
    old = "A seller must keep records. [Order 697, 72 FR 40038, July 20, 2007]"
    new = ("A seller must keep records. [Order 697, 72 FR 40038, July 20, 2007, "
           "as amended by Order 768, 77 FR 61924, Oct. 11, 2012]")
    assert normalize_for_diff(old, "cfr") == normalize_for_diff(new, "cfr")


def test_cfr_amendment_link_is_cosmetic():
    old = "You must comply with this section."
    new = old + " Link to an amendment published at 91 FR 58997, Sept. 17, 2026."
    assert normalize_for_diff(old, "cfr") == normalize_for_diff(new, "cfr")


# --- substantive pairs: must still differ -----------------------------------

_SUBSTANTIVE_PAIRS = [
    ("shall not", "may not"),
    ("A utility shall file the report.", "A utility may file the report."),
    ("within thirty (30) days", "within sixty (60) days"),
    ("A utility shall file the report.", "A utility shall not file the report."),
    ("not later than April 30", "not later than July 31"),
    ("each year", "every two years"),
    ("applies to a public utility", "applies to a municipal utility"),
]


@pytest.mark.parametrize("old,new", _SUBSTANTIVE_PAIRS)
@pytest.mark.parametrize("system", ["iac", "cfr"])
def test_one_word_substantive_pairs_differ(old, new, system):
    base = "The commission finds that {} under this rule."
    footer = f" {_FOOTER_OLD}" if system == "iac" else " [Order 1, 70 FR 1, Jan. 1, 2005]"
    a = normalize_for_diff(base.format(old) + footer, system)
    b = normalize_for_diff(base.format(new) + footer, system)
    assert a != b


def test_substantive_pair_count():
    assert len(_SUBSTANTIVE_PAIRS) >= 5


def test_substantive_change_next_to_readoption_still_differs():
    old = f"{_BODY} {_FOOTER_OLD}"
    new = f"{_BODY.replace('shall', 'may')} {_footer_with('; ' + _READOPT)}"
    a, b = _iac(old, new)
    assert a != b


def test_repeal_is_not_cosmetic():
    live = f"{_BODY} {_FOOTER_OLD}"
    repealed = "Sec. 4. (Repealed by Indiana Utility Regulatory Commission; filed May 25, 2010: 20100623-IR-170090792FRA)"
    a, b = _iac(live, repealed)
    assert a != b


def test_empty_and_unknown_system():
    assert normalize_for_diff("", "iac") == ""
    assert normalize_for_diff("a   b", "other") == "a b"
