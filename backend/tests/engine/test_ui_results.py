import asyncio
import uuid

import pytest
from fastapi import HTTPException

import app.api.engine.routes  # noqa: F401  (registers sub-routers; avoids circular import)
from app.api.engine import routes_ui_results as m

RUN = {"run_id": uuid.uuid4(), "company_id": "rpl", "status": "done"}


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_router_paths():
    paths = {r.path for r in m.router.routes}
    for p in ("/ui/runs/{rid}/changes", "/ui/runs/{rid}/changes/{change_id}", "/ui/runs/{rid}/candidates",
              "/ui/runs/{rid}/findings", "/ui/findings/{finding_id}", "/ui/runs/{rid}/rollups",
              "/ui/runs/{rid}/documents/{doc_id}/annotations", "/ui/runs/{rid}/matrix", "/ui/runs/{rid}/radar"):
        assert p in paths


def test_change_json_light_vs_full_and_fallbacks():
    r = {"change_id": uuid.uuid4(), "citation": "170 IAC 4-1-16", "heading": "170 IAC 4-1-16 Reports",
         "source_system": "iac", "rule_key": "170 IAC 4-1", "change_class": "new_section", "published_date": None,
         "date_basis": None, "din": None, "in_footprint": True, "cited_clause_count": 2,
         "obligation_changed": None, "direction": "removed_requirement", "summary": None,
         "value_changes": [{"subject": "Day", "old_value_num": 17, "new_value_text": "26 days", "unit": "days"}],
         "disposition": None, "disposition_reason": None, "agency_id": "iurc", "title_number": None,
         "s1_date": None, "s2_date": None, "s1_text_norm": None, "s2_text_norm": "New text.", "diff_segments": None}
    snaps = {"iac": {"s1": "2024-12-31", "s2": "2025-12-31"}}
    light = m._change_json(r, snaps, False)
    assert light["diff_segments"] == [] and light["s1_text"] == "" and light["s2_text"] == ""
    assert light["heading"] == "Reports" and light["title_number"] == "170"
    assert light["s1_snapshot"] == "2024-12-31" and light["published_date"] is None
    assert light["characterization"]["direction"] == "removed"
    assert light["characterization"]["value_changes"] == [
        {"label": "Day", "old": "17", "new": "26 days", "unit": "days"}]
    full = m._change_json(r, snaps, True)
    assert full["diff_segments"] == [{"op": "insert", "text": "New text."}] and full["s2_text"] == "New text."


def test_quote_spans():
    assert m._quote(None, "abc") == {"text": "", "span": None}
    q = m._quote("must file within 30 days", "The utility Must file within 30 days of notice.")
    assert q["span"] == [12, 12 + len("must file within 30 days")]
    assert m._quote("not present anywhere", "abc")["span"] is None


def test_attr_value():
    assert m._attr_value({"value_bool": True, "value_num": None, "value_text": None}) is True
    from decimal import Decimal
    v = m._attr_value({"value_bool": None, "value_num": Decimal("407491"), "value_text": None})
    assert v == 407491 and isinstance(v, int)
    assert m._attr_value({"value_bool": None, "value_num": None, "value_text": None}) == "not in profile"


def test_running_run_is_409(monkeypatch):
    async def fake(db, rid, require_done=True):
        raise HTTPException(409, "run is still running")
    monkeypatch.setattr(m, "resolve_run", fake)
    with pytest.raises(HTTPException) as e:
        run(m.ui_list_changes("x", db=None))
    assert e.value.status_code == 409


def test_matrix_cells_and_candidates(monkeypatch):
    c1, c2 = uuid.uuid4(), uuid.uuid4()

    async def fake_resolve(db, rid, require_done=True):
        return RUN

    async def fake_light(db, rid, where=""):
        return [{"change_id": str(c1)}]

    async def fake_all(db, sql, **p):
        return [{"doc_id": "D1", "change_id": c1, "verdict": "review"},
                {"doc_id": "D1", "change_id": c1, "verdict": "action_required"},
                {"doc_id": "D1", "change_id": c1, "verdict": None},
                {"doc_id": "D2", "change_id": c1, "verdict": None},
                {"doc_id": "D1", "change_id": c2, "verdict": "info"}]
    monkeypatch.setattr(m, "resolve_run", fake_resolve)
    monkeypatch.setattr(m, "_light_changes", fake_light)
    monkeypatch.setattr(m, "_all", fake_all)
    out = run(m.ui_matrix("x", include_noise=False, db=None))
    assert out["cells"] == [
        {"doc_id": "D1", "change_id": str(c1), "worst_verdict": "action_required", "n_findings": 2, "n_cleared": 1},
        {"doc_id": "D2", "change_id": str(c1), "worst_verdict": "cleared", "n_findings": 0, "n_cleared": 1}]
