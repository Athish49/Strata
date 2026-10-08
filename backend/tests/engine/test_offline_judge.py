"""Offline judge export/import helpers - fakes only, no DB, no LLM."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import offline_judge_common as C  # noqa: E402
import offline_judge_export as X  # noqa: E402
import offline_judge_import as I  # noqa: E402
from app.engine import llm as L  # noqa: E402
from app.engine.schemas import JudgeResult  # noqa: E402
from tests.engine.test_judge import CLAUSE, S1, S2, make_item  # noqa: E402

ANS = dict(affected=True, finding_type="required_content_change", severity="high", required_change=None,
           quotes={"s1": "within 30 days", "s2": "within 45 days", "clause": "within 30 days"},
           rationale="Period changed.", confidence=0.9)


def test_key_parity_with_engine_prompts():
    from app.engine import judge as J
    it = make_item(clause_role="regulatory_restatement")
    system, user = C.build_prompts(it)
    assert system == J.system_prompt_for(it) and user == J.build_user_prompt(it)
    assert C.cache_key(system, user) == L.prompt_sha256(system, user, JudgeResult)
    plain = make_item(clause_role="internal_procedure")
    assert C.build_prompts(plain)[0] == J.SYSTEM_PROMPT != system


def test_plan_splits_hits_and_misses():
    a = make_item(clause_role="internal_procedure", candidate_id="a")
    b = make_item(clause_role="regulatory_restatement", candidate_id="b", clause_id="CL-2")
    sha_a = C.cache_key(*C.build_prompts(a))
    p = X.plan([a, b], {sha_a})
    assert (p["llm_judged"], p["cache_hits"], p["cache_misses"]) == (2, 1, 1)
    assert [e["id"] for e in p["entries"]] == ["b"]
    e = p["entries"][0]
    assert e["prompt_sha256"] == C.cache_key(e["system"], e["user"])


def test_write_out_idempotent_and_batches(tmp_path):
    items = [make_item(candidate_id=f"c{i}", clause_id=f"CL-{i}", clause_role="definition") for i in range(5)]
    p = X.plan(items, set())
    m1 = X.write_out(tmp_path, "run", "m", p, 2)
    names1 = sorted(f.name for f in tmp_path.glob("batch_*.json"))
    m2 = X.write_out(tmp_path, "run", "m", p, 2)
    assert m1 == m2 and names1 == ["batch_01.json", "batch_02.json", "batch_03.json"]
    assert m1["cache_misses"] == 5 and [b["count"] for b in m1["batches"]] == [2, 2, 1]


def _prep(tmp_path, answers):
    p = X.plan([make_item(candidate_id="c1", clause_role="regulatory_restatement")], set())
    X.write_out(tmp_path, "00000000-0000-0000-0000-000000000001", "claude-sonnet-5-5", p, 50)
    (tmp_path / "answers_01.json").write_text(json.dumps(answers))
    return p["entries"][0]


def test_check_answers_validates(tmp_path):
    ent = _prep(tmp_path, [
        {"id": "c1", "answer": ANS},
        {"id": "zzz", "answer": ANS},
        {"id": "c1", "answer": {**ANS, "severity": "bogus"}},
    ])
    good, rejected, qwarn = I.check_answers(tmp_path, I.load_prompts(tmp_path))
    assert len(good) == 1 and good[0][1] == ent["prompt_sha256"]
    reasons = " | ".join(r["reason"] for r in rejected)
    assert "unknown id" in reasons and "duplicate answer" in reasons
    assert qwarn == []


def test_bad_schema_and_quote_warning(tmp_path):
    _prep(tmp_path, [{"id": "c1", "answer": {"affected": True}}])
    good, rejected, _ = I.check_answers(tmp_path, I.load_prompts(tmp_path))
    assert not good and rejected[0]["reason"].startswith("schema:")
    (tmp_path / "answers_01.json").write_text(json.dumps(
        [{"id": "c1", "answer": {**ANS, "quotes": {"s1": "not in prompt at all", "clause": CLAUSE[:20]}}}]))
    good, rejected, qwarn = I.check_answers(tmp_path, I.load_prompts(tmp_path))
    assert len(good) == 1 and qwarn == [{"id": "c1", "quote": "s1"}]


class FakeSession:
    def __init__(self):
        self.store = []

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        if sql.startswith("SELECT"):
            hit = any(r["sha"] == params["h"] for r in self.store)

            class R:
                def first(self_):
                    return (1,) if hit else None
            return R()
        self.store.append(dict(params))

    async def commit(self):
        pass


def test_import_row_shape_dry_run_and_idempotent(tmp_path):
    _prep(tmp_path, [{"id": "c1", "answer": ANS}])
    good, _, _ = I.check_answers(tmp_path, I.load_prompts(tmp_path))
    s = FakeSession()
    assert asyncio.run(I.run_import(s, good, "m", "rid", True)) == {"inserted": 1, "skipped_existing": 0}
    assert s.store == []
    assert asyncio.run(I.run_import(s, good, "m", "rid", False))["inserted"] == 1
    assert asyncio.run(I.run_import(s, good, "m", "rid", False)) == {"inserted": 0, "skipped_existing": 1}
    row = s.store[0]
    assert row["valid"] is True and row["error"] == C.PROVENANCE and row["stage"] == "judge"
    assert json.loads(row["request"])["schema_name"] == "JudgeResult"
    # the engine's cache lookup would accept it
    assert JudgeResult.model_validate(json.loads(row["response"])).affected is True
