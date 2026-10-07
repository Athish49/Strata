"""Tests for task 4.1.3: Reference extraction.

Run (unit tests only — no DB):
    cd backend && .venv/bin/python -m pytest tests/company_ingest/test_references.py -v \
        -k "not qdrant and not corpus and not neon"
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.company_ingest.constants import LinkType
from app.company_ingest.enrich.ref_entry import RefEntry
from app.company_ingest.enrich.references import enrich_references
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx() -> RunContext:
    return RunContext(run_id=uuid.uuid4(), company_id="test_co")


def _make_unit(
    text_raw: str,
    doc_id: str = "RPL-CS-PRO-001",
    clause_id: str | None = None,
    row_cells: dict[str, Any] | None = None,
) -> ClauseUnit:
    cid = clause_id or f"{doc_id}:1.1"
    return ClauseUnit(
        version_id=str(uuid.uuid4()),
        doc_id=doc_id,
        clause_id=cid,
        local_id="1.1",
        parent_clause_id=None,
        unit_kind="section",
        heading_path=[],
        section_kind="procedure",
        ordinal=1,
        char_start=0,
        char_end=len(text_raw),
        line_start=1,
        text_raw=text_raw,
        text_norm=text_raw,
        text_sha256="",
        row_cells=row_cells,
    )


REGISTERED = ["RPL-CS-PRO-004", "RPL-DCC-PRO-003", "RPL-OPS-PRO-007"]


# ---------------------------------------------------------------------------
# Test 1: Document ID in text → found as references_doc with correct target_hint
# ---------------------------------------------------------------------------

class TestDocIdReference:
    def test_doc_id_found(self):
        unit = _make_unit("See RPL-CS-PRO-004 for details.")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_DOC]
        assert len(refs) == 1
        assert refs[0].target_hint == "RPL-CS-PRO-004"
        assert refs[0].raw == "RPL-CS-PRO-004"

    def test_doc_id_span_correct(self):
        text = "See RPL-CS-PRO-004 for details."
        unit = _make_unit(text)
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_DOC]
        r = refs[0]
        assert text[r.span_start:r.span_end] == "RPL-CS-PRO-004"


# ---------------------------------------------------------------------------
# Test 2: Doc ID not in registered list → not extracted
# ---------------------------------------------------------------------------

class TestDocIdNotRegistered:
    def test_unregistered_doc_id_not_extracted(self):
        unit = _make_unit("Refer to RPL-HR-PRO-999 for HR guidance.")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_DOC]
        assert len(refs) == 0


# ---------------------------------------------------------------------------
# Test 3: Explicit DOC:CLAUSE form → references_clause with correct target_hint
# ---------------------------------------------------------------------------

class TestExplicitClauseRef:
    def test_explicit_clause_found(self):
        unit = _make_unit("See RPL-DCC-PRO-003:4A for the definition.")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_CLAUSE]
        assert len(refs) >= 1
        hints = [r.target_hint for r in refs]
        assert "RPL-DCC-PRO-003:4A" in hints

    def test_explicit_clause_target_hint_format(self):
        unit = _make_unit("Per RPL-OPS-PRO-007:2.1.3 the operator must...")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_CLAUSE]
        assert any(r.target_hint == "RPL-OPS-PRO-007:2.1.3" for r in refs)


# ---------------------------------------------------------------------------
# Test 4: §7.2 same-doc reference → references_clause with {unit.doc_id}:7.2
# ---------------------------------------------------------------------------

class TestSectionSymbolRef:
    def test_section_symbol_found(self):
        unit = _make_unit("This is governed by §7.2 of this document.", doc_id="RPL-CS-PRO-001")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_CLAUSE]
        assert any(r.target_hint == "RPL-CS-PRO-001:7.2" for r in refs)

    def test_section_symbol_uses_unit_doc_id(self):
        unit = _make_unit("See §3 for scope.", doc_id="RPL-DCC-PRO-003")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_CLAUSE]
        assert any(r.target_hint == "RPL-DCC-PRO-003:3" for r in refs)


# ---------------------------------------------------------------------------
# Test 5: "Sheet No. 4" → references_tariff, target_hint="sheet:4"
# ---------------------------------------------------------------------------

class TestTariffSheetRef:
    def test_sheet_no_found(self):
        unit = _make_unit("See Sheet No. 4 for the rate schedule.")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_TARIFF]
        assert any(r.target_hint == "sheet:4" for r in refs)


# ---------------------------------------------------------------------------
# Test 6: "Sheets 4-6" → references_tariff (range as written)
# ---------------------------------------------------------------------------

class TestTariffSheetRange:
    def test_sheet_range_found(self):
        unit = _make_unit("Refer to Sheets 4-6 for details.")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_TARIFF]
        assert len(refs) >= 1
        assert refs[0].target_hint == "sheet:4-6"


# ---------------------------------------------------------------------------
# Test 7: "Rule 16" → references_tariff, target_hint="rule:16"
# ---------------------------------------------------------------------------

class TestTariffRuleRef:
    def test_rule_found(self):
        unit = _make_unit("This is subject to Rule 16 of the tariff.")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_TARIFF]
        assert any(r.target_hint == "rule:16" for r in refs)


# ---------------------------------------------------------------------------
# Test 8: "RPL-DCC-F-042" → references_form
# ---------------------------------------------------------------------------

class TestFormRef:
    def test_form_found(self):
        unit = _make_unit("Complete RPL-DCC-F-042 and submit.")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_FORM]
        assert len(refs) == 1
        assert refs[0].target_hint == "RPL-DCC-F-042"


# ---------------------------------------------------------------------------
# Test 9: "RRS-CS-001" → references_record_series
# ---------------------------------------------------------------------------

class TestRecordSeriesRef:
    def test_record_series_found(self):
        unit = _make_unit("Records are filed under RRS-CS-001.")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_RECORD_SERIES]
        assert len(refs) == 1
        assert refs[0].target_hint == "RRS-CS-001"


# ---------------------------------------------------------------------------
# Test 10: "OBL-2024-0042" → references_obligation
# ---------------------------------------------------------------------------

class TestObligationRef:
    def test_obligation_long_form_found(self):
        unit = _make_unit("This obligation is tracked as OBL-2024-0042.")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_OBLIGATION]
        assert len(refs) == 1
        assert refs[0].target_hint == "OBL-2024-0042"

    def test_obligation_short_form_found(self):
        unit = _make_unit("See OBL-2023 for details.")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_OBLIGATION]
        assert len(refs) == 1
        assert refs[0].target_hint == "OBL-2023"


# ---------------------------------------------------------------------------
# Test 11: P2 register_row with reference_list column (semicolon-separated)
# ---------------------------------------------------------------------------

class TestP2RegisterRowRefList:
    def test_reference_list_column_extracted(self):
        row_cells = {
            "reference_list": "RPL-CS-PRO-004; RPL-DCC-PRO-003; RRS-CS-001"
        }
        unit = _make_unit("", row_cells=row_cells)
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        assert len(unit.refs) == 3

    def test_reference_list_doc_ids(self):
        row_cells = {
            "reference_list": "RPL-CS-PRO-004; RPL-DCC-PRO-003"
        }
        unit = _make_unit("", row_cells=row_cells)
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        doc_refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_DOC]
        assert len(doc_refs) == 2
        hints = {r.target_hint for r in doc_refs}
        assert "RPL-CS-PRO-004" in hints
        assert "RPL-DCC-PRO-003" in hints

    def test_reference_list_mixed_types(self):
        row_cells = {
            "reference_list": "RPL-CS-PRO-004; RRS-CS-001; OBL-2024-0042"
        }
        unit = _make_unit("", row_cells=row_cells)
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        ref_types = {r.ref_type for r in unit.refs}
        assert LinkType.REFERENCES_DOC in ref_types
        assert LinkType.REFERENCES_RECORD_SERIES in ref_types
        assert LinkType.REFERENCES_OBLIGATION in ref_types


# ---------------------------------------------------------------------------
# Test 12: Deduplication — same (ref_type, target_hint) only once
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_same_doc_ref_deduplicated(self):
        unit = _make_unit(
            "See RPL-CS-PRO-004 and also RPL-CS-PRO-004 again."
        )
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        doc_refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_DOC]
        assert len(doc_refs) == 1

    def test_same_clause_ref_deduplicated(self):
        unit = _make_unit("Both §3.1 and §3.1 apply here.", doc_id="RPL-CS-PRO-001")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        clause_refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_CLAUSE]
        assert len(clause_refs) == 1


# ---------------------------------------------------------------------------
# Test 13: ctx.count("references_found") incremented
# ---------------------------------------------------------------------------

class TestCtxCount:
    def test_count_incremented(self):
        unit = _make_unit("See RPL-CS-PRO-004 and §7.2 and RRS-CS-001.")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        assert ctx.stats.get("references_found", 0) == len(unit.refs)

    def test_count_zero_when_no_refs(self):
        unit = _make_unit("No references here.")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        assert ctx.stats.get("references_found", 0) == 0


# ---------------------------------------------------------------------------
# Test 14: Mixed text — multiple different ref types in one clause
# ---------------------------------------------------------------------------

class TestMixedText:
    def test_multiple_ref_types_found(self):
        text = (
            "Per RPL-CS-PRO-004 and §5.1, complete RPL-DCC-F-042, "
            "file under RRS-CS-001, and track as OBL-2024-0042. "
            "Also see Sheet No. 3 and Rule 7."
        )
        unit = _make_unit(text, doc_id="RPL-CS-PRO-001")
        ctx = _make_ctx()
        enrich_references([unit], REGISTERED, ctx)
        ref_types = {r.ref_type for r in unit.refs}
        assert LinkType.REFERENCES_DOC in ref_types
        assert LinkType.REFERENCES_CLAUSE in ref_types
        assert LinkType.REFERENCES_FORM in ref_types
        assert LinkType.REFERENCES_RECORD_SERIES in ref_types
        assert LinkType.REFERENCES_OBLIGATION in ref_types
        assert LinkType.REFERENCES_TARIFF in ref_types


# ---------------------------------------------------------------------------
# Test 15: No registered_doc_ids → no references_doc found
# ---------------------------------------------------------------------------

class TestNoRegisteredDocIds:
    def test_no_doc_refs_when_empty_list(self):
        unit = _make_unit("See RPL-CS-PRO-004 for details.")
        ctx = _make_ctx()
        enrich_references([unit], [], ctx)
        doc_refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_DOC]
        assert len(doc_refs) == 0

    def test_other_refs_still_found_when_empty_list(self):
        unit = _make_unit("Refer to §3.2 of this document.", doc_id="RPL-CS-PRO-001")
        ctx = _make_ctx()
        enrich_references([unit], [], ctx)
        clause_refs = [r for r in unit.refs if r.ref_type == LinkType.REFERENCES_CLAUSE]
        assert len(clause_refs) == 1
