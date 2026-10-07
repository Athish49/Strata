"""Tests for task 1.1.1: package skeleton, config, constants, ids."""
import uuid

import pytest

from app.company_ingest.constants import (
    ClauseRole,
    ColumnRole,
    DayType,
    DocClass,
    LinkType,
    ParameterKind,
    Profile,
    Qualifier,
    SemanticRole,
    SectionKind,
    UnitKind,
)
from app.company_ingest.ids import UUID_NAMESPACE, stable_uuid


# ---------------------------------------------------------------------------
# Profile enum
# ---------------------------------------------------------------------------

def test_profile_values():
    assert Profile.P1_PROSE == "p1_prose"
    assert Profile.P2_REGISTER == "p2_register"
    assert Profile.P3_DATASET == "p3_dataset"
    assert Profile.P4_REFERENCE == "p4_reference"
    assert Profile.RENDER == "render"


# ---------------------------------------------------------------------------
# DocClass enum
# ---------------------------------------------------------------------------

def test_doc_class_values():
    expected = {"procedure", "plan", "tariff", "register", "calendar", "retention_schedule", "reference"}
    assert set(DocClass) == expected


# ---------------------------------------------------------------------------
# UnitKind enum
# ---------------------------------------------------------------------------

def test_unit_kind_values():
    expected = {"section", "appendix", "form_field", "table_row", "tariff_subrule", "register_row", "other"}
    assert set(UnitKind) == expected


# ---------------------------------------------------------------------------
# SectionKind enum
# ---------------------------------------------------------------------------

def test_section_kind_values():
    expected = {
        "purpose", "scope", "definitions", "regulatory_basis", "roles",
        "procedure", "records", "training", "related_docs", "revision_history",
        "approval", "appendix", "front_matter", "other",
    }
    assert set(SectionKind) == expected


# ---------------------------------------------------------------------------
# ClauseRole enum
# ---------------------------------------------------------------------------

def test_clause_role_values():
    expected = {
        "internal_target", "company_position", "template_field", "definition",
        "boilerplate", "regulatory_restatement", "out_of_scope_reference",
        "internal_procedure", "informational",
    }
    assert set(ClauseRole) == expected


# ---------------------------------------------------------------------------
# ParameterKind enum
# ---------------------------------------------------------------------------

def test_parameter_kind_values():
    expected = {
        "number", "period", "deadline", "frequency", "threshold", "amount",
        "qualifier", "condition", "exception", "party", "channel",
        "content_element", "applicability", "record_retention",
    }
    assert set(ParameterKind) == expected


# ---------------------------------------------------------------------------
# Qualifier enum
# ---------------------------------------------------------------------------

def test_qualifier_values():
    expected = {"within", "at_least", "not_more_than", "not_less_than", "prior_to", "after", "exactly"}
    assert set(Qualifier) == expected


# ---------------------------------------------------------------------------
# DayType enum
# ---------------------------------------------------------------------------

def test_day_type_values():
    expected = {"calendar", "business", "working", "hours", "n_a"}
    assert set(DayType) == expected


# ---------------------------------------------------------------------------
# LinkType enum
# ---------------------------------------------------------------------------

def test_link_type_values():
    expected = {
        "references_doc", "references_clause", "references_tariff",
        "references_form", "references_record_series", "references_obligation", "restates",
    }
    assert set(LinkType) == expected


# ---------------------------------------------------------------------------
# ColumnRole enum
# ---------------------------------------------------------------------------

def test_column_role_values():
    expected = {
        "id", "citation", "regulatory_value", "rule_quote", "summary_text",
        "reference_list", "owner_person", "date", "enum", "status", "free_text", "ignore",
    }
    assert set(ColumnRole) == expected


# ---------------------------------------------------------------------------
# SemanticRole enum
# ---------------------------------------------------------------------------

def test_semantic_role_values():
    expected = {"id", "foreign_key", "timestamp", "duration", "quantity", "flag", "category", "clause_ref", "free_text"}
    assert set(SemanticRole) == expected


# ---------------------------------------------------------------------------
# stable_uuid — determinism
# ---------------------------------------------------------------------------

def test_stable_uuid_deterministic():
    a = stable_uuid("rpl", "v1", "RPL-CS-PRO-004:7.2")
    b = stable_uuid("rpl", "v1", "RPL-CS-PRO-004:7.2")
    assert a == b


def test_stable_uuid_different_inputs():
    a = stable_uuid("rpl", "v1", "RPL-CS-PRO-004:7.2")
    b = stable_uuid("rpl", "v1", "RPL-CS-PRO-004:7.3")
    assert a != b


def test_stable_uuid_is_uuidv5():
    result = stable_uuid("rpl", "v1", "clause-id")
    assert result.version == 5


def test_stable_uuid_uses_fixed_namespace():
    expected = uuid.uuid5(UUID_NAMESPACE, "rpl|v1|RPL-CS-PRO-004:7.2")
    actual = stable_uuid("rpl", "v1", "RPL-CS-PRO-004:7.2")
    assert actual == expected
