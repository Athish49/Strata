from app.engine.rules import (
    RuleCandidate, RuleChange, RuleClause, apply_rules, map_verdict, severity_for,
)
from app.engine.schemas import ValueChange

S1 = "The provider shall file the report within 30 days of the event. Other text here."
S2 = "The provider shall file the report within 10 days of the event. Other text here."
CLAUSE = "Preamble sentence. The vendor must file the report within 30 days of the event. Tail."


def _vc(**kw):
    d = dict(kind="period", unit="day", day_type=None, old_value_text="30 days",
             new_value_text="10 days", old_value_num=30.0, new_value_num=10.0,
             subject="report filing deadline")
    d.update(kw)
    return ValueChange(**d)


def _change(vcs=None, **kw):
    d = dict(change_id="c1", citation="X 1-2", change_class="substantive",
             direction="tightened", value_changes=[_vc()] if vcs is None else vcs,
             s1_text_norm=S1, s2_text_norm=S2)
    d.update(kw)
    return RuleChange(**d)


def _param(**kw):
    s = CLAUSE.index("30 days")
    d = dict(kind="period", value_text="30 days", value_num=30.0, unit="days",
             day_type=None, span_start=s, span_end=s + 7, is_citation_fragment=False)
    d.update(kw)
    return d


def _clause(params=None):
    return RuleClause(clause_pk=1, clause_id="d:1", doc_id="d",
                      text_raw=CLAUSE, parameters=[_param()] if params is None else params)


def _cand(**kw):
    d = dict(candidate_id=1, cited_citation="X 1-2", match_path="direct_section")
    d.update(kw)
    return RuleCandidate(**d)


def test_r4_skip_reason_clears():
    r = apply_rules(_change(), _clause(), _cand(skip_reason="superseded"))
    assert r.decided and r.cleared and r.finding is None


def test_r1_repealed():
    r = apply_rules(_change(change_class="repealed"), _clause(), _cand())
    f = r.finding
    assert f.finding_type == "stale_citation" and f.verdict == "update_citation"
    assert f.severity == "low" and f.decided_by == "rule" and f.confidence is None
    assert f.required_change == {"from_text": "X 1-2", "to_text": "(repealed)"}
    assert f.rationale == "Cited section repealed in S2; confirm whether the obligation can be removed."


def test_r1_not_for_other_paths():
    assert apply_rules(_change(change_class="repealed", vcs=[]), _clause(),
                       _cand(match_path="direct_rule")) is None


def test_r2_renumbered():
    c = _change(change_class="renumbered", citation="X 1-9", renumbered_from="X 1-2")
    f = apply_rules(c, _clause(), _cand()).finding
    assert f.finding_type == "stale_citation"
    assert f.required_change == {"from_text": "X 1-2", "to_text": "X 1-9"}


def test_r3_parameter_change_with_singularized_unit():
    r = apply_rules(_change(), _clause(), _cand(match_path="value_echo"))
    f = r.finding
    assert f.finding_type == "parameter_change" and f.severity == "high"
    assert f.verdict == "action_required"
    assert f.required_change == {"from_text": "30 days", "to_text": "10 days"}
    assert f.rationale == ("Clause states 30 days; X 1-2 now requires 10 days "
                           "(report filing deadline).")
    assert f.quotes_verified
    assert "30 days" in f.quotes["s1"] and "10 days" in f.quotes["s2"]
    assert f.quotes["clause"] == "The vendor must file the report within 30 days of the event."


def test_r3_relaxed():
    r = apply_rules(_change(direction="relaxed"), _clause(), _cand())
    assert r.finding.verdict == "optional_relaxed"


def test_r3_day_type_mismatch_no_override():
    c = _change(vcs=[_vc(day_type="business")])
    assert apply_rules(c, _clause([_param(day_type="calendar")]), _cand()) is None
    assert apply_rules(c, _clause([_param(day_type=None)]), _cand()) is not None


def test_r3_citation_fragment_ignored():
    assert apply_rules(_change(), _clause([_param(is_citation_fragment=True)]), _cand()) is None


def test_r3_bare_number_ineligible():
    p = _param(kind="number", unit=None)
    c = _change(vcs=[_vc(unit=None)])
    assert apply_rules(c, _clause([p]), _cand()) is None


def test_r3_unverified_value_change_skipped():
    c = _change(vcs=[_vc(old_value_text="45 days", old_value_num=45.0)])
    assert apply_rules(c, _clause([_param(value_num=45.0)]), _cand()) is None


def test_r3_quote_failure_flags_unverified():
    # clause context too short to verify (< MIN_QUOTE_LEN)
    cl = RuleClause(clause_pk=1, clause_id="d:1", doc_id="d", text_raw="30 days",
                    parameters=[_param(span_start=0, span_end=7)])
    r = apply_rules(_change(), cl, _cand())
    assert r.finding.quotes_verified is False


def test_mappings():
    assert map_verdict("informational", None, True) == "review"
    assert map_verdict("informational", None, False) == "info"
    assert map_verdict("stale_citation", "relaxed") == "update_citation"
    assert map_verdict("conflict", "relaxed") == "optional_relaxed"
    assert map_verdict("conflict", "tightened") == "action_required"
    assert severity_for("informational") == "low" and severity_for("conflict") == "high"
