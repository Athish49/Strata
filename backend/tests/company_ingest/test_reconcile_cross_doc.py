"""Tests for app.company_ingest.link.reconcile_cross_doc (cross-document backlog sweep).

Postgres behaviour runs against a throwaway local cluster, same pattern as
tests/company_ingest/test_promote.py (initdb in a pytest tmp dir, unix socket only,
torn down afterwards). It never connects to DATABASE_URL. R2 is a tiny in-memory fake
keyed by (company_id, run_id) -> report dict, so no boto3/network is involved.
"""
from __future__ import annotations

import shutil
import socket
import subprocess
import uuid
from pathlib import Path

import pytest

from app.company_ingest.link.reconcile_cross_doc import reconcile_unresolved_references

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "engine" / "fixtures" / "company_schema.sql"
CO = "co"
U = lambda s: str(uuid.uuid5(uuid.NAMESPACE_URL, s))  # noqa: E731


# =========================================================================== fakes
class FakeR2:
    """{(company_id, run_id): report_dict} -> get_bytes(key) by re-deriving the key."""

    def __init__(self, reports: dict[tuple[str, str], dict]):
        self._reports = reports

    def get_bytes(self, key: str) -> bytes:
        import json

        from app.company_ingest.store.r2_keys import report_key

        for (company_id, run_id), report in self._reports.items():
            if report_key(company_id, run_id) == key:
                return json.dumps(report).encode("utf-8")
        raise KeyError(key)


def _unresolved_ref_issue(doc_id: str, clause_id: str, target_hint: str | None) -> dict:
    return {
        "severity": "warning", "stage": "6.1.1_resolve_refs", "code": "unresolved_ref",
        "message": "x", "doc_id": doc_id, "clause_id": clause_id, "path": None,
        "details": {"ref_type": "references_clause", "target_hint": target_hint},
    }


# =========================================================================== scratch PG
def _pg_bin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for cand in sorted(Path("/opt/homebrew/opt").glob("postgresql@*/bin/" + name), reverse=True):
        return str(cand)
    return None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def scratch_pg(tmp_path_factory):
    initdb, pg_ctl = _pg_bin("initdb"), _pg_bin("pg_ctl")
    if not (initdb and pg_ctl):
        pytest.skip("no local initdb/pg_ctl for a scratch PostgreSQL cluster")
    base = tmp_path_factory.mktemp("pg")
    data, sock = base / "data", Path(f"/tmp/strata-pg-{uuid.uuid4().hex[:8]}")
    sock.mkdir()
    port = _free_port()
    subprocess.run([initdb, "-D", str(data), "-A", "trust", "-U", "postgres", "--no-sync"],
                   check=True, capture_output=True)
    subprocess.run([pg_ctl, "start", "-D", str(data), "-w", "-l", str(base / "log"), "-o",
                    f"-p {port} -k {sock} -c listen_addresses='' -c fsync=off"],
                   check=True, capture_output=True)
    try:
        yield {"host": str(sock), "port": port,
               "url": f"postgresql+asyncpg://postgres@/postgres?host={sock}&port={port}"}
    finally:
        subprocess.run([pg_ctl, "-D", str(data), "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(sock, ignore_errors=True)


def _sync_conn(pg):
    import psycopg2

    con = psycopg2.connect(host=pg["host"], port=pg["port"], user="postgres", dbname="postgres")
    con.autocommit = True
    return con


def _seed(cur, *, doc_id, doc_number, version_id, run_id, clause_ids):
    cur.execute(
        "INSERT INTO company.company_documents (company_id, doc_id, title, doc_number, "
        "current_version_id) VALUES (%s,%s,'t',%s,%s)",
        (CO, doc_id, doc_number, version_id))
    cur.execute(
        "INSERT INTO company.document_versions (version_id, company_id, doc_id, version_no, "
        "status, ingest_status, is_current, ingest_run_id) VALUES (%s,%s,%s,1,'effective',"
        "'ingested',true,%s)",
        (version_id, CO, doc_id, run_id))
    for i, local_id in enumerate(clause_ids):
        clause_id = f"{doc_id}:{local_id}"
        cur.execute(
            "INSERT INTO company.clauses (clause_pk, company_id, version_id, doc_id, clause_id, "
            "local_id, ordinal, unit_kind, section_kind, text_raw, text_norm, text_sha256, "
            "clause_role, assessable) VALUES (%s,%s,%s,%s,%s,%s,%s,'section','body','t','t','x',"
            "'internal_procedure',true)",
            (U(f"pk/{clause_id}"), CO, version_id, doc_id, clause_id, local_id, i))


@pytest.fixture
def pg(scratch_pg):
    con = _sync_conn(scratch_pg)
    cur = con.cursor()
    cur.execute("DROP SCHEMA IF EXISTS company CASCADE")
    cur.execute(SCHEMA_SQL.read_text())
    cur.execute("INSERT INTO company.companies (company_id) VALUES (%s)", (CO,))
    con.close()
    return scratch_pg


def _rows(pg, sql, params=()):
    con = _sync_conn(pg)
    try:
        cur = con.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        con.close()


@pytest.fixture
async def make_session(pg):
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    engines = []

    def _make():
        eng = create_async_engine(pg["url"])
        engines.append(eng)
        return AsyncSession(eng)

    yield _make
    for eng in engines:
        await eng.dispose()


# =========================================================================== acceptance
V_SRC, V_TGT = U("v-src"), U("v-tgt")
RUN_SRC, RUN_TGT = U("run-src"), U("run-tgt")


async def test_resolves_a_real_cross_document_reference(pg, make_session):
    """The traced example from findings_1.0: a register row's unresolved reference to
    another document's clause becomes a real clause_links row once that target exists."""
    con = _sync_conn(pg)
    cur = con.cursor()
    _seed(cur, doc_id="DOC-000006", doc_number="RPL-LEG-RRS-001", version_id=V_SRC,
          run_id=RUN_SRC, clause_ids=["RRS-FIN-003"])
    _seed(cur, doc_id="DOC-000007", doc_number="RPL-TAR-GRR-012", version_id=V_TGT,
          run_id=RUN_TGT, clause_ids=["R01.D20"])
    con.close()

    r2 = FakeR2({
        (CO, RUN_SRC): {"issues": [
            _unresolved_ref_issue("DOC-000006", "DOC-000006:RRS-FIN-003",
                                   "RPL-TAR-GRR-012:R01.D20"),
        ]},
        (CO, RUN_TGT): {"issues": []},
    })

    async with make_session() as s:
        result = await reconcile_unresolved_references(s, CO, r2_client=r2)
        await s.commit()

    assert (result.scanned, result.resolved, result.still_unresolved, result.skipped) == (1, 1, 0, 0)

    rows = _rows(pg, "SELECT link_type, method, evidence, confidence FROM company.clause_links")
    assert rows == [("references_clause", "cross_doc_backlog", "RPL-TAR-GRR-012:R01.D20", 1.0)]


async def test_idempotent_rerun_is_a_no_op(pg, make_session):
    con = _sync_conn(pg)
    cur = con.cursor()
    _seed(cur, doc_id="DOC-000006", doc_number="RPL-LEG-RRS-001", version_id=V_SRC,
          run_id=RUN_SRC, clause_ids=["RRS-FIN-003"])
    _seed(cur, doc_id="DOC-000007", doc_number="RPL-TAR-GRR-012", version_id=V_TGT,
          run_id=RUN_TGT, clause_ids=["R01.D20"])
    con.close()

    r2 = FakeR2({
        (CO, RUN_SRC): {"issues": [
            _unresolved_ref_issue("DOC-000006", "DOC-000006:RRS-FIN-003",
                                   "RPL-TAR-GRR-012:R01.D20"),
        ]},
        (CO, RUN_TGT): {"issues": []},
    })

    async with make_session() as s:
        await reconcile_unresolved_references(s, CO, r2_client=r2)
        await s.commit()
    async with make_session() as s:
        result = await reconcile_unresolved_references(s, CO, r2_client=r2)
        await s.commit()

    assert result.resolved == 1  # re-counted as "resolved" even though it's a no-op write
    rows = _rows(pg, "SELECT count(*) FROM company.clause_links")
    assert rows == [(1,)]  # still exactly one row — ON CONFLICT DO NOTHING held


async def test_target_document_not_found_is_counted_not_raised(pg, make_session):
    con = _sync_conn(pg)
    cur = con.cursor()
    _seed(cur, doc_id="DOC-000006", doc_number="RPL-LEG-RRS-001", version_id=V_SRC,
          run_id=RUN_SRC, clause_ids=["RRS-FIN-003"])
    con.close()

    r2 = FakeR2({(CO, RUN_SRC): {"issues": [
        _unresolved_ref_issue("DOC-000006", "DOC-000006:RRS-FIN-003", "RPL-NOPE-999:X1"),
    ]}})

    async with make_session() as s:
        result = await reconcile_unresolved_references(s, CO, r2_client=r2)
        await s.commit()

    assert (result.scanned, result.resolved, result.still_unresolved) == (1, 0, 1)
    assert _rows(pg, "SELECT count(*) FROM company.clause_links") == [(0,)]


async def test_target_clause_missing_in_existing_document_is_counted_not_raised(pg, make_session):
    con = _sync_conn(pg)
    cur = con.cursor()
    _seed(cur, doc_id="DOC-000006", doc_number="RPL-LEG-RRS-001", version_id=V_SRC,
          run_id=RUN_SRC, clause_ids=["RRS-FIN-003"])
    _seed(cur, doc_id="DOC-000007", doc_number="RPL-TAR-GRR-012", version_id=V_TGT,
          run_id=RUN_TGT, clause_ids=["R01.D20"])
    con.close()

    r2 = FakeR2({
        (CO, RUN_SRC): {"issues": [
            _unresolved_ref_issue("DOC-000006", "DOC-000006:RRS-FIN-003",
                                   "RPL-TAR-GRR-012:NO-SUCH-LOCAL-ID"),
        ]},
        (CO, RUN_TGT): {"issues": []},
    })

    async with make_session() as s:
        result = await reconcile_unresolved_references(s, CO, r2_client=r2)
        await s.commit()

    assert (result.scanned, result.resolved, result.still_unresolved) == (1, 0, 1)


async def test_same_document_hint_with_no_colon_is_skipped_not_fixed(pg, make_session):
    """A bare local_id (no doc prefix) means the resolver already tried this exact
    document and failed to find it there — not a cross-document candidate, nothing
    this sweep can or should fix."""
    con = _sync_conn(pg)
    cur = con.cursor()
    _seed(cur, doc_id="DOC-000006", doc_number="RPL-LEG-RRS-001", version_id=V_SRC,
          run_id=RUN_SRC, clause_ids=["RRS-FIN-003"])
    con.close()

    r2 = FakeR2({(CO, RUN_SRC): {"issues": [
        _unresolved_ref_issue("DOC-000006", "DOC-000006:RRS-FIN-003", "SOME-LOCAL-ID"),
    ]}})

    async with make_session() as s:
        result = await reconcile_unresolved_references(s, CO, r2_client=r2)
        await s.commit()

    assert (result.scanned, result.resolved, result.skipped) == (1, 0, 1)


async def test_other_ref_types_and_report_fetch_failures_are_ignored(pg, make_session):
    con = _sync_conn(pg)
    cur = con.cursor()
    _seed(cur, doc_id="DOC-000006", doc_number="RPL-LEG-RRS-001", version_id=V_SRC,
          run_id=RUN_SRC, clause_ids=["RRS-FIN-003"])
    con.close()

    other_type_issue = {
        "severity": "warning", "stage": "s", "code": "unresolved_ref", "message": "x",
        "doc_id": "DOC-000006", "clause_id": "DOC-000006:RRS-FIN-003",
        "details": {"ref_type": "restates", "target_hint": "RPL-TAR-GRR-012:R01.D20"},
    }
    r2 = FakeR2({(CO, RUN_SRC): {"issues": [other_type_issue]}})

    async with make_session() as s:
        result = await reconcile_unresolved_references(s, CO, r2_client=r2)
        await s.commit()

    assert (result.scanned, result.resolved) == (0, 0)


async def test_missing_report_in_r2_does_not_raise(pg, make_session):
    con = _sync_conn(pg)
    cur = con.cursor()
    _seed(cur, doc_id="DOC-000006", doc_number="RPL-LEG-RRS-001", version_id=V_SRC,
          run_id=RUN_SRC, clause_ids=["RRS-FIN-003"])
    con.close()

    r2 = FakeR2({})  # no report at all for this run_id

    async with make_session() as s:
        result = await reconcile_unresolved_references(s, CO, r2_client=r2)
        await s.commit()

    assert (result.scanned, result.resolved) == (0, 0)
