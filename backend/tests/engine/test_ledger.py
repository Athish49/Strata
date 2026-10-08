import json
import uuid

import pytest
from sqlalchemy import text

from app.engine.ledger import (
    LedgerCheckError,
    build_rollup,
    build_stats,
    check_completeness,
    cleared_reason,
    compute_propagation,
    decide_disposition,
    run_ledger,
)


def F(**kw):
    base = dict(finding_id="f1", change_id="c1", candidate_id="k1", clause_pk="p1", clause_id="cl1",
                doc_id="d1", finding_type="parameter_change", verdict="action_required",
                needs_review=False, quotes_verified=True, match_path="direct_section")
    base.update(kw)
    return base


def test_disposition_untouched_cases():
    assert decide_disposition({"disposition": "excluded_noise"}, 3, []) is None
    assert decide_disposition({"disposition": "not_in_footprint"}, 0, []) is None
    assert decide_disposition({"disposition": "needs_review", "change_class": "new_section"}, 0, []) is None
    # set by characterize, no findings -> keep its reason
    assert decide_disposition({"disposition": "no_affected_clauses"}, 0, []) is None
    assert decide_disposition({"disposition": "needs_review", "change_class": "substantive"}, 0, []) is None


def test_disposition_decisions():
    ch = {"disposition": None, "change_class": "substantive"}
    assert decide_disposition(ch, 2, [F()])[0] == "findings_emitted"
    info_rev = F(finding_type="informational", verdict="review", needs_review=True)
    assert decide_disposition(ch, 2, [info_rev])[0] == "needs_review"
    assert decide_disposition(ch, 2, [info_rev, F()])[0] == "findings_emitted"
    info = F(finding_type="informational", verdict="info", needs_review=False)
    assert decide_disposition(ch, 2, [info]) == ("no_affected_clauses", "2 candidate(s) checked, none affected")
    assert decide_disposition(ch, 0, [])[0] == "no_affected_clauses"
    # earlier no_affected disposition is overridden when findings now exist
    assert decide_disposition({"disposition": "no_affected_clauses", "change_class": "substantive"},
                              1, [F()])[0] == "findings_emitted"


def test_propagation():
    parent = F(finding_id="fp", candidate_id="kp", clause_id="REG1")
    hop = F(finding_id="fh", candidate_id="kh", clause_id="X", match_path="register_hop")
    other_change = F(finding_id="fo", change_id="c2", clause_id="REG1")
    pd = {"kh": [{"path": "register_hop", "via_clause_id": "REG1", "link_type": "references_clause"}]}
    assert compute_propagation([parent, hop, other_change], pd) == {"fh": "fp"}
    # no finding on the via clause -> nothing
    assert compute_propagation([hop], pd) == {}


def test_completeness_violations():
    changes = [{"change_id": "c1", "citation": "a", "disposition": None}, {"change_id": "c2", "disposition": "x"}]
    cands = [{"candidate_id": "k1", "clause_id": "a", "judged_by": None, "skip_reason": None},
             {"candidate_id": "k2", "judged_by": "rule", "skip_reason": None},
             {"candidate_id": "k3", "judged_by": None, "skip_reason": "noise:cosmetic"}]
    fnds = [F(quotes_verified=False), F(finding_id="f2", finding_type="informational", quotes_verified=False)]
    v = check_completeness(changes, cands, fnds)
    assert len(v) == 3
    assert check_completeness([changes[1]], cands[1:], [fnds[1]]) == []
    err = LedgerCheckError(v)
    assert "3 violation" in str(err)


def test_cleared_reason_templates():
    assert cleared_reason([]) == "No S2 change touches sections this document cites."
    assert cleared_reason(["cosmetic", "cosmetic", "no obligation change"]) == \
        "3 changes considered: 2 cosmetic, 1 no obligation change"
    assert cleared_reason(["cosmetic"]) == "1 change considered: 1 cosmetic"


def test_rollup_flagged_and_cleared():
    chg = {"c1": {"citation": "A 1", "change_class": "substantive"},
           "c2": {"citation": "B 2", "change_class": "cosmetic"}}
    cands = [{"change_id": "c1", "clause_pk": "p1", "skip_reason": None},
             {"change_id": "c1", "clause_pk": "p2", "skip_reason": None},
             {"change_id": "c2", "clause_pk": "p3", "skip_reason": "noise:cosmetic"}]
    r = build_rollup("d1", chg, cands, [F()])
    assert r["status"] == "flagged" and r["reason"] is None
    assert r["counts"]["action_required"] == 1 and r["counts"]["cleared_clauses"] == 2
    assert [c["outcome"] for c in r["changes_considered"]] == ["findings_emitted", "cosmetic"]

    r = build_rollup("d1", chg, cands[2:], [])
    assert r["status"] == "cleared" and r["reason"] == "1 change considered: 1 cosmetic"
    r = build_rollup("d9", chg, [], [])
    assert r["status"] == "cleared" and r["changes_considered"] == []
    assert r["reason"] == "No S2 change touches sections this document cites."
    # informational-only doc is cleared
    info = F(finding_type="informational", verdict="info")
    r = build_rollup("d1", chg, cands[:1], [info])
    assert r["status"] == "cleared" and r["counts"]["info"] == 1


def test_stats():
    cands = [{"match_path": "direct_section", "judged_by": "rule", "clause_pk": "p1"},
             {"match_path": "register_hop", "judged_by": "llm", "clause_pk": "p2"}]
    st = build_stats([{"obligation_changed": True}, {"obligation_changed": None}], cands, [F()],
                     [{"status": "flagged"}, {"status": "cleared"}])
    assert st["candidates"] == {"direct_section": 1, "register_hop": 1}
    assert st["judged_rule"] == 1 and st["judged_llm"] == 1 and st["findings"] == {"action_required": 1}
    assert st["clauses_cleared"] == 1 and st["docs_flagged"] == 1 and st["docs_cleared"] == 1
    assert st["obligation_changed"] == 1 and "radar" not in st


# ---------------------------------------------------------------------------
# Live DB: synthetic run in engine.* only
# ---------------------------------------------------------------------------

@pytest.fixture
async def live_session():
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.db import engine as app_engine
    eng = create_async_engine(app_engine.url, poolclass=NullPool)  # one engine per test loop
    s = AsyncSession(eng, expire_on_commit=False)
    try:
        await s.execute(text("SELECT 1"))
    except Exception as e:  # unusable DATABASE_URL / no network
        await s.close()
        await eng.dispose()
        pytest.skip(f"live DB unavailable: {e}")
    try:
        yield s
    finally:
        await s.close()
        await eng.dispose()


@pytest.mark.neon
async def test_ledger_synthetic_run(live_session):
    from app.engine.config import engine_settings
    s = live_session
    cid = engine_settings.ENGINE_COMPANY_ID
    docs = (await s.execute(text(
        "SELECT doc_id, owner_id, reviewer_id, approver_id FROM company.company_documents "
        "WHERE company_id = :c ORDER BY doc_id"), {"c": cid})).mappings().all()
    if len(docs) < 2:
        pytest.skip("need >=2 company documents")
    da, db = docs[0], docs[1]
    rid = str(uuid.uuid4())
    ch = {k: str(uuid.uuid4()) for k in ("sub", "cos", "none", "noise", "pend")}
    pk = {k: str(uuid.uuid4()) for k in ("a", "b", "c")}
    cand = {k: str(uuid.uuid4()) for k in ("a", "b", "c")}
    fid = {k: str(uuid.uuid4()) for k in ("a", "b")}
    try:
        await s.execute(text("""INSERT INTO engine.runs (run_id, kind, company_id, snapshots, status)
            VALUES (CAST(:r AS uuid), 'kb', :c, '{}'::jsonb, 'running')"""), {"r": rid, "c": cid})
        for name, (cls, fp, disp) in {
            "sub": ("substantive", True, None), "cos": ("cosmetic", True, "excluded_noise"),
            "none": ("substantive", True, None), "noise": ("substantive", False, "not_in_footprint"),
            "pend": ("substantive", True, None)}.items():
            await s.execute(text("""INSERT INTO engine.change_records
                (change_id, run_id, origin, source_system, citation, rule_key, change_class, in_footprint, disposition)
                VALUES (CAST(:i AS uuid), CAST(:r AS uuid), 'kb', 'iac', :cit, 'rk', :cls, :fp, :d)"""),
                {"i": ch[name], "r": rid, "cit": f"X {name}", "cls": cls, "fp": fp, "d": disp})

        async def add_cand(key, change, doc, clause_id, path, detail, judged, skip):
            await s.execute(text("""INSERT INTO engine.candidates
                (candidate_id, run_id, change_id, clause_pk, clause_id, doc_id, match_path, path_detail,
                 judged_by, skip_reason)
                VALUES (CAST(:i AS uuid), CAST(:r AS uuid), CAST(:ch AS uuid), CAST(:pk AS uuid), :cl, :d,
                        :mp, CAST(:pd AS jsonb), :j, :sk)"""),
                {"i": cand[key], "r": rid, "ch": ch[change], "pk": pk[key], "cl": clause_id, "d": doc,
                 "mp": path, "pd": json.dumps(detail), "j": judged, "sk": skip})

        await add_cand("a", "sub", da["doc_id"], "CLA", "direct_section", [{"path": "direct_section"}], "rule", None)
        await add_cand("b", "sub", db["doc_id"], "CLB", "register_hop",
                       [{"path": "register_hop", "via_clause_id": "CLA", "link_type": "references_clause"}],
                       "llm", None)
        await add_cand("c", "none", db["doc_id"], "CLC", "direct_section", [{"path": "direct_section"}], "llm", None)
        for k, cl, doc in (("a", "CLA", da["doc_id"]), ("b", "CLB", db["doc_id"])):
            await s.execute(text("""INSERT INTO engine.findings
                (finding_id, run_id, change_id, candidate_id, clause_pk, clause_id, doc_id, citation, finding_type,
                 severity, verdict, quotes, quotes_verified, rationale, decided_by, match_path)
                VALUES (CAST(:f AS uuid), CAST(:r AS uuid), CAST(:ch AS uuid), CAST(:c AS uuid), CAST(:pk AS uuid),
                        :cl, :d, 'X sub', 'parameter_change', 'high', 'action_required', '{}'::jsonb, true,
                        'r', 'rule', :mp)"""),
                {"f": fid[k], "r": rid, "ch": ch["sub"], "c": cand[k], "pk": pk[k], "cl": cl, "d": doc,
                 "mp": "direct_section" if k == "a" else "register_hop"})
        await s.commit()

        # 'pend' change has no candidates and no disposition -> still gets one; run passes
        stats = await run_ledger(s, rid, cid)

        disp = {r["citation"]: (r["disposition"], r["disposition_reason"]) for r in (await s.execute(text(
            "SELECT citation, disposition, disposition_reason FROM engine.change_records "
            "WHERE run_id = CAST(:r AS uuid)"), {"r": rid})).mappings().all()}
        assert disp["X sub"][0] == "findings_emitted"
        assert disp["X none"] == ("no_affected_clauses", "1 candidate(s) checked, none affected")
        assert disp["X pend"][0] == "no_affected_clauses"
        assert disp["X cos"][0] == "excluded_noise" and disp["X noise"][0] == "not_in_footprint"

        fr = {r["finding_id"]: r for r in (await s.execute(text(
            "SELECT finding_id::text, propagated_from::text AS pf, route_owner, route_reviewer, route_approver "
            "FROM engine.findings WHERE run_id = CAST(:r AS uuid)"), {"r": rid})).mappings().all()}
        assert fr[fid["b"]]["pf"] == fid["a"] and fr[fid["a"]]["pf"] is None
        assert fr[fid["a"]]["route_owner"] == da["owner_id"]
        assert fr[fid["a"]]["route_approver"] == da["approver_id"]
        assert fr[fid["b"]]["route_reviewer"] == db["reviewer_id"]

        roll = {r["doc_id"]: r for r in (await s.execute(text(
            "SELECT doc_id, status, counts, reason FROM engine.doc_rollups WHERE run_id = CAST(:r AS uuid)"),
            {"r": rid})).mappings().all()}
        assert len(roll) == len(docs)
        assert roll[da["doc_id"]]["status"] == "flagged" and roll[db["doc_id"]]["status"] == "flagged"
        for d in docs[2:]:
            assert roll[d["doc_id"]]["status"] == "cleared"
            assert roll[d["doc_id"]]["reason"] == "No S2 change touches sections this document cites."
        assert roll[db["doc_id"]]["counts"]["cleared_clauses"] == 1

        assert stats["findings_non_info"] == 2 and stats["docs_flagged"] == 2
        assert stats["candidates"] == {"direct_section": 2, "register_hop": 1}
        saved = (await s.execute(text("SELECT stats FROM engine.runs WHERE run_id = CAST(:r AS uuid)"),
                                 {"r": rid})).scalar()
        assert saved["judged_rule"] == 1 and saved["judged_llm"] == 2

        # completeness violation: strip judged_by from a candidate
        await s.execute(text("UPDATE engine.candidates SET judged_by = NULL WHERE candidate_id = CAST(:i AS uuid)"),
                        {"i": cand["c"]})
        await s.commit()
        with pytest.raises(LedgerCheckError):
            await run_ledger(s, rid, cid)
    finally:
        await s.rollback()
        await s.execute(text("DELETE FROM engine.runs WHERE run_id = CAST(:r AS uuid)"), {"r": rid})
        await s.commit()


@pytest.mark.neon
async def test_ledger_real_kb_run_is_incomplete_readonly(live_session):
    """The Stage-1-only kb run has NULL dispositions; check the pure check flags them (no writes)."""
    from app.engine.ledger import _CANDS_SQL, _CHANGES_SQL, _FINDINGS_SQL, _rows
    rid = "ff75a8be-5b1c-44b4-a73d-40b3279caf7f"
    s = live_session
    changes = await _rows(s, _CHANGES_SQL, rid=rid)
    if not changes:
        pytest.skip("reference run not present")
    cands = await _rows(s, _CANDS_SQL, rid=rid)
    fnds = await _rows(s, _FINDINGS_SQL, rid=rid)
    pending = [c for c in changes if decide_disposition(c, 0, []) is not None]
    for c in pending:
        c["disposition"] = "x"
    assert check_completeness(changes, [], fnds) == []
    assert any("no disposition" in v for v in check_completeness(
        [dict(c, disposition=None) for c in pending], cands, fnds)) or not pending
