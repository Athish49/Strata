"""Radar stage: code rules, prompt building, and the radar route (no DB / no LLM)."""
import asyncio
import uuid

import pytest

from app.engine import radar
from app.engine.schemas import RadarResult
from tests.engine.test_api_routes import RUN, client_for, run_row, _clear  # noqa: F401

S2 = "The operator shall inspect every generator within 30 days of the event."
KEYS = {"has_fleet_vehicles", "utility_type"}


def res(**kw):
    base = dict(obligation_changed=True, applicable="yes", attribute_basis=["utility_type"],
                affected_activity="x", reason="r", quote_s2="inspect every generator within 30 days")
    return RadarResult(**{**base, **kw})


def test_yes_keeps_valid_basis_and_verifies_quote():
    o = radar.apply_rules(res(attribute_basis=["utility_type", "bogus"]), KEYS, S2)
    assert o["applicable"] == "yes" and o["attribute_basis"] == ["utility_type"]
    assert o["quote_verified"] is True


def test_yes_with_only_invalid_basis_becomes_unclear():
    assert radar.apply_rules(res(attribute_basis=["bogus"]), KEYS, S2)["applicable"] == "unclear"
    assert radar.apply_rules(res(attribute_basis=[]), KEYS, S2)["applicable"] == "unclear"


def test_no_obligation_change_forces_no():
    o = radar.apply_rules(res(obligation_changed=False, reason="whatever"), KEYS, S2)
    assert o["applicable"] == "no" and o["reason"] == "no change in obligation"


def test_unverified_and_missing_quote():
    assert radar.apply_rules(res(quote_s2="a made up sentence entirely"), KEYS, S2)["quote_verified"] is False
    assert radar.apply_rules(res(quote_s2=None), KEYS, S2)["quote_verified"] is None


def test_prompt_by_class():
    attrs = [("utility_type", "electric")]
    ch = {"citation": "C 1", "heading": "H", "agency": "A", "change_class": "substantive",
          "diff_segments": [{"op": "equal", "text": "a"}, {"op": "delete", "text": "30"},
                            {"op": "insert", "text": "10"}]}
    p = radar.build_user_prompt(ch, attrs)
    assert "a [-30-] {+10+}" in p and "utility_type=electric" in p
    p = radar.build_user_prompt({**ch, "change_class": "new_section", "s2_text_norm": "NEWTEXT"}, attrs)
    assert "NEWTEXT" in p
    p = radar.build_user_prompt({**ch, "change_class": "repealed", "s1_text_norm": "OLDTEXT"}, attrs)
    assert "OLDTEXT" in p and "Repealed" in p


def test_long_diff_is_trimmed_to_changes():
    segs = [{"op": "equal", "text": "w " * 4000}, {"op": "insert", "text": "NEWBIT"},
            {"op": "equal", "text": "z " * 4000}]
    out = radar._diff_for_prompt(segs)
    assert "NEWBIT" in out and len(out) < 7000


def test_run_stage_writes_stats_and_charges_budget(monkeypatch):
    async def fake_run_radar(sf, run_id, company_id, max_calls):
        assert max_calls == 8
        return {"yes": 1, "no": 2, "unclear": 0}, 3

    monkeypatch.setattr(radar, "run_radar", fake_run_radar)

    class L:
        max_calls, calls_made = 10, 2

    class S:
        session_factory, run_id, llm, stats = None, RUN, L(), {}

    asyncio.run(radar.run_stage(S))
    assert S.stats["radar"] == {"yes": 1, "no": 2, "unclear": 0} and S.llm.calls_made == 5


async def test_radar_route_filters_and_serialises():
    cid = uuid.uuid4()
    row = {"change_id": cid, "citation": "C 1", "heading": "H", "agency": "A", "obligation_changed": True,
           "applicable": "yes", "attribute_basis": ["utility_type"], "affected_activity": "x",
           "reason": "r", "quote_s2": None, "rule_covered_by_docs": None}
    c, sess = client_for([("FROM engine.runs r", [run_row()]), ("FROM engine.radar_items", [row])])
    async with c:
        r = await c.get(f"/engine/runs/{RUN}/radar?applicable=yes")
        assert r.status_code == 200
        assert r.json()[0]["change_id"] == str(cid) and r.json()[0]["rule_covered_by_docs"] == []
        assert (await c.get(f"/engine/runs/{RUN}/radar?applicable=maybe")).status_code == 422
    assert sess.sql[-1][1]["app"] == "yes"


async def test_radar_route_404_and_409():
    c, _ = client_for([("FROM engine.runs r", [])])
    async with c:
        assert (await c.get(f"/engine/runs/{RUN}/radar")).status_code == 404
    c, _ = client_for([("FROM engine.runs r", [run_row("running")])])
    async with c:
        assert (await c.get(f"/engine/runs/{RUN}/radar")).status_code == 409
