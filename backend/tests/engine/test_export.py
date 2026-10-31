import importlib.util
from pathlib import Path

import pytest

from app.engine.export import ExportError, assemble_export, build_export, section_level

# score_run is synthetic-corpus tooling (it shells out to the eval harness), so it
# lives under backend/synthetic/. The suite must stay green when that directory is
# deleted (implementation_plan.md task 9.4), hence the module-level skip.
_SCORE_RUN = Path(__file__).resolve().parents[2] / "synthetic" / "score_run.py"
if not _SCORE_RUN.exists():
    pytest.skip("backend/synthetic/ is absent; score_run tests need it", allow_module_level=True)

_spec = importlib.util.spec_from_file_location("score_run", _SCORE_RUN)
score_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score_run)

S2_STDOUT = """======================================================================
STRATA CORPUS SCORING REPORT
Snapshot:       S2
======================================================================

Metric                                        Value
----------------------------------------------------
Expected non-informational findings              20
  — medium                                       12
System non-informational findings                18
Matched                                          16
Recall (overall)                              0.800
Recall (medium severity)                      0.750
Recall (low severity)                         0.875
Precision                                     0.889
FP rate on negative set                       0.000
Routing accuracy (matched)                    0.938

--- Per-Document Status ---
  ✓ DOC-A                          expected=flagged  system=flagged  exp=3 sys=3 matched=2
  ✗ DOC-B                          expected=cleared  system=flagged  exp=0 sys=1 matched=0

  [PASS] Recall >= 0.83
  [FAIL] Precision >= 0.80

Overall: FAIL
"""


def test_section_level():
    assert section_level("170 IAC 4-1-16(a)(2)") == "170 IAC 4-1-16"
    assert section_level("18 CFR 35.28 (b)") == "18 CFR 35.28"
    assert section_level("170 IAC 4-1-16") == "170 IAC 4-1-16"
    assert section_level(None) == ""


def test_parse_metrics_s2():
    m = score_run.parse_metrics(S2_STDOUT)
    assert m["recall"] == 0.8 and m["precision"] == 0.889
    assert m["fp_rate_must_not_flag"] == 0.0 and m["routing_accuracy"] == 0.938
    assert m["matched"] == 16 and m["expected_non_informational"] == 20
    assert m["recall_medium"] == 0.75
    assert m["overall"] == "FAIL"
    assert [d["doc_id"] for d in m["per_doc"]] == ["DOC-A", "DOC-B"]
    assert m["per_doc"][1]["system"] == "flagged" and m["per_doc"][0]["matched"] == 2
    assert {"target": "Precision >= 0.80", "result": "FAIL"} in m["targets"]


def test_parse_metrics_baseline_and_garbage():
    m = score_run.parse_metrics("=== BASELINE CHECK (S1) ===\nPASS — zero non-informational findings on S1 corpus.\n")
    assert m["baseline_check"] == "PASS"
    assert score_run.parse_metrics("nothing useful") == {}


def test_assemble_export_all_docs_and_status():
    docs = [
        {"doc_id": "d2", "owner_id": "P1", "reviewer_id": "P2", "approver_id": ""},
        {"doc_id": "d1", "owner_id": "P1", "reviewer_id": "P2", "approver_id": "P3"},
        {"doc_id": "d3", "owner_id": "P1", "reviewer_id": "P2", "approver_id": None},
    ]
    findings = [
        {"clause_id": "c1", "doc_id": "d1", "citation": "1 X 2-3(a)", "finding_type": "parameter_change",
         "severity": "high", "route_owner": "P9", "route_reviewer": None, "route_approver": None},
        {"clause_id": "c2", "doc_id": "d2", "citation": "1 X 2-4", "finding_type": "informational",
         "severity": "low", "route_owner": None, "route_reviewer": None, "route_approver": None},
    ]
    out = assemble_export(docs, findings, {"d3": "cleared"})
    assert [d["doc_id"] for d in out["documents"]] == ["d1", "d2", "d3"]
    d1, d2, d3 = out["documents"]
    assert d1["status"] == "flagged" and d1["findings"][0]["citation"] == "1 X 2-3"
    assert d1["findings"][0]["route_to"] == {"owner": "P9", "reviewer": "P2", "approver": "P3"}
    assert d2["status"] == "cleared" and len(d2["findings"]) == 1  # informational only
    assert d2["findings"][0]["route_to"]["approver"] is None
    assert d3["findings"] == []


def test_assemble_export_rekeys_doc_id_and_clause_id_to_doc_number():
    """task 9.2 step 5/6 bug: scoring matches by the pre-v2 convention where doc_id
    *was* the RPL id. v2 made doc_id system-generated and moved the RPL id to
    doc_number; the export must emit doc_number (and rewrite each clause_id's
    prefix) or every scoring comparison silently fails to join, even for a
    substantively correct finding (found on the real post-cutover kb run)."""
    docs = [
        {"doc_id": "DOC-000001", "doc_number": "RPL-CMP-REG-001",
         "owner_id": "P1", "reviewer_id": "P2", "approver_id": "P3"},
        {"doc_id": "DOC-000002", "doc_number": "RPL-CMP-REG-001#register",
         "owner_id": "P1", "reviewer_id": "P2", "approver_id": "P3"},
        {"doc_id": "DOC-000009", "doc_number": None,  # no doc_number: falls back to doc_id
         "owner_id": "P1", "reviewer_id": "P2", "approver_id": "P3"},
    ]
    findings = [
        {"clause_id": "DOC-000001:B.1", "doc_id": "DOC-000001", "citation": "170 IAC 1-6-3",
         "finding_type": "stale_citation", "severity": "medium",
         "route_owner": None, "route_reviewer": None, "route_approver": None},
        {"clause_id": "DOC-000002:OBL-2024-0018", "doc_id": "DOC-000002", "citation": "170 IAC 1-6-3",
         "finding_type": "required_content_change", "severity": "high",
         "route_owner": None, "route_reviewer": None, "route_approver": None},
        {"clause_id": "DOC-000009:3.1", "doc_id": "DOC-000009", "citation": "170 IAC 1-6-8",
         "finding_type": "informational", "severity": "low",
         "route_owner": None, "route_reviewer": None, "route_approver": None},
    ]
    out = assemble_export(docs, findings, {})
    by_doc = {d["doc_id"]: d for d in out["documents"]}
    assert set(by_doc) == {"RPL-CMP-REG-001", "RPL-CMP-REG-001#register", "DOC-000009"}
    assert by_doc["RPL-CMP-REG-001"]["findings"][0]["clause_id"] == "RPL-CMP-REG-001:B.1"
    assert by_doc["RPL-CMP-REG-001#register"]["findings"][0]["clause_id"] == \
        "RPL-CMP-REG-001#register:OBL-2024-0018"
    # No doc_number on this one: both the doc-level id and the clause_id prefix are
    # left as the raw system doc_id, not silently dropped or blanked.
    assert by_doc["DOC-000009"]["findings"][0]["clause_id"] == "DOC-000009:3.1"


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _FakeSession:
    def __init__(self, kind):
        self.kind = kind

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        if "FROM engine.runs" in sql:
            return _Result([{"kind": self.kind, "company_id": "co"}])
        if "company_documents" in sql:
            return _Result([{"doc_id": "d1", "owner_id": "P1", "reviewer_id": "P2", "approver_id": None}])
        return _Result([])


@pytest.mark.asyncio
async def test_build_export_with_fake_session():
    out = await build_export(_FakeSession("baseline"), "r1")
    assert out == {"documents": [{"doc_id": "d1", "status": "cleared", "findings": []}]}


@pytest.mark.asyncio
async def test_build_export_rejects_whatif():
    with pytest.raises(ExportError):
        await build_export(_FakeSession("whatif"), "r1")
