import importlib.util
from pathlib import Path

import pytest

# score_run is synthetic-corpus tooling (it shells out to the eval harness), so it
# lives under backend/synthetic/. These tests exercise its metric parsing directly,
# so they need the module to be importable and must skip cleanly if that directory
# is ever absent.
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
