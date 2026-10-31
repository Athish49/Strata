"""Task 5.7 — ingest jobs, failure semantics and recovery (TDD §6.2, §6.3).

Runs against a throwaway local PostgreSQL cluster (initdb in a pytest tmp dir,
unix socket only, torn down afterwards), loaded from
``tests/engine/fixtures/company_schema.sql``.  It never connects to
DATABASE_URL: an autouse fixture makes ``jobs._default_session_factory`` raise,
so a test that forgets to inject the scratch factory fails instead of touching
production.  R2 is ``moto``.  ``service.ingest_document`` is replaced by fakes
that take its real keyword contract and write real rows through the session
they are given, so rollback behaviour is exercised against real Postgres.
"""
from __future__ import annotations

import hashlib
import shutil
import socket
import subprocess
import uuid
from pathlib import Path

import boto3
import pytest
from fastapi import BackgroundTasks
from moto import mock_aws
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.company_ingest.store.r2 as r2_mod
from app.company_ingest import jobs
from app.company_ingest.extract import DocxExtractor, anchor_clauses
from app.company_ingest.hashing import content_hash
from app.company_ingest.service import CitationResolutionError, IngestError, IngestResult

pytestmark = pytest.mark.asyncio

BACKEND = Path(__file__).resolve().parents[2]
SCHEMA_SQL = BACKEND / "tests" / "engine" / "fixtures" / "company_schema.sql"
# A test-owned, byte-identical copy of a seeded corpus render, so these tests keep
# running when backend/synthetic/ is deleted (task 9.4 deletability gate).
DOCX_FIXTURE = BACKEND / "tests" / "fixtures" / "docx" / "RPL-CS-PRO-004_v5.1.docx"
CO = "co"
H1 = hashlib.sha256(b"content-1").hexdigest()
H2 = hashlib.sha256(b"content-2").hexdigest()


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
    import psycopg2

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
        con = psycopg2.connect(host=str(sock), port=port, user="postgres", dbname="postgres")
        con.autocommit = True
        con.cursor().execute(SCHEMA_SQL.read_text())
        con.close()
        yield f"postgresql+asyncpg://postgres@/postgres?host={sock}&port={port}"
    finally:
        subprocess.run([pg_ctl, "-D", str(data), "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(sock, ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_production_db(monkeypatch):
    def _refuse():
        raise AssertionError("test reached the production session factory")

    monkeypatch.setattr(jobs, "_default_session_factory", _refuse)


@pytest.fixture
async def factory(scratch_pg):
    engine = create_async_engine(scratch_pg, poolclass=NullPool)
    async with engine.begin() as c:
        await c.execute(text(
            "TRUNCATE company.ingest_jobs, company.company_documents, "
            "company.document_versions, company.clauses"))
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


# --------------------------------------------------------------------------- helpers
async def _upload(factory, doc_id: str, *, h: str = H1, first: bool = True,
                  source_r2_key: str | None = None, register_spec=None) -> tuple[str, str]:
    """Mimic task 6.1 step 7: doc (+ reserved hash) + version + job in ONE
    transaction, committed.  For ``first=False`` the document already has a
    current version and a live hash; a version 2 is added."""
    vid = str(uuid.uuid4())
    async with factory() as s:
        if first:
            await s.execute(text(
                "INSERT INTO company.company_documents (company_id, doc_id, title, "
                "current_content_hash, lifecycle_state) VALUES (:c, :d, :d, :h, 'pending')"),
                {"c": CO, "d": doc_id, "h": h})
            vno = 1
        else:
            v1 = str(uuid.uuid4())
            await s.execute(text(
                "INSERT INTO company.company_documents (company_id, doc_id, title, "
                "current_content_hash, lifecycle_state, current_version_id) "
                "VALUES (:c, :d, :d, :h, 'active', CAST(:v1 AS uuid))"),
                {"c": CO, "d": doc_id, "h": h, "v1": v1})
            await s.execute(text(
                "INSERT INTO company.document_versions (version_id, company_id, doc_id, version_no, "
                "status, is_current, ingest_status) "
                "VALUES (CAST(:v AS uuid), :c, :d, 1, 'effective', true, 'ingested')"),
                {"v": v1, "c": CO, "d": doc_id})
            vno = 2
        await s.execute(text(
            "INSERT INTO company.document_versions (version_id, company_id, doc_id, version_no, "
            "status, is_current, ingest_status, source_r2_key) "
            "VALUES (CAST(:v AS uuid), :c, :d, :n, 'in_review', false, 'pending', :k)"),
            {"v": vid, "c": CO, "d": doc_id, "n": vno, "k": source_r2_key})
        job_id = await jobs.create_job(s, company_id=CO, doc_id=doc_id, version_id=vid,
                                       register_spec=register_spec)
        await s.commit()
    return job_id, vid


async def _one(factory, sql: str, **params):
    async with factory() as s:
        return (await s.execute(text(sql), params)).mappings().first()


async def _clause_count(factory, vid: str) -> int:
    row = await _one(factory, "SELECT count(*) AS n FROM company.clauses "
                              "WHERE version_id = CAST(:v AS uuid)", v=vid)
    return row["n"]


async def _write_like_service(session, *, company_id, doc_id, version_id) -> None:
    # Stage 0 of the real service upserts the version row (taking its lock),
    # then commit_run writes clauses — all in the caller's session.
    await session.execute(text(
        "UPDATE company.document_versions SET ingest_status = 'ingested' "
        "WHERE version_id = CAST(:v AS uuid)"), {"v": version_id})
    await session.execute(text(
        "INSERT INTO company.clauses (clause_pk, company_id, version_id, doc_id, clause_id) "
        "VALUES (CAST(:pk AS uuid), :c, CAST(:v AS uuid), :d, :cid)"),
        {"pk": str(uuid.uuid4()), "c": company_id, "v": version_id, "d": doc_id,
         "cid": f"{doc_id}:1"})


def _ok_ingest(seen: dict | None = None):
    async def fake(*, company_id, doc_id, version_id, markdown, register_spec, session, ctx, **kw):
        assert ctx.company_id == company_id
        if seen is not None:
            seen["markdown"] = markdown
            seen["register_spec"] = register_spec
        await _write_like_service(session, company_id=company_id, doc_id=doc_id,
                                  version_id=version_id)
        return IngestResult(version_id=version_id, clause_count=1, citations_resolved=2,
                            llm_calls=3, llm_cache_hits=4)
    return fake


def _failing_ingest(exc_factory):
    async def fake(*, company_id, doc_id, version_id, markdown, register_spec, session, ctx, **kw):
        await _write_like_service(session, company_id=company_id, doc_id=doc_id,
                                  version_id=version_id)
        raise exc_factory()
    return fake


def _anchor_value_error():
    try:
        anchor_clauses("# Heading\n\nbody\n", "bad id: with spaces")
    except ValueError as exc:
        return exc
    raise AssertionError("anchor_clauses accepted an invalid doc_id")


# --------------------------------------------------------------------------- tests
async def test_job_row_is_queued_before_task_starts(factory):
    job_id, vid = await _upload(factory, "DOC-000001")
    tasks = BackgroundTasks()
    tasks.add_task(jobs.run_ingest_job, job_id, markdown="# x\n", session_factory=factory,
                   ingest_fn=_ok_ingest())

    # What a poll between the 202 and the task start sees: a row, not a 404.
    polled = await jobs.get_job(job_id, session_factory=factory)
    assert polled is not None and polled.state == jobs.JOB_QUEUED
    assert polled.started_at is None

    await tasks()

    done = await jobs.get_job(job_id, session_factory=factory)
    assert done.state == jobs.JOB_SUCCEEDED and done.error is None
    assert done.started_at is not None and done.finished_at is not None
    for key, val in {"clause_count": 1, "citations_resolved": 2, "llm_calls": 3,
                     "llm_cache_hits": 4}.items():
        assert done.stats[key] == val
    assert await _clause_count(factory, vid) == 1
    # Success leaves the reservation alone: promotion (5.6) owns the hash from here.
    doc = await _one(factory, "SELECT current_content_hash, lifecycle_state FROM "
                              "company.company_documents WHERE doc_id = 'DOC-000001'")
    assert doc["current_content_hash"] == H1 and doc["lifecycle_state"] == "pending"


@pytest.mark.parametrize("make_exc", [
    lambda: IngestError("segmentation produced no clauses"),
    lambda: CitationResolutionError("0 resolved"),
    _anchor_value_error,
], ids=["IngestError", "CitationResolutionError", "anchor_ValueError"])
async def test_failure_releases_hash_and_same_file_is_accepted(factory, make_exc):
    job_id, vid = await _upload(factory, "DOC-000002")

    # The reservation is real: while pending, the same content is rejected.
    async with factory() as s:
        with pytest.raises(IntegrityError):
            await s.execute(text(
                "INSERT INTO company.company_documents (company_id, doc_id, current_content_hash, "
                "lifecycle_state) VALUES (:c, 'DOC-000099', :h, 'pending')"), {"c": CO, "h": H1})

    job = await jobs.run_ingest_job(job_id, markdown="# x\n", session_factory=factory,
                                    ingest_fn=_failing_ingest(make_exc))

    # Failed status survived the ingest rollback, and the rollback happened.
    assert job.state == jobs.JOB_FAILED
    assert type(make_exc()).__name__ in job.error
    assert await _clause_count(factory, vid) == 0
    doc = await _one(factory, "SELECT current_content_hash, lifecycle_state FROM "
                              "company.company_documents WHERE doc_id = 'DOC-000002'")
    assert doc["current_content_hash"] is None
    assert doc["lifecycle_state"] == jobs.LIFECYCLE_FAILED
    ver = await _one(factory, "SELECT status, ingest_status, is_current FROM "
                              "company.document_versions WHERE version_id = CAST(:v AS uuid)", v=vid)
    assert ver["ingest_status"] == "failed" and ver["status"] == "in_review"
    assert ver["is_current"] is False

    # Re-uploading the same file is accepted: the 6.1 hash lookup finds nothing
    # and the partial unique index lets the new reservation through.
    hit = await _one(factory, "SELECT doc_id FROM company.company_documents "
                              "WHERE company_id = :c AND current_content_hash = :h", c=CO, h=H1)
    assert hit is None
    job2, _ = await _upload(factory, "DOC-000003", h=H1)
    assert (await jobs.get_job(job2, session_factory=factory)).state == jobs.JOB_QUEUED


async def test_unexpected_exception_also_fails_the_job(factory):
    job_id, vid = await _upload(factory, "DOC-000004")
    job = await jobs.run_ingest_job(job_id, markdown="# x\n", session_factory=factory,
                                    ingest_fn=_failing_ingest(lambda: KeyError("boom")))
    assert job.state == jobs.JOB_FAILED and "KeyError" in job.error
    assert await _clause_count(factory, vid) == 0


async def test_later_version_failure_leaves_in_review_and_hash(factory):
    job_id, vid = await _upload(factory, "DOC-000005", h=H2, first=False)
    job = await jobs.run_ingest_job(job_id, markdown="# x\n", session_factory=factory,
                                    ingest_fn=_failing_ingest(lambda: IngestError("x")))
    assert job.state == jobs.JOB_FAILED
    doc = await _one(factory, "SELECT current_content_hash, lifecycle_state FROM "
                              "company.company_documents WHERE doc_id = 'DOC-000005'")
    assert doc["current_content_hash"] == H2 and doc["lifecycle_state"] == "active"
    ver = await _one(factory, "SELECT status FROM company.document_versions "
                              "WHERE version_id = CAST(:v AS uuid)", v=vid)
    assert ver["status"] == "in_review"


async def test_startup_sweep_reclaims_orphaned_running_job(factory, monkeypatch):
    old_job, old_vid = await _upload(factory, "DOC-000006", h=H1)
    fresh_job, _ = await _upload(factory, "DOC-000007", h=H2)
    async with factory() as s:
        await s.execute(text("UPDATE company.ingest_jobs SET state = 'running', "
                             "started_at = now() - interval '30 minutes' "
                             "WHERE job_id = CAST(:j AS uuid)"), {"j": old_job})
        await s.execute(text("UPDATE company.ingest_jobs SET state = 'running', started_at = now() "
                             "WHERE job_id = CAST(:j AS uuid)"), {"j": fresh_job})
        await s.commit()

    # The real startup hook, pointed at the scratch cluster.
    monkeypatch.setattr(jobs, "_default_session_factory", lambda: factory)
    monkeypatch.setenv("INGEST_JOB_STALE_MINUTES", "15")
    from app import main

    async with main._lifespan(main.app):
        pass

    old = await jobs.get_job(old_job, session_factory=factory)
    assert old.state == jobs.JOB_FAILED and old.error.startswith("orphaned: running")
    assert (await jobs.get_job(fresh_job, session_factory=factory)).state == jobs.JOB_RUNNING
    doc = await _one(factory, "SELECT current_content_hash, lifecycle_state FROM "
                              "company.company_documents WHERE doc_id = 'DOC-000006'")
    assert doc["current_content_hash"] is None and doc["lifecycle_state"] == jobs.LIFECYCLE_FAILED
    still = await _one(factory, "SELECT current_content_hash FROM company.company_documents "
                                "WHERE doc_id = 'DOC-000007'")
    assert still["current_content_hash"] == H2

    # reclaim_if_stale (for the 6.4 poll path) only touches the one job.
    assert (await jobs.reclaim_if_stale(fresh_job, session_factory=factory)).state == jobs.JOB_RUNNING
    reclaimed = await jobs.reclaim_if_stale(fresh_job, stale_minutes=0, session_factory=factory)
    assert reclaimed.state == jobs.JOB_FAILED


async def test_startup_sweep_never_raises(monkeypatch):
    # Default factory raises (autouse fixture) -> logged, not propagated.
    await jobs.startup_sweep()


async def test_sweep_wins_race_against_inflight_ingest(factory):
    job_id, vid = await _upload(factory, "DOC-000008")

    async def ingest_then_get_reclaimed(*, session, version_id, doc_id, company_id, **kw):
        # Sweep first: in one event loop it would otherwise wait on the version
        # row lock this transaction is about to take (another process would
        # simply wait for the ingest to finish).
        await jobs.sweep_orphaned_jobs(stale_minutes=0, session_factory=factory)
        await _write_like_service(session, company_id=company_id, doc_id=doc_id,
                                  version_id=version_id)
        return IngestResult(version_id=version_id, clause_count=1, citations_resolved=0,
                            llm_calls=0, llm_cache_hits=0)

    job = await jobs.run_ingest_job(job_id, markdown="# x\n", session_factory=factory,
                                    ingest_fn=ingest_then_get_reclaimed)
    assert job.state == jobs.JOB_FAILED and job.error.startswith("orphaned")
    assert await _clause_count(factory, vid) == 0   # the late success was discarded


@pytest.fixture
def r2():
    with mock_aws():
        def client():
            return boto3.client("s3", region_name="us-east-1",
                                aws_access_key_id="k", aws_secret_access_key="s")
        client().create_bucket(Bucket="test-bucket")
        mp = pytest.MonkeyPatch()
        mp.setattr(r2_mod, "_get_client", client)
        mp.setattr(r2_mod.settings, "R2_BUCKET_NAME", "test-bucket")
        try:
            yield r2_mod
        finally:
            mp.undo()


async def test_retry_completes_from_r2_raw_bytes(factory, r2):
    raw = DOCX_FIXTURE.read_bytes()
    key = f"company/{CO}/raw/DOC-000009/1/source.docx"
    r2.put_bytes(key, raw, {"content_type": "docx", "doc_id": "DOC-000009", "version": "1",
                            "profile": "upload"})
    expected_md = DocxExtractor().extract(raw).markdown
    h = content_hash(expected_md)

    job_id, vid = await _upload(factory, "DOC-000009", h=h, source_r2_key=key)
    failed = await jobs.run_ingest_job(job_id, markdown=expected_md, session_factory=factory,
                                       ingest_fn=_failing_ingest(lambda: IngestError("x")))
    assert failed.state == jobs.JOB_FAILED

    seen: dict = {}
    done = await jobs.retry_job(job_id, session_factory=factory, ingest_fn=_ok_ingest(seen))

    assert seen["markdown"] == expected_md   # re-extracted from R2, no re-upload
    assert done.job_id == job_id and done.state == jobs.JOB_SUCCEEDED
    assert done.stats["clause_count"] == 1
    assert await _clause_count(factory, vid) == 1
    doc = await _one(factory, "SELECT current_content_hash, lifecycle_state FROM "
                              "company.company_documents WHERE doc_id = 'DOC-000009'")
    assert doc["current_content_hash"] == h and doc["lifecycle_state"] == jobs.LIFECYCLE_PENDING

    # Only failed jobs can be retried.
    with pytest.raises(jobs.JobStateError):
        await jobs.retry_job(job_id, session_factory=factory, ingest_fn=_ok_ingest())


async def test_retry_refused_when_hash_taken_meanwhile(factory, r2):
    raw = DOCX_FIXTURE.read_bytes()
    key = f"company/{CO}/raw/DOC-000010/1/source.docx"
    r2.put_bytes(key, raw, {"content_type": "docx", "doc_id": "DOC-000010", "version": "1",
                            "profile": "upload"})
    h = content_hash(DocxExtractor().extract(raw).markdown)
    job_id, _ = await _upload(factory, "DOC-000010", h=h, source_r2_key=key)
    await jobs.run_ingest_job(job_id, markdown="# x\n", session_factory=factory,
                              ingest_fn=_failing_ingest(lambda: IngestError("x")))
    await _upload(factory, "DOC-000011", h=h)   # customer re-uploaded as a new document

    with pytest.raises(jobs.RetryError):
        await jobs.retry_job(job_id, session_factory=factory, ingest_fn=_ok_ingest())
    assert (await jobs.get_job(job_id, session_factory=factory)).state == jobs.JOB_FAILED


async def test_v2_failure_while_v1_pending_keeps_v1_reservation(factory, r2):
    """v1 ingested but still in review (document 'pending', no current version);
    a failing v2 must not release v1's hash, and a v2 retry must not overwrite it."""
    _, v1 = await _upload(factory, "DOC-000012", h=H1)
    async with factory() as s:
        await s.execute(text("UPDATE company.document_versions SET ingest_status = 'ingested' "
                             "WHERE version_id = CAST(:v AS uuid)"), {"v": v1})
        await s.execute(text("UPDATE company.ingest_jobs SET state = 'succeeded'"))
        await s.commit()

    raw = DOCX_FIXTURE.read_bytes()
    key = f"company/{CO}/raw/DOC-000012/2/source.docx"
    r2.put_bytes(key, raw, {"content_type": "docx", "doc_id": "DOC-000012", "version": "2",
                            "profile": "upload"})
    v2 = str(uuid.uuid4())
    async with factory() as s:
        await s.execute(text(
            "INSERT INTO company.document_versions (version_id, company_id, doc_id, version_no, "
            "status, ingest_status, source_r2_key) "
            "VALUES (CAST(:v AS uuid), :c, 'DOC-000012', 2, 'in_review', 'pending', :k)"),
            {"v": v2, "c": CO, "k": key})
        job2 = await jobs.create_job(s, company_id=CO, doc_id="DOC-000012", version_id=v2)
        await s.commit()

    failed = await jobs.run_ingest_job(job2, markdown="# x\n", session_factory=factory,
                                       ingest_fn=_failing_ingest(lambda: IngestError("x")))
    assert failed.state == jobs.JOB_FAILED
    sql = ("SELECT current_content_hash, lifecycle_state FROM company.company_documents "
           "WHERE doc_id = 'DOC-000012'")
    doc = await _one(factory, sql)
    assert doc["current_content_hash"] == H1 and doc["lifecycle_state"] == jobs.LIFECYCLE_PENDING

    done = await jobs.retry_job(job2, session_factory=factory, ingest_fn=_ok_ingest())
    assert done.state == jobs.JOB_SUCCEEDED
    doc = await _one(factory, sql)
    assert doc["current_content_hash"] == H1 and doc["lifecycle_state"] == jobs.LIFECYCLE_PENDING


# --------------------------------------------------------------------------- task 3.2
REGISTER_CSV = "ref,citation\nR-1,170 IAC 4-1-16\nR-2,170 IAC 4-1-17\n"


async def test_register_upload_retries_from_stored_spec(factory, r2):
    """Task 3.2: create_job stores the RegisterSpec on the job row, so a failed
    register-CSV upload is retryable from the R2 bytes alone (previously
    _markdown_from_raw always raised RetryError for a .csv)."""
    from app.company_ingest.register_spec import RegisterSpec

    spec = RegisterSpec(register_type="obligation", id_column="ref",
                        citation_columns=["citation"])
    raw = REGISTER_CSV.encode("utf-8")
    key = f"company/{CO}/raw/DOC-000013/1/source.csv"
    r2.put_bytes(key, raw, {"content_type": "csv", "doc_id": "DOC-000013", "version": "1",
                            "profile": "upload"})
    h = content_hash(REGISTER_CSV)
    job_id, vid = await _upload(factory, "DOC-000013", h=h, source_r2_key=key,
                                register_spec=spec)
    stored = await _one(factory, "SELECT register_spec FROM company.ingest_jobs "
                                 "WHERE job_id = CAST(:j AS uuid)", j=job_id)
    assert stored["register_spec"] is not None

    failed = await jobs.run_ingest_job(job_id, markdown=REGISTER_CSV, register_spec=spec,
                                       session_factory=factory,
                                       ingest_fn=_failing_ingest(lambda: IngestError("x")))
    assert failed.state == jobs.JOB_FAILED

    seen: dict = {}
    done = await jobs.retry_job(job_id, session_factory=factory, ingest_fn=_ok_ingest(seen))
    assert done.state == jobs.JOB_SUCCEEDED and done.job_id == job_id
    assert seen["register_spec"] == spec            # read back from the job row
    assert seen["markdown"] == REGISTER_CSV         # the raw CSV text from R2
    assert await _clause_count(factory, vid) == 1
    doc = await _one(factory, "SELECT current_content_hash, lifecycle_state FROM "
                              "company.company_documents WHERE doc_id = 'DOC-000013'")
    assert doc["current_content_hash"] == h and doc["lifecycle_state"] == jobs.LIFECYCLE_PENDING
    # The requeue keeps the spec for any later retry.
    again = await _one(factory, "SELECT register_spec FROM company.ingest_jobs "
                                "WHERE job_id = CAST(:j AS uuid)", j=job_id)
    assert again["register_spec"] is not None


async def test_register_retry_explicit_spec_overrides_and_missing_spec_is_refused(factory, r2):
    from app.company_ingest.register_spec import RegisterSpec

    raw = REGISTER_CSV.encode("utf-8")
    key = f"company/{CO}/raw/DOC-000014/1/source.csv"
    r2.put_bytes(key, raw, {"content_type": "csv", "doc_id": "DOC-000014", "version": "1",
                            "profile": "upload"})
    job_id, _ = await _upload(factory, "DOC-000014", h=content_hash(REGISTER_CSV),
                              source_r2_key=key)       # no spec stored (pre-3.2 row)
    await jobs.run_ingest_job(job_id, markdown=REGISTER_CSV, session_factory=factory,
                              ingest_fn=_failing_ingest(lambda: IngestError("x")))
    with pytest.raises(jobs.RetryError, match="register_spec"):
        await jobs.prepare_retry(job_id, session_factory=factory)
    assert (await jobs.get_job(job_id, session_factory=factory)).state == jobs.JOB_FAILED

    override = RegisterSpec(register_type="event", id_column="ref")
    seen: dict = {}
    done = await jobs.retry_job(job_id, register_spec=override, session_factory=factory,
                                ingest_fn=_ok_ingest(seen))
    assert done.state == jobs.JOB_SUCCEEDED and seen["register_spec"] == override
