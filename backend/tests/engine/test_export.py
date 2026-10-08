import importlib.util
from pathlib import Path

import pytest

from app.engine.export import ExportError, assemble_export, build_export, section_level

_spec = importlib.util.spec_from_file_location(
    "score_run", Path(__file__).resolve().parents[2] / "scripts" / "score_run.py")
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
