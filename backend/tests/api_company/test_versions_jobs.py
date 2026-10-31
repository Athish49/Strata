"""Task 6.4 (version history + ingest-job status/retry) and the task 6.3 leftovers
(cancel retires the version; approval gated on the ingest job), through the HTTP
handlers against a throwaway local PostgreSQL cluster.

Same scratch-cluster pattern as tests/company_ingest/test_jobs_recovery.py: initdb
in a pytest tmp dir, unix socket only, loaded from
tests/engine/fixtures/company_schema.sql, torn down afterwards. It never connects to
DATABASE_URL: ``jobs._default_session_factory`` raises, ``get_db`` and the
``versions.job_session_factory`` dependency are overridden with the scratch factory,
R2 reads are monkeypatched, and the Qdrant client factory raises.
"""
from __future__ import annotations

import hashlib
import shutil
import socket
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.company_ingest.store.r2 as r2_mod
from app.api.company import org, versions
from app.company_ingest import jobs
from app.company_ingest.hashing import content_hash
from app.company_ingest.index import upsert as upsert_module
from app.db import get_db
from app.main import app

pytestmark = pytest.mark.asyncio

BACKEND = Path(__file__).resolve().parents[2]
SCHEMA_SQL = BACKEND / "tests" / "engine" / "fixtures" / "company_schema.sql"
# Test-owned copy (not the deletable synthetic/ corpus), same reasoning as task 9.4's
# fix for test_jobs_recovery.py/test_service.py: this file must keep running the same
# way whether or not backend/synthetic/ is present.
DOCX_FIXTURE = BACKEND / "tests" / "fixtures" / "docx" / "RPL-CS-PRO-004_v5.1.docx"
CO = "co"
DOC = "DOC-000001"
H1 = hashlib.sha256(b"content-1").hexdigest()
H2 = hashlib.sha256(b"content-2").hexdigest()


def U(s: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, s))


# --------------------------------------------------------------------------- scratch cluster
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


def _sync(pg):
    import psycopg2

    con = psycopg2.connect(host=pg["host"], port=pg["port"], user="postgres", dbname="postgres")
    con.autocommit = True
    return con


def _exec(pg, sql, params=()):
    con = _sync(pg)
    try:
        con.cursor().execute(sql, params)
    finally:
        con.close()


def _rows(pg, sql, params=()):
    con = _sync(pg)
    try:
        cur = con.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        con.close()


@pytest.fixture
def pg(scratch_pg):
    """Fresh schema per test plus one acting person."""
    con = _sync(scratch_pg)
    cur = con.cursor()
    cur.execute("DROP SCHEMA IF EXISTS company CASCADE")
    cur.execute(SCHEMA_SQL.read_text())
    cur.execute("INSERT INTO company.companies (company_id) VALUES (%s)", (CO,))
    cur.execute("INSERT INTO company.people (company_id, person_id, name) VALUES (%s,'P1','A')", (CO,))
    con.close()
    return scratch_pg


@pytest.fixture
async def factory(pg):
    engine = create_async_engine(pg["url"], poolclass=NullPool)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    def _refuse(*a, **kw):
        raise AssertionError("test reached a production client")

    monkeypatch.setattr(jobs, "_default_session_factory", _refuse)
    monkeypatch.setattr(upsert_module, "_make_client", _refuse)
    monkeypatch.setattr(r2_mod, "get_bytes", _refuse)
    monkeypatch.setattr(org.engine_settings, "ENGINE_COMPANY_ID", CO)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(factory):
    async def _db():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[versions.job_session_factory] = lambda: factory
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


@pytest.fixture
def ran(monkeypatch):
    """Replace the BackgroundTask body with a recorder (Starlette runs background
    tasks inside the ASGI call, so the real one would run the real ingest)."""
    calls = []

    async def _record(job_id, **kw):
        calls.append({"job_id": job_id, **kw})

    # versions.py binds the name at import time, so patch it where it is used.
    monkeypatch.setattr("app.api.company.versions.run_ingest_with_bookkeeping", _record)
    return calls


# --------------------------------------------------------------------------- seed helpers
def _doc(pg, doc_id=DOC, *, current=None, h=H1, state="active", title="Policy"):
    _exec(pg, "INSERT INTO company.company_documents (company_id, doc_id, title, "
              "current_version_id, current_content_hash, lifecycle_state) VALUES (%s,%s,%s,%s,%s,%s)",
          (CO, doc_id, title, current, h, state))


def _version(pg, vid, no, status, *, doc_id=DOC, is_current=False, ingest="ingested",
             pending=None, key=None, supersedes=None, superseded_by=None, reason=None):
    _exec(pg, "INSERT INTO company.document_versions (version_id, company_id, doc_id, version_no, "
              "version, status, is_current, ingest_status, pending_content_hash, source_r2_key, "
              "supersedes_version_id, superseded_by, change_reason, created_by_person_id, "
              "effective_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'P1',"
              "CASE WHEN %s THEN DATE '2026-01-01' END)",
          (vid, CO, doc_id, no, f"v{no}.0", status, is_current, ingest, pending, key,
           supersedes, superseded_by, reason, is_current))


def _job(pg, jid, vid, state, *, doc_id=DOC, minutes_ago=0, error=None):
    _exec(pg, "INSERT INTO company.ingest_jobs (job_id, company_id, doc_id, version_id, state, "
              "error, created_at, started_at) VALUES (%s,%s,%s,%s,%s,%s, "
              "now() - make_interval(mins => %s), "
              "CASE WHEN %s IN ('running','succeeded','failed') "
              "THEN now() - make_interval(mins => %s) END)",
          (jid, CO, doc_id, vid, state, error, minutes_ago, state, minutes_ago))


def _request(pg, rid, vid, steps, *, state="open"):
    """steps: list of (step_no, role, decision)."""
    _exec(pg, "INSERT INTO company.approval_requests (request_id, company_id, version_id, state) "
              "VALUES (%s,%s,%s,%s)", (rid, CO, vid, state))
    for no, role, decision in steps:
        _exec(pg, "INSERT INTO company.approval_steps (request_id, step_no, required_role, "
                  "assignee_person_id, decision) VALUES (%s,%s,%s,'P1',%s)", (rid, no, role, decision))


V1, V2 = U("v1"), U("v2")


# =========================================================================== version history
async def test_two_versions_newest_first_exactly_one_current(pg, client):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True, superseded_by=None)
    _version(pg, V2, 2, "in_review", pending=H2, supersedes=V1, reason="annual review")
    rid = U("req")
    _request(pg, U("old-req"), V2, [(1, "reviewer", "rejected")], state="rejected")
    _exec(pg, "UPDATE company.approval_requests SET created_at = now() - interval '1 hour'")
    _request(pg, rid, V2, [(1, "reviewer", "approved"), (2, "approver", None)])
    _job(pg, U("j2"), V2, "succeeded")

    async with client as c:
        res = await c.get(f"/company/documents/{DOC}/versions")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["doc_id"] == DOC and body["current_version_id"] == V1
    vs = body["versions"]
    assert [v["version_no"] for v in vs] == [2, 1]
    assert [v["is_current"] for v in vs] == [False, True]
    assert sum(v["is_current"] for v in vs) == 1

    v2, v1 = vs
    assert v2["version_id"] == V2 and v2["status"] == "in_review" and v2["version"] == "v2.0"
    assert v2["supersedes_version_id"] == V1 and v2["change_reason"] == "annual review"
    assert v2["created_by_person_id"] == "P1" and v2["created_at"]
    assert v2["ingest_status"] == "ingested"
    assert v2["ingest_job"] == {"job_id": U("j2"), "state": "succeeded"}
    # the LATEST request wins, with step progress
    assert v2["approval"]["request_id"] == rid and v2["approval"]["state"] == "open"
    assert (v2["approval"]["steps_total"], v2["approval"]["steps_decided"],
            v2["approval"]["steps_approved"]) == (2, 1, 1)
    assert v2["approval"]["next_step_no"] == 2
    assert v2["approval"]["next_required_role"] == "approver"
    assert v1["effective_date"] == "2026-01-01" and v1["approval"] is None
    assert v1["ingest_job"] is None
    for key in ("version_id", "version_no", "version", "status", "is_current", "effective_date",
                "approved_date", "created_at", "created_by_person_id", "change_reason",
                "supersedes_version_id", "superseded_by", "ingest_status", "approval"):
        assert key in v1


async def test_versions_unknown_doc_404_and_doc_without_versions_empty(pg, client):
    _doc(pg, current=None, h=None, state="pending")
    async with client as c:
        missing = await c.get("/company/documents/DOC-404/versions")
        empty = await c.get(f"/company/documents/{DOC}/versions")
    assert missing.status_code == 404
    assert empty.status_code == 200 and empty.json()["versions"] == []
    assert empty.json()["current_version_id"] is None


# =========================================================================== job polling
async def test_poll_queued_running_succeeded_never_404(pg, factory, client):
    _doc(pg, current=None, state="pending")
    _version(pg, V1, 1, "in_review", ingest="pending")
    async with factory() as s:
        jid = await jobs.create_job(s, company_id=CO, doc_id=DOC, version_id=V1)
        await s.commit()

    async with client as c:
        r = await c.get(f"/company/ingest-jobs/{jid}")
        assert r.status_code == 200, r.text
        assert r.json()["job"]["state"] == "queued" and r.json()["stats"] == {}
        assert r.json()["job"]["created_at"] and r.json()["job"]["started_at"] is None

        await jobs.mark_running(jid, session_factory=factory)
        r = await c.get(f"/company/ingest-jobs/{jid}")
        assert r.status_code == 200 and r.json()["job"]["state"] == "running"
        assert r.json()["job"]["started_at"] and r.json()["job"]["finished_at"] is None

        async with factory() as s:
            await jobs.mark_succeeded(s, jid, {"clauses": 12, "citations": 3})
            await s.commit()
        r = await c.get(f"/company/ingest-jobs/{jid}")
    assert r.status_code == 200
    body = r.json()
    assert body["job"]["state"] == "succeeded" and body["job"]["error"] is None
    assert body["stats"] == {"clauses": 12, "citations": 3}
    assert body["job"]["finished_at"]
    assert body["job"]["job_id"] == jid and body["job"]["doc_id"] == DOC
    assert body["job"]["version_id"] == V1


async def test_poll_failed_job_reports_error(pg, factory, client):
    _doc(pg, current=None, state="pending")
    _version(pg, V1, 1, "in_review", ingest="pending")
    jid = U("jf")
    _job(pg, jid, V1, "running")
    await jobs.mark_failed(jid, "IngestError: no clauses", session_factory=factory)
    async with client as c:
        r = await c.get(f"/company/ingest-jobs/{jid}")
    assert r.status_code == 200
    assert r.json()["job"]["state"] == "failed"
    assert r.json()["job"]["error"] == "IngestError: no clauses"
    assert r.json()["stats"] == {}


async def test_poll_unknown_or_malformed_job_is_404(pg, client):
    async with client as c:
        unknown = await c.get(f"/company/ingest-jobs/{uuid.uuid4()}")
        bad = await c.get("/company/ingest-jobs/not-a-uuid")
    assert unknown.status_code == 404 and bad.status_code == 404


async def test_stale_running_job_is_reclaimed_by_a_poll(pg, client):
    """A job killed < N minutes before a restart escapes the startup sweep; once it is
    stale, the next poll fails it and releases the first-version reservation."""
    _doc(pg, current=None, state="pending")
    _version(pg, V1, 1, "in_review", ingest="pending", pending=H1)
    stale, fresh = U("stale"), U("fresh")
    _job(pg, stale, V1, "running", minutes_ago=jobs.DEFAULT_STALE_MINUTES + 5)
    # a young running job is left alone
    _doc(pg, "DOC-000002", current=None, h=H2, state="pending")
    _version(pg, V2, 1, "in_review", doc_id="DOC-000002", ingest="pending")
    _job(pg, fresh, V2, "running", doc_id="DOC-000002", minutes_ago=1)

    async with client as c:
        r = await c.get(f"/company/ingest-jobs/{stale}")
        young = await c.get(f"/company/ingest-jobs/{fresh}")
    assert r.status_code == 200
    assert r.json()["job"]["state"] == "failed"
    assert r.json()["job"]["error"].startswith("orphaned: running")
    assert _rows(pg, "SELECT doc_id, current_content_hash, lifecycle_state "
                     "FROM company.company_documents ORDER BY doc_id") == [
        (DOC, None, "failed"), ("DOC-000002", H2, "pending")]
    assert _rows(pg, "SELECT doc_id, ingest_status FROM company.document_versions ORDER BY doc_id") \
        == [(DOC, "failed"), ("DOC-000002", "pending")]
    assert young.json()["job"]["state"] == "running"


async def test_poll_honours_ingest_job_stale_minutes(pg, client, monkeypatch):
    monkeypatch.setenv("INGEST_JOB_STALE_MINUTES", "2")
    _doc(pg, current=None, state="pending")
    _version(pg, V1, 1, "in_review", ingest="pending")
    _job(pg, U("j"), V1, "running", minutes_ago=3)
    async with client as c:
        r = await c.get(f"/company/ingest-jobs/{U('j')}")
    assert r.json()["job"]["state"] == "failed"


# =========================================================================== retry
def _docx_bytes() -> bytes:
    if not DOCX_FIXTURE.exists():
        pytest.skip(f"missing DOCX fixture {DOCX_FIXTURE}")
    return DOCX_FIXTURE.read_bytes()


async def test_retry_failed_job_is_202_same_job_and_schedules_ingest(pg, client, ran, monkeypatch):
    raw = _docx_bytes()
    key = f"company/{CO}/{DOC}/{V1}/raw/policy.docx"
    monkeypatch.setattr(r2_mod, "get_bytes", lambda k: raw if k == key else (_ for _ in ()).throw(KeyError(k)))
    _doc(pg, current=None, h=None, state="failed", title="Billing Policy")
    _doc(pg, "DOC-000002", current=None, h=H2)
    _version(pg, V1, 1, "in_review", ingest="failed", pending=H1, key=key)
    jid = U("jr")
    _job(pg, jid, V1, "failed", error="IngestError: boom")

    async with client as c:
        res = await c.post(f"/company/ingest-jobs/{jid}/retry")
        polled = await c.get(f"/company/ingest-jobs/{jid}")
    assert res.status_code == 202, res.text
    assert res.json()["job_id"] == jid and res.json()["state"] == "queued"
    assert polled.json()["job"]["state"] == "queued" and polled.json()["job"]["error"] is None

    assert len(ran) == 1
    call = ran[0]
    assert call["job_id"] == jid and call["register_spec"] is None
    assert call["markdown"].strip()
    assert call["document_title"] == "Billing Policy"
    assert call["registered_doc_ids"] == [DOC, "DOC-000002"]
    assert callable(call["session_factory"])
    # the first-version reservation is re-taken with the re-extracted content's hash
    assert _rows(pg, "SELECT current_content_hash, lifecycle_state FROM company.company_documents "
                     "WHERE doc_id = %s", (DOC,)) == [(content_hash(call["markdown"]), "pending")]
    assert _rows(pg, "SELECT ingest_status FROM company.document_versions") == [("pending",)]


@pytest.mark.parametrize("state", ["queued", "running", "succeeded"])
async def test_retry_of_a_non_failed_job_is_409(pg, client, ran, state):
    _doc(pg, current=None, state="pending")
    _version(pg, V1, 1, "in_review", ingest="pending", key="k.docx")
    _job(pg, U("j"), V1, state)
    async with client as c:
        res = await c.post(f"/company/ingest-jobs/{U('j')}/retry")
    assert res.status_code == 409 and "only 'failed' jobs can be retried" in res.json()["detail"]
    assert ran == []
    assert _rows(pg, "SELECT state FROM company.ingest_jobs") == [(state,)]


async def test_retry_unknown_job_404_and_unretryable_422(pg, client, ran):
    _doc(pg, current=None, h=None, state="failed")
    _version(pg, V1, 1, "in_review", ingest="failed", key=None)     # no raw key
    _job(pg, U("j"), V1, "failed")
    async with client as c:
        unknown = await c.post(f"/company/ingest-jobs/{uuid.uuid4()}/retry")
        bad = await c.post("/company/ingest-jobs/nope/retry")
        no_key = await c.post(f"/company/ingest-jobs/{U('j')}/retry")
    assert unknown.status_code == 404 and bad.status_code == 404
    assert no_key.status_code == 422 and "source_r2_key" in no_key.json()["detail"]
    assert ran == []
    assert _rows(pg, "SELECT state FROM company.ingest_jobs") == [("failed",)]


async def test_retry_when_another_document_now_holds_the_hash_is_409(pg, client, ran, monkeypatch):
    raw = _docx_bytes()
    monkeypatch.setattr(r2_mod, "get_bytes", lambda k: raw)
    from app.company_ingest.extract import DocxExtractor

    h = content_hash(DocxExtractor().extract(raw, "x.docx").markdown)
    _doc(pg, current=None, h=None, state="failed")
    _doc(pg, "DOC-000009", current=U("other"), h=h)       # took the content meanwhile
    _version(pg, V1, 1, "in_review", ingest="failed", key="raw/x.docx")
    _job(pg, U("j"), V1, "failed")
    async with client as c:
        res = await c.post(f"/company/ingest-jobs/{U('j')}/retry")
    assert res.status_code == 409 and "another document" in res.json()["detail"]
    assert ran == []
    assert _rows(pg, "SELECT state FROM company.ingest_jobs") == [("failed",)]


# =========================================================================== task 6.3 leftovers
async def test_cancel_retires_the_version_and_nulls_its_pending_hash(pg, client):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    _version(pg, V2, 2, "in_review", pending=H2)
    rid = U("req")
    _request(pg, rid, V2, [(1, "approver", None)])
    async with client as c:
        res = await c.post(f"/company/approval-requests/{rid}/cancel", json={"acting_person_id": "P1"})
        listing = await c.get(f"/company/documents/{DOC}/versions")
    assert res.status_code == 200, res.text
    assert res.json()["state"] == "cancelled" and res.json()["version_status"] == "retired"
    assert _rows(pg, "SELECT version_no, status, is_current, pending_content_hash "
                     "FROM company.document_versions ORDER BY version_no") == [
        (1, "effective", True, None), (2, "retired", False, None)]
    # the live document is untouched
    assert _rows(pg, "SELECT current_version_id::text, current_content_hash "
                     "FROM company.company_documents") == [(V1, H1)]
    assert listing.json()["versions"][0]["status"] == "retired"
    assert listing.json()["versions"][0]["approval"]["state"] == "cancelled"


async def test_cancel_unknown_acting_person_changes_nothing(pg, client):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    _version(pg, V2, 2, "in_review", pending=H2)
    rid = U("req")
    _request(pg, rid, V2, [(1, "approver", None)])
    async with client as c:
        res = await c.post(f"/company/approval-requests/{rid}/cancel", json={"acting_person_id": "GHOST"})
    assert res.status_code == 404
    assert _rows(pg, "SELECT status, pending_content_hash FROM company.document_versions "
                     "WHERE version_id = %s", (V2,)) == [("in_review", H2)]


@pytest.mark.parametrize("job_state", ["queued", "running", "failed"])
async def test_approval_refused_until_ingest_job_succeeded(pg, client, job_state):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    _version(pg, V2, 2, "in_review", ingest="failed" if job_state == "failed" else "pending", pending=H2)
    _job(pg, U("j2"), V2, job_state)
    rid = U("req")
    _request(pg, rid, V2, [(1, "reviewer", None), (2, "approver", None)])
    async with client as c:
        res = await c.post(f"/company/approval-requests/{rid}/steps/1/decision",
                           json={"decision": "approved", "acting_person_id": "P1"})
        # rejecting is still allowed
        rej = await c.post(f"/company/approval-requests/{rid}/steps/1/decision",
                           json={"decision": "rejected", "acting_person_id": "P1"})
    assert res.status_code == 409
    assert f"'{job_state}', not 'succeeded'" in res.json()["detail"]
    assert rej.status_code == 200 and rej.json()["request_state"] == "rejected"
    assert _rows(pg, "SELECT decision FROM company.approval_steps ORDER BY step_no") == [
        ("rejected",), (None,)]


async def test_approval_allowed_once_ingest_job_succeeded(pg, client):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    _version(pg, V2, 2, "in_review", pending=H2)
    _job(pg, U("j2"), V2, "succeeded")
    rid = U("req")
    _request(pg, rid, V2, [(1, "reviewer", None), (2, "approver", None)])
    async with client as c:
        res = await c.post(f"/company/approval-requests/{rid}/steps/1/decision",
                           json={"decision": "approved", "acting_person_id": "P1"})
    assert res.status_code == 200 and res.json()["request_state"] == "open"


async def test_rejection_leaves_version_in_review_not_current_and_not_indexed(pg, client):
    """Qdrant's client factory raises (autouse), so any indexing attempt would 500."""
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    _version(pg, V2, 2, "in_review", pending=H2)
    _job(pg, U("j2"), V2, "succeeded")
    rid = U("req")
    _request(pg, rid, V2, [(1, "approver", None)])
    async with client as c:
        res = await c.post(f"/company/approval-requests/{rid}/steps/1/decision",
                           json={"decision": "rejected", "acting_person_id": "P1"})
    assert res.status_code == 200 and res.json()["request_state"] == "rejected"
    # Task 3.2 decision 1: a rejected version KEEPS its pending hash
    assert _rows(pg, "SELECT status, is_current, pending_content_hash FROM company.document_versions "
                     "WHERE version_id = %s", (V2,)) == [("in_review", False, H2)]
    assert _rows(pg, "SELECT current_version_id::text, current_content_hash "
                     "FROM company.company_documents") == [(V1, H1)]


async def test_cancelling_a_first_version_releases_the_documents_reserved_hash(pg, client):
    """A document whose only version is cancelled must not stay reserved.

    Otherwise it sits `pending` with a hash and no live version, and re-uploading the
    same content is rejected as a duplicate of a document that has nothing live."""
    _doc(pg, current=None, h=H1, state="pending")
    _version(pg, V1, 1, "in_review", pending=H1)
    rid = U("req1")
    _request(pg, rid, V1, [(1, "approver", None)])
    async with client as c:
        res = await c.post(f"/company/approval-requests/{rid}/cancel", json={"acting_person_id": "P1"})
    assert res.status_code == 200, res.text
    assert _rows(pg, "SELECT status, pending_content_hash FROM company.document_versions") == [("retired", None)]
    assert _rows(pg, "SELECT current_version_id, current_content_hash, lifecycle_state "
                     "FROM company.company_documents") == [(None, None, "retired")]
    # the released hash is genuinely free: another document may now take it
    _exec(pg, "INSERT INTO company.company_documents (company_id, doc_id, title, current_content_hash, "
              "lifecycle_state) VALUES (%s,%s,%s,%s,'pending')", (CO, "DOC-000099", "Other", H1))


async def test_cancelling_a_later_version_keeps_the_live_documents_hash(pg, client):
    """The release must never touch a document that has a live version."""
    _doc(pg, current=V1, h=H1)
    _version(pg, V1, 1, "effective", is_current=True)
    _version(pg, V2, 2, "in_review", pending=H2)
    rid = U("req2")
    _request(pg, rid, V2, [(1, "approver", None)])
    async with client as c:
        res = await c.post(f"/company/approval-requests/{rid}/cancel", json={"acting_person_id": "P1"})
    assert res.status_code == 200, res.text
    assert _rows(pg, "SELECT current_version_id::text, current_content_hash, lifecycle_state "
                     "FROM company.company_documents") == [(V1, H1, "active")]


async def test_cancelling_a_first_version_with_another_open_version_keeps_the_reservation(pg, client):
    """If another non-retired version exists the document is still in play: don't release."""
    V3 = U("v3")
    _doc(pg, current=None, h=H1, state="pending")
    _version(pg, V1, 1, "in_review", pending=H1)
    _version(pg, V3, 2, "in_review", pending=H2)
    rid = U("req3")
    _request(pg, rid, V1, [(1, "approver", None)])
    async with client as c:
        res = await c.post(f"/company/approval-requests/{rid}/cancel", json={"acting_person_id": "P1"})
    assert res.status_code == 200, res.text
    assert _rows(pg, "SELECT current_content_hash, lifecycle_state FROM company.company_documents") == [(H1, "pending")]


async def test_retry_of_a_retired_version_is_refused_with_409(pg, client, ran):
    """A version retired by a cancel or a newer upload must not be re-ingested."""
    _doc(pg, current=None, h=H1, state="pending")
    _version(pg, V1, 1, "retired", key="company/rpl/raw/DOC-000001/1/x.docx")
    _job(pg, U("jr"), V1, "failed", error="boom")
    async with client as c:
        res = await c.post(f"/company/ingest-jobs/{U('jr')}/retry")
    assert res.status_code == 409, res.text
    assert "retired" in res.json()["detail"]
    assert ran == [], "nothing may be scheduled for a retired version"


# =========================================================================== document list state
async def test_document_list_reports_state_for_documents_without_a_current_version(pg, client):
    """Runs the real `_DOC_SQL` (including its LATERAL "newest non-retired version" join).

    A brand-new upload has no current version, so `version`/`status` are blank; the list
    must still say what state it is in so the UI can show "processing" / "in review"."""
    # `_documents()` also runs the cited-citations query, which joins the regulatory KB.
    _exec(pg, "CREATE TABLE IF NOT EXISTS public.code_sections (id int PRIMARY KEY, citation text)")
    # DOC-000001: v1 retired, v2 in review (newest non-retired = v2); never promoted
    _doc(pg, "DOC-000001", current=None, h="a" * 64, state="pending", title="Brand new")
    _version(pg, U("a1"), 1, "retired", doc_id="DOC-000001", ingest="failed")
    _version(pg, U("a2"), 2, "in_review", doc_id="DOC-000001", ingest="ingested", pending="c" * 64)
    # DOC-000002: live v1, plus a pending v2 -> current version wins for status/monitored
    _doc(pg, "DOC-000002", current=U("b1"), h="b" * 64, state="active", title="Live")
    _version(pg, U("b1"), 1, "effective", doc_id="DOC-000002", is_current=True)
    _version(pg, U("b2"), 2, "in_review", doc_id="DOC-000002", ingest="pending", pending="d" * 64)
    # DOC-000003: the only version was retired -> no non-retired version at all
    _doc(pg, "DOC-000003", current=None, h=None, state="retired", title="Cancelled")
    _version(pg, U("c1"), 1, "retired", doc_id="DOC-000003")

    async with client as c:
        res = await c.get("/company/documents")
    assert res.status_code == 200, res.text
    by = {d["doc_id"]: d for d in res.json()}
    assert set(by) == {"DOC-000001", "DOC-000002", "DOC-000003"}, "one row per document, no duplicates from the join"

    new = by["DOC-000001"]
    assert (new["lifecycle_state"], new["has_current_version"], new["monitored"]) == ("pending", False, False)
    assert (new["latest_version_no"], new["latest_version_status"], new["latest_ingest_status"]) == (2, "in_review", "ingested")
    assert new["version"] == "" and new["status"] == ""

    live = by["DOC-000002"]
    assert (live["lifecycle_state"], live["has_current_version"], live["status"]) == ("active", True, "effective")
    assert (live["latest_version_no"], live["latest_version_status"]) == (2, "in_review"), "newest version is the pending v2"
    assert live["monitored"] is True, "monitored reflects the CURRENT version's ingest_status, not the pending v2's"

    gone = by["DOC-000003"]
    assert gone["lifecycle_state"] == "retired"
    assert (gone["latest_version_no"], gone["latest_version_status"], gone["latest_ingest_status"]) == (None, None, None)
