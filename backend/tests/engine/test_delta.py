import datetime as dt

from sqlalchemy import text

from app.engine.delta import (
    ShingleIndex, Stage1Result, classify_change, jaccard, persist_stage1, run_stage1,
    shingles, stage1_stats, format_in_footprint,
)
from app.engine.footprint import Footprint
from app.engine.schemas import ChangeInput

A = "The utility shall file a report with the commission within 30 days after the end of each quarter."


def _pair(s1, s2, cit="1 IAC 2-3-4", sys="iac", s1_status="approved", s2_status="approved", **kw):
    return ChangeInput(origin="kb", source_system=sys, citation=cit, s1_section_id=10, s2_section_id=20,
                       s1_text=s1, s2_text=s2, s1_status=s1_status, s2_status=s2_status, **kw)


def _fp(section=10, clauses=("c1", "c2")):
    fp = Footprint()
    fp.cited_section_ids.add(section)
    fp.clauses_by_section[section] = set(clauses)
    return fp


def test_repealed_first():
    r = classify_change(_pair(A, None, s2_status="repealed"))
    assert r.change_class == "repealed" and r.s2_text_norm is None and r.diff_segments is None
    assert r.disposition == "not_in_footprint"


def test_repealed_not_when_already_repealed():
    r = classify_change(_pair(A, A, s1_status="repealed", s2_status="repealed"))
    assert r.change_class == "cosmetic"


def test_cosmetic_and_noise_candidates_specs():
    r = classify_change(_pair(A, A.replace(" ", "  ") + "  "), footprint=_fp())
    assert r.change_class == "cosmetic" and r.disposition == "excluded_noise"
    assert r.in_footprint and r.cited_clause_count == 2 and r.noise_clause_pks == ["c1", "c2"]


def test_noise_not_in_footprint_has_no_candidates():
    r = classify_change(_pair(A, A), footprint=Footprint())
    assert r.disposition == "excluded_noise" and not r.noise_clause_pks and not r.in_footprint


def test_metadata_only_iac():
    s1 = A + " Authority: IC 8-1-1 Affected: IC 8-1-2"
    s2 = A + " Authority: IC 8-1-1 ; IC 8-1-3 Affected: IC 8-1-2"
    r = classify_change(_pair(s1, s2))
    assert r.change_class == "metadata_only"


def test_punctuation_only():
    r = classify_change(_pair(A, A.replace("quarter.", "quarter;")))
    assert r.change_class == "punctuation_only"


def test_cross_ref_only():
    base = "Each utility shall comply with {} when filing."
    r = classify_change(_pair(base.format("170 IAC 4-1-16"), base.format("170 IAC 4-1-17")))
    assert r.change_class == "cross_ref_only"


def test_cross_ref_requires_nonempty_change():
    # insertion of a plain word is substantive, not vacuously cross_ref_only
    r = classify_change(_pair(A, A.replace("30 days", "30 business days")))
    assert r.change_class == "substantive"


def test_substantive_diff_and_footprint():
    r = classify_change(_pair(A, A.replace("30", "45")), footprint=_fp())
    assert r.change_class == "substantive" and r.in_footprint and r.disposition is None
    assert any(s["op"] == "insert" and s["text"] == "45" for s in r.diff_segments)
    assert r.noise_clause_pks == []


def test_substantive_not_in_footprint():
    r = classify_change(_pair(A, A.replace("30", "45")), footprint=Footprint())
    assert r.disposition == "not_in_footprint"


def _new(cit="1 IAC 2-3-9", text_=A):
    return ChangeInput(origin="kb", source_system="iac", citation=cit, s1_section_id=None,
                       s2_section_id=99, s2_text=text_, s2_status="approved")


def test_new_section_and_review_in_rule_footprint():
    fp = Footprint()
    fp.cited_rule_keys.add("1 IAC 2-3")
    r = classify_change(_new(), footprint=fp)
    assert r.change_class == "new_section" and r.disposition == "needs_review"
    assert r.disposition_reason == "New section inside a rule your documents cover"
    assert r.s1_text_norm is None and r.diff_segments is None
    assert classify_change(_new(), footprint=Footprint()).disposition == "not_in_footprint"


def test_renumbered_via_shingles():
    old = A + " The report shall include all customer complaints received during the quarter."
    idx = ShingleIndex.from_rows(
        [{"id": 5, "source_system": "iac", "title_number": "1", "citation": "1 IAC 2-3-4", "body_text": old},
         {"id": 6, "source_system": "iac", "title_number": "1", "citation": "1 IAC 2-3-5", "body_text": "Unrelated text about other things entirely and nothing more."}],
        {99: "1"})
    r = classify_change(_new(text_=old), idx, footprint=_fp(section=5))
    assert r.change_class == "renumbered" and r.renumbered_from == "1 IAC 2-3-4" and r.s1_section_id == 5
    assert r.in_footprint and r.disposition is None
    # same citation is never a renumber source; different title neither
    idx2 = ShingleIndex.from_rows(
        [{"id": 5, "source_system": "iac", "title_number": "2", "citation": "2 IAC 2-3-4", "body_text": old}], {99: "1"})
    assert classify_change(_new(text_=old), idx2).change_class == "new_section"
    idx3 = ShingleIndex.from_rows(
        [{"id": 5, "source_system": "iac", "title_number": "1", "citation": "1 IAC 2-3-9", "body_text": old}], {99: "1"})
    assert classify_change(_new(text_=old), idx3).change_class == "new_section"


def test_shingles_and_jaccard():
    assert shingles("") == frozenset()
    assert len(shingles("a b c")) == 1
    assert len(shingles("a b c d e f")) == 2
    assert jaccard(shingles("a b c d e f"), shingles("a b c d e f")) == 1.0


def test_whatif_repeal_and_edit():
    inp = ChangeInput(origin="whatif", source_system="iac", citation="1 IAC 2-3-4", s1_section_id=10,
                      s1_text=A, s2_text=None, s1_status="approved", s2_status="repealed")
    r = classify_change(inp, footprint=_fp())
    assert r.change_class == "repealed" and r.in_footprint and r.disposition is None
    inp2 = inp.model_copy(update={"s2_text": A.replace("30", "10"), "s2_status": "approved"})
    assert classify_change(inp2, footprint=_fp()).change_class == "substantive"


def test_dates_din_and_cfr():
    s2 = A.replace("30", "45") + " (Agency; 1 IAC 2-3-4; filed Jun 3, 2025: 20250618-IR-326250285ACA)"
    r = classify_change(_pair(A, s2))
    assert r.din == "20250618-IR-326250285ACA" and r.published_date == dt.date(2025, 6, 18)
    c = _pair("Text one here now.", "Text two here now.", cit="18 CFR 35.28", sys="cfr", amendment_source="2025-06941")
    r = classify_change(c, fr_lookup={"2025-06941": (dt.date(2025, 7, 1), "fr_effective")})
    assert r.date_basis == "fr_effective" and r.rule_key == "18 CFR 35"


def test_stats():
    rs = [classify_change(_pair(A, A), footprint=_fp()), classify_change(_pair(A, A.replace("30", "9")), footprint=_fp()),
          classify_change(_pair(A, A, sys="cfr", cit="18 CFR 35.1"))]
    st = stage1_stats(rs)
    assert st["by_source"]["iac"] == {"cosmetic": 1, "substantive": 1}
    assert st["total"] == 3 and len(st["in_footprint"]) == 2
    assert format_in_footprint(st)[0].endswith("| 2")


# ---- async wrapper / persistence with fake sessions ----
class _Res:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, clause_rows=()):
        self.calls, self.clause_rows = [], list(clause_rows)

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.calls.append((sql, params))
        if "company.clauses" in sql:
            return _Res(self.clause_rows)
        return _Res([])


async def test_run_and_persist_stage1():
    inputs = [_pair(A, A), _pair(A, A.replace("30", "45"), cit="1 IAC 2-3-5")]
    sess = FakeSession([
        {"clause_pk": "11111111-1111-1111-1111-111111111111", "clause_id": "D1-001", "doc_id": "D1"},
        {"clause_pk": "22222222-2222-2222-2222-222222222222", "clause_id": "D2-001", "doc_id": "D2"}])
    fp = _fp(clauses=("11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"))
    s1 = await run_stage1(sess, "run-1", inputs, fp)
    assert [r.change_class for r in s1.results] == ["cosmetic", "substantive"]
    assert len(s1.candidates) == 2
    c = s1.candidates[0]
    assert c.skip_reason == "noise:cosmetic" and c.affected is False and c.judged_by is None
    assert c.match_path == "direct_section" and c.change_id == s1.results[0].change_id
    # one clause query only
    assert sum("company.clauses" in sql for sql, _ in sess.calls) == 1

    sess2 = FakeSession()
    await persist_stage1(sess2, "run-1", s1)
    assert "engine.change_records" in sess2.calls[0][0] and "CAST(:diff_segments AS jsonb)" in sess2.calls[0][0]
    assert len(sess2.calls[0][1]) == 2
    assert "engine.candidates" in sess2.calls[1][0] and len(sess2.calls[1][1]) == 2
    row = sess2.calls[1][1][0]
    assert row["run_id"] == "run-1" and row["affected"] is False and row["path_detail"].startswith("[")

    sess3 = FakeSession()
    await persist_stage1(sess3, "run-1", Stage1Result([], []))
    assert sess3.calls == []
