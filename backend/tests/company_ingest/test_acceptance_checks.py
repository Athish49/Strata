"""Tests for Task 8.1.1 — acceptance checks (backend/app/company_ingest/validate/checks.py)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.company_ingest.datasets.profile import DatasetProfile
from app.company_ingest.datasets.propose_checks import CheckProposal
from app.company_ingest.enrich.parameter_entry import ParameterEntry
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.parse.text import sha256_text
from app.company_ingest.run_context import Issue, RunContext
from app.company_ingest.validate.checks import (
    CheckOutcome,
    RunState,
    check_1,
    check_2,
    check_3,
    check_4,
    check_5,
    check_6,
    check_7,
    check_8,
    check_9,
    check_10,
    check_11,
    check_12,
    run_all_checks,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _unit(
    clause_id: str = "DOC1:C1",
    text_raw: str = "Some clause text.",
    role: str | None = "obligation",
    citations: list | None = None,
    parameters: list | None = None,
) -> ClauseUnit:
    """Build a minimal ClauseUnit with correct sha256."""
    return ClauseUnit(
        version_id="ver-1",
        doc_id=clause_id.split(":")[0],
        clause_id=clause_id,
        local_id=clause_id.split(":", 1)[1],
        parent_clause_id=None,
        unit_kind="clause",
        heading_path=[],
        section_kind="body",
        ordinal=0,
        char_start=0,
        char_end=len(text_raw),
        line_start=0,
        text_raw=text_raw,
        text_norm=text_raw.lower(),
        text_sha256=sha256_text(text_raw),
        role=role,
        citations=citations if citations is not None else [],
        parameters=parameters if parameters is not None else [],
    )


def _state(
    units: list | None = None,
    stats: dict | None = None,
    issues: list | None = None,
    dataset_profiles: list | None = None,
    check_proposals: list | None = None,
) -> RunState:
    return RunState(
        units=units or [],
        links=[],
        scope_rows=[],
        dataset_profiles=dataset_profiles or [],
        check_proposals=check_proposals or [],
        doc_ids=["DOC1"],
        stats=stats or {},
        issues=issues or [],
    )


def _param_entry(method: str = "regex", verified: bool = True) -> ParameterEntry:
    return ParameterEntry(
        kind="period",
        unit="day",
        value_text="30 days",
        value_num=30.0,
        value_source=None,
        qualifier=None,
        day_type="n_a",
        span_start=0,
        span_end=7,
        method=method,
        verified=verified,
    )


def _profile(name: str = "ds1", row_count: int = 100) -> DatasetProfile:
    return DatasetProfile(
        name=name,
        doc_id="DOC1",
        row_count=row_count,
        file_sha256="abc",
        r2_parquet_key="r2/key.parquet",
        r2_source_key="r2/source.csv",
        primary_key=None,
        columns=[],
    )


def _proposal(dataset_name: str = "ds1", validated: bool = False) -> CheckProposal:
    return CheckProposal(
        dataset_name=dataset_name,
        doc_id="DOC1",
        purpose="Check something.",
        sql_template="SELECT * FROM ds1 WHERE val > {x}",
        param_bindings={"x": "pk1"},
        validated=validated,
    )


def _issue(
    code: str = "some_issue",
    severity: str = "warning",
    stage: str = "parse",
) -> Issue:
    return Issue(severity=severity, stage=stage, code=code, message="test issue")


# ---------------------------------------------------------------------------
# Check 1: unclaimed text ≤ 5%
# ---------------------------------------------------------------------------


def test_check_1_passes_when_unclaimed_within_threshold():
    """Unclaimed chars ≤ 5% of total → passes."""
    text = "a" * 100
    u = _unit(text_raw=text)
    state = _state(units=[u], stats={"unclaimed_text_chars": 4})
    outcome = check_1(state)
    assert outcome.passed is True
    assert outcome.check_number == 1


def test_check_1_fails_when_unclaimed_exceeds_threshold():
    """Unclaimed chars > 5% of total → fails."""
    text = "a" * 100
    u = _unit(text_raw=text)
    state = _state(units=[u], stats={"unclaimed_text_chars": 10})
    outcome = check_1(state)
    assert outcome.passed is False
    assert "10/100" in outcome.metric


def test_check_1_passes_when_no_units():
    """No units (total_chars=0) → passes (nothing to fail)."""
    state = _state(units=[], stats={"unclaimed_text_chars": 0})
    outcome = check_1(state)
    assert outcome.passed is True


def test_check_1_metric_format():
    """Metric string has expected format."""
    u = _unit(text_raw="x" * 50)
    state = _state(units=[u], stats={"unclaimed_text_chars": 1})
    outcome = check_1(state)
    assert "unclaimed chars" in outcome.metric


# ---------------------------------------------------------------------------
# Check 2: no duplicate clause IDs
# ---------------------------------------------------------------------------


def test_check_2_passes_with_unique_ids():
    """All clause_ids are unique → passes."""
    u1 = _unit("DOC1:C1")
    u2 = _unit("DOC1:C2")
    state = _state(units=[u1, u2])
    outcome = check_2(state)
    assert outcome.passed is True
    assert outcome.metric == "0 duplicates"


def test_check_2_fails_with_duplicate_ids():
    """Two units share a clause_id → fails."""
    u1 = _unit("DOC1:C1")
    u2 = _unit("DOC1:C1")
    state = _state(units=[u1, u2])
    outcome = check_2(state)
    assert outcome.passed is False
    assert "1 duplicates" in outcome.metric
    assert "DOC1:C1" in outcome.details["first_10_duplicates"]


def test_check_2_reports_multiple_duplicates():
    """Multiple duplicated IDs are all reported."""
    units = [_unit(f"DOC1:C{i}") for i in range(3)]
    units.append(_unit("DOC1:C0"))  # duplicate C0
    units.append(_unit("DOC1:C1"))  # duplicate C1
    state = _state(units=units)
    outcome = check_2(state)
    assert outcome.passed is False
    assert len(outcome.details["first_10_duplicates"]) == 2


# ---------------------------------------------------------------------------
# Check 3: all text_sha256 verified
# ---------------------------------------------------------------------------


def test_check_3_passes_when_all_hashes_match():
    """All text_sha256 match → passes."""
    u1 = _unit("DOC1:C1", text_raw="hello world")
    u2 = _unit("DOC1:C2", text_raw="goodbye world")
    state = _state(units=[u1, u2])
    outcome = check_3(state)
    assert outcome.passed is True
    assert outcome.metric.startswith("0/2")


def test_check_3_fails_when_hash_is_wrong():
    """One unit has a wrong sha256 → fails."""
    u = _unit("DOC1:C1", text_raw="actual text")
    u.text_sha256 = "0" * 64  # wrong hash
    state = _state(units=[u])
    outcome = check_3(state)
    assert outcome.passed is False
    assert "1/1" in outcome.metric
    assert "DOC1:C1" in outcome.details["first_10_mismatches"]


def test_check_3_correct_count_of_mismatches():
    """Only mismatching units are counted."""
    u1 = _unit("DOC1:C1", text_raw="good")
    u2 = _unit("DOC1:C2", text_raw="also good")
    u3 = _unit("DOC1:C3", text_raw="bad")
    u3.text_sha256 = "f" * 64
    state = _state(units=[u1, u2, u3])
    outcome = check_3(state)
    assert outcome.passed is False
    assert "1/3" in outcome.metric


# ---------------------------------------------------------------------------
# Check 4: all regex parameters verified
# ---------------------------------------------------------------------------


def test_check_4_passes_when_all_regex_verified():
    """All regex params have verified=True → passes."""
    p = _param_entry(method="regex", verified=True)
    u = _unit(parameters=[p])
    state = _state(units=[u])
    outcome = check_4(state)
    assert outcome.passed is True
    assert "0 unverified" in outcome.metric


def test_check_4_fails_when_regex_param_not_verified():
    """A regex param with verified=False → fails."""
    p = _param_entry(method="regex", verified=False)
    u = _unit(parameters=[p])
    state = _state(units=[u])
    outcome = check_4(state)
    assert outcome.passed is False
    assert "1 unverified" in outcome.metric


def test_check_4_ignores_non_regex_params():
    """Parameters with method!='regex' are ignored regardless of verified."""
    p = _param_entry(method="llm", verified=False)
    u = _unit(parameters=[p])
    state = _state(units=[u])
    outcome = check_4(state)
    assert outcome.passed is True


# ---------------------------------------------------------------------------
# Check 5: no regulatory_restatement without citation
# ---------------------------------------------------------------------------


def test_check_5_passes_when_restatement_has_citation():
    """regulatory_restatement with citations → passes."""
    u = _unit(role="regulatory_restatement", citations=["cit1"])
    state = _state(units=[u])
    outcome = check_5(state)
    assert outcome.passed is True
    assert "0 violations" in outcome.metric


def test_check_5_fails_when_restatement_lacks_citation():
    """regulatory_restatement with no citations → fails."""
    u = _unit(role="regulatory_restatement", citations=[])
    state = _state(units=[u])
    outcome = check_5(state)
    assert outcome.passed is False
    assert "1 violations" in outcome.metric


def test_check_5_ignores_other_roles():
    """Units with other roles and no citations do not trigger the check."""
    u = _unit(role="obligation", citations=[])
    state = _state(units=[u])
    outcome = check_5(state)
    assert outcome.passed is True


# ---------------------------------------------------------------------------
# Check 6: all eligible units have a role
# ---------------------------------------------------------------------------


def test_check_6_passes_when_all_eligible_have_role():
    """Eligible units all have roles → passes."""
    u1 = _unit("DOC1:C1", role="obligation")
    u2 = _unit("DOC1:C2", role="definition")
    state = _state(units=[u1, u2])
    outcome = check_6(state)
    assert outcome.passed is True


def test_check_6_fails_when_eligible_unit_has_no_role():
    """An eligible unit with role=None → fails."""
    u = _unit("DOC1:C1", role=None)
    state = _state(units=[u])
    outcome = check_6(state)
    assert outcome.passed is False
    assert "DOC1:C1" in outcome.details["undecided_clause_ids"]


def test_check_6_skips_boilerplate_units():
    """Boilerplate units are not eligible and are skipped."""
    u1 = _unit("DOC1:C1", role="boilerplate")  # should_enrich=False
    u2 = _unit("DOC1:C2", role="obligation")
    state = _state(units=[u1, u2])
    outcome = check_6(state)
    assert outcome.passed is True


def test_check_6_skips_empty_text_units():
    """Units with empty text are not eligible."""
    u = _unit("DOC1:C1", text_raw="   ", role=None)
    state = _state(units=[u])
    outcome = check_6(state)
    assert outcome.passed is True


# ---------------------------------------------------------------------------
# Check 7: reference resolution ≥ 80%
# ---------------------------------------------------------------------------


def test_check_7_passes_when_no_refs():
    """No references at all → passes (vacuously true)."""
    state = _state(stats={"links_resolved": 0, "links_unresolved": 0})
    outcome = check_7(state)
    assert outcome.passed is True
    assert "0/0" in outcome.metric


def test_check_7_passes_when_resolution_above_threshold():
    """80 resolved, 20 unresolved (80%) → passes."""
    state = _state(stats={"links_resolved": 80, "links_unresolved": 20})
    outcome = check_7(state)
    assert outcome.passed is True
    assert "80/100" in outcome.metric


def test_check_7_fails_when_resolution_below_threshold():
    """0 resolved, 1 unresolved (0%) → fails."""
    state = _state(stats={"links_resolved": 0, "links_unresolved": 1})
    outcome = check_7(state)
    assert outcome.passed is False
    assert "0/1" in outcome.metric


def test_check_7_fails_just_below_threshold():
    """79 resolved, 21 unresolved (79%) → fails."""
    state = _state(stats={"links_resolved": 79, "links_unresolved": 21})
    outcome = check_7(state)
    assert outcome.passed is False


# ---------------------------------------------------------------------------
# Check 8: all front-matter regulatory_basis in scope
# ---------------------------------------------------------------------------


def test_check_8_passes_when_no_unresolved_front_matter():
    """No front_matter_citation_not_found issues → passes."""
    state = _state(issues=[_issue(code="some_other_issue")])
    outcome = check_8(state)
    assert outcome.passed is True
    assert "0 unresolved" in outcome.metric


def test_check_8_fails_when_front_matter_citation_not_found():
    """An issue with code=front_matter_citation_not_found → fails."""
    bad_issue = _issue(code="front_matter_citation_not_found", severity="warning", stage="6.1.3")
    state = _state(issues=[bad_issue])
    outcome = check_8(state)
    assert outcome.passed is False
    assert "1 unresolved" in outcome.metric


def test_check_8_ignores_other_issue_codes():
    """Issues with different codes are not counted."""
    state = _state(issues=[
        _issue(code="unresolved_ref"),
        _issue(code="r2_upload_failed"),
    ])
    outcome = check_8(state)
    assert outcome.passed is True


# ---------------------------------------------------------------------------
# Check 9: Parquet row counts match CSV
# ---------------------------------------------------------------------------


def test_check_9_skips_when_no_profiles():
    """No dataset profiles → skipped (passes)."""
    state = _state(dataset_profiles=[])
    outcome = check_9(state)
    assert outcome.passed is True
    assert "skipped" in outcome.metric


def test_check_9_passes_when_all_profiles_have_rows():
    """All profiles have row_count > 0 → passes."""
    p1 = _profile("ds1", 50)
    p2 = _profile("ds2", 100)
    state = _state(dataset_profiles=[p1, p2])
    outcome = check_9(state)
    assert outcome.passed is True
    assert "2 datasets" in outcome.metric


def test_check_9_fails_when_profile_has_zero_rows():
    """A profile with row_count=0 → fails."""
    p = _profile("ds1", 0)
    state = _state(dataset_profiles=[p])
    outcome = check_9(state)
    assert outcome.passed is False
    assert "ds1" in outcome.details["empty_datasets"]


# ---------------------------------------------------------------------------
# Check 10: parameter checks validated
# ---------------------------------------------------------------------------


def test_check_10_skips_when_no_proposals():
    """No check proposals → skipped (passes)."""
    state = _state(check_proposals=[])
    outcome = check_10(state)
    assert outcome.passed is True
    assert "skipped" in outcome.metric


def test_check_10_passes_when_at_least_one_validated():
    """At least 1 validated check per dataset → passes."""
    p1 = _proposal("ds1", validated=True)
    p2 = _proposal("ds1", validated=False)
    state = _state(check_proposals=[p1, p2])
    outcome = check_10(state)
    assert outcome.passed is True
    assert "1/2" in outcome.metric


def test_check_10_fails_when_none_validated_for_dataset():
    """0 validated out of 1 proposal → fails."""
    p = _proposal("ds1", validated=False)
    state = _state(check_proposals=[p])
    outcome = check_10(state)
    assert outcome.passed is False
    assert "0/1" in outcome.metric
    assert "ds1" in outcome.details["datasets_without_validated_check"]


def test_check_10_fails_when_one_dataset_lacks_validated():
    """Two datasets: one has validated, the other doesn't → fails."""
    p1 = _proposal("ds1", validated=True)
    p2 = _proposal("ds2", validated=False)
    state = _state(check_proposals=[p1, p2])
    outcome = check_10(state)
    assert outcome.passed is False
    assert "ds2" in outcome.details["datasets_without_validated_check"]


# ---------------------------------------------------------------------------
# Check 11: Qdrant round-trip (always passes in offline mode)
# ---------------------------------------------------------------------------


def test_check_11_always_passes():
    """Check 11 always passes (offline mode)."""
    state = _state()
    outcome = check_11(state)
    assert outcome.passed is True
    assert "skipped" in outcome.metric
    assert outcome.check_number == 11


def test_check_11_passes_regardless_of_state():
    """Check 11 passes even with error-filled state."""
    state = _state(
        issues=[_issue(code="some_error", severity="error", stage="collect.1")],
        stats={"links_unresolved": 999},
    )
    outcome = check_11(state)
    assert outcome.passed is True


# ---------------------------------------------------------------------------
# Check 12: no denied files in R2
# ---------------------------------------------------------------------------


def test_check_12_passes_when_denied_paths_and_no_collect_errors():
    """denied_paths > 0 and no collect errors → passes."""
    state = _state(stats={"denied_paths": 3})
    outcome = check_12(state)
    assert outcome.passed is True
    assert "3 denied paths" in outcome.metric


def test_check_12_fails_when_denied_paths_is_zero():
    """denied_paths=0 → fails (allowlist not exercised)."""
    state = _state(stats={"denied_paths": 0})
    outcome = check_12(state)
    assert outcome.passed is False
    assert "0 denied paths" in outcome.metric


def test_check_12_fails_when_collect_error_exists():
    """denied_paths > 0 but a collect error exists → fails."""
    collect_error = _issue(code="access_denied", severity="error", stage="collect.1")
    state = _state(stats={"denied_paths": 2}, issues=[collect_error])
    outcome = check_12(state)
    assert outcome.passed is False
    assert outcome.details["collect_error_count"] == 1


def test_check_12_ignores_non_collect_errors():
    """Errors in stages other than 'collect*' do not affect check 12."""
    parse_error = _issue(code="parse_failed", severity="error", stage="parse.1")
    state = _state(stats={"denied_paths": 1}, issues=[parse_error])
    outcome = check_12(state)
    assert outcome.passed is True


# ---------------------------------------------------------------------------
# run_all_checks orchestrator
# ---------------------------------------------------------------------------


def test_run_all_checks_returns_12_outcomes():
    """run_all_checks returns exactly 12 CheckOutcome objects."""
    ctx = RunContext()
    units = [
        _unit("DOC1:C1", role="obligation"),
        _unit("DOC1:C2", role="definition"),
    ]
    state = _state(
        units=units,
        stats={"denied_paths": 1, "links_resolved": 5, "links_unresolved": 0},
    )
    outcomes = run_all_checks(state, ctx)
    assert len(outcomes) == 12
    for i, outcome in enumerate(outcomes, 1):
        assert outcome.check_number == i


def test_run_all_checks_exception_does_not_halt_others():
    """If one check raises, remaining checks still run and get failed outcomes."""
    ctx = RunContext()
    state = _state()

    from unittest.mock import patch

    # Make check_1 raise; all others should still run
    with patch(
        "app.company_ingest.validate.checks.check_1",
        side_effect=RuntimeError("boom"),
    ):
        outcomes = run_all_checks(state, ctx)

    assert len(outcomes) == 12
    # First outcome is the error placeholder
    assert outcomes[0].passed is False
    assert "boom" in outcomes[0].details.get("error", "")
    # Other outcomes should be present (may pass or fail, but they ran)
    assert outcomes[1].check_number == 2


def test_run_all_checks_all_check_numbers_present():
    """All 12 check numbers 1–12 are present in outputs."""
    ctx = RunContext()
    state = _state(stats={"denied_paths": 1})
    outcomes = run_all_checks(state, ctx)
    numbers = [o.check_number for o in outcomes]
    assert numbers == list(range(1, 13))


def test_run_all_checks_outcome_names_are_non_empty():
    """Every outcome has a non-empty name string."""
    ctx = RunContext()
    state = _state(stats={"denied_paths": 1})
    outcomes = run_all_checks(state, ctx)
    for o in outcomes:
        assert isinstance(o.name, str) and len(o.name) > 0
