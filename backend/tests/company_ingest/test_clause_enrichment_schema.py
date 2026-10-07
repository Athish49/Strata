"""Tests for task 5.1.1: schemas, prompt builders, and split_if_long."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.company_ingest.constants import ClauseRole, DocClass
from app.company_ingest.llm.schemas import (
    CitationLink,
    ClauseEnrichment,
    DocClassification,
    SemanticParam,
)
from app.company_ingest.llm.clause_enrichment import (
    build_clause_user_message,
    build_doc_class_user_message,
    should_enrich,
    split_if_long,
)
from app.company_ingest.parse.models import ClauseUnit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_unit(
    text_raw: str = "The company shall comply with all applicable regulations.",
    role: str | None = None,
    clause_id: str = "DOC001:clause-1",
    local_id: str = "clause-1",
    heading_path: list[str] | None = None,
) -> ClauseUnit:
    import hashlib

    return ClauseUnit(
        version_id="ver-001",
        doc_id="DOC001",
        clause_id=clause_id,
        local_id=local_id,
        parent_clause_id=None,
        unit_kind="section",
        heading_path=heading_path or ["Purpose", "Scope"],
        section_kind="procedure",
        ordinal=1,
        char_start=0,
        char_end=len(text_raw),
        line_start=1,
        text_raw=text_raw,
        text_norm=text_raw.lower(),
        text_sha256=hashlib.sha256(text_raw.encode()).hexdigest(),
        role=role,
    )


# ---------------------------------------------------------------------------
# 1. ClauseEnrichment schema round-trips through JSON
# ---------------------------------------------------------------------------

def test_clause_enrichment_json_roundtrip():
    enrichment = ClauseEnrichment(
        clause_role=ClauseRole.INTERNAL_PROCEDURE,
        normalized_statement="The company maintains internal procedures.",
        topic_terms=["compliance", "procedures"],
        parameters=[
            SemanticParam(kind="party", name="company", value_text="the company")
        ],
        citation_links=[CitationLink(parameter_index=0, citation_raw="§5.1")],
    )
    serialized = enrichment.model_dump_json()
    deserialized = ClauseEnrichment.model_validate_json(serialized)
    assert deserialized.clause_role == ClauseRole.INTERNAL_PROCEDURE
    assert deserialized.normalized_statement == enrichment.normalized_statement
    assert len(deserialized.parameters) == 1
    assert deserialized.parameters[0].kind == "party"
    assert len(deserialized.citation_links) == 1


# ---------------------------------------------------------------------------
# 2. topic_terms validator caps at 6 terms (input 8, output 6)
# ---------------------------------------------------------------------------

def test_topic_terms_capped_at_six():
    enrichment = ClauseEnrichment(
        topic_terms=["a", "b", "c", "d", "e", "f", "g", "h"]
    )
    assert len(enrichment.topic_terms) == 6
    assert enrichment.topic_terms == ["a", "b", "c", "d", "e", "f"]


# ---------------------------------------------------------------------------
# 3. SemanticParam rejects invalid kind values
# ---------------------------------------------------------------------------

def test_semantic_param_rejects_invalid_kind():
    with pytest.raises(ValidationError):
        SemanticParam(kind="invalid_kind", name="test", value_text="some text")


# ---------------------------------------------------------------------------
# 4. ClauseEnrichment with clause_role=None is valid
# ---------------------------------------------------------------------------

def test_clause_enrichment_null_role():
    enrichment = ClauseEnrichment(clause_role=None)
    assert enrichment.clause_role is None


# ---------------------------------------------------------------------------
# 5. DocClassification accepts all DocClass values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("doc_class", list(DocClass))
def test_doc_classification_accepts_all_doc_classes(doc_class):
    dc = DocClassification(doc_class=doc_class, reasoning="test")
    assert dc.doc_class == doc_class


# ---------------------------------------------------------------------------
# 6. should_enrich: returns False for unit with role="boilerplate"
# ---------------------------------------------------------------------------

def test_should_enrich_boilerplate_false():
    unit = _make_unit(role="boilerplate")
    assert should_enrich(unit) is False


# ---------------------------------------------------------------------------
# 7. should_enrich: returns True for unit with role=None
# ---------------------------------------------------------------------------

def test_should_enrich_no_role_true():
    unit = _make_unit(role=None)
    assert should_enrich(unit) is True


# ---------------------------------------------------------------------------
# 8. should_enrich: returns False for empty text_raw
# ---------------------------------------------------------------------------

def test_should_enrich_empty_text_false():
    unit = _make_unit(text_raw="   ")
    assert should_enrich(unit) is False


# ---------------------------------------------------------------------------
# 9. build_clause_user_message: includes clause_id in output
# ---------------------------------------------------------------------------

def test_build_clause_user_message_includes_clause_id():
    unit = _make_unit()
    msg = build_clause_user_message(unit, parent_text=None, citations_found=[], params_found=[])
    assert "DOC001:clause-1" in msg


# ---------------------------------------------------------------------------
# 10. build_clause_user_message: includes heading_path in output
# ---------------------------------------------------------------------------

def test_build_clause_user_message_includes_heading_path():
    unit = _make_unit(heading_path=["Purpose", "Scope"])
    msg = build_clause_user_message(unit, parent_text=None, citations_found=[], params_found=[])
    assert "Purpose" in msg
    assert "Scope" in msg


# ---------------------------------------------------------------------------
# 11. build_clause_user_message: includes parent_text (truncated to 400 chars)
# ---------------------------------------------------------------------------

def test_build_clause_user_message_includes_parent_text():
    long_parent = "Parent content " * 100  # > 400 chars
    unit = _make_unit()
    msg = build_clause_user_message(unit, parent_text=long_parent, citations_found=[], params_found=[])
    # Should include the first 400 chars of parent text
    assert "Parent content" in msg
    # The full parent text should not appear (truncated)
    assert long_parent not in msg
    assert long_parent[:400] in msg


# ---------------------------------------------------------------------------
# 12. build_doc_class_user_message: includes body_preview and headings
# ---------------------------------------------------------------------------

def test_build_doc_class_user_message_includes_preview_and_headings():
    msg = build_doc_class_user_message(
        doc_id="DOC001",
        doc_title="Compliance Policy",
        body_preview="This document describes compliance requirements.",
        heading_outline=["Purpose", "Scope", "Procedures"],
    )
    assert "DOC001" in msg
    assert "Compliance Policy" in msg
    assert "This document describes compliance requirements." in msg
    assert "Purpose" in msg
    assert "Scope" in msg
    assert "Procedures" in msg


# ---------------------------------------------------------------------------
# 13. split_if_long: short text → returns [original_unit] unchanged
# ---------------------------------------------------------------------------

def test_split_if_long_short_text_unchanged():
    unit = _make_unit(text_raw="Short clause text.")
    result = split_if_long(unit, max_tokens=1500)
    assert result == [unit]


# ---------------------------------------------------------------------------
# 14. split_if_long: long bulleted list → splits into multiple units with "#1", "#2" suffixes
# ---------------------------------------------------------------------------

def test_split_if_long_bulleted_list_splits():
    # Create a text that exceeds 1500 tokens (6000 chars) with multiple bullet items
    item_text = "word " * 200  # ~1000 chars per item
    text = (
        f"- First item: {item_text}\n"
        f"- Second item: {item_text}\n"
        f"- Third item: {item_text}\n"
        f"- Fourth item: {item_text}\n"
        f"- Fifth item: {item_text}\n"
        f"- Sixth item: {item_text}\n"
        f"- Seventh item: {item_text}\n"
    )
    unit = _make_unit(text_raw=text, clause_id="DOC001:clause-2", local_id="clause-2")
    result = split_if_long(unit, max_tokens=1500)
    assert len(result) >= 2
    assert result[0].clause_id == "DOC001:clause-2#1"
    assert result[1].clause_id == "DOC001:clause-2#2"
    assert result[0].local_id == "clause-2#1"
    assert result[1].local_id == "clause-2#2"


# ---------------------------------------------------------------------------
# 15. split_if_long: child units have parent_clause_id = original clause_id
# ---------------------------------------------------------------------------

def test_split_if_long_child_parent_clause_id():
    item_text = "word " * 200
    text = (
        f"- First item: {item_text}\n"
        f"- Second item: {item_text}\n"
        f"- Third item: {item_text}\n"
        f"- Fourth item: {item_text}\n"
        f"- Fifth item: {item_text}\n"
        f"- Sixth item: {item_text}\n"
        f"- Seventh item: {item_text}\n"
    )
    original_clause_id = "DOC001:clause-3"
    unit = _make_unit(text_raw=text, clause_id=original_clause_id, local_id="clause-3")
    result = split_if_long(unit, max_tokens=1500)
    assert len(result) >= 2
    for child in result:
        assert child.parent_clause_id == original_clause_id


# ---------------------------------------------------------------------------
# 16. Snapshot test: build_clause_user_message produces a stable string
# ---------------------------------------------------------------------------

def test_build_clause_user_message_snapshot():
    unit = _make_unit(
        text_raw="The company shall maintain records for at least 5 years.",
        clause_id="DOC001:clause-snap",
        local_id="clause-snap",
        heading_path=["Records", "Retention"],
    )

    class _FakeCitation:
        citation_raw = "§5.2"

    class _FakeParam:
        kind = "condition"
        value_text = "at least 5 years"

    msg = build_clause_user_message(
        unit,
        parent_text="Parent section text here.",
        citations_found=[_FakeCitation()],
        params_found=[_FakeParam()],
    )

    # Key structural elements that must be present in a stable snapshot.
    assert "CLAUSE_ID: DOC001:clause-snap" in msg
    assert "HEADING_PATH: Records > Retention" in msg
    assert "PARENT_CLAUSE (first 400 chars):" in msg
    assert "Parent section text here." in msg
    assert "CLAUSE_TEXT:" in msg
    assert "The company shall maintain records for at least 5 years." in msg
    assert "CITATIONS_FOUND" in msg
    assert "§5.2" in msg
    assert "PARAMETERS_FOUND" in msg
    assert "at least 5 years" in msg
