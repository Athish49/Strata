"""Tests for ``synthetic/verify_parity.py`` (task 9.3, the parity gate).

* The frozen ``HISTORY`` reconciles with ``baseline_before_v2.json`` (1,244 / 487),
  so the "historical accumulation" explanation is checked, not asserted.
* Apples-to-apples: baseline metrics are measured only through
  ``baseline_snapshot.collect`` (the task 0.1 SQL).
* Gate arithmetic at each boundary, and the two conditional acceptances: every
  condition, broken on its own, turns an accepted FAIL into an unaccepted one
  (exit 1).
* Read-only: no write SQL, no file writes, a non-read-only session is refused.
* End to end on a scratch PostgreSQL cluster (never ``DATABASE_URL``/``.env``):
  the v2-only queries run against the v2 test schema and ``main()`` exits 0.

Skips cleanly when ``backend/synthetic/`` is absent.
"""
from __future__ import annotations

import ast
import copy
import json
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
SYNTHETIC = BACKEND / "synthetic"
if not (SYNTHETIC / "verify_parity.py").is_file():
    pytest.skip("backend/synthetic/ is absent", allow_module_level=True)

from synthetic import baseline_snapshot as bs  # noqa: E402
from synthetic import verify_parity as vp  # noqa: E402

from .conftest import fresh_database  # noqa: E402

BASELINE = json.loads((SYNTHETIC / "baseline_before_v2.json").read_text())
SCHEMA_SQL = BACKEND / "tests" / "engine" / "fixtures" / "company_schema.sql"
KB_RUN = "858d3160-8c5a-4468-9021-6d0690095f54"


def post_cutover() -> dict:
    """The post-cutover production shape (task 9.2 step 4b / step 5 numbers)."""
    cur = copy.deepcopy(BASELINE)
    cur.update({
        "citations_resolved": 1119,
        "citations_resolved_by_unit_kind": {**BASELINE["citations_resolved_by_unit_kind"],
                                            "register_row": 162},
        "findings_total": 41,
        "findings_by_unit_kind": {"register_row": 26, "section": 14, "tariff_subrule": 1},
        "table_counts": {**BASELINE["table_counts"],
                         **{t: {"error": f'relation "company.{t}" does not exist'}
                            for t in vp.DROPPED_TABLES}},
        "score_reports": [],
    })
    cur["extra"] = {
        "resolved_pairs": {"narrative": 814, "register_row": 160},
        "runs": [
            {"run_id": "50d35816-ff73-4625-b82e-d133fcb06c90", "kind": "baseline",
             "status": "done", "snapshots": {}, "started_at": "t1", "findings": 0,
             "register_row": 0},
            {"run_id": KB_RUN, "kind": "kb", "status": "done",
             "snapshots": copy.deepcopy(vp.KB_SNAPSHOTS), "started_at": "t2",
             "findings": 41, "register_row": 26},
        ],
    }
    return cur


def gate(gates, name):
    return next(g for g in gates if g.name == name)


def run(cur):
    gates = vp.evaluate(BASELINE, cur, vp.HISTORY)
    return gates, vp.exit_code(gates, cur)


# ======================================================================= history
def test_frozen_history_reconciles_with_the_baseline_findings():
    """The 1,244 / 487 baseline is the sum over all 25 runs, failed run included."""
    runs = vp.HISTORY_RUNS
    assert len(runs) == len({r[0] for r in runs}) == 25
    assert sum(r[3] for r in runs) == BASELINE["findings_total"] == 1244
    assert sum(r[4] for r in runs) == BASELINE["findings_by_unit_kind"]["register_row"] == 487
    assert sum(1 for r in runs if r[2] == "failed") == 1
    assert sum(r[2] == "done" for r in runs) == BASELINE["engine_runs_by_status"]["done"]


def test_history_latest_kb_run_and_scorecards_link_to_the_baseline():
    hv = vp.history_view(vp.HISTORY, BASELINE)
    assert hv["kb_findings"] == [0, 187, 187, 7, 7, 4]
    assert hv["kb_register"] == [0, 120, 120, 4, 4, 3]
    assert hv["latest_kb"][0].startswith("0dcc125e")
    assert hv["latest_kb_score"]["matched"] == 0
    # every baseline scorecard belongs to a run in the frozen history
    ids = {r[0] for r in vp.HISTORY_RUNS}
    assert {s["run_id"] for s in BASELINE["score_reports"]} <= ids


def test_history_resolved_split_reconciles_with_the_baseline():
    meth = vp.HISTORY["register_resolved_by_method"]
    assert sum(meth.values()) == BASELINE["citations_resolved_by_unit_kind"]["register_row"]
    split = vp.HISTORY["children_split"]
    for t in ("clause_links", "clause_parameters", "term_usages"):
        assert sum(split[t].values()) == BASELINE["table_counts"][t]


def test_history_drift_reports_only_changed_keys():
    live = copy.deepcopy(vp.HISTORY)
    live["runs"] = [list(r) for r in live["runs"]]  # tuples vs lists are not drift
    assert vp.history_drift(vp.HISTORY, live) == []
    live["resolved_pairs"] = {"narrative": 814, "register_row": 168}
    (d,) = vp.history_drift(vp.HISTORY, live)
    assert d.startswith("resolved_pairs:")


# ========================================================== apples-to-apples
class FakeCursor:
    def __init__(self):
        self.sql: list[str] = []
        self.connection = self

    def rollback(self):
        pass

    def execute(self, sql):
        self.sql.append(sql)
        self._last = sql

    def fetchone(self):
        return (7,)

    def fetchall(self):
        return []


def test_baseline_metrics_come_from_baseline_snapshot_collect(monkeypatch):
    """Changing a task 0.1 query changes what verify_parity measures: it reuses the
    definitions instead of re-typing them."""
    monkeypatch.setitem(bs.QUERIES, "citations_resolved", ("SELECT 'sentinel-sql'", "scalar"))
    cur = FakeCursor()
    snap = vp.collect_current(cur)
    assert "SELECT 'sentinel-sql'" in cur.sql
    assert snap["citations_resolved"] == 7
    for key, (sql, _) in bs.QUERIES.items():
        assert sql in cur.sql, key


def test_extra_queries_never_shadow_a_baseline_metric():
    assert not set(vp.EXTRA_QUERIES) & set(bs.QUERIES)
    tree = ast.parse((SYNTHETIC / "verify_parity.py").read_text())
    consts = {n.value.strip() for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    consts |= {sql for sql, _ in vp.EXTRA_QUERIES.values()}
    for sql, _ in bs.QUERIES.values():
        assert sql not in consts  # no re-typed copy of a baseline query


# ====================================================================== verdicts
def test_post_cutover_shape_passes_with_three_accepted_exceptions():
    gates, code = run(post_cutover())
    verdicts = {g.name: g.verdict for g in gates}
    assert verdicts == {
        "citations_resolved": "FAIL (accepted)",
        "distinct_code_sections_total": "PASS",
        "register_row clauses": "PASS",
        "findings_total": "FAIL (accepted)",
        "register_row findings": "FAIL (accepted)",
        "public.code_sections": "PASS",
        "register_row largest distinct contributor": "PASS",
    }
    assert code == 0
    assert vp.overall(gates, post_cutover()) == "PASS WITH ACCEPTED EXCEPTIONS"


@pytest.mark.parametrize("value,passed", [(1156, True), (1155, False)])
def test_citations_gate_boundary(value, passed):
    cur = post_cutover()
    cur["citations_resolved"] = value
    assert gate(run(cur)[0], "citations_resolved").passed is passed


@pytest.mark.parametrize("value,passed", [(72, True), (71, False)])
def test_distinct_coverage_gate_boundary(value, passed):
    cur = post_cutover()
    cur["distinct_code_sections_total"] = value
    gates, code = run(cur)
    assert gate(gates, "distinct_code_sections_total").passed is passed
    assert code == (0 if passed else 1)


@pytest.mark.parametrize("value,passed", [(200, True), (199, False)])
def test_register_row_clauses_gate_boundary(value, passed):
    cur = post_cutover()
    cur["clauses_by_unit_kind"] = {**cur["clauses_by_unit_kind"], "register_row": value}
    gates, code = run(cur)
    assert gate(gates, "register_row clauses").verdict == ("PASS" if passed else "FAIL")
    assert code == (0 if passed else 1)


def test_code_sections_must_be_unchanged_in_both_directions():
    for v in (4602, 4604):
        cur = post_cutover()
        cur["code_sections_total"] = v
        gates, code = run(cur)
        assert gate(gates, "public.code_sections").verdict == "FAIL" and code == 1


@pytest.mark.parametrize("section", [69, 70])
def test_register_row_must_strictly_lead_distinct_coverage(section):
    cur = post_cutover()
    cur["distinct_code_sections_by_unit_kind"] = {
        **cur["distinct_code_sections_by_unit_kind"], "section": section}
    gates, code = run(cur)
    assert gate(gates, "register_row largest distinct contributor").verdict == "FAIL"
    assert code == 1


# ============================================ conditional acceptance: citations
def _citations(narrative_drop=0, register=162):
    cur = post_cutover()
    cur["citations_resolved_by_unit_kind"]["register_row"] = register
    cur["citations_resolved"] = 957 - narrative_drop + register
    return cur


def test_citations_acceptance_needs_the_transplanted_narrative_count_intact():
    gates, code = run(_citations(narrative_drop=1))  # 956 narrative
    g = gate(gates, "citations_resolved")
    assert g.verdict == "FAIL" and code == 1
    assert any("BROKEN" in n for n in g.note)


def test_citations_acceptance_needs_the_register_floor():
    gates, code = run(_citations(register=161))
    assert gate(gates, "citations_resolved").verdict == "FAIL" and code == 1


def test_citations_narrative_floor_is_derived_from_the_baseline_file():
    base = copy.deepcopy(BASELINE)
    base["citations_resolved_by_unit_kind"]["register_row"] -= 1  # narrative floor 958
    gates = vp.evaluate(base, _citations(), vp.HISTORY)
    assert gate(gates, "citations_resolved").verdict == "FAIL"


# ============================================= conditional acceptance: findings
def _kb(cur):
    return cur["extra"]["runs"][-1]


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(findings=3),                       # below the old latest kb (4)
    lambda r: r.update(register_row=2),                   # below the old latest kb (3)
    lambda r: r["snapshots"]["iac"].update(s2="2026-06-30"),  # not the same S1->S2
    lambda r: r.update(status="failed"),                  # no completed kb run
])
def test_findings_acceptance_breaks_on_each_condition(mutate):
    cur = post_cutover()
    mutate(_kb(cur))
    gates, code = run(cur)
    assert gate(gates, "findings_total").verdict == "FAIL"
    assert gate(gates, "register_row findings").verdict == "FAIL"
    assert code == 1


def test_findings_acceptance_uses_the_latest_completed_kb_run():
    cur = post_cutover()
    older = dict(_kb(cur), run_id="0" * 36, findings=1, register_row=0)
    cur["extra"]["runs"].insert(1, older)
    assert run(cur)[1] == 0  # the older, weaker run is not the one judged
    cur["extra"]["runs"].append(dict(older, run_id="f" * 36))
    assert run(cur)[1] == 1  # a newer weak run is


def test_findings_at_threshold_pass_without_acceptance():
    cur = post_cutover()
    cur["findings_total"] = 1058
    cur["findings_by_unit_kind"] = {"register_row": 400}
    gates, _ = run(cur)
    assert gate(gates, "findings_total").verdict == "PASS"
    assert gate(gates, "register_row findings").verdict == "PASS"
    cur["findings_total"] = 1057
    assert gate(run(cur)[0], "findings_total").passed is False


# ========================================================================== misc
def test_fold_doc_numbers_folds_register_documents_into_their_parent():
    assert vp.fold_doc_numbers({"RPL-A": 85, "RPL-A#register": 70, "RPL-B": 3}) == \
        {"RPL-A": 155, "RPL-B": 3}


def test_dropped_tables_are_expected_errors_but_others_make_the_run_incomplete():
    cur = post_cutover()
    assert vp.extra_errors(cur) == {}
    cur["extra"]["approval_requests_by_state"] = {"error": "column state does not exist"}
    gates, code = run(cur)
    assert vp.overall(gates, cur) == "INCOMPLETE" and code == 2


def test_soft_band_is_informational_and_does_not_change_the_exit_code():
    cur = post_cutover()
    cur["clauses_total"] = 4000
    (row,) = vp.soft_checks(BASELINE, cur)
    assert "OUTSIDE" in row[4]
    assert run(cur)[1] == 0
    cur["clauses_total"] = int(2334 * 1.35)
    assert "inside" in vp.soft_checks(BASELINE, cur)[0][4]


def test_report_renders_explanations_for_every_failed_gate():
    cur = post_cutover()
    gates = vp.evaluate(BASELINE, cur, vp.HISTORY)
    text = vp.render(BASELINE, cur, vp.HISTORY, gates, None)
    assert "[citations_resolved] FAIL (accepted)" in text
    assert "25 historical runs" in text
    assert "dropped by migration (expected)" in text
    assert "overall: PASS WITH ACCEPTED EXCEPTIONS" in text


# ===================================================================== read-only
_WRITE_SQL = re.compile(r"\b(INSERT|UPDATE|DELETE|TRUNCATE|DROP|ALTER|CREATE|GRANT|COPY)\b")


def test_script_contains_no_write_sql_and_writes_no_files():
    src = (SYNTHETIC / "verify_parity.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and \
                re.search(r"\b(SELECT|SHOW)\b", node.value):
            assert not _WRITE_SQL.search(node.value), node.value
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"write_text", "write_bytes", "mkdir", "unlink", "commit"}
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
            pytest.fail("verify_parity must not open files for writing")


def test_a_session_that_is_not_read_only_is_refused(monkeypatch):
    import psycopg2

    class Conn:
        closed = False

        def set_session(self, readonly):
            self.readonly = readonly

        def cursor(self):
            return self

        def execute(self, sql):
            assert sql == "SHOW transaction_read_only"

        def fetchone(self):
            return ("off",)

        def close(self):
            Conn.closed = True

    monkeypatch.setattr(psycopg2, "connect", lambda *a, **k: Conn())
    with pytest.raises(SystemExit, match="not read-only"):
        vp._connect_readonly("postgresql+asyncpg://u@h/db")
    assert Conn.closed


# =========================================================== scratch PostgreSQL
ENGINE_DDL = """
CREATE SCHEMA engine;
CREATE TABLE public.alembic_version (version_num text);
INSERT INTO public.alembic_version VALUES ('f7b2c91d4a08');
CREATE TABLE public.code_sections (code_section_id text PRIMARY KEY);
INSERT INTO public.code_sections SELECT g::text FROM generate_series(1, 3) g;
CREATE TABLE engine.runs (run_id uuid PRIMARY KEY, kind text, company_id text,
    scenario_id uuid, snapshots jsonb, status text, error text, stats jsonb,
    models jsonb, started_at timestamptz, finished_at timestamptz);
CREATE TABLE engine.findings (finding_id uuid PRIMARY KEY, run_id uuid, clause_pk uuid,
    clause_id text, doc_id text);
CREATE TABLE engine.score_reports (run_id uuid PRIMARY KEY, snapshot text, metrics jsonb,
    raw_stdout text, created_at timestamptz);
"""

SEED = """
INSERT INTO company.company_documents (company_id, doc_id, doc_number, current_version_id)
VALUES ('co', 'DOC-1', 'RPL-A', '11111111-1111-1111-1111-111111111111'),
       ('co', 'DOC-2', 'RPL-A#register', '22222222-2222-2222-2222-222222222222');
INSERT INTO company.document_versions (version_id, company_id, doc_id, status, version_no,
    is_current)
VALUES ('11111111-1111-1111-1111-111111111111', 'co', 'DOC-1', 'effective', 1, true),
       ('22222222-2222-2222-2222-222222222222', 'co', 'DOC-2', 'effective', 1, true);
INSERT INTO company.clauses (clause_pk, company_id, version_id, doc_id, clause_id, unit_kind,
    assessable, clause_role)
VALUES ('a0000000-0000-0000-0000-000000000001', 'co', '11111111-1111-1111-1111-111111111111',
        'DOC-1', 'DOC-1:s1', 'section', true, 'obligation'),
       ('a0000000-0000-0000-0000-000000000002', 'co', '22222222-2222-2222-2222-222222222222',
        'DOC-2', 'DOC-2:OBL-1', 'register_row', true, 'obligation');
INSERT INTO company.clause_citations (citation_pk, clause_pk, code_section_id, resolution_status)
VALUES ('c0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', '1', 'resolved'),
       ('c0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000002', '2', 'resolved'),
       ('c0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000002', '2', 'resolved');
INSERT INTO engine.runs (run_id, kind, status, snapshots, started_at) VALUES
  ('858d3160-8c5a-4468-9021-6d0690095f54', 'kb', 'done',
   '{"cfr": {"s1": "2025-01-02", "s2": "2026-10-02"}, "iac": {"s1": "2024-12-31", "s2": "2025-12-31"}}',
   now());
INSERT INTO engine.findings (finding_id, run_id, clause_pk, doc_id) VALUES
  ('f0000000-0000-0000-0000-000000000001', '858d3160-8c5a-4468-9021-6d0690095f54',
   'a0000000-0000-0000-0000-000000000002', 'DOC-2');
"""


@pytest.fixture
def v2db(scratch_pg):
    con = fresh_database(scratch_pg, "verify_parity")
    with con.cursor() as cur:
        cur.execute(SCHEMA_SQL.read_text())
        cur.execute(ENGINE_DDL)
        cur.execute(SEED)
    con.close()
    pg = scratch_pg
    return f"postgresql://postgres@/verify_parity?host={pg['host']}&port={pg['port']}"


def test_collect_current_runs_every_v2_query_on_the_v2_schema(v2db):
    conn, cur = vp._connect_readonly(v2db)
    try:
        snap = vp.collect_current(cur)
        with pytest.raises(Exception, match="read-only"):
            cur.execute("CREATE TABLE public.should_not_exist (x int)")
    finally:
        conn.close()
    assert vp.extra_errors(snap) == {}
    ex = snap["extra"]
    assert ex["alembic_version"] == "f7b2c91d4a08"
    assert ex["clauses_by_doc_number"] == {"RPL-A": 1, "RPL-A#register": 1}
    assert ex["findings_by_doc_number"] == {"RPL-A#register": 1}
    assert ex["resolved_pairs"] == {"narrative": 1, "register_row": 1}  # dup row counted once
    assert ex["clauses_outside_current_version"] == 0
    (run_row,) = ex["runs"]
    assert (run_row["findings"], run_row["register_row"]) == (1, 1)
    assert run_row["snapshots"] == vp.KB_SNAPSHOTS
    assert snap["citations_resolved"] == 3
    assert {t for t, v in snap["table_counts"].items() if isinstance(v, dict)} == \
        set(vp.DROPPED_TABLES)


def test_main_end_to_end_against_scratch_is_read_only(v2db, monkeypatch, capsys):
    import psycopg2

    monkeypatch.setenv("DATABASE_URL", v2db)
    con = psycopg2.connect(v2db)
    with con.cursor() as c:
        c.execute("SELECT count(*) FROM company.clauses")
        before = c.fetchone()[0]
    code = vp.main([])
    out = capsys.readouterr().out
    assert "=== Task 9.3 parity report" in out
    assert "overall: FAIL" in out and code == 1  # a 2-clause toy is far below the baseline
    with con.cursor() as c:
        c.execute("SELECT count(*) FROM company.clauses")
        assert c.fetchone()[0] == before
    con.close()
