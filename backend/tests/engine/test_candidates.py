from app.engine.candidates import (
    CandidateData, ChangeRow, build_candidates_from_data,
)
from app.engine.schemas import ValueChange


def _data():
    d = CandidateData()
    for pk, cid, doc in [("a", "A1", "D1"), ("b", "B1", "D1"), ("c", "C1", "D2"), ("e", "E1", "D3"), ("f", "F1", "D4")]:
        d.clauses[pk] = {"clause_id": cid, "doc_id": doc}
    d.citations = {
        "a": [{"status": "resolved", "section_id": "10", "raw": "1 IAC 2-3-4"}],
        "c": [{"status": "resolved_rule", "section_id": None, "raw": "1 IAC 2-3"}],
        "e": [{"status": "resolved", "section_id": "99", "raw": "1 IAC 2-3-9"}],   # same rule, other section
        "zz": [{"status": "resolved", "section_id": "10", "raw": "1 IAC 2-3-4"}],  # ineligible clause
    }
    # a<->b hop, b->x hop-of-hop, a->ineligible, a->c (also direct_rule)
    d.links = {
        "a": [("b", "references_clause"), ("ghost", "references_form"), ("c", "references_tariff")],
        "b": [("a", "references_clause"), ("f", "references_clause")],
    }
    d.params = [
        {"clause_pk": "b", "kind": "period", "value_text": "30 days", "value_num": 30, "unit": "days", "day_type": None},
        {"clause_pk": "e", "kind": "period", "value_text": "30 day", "value_num": 30, "unit": "Day", "day_type": "calendar"},
        {"clause_pk": "f", "kind": "period", "value_text": "30 days", "value_num": 30, "unit": "days", "day_type": None},
        {"clause_pk": "c", "kind": "period", "value_text": "30 days", "value_num": 30, "unit": "days", "day_type": "business"},
        {"clause_pk": "c", "kind": "amount", "value_text": "$30", "value_num": 30, "unit": "dollar", "day_type": None},
    ]
    return d.index()


def _ch(**kw):
    base = dict(change_id="ch1", change_class="substantive", s1_section_id=10, citation="1 IAC 2-3-4",
                rule_key="1 IAC 2-3", value_changes=None)
    base.update(kw)
    return ChangeRow(**base)


def _by_clause(rows):
    return {r.clause_id: r for r in rows}


def test_paths_priority_and_dedupe():
    rows = _by_clause(build_candidates_from_data(_data(), "run", [_ch()]))
    assert set(rows) == {"A1", "B1", "C1"}
    assert rows["A1"].match_path == "direct_section" and rows["A1"].cited_citation == "1 IAC 2-3-4"
    assert rows["C1"].match_path == "direct_rule"
    # C1 is both direct_rule and a hop target of A1: one row, both paths recorded
    assert [e["path"] for e in rows["C1"].path_detail] == ["direct_rule", "register_hop"]
    assert rows["B1"].match_path == "register_hop"
    assert rows["B1"].path_detail[0]["via_clause_id"] == "A1"
    assert rows["B1"].path_detail[0]["link_type"] == "references_clause"
    assert rows["B1"].judged_by is None and rows["B1"].skip_reason is None


def test_register_hop_one_hop_only_and_ineligible_end():
    rows = _by_clause(build_candidates_from_data(_data(), "run", [_ch()]))
    assert "F1" not in rows  # b -> f is a second hop
    assert all(r.clause_id != "ghost" for r in rows.values())


def test_value_echo():
    vc = ValueChange(kind="period", unit="day", old_value_text="30 days", new_value_text="10 days",
                     old_value_num=30, new_value_num=10, subject="x", day_type="calendar")
    rows = _by_clause(build_candidates_from_data(_data(), "run", [_ch(value_changes=[vc])]))
    # B1: same doc as a direct candidate; E1: cites the same rule (day_type equal); unit singularized
    assert rows["B1"].match_path == "register_hop"
    assert [e["path"] for e in rows["B1"].path_detail] == ["register_hop", "value_echo"]
    assert rows["E1"].match_path == "value_echo" and rows["E1"].path_detail[0]["value"] == "30 day"
    assert "F1" not in rows            # different doc, cites nothing in the rule
    # C1: day_type business != calendar, so no value_echo entry; amount param has other unit
    assert [e["path"] for e in rows["C1"].path_detail] == ["direct_rule", "register_hop"]


def test_value_echo_requires_value_changes_and_dict_input():
    assert "E1" not in _by_clause(build_candidates_from_data(_data(), "run", [_ch()]))
    vc = {"old_value_num": 30, "unit": "days", "day_type": None}
    rows = _by_clause(build_candidates_from_data(_data(), "run", [_ch(value_changes=[vc])]))
    assert "E1" in rows and "F1" not in rows


def test_repealed_renumbered_direct_section_only():
    for cls in ("repealed", "renumbered"):
        rows = build_candidates_from_data(_data(), "run", [_ch(change_class=cls, value_changes=[
            {"old_value_num": 30, "unit": "days"}])])
        assert [r.clause_id for r in rows] == ["A1"] and rows[0].match_path == "direct_section"


def test_closed_classes_skipped():
    assert build_candidates_from_data(_data(), "run", [_ch(change_class="cosmetic")]) == []
