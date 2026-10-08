from datetime import datetime, timedelta, timezone

import app.api.engine.routes  # noqa: F401  (load aggregate router first; avoids circular import)
from app.api.engine import routes_ui_runs as r

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


def run(i, kind, status, mins=0, rid=None):
    return {"run_id": rid or f"r{i}", "kind": kind, "status": status, "started_at": T0 + timedelta(minutes=mins),
            "finished_at": None, "scenario_title": None}


def test_title():
    assert r._title(run(1, "kb", "done")) == "Real wave · S1→S2"
    assert r._title(run(1, "baseline", "done")) == "Baseline · S1 vs S1"
    assert r._title(run(1, "whatif", "done")) == "What-if scenario"
    assert r._title({**run(1, "whatif", "done"), "scenario_title": "X"}) == "X"


def test_collapse():
    rows = [  # started_at DESC
        run(1, "kb", "running", 100), run(2, "kb", "done", 90), run(3, "kb", "done", 80),
        run(4, "kb", "failed", 70), run(5, "baseline", "done", 60), run(6, "baseline", "done", 50),
        run(7, "whatif", "done", 40), run(8, "whatif", "done", 30), run(9, "whatif", "running", 20),
    ]
    out = [x["run_id"] for x in r._collapse(rows, {"r7"})]
    assert out == ["r1", "r2", "r5", "r7", "r9"]


def test_collapse_no_done_kb_keeps_failed():
    assert [x["run_id"] for x in r._collapse([run(1, "kb", "failed", 5)], set())] == ["r1"]


def test_target_parse():
    t = [{"target": "Recall ≥ 0.83"}, {"target": "Precision ≥ 0.80"},
         {"target": "FP rate on negative set = 0"}, {"target": "Routing accuracy ≥ 0.9"}]
    assert r._target(t, "recall", 1) == 0.83
    assert r._target(t, "fp", 1) == 0.0
    assert r._target(t, "routing", 1) == 0.9
    assert r._target(None, "precision", 0.8) == 0.8
