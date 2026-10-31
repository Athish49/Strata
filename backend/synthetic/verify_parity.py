"""Task 9.3 — parity gate: the post-cutover database vs. the pre-v2 baseline.

Read-only. Writes nothing (no file, no row). Prints a per-metric report and exits
0 when every hard gate passes or each failure is explained and its acceptance
condition still holds, 1 otherwise, 2 when a v2-specific query could not run.

How the comparison stays apples-to-apples: every metric that has a baseline is
re-measured with ``baseline_snapshot.collect`` — the exact SQL that produced
``baseline_before_v2.json`` (task 0.1) — never a re-typed copy of it. Queries
added here (``EXTRA_QUERIES``) are only for things the baseline could not
express: correlation through ``doc_number``, per-run findings, and the v2-only
tables.

Two hard gates are known to fail and are accepted *conditionally* (the condition
is re-checked on every run, so a later real regression is not hidden behind an
old explanation):

* ``citations_resolved`` — the narrative documents' clauses were transplanted
  from v1 (task 9.1d), so their resolved count must equal the baseline's own
  non-register count (derived from the baseline file); the three registers were
  re-ingested by the v2 pipeline, which resolves 162 (task 9.1 rehearsal, 9.2
  step 4b). v1's register figure (327) double-counted rows: see ``HISTORY``.
* ``findings_total`` / ``register_row findings`` — the baseline's 1,244 / 487 are
  ``count(*)`` summed over 25 development runs, not one run. Accepted when the
  latest post-cutover ``kb`` run used the same snapshots as the historical ``kb``
  runs and produced at least as many findings (total and register_row) as the
  old system's latest ``kb`` run.

``HISTORY`` was measured read-only on the pre-cutover Neon backup branch
(2026-10-31). Pass ``--history-url <that branch>`` to re-derive it live instead;
any drift from the frozen copy is reported.

Usage:
    cd backend && .venv/bin/python synthetic/verify_parity.py
    cd backend && .venv/bin/python synthetic/verify_parity.py --history-url "$BRANCH_URL"
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from synthetic import baseline_snapshot as bs  # noqa: E402  (the task 0.1 queries)

DEFAULT_BASELINE = HERE / "baseline_before_v2.json"
REGISTER_SUFFIX = "#register"
REGISTER = "register_row"

# Tables task 3.1 dropped (they held 0 rows at baseline). An error querying them
# post-cutover is the expected outcome, not a failure.
DROPPED_TABLES = frozenset(bs.EXPECT_ZERO)

# ---------------------------------------------------------------- frozen history
# Measured read-only on the pre-cutover Neon backup branch (alembic e5a1c7d9b304),
# 2026-10-31. One row per engine run, oldest first:
# (run_id, kind, status, findings, register_row findings).
HISTORY_RUNS: list[tuple[str, str, str, int, int]] = [
    ("ff75a8be-5b1c-44b4-a73d-40b3279caf7f", "kb", "done", 0, 0),
    ("eaae663f-fd4c-4c14-82ae-a6179eac05e7", "baseline", "done", 0, 0),
    ("61237079-7eea-45bb-985e-89bcdebeaaaa", "kb", "done", 187, 120),
    ("53dd08ab-7db7-4476-9ede-ab6496c15ec8", "baseline", "done", 0, 0),
    ("76622053-3d17-4e55-b551-df60ff428fbd", "kb", "done", 187, 120),
    ("45b7d2c1-6b97-4a60-8996-187975ebf74b", "kb", "done", 7, 4),
    ("e792cf7c-00f6-43a9-8a2d-8bc48430b000", "whatif", "done", 52, 29),
    ("e4ff6043-6a12-41a8-a791-f12eb32b7681", "whatif", "done", 66, 11),
    ("c759324c-c503-408b-b2ab-14faf8e7a11c", "whatif", "done", 93, 4),
    ("d5233b07-5b5d-482c-ab02-2ed971588f9b", "whatif", "done", 0, 0),
    ("d4e28fc9-df4a-4b80-b2ee-bebc418d8ba9", "whatif", "done", 62, 32),
    ("3bcc15b1-d29a-4685-8c15-c92c8f5a506b", "whatif", "failed", 76, 11),
    ("00d62750-34fc-4359-95ec-6cb3c0e3cac0", "whatif", "done", 0, 0),
    ("0c9a2714-7c06-4d3e-ad03-717651f9fafa", "whatif", "done", 76, 11),
    ("bfdb6aa9-8439-41cb-8395-2c126dc429bf", "whatif", "done", 0, 0),
    ("ad4bf623-67d4-4cfe-9050-404209da8487", "whatif", "done", 62, 32),
    ("77777151-14e4-44c2-b113-87ba27affe81", "whatif", "done", 20, 8),
    ("58cc6af2-a96f-4dfd-a57c-e94eb4e81bd8", "whatif", "done", 20, 0),
    ("2cb0b3db-3f1a-4dc9-accf-cd682beebaa8", "whatif", "done", 0, 0),
    ("09189501-b58f-4944-9440-8316db27f83e", "whatif", "done", 93, 4),
    ("9ad3a671-b91d-4401-bc25-cf70749581dd", "whatif", "done", 108, 46),
    ("7b4e0646-6867-4541-8f94-1156c0615e88", "whatif", "done", 109, 46),
    ("18ee057d-f1bf-4f3f-92a7-498a676d0787", "whatif", "done", 15, 2),
    ("05b50712-79df-4c4e-bdb3-c84f31e189ec", "kb", "done", 7, 4),
    ("0dcc125e-6da6-419f-beb1-8c347e4fb2d4", "kb", "done", 4, 3),
]
# Every historical kb run compared these snapshots (S1 -> S2).
KB_SNAPSHOTS = {"cfr": {"s1": "2025-01-02", "s2": "2026-10-02"},
                "iac": {"s1": "2024-12-31", "s2": "2025-12-31"}}

HISTORY: dict[str, Any] = {
    "runs": HISTORY_RUNS,
    "kb_snapshots": KB_SNAPSHOTS,
    # distinct (clause_pk, code_section_id) among resolved citation rows
    "resolved_pairs": {"narrative": 814, REGISTER: 169},
    # v1 register_row resolved citation rows by extraction_method: the NULL rows came
    # from the v1 citation-column path, 'register_cell_parse' re-parsed every cell
    # (notes/description included), duplicating rows: 327 rows, 169 distinct pairs.
    "register_resolved_by_method": {"register_cell_parse": 216, "<null>": 111},
    # child rows by the side of their clause (links: the source clause)
    "children_split": {"clause_links": {"narrative": 2690, REGISTER: 1985},
                       "clause_parameters": {"narrative": 2420, REGISTER: 528},
                       "term_usages": {"narrative": 643, REGISTER: 50}},
}

# v2 register pipeline's resolved count for the three registers: task 9.1's
# rehearsal (after the multi-citation fix) and 9.2 step 4b both measured 162.
ACCEPTED_REGISTER_RESOLVED = 162

# --------------------------------------------------------------- v2-only queries
_DOC_JOIN = ("JOIN company.company_documents d "
             "ON d.company_id = c.company_id AND d.doc_id = c.doc_id")

EXTRA_QUERIES: dict[str, tuple[str, str]] = {
    "alembic_version": ("SELECT version_num FROM public.alembic_version", "scalar"),
    "clauses_by_doc_number": (
        f"SELECT d.doc_number, count(*) FROM company.clauses c {_DOC_JOIN} "
        "GROUP BY 1 ORDER BY 1", "rows"),
    "findings_by_doc_number": (
        "SELECT coalesce(d.doc_number, f.doc_id, '<no doc>'), count(*) FROM engine.findings f "
        "LEFT JOIN company.clauses c ON c.clause_pk = f.clause_pk "
        "LEFT JOIN company.company_documents d "
        "ON d.company_id = c.company_id AND d.doc_id = c.doc_id GROUP BY 1 ORDER BY 1", "rows"),
    "document_scope_by_doc_number": (
        "SELECT d.doc_number, count(*) FROM company.document_scope c "
        f"{_DOC_JOIN} GROUP BY 1 ORDER BY 1", "rows"),
    "resolved_pairs": (
        "SELECT CASE WHEN c.unit_kind = 'register_row' THEN 'register_row' ELSE 'narrative' END, "
        "count(DISTINCT (cc.clause_pk, cc.code_section_id)) FROM company.clause_citations cc "
        "JOIN company.clauses c ON c.clause_pk = cc.clause_pk "
        "WHERE cc.code_section_id IS NOT NULL GROUP BY 1", "rows"),
    "clauses_outside_current_version": (
        f"SELECT count(*) FROM company.clauses c {_DOC_JOIN} "
        "WHERE c.version_id IS DISTINCT FROM d.current_version_id", "scalar"),
    "document_versions_by_status": (
        "SELECT status, count(*) FROM company.document_versions GROUP BY 1", "rows"),
    "approval_requests_by_state": (
        "SELECT state, count(*) FROM company.approval_requests GROUP BY 1", "rows"),
    "approval_steps_by_decision": (
        "SELECT coalesce(decision, '<pending>'), count(*) FROM company.approval_steps GROUP BY 1",
        "rows"),
    "ingest_jobs_by_state": (
        "SELECT state, count(*) FROM company.ingest_jobs GROUP BY 1", "rows"),
    "role_assignments_by_role": (
        "SELECT role, count(*) FROM company.document_role_assignments GROUP BY 1", "rows"),
}

_SIDE = "CASE WHEN c.unit_kind = 'register_row' THEN 'register_row' ELSE 'narrative' END"
CHILDREN_SPLIT_SQL = {
    "clause_links": f"SELECT {_SIDE}, count(*) FROM company.clause_links x "
                    "JOIN company.clauses c ON c.clause_pk = x.from_clause_pk GROUP BY 1",
    "clause_parameters": f"SELECT {_SIDE}, count(*) FROM company.clause_parameters x "
                         "JOIN company.clauses c ON c.clause_pk = x.clause_pk GROUP BY 1",
    "term_usages": f"SELECT {_SIDE}, count(*) FROM company.term_usages x "
                   "JOIN company.clauses c ON c.clause_pk = x.clause_pk GROUP BY 1",
}

RUNS_SQL = """
SELECT r.run_id::text, r.kind, r.status, r.snapshots, r.started_at,
       count(f.finding_id),
       count(f.finding_id) FILTER (WHERE c.unit_kind = 'register_row')
FROM engine.runs r
LEFT JOIN engine.findings f ON f.run_id = r.run_id
LEFT JOIN company.clauses c ON c.clause_pk = f.clause_pk
GROUP BY 1, 2, 3, 4, 5
ORDER BY r.started_at NULLS FIRST, 1
"""

TABLES_SQL = ("SELECT table_schema, table_name FROM information_schema.tables "
              "WHERE table_schema IN ('company', 'engine') AND table_type = 'BASE TABLE' "
              "ORDER BY 1, 2")

HISTORY_RESOLVED_BY_METHOD_SQL = (
    "SELECT coalesce(cc.extraction_method, '<null>'), count(cc.code_section_id) "
    "FROM company.clause_citations cc JOIN company.clauses c ON c.clause_pk = cc.clause_pk "
    "WHERE c.unit_kind = 'register_row' GROUP BY 1")


# ======================================================================= collect
def _run(cur, sql: str, kind: str):
    try:
        cur.execute(sql)
        if kind == "scalar":
            return cur.fetchone()[0]
        return {str(r[0]): r[1] for r in cur.fetchall()}
    except Exception as exc:  # a query that cannot run is data, as in task 0.1
        cur.connection.rollback()
        return {"error": str(exc).strip().splitlines()[0]}


def collect_runs(cur) -> list[dict]:
    cur.execute(RUNS_SQL)
    return [{"run_id": r[0], "kind": r[1], "status": r[2], "snapshots": r[3],
             "started_at": str(r[4]), "findings": r[5], REGISTER: r[6]}
            for r in cur.fetchall()]


def collect_current(cur) -> dict:
    """The task 0.1 capture (same SQL) plus the v2-only extras."""
    snap = bs.collect(cur)
    extra = {k: _run(cur, sql, kind) for k, (sql, kind) in EXTRA_QUERIES.items()}
    try:
        extra["runs"] = collect_runs(cur)
    except Exception as exc:
        cur.connection.rollback()
        extra["runs"] = {"error": str(exc).strip().splitlines()[0]}
    try:
        cur.execute(TABLES_SQL)
        tables = [f"{s}.{t}" for s, t in cur.fetchall()]
        extra["table_rows"] = {t: _run(cur, f"SELECT count(*) FROM {t}", "scalar") for t in tables}
    except Exception as exc:
        cur.connection.rollback()
        extra["table_rows"] = {"error": str(exc).strip().splitlines()[0]}
    extra["children_split"] = {t: _run(cur, q, "rows") for t, q in CHILDREN_SPLIT_SQL.items()}
    snap["extra"] = extra
    return snap


def collect_history(cur) -> dict:
    """Re-derive ``HISTORY`` from a pre-v2 database (the backup branch)."""
    runs = collect_runs(cur)
    kb_snaps = [r["snapshots"] for r in runs if r["kind"] == "kb"]
    return {
        "runs": [(r["run_id"], r["kind"], r["status"], r["findings"], r[REGISTER]) for r in runs],
        "kb_snapshots": kb_snaps[0] if kb_snaps and all(s == kb_snaps[0] for s in kb_snaps)
        else {"error": f"kb runs disagree on snapshots: {kb_snaps}"},
        "resolved_pairs": _run(cur, EXTRA_QUERIES["resolved_pairs"][0], "rows"),
        "register_resolved_by_method": _run(cur, HISTORY_RESOLVED_BY_METHOD_SQL, "rows"),
        "children_split": {t: _run(cur, q, "rows") for t, q in CHILDREN_SPLIT_SQL.items()},
    }


def history_drift(frozen: dict, live: dict) -> list[str]:
    def norm(v):
        return json.loads(json.dumps(v, default=str))
    return [f"{k}: frozen={norm(frozen[k])} live={norm(live.get(k))}"
            for k in frozen if norm(frozen[k]) != norm(live.get(k))]


# ====================================================================== evaluate
@dataclass
class Gate:
    name: str
    baseline: Any
    current: Any
    threshold: str
    passed: bool
    accepted: bool | None = None   # None: no acceptance case exists for this gate
    note: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if self.passed:
            return "PASS"
        if self.accepted:
            return "FAIL (accepted)"
        return "FAIL"

    @property
    def ok(self) -> bool:
        return self.passed or bool(self.accepted)


def _num(v) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _ratio_gate(name, base, cur, ratio) -> Gate:
    b, c = _num(base), _num(cur)
    need = math.ceil(ratio * b) if b is not None else None
    ok = b is not None and c is not None and c >= ratio * b
    return Gate(name, base, cur, f">= {ratio:.0%} of baseline (>= {need})", ok)


def _kind(d: Any, k: str) -> int:
    return d.get(k, 0) if isinstance(d, dict) and "error" not in d else 0


def history_view(history: dict, baseline: dict) -> dict:
    """Summaries of the historical runs that the findings gates are judged against."""
    runs = history["runs"]
    kb = [r for r in runs if r[1] == "kb" and r[2] == "done"]
    scores = {s["run_id"]: s["metrics"] for s in baseline.get("score_reports", [])
              if isinstance(s, dict)}
    latest = kb[-1] if kb else None
    return {
        "n_runs": len(runs),
        "by_kind": {k: sum(1 for r in runs if r[1] == k) for k in sorted({r[1] for r in runs})},
        "sum_findings": sum(r[3] for r in runs),
        "sum_register": sum(r[4] for r in runs),
        "kb_findings": [r[3] for r in kb],
        "kb_register": [r[4] for r in kb],
        "latest_kb": latest,
        "latest_kb_score": scores.get(latest[0]) if latest else None,
    }


def score_line(m: dict | None) -> str:
    """One-line scorecard (engine.score_reports.metrics) summary."""
    if not m:
        return "no scorecard"
    if "baseline_check" in m:
        return f"scorecard baseline_check={m['baseline_check']}"
    return (f"scorecard {m.get('overall')} matched={m.get('matched')}/"
            f"{m.get('expected_non_informational')} precision={m.get('precision')} "
            f"recall={m.get('recall')} fp_rate={m.get('fp_rate_must_not_flag')} "
            f"routing={m.get('routing_accuracy')}")


def latest_current_kb(snap: dict) -> dict | None:
    runs = snap.get("extra", {}).get("runs")
    if not isinstance(runs, list):
        return None
    kb = [r for r in runs if r["kind"] == "kb" and r["status"] == "done"]
    return kb[-1] if kb else None


def evaluate(baseline: dict, cur: dict, history: dict) -> list[Gate]:
    gates: list[Gate] = []

    # --- resolved citations ------------------------------------------------
    g = _ratio_gate("citations_resolved", baseline["citations_resolved"],
                    cur["citations_resolved"], 0.90)
    b_reg = _kind(baseline["citations_resolved_by_unit_kind"], REGISTER)
    b_narr = baseline["citations_resolved"] - b_reg
    c_by = cur["citations_resolved_by_unit_kind"]
    c_reg = _kind(c_by, REGISTER)
    c_narr = (cur["citations_resolved"] - c_reg) if _num(cur["citations_resolved"]) is not None else 0
    pairs_b = history["resolved_pairs"]
    pairs_c = cur.get("extra", {}).get("resolved_pairs", {})
    if not g.passed:
        g.accepted = c_narr >= b_narr and c_reg >= ACCEPTED_REGISTER_RESOLVED
    g.note += [
        f"narrative (non-register) resolved: baseline {b_narr}, now {c_narr} "
        f"(transplanted from v1; must not drop: {'holds' if c_narr >= b_narr else 'BROKEN'})",
        f"register_row resolved: baseline {b_reg}, now {c_reg} "
        f"(v2 register pipeline; accepted floor {ACCEPTED_REGISTER_RESOLVED}: "
        f"{'holds' if c_reg >= ACCEPTED_REGISTER_RESOLVED else 'BROKEN'})",
    ]
    if isinstance(pairs_c, dict) and "error" not in pairs_c:
        tb = sum(pairs_b.values())
        tc = sum(pairs_c.values())
        g.note.append(
            f"distinct resolved (clause, code_section) pairs: baseline {tb} "
            f"(narrative {pairs_b.get('narrative')}, register {pairs_b.get(REGISTER)}), "
            f"now {tc} (narrative {pairs_c.get('narrative')}, register {pairs_c.get(REGISTER)}) "
            f"= {tc / tb:.1%} of baseline")
    meth = history["register_resolved_by_method"]
    g.note.append(
        f"v1's {b_reg} register resolved rows = {meth.get('<null>')} (citation-column path) + "
        f"{meth.get('register_cell_parse')} ('register_cell_parse', which re-parsed every cell "
        f"incl. notes/description) over only {pairs_b.get(REGISTER)} distinct pairs: duplicated "
        "rows plus incidental mentions in free-text cells, which v2 (citation-role columns only) "
        "does not extract")
    gates.append(g)

    # --- distinct code_section coverage -------------------------------------
    gates.append(_ratio_gate("distinct_code_sections_total",
                             baseline["distinct_code_sections_total"],
                             cur["distinct_code_sections_total"], 0.95))

    # --- register rows -------------------------------------------------------
    rr = _kind(cur["clauses_by_unit_kind"], REGISTER)
    gates.append(Gate("register_row clauses", _kind(baseline["clauses_by_unit_kind"], REGISTER),
                      rr, ">= 200", rr >= 200))

    # --- findings (two gates, one shared acceptance condition) ---------------
    hv = history_view(history, baseline)
    latest = latest_current_kb(cur)
    old = hv["latest_kb"]
    same_snaps = latest is not None and latest["snapshots"] == history["kb_snapshots"]
    total_ok = latest is not None and old is not None and latest["findings"] >= old[3]
    reg_ok = latest is not None and old is not None and latest[REGISTER] >= old[4]
    accept = same_snaps and total_ok and reg_ok
    evidence = [
        f"baseline {baseline['findings_total']} / register_row "
        f"{_kind(baseline['findings_by_unit_kind'], REGISTER)} = count(*) summed over "
        f"{hv['n_runs']} historical runs {hv['by_kind']} (frozen history sums to "
        f"{hv['sum_findings']} / {hv['sum_register']}; the failed run is included)",
        f"historical kb runs (same S1->S2 snapshots), oldest first: findings {hv['kb_findings']}, "
        f"register_row {hv['kb_register']}",
    ]
    if old:
        evidence.append(f"old system's latest kb run {old[0][:8]}: {old[3]} findings "
                        f"({old[4]} register_row); {score_line(hv['latest_kb_score'])}")
    if latest:
        cur_scores = {s["run_id"]: s["metrics"] for s in cur.get("score_reports", [])
                      if isinstance(s, dict)}
        evidence.append(
            f"post-cutover latest kb run {latest['run_id'][:8]}: {latest['findings']} findings "
            f"({latest[REGISTER]} register_row); snapshots "
            f"{'identical to' if same_snaps else 'DIFFER from'} the historical kb runs; "
            f"{score_line(cur_scores.get(latest['run_id']))}")
    else:
        evidence.append("post-cutover: no completed kb run found")
    evidence.append(
        "acceptance (single run vs single run): latest kb >= old latest kb on total "
        f"({'holds' if total_ok else 'BROKEN'}) and register_row "
        f"({'holds' if reg_ok else 'BROKEN'}), same snapshots "
        f"({'holds' if same_snaps else 'BROKEN'})")

    g = _ratio_gate("findings_total", baseline["findings_total"], cur["findings_total"], 0.85)
    if not g.passed:
        g.accepted = accept
    g.note += evidence
    gates.append(g)

    fr = _kind(cur["findings_by_unit_kind"], REGISTER)
    g = Gate("register_row findings", _kind(baseline["findings_by_unit_kind"], REGISTER), fr,
             ">= 400", fr >= 400)
    if not g.passed:
        g.accepted = accept
        g.note.append("same evidence and acceptance condition as findings_total")
    gates.append(g)

    # --- KB untouched --------------------------------------------------------
    b, c = baseline["code_sections_total"], cur["code_sections_total"]
    gates.append(Gate("public.code_sections", b, c, f"== {b} (unchanged)", c == b))

    # --- register decision held ---------------------------------------------
    d = cur["distinct_code_sections_by_unit_kind"]
    d = d if isinstance(d, dict) and "error" not in d else {}
    reg = d.get(REGISTER, 0)
    others = {k: v for k, v in d.items() if k != REGISTER}
    runner = max(others.items(), key=lambda kv: kv[1]) if others else ("-", 0)
    gates.append(Gate("register_row largest distinct contributor",
                      _kind(baseline["distinct_code_sections_by_unit_kind"], REGISTER), reg,
                      f"strictly > every other unit_kind (next: {runner[0]} {runner[1]})",
                      bool(d) and reg > runner[1]))
    return gates


# ------------------------------------------------------------- soft / info rows
def _delta(b, c) -> str:
    if _num(b) is None or _num(c) is None:
        return "n/a"
    if b == 0:
        return f"{c - b:+d}"
    return f"{c - b:+d} ({(c - b) / b:+.1%})"


def fold_doc_numbers(by_doc_number: dict) -> dict:
    """v1 kept register rows under their parent doc; v2 gives each register its own
    document ``<RPL id>#register``. Fold them back to compare per document."""
    out: dict[str, int] = {}
    for k, v in by_doc_number.items():
        base = k[: -len(REGISTER_SUFFIX)] if k.endswith(REGISTER_SUFFIX) else k
        out[base] = out.get(base, 0) + v
    return out


def soft_checks(baseline: dict, cur: dict) -> list[tuple[str, Any, Any, str, str]]:
    """(metric, baseline, current, delta, verdict) for the soft/informational band."""
    rows = []
    b, c = baseline["clauses_total"], cur["clauses_total"]
    inside = _num(c) is not None and abs(c - b) <= 0.35 * b
    rows.append(("clauses_total", b, c, _delta(b, c),
                 "inside ±35%" if inside else "OUTSIDE ±35% — investigate"))
    return rows


def per_key_rows(b: dict, c: dict) -> list[tuple[str, Any, Any, str]]:
    b = b if isinstance(b, dict) and "error" not in b else {}
    c = c if isinstance(c, dict) and "error" not in c else {}
    keys = sorted(set(b) | set(c), key=lambda k: (-(b.get(k) or 0), k))
    return [(k, b.get(k, 0), c.get(k, 0), _delta(b.get(k, 0), c.get(k, 0))) for k in keys]


# ========================================================================= print
def _table(rows, headers) -> list[str]:
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)] if rows else \
        [len(h) for h in headers]
    fmt = "  ".join("{:<%d}" % w for w in widths)
    out = [fmt.format(*headers), fmt.format(*("-" * w for w in widths))]
    out += [fmt.format(*(str(x) for x in r)) for r in rows]
    return ["  " + line for line in out]


def render(baseline: dict, cur: dict, history: dict, gates: list[Gate],
           drift: list[str] | None) -> str:
    L: list[str] = []
    ex = cur.get("extra", {})
    L.append("=== Task 9.3 parity report: post-cutover database vs baseline_before_v2.json ===")
    L.append(f"  baseline captured_at  {baseline.get('captured_at')} (schema {baseline.get('schema_version')})")
    L.append(f"  current alembic       {ex.get('alembic_version')}")
    L.append(f"  history source        {'live --history-url' if drift is not None else 'frozen (backup branch, 2026-10-31)'}")
    if drift:
        L.append("  HISTORY DRIFT vs frozen copy:")
        L += [f"    {d}" for d in drift]
    elif drift is not None:
        L.append("  live history matches the frozen copy exactly (0 differences)")

    L.append("\n--- Hard gates ---")
    L += _table([(g.name, g.baseline, g.current, _delta(g.baseline, g.current), g.threshold,
                  g.verdict) for g in gates],
                ("metric", "baseline", "current", "delta", "gate", "verdict"))
    for g in gates:
        if g.note and not g.passed:
            L.append(f"\n  [{g.name}] {g.verdict}")
            L += [f"    - {n}" for n in g.note]

    L.append("\n--- Soft / informational: segmentation-derived ---")
    L += _table(soft_checks(baseline, cur), ("metric", "baseline", "current", "delta", "band"))
    L.append("\n  clauses by unit_kind (form_field/appendix kept: the 12 narrative documents "
             "were transplanted from v1, task 9.1d)")
    L += _table(per_key_rows(baseline["clauses_by_unit_kind"], cur["clauses_by_unit_kind"]),
                ("unit_kind", "baseline", "current", "delta"))

    L.append("\n  clauses per document, correlated by doc_number (clause_id/doc_id are "
             "system-derived in v2; '#register' documents folded into their parent)")
    by_dn = ex.get("clauses_by_doc_number", {})
    folded = fold_doc_numbers(by_dn) if isinstance(by_dn, dict) and "error" not in by_dn else {}
    rows = per_key_rows(baseline["clauses_by_doc"], folded)
    L += _table(rows, ("doc_number", "baseline", "current", "delta"))
    mism = [r[0] for r in rows if r[1] != r[2]]
    L.append(f"  -> {len(rows) - len(mism)}/{len(rows)} documents identical"
             + (f"; differ: {mism}" if mism else ""))

    L.append("\n--- Informational: other baseline metrics (same task 0.1 SQL) ---")
    scal = [(k, baseline.get(k), cur.get(k), _delta(baseline.get(k), cur.get(k)))
            for k in ("citations_total", "document_scope_rows", "documents_total",
                      "document_versions_total")]
    for t in bs.TABLE_COUNTS:
        bv, cv = baseline["table_counts"].get(t), cur["table_counts"].get(t)
        if t in DROPPED_TABLES and isinstance(cv, dict):
            cv = "dropped by migration (expected)"
        scal.append((f"table_counts.{t}", bv, cv, _delta(bv, cv)))
    L += _table(scal, ("metric", "baseline", "current", "delta"))
    split_c = ex.get("children_split", {})
    L.append("\n  child rows split by their clause's side (narrative = the 12 transplanted "
             "documents; register_row = the 3 registers, re-ingested by the v2 pipeline)")
    split_rows = []
    for t, b_split in history.get("children_split", {}).items():
        c_split = split_c.get(t, {})
        c_split = c_split if isinstance(c_split, dict) and "error" not in c_split else {}
        for side in ("narrative", REGISTER):
            bv, cv = b_split.get(side, 0), c_split.get(side, 0)
            split_rows.append((f"{t} [{side}]", bv, cv, _delta(bv, cv)))
    L += _table(split_rows, ("metric", "baseline", "current", "delta"))
    for title, key in (("citations by resolution_status", "citations_by_status"),
                       ("resolved citations by unit_kind", "citations_resolved_by_unit_kind"),
                       ("distinct code_sections by unit_kind", "distinct_code_sections_by_unit_kind"),
                       ("findings by unit_kind (all runs)", "findings_by_unit_kind")):
        L.append(f"\n  {title}")
        L += _table(per_key_rows(baseline[key], cur[key]), ("key", "baseline", "current", "delta"))
    L.append("\n  document_scope per document (folded by doc_number)")
    sdn = ex.get("document_scope_by_doc_number", {})
    if isinstance(sdn, dict) and "error" not in sdn:
        narr = sum(v for k, v in sdn.items() if not k.endswith(REGISTER_SUFFIX))
        reg = sum(v for k, v in sdn.items() if k.endswith(REGISTER_SUFFIX))
        L.append(f"    narrative documents {narr} (baseline total {baseline['document_scope_rows']}), "
                 f"'#register' documents {reg} (new: registers are their own documents)")
    L.append("\n  findings per document (folded by doc_number, all runs)")
    fdn = ex.get("findings_by_doc_number", {})
    fold_f = fold_doc_numbers(fdn) if isinstance(fdn, dict) and "error" not in fdn else {}
    L += _table(per_key_rows(baseline["findings_by_doc"], fold_f),
                ("doc_number", "baseline", "current", "delta"))

    L.append("\n--- New metrics (no baseline) ---")
    for key in ("document_versions_by_status", "approval_requests_by_state",
                "approval_steps_by_decision", "ingest_jobs_by_state", "role_assignments_by_role"):
        L.append(f"  {key:30s} {ex.get(key)}")
    L.append(f"  {'clauses_outside_current_version':30s} {ex.get('clauses_outside_current_version')}")
    runs = ex.get("runs")
    if isinstance(runs, list):
        scores = {s["run_id"]: s["metrics"] for s in cur.get("score_reports", [])
                  if isinstance(s, dict)}
        L.append("  engine runs:")
        for r in runs:
            score = score_line(scores.get(r["run_id"]))
            L.append(f"    {r['run_id'][:8]} {r['kind']:8s} {r['status']:6s} "
                     f"findings={r['findings']} register_row={r[REGISTER]}  {score}")
    tr = ex.get("table_rows")
    if isinstance(tr, dict) and "error" not in tr:
        known = {f"company.{t}" for t in bs.TABLE_COUNTS} | {
            "company.clauses", "company.clause_citations", "company.document_scope",
            "company.company_documents", "company.document_versions", "engine.findings",
            "engine.runs", "engine.score_reports"}
        L.append("  row counts of tables not covered above:")
        L += [f"    {t:40s} {n}" for t, n in tr.items() if t not in known]

    errs = extra_errors(cur)
    L.append("\n--- Summary ---")
    failed = [g for g in gates if not g.passed]
    L.append(f"  hard gates: {sum(g.passed for g in gates)}/{len(gates)} pass; "
             f"{sum(1 for g in failed if g.accepted)} failed-and-accepted; "
             f"{sum(1 for g in failed if not g.accepted)} failed-unaccepted")
    if errs:
        L.append(f"  QUERY ERRORS: {errs}")
    L.append(f"  overall: {overall(gates, cur)}")
    return "\n".join(L)


def extra_errors(cur: dict) -> dict:
    """Errors in queries that must run post-cutover (dropped tables excluded)."""
    errs = {}
    for k, v in cur.items():
        if isinstance(v, dict) and "error" in v:
            errs[k] = v["error"]
    for t, v in cur.get("table_counts", {}).items():
        if isinstance(v, dict) and t not in DROPPED_TABLES:
            errs[f"table_counts.{t}"] = v["error"]
    for k, v in cur.get("extra", {}).items():
        if isinstance(v, dict) and "error" in v:
            errs[f"extra.{k}"] = v["error"]
    return errs


def overall(gates: list[Gate], cur: dict) -> str:
    if extra_errors(cur):
        return "INCOMPLETE"
    if all(g.passed for g in gates):
        return "PASS"
    if all(g.ok for g in gates):
        return "PASS WITH ACCEPTED EXCEPTIONS"
    return "FAIL"


def exit_code(gates: list[Gate], cur: dict) -> int:
    return {"PASS": 0, "PASS WITH ACCEPTED EXCEPTIONS": 0, "FAIL": 1,
            "INCOMPLETE": 2}[overall(gates, cur)]


# ========================================================================== main
def _connect_readonly(url: str):
    import psycopg2

    conn = psycopg2.connect(re.sub(r"^postgresql\+\w+://", "postgresql://", url))
    conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute("SHOW transaction_read_only")
    if cur.fetchone()[0] != "on":
        conn.close()
        raise SystemExit("refusing to continue: session is not read-only")
    return conn, cur


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Task 9.3 parity gate (read-only)")
    ap.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    ap.add_argument("--history-url", help="pre-v2 backup database to re-derive HISTORY from")
    args = ap.parse_args(argv)

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    history, drift = HISTORY, None
    if args.history_url:
        conn, c = _connect_readonly(args.history_url)
        try:
            live = collect_history(c)
        finally:
            conn.close()
        drift = history_drift(HISTORY, live)
        history = live

    conn, c = _connect_readonly(bs._dsn())
    try:
        current = collect_current(c)
    finally:
        conn.close()

    gates = evaluate(baseline, current, history)
    print(render(baseline, current, history, gates, drift))
    return exit_code(gates, current)


if __name__ == "__main__":
    sys.exit(main())
