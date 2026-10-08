"""Engine API routes against a scripted fake session (no DB)."""
import uuid
from datetime import datetime

import httpx
import pytest

from app.db import get_db
from app.main import app

RUN = str(uuid.uuid4())
CHANGE = uuid.uuid4()
FID = uuid.uuid4()
FID2 = uuid.uuid4()
CPK = uuid.uuid4()
CAND = uuid.uuid4()

S1 = "The licensee shall file the report within 30 days of the event."
S2 = "The licensee shall file the report within 10 days of the event."
CLAUSE = "Our team will file the report within 30 days of the event, per policy."


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    """Matches the first (substring, rows) rule found in the SQL text."""

    def __init__(self, rules):
        self.rules = rules
        self.sql = []

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.sql.append((sql, params))
        for key, rows in self.rules:
            if key in sql:
                return _Res(rows(params) if callable(rows) else rows)
        return _Res([])


def run_row(status="done", kind="kb", rid=RUN):
    return {"run_id": uuid.UUID(rid), "kind": kind, "status": status, "company_id": "co",
            "started_at": datetime(2026, 1, 1), "finished_at": datetime(2026, 1, 2),
            "stats": {"raw_changed": 5}, "error": None, "scenario_title": None}


def client_for(rules):
    sess = FakeSession(rules)

    async def _dep():
        yield sess

    app.dependency_overrides[get_db] = _dep
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    return c, sess


@pytest.fixture(autouse=True)
def _clear():
    yield
    app.dependency_overrides.clear()


async def test_unknown_run_404_and_bad_uuid_404():
    c, _ = client_for([("FROM engine.runs r", [])])
    async with c:
        assert (await c.get(f"/engine/runs/{RUN}")).status_code == 404
        assert (await c.get("/engine/runs/not-a-uuid")).status_code == 404
        assert (await c.get("/engine/findings/not-a-uuid")).status_code == 404


async def test_running_run_409_on_results_but_status_ok():
    c, _ = client_for([("FROM engine.runs r", [run_row("running")])])
    async with c:
        assert (await c.get(f"/engine/runs/{RUN}/documents")).status_code == 409
        assert (await c.get(f"/engine/runs/{RUN}/ledger")).status_code == 409
        assert (await c.get(f"/engine/runs/{RUN}/scorecard")).status_code == 409
        r = await c.get(f"/engine/runs/{RUN}")
        assert r.status_code == 200 and r.json()["run"]["status"] == "running"


async def test_default_run_is_latest_done_kb():
    c, sess = client_for([("FROM engine.runs r", [run_row()]), ("FROM engine.doc_rollups", [])])
    async with c:
        r = await c.get("/engine/runs/" + RUN + "/documents")
        assert r.status_code == 200
    # helper: omitted run -> done kb query
    from app.api.engine.routes import _get_run
    s = FakeSession([("FROM engine.runs r", [run_row()])])
    run = await _get_run(s, None)
    assert str(run["run_id"]) == RUN
    assert "r.kind = 'kb' AND r.status = 'done'" in s.sql[0][0]
    with pytest.raises(Exception) as e:
        await _get_run(FakeSession([]), None)
    assert e.value.status_code == 404


async def test_start_run_returns_run_id_and_schedules(monkeypatch):
    import sys, types
    calls = []
    mod = types.ModuleType("app.engine.run")

    async def run_engine(kind, run_id):
        calls.append((kind, run_id))
    mod.run_engine = run_engine
    monkeypatch.setitem(sys.modules, "app.engine.run", mod)
    c, _ = client_for([])
    async with c:
        r = await c.post("/engine/runs", json={"kind": "baseline"})
        assert r.status_code == 200
        rid = r.json()["run_id"]
        assert uuid.UUID(rid)
        assert (await c.post("/engine/runs", json={"kind": "whatif"})).status_code == 422
    assert calls == [("baseline", rid)]


def _finding(**kw):
    base = {"finding_id": FID, "run_id": uuid.UUID(RUN), "change_id": CHANGE, "candidate_id": CAND,
            "clause_pk": CPK, "clause_id": "C1", "doc_id": "D1", "citation": "X 1-2",
            "finding_type": "parameter_change", "severity": "high", "verdict": "action_required",
            "needs_review": False, "required_change": {"from_text": "30 days", "to_text": "10 days"},
            "quotes": {"s1": "within 30 days of the event", "s2": "within 10 days of the event",
                       "clause": "within 30 days of the event"},
            "quotes_verified": True, "rationale": "Deadline shortened.", "confidence": 0.9,
            "decided_by": "llm", "match_path": "direct_section", "propagated_from": FID2,
            "route_owner": "P1", "route_reviewer": "P2", "route_approver": None}
    base.update(kw)
    return base


CHANGE_ROW = {"change_id": CHANGE, "run_id": uuid.UUID(RUN), "citation": "X 1-2", "heading": "H",
              "change_class": "substantive", "summary": "s", "direction": "tightened",
              "value_changes": None, "published_date": None, "date_basis": None, "din": None,
              "amendment_source": None, "origin": "kb",
              "diff_segments": [{"op": "equal", "text": "a"}], "s1_text_norm": S1, "s2_text_norm": S2}


async def test_evidence_card_assembly_with_spans():
    rules = [
        ("FROM engine.runs r", [run_row()]),
        ("SELECT * FROM engine.findings WHERE finding_id", [_finding()]),
        ("SELECT * FROM engine.change_records", [CHANGE_ROW]),
        ("FROM company.clauses c", [{"clause_id": "C1", "heading_path": ["A", "B"], "text_raw": CLAUSE,
                                    "doc_title": "Policy"}]),
        ("SELECT path_detail", [{"path_detail": [{"path": "direct_section", "via_clause_id": None,
                                                  "link_type": None, "value": None}]}]),
        ("FROM company.people", [{"person_id": "P1", "name": "Ann", "title": "Owner"},
                                 {"person_id": "P2", "name": "Bo", "title": "Rev"}]),
        ("FROM engine.finding_reviews", [{"action": "accept", "note": None, "person_id": "P2",
                                          "created_at": None}]),
        ("finding_id <> :f", [{"finding_id": uuid.uuid4(), "doc_id": "D2", "clause_id": "C9",
                               "verdict": "review"}]),
        ("WHERE finding_id = :p", [{"finding_id": FID2, "clause_id": "C0"}]),
    ]
    c, _ = client_for(rules)
    async with c:
        r = await c.get(f"/engine/findings/{FID}")
    assert r.status_code == 200, r.text
    j = r.json()
    s1 = j["change"]["s1_quote_span"]
    assert S1[s1[0]:s1[1]] == "within 30 days of the event"
    s2 = j["change"]["s2_quote_span"]
    assert S2[s2[0]:s2[1]] == "within 10 days of the event"
    cs = j["clause"]["quote_span"]
    assert CLAUSE[cs[0]:cs[1]] == "within 30 days of the event"
    assert j["finding"]["route"]["owner"]["name"] == "Ann"
    assert j["finding"]["route"]["approver"] is None
    assert j["finding"]["reviews"][0]["action"] == "accept"
    assert j["propagated_from"] == {"finding_id": str(FID2), "clause_id": "C0"}
    assert j["also_affected"][0]["doc_id"] == "D2"
    assert j["path"][0]["path"] == "direct_section"
    assert j["finding"]["confidence"] == 0.9


async def test_evidence_card_unverified_quote_has_null_span():
    rules = [
        ("FROM engine.runs r", [run_row()]),
        ("SELECT * FROM engine.findings WHERE finding_id",
         [_finding(propagated_from=None, quotes={"s1": "not in the text anywhere", "s2": None, "clause": ""})]),
        ("SELECT * FROM engine.change_records", [CHANGE_ROW]),
    ]
    c, _ = client_for(rules)
    async with c:
        r = await c.get(f"/engine/findings/{FID}")
    j = r.json()
    assert j["change"]["s1_quote_span"] is None and j["change"]["s2_quote_span"] is None
    assert j["propagated_from"] is None and j["clause"]["quote_span"] is None


async def test_unknown_finding_404():
    c, _ = client_for([])
    async with c:
        assert (await c.get(f"/engine/findings/{FID}")).status_code == 404


async def test_document_grouping_and_cleared():
    def f(verdict, sev, i):
        return {"finding_id": uuid.uuid4(), "clause_id": f"C{i}", "citation": "X 1", "finding_type": "parameter_change",
                "verdict": verdict, "severity": sev, "rationale": "r" * 400, "heading_path": ["H"]}
    rules = [
        ("FROM engine.runs r", [run_row()]),
        ("FROM engine.doc_rollups", [{"run_id": uuid.UUID(RUN), "doc_id": "D1", "status": "flagged",
                                      "counts": {"action_required": 1}, "changes_considered": [], "reason": None}]),
        ("FROM company.company_documents cd", [{"doc_id": "D1", "title": "T", "vertical": "v",
                                                "owner_name": "Ann", "approved_date": None}]),
        ("FROM engine.findings f LEFT JOIN company.clauses",
         [f("action_required", "high", 1), f("info", "low", 2), f("action_required", "low", 3)]),
        ("FROM engine.candidates k", [{"clause_id": "C7", "citation": "X 9", "skip_reason": "noise:cosmetic",
                                       "rationale": None, "change_class": "cosmetic"}]),
    ]
    c, _ = client_for(rules)
    async with c:
        r = await c.get(f"/engine/runs/{RUN}/documents/D1")
    assert r.status_code == 200, r.text
    j = r.json()
    assert [x["clause_id"] for x in j["groups"]["action_required"]] == ["C1", "C3"]
    assert len(j["groups"]["info"]) == 1 and j["groups"]["review"] == []
    assert len(j["groups"]["action_required"][0]["short_rationale"]) <= 220
    assert j["cleared"][0]["change_class"] == "cosmetic"
    assert j["rollup"]["title"] == "T" and j["doc"]["owner_name"] == "Ann"


async def test_document_not_in_run_404():
    c, _ = client_for([("FROM engine.runs r", [run_row()])])
    async with c:
        assert (await c.get(f"/engine/runs/{RUN}/documents/NOPE")).status_code == 404


async def test_ledger_and_filters_passed_through():
    row = {"change_id": CHANGE, "citation": "X", "heading": None, "change_class": "substantive",
           "in_footprint": True, "cited_clause_count": 3, "disposition": "findings_emitted",
           "disposition_reason": None, "published_date": None, "n_findings": 2, "n_cleared": 1}
    c, sess = client_for([("FROM engine.runs r", [run_row()]), ("FROM engine.change_records ch", [row])])
    async with c:
        r = await c.get(f"/engine/runs/{RUN}/ledger?in_footprint=true&change_class=substantive")
    assert r.status_code == 200 and r.json()[0]["n_findings"] == 2
    params = [p for s, p in sess.sql if "engine.change_records ch" in s][0]
    assert params["inf"] is True and params["cc"] == "substantive" and params["disp"] is None


async def test_change_detail_and_scorecard():
    cand = {"candidate_id": CAND, "clause_id": "C1", "doc_id": "D1", "cited_citation": "X", "match_path": "direct_section",
            "path_detail": [], "judged_by": "llm", "skip_reason": None, "affected": True, "rationale": "r",
            "finding_id": FID, "verdict": "action_required"}
    rules = [("FROM engine.runs r", [run_row()]),
             ("SELECT * FROM engine.change_records", [CHANGE_ROW]),
             ("FROM engine.candidates k", [cand]),
             ("FROM engine.score_reports s", [{"metrics": {"recall": 0.5}}]),
             ("SELECT metrics FROM engine.score_reports", [{"metrics": {"recall": 1.0}}])]
    c, _ = client_for(rules)
    async with c:
        d = await c.get(f"/engine/changes/{CHANGE}")
        s = await c.get(f"/engine/runs/{RUN}/scorecard")
    assert d.status_code == 200 and d.json()["candidates"][0]["finding_id"] == str(FID)
    assert s.json()["metrics"] == {"recall": 1.0} and s.json()["baseline"] == {"recall": 0.5}
