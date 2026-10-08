import uuid

from app.engine import characterize as C
from app.engine.delta import DeltaResult
from app.engine.llm import LLMBudgetExceeded, LLMContext
from app.engine.schemas import Characterization, ValueChange

S1 = "A utility shall not disconnect service without notice. The utility shall respond within 30 days of the request."
S2 = "A utility may not disconnect service without notice. The utility shall respond within 45 days of the request."


def _char(**kw):
    base = dict(obligation_changed=True, direction="relaxed", summary="Response period lengthened.",
                value_changes=[], added_requirements=[], removed_requirements=[], quotes={})
    base.update(kw)
    return Characterization(**base)


def _vc(old="within 30 days", new="within 45 days"):
    return ValueChange(kind="period", unit="day", day_type=None, old_value_text=old, new_value_text=new,
                       old_value_num=30, new_value_num=45, subject="response time")


def _delta(s1=S1, s2=S2):
    return DeltaResult(
        change_id=str(uuid.uuid4()), origin="kb", source_system="iac", citation="1 IAC 2-3-4",
        rule_key="1 IAC 2-3", heading="h", s1_section_id=1, s2_section_id=2, renumbered_from=None,
        change_class="substantive", s1_text_norm=s1, s2_text_norm=s2, diff_segments=None,
        published_date=None, date_basis=None, din=None, amendment_source=None, in_footprint=True,
        cited_clause_count=1, disposition=None, disposition_reason=None)


def test_value_change_kept_when_verifiable():
    v = C.verify_characterization("c", _char(value_changes=[_vc()], quotes={"s1": "within 30 days", "s2": "within 45 days"}), S1, S2)
    assert v.disposition is None and len(v.value_changes) == 1 and set(v.quotes) == {"s1", "s2"}


def test_value_change_dropped_when_new_text_not_in_s2():
    v = C.verify_characterization("c", _char(value_changes=[_vc(new="within 60 days")]), S1, S2)
    assert v.value_changes == []
    assert v.disposition == "needs_review"


def test_unverifiable_added_removed_dropped_but_other_evidence_keeps_open():
    c = _char(added_requirements=["invented requirement text"], removed_requirements=["shall respond within 30 days"])
    v = C.verify_characterization("c", c, S1, S2)
    assert v.added_requirements == [] and v.removed_requirements == ["shall respond within 30 days"]
    assert v.disposition is None


def test_changed_but_nothing_verifiable_is_needs_review():
    v = C.verify_characterization("c", _char(quotes={"s1": "not in the text at all", "s2": "also missing"}), S1, S2)
    assert v.disposition == "needs_review" and v.obligation_changed is True


def test_no_obligation_change_closes():
    c = _char(obligation_changed=False, direction="style_only", summary="Wording only.")
    v = C.verify_characterization("c", c, S1, S2)
    assert v.disposition == "no_affected_clauses" and v.reason == "Wording only."


def test_param_hints_ignore_kind():
    only1, only2 = C.param_hints(S1, S2)
    assert [p["value_num"] for p in only1] == [30] and [p["value_num"] for p in only2] == [45]


async def test_characterize_one_invalid_and_budget(monkeypatch):
    async def none(*a, **k):
        return None
    monkeypatch.setattr(C, "call_cached", none)
    v = await C.characterize_one(_delta(), LLMContext(run_id=uuid.uuid4()), "sys")
    assert v.obligation_changed is None and v.disposition == "needs_review"

    async def boom(*a, **k):
        raise LLMBudgetExceeded("cap")
    monkeypatch.setattr(C, "call_cached", boom)
    v = await C.characterize_one(_delta(), LLMContext(run_id=uuid.uuid4()), "sys")
    assert v.obligation_changed is None and "cap" in v.reason


async def test_characterize_one_ok(monkeypatch):
    seen = {}

    async def fake(stage, model, system, user, schema, run_id, **k):
        seen.update(stage=stage, user=user, schema=schema)
        return _char(value_changes=[_vc()])
    monkeypatch.setattr(C, "call_cached", fake)
    v = await C.characterize_one(_delta(), LLMContext(run_id=uuid.uuid4()), "sys")
    assert seen["stage"] == "characterize" and "params_only_in_s1" in seen["user"] and "30 days" in seen["user"]
    assert len(v.value_changes) == 1 and v.disposition is None
