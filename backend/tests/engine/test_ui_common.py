from datetime import datetime, timedelta, timezone

from app.api.engine import routes_ui_common as c

CL = {"clause_id": "RPL-CS-PRO-004:8.2", "doc_id": "RPL-CS-PRO-004", "heading_path": ["8", "Notice"]}


def test_clean_heading():
    assert c.clean_heading("170 IAC 4-1-16", "170 IAC 4-1-16 Reports") == "Reports"
    assert c.clean_heading("170 IAC 4-1-16", "170 iac 4-1-16: Reports.") == "Reports"
    assert c.clean_heading("18 CFR 35.19", "§ 35.19 Fuel cost") == "Fuel cost"
    assert c.clean_heading("x", "Plain") == "Plain"
    assert c.clean_heading("170 IAC 4-1-16", "170 IAC 4-1-16") == "170 IAC 4-1-16"
    assert c.clean_heading("x", None) == ""


def test_direction_and_reason():
    assert c.map_direction("removed_requirement") == "removed"
    assert c.map_direction("mixed") == "mixed"
    assert c.map_direction(None) is None
    assert c.cleared_reason_text("metadata_only", "170 IAC 1-1") == \
        "Checked: no impact — metadata-only change to 170 IAC 1-1."
    assert c.cleared_reason_text("weird_Class", "X") == "Checked: no impact — weird_class change to X."
    assert c.cleared_reason_text(None, "X") == "Checked: no impact."


def test_map_stats_empty_and_full():
    e = c.map_stats(None)
    assert e["changes_raw"] == 0 and e["by_class"] == {} and e["in_footprint"] == 0
    assert e["candidates_by_path"] == {p: 0 for p in c.CANDIDATE_PATHS}
    assert e["findings_by_verdict"] == {v: 0 for v in c.VERDICT_RANK}
    assert e["radar"] == {"applicable": 0, "screened_out": 0, "unclear": 0}
    s = {"raw_changed": 10, "by_class": {"substantive": 3, "repealed": 1, "cosmetic": 5, "cross_ref_only": 1},
         "substantive": 3, "in_footprint": {"substantive": 2, "cosmetic": 1}, "obligation_changed": 2,
         "candidates": {"direct_section": 4}, "findings": {"review": 2}, "clauses_cleared": 7,
         "docs_flagged": 1, "docs_cleared": 2, "radar": {"yes": 1, "no": 2, "unclear": 3},
         "judged_rule": 5, "judged_llm": 6, "llm_calls": 0}
    m = c.map_stats(s)
    assert m["substantive"] == 4 and m["noise"] == 6
    assert m["changes_raw"] == m["substantive"] + m["noise"]
    assert m["in_footprint"] == 3 and m["in_footprint_real"] == 2
    assert e["in_footprint_real"] is None
    assert m["candidates_by_path"]["direct_section"] == 4 and m["candidates_by_path"]["register_hop"] == 0
    assert m["findings_by_verdict"]["review"] == 2 and m["findings_by_verdict"]["info"] == 0
    assert m["radar"] == {"applicable": 1, "screened_out": 2, "unclear": 3}
    assert m["decided_by"] == {"rule": 5, "ai": 6}


def test_map_run_status():
    now = datetime.now(timezone.utc)
    assert c.map_run_status("done", now, now) == "succeeded"
    assert c.map_run_status("failed", now, None) == "failed"
    assert c.map_run_status("running", now, None) == "running"
    old = now - timedelta(minutes=c.STALE_RUN_MINUTES + 1)
    assert c.map_run_status("running", old, None) == "failed"
    assert c.map_run_status("running", old.replace(tzinfo=None), None) == "failed"
    assert c.map_run_status("running", old, now) == "running"


def test_build_path_nodes():
    sec = lambda: {"kind": "section", "ref": "170 IAC 4-1-16", "label": "170 IAC 4-1-16 · Reports"}
    clause = {"kind": "clause", "ref": CL["clause_id"], "label": "RPL-CS-PRO-004 · Notice"}
    n = c.build_path_nodes([{"path": "direct_section"}], "direct_section", "170 IAC 4-1-16",
                           "170 IAC 4-1-16 Reports", CL)
    assert n == [sec(), clause]
    n = c.build_path_nodes([{"path": "direct_section"}, {"path": "direct_rule", "value": "170 IAC 4-1"}],
                           "direct_rule", "170 IAC 4-1-16", "Reports", CL)
    assert n[1] == {"kind": "rule", "ref": "170 IAC 4-1", "label": "170 IAC 4-1"} and len(n) == 3
    steps = [{"path": "register_hop", "via_clause_id": "RPL-CMP-REG-001:OBL-1"}]
    via = {"clause_id": "RPL-CMP-REG-001:OBL-1", "doc_id": "RPL-CMP-REG-001", "unit_kind": "register_row"}
    n = c.build_path_nodes(steps, "register_hop", "170 IAC 4-1-16", "Reports", CL, via)
    assert n[1] == {"kind": "register_row", "ref": "RPL-CMP-REG-001:OBL-1", "label": "RPL-CMP-REG-001 · OBL-1"}
    via["unit_kind"] = "tariff_subrule"
    assert c.build_path_nodes(steps, "register_hop", "c", "", CL, via)[1]["kind"] == "tariff_rule"
    via["unit_kind"] = "section"
    assert c.build_path_nodes(steps, "register_hop", "c", "", CL, via)[1]["kind"] == "clause"
    # no matching step -> first step; no steps -> section+clause; no heading_path -> local id
    cl2 = {"clause_id": "D:1.2", "doc_id": "D", "heading_path": []}
    n = c.build_path_nodes([], None, "c", None, cl2)
    assert [x["kind"] for x in n] == ["section", "clause"] and n[0]["label"] == "c" and n[1]["label"] == "D · 1.2"
    n = c.build_path_nodes([{"path": "value_echo"}], "zzz", "c", "H", cl2)
    assert len(n) == 2
