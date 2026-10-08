from datetime import date

import pytest

from app.engine import judge as J
from app.engine import llm as L
from app.engine.schemas import JudgeResult, ValueChange

S1 = "The utility shall file the report within 30 days after the end of each quarter."
S2 = "The utility shall file the report within 45 days after the end of each quarter."
CLAUSE = "Staff must submit the quarterly report within 30 days of quarter end."


def make_item(**kw):
    base = dict(
        candidate_id="00000000-0000-0000-0000-0000000000c1",
        change_id="00000000-0000-0000-0000-0000000000a1",
        clause_pk="00000000-0000-0000-0000-0000000000b1", clause_id="CL-1", doc_id="D1",
        cited_citation="1-2-3", match_path="direct_section",
        path_detail=[{"path": "direct_section", "value": "1-2-3"}],
        citation="1-2-3", change_class="substantive", origin="kb", source_system="iac",
        heading="Reports", direction="tightened", summary="Period changed.",
        value_changes=[], char_quotes=None, s1_text_norm=S1, s2_text_norm=S2,
        diff_segments=[{"op": "equal", "text": "within"}, {"op": "delete", "text": "30"},
                       {"op": "insert", "text": "45"}],
        renumbered_from=None, published_date=date(2025, 6, 1), doc_title="Doc",
        heading_path=["A", "B"], unit_kind="paragraph", text_raw=CLAUSE, parameters=[],
        approved_date=date(2024, 1, 1),
    )
    base.update(kw)
    return J.JudgeItem(**base)


def jr(**kw):
    base = dict(affected=True, finding_type="required_content_change", severity="high",
                required_change={"from_text": "within 30 days", "to_text": "within 45 days"},
                quotes={"s1": "within 30 days after the end", "s2": "within 45 days after the end",
                        "clause": "within 30 days of quarter end"},
                rationale="Period differs.", confidence=0.9)
    base.update(kw)
    return JudgeResult(**base)


@pytest.fixture
def fake(monkeypatch):
    st = {"results": [], "users": []}

    async def call(stage, model, system, user, schema, run_id, **kw):
        st["users"].append(user)
        return st["results"].pop(0)

    monkeypatch.setattr(L, "call_cached", call)
    return st


def ctx():
    return L.LLMContext()


async def run(item, fake_state, *results):
    fake_state["results"] = list(results)
    return await J.judge_item(item, "00000000-0000-0000-0000-000000000001", ctx(), "m")


async def test_happy_path_action_required(fake):
    out = await run(make_item(), fake, jr())
    f = out.finding
    assert out.affected is True and out.judged_by == "llm"
    assert f.finding_type == "required_content_change" and f.verdict == "action_required"
    assert f.quotes_verified and f.severity == "high" and f.decided_by == "llm"
    assert len(fake["users"]) == 1


async def test_relaxed_direction_optional(fake):
    out = await run(make_item(direction="relaxed"), fake, jr())
    assert out.finding.verdict == "optional_relaxed"


async def test_p6_unaffected(fake):
    out = await run(make_item(), fake, jr(affected=False, rationale="Different topic."))
    assert out.affected is False and out.finding is None and out.rationale == "Different topic."


async def test_p1_retry_once_then_success(fake):
    bad = jr(quotes={"s1": "within 30 days after the end", "s2": "this text is invented here",
                     "clause": "within 30 days of quarter end"})
    out = await run(make_item(), fake, bad, jr())
    assert len(fake["users"]) == 2
    assert "failed quote verification" in fake["users"][1] and "quotes.s2" in fake["users"][1]
    assert out.finding.quotes_verified and out.finding.finding_type == "required_content_change"


async def test_p1_fails_twice_informational_review(fake):
    bad = jr(quotes={"s1": None, "s2": None, "clause": "not in the clause at all"})
    out = await run(make_item(), fake, bad, bad)
    assert len(fake["users"]) == 2
    f = out.finding
    assert f.finding_type == "informational" and out.needs_review and not f.quotes_verified
    assert f.verdict == "review" and f.severity == "low"


async def test_p1_retry_becomes_unaffected(fake):
    bad = jr(quotes={"s1": None, "s2": None, "clause": "not in the clause at all"})
    out = await run(make_item(), fake, bad, jr(affected=False))
    assert out.affected is False and out.finding is None


async def test_p2_confidence_gate(fake):
    out = await run(make_item(), fake, jr(confidence=0.3))
    f = out.finding
    assert f.finding_type == "informational" and out.needs_review and f.verdict == "review"
    assert f.quotes_verified and f.severity == "low"


async def test_p3_stale_at_approval(fake):
    item = make_item(published_date=date(2023, 12, 1), approved_date=date(2024, 1, 1))
    out = await run(item, fake, jr())
    assert out.finding.finding_type == "stale_at_approval"
    assert out.finding.verdict == "action_required" and out.finding.severity == "high"


async def test_p3_not_applied_cases(fake):
    base = dict(published_date=date(2023, 12, 1), approved_date=date(2024, 1, 1))
    for kw in (dict(origin="whatif"), dict(published_date=None), dict(approved_date=None),
               dict(published_date=date(2024, 2, 1))):
        out = await run(make_item(**{**base, **kw}), fake, jr())
        assert out.finding.finding_type == "required_content_change", kw
    # not in the eligible type set
    out = await run(make_item(**base), fake, jr(finding_type="stale_citation"))
    assert out.finding.finding_type == "stale_citation" and out.finding.verdict == "update_citation"
    assert out.finding.severity == "low"


async def test_llm_never_stale_at_approval(fake):
    item = make_item(published_date=date(2025, 6, 1))
    out = await run(item, fake, jr(finding_type="stale_at_approval"))
    assert out.finding.finding_type == "required_content_change"


async def test_none_result(fake):
    out = await run(make_item(), fake, None)
    f = out.finding
    assert out.judged_by == "llm" and out.affected is None
    assert f.finding_type == "informational" and out.needs_review and not f.quotes_verified
    assert f.rationale == "LLM judgement unavailable" and f.verdict == "review"


async def test_none_on_retry(fake):
    bad = jr(quotes={"s1": None, "s2": None, "clause": "not in the clause at all"})
    out = await run(make_item(), fake, bad, None)
    assert out.affected is None and out.finding.rationale == "LLM judgement unavailable"


async def test_budget_exceeded(monkeypatch):
    async def call(*a, **k):
        raise L.LLMBudgetExceeded("cap")

    monkeypatch.setattr(L, "call_cached", call)
    out = await J.judge_item(make_item(), "00000000-0000-0000-0000-000000000001", ctx(), "m")
    assert out.affected is None and "cap" in out.rationale


# ---- rules bridge ----
def test_rules_r3_decides():
    vc = ValueChange(kind="period", unit="days", day_type=None, old_value_text="30 days",
                     new_value_text="45 days", old_value_num=30, new_value_num=45, subject="report")
    item = make_item(value_changes=[vc], parameters=[
        {"kind": "period", "value_text": "30 days", "value_num": 30, "unit": "days",
         "day_type": None, "span_start": None, "span_end": None, "is_citation_fragment": False}])
    out = J.decide_by_rules(item)
    assert out.judged_by == "rule" and out.finding.finding_type == "parameter_change"
    assert out.finding.decided_by == "rule"


def test_rules_none_goes_to_llm():
    assert J.decide_by_rules(make_item()) is None


def test_rules_r1_repealed():
    out = J.decide_by_rules(make_item(change_class="repealed", s2_text_norm=None))
    assert out.finding.finding_type == "stale_citation" and out.finding.verdict == "update_citation"


# ---- prompt building ----
def test_render_diff():
    d = J.render_diff([{"op": "equal", "text": "a b"}, {"op": "delete", "text": "30"},
                       {"op": "insert", "text": "45"}])
    assert d == "a b [-30-] {+45+}"


def test_window_short_texts_unchanged():
    assert J.window_texts("abc def", "abc xyz", 100, 10) == ("abc def", "abc xyz")


def test_window_long_texts_windowed():
    filler = " ".join(f"w{i}" for i in range(400))
    a = f"{filler} the period is 30 days {filler}"
    b = f"{filler} the period is 45 days {filler}"
    s1, s2 = J.window_texts(a, b, 1000, 40)
    assert len(a) > 1000 and len(s1) < 200 and len(s2) < 200
    assert "30" in s1 and "45" in s2 and "30" not in s2
    assert s1.startswith("...") and "the period is" in s1


def test_window_multiple_hunks_marker():
    filler = " ".join(f"w{i}" for i in range(400))
    a = f"first 30 days {filler} second 10 hours {filler}"
    b = f"first 45 days {filler} second 20 hours {filler}"
    s1, _ = J.window_texts(a, b, 1000, 40)
    assert J.HUNK_SEP in s1 and "first" in s1 and "second" in s1


def test_user_prompt_contents_and_windowing():
    item = make_item(
        value_changes=[ValueChange(kind="period", unit="days", old_value_text="30 days",
                                   new_value_text="45 days", old_value_num=30,
                                   new_value_num=45, subject="report filing")],
        path_detail=[{"path": "register_hop", "via_clause_id": "REG-9",
                      "link_type": "references_obligation"}], match_path="register_hop",
        parameters=[{"kind": "period", "value_text": "30 days", "unit": "days", "day_type": None}])
    u = J.build_user_prompt(item)
    for needle in ("CL-1", "Doc", "A > B", "paragraph", CLAUSE, "report filing", "[-30-]",
                   "{+45+}", "REG-9", "references_obligation", "Direction: tightened"):
        assert needle in u, needle
    filler = " ".join(f"w{i}" for i in range(2000))
    big = make_item(s1_text_norm=f"{filler} limit is 30 days {filler}",
                    s2_text_norm=f"{filler} limit is 45 days {filler}")
    u2 = J.build_user_prompt(big, max_chars=1000, window=50)
    assert len(u2) < 2500 and "limit is 30 days" in u2


def test_match_path_words():
    it = make_item(path_detail=[{"path": "direct_section", "value": "1-2-3"},
                                {"path": "value_echo", "value": "30 days"}])
    w = J.match_path_words(it)
    assert "cites this section" in w and "30 days" in w


def test_system_prompt_loaded():
    assert "stale_at_approval" in J.SYSTEM_PROMPT and "NOT enough" in J.SYSTEM_PROMPT


def test_rule_finding_with_unverified_quotes_is_downgraded(monkeypatch):
    from app.engine import judge as J
    from app.engine.rules import FindingDraft, RuleDecision
    draft = FindingDraft(finding_type="parameter_change", severity="high", verdict="action_required",
                         required_change={"from_text": "7", "to_text": "10"},
                         quotes={"s1": "a", "s2": "b", "clause": ""}, quotes_verified=False, rationale="r")
    monkeypatch.setattr(J, "apply_rules", lambda *a: RuleDecision(decided=True, finding=draft, rationale="r"))
    monkeypatch.setattr(J, "_rule_objs", lambda item: (None, None, None))
    out = J.decide_by_rules(object())
    assert out.finding.finding_type == "informational" and out.needs_review is True
    assert out.finding.verdict == "review"
