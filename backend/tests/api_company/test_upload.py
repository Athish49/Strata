"""Tasks 6.1 / 6.2 — POST /company/documents and POST /company/documents/{doc_id}/versions.

Two harnesses:

* Guard tests (413 / 415 / 422) run against a scripted FakeSession (idiom of
  ``tests/engine/test_api_routes.py``): they must reject before any extraction
  or write, so the fake asserts no INSERT / UPDATE was ever issued.
* Everything that writes runs against a throwaway local PostgreSQL cluster
  (pattern of ``tests/company_ingest/test_jobs_recovery.py``) loaded from
  ``tests/engine/fixtures/company_schema.sql`` — real unique indexes, real
  advisory locks, real row counts.

Never touches production: ``jobs`` / ``store.commit`` default session factories
are replaced by a refusal, ``get_db`` and ``get_upload_deps`` are overridden,
R2 is ``moto``, and ``service.ingest_document`` is a fake that takes its real
keyword contract.  httpx's ASGITransport does not run the lifespan, so the
startup sweep never fires; it does run BackgroundTasks before returning.
"""
from __future__ import annotations

import ast
import asyncio
import base64
import hashlib
import io
import shutil
import socket
import subprocess
import uuid
from pathlib import Path

import boto3
import docx
import httpx
import pytest
from moto import mock_aws
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.company_ingest.store.commit as commit_mod
import app.company_ingest.store.r2 as r2_mod
from app.api.company import upload
from app.company_ingest import jobs
from app.company_ingest.hashing import content_hash
from app.company_ingest.service import IngestError, IngestResult
from app.db import get_db
from app.engine.config import engine_settings
from app.main import app

pytestmark = pytest.mark.asyncio

BACKEND = Path(__file__).resolve().parents[2]
SCHEMA_SQL = BACKEND / "tests" / "engine" / "fixtures" / "company_schema.sql"


def _migration_vertical_rows() -> list[dict]:
    """``company.verticals`` row shape (name, slug), read from the verticals-retaxonomy
    migration's ``NEW_VERTICALS`` with ``ast`` -- no DB connection, no second hand-synced
    copy of the 14 verticals. ``routes.fetch_vertical_slugs()`` issues this exact query,
    and ``FakeSession`` below answers it with these rows by default."""
    migrations_dir = BACKEND / "migrations" / "versions"
    candidates = [p for p in migrations_dir.glob("*.py")
                  if "verticals_retaxonomy" in p.name or "retaxonomy" in p.name]
    assert candidates, "verticals-retaxonomy migration file not found"
    tree = ast.parse(candidates[0].read_text(encoding="utf-8"))
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
        if any(isinstance(t, ast.Name) and t.id == "NEW_VERTICALS" for t in targets):
            rows = ast.literal_eval(node.value)
            return [{"name": n, "slug": s} for n, s, _d in rows]
    raise AssertionError("NEW_VERTICALS not found in verticals-retaxonomy migration")


#: Rule for ``routes.fetch_vertical_slugs()``'s ``SELECT name, slug FROM company.verticals``.
VERTICALS_SQL_RULE = ("FROM company.verticals", _migration_vertical_rows())
CO = engine_settings.ENGINE_COMPANY_ID
PID = "P-UPLOADER"
VERTICAL = "Compliance & Ethics"
BUCKET = "test-bucket"
DOCX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

TEXT_A = [
    ("Heading 1", "Customer Service Procedure"),
    (None, "This procedure governs how customer complaints are received, logged and resolved "
           "within the regulated time limits set by the commission."),
    ("Heading 2", "1. Intake"),
    (None, "Every complaint is logged within one business day of receipt."),
]
TEXT_B = TEXT_A + [(None, "Escalations go to the compliance officer within five business days.")]
TEXT_C = [
    ("Heading 1", "Records Retention Policy"),
    (None, "Customer account records are retained for seven years after the account closes, "
           "consistent with the applicable administrative code."),
]


# --------------------------------------------------------------------------- builders
def make_docx(paras=TEXT_A, *, author: str = "Alice", image_only: bool = False) -> bytes:
    d = docx.Document()
    d.core_properties.author = author
    if image_only:
        d.add_picture(io.BytesIO(PNG_1X1))
    else:
        for style, body in paras:
            if style and style.startswith("Heading"):
                d.add_heading(body, level=int(style.split()[-1]))
            else:
                d.add_paragraph(body)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def docx_file(raw: bytes, name: str = "policy.docx"):
    return {"file": (name, raw, DOCX_CT)}


def form(**extra):
    base = {"vertical": VERTICAL, "acting_person_id": PID, "title": "Customer Service Procedure"}
    base.update(extra)
    return base


REGISTER_CSV = (
    "﻿obligation_id,obligation,citation\n"
    "OB-1,File the annual report with the commission,170 IAC 1-1-1\n"
    "OB-2,Retain complaint logs for three years,170 IAC 1-1-2\n"
).encode("utf-8")


# --------------------------------------------------------------------------- safety
@pytest.fixture(autouse=True)
def _no_production(monkeypatch):
    def _refuse(*a, **k):
        raise AssertionError("test reached a production session factory / Qdrant / model")

    monkeypatch.setattr(jobs, "_default_session_factory", _refuse)
    monkeypatch.setattr(commit_mod, "_default_session_factory", _refuse)
    from app.company_ingest.index import upsert as upsert_mod
    monkeypatch.setattr(upsert_mod, "_make_client", _refuse)
    monkeypatch.setattr(upsert_mod, "embed_texts", _refuse, raising=False)
    real_resolve = upload._resolve_factory

    def _resolve(sf):
        if sf is None:
            _refuse()
        return real_resolve(sf)

    monkeypatch.setattr(upload, "_resolve_factory", _resolve)
    yield
    app.dependency_overrides.clear()


class FakeQdrant:
    """Records upserts / deletes; ``fail`` makes the delete (the sweep) raise."""

    def __init__(self):
        self.ops: list[str] = []
        self.fail = False

    def upsert(self, collection_name, points, wait=False):
        self.ops.append("upsert")

    def delete(self, collection_name, points_selector, wait=False):
        self.ops.append("delete")
        if self.fail:
            raise ConnectionError("qdrant unreachable")


@pytest.fixture
def r2():
    with mock_aws():
        def client():
            return boto3.client("s3", region_name="us-east-1",
                                aws_access_key_id="k", aws_secret_access_key="s")
        client().create_bucket(Bucket=BUCKET)
        mp = pytest.MonkeyPatch()
        mp.setattr(r2_mod, "_get_client", client)
        mp.setattr(r2_mod.settings, "R2_BUCKET_NAME", BUCKET)
        try:
            yield r2_mod
        finally:
            mp.undo()


def r2_keys(r2) -> list[str]:
    res = r2._get_client().list_objects_v2(Bucket=BUCKET)
    return sorted(o["Key"] for o in res.get("Contents", []))


# --------------------------------------------------------------------------- fake ingest
class Ingest:
    """Fake ``service.ingest_document``: real keyword contract, writes through
    the session it is given.  ``fail`` makes it raise IngestError."""

    def __init__(self):
        self.fail = False
        self.calls: list[dict] = []

    async def __call__(self, *, company_id, doc_id, version_id, markdown, register_spec,
                       session, ctx, **kw):
        assert ctx.company_id == company_id == CO
        self.calls.append({"doc_id": doc_id, "version_id": version_id, "markdown": markdown,
                           "register_spec": register_spec, "run_id": str(ctx.run_id), **kw})
        await session.execute(text(
            "UPDATE company.document_versions SET ingest_status = 'ingested' "
            "WHERE version_id = CAST(:v AS uuid)"), {"v": version_id})
        if self.fail:
            raise IngestError("forced failure")
        return IngestResult(version_id=version_id, clause_count=3, citations_resolved=1,
                            llm_calls=0, llm_cache_hits=0)


# --------------------------------------------------------------------------- FakeSession harness
class _Res:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return next(iter(self._rows[0].values())) if self._rows else None


class FakeSession:
    def __init__(self, rules=()):
        self.rules = list(rules) + [
            ("FROM company.people", [{"person_id": PID, "is_active": True}]),
            VERTICALS_SQL_RULE,
        ]
        self.sql: list[str] = []
        self.committed = 0

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.sql.append(sql)
        for key, rows in self.rules:
            if key in sql:
                return _Res(rows)
        return _Res([])

    async def commit(self):
        self.committed += 1

    async def rollback(self):
        pass

    def writes(self):
        return [s for s in self.sql if any(w in s for w in ("INSERT", "UPDATE", "DELETE"))]


@pytest.fixture
def fake(r2):
    sess = FakeSession()
    ingest = Ingest()

    async def _db():
        yield sess

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[upload.get_upload_deps] = lambda: upload.UploadDeps(
        session_factory=None, r2=r2, ingest_fn=ingest)
    return sess


@pytest.fixture
def no_extract(monkeypatch):
    calls = []

    def _boom(*a, **k):
        calls.append(1)
        raise AssertionError("extraction must not run")

    monkeypatch.setattr(upload, "_extract_docx", _boom)
    return calls


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


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


@pytest.fixture
async def factory(scratch_pg):
    engine = create_async_engine(scratch_pg, poolclass=NullPool)
    async with engine.begin() as c:
        await c.execute(text(
            "TRUNCATE company.ingest_jobs, company.company_documents, company.document_versions, "
            "company.clauses, company.people, company.ingest_runs, company.approval_requests, "
            "company.approval_steps, company.approval_policies, company.approval_policy_steps, "
            "company.document_role_assignments"))
        await c.execute(text("INSERT INTO company.people (company_id, person_id, name) "
                             "VALUES (:c, :p, 'Uploader')"), {"c": CO, "p": PID})
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def qdrant():
    return FakeQdrant()


@pytest.fixture
def pg(factory, r2, qdrant):
    ingest = Ingest()

    async def _db():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[upload.get_upload_deps] = lambda: upload.UploadDeps(
        session_factory=factory, r2=r2, ingest_fn=ingest, qdrant_client=qdrant)
    return factory, ingest


async def q(factory, sql: str, **params):
    async with factory() as s:
        return [dict(r) for r in (await s.execute(text(sql), params)).mappings().all()]


async def counts(factory) -> dict:
    out = {}
    for t in ("company_documents", "document_versions", "ingest_jobs", "approval_requests"):
        out[t] = (await q(factory, f"SELECT count(*) AS n FROM company.{t}"))[0]["n"]
    return out


async def post_doc(c, raw, name="policy.docx", **f):
    return await c.post("/company/documents", files=docx_file(raw, name), data=form(**f))


async def post_version(c, doc_id, raw, name="policy.docx", **f):
    data = {"acting_person_id": PID, **f}
    return await c.post(f"/company/documents/{doc_id}/versions", files=docx_file(raw, name), data=data)


async def add_policy(factory, doc_id: str | None = None) -> str:
    """A one-step (owner) default policy, so uploads open an approval request
    and the version stays in_review after its ingest."""
    pol = str(uuid.uuid4())
    async with factory() as s:
        await s.execute(text("INSERT INTO company.approval_policies (company_id, policy_id, name) "
                             "VALUES (:c, CAST(:p AS uuid), 'default')"), {"c": CO, "p": pol})
        await s.execute(text("INSERT INTO company.approval_policy_steps (policy_id, step_no, required_role) "
                             "VALUES (CAST(:p AS uuid), 1, 'owner')"), {"p": pol})
        if doc_id:
            await s.execute(text("INSERT INTO company.document_role_assignments "
                                 "(company_id, doc_id, person_id, role) VALUES (:c, :d, :p, 'owner')"),
                            {"c": CO, "d": doc_id, "p": PID})
        await s.commit()
    return pol


async def version_row(factory, version_id: str) -> dict:
    return (await q(factory, "SELECT * FROM company.document_versions WHERE version_id = CAST(:v AS uuid)",
                    v=version_id))[0]


# =========================================================================== 6.1 guards (FakeSession)
async def test_pdf_is_415_before_extraction_or_any_write(fake, r2, no_extract):
    async with _client() as c:
        r = await c.post("/company/documents", data=form(),
                         files={"file": ("policy.pdf", b"%PDF-1.7\n...", "application/pdf")})
        # A PDF renamed to .docx is still refused (magic bytes).
        r2_ = await c.post("/company/documents", data=form(),
                           files={"file": ("sneaky.docx", b"%PDF-1.4 x", DOCX_CT)})
        r3 = await c.post("/company/documents", data=form(),
                          files={"file": ("notes.txt", b"hello", "text/plain")})
    for resp in (r, r2_, r3):
        assert resp.status_code == 415
        assert "docx" in resp.json()["detail"].lower() and "PDF is not yet available" in resp.json()["detail"]
    assert no_extract == []
    assert fake.sql == [] and fake.committed == 0
    assert r2_keys(r2) == []


async def test_image_only_docx_is_422_twice_not_409(fake, r2):
    raw1 = make_docx(image_only=True, author="A")
    raw2 = make_docx(image_only=True, author="B")
    assert raw1 != raw2
    async with _client() as c:
        a = await post_doc(c, raw1, "scan1.docx")
        b = await post_doc(c, raw2, "scan2.docx")
    assert a.status_code == 422 and b.status_code == 422
    assert a.json()["detail"] == b.json()["detail"] == upload.MSG_EMPTY
    assert fake.sql == [] and r2_keys(r2) == []


async def test_register_csv_without_spec_is_422(fake, r2):
    async with _client() as c:
        r = await c.post("/company/documents", data=form(),
                         files={"file": ("register.csv", REGISTER_CSV, "text/csv")})
    assert r.status_code == 422 and "register_spec" in r.json()["detail"]
    assert fake.sql == [] and r2_keys(r2) == []


async def test_register_csv_with_bad_id_column_is_422(fake, r2):
    async with _client() as c:
        bad_col = await c.post("/company/documents", data=form(
            register_spec='{"register_type":"obligation","id_column":"nope"}'),
            files={"file": ("register.csv", REGISTER_CSV, "text/csv")})
        bad_json = await c.post("/company/documents", data=form(register_spec='{"register_type":'),
                                files={"file": ("register.csv", REGISTER_CSV, "text/csv")})
        spec_on_docx = await c.post("/company/documents", data=form(
            register_spec='{"register_type":"obligation","id_column":"obligation_id"}'),
            files=docx_file(make_docx()))
        cp1252 = await c.post("/company/documents", data=form(
            register_spec='{"register_type":"obligation","id_column":"obligation_id"}'),
            files={"file": ("r.csv", "obligation_id,x\nOB-1,caf\xe9\n".encode("cp1252"), "text/csv")})
    assert bad_col.status_code == 422 and "nope" in bad_col.json()["detail"]
    assert bad_json.status_code == 422
    assert spec_on_docx.status_code == 422
    assert cp1252.status_code == 422 and "UTF-8" in cp1252.json()["detail"]
    assert fake.writes() == [] and r2_keys(r2) == []


async def test_oversize_is_413(fake, r2, monkeypatch, no_extract):
    monkeypatch.setattr(upload, "MAX_UPLOAD_BYTES", 1024)
    async with _client() as c:
        r = await post_doc(c, b"x" * 2048)
    assert r.status_code == 413
    assert no_extract == [] and fake.sql == [] and r2_keys(r2) == []


# =========================================================================== 6.1 against Postgres
def _md(raw: bytes) -> str:
    from app.company_ingest.extract import DocxExtractor
    return DocxExtractor().extract(raw).markdown


async def test_new_docx_is_202_rows_job_and_ingest_runs(pg, r2):
    factory, ingest = pg
    await add_policy(factory)      # keeps v1 in_review after ingest (no auto-promotion)
    raw = make_docx()
    async with _client() as c:
        r = await post_doc(c, raw, doc_number="RPL-CS-PRO-004", law_as_of="2025-01-01")
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "processing" and body["doc_id"] == "DOC-000001"
    assert {"doc_id", "version_id", "job_id", "status"} <= set(body)
    assert body["approval_state"] == "open" and body["approval_request_id"]

    md = _md(raw)
    h = content_hash(md)
    doc = (await q(factory, "SELECT * FROM company.company_documents"))[0]
    assert doc["current_content_hash"] == h and doc["lifecycle_state"] == "pending"
    assert doc["vertical"] == VERTICAL and doc["doc_number"] == "RPL-CS-PRO-004"
    assert doc["current_version_id"] is None
    v = await version_row(factory, body["version_id"])
    assert v["version_no"] == 1 and v["status"] == "in_review" and v["is_current"] is False
    assert v["pending_content_hash"] == h and v["created_by_person_id"] == PID
    assert str(v["law_as_of"]) == "2025-01-01" and v["ingest_status"] == "ingested"
    assert v["source_r2_key"].endswith(".docx") and v["source_r2_key"] in r2_keys(r2)
    assert r2._get_client().get_object(Bucket=BUCKET, Key=v["source_r2_key"])["Body"].read() == raw

    job = (await q(factory, "SELECT * FROM company.ingest_jobs"))[0]
    assert str(job["job_id"]) == body["job_id"] and job["state"] == "succeeded"
    assert job["register_spec"] is None
    call = ingest.calls[0]   # UN-anchored markdown, the real raw key, the doc id list
    assert call["markdown"] == md and "<!--" not in call["markdown"]
    assert call["source_r2_key"] == v["source_r2_key"] and call["document_title"]
    assert "DOC-000001" in call["registered_doc_ids"]
    runs = await q(factory, "SELECT * FROM company.ingest_runs")   # task 5.8 pattern
    assert len(runs) == 1 and runs[0]["status"] == "completed"
    assert str(runs[0]["run_id"]) == call["run_id"]


async def test_no_policy_upload_auto_approves_and_promotes_after_ingest(pg, r2, qdrant):
    factory, _ = pg
    raw = make_docx()
    async with _client() as c:
        r = await post_doc(c, raw)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["approval_state"] == "approved"
    v = await version_row(factory, body["version_id"])
    assert v["is_current"] is True and v["status"] == "effective"
    assert v["pending_content_hash"] is None
    doc = (await q(factory, "SELECT * FROM company.company_documents"))[0]
    assert str(doc["current_version_id"]) == body["version_id"]
    assert doc["current_content_hash"] == content_hash(_md(raw)) and doc["lifecycle_state"] == "active"
    job = (await q(factory, "SELECT state FROM company.ingest_jobs"))[0]
    assert job["state"] == "succeeded"
    assert "delete" in qdrant.ops        # promotion's sweep ran on the injected client


async def test_no_policy_upload_whose_ingest_fails_never_promotes(pg, r2, qdrant):
    factory, ingest = pg
    ingest.fail = True
    async with _client() as c:
        r = await post_doc(c, make_docx())
    assert r.status_code == 202
    body = r.json()
    v = await version_row(factory, body["version_id"])        # rows persist
    assert v["is_current"] is False and v["status"] == "in_review" and v["ingest_status"] == "failed"
    doc = (await q(factory, "SELECT * FROM company.company_documents"))[0]
    assert doc["current_version_id"] is None and doc["current_content_hash"] is None   # released
    assert doc["lifecycle_state"] == "failed"
    job = (await q(factory, "SELECT state, error FROM company.ingest_jobs"))[0]
    assert job["state"] == "failed" and "forced failure" in job["error"]
    assert qdrant.ops == []
    runs = await q(factory, "SELECT status FROM company.ingest_runs")
    assert [x["status"] for x in runs] == ["failed"]


async def test_auto_approved_promotion_failure_fails_job_and_leaves_in_review(pg, r2, qdrant):
    factory, _ = pg
    qdrant.fail = True
    async with _client() as c:
        r = await post_doc(c, make_docx())
    assert r.status_code == 202
    v = await version_row(factory, r.json()["version_id"])
    assert v["status"] == "in_review" and v["is_current"] is False
    job = (await q(factory, "SELECT state, error FROM company.ingest_jobs"))[0]
    assert job["state"] == "failed" and "promotion" in job["error"]
    doc = (await q(factory, "SELECT * FROM company.company_documents"))[0]
    assert doc["current_version_id"] is None


async def test_byte_identical_reupload_under_other_name_is_409_storing_nothing(pg, r2):
    factory, _ = pg
    raw = make_docx()
    async with _client() as c:
        first = await post_doc(c, raw, "policy.docx")
        before, keys = await counts(factory), r2_keys(r2)
        dup = await post_doc(c, raw, "renamed copy.docx", title="Totally different title")
    assert first.status_code == 202
    assert dup.status_code == 409
    assert dup.json() == {
        "status": "duplicate",
        "message": "This document is already in the system as 'Customer Service Procedure'.",
        "doc_id": first.json()["doc_id"],
    }
    assert await counts(factory) == before
    assert r2_keys(r2) == keys


async def test_resaved_docx_with_different_bytes_same_wording_is_409(pg, r2):
    factory, _ = pg
    raw1, raw2 = make_docx(author="Alice"), make_docx(author="Bob (re-saved)")
    assert raw1 != raw2
    async with _client() as c:
        assert (await post_doc(c, raw1)).status_code == 202
        before, keys = await counts(factory), r2_keys(r2)
        r = await post_doc(c, raw2, "resaved.docx")
    assert r.status_code == 409 and r.json()["status"] == "duplicate"
    assert await counts(factory) == before and r2_keys(r2) == keys


async def test_duplicate_of_live_candidate_pending_version_is_409(pg, r2):
    """6.1 also checks other documents' in-flight versions' pending hashes."""
    factory, _ = pg
    async with _client() as c:
        d1 = (await post_doc(c, make_docx(TEXT_A))).json()           # auto-promoted (no policy)
        await add_policy(factory, d1["doc_id"])
        v2 = await post_version(c, d1["doc_id"], make_docx(TEXT_B))   # stays in_review
        assert v2.status_code == 202 and v2.json()["approval_state"] == "open"
        before = await counts(factory)
        r = await post_doc(c, make_docx(TEXT_B, author="someone else"), "new.docx")
    assert r.status_code == 409 and r.json()["doc_id"] == d1["doc_id"]
    assert await counts(factory) == before


async def test_unknown_acting_person_is_404_and_stores_nothing(pg, r2):
    factory, _ = pg
    async with _client() as c:
        r = await post_doc(c, make_docx(), acting_person_id="P-NOBODY")
    assert r.status_code == 404
    assert (await counts(factory))["company_documents"] == 0 and r2_keys(r2) == []


async def test_register_csv_202_hashes_decoded_text_and_stores_spec(pg, r2):
    factory, ingest = pg
    await add_policy(factory)
    async with _client() as c:
        r = await c.post("/company/documents", data=form(
            title="Obligations register",
            register_spec='{"register_type":"obligation","id_column":"obligation_id",'
                          '"citation_columns":["citation"]}'),
            files={"file": ("obligations.csv", REGISTER_CSV, "text/csv")})
    assert r.status_code == 202, r.text
    doc = (await q(factory, "SELECT * FROM company.company_documents"))[0]
    assert doc["current_content_hash"] == content_hash(REGISTER_CSV.decode("utf-8-sig"))
    job = (await q(factory, "SELECT register_spec FROM company.ingest_jobs"))[0]
    assert job["register_spec"] is not None
    v = (await q(factory, "SELECT source_r2_key FROM company.document_versions"))[0]
    assert v["source_r2_key"].endswith(".csv")
    assert ingest.calls[0]["register_spec"].id_column == "obligation_id"
    assert ingest.calls[0]["markdown"] == REGISTER_CSV.decode("utf-8-sig")


async def test_doc_ids_are_sequential(pg, r2):
    async with _client() as c:
        a = await post_doc(c, make_docx(TEXT_A))
        b = await post_doc(c, make_docx(TEXT_C), title="Retention")
    assert (a.json()["doc_id"], b.json()["doc_id"]) == ("DOC-000001", "DOC-000002")


@pytest.mark.parametrize("bypass_hash_lock", [False, True], ids=["advisory-lock", "unique-index"])
async def test_two_concurrent_identical_uploads_one_202_one_409(pg, r2, monkeypatch, bypass_hash_lock):
    """Both requests pass the unlocked SELECT together (barrier).  With the
    content-hash advisory lock the loser's re-check sees the winner; with the
    lock bypassed the partial unique index's UniqueViolation must produce the
    same 409.  Either way: one 202, one 409, one row, one raw object."""
    factory, _ = pg
    barrier = asyncio.Barrier(2)

    async def hook():
        await asyncio.wait_for(barrier.wait(), 10)

    monkeypatch.setattr(upload, "_after_dedupe_hook", hook)
    if bypass_hash_lock:
        async def no_lock(db, h):
            return None
        monkeypatch.setattr(upload, "_lock_content_hash", no_lock)

    found: list[bool] = []
    real_holder = upload._holder

    async def spy_holder(db, h, exclude=None):
        res = await real_holder(db, h, exclude)
        found.append(res is not None)
        return res

    monkeypatch.setattr(upload, "_holder", spy_holder)

    raw = make_docx()
    async with _client() as c:
        r1, r2_resp = await asyncio.gather(post_doc(c, raw, "a.docx"), post_doc(c, raw, "b.docx"))
    # advisory lock: 2 unlocked misses, winner's re-check miss, loser's re-check HIT.
    # unique index: 4 misses (both re-checks pass), then the post-UniqueViolation lookup hits.
    assert found == ([False] * 3 + [True] if not bypass_hash_lock else [False] * 4 + [True])
    codes = sorted([r1.status_code, r2_resp.status_code])
    assert codes == [202, 409], (r1.text, r2_resp.text)
    loser = r1 if r1.status_code == 409 else r2_resp
    winner = r2_resp if loser is r1 else r1
    assert loser.json()["status"] == "duplicate" and loser.json()["doc_id"] == winner.json()["doc_id"]
    c_ = await counts(factory)
    assert c_["company_documents"] == 1 and c_["document_versions"] == 1 and c_["ingest_jobs"] == 1
    assert len([k for k in r2_keys(r2) if "/raw/" in k]) == 1


async def test_r2_failure_rolls_back_everything(pg, r2, monkeypatch):
    factory, _ = pg

    def broken_put(*a, **k):
        raise RuntimeError("R2 down")

    monkeypatch.setattr(r2, "put_bytes", broken_put)
    async with _client() as c:
        r = await post_doc(c, make_docx())
    assert r.status_code == 503
    assert await counts(factory) == {"company_documents": 0, "document_versions": 0,
                                     "ingest_jobs": 0, "approval_requests": 0}


# =========================================================================== 6.2 against Postgres
async def _live_doc(c, factory, paras=TEXT_A, *, gated: bool = True) -> dict:
    """A document whose v1 is current (auto-promoted: no policy yet).  With
    *gated*, a one-step policy is then added so later versions stay in_review."""
    d = (await post_doc(c, make_docx(paras), title=paras[0][1])).json()
    assert (await version_row(factory, d["version_id"]))["is_current"] is True
    if gated:
        await add_policy(factory, d["doc_id"])
    return d


async def test_version_unknown_doc_is_404(pg, r2):
    async with _client() as c:
        r = await post_version(c, "DOC-999999", make_docx())
    assert r.status_code == 404


async def test_version_unchanged_is_200_writing_nothing(pg, r2):
    factory, _ = pg
    async with _client() as c:
        d = await _live_doc(c, factory)
        before, keys = await counts(factory), r2_keys(r2)
        r = await post_version(c, d["doc_id"], make_docx(author="re-saved"))
    assert r.status_code == 200
    assert r.json() == {"status": "unchanged", "message": "No changes compared to the current version."}
    assert await counts(factory) == before and r2_keys(r2) == keys


async def test_version_double_save_while_pending_is_unchanged(pg, r2, monkeypatch):
    """A second identical save while v2's ingest is still pending must not
    create v3: in-flight pending hashes count too (TDD §7.2)."""
    factory, _ = pg
    async with _client() as c:
        d = await _live_doc(c, factory)
        monkeypatch.setattr(upload, "_schedule", lambda *a, **k: None)   # v2 never ingests
        v2 = await post_version(c, d["doc_id"], make_docx(TEXT_B))
        assert v2.status_code == 202
        assert (await version_row(factory, v2.json()["version_id"]))["ingest_status"] == "pending"
        before, keys = await counts(factory), r2_keys(r2)
        r = await post_version(c, d["doc_id"], make_docx(TEXT_B, author="again"))
    assert r.status_code == 200 and r.json()["status"] == "unchanged"
    assert await counts(factory) == before and r2_keys(r2) == keys


async def test_version_changed_is_202_incremented_prior_still_current(pg, r2):
    factory, _ = pg
    async with _client() as c:
        d = await _live_doc(c, factory)
        doc_before = (await q(factory, "SELECT * FROM company.company_documents"))[0]
        keys_before = r2_keys(r2)
        r = await post_version(c, d["doc_id"], make_docx(TEXT_B), change_reason="Added escalation rule")
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["version_no"] == 2 and body["status"] == "processing" and body["job_id"]
    assert body["approval_state"] == "open" and body["approval_request_id"]
    v1, v2 = await version_row(factory, d["version_id"]), await version_row(factory, body["version_id"])
    assert v1["is_current"] is True and v1["status"] == "effective"
    assert v2["is_current"] is False and v2["status"] == "in_review" and v2["ingest_status"] == "ingested"
    assert v2["change_reason"] == "Added escalation rule" and v2["version_no"] == 2
    assert v2["pending_content_hash"] == content_hash(_md(make_docx(TEXT_B)))
    assert str(v2["supersedes_version_id"]) == d["version_id"]
    doc = (await q(factory, "SELECT * FROM company.company_documents"))[0]
    assert doc["current_version_id"] == doc_before["current_version_id"]       # untouched
    assert doc["current_content_hash"] == doc_before["current_content_hash"]   # untouched
    req = (await q(factory, "SELECT * FROM company.approval_requests WHERE request_id = CAST(:r AS uuid)",
                   r=body["approval_request_id"]))[0]
    assert req["state"] == "open" and str(req["version_id"]) == body["version_id"]
    step = (await q(factory, "SELECT * FROM company.approval_steps"))[0]
    assert step["assignee_person_id"] == PID
    assert len(r2_keys(r2)) > len(keys_before)
    job = (await q(factory, "SELECT state FROM company.ingest_jobs WHERE job_id = CAST(:j AS uuid)",
                   j=body["job_id"]))[0]
    assert job["state"] == "succeeded"


async def test_version_cross_document_duplicate_is_409(pg, r2):
    factory, _ = pg
    async with _client() as c:
        a = await _live_doc(c, factory, TEXT_A, gated=False)
        b = await _live_doc(c, factory, TEXT_C)
        before, keys = await counts(factory), r2_keys(r2)
        r = await post_version(c, b["doc_id"], make_docx(TEXT_A, author="copy"))
    assert r.status_code == 409
    assert r.json() == {"status": "duplicate",
                        "message": "This document is already in the system as 'Customer Service Procedure'.",
                        "doc_id": a["doc_id"]}
    assert await counts(factory) == before and r2_keys(r2) == keys


async def test_failed_version_same_content_new_bytes_creates_new_version_and_retires_stale(pg, r2):
    factory, ingest = pg
    async with _client() as c:
        d = await _live_doc(c, factory)
        ingest.fail = True
        v2 = await post_version(c, d["doc_id"], make_docx(TEXT_B, author="first try"))
        assert v2.status_code == 202
        failed = await version_row(factory, v2.json()["version_id"])
        assert failed["ingest_status"] == "failed" and failed["pending_content_hash"]   # kept (3.2 rule 1)
        ingest.fail = False
        v3 = await post_version(c, d["doc_id"], make_docx(TEXT_B, author="second try"))
    assert v3.status_code == 202, v3.text
    assert v3.json()["version_no"] == 3
    assert v3.json()["retired_version_ids"] == [v2.json()["version_id"]]
    stale = await version_row(factory, v2.json()["version_id"])
    assert stale["status"] == "retired" and stale["pending_content_hash"] is None
    old_req = (await q(factory, "SELECT state FROM company.approval_requests WHERE version_id = CAST(:v AS uuid)",
                       v=v2.json()["version_id"]))[0]
    assert old_req["state"] == "cancelled"        # its open request does not linger
    assert (await version_row(factory, d["version_id"]))["is_current"] is True


async def test_failed_version_byte_identical_points_at_retry_and_writes_nothing(pg, r2):
    factory, ingest = pg
    raw_b = make_docx(TEXT_B, author="same bytes")
    async with _client() as c:
        d = await _live_doc(c, factory)
        ingest.fail = True
        v2 = (await post_version(c, d["doc_id"], raw_b)).json()
        ingest.fail = False
        before, keys = await counts(factory), r2_keys(r2)
        r = await post_version(c, d["doc_id"], raw_b, "renamed.docx")
    assert r.status_code == 409
    assert r.json()["status"] == "retry_available"
    assert r.json()["job_id"] == v2["job_id"] and r.json()["version_id"] == v2["version_id"]
    assert await counts(factory) == before and r2_keys(r2) == keys


async def test_rejected_version_same_content_creates_new_version(pg, r2):
    factory, _ = pg
    async with _client() as c:
        d = await _live_doc(c, factory)
        v2 = (await post_version(c, d["doc_id"], make_docx(TEXT_B))).json()
        async with factory() as s:
            await s.execute(text("UPDATE company.approval_requests SET state = 'rejected', "
                                 "completed_at = now() WHERE request_id = CAST(:r AS uuid)"),
                            {"r": v2["approval_request_id"]})
            await s.commit()
        v3 = await post_version(c, d["doc_id"], make_docx(TEXT_B, author="resubmitted"))
    assert v3.status_code == 202 and v3.json()["version_no"] == 3
    stale = await version_row(factory, v2["version_id"])
    assert (stale["status"], stale["pending_content_hash"]) == ("retired", None)


async def test_version_register_inherits_spec_and_revalidates_new_header(pg, r2):
    factory, _ = pg
    spec = '{"register_type":"obligation","id_column":"obligation_id"}'
    async with _client() as c:
        d = (await c.post("/company/documents", data=form(title="Register", register_spec=spec),
                          files={"file": ("reg.csv", REGISTER_CSV, "text/csv")})).json()
        assert (await version_row(factory, d["version_id"]))["is_current"] is True
        renamed = "id,obligation,citation\nOB-1,x,y\n".encode()
        bad = await c.post(f"/company/documents/{d['doc_id']}/versions", data={"acting_person_id": PID},
                           files={"file": ("reg.csv", renamed, "text/csv")})
        good = await c.post(f"/company/documents/{d['doc_id']}/versions", data={"acting_person_id": PID},
                            files={"file": ("reg.csv", REGISTER_CSV + b"OB-3,New duty,170 IAC 1-1-3\n",
                                            "text/csv")})
        wrong_kind = await post_version(c, d["doc_id"], make_docx(TEXT_C))
    assert bad.status_code == 422 and "obligation_id" in bad.json()["detail"]
    assert good.status_code == 202, good.text
    job = (await q(factory, "SELECT register_spec FROM company.ingest_jobs WHERE job_id = CAST(:j AS uuid)",
                   j=good.json()["job_id"]))[0]
    assert job["register_spec"] is not None        # inherited spec stored for retry
    assert wrong_kind.status_code == 422


async def test_rejected_first_version_reupload_is_new_version_not_unchanged(pg, r2):
    """Never-promoted doc: v1's reservation on current_content_hash survives a
    rejection, so it must not be read as 'the current version'."""
    factory, _ = pg
    await add_policy(factory)
    async with _client() as c:
        d = (await post_doc(c, make_docx(TEXT_A))).json()
        async with factory() as s:
            await s.execute(text("UPDATE company.approval_requests SET state = 'rejected', "
                                 "completed_at = now() WHERE request_id = CAST(:r AS uuid)"),
                            {"r": d["approval_request_id"]})
            await s.commit()
        r = await post_version(c, d["doc_id"], make_docx(TEXT_A, author="resubmitted"))
    assert r.status_code == 202, r.text
    assert r.json()["version_no"] == 2 and r.json()["retired_version_ids"] == [d["version_id"]]
    v1 = await version_row(factory, d["version_id"])
    assert (v1["status"], v1["pending_content_hash"]) == ("retired", None)


async def test_no_policy_version_promotes_after_ingest_and_supersedes_v1(pg, r2, qdrant):
    factory, _ = pg
    async with _client() as c:
        d = await _live_doc(c, factory, gated=False)
        r = await post_version(c, d["doc_id"], make_docx(TEXT_B))
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["approval_state"] == "approved"
    v1, v2 = await version_row(factory, d["version_id"]), await version_row(factory, body["version_id"])
    assert (v2["status"], v2["is_current"], v2["pending_content_hash"]) == ("effective", True, None)
    assert (v1["status"], v1["is_current"]) == ("superseded", False)
    assert str(v1["superseded_by"]) == body["version_id"]
    doc = (await q(factory, "SELECT * FROM company.company_documents"))[0]
    assert str(doc["current_version_id"]) == body["version_id"]
    assert doc["current_content_hash"] == content_hash(_md(make_docx(TEXT_B)))
    job = (await q(factory, "SELECT state FROM company.ingest_jobs WHERE job_id = CAST(:j AS uuid)",
                   j=body["job_id"]))[0]
    assert job["state"] == "succeeded"


async def test_no_policy_version_whose_ingest_fails_never_promotes(pg, r2):
    factory, ingest = pg
    async with _client() as c:
        d = await _live_doc(c, factory, gated=False)
        doc_before = (await q(factory, "SELECT * FROM company.company_documents"))[0]
        ingest.fail = True
        r = await post_version(c, d["doc_id"], make_docx(TEXT_B))
    assert r.status_code == 202
    v2 = await version_row(factory, r.json()["version_id"])     # rows persist
    assert v2["is_current"] is False and v2["status"] == "in_review" and v2["ingest_status"] == "failed"
    assert (await version_row(factory, d["version_id"]))["is_current"] is True
    doc = (await q(factory, "SELECT * FROM company.company_documents"))[0]
    assert doc["current_version_id"] == doc_before["current_version_id"]
    assert doc["current_content_hash"] == doc_before["current_content_hash"]
    job = (await q(factory, "SELECT state FROM company.ingest_jobs WHERE job_id = CAST(:j AS uuid)",
                   j=r.json()["job_id"]))[0]
    assert job["state"] == "failed"


# =========================================================================== explicit policy_id (task 9.1)
async def _policy(factory, name: str, roles: list[str]) -> str:
    pol = str(uuid.uuid4())
    async with factory() as s:
        await s.execute(text("INSERT INTO company.approval_policies (company_id, policy_id, name) "
                             "VALUES (:c, CAST(:p AS uuid), :n)"), {"c": CO, "p": pol, "n": name})
        for i, role in enumerate(roles, 1):
            await s.execute(text("INSERT INTO company.approval_policy_steps "
                                 "(policy_id, step_no, required_role) VALUES (CAST(:p AS uuid), :n, :r)"),
                            {"p": pol, "n": i, "r": role})
        await s.commit()
    return pol


async def test_explicit_policy_id_overrides_automatic_selection(pg, r2):
    """Two documents sharing (vertical, doc_class) can need different signature chains
    (RPL-CS-PRO-004 has an approver; RPL-CS-PRO-007/011 are owner + reviewer only), and
    select_policy only sees (vertical, doc_class). The optional policy_id form field
    picks the chain explicitly, on both upload endpoints."""
    factory, _ = pg
    default = await _policy(factory, "A default", ["reviewer", "approver"])
    two_sig = await _policy(factory, "Z two-signature", ["owner", "reviewer"])
    async with _client() as c:
        auto = await post_doc(c, make_docx(TEXT_A), doc_class="procedure")
        explicit = await post_doc(c, make_docx(TEXT_B), doc_class="procedure", policy_id=two_sig)
    assert auto.status_code == 202 and explicit.status_code == 202, (auto.text, explicit.text)
    rows = {r["request_id"]: r for r in await q(
        factory, "SELECT r.request_id::text AS request_id, r.policy_id::text AS policy_id, "
                 "array_agg(s.required_role ORDER BY s.step_no) AS roles "
                 "FROM company.approval_requests r JOIN company.approval_steps s USING (request_id) "
                 "GROUP BY r.request_id, r.policy_id")}
    a, e = rows[auto.json()["approval_request_id"]], rows[explicit.json()["approval_request_id"]]
    assert a["policy_id"] == default and list(a["roles"]) == ["reviewer", "approver"]
    assert e["policy_id"] == two_sig and list(e["roles"]) == ["owner", "reviewer"]

    # The version endpoint takes it too.
    await add_policy(factory, explicit.json()["doc_id"])
    async with _client() as c:
        v2 = await post_version(c, explicit.json()["doc_id"], make_docx(TEXT_B + [(None, "Revised: complaints are logged the same day.")]),
                                policy_id=two_sig)
    assert v2.status_code == 202, v2.text
    pid = (await q(factory, "SELECT policy_id::text AS p FROM company.approval_requests "
                            "WHERE request_id = CAST(:r AS uuid)", r=v2.json()["approval_request_id"]))
    assert pid[0]["p"] == two_sig


@pytest.mark.parametrize("bad", ["not-a-uuid", str(uuid.uuid4())])
async def test_unknown_policy_id_is_422_and_stores_nothing(pg, r2, bad):
    factory, _ = pg
    async with _client() as c:
        r = await post_doc(c, make_docx(), policy_id=bad)
    assert r.status_code == 422 and "Unknown approval policy" in r.json()["detail"]
    assert await counts(factory) == {"company_documents": 0, "document_versions": 0,
                                     "ingest_jobs": 0, "approval_requests": 0}
    assert r2_keys(r2) == []
