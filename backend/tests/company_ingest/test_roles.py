"""Tests for task 4.1.4 — deterministic clause-role markers."""
from __future__ import annotations

import pytest

from app.company_ingest.enrich.roles import enrich_roles
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_unit(
    text_raw: str = "Some clause text.",
    unit_kind: str = "section",
    section_kind: str = "procedure",
    **kwargs,
) -> ClauseUnit:
    defaults = dict(
        version_id="ver-1",
        doc_id="doc-1",
        clause_id="doc-1:c1",
        local_id="c1",
        parent_clause_id=None,
        unit_kind=unit_kind,
        heading_path=[],
        section_kind=section_kind,
        ordinal=0,
        char_start=0,
        char_end=len(text_raw),
        line_start=1,
        text_raw=text_raw,
        text_norm=text_raw.lower(),
        text_sha256="abc",
    )
    defaults.update(kwargs)
    return ClauseUnit(**defaults)


def run(units: list[ClauseUnit]) -> RunContext:
    ctx = RunContext()
    enrich_roles(units, ctx)
    return ctx


# ---------------------------------------------------------------------------
# Tests 1-12: role assignment
# ---------------------------------------------------------------------------

def test_internal_target_marker():
    """Test 1: text starting with 'Internal performance target:' → internal_target/marker"""
    u = make_unit(text_raw="Internal performance target: resolve 95% of tickets in 2 days")
    run([u])
    assert u.role == "internal_target"
    assert u.role_method == "marker"


def test_company_position_marker():
    """Test 2: text starting with 'Company position:' → company_position/marker"""
    u = make_unit(text_raw="Company position: we comply with all applicable regulations")
    run([u])
    assert u.role == "company_position"
    assert u.role_method == "marker"


def test_form_field_heuristic():
    """Test 3: unit_kind=form_field → template_field/heuristic"""
    u = make_unit(unit_kind="form_field", text_raw="Date of review: ___________")
    run([u])
    assert u.role == "template_field"
    assert u.role_method == "heuristic"


def test_company_position_beats_form_field():
    """Test 4: 'Company position:' text with unit_kind=form_field → company_position (rule 2 > rule 3)"""
    u = make_unit(
        unit_kind="form_field",
        text_raw="Company position: this overrides the form_field heuristic",
    )
    run([u])
    assert u.role == "company_position"
    assert u.role_method == "marker"


def test_definitions_section_heuristic():
    """Test 5: section_kind=definitions → definition/heuristic"""
    u = make_unit(section_kind="definitions", text_raw="A word that means something.")
    run([u])
    assert u.role == "definition"
    assert u.role_method == "heuristic"


def test_definition_grammar_means():
    """Test 6: **Term** means something → definition/grammar"""
    u = make_unit(text_raw="**Business Day** means any day the bank is open.")
    run([u])
    assert u.role == "definition"
    assert u.role_method == "grammar"


def test_definition_grammar_is():
    """Test 7: **Another Term** is defined as → definition/grammar"""
    u = make_unit(text_raw="**Another Term** is defined as the period between events.")
    run([u])
    assert u.role == "definition"
    assert u.role_method == "grammar"


def test_revision_history_boilerplate():
    """Test 8: section_kind=revision_history → boilerplate"""
    u = make_unit(section_kind="revision_history", text_raw="v1.0 - initial release")
    run([u])
    assert u.role == "boilerplate"


def test_approval_boilerplate():
    """Test 9: section_kind=approval → boilerplate"""
    u = make_unit(section_kind="approval", text_raw="Approved by: CEO")
    run([u])
    assert u.role == "boilerplate"


def test_related_docs_boilerplate():
    """Test 10: section_kind=related_docs → boilerplate"""
    u = make_unit(section_kind="related_docs", text_raw="See also: Policy XYZ")
    run([u])
    assert u.role == "boilerplate"


def test_front_matter_boilerplate():
    """Test 11: section_kind=front_matter → boilerplate"""
    u = make_unit(section_kind="front_matter", text_raw="Document title and classification")
    run([u])
    assert u.role == "boilerplate"


def test_register_row_regulatory_restatement():
    """Test 12: unit_kind=register_row → regulatory_restatement"""
    u = make_unit(unit_kind="register_row", text_raw="Obligation ID: 42, text: comply with rule")
    run([u])
    assert u.role == "regulatory_restatement"
    assert u.role_method == "heuristic"


def test_normal_clause_undecided():
    """Test 13: ordinary section clause → role=None"""
    u = make_unit(
        section_kind="procedure",
        unit_kind="section",
        text_raw="The team shall review all incidents within 30 days.",
    )
    run([u])
    assert u.role is None


# ---------------------------------------------------------------------------
# Tests 14-17: assessable flag
# ---------------------------------------------------------------------------

def test_assessable_false_for_boilerplate():
    """Test 14: role=boilerplate → assessable=False"""
    u = make_unit(section_kind="revision_history", text_raw="v1.2 - update")
    run([u])
    assert u.assessable is False


def test_assessable_true_for_internal_target():
    """Test 15: role=internal_target → assessable=True"""
    u = make_unit(text_raw="Internal performance target: 99.9% uptime")
    run([u])
    assert u.assessable is True


def test_assessable_true_for_none_role():
    """Test 16: role=None → assessable=True (provisional)"""
    u = make_unit(
        section_kind="procedure",
        unit_kind="section",
        text_raw="Review all documents.",
    )
    run([u])
    assert u.role is None
    assert u.assessable is True


def test_assessable_false_for_approval_section_regardless_of_role():
    """Test 17: section_kind=approval → assessable=False regardless of computed role"""
    # approval section gets role=boilerplate but assessable override is via section check
    u = make_unit(section_kind="approval", text_raw="Approved by Director")
    run([u])
    assert u.assessable is False


# ---------------------------------------------------------------------------
# Tests 18-20: counting
# ---------------------------------------------------------------------------

def test_count_roles_deterministic():
    """Test 18: ctx.count('roles_deterministic') incremented for decided roles"""
    units = [
        make_unit(text_raw="Internal performance target: metric"),
        make_unit(section_kind="definitions", text_raw="term explanation"),
    ]
    ctx = run(units)
    assert ctx.stats.get("roles_deterministic", 0) == 2


def test_count_roles_undecided():
    """Test 19: ctx.count('roles_undecided') incremented for None roles"""
    units = [
        make_unit(section_kind="procedure", unit_kind="section", text_raw="Do the thing."),
        make_unit(section_kind="scope", unit_kind="section", text_raw="Applies to all staff."),
    ]
    ctx = run(units)
    assert ctx.stats.get("roles_undecided", 0) == 2


def test_multiple_units_partial_match():
    """Test 20: multiple units — only matching units get roles, others stay None"""
    units = [
        make_unit(text_raw="Company position: our stance", unit_kind="section", section_kind="scope"),
        make_unit(text_raw="Regular policy clause.", unit_kind="section", section_kind="procedure"),
        make_unit(unit_kind="register_row", text_raw="reg obligation row"),
    ]
    ctx = run(units)

    assert units[0].role == "company_position"
    assert units[1].role is None
    assert units[2].role == "regulatory_restatement"

    assert ctx.stats.get("roles_deterministic", 0) == 2
    assert ctx.stats.get("roles_undecided", 0) == 1
