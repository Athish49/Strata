"""Document upload endpoints (tasks 6.1 / 6.2; TDD §7.1, §7.2, architecture §3-§5).

    POST /company/documents                      -> new document (version 1)
    POST /company/documents/{doc_id}/versions    -> new version of an existing document

**A duplicate stores nothing** — no R2 object, no row, no job.  So every
request runs the whole read-only pipeline first::

    read bytes (25 MB cap -> 413)
    -> type allowlist (DOCX, or CSV + register_spec; anything else -> 415)
    -> extract (DocxExtractor) / decode + validate_register_spec (registers)
    -> empty-extraction guard (422)        <- BEFORE hashing: every empty text
                                               hashes identically
    -> content_hash
    -> duplicate / unchanged lookup        (409 / 200, nothing written)

and only then the write transaction (one per request, on the ``get_db``
session)::

    pg_advisory_xact_lock(content hash)    serialises same-content uploads
    re-run the duplicate lookup under the lock
    6.1: pg_advisory_xact_lock(doc_id allocator) -> DOC-%06d = MAX+1
         INSERT company_documents (current_content_hash reserved,
                                   lifecycle_state='pending')
           -> UniqueViolation on company_documents_content_hash_uq -> 409
    6.2: SELECT company_documents ... FOR UPDATE; version_no = MAX+1;
         retire stale failed/rejected versions; open approval per policy
    INSERT document_versions (pending_content_hash, source_r2_key, ...)
    jobs.create_job(...)
    R2 put of the raw bytes                 (after every check has passed)
    COMMIT
    BackgroundTasks -> run_ingest_with_bookkeeping -> jobs.run_ingest_job

The R2 put happens inside the transaction, after the document INSERT, so a
concurrent loser fails at its INSERT / re-check and never writes an object; an
R2 failure rolls the rows back.  The only orphan possible is an R2 object whose
COMMIT then fails, which no row references (keys embed the version uuid, so it
can never collide with a later upload).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.company.org import (
    _LEGACY_COL,
    _policy_steps,
    _require_person,
    _role_holder,
    select_policy,
)
from app.api.company.routes import fetch_vertical_slugs
from app.company_ingest import jobs
from app.company_ingest.extract import DocxExtractor
from app.company_ingest.hashing import canonicalize, content_hash
from app.company_ingest.register_spec import RegisterSpec, RegisterSpecError, validate_register_spec
from app.company_ingest.run_context import RunContext
from app.company_ingest.store.r2_keys import raw_doc_key
from app.db import get_db
from app.engine.config import engine_settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/company", tags=["company-upload"])

#: 25 MB request-body cap (413 above it).  Module constant so tests can shrink it.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
#: Below this many canonical characters a DOCX counts as "no extractable text".
MIN_CANONICAL_CHARS = 50

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_CSV_CONTENT_TYPES = frozenset({"text/csv", "application/csv", "text/x-csv"})

MSG_UNSUPPORTED = "Only .docx documents are supported. PDF is not yet available."
MSG_EMPTY = "No extractable text found in this document."
MSG_UNCHANGED = "No changes compared to the current version."
MSG_STORAGE = "The file could not be stored; nothing was saved. Please try again."

_KIND_DOCX, _KIND_CSV = "docx", "csv"


def _cid() -> str:
    return engine_settings.ENGINE_COMPANY_ID


# ---------------------------------------------------------------------------
# Injectable dependencies — the defaults point at production Neon / R2, so
# tests override ``get_upload_deps``.
# ---------------------------------------------------------------------------


@dataclass
class UploadDeps:
    #: Session factory for the BACKGROUND ingest (job state + ingest txn +
    #: ingest_runs).  None -> the app's ``AsyncSessionLocal`` (resolved lazily
    #: by jobs / store.commit).  The upload transaction itself always uses the
    #: request's ``get_db`` session.
    session_factory: Any = None
    #: Object exposing ``put_bytes(key, data, metadata, content_type)`` and
    #: ``get_bytes(key)`` (the ``store.r2`` module by default).
    r2: Any = None
    #: Replacement for ``service.ingest_document`` (tests).  None -> the real one.
    ingest_fn: Any = None
    #: Qdrant client for promote-on-success of an auto-approved version.
    #: None -> promote_version builds the configured client.
    qdrant_client: Any = None


def get_upload_deps() -> UploadDeps:
    return UploadDeps()


def _r2(deps: UploadDeps) -> Any:
    if deps.r2 is not None:
        return deps.r2
    from app.company_ingest.store import r2 as r2_mod  # lazy: boto3 client

    return r2_mod


async def _after_dedupe_hook() -> None:
    """No-op seam between the unlocked duplicate SELECT and the write
    transaction.  Tests patch it with a barrier to force two concurrent
    identical uploads past the SELECT together."""


# ---------------------------------------------------------------------------
# Read-only pipeline: bytes -> kind -> text -> guard -> hash
# ---------------------------------------------------------------------------


@dataclass
class Prepared:
    raw: bytes
    kind: str                       # "docx" | "csv"
    markdown: str                   # UN-anchored extractor output / decoded CSV
    content_hash: str
    raw_sha256: str
    extraction_method: str
    register_spec: Optional[RegisterSpec]


async def _read_capped(file: UploadFile) -> bytes:
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
        )
    return raw


def _classify(file: UploadFile, raw: bytes) -> str:
    """DOCX or CSV, by extension / content type plus a magic-byte sanity check.
    Anything else (PDF included) -> 415 before any extraction."""
    name = (file.filename or "").lower()
    ctype = (file.content_type or "").split(";")[0].strip().lower()
    if raw.startswith(b"%PDF") or name.endswith(".pdf") or ctype == "application/pdf":
        raise HTTPException(status_code=415, detail=MSG_UNSUPPORTED)
    if name.endswith(".docx") or ctype == DOCX_CONTENT_TYPE:
        return _KIND_DOCX
    if name.endswith(".csv") or ctype in _CSV_CONTENT_TYPES:
        return _KIND_CSV
    raise HTTPException(status_code=415, detail=MSG_UNSUPPORTED)


def _parse_spec(register_spec: Optional[str]) -> Optional[RegisterSpec]:
    if register_spec is None or not register_spec.strip():
        return None
    try:
        return RegisterSpec.model_validate_json(register_spec)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"register_spec is invalid: {exc}") from exc


def _extract_docx(raw: bytes, filename: str) -> tuple[str, str]:
    doc = DocxExtractor().extract(raw, filename)
    return doc.markdown, doc.method


async def _prepare(raw: bytes, kind: str, filename: str,
                   spec: Optional[RegisterSpec]) -> Prepared:
    """Extract / validate, guard, hash.  Pure: no DB, no R2."""
    if kind == _KIND_DOCX:
        if spec is not None:
            raise HTTPException(status_code=422,
                                detail="register_spec applies only to a register CSV upload.")
        try:
            markdown, method = await asyncio.to_thread(_extract_docx, raw, filename)
        except Exception as exc:  # UnreadableDocumentError, or anything python-docx raises
            raise HTTPException(status_code=422,
                                detail=f"This document could not be read: {exc}") from exc
        # Empty-extraction guard BEFORE hashing (TDD §2 consequence 2, §3.2).
        if len(canonicalize(markdown)) < MIN_CANONICAL_CHARS:
            raise HTTPException(status_code=422, detail=MSG_EMPTY)
        return Prepared(raw=raw, kind=kind, markdown=markdown, content_hash=content_hash(markdown),
                        raw_sha256=hashlib.sha256(raw).hexdigest(), extraction_method=method,
                        register_spec=None)

    # Register CSV (TDD §3.3-§3.5).
    if spec is None:
        raise HTTPException(
            status_code=422,
            detail="A CSV upload is a register and needs a register_spec "
                   '(e.g. {"register_type":"obligation","id_column":"obligation_id"}).',
        )
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail="This CSV is not valid UTF-8 text. Re-export it as 'CSV UTF-8' and upload it again.",
        ) from exc
    try:
        await asyncio.to_thread(validate_register_spec, spec, decoded)
    except RegisterSpecError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not canonicalize(decoded):  # unreachable after validation; never hash empty text
        raise HTTPException(status_code=422, detail=MSG_EMPTY)
    # Task 3.2 decision 4: exactly the expression jobs.prepare_retry re-reserves with.
    return Prepared(raw=raw, kind=kind, markdown=decoded,
                    content_hash=content_hash(raw.decode("utf-8-sig")),
                    raw_sha256=hashlib.sha256(raw).hexdigest(), extraction_method="register-csv",
                    register_spec=spec)


def _canonical_vertical(value: str, slugs: dict[str, str]) -> str:
    """Accept the backend name (any case) or the frontend slug; store the name.

    ``slugs`` is the ``name.lower() -> slug`` mapping from ``fetch_vertical_slugs()``
    (fetched by the caller through the request-scoped session).
    """
    v = (value or "").strip()
    if not v:
        raise HTTPException(status_code=422, detail="vertical is required.")
    names = {k: k.title() for k in slugs}
    if v.lower() in names:
        return names[v.lower()]
    by_slug = {slug: names[k] for k, slug in slugs.items()}
    if v.lower() in by_slug:
        return by_slug[v.lower()]
    allowed = ", ".join(sorted(names.values()))
    raise HTTPException(status_code=422, detail=f"Unknown vertical {v!r}. Use one of: {allowed}.")


def _parse_law_as_of(value: Optional[str]) -> Optional[date]:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="law_as_of must be an ISO date (YYYY-MM-DD).") from exc


def _raw_key(doc_id: str, version_no: int, version_id: str, kind: str) -> str:
    # The key must end in .docx / .csv (jobs._markdown_from_raw dispatches on it)
    # and embeds the version uuid so a rolled-back upload's orphan can never
    # collide with a later upload under R2's write-once guard.
    return raw_doc_key(_cid(), doc_id, str(version_no), f"{version_id}.{kind}")


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

#: A version whose hash still counts: in review, ingest not failed, latest
#: approval request neither rejected nor cancelled (task 3.2 decision 2, with
#: in-flight ingests included — see the report / ``_LIVE_CANDIDATE`` note).
_LIVE_CANDIDATE = """
    v.status = 'in_review'
    AND v.pending_content_hash IS NOT NULL
    AND COALESCE(v.ingest_status, 'pending') <> 'failed'
    AND COALESCE((SELECT r.state FROM company.approval_requests r
                   WHERE r.version_id = v.version_id
                   ORDER BY r.created_at DESC LIMIT 1), 'none') NOT IN ('rejected', 'cancelled')
"""

#: Document holding *h* as its current hash, or as a live candidate's pending
#: hash.  ``:exclude`` skips one doc (6.2's cross-document check).
_HOLDER_SQL = text(f"""
    SELECT d.doc_id, COALESCE(d.title, d.doc_id) AS title, 0 AS pri
      FROM company.company_documents d
     WHERE d.company_id = :c AND d.current_content_hash = :h
       AND d.doc_id IS DISTINCT FROM :exclude
    UNION ALL
    SELECT d.doc_id, COALESCE(d.title, d.doc_id) AS title, 1 AS pri
      FROM company.document_versions v
      JOIN company.company_documents d ON d.company_id = v.company_id AND d.doc_id = v.doc_id
     WHERE v.company_id = :c AND v.pending_content_hash = :h
       AND v.doc_id IS DISTINCT FROM :exclude
       AND {_LIVE_CANDIDATE}
     ORDER BY pri, doc_id
     LIMIT 1
""")

_LOCK_SQL = text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))")

_NEXT_DOC_NO_SQL = text("""
    SELECT COALESCE(MAX(CAST(substring(doc_id FROM 5) AS bigint)), 0) + 1 AS n
      FROM company.company_documents
     WHERE company_id = :c AND doc_id ~ '^DOC-[0-9]+$'
""")

_INSERT_DOC_SQL = text("""
    INSERT INTO company.company_documents
        (company_id, doc_id, title, doc_class, vertical, doc_number,
         current_content_hash, lifecycle_state, created_at, updated_at)
    VALUES (:c, :d, :title, :doc_class, :vertical, :doc_number, :h, :lifecycle, now(), now())
""")

_INSERT_VERSION_SQL = text("""
    INSERT INTO company.document_versions
        (version_id, company_id, doc_id, version_no, status, is_current, ingest_status,
         source_r2_key, pending_content_hash, law_as_of, created_by_person_id, change_reason,
         extraction_method, supersedes_version_id)
    VALUES (CAST(:v AS uuid), :c, :d, :no, 'in_review', false, 'pending',
            :key, :h, :law_as_of, :person, :reason, :method, CAST(:supersedes AS uuid))
""")

_DOC_IDS_SQL = text("SELECT doc_id FROM company.company_documents WHERE company_id = :c")


async def _lock(db: AsyncSession, key: str) -> None:
    await db.execute(_LOCK_SQL, {"k": key})


async def _lock_content_hash(db: AsyncSession, h: str) -> None:
    """Serialise every upload (6.1 and 6.2) of the same content in this company.
    Taken before the doc-id lock / doc row lock — one global order, no deadlock."""
    await _lock(db, f"strata:upload:hash:{_cid()}:{h}")


async def _holder(db: AsyncSession, h: str, exclude: Optional[str] = None) -> Optional[dict]:
    row = (await db.execute(_HOLDER_SQL, {"c": _cid(), "h": h, "exclude": exclude})).mappings().first()
    return dict(row) if row else None


def _duplicate(holder: dict) -> JSONResponse:
    return JSONResponse(status_code=409, content={
        "status": "duplicate",
        "message": f"This document is already in the system as '{holder['title']}'.",
        "doc_id": holder["doc_id"],
    })


async def _registered_doc_ids(db: AsyncSession, doc_id: str) -> list[str]:
    rows = (await db.execute(_DOC_IDS_SQL, {"c": _cid()})).mappings().all()
    return list(dict.fromkeys([doc_id, *(r["doc_id"] for r in rows)]))


async def _put_raw(deps: UploadDeps, key: str, p: Prepared, doc_id: str, version_no: int) -> None:
    ctype = DOCX_CONTENT_TYPE if p.kind == _KIND_DOCX else "text/csv"
    meta = {"sha256": p.raw_sha256, "content_type": ctype, "doc_id": doc_id,
            "version": str(version_no), "profile": "upload"}
    await asyncio.to_thread(_r2(deps).put_bytes, key, p.raw, meta, ctype)


# ---------------------------------------------------------------------------
# Background: ingest_runs bookkeeping + promote-on-success around run_ingest_job
# ---------------------------------------------------------------------------

_LATEST_REQUEST_STATE_SQL = text("""
    SELECT r.state, v.is_current, v.status
      FROM company.document_versions v
      LEFT JOIN LATERAL (SELECT state FROM company.approval_requests r
                          WHERE r.version_id = v.version_id
                          ORDER BY r.created_at DESC LIMIT 1) r ON true
     WHERE v.company_id = :c AND v.version_id = CAST(:v AS uuid)
""")

_JOB_PROMOTION_FAILED_SQL = text("""
    UPDATE company.ingest_jobs
       SET state = 'failed', error = :err, finished_at = now()
     WHERE job_id = CAST(:j AS uuid) AND state = 'succeeded'
""")


def _resolve_factory(session_factory: Any) -> Any:
    if session_factory is not None:
        return session_factory
    from app.db import AsyncSessionLocal  # lazy: reads the production .env

    return AsyncSessionLocal


def _resolve_r2(r2_client: Any) -> Any:
    if r2_client is not None:
        return r2_client
    from app.company_ingest.store import r2 as r2_mod  # lazy: boto3 client

    return r2_mod


async def _promote_if_auto_approved(job: "jobs.IngestJob", ctx: RunContext, factory: Any,
                                    qdrant_client: Any) -> "jobs.IngestJob":
    """After a SUCCESSFUL ingest: if the version's latest approval request is
    already ``approved`` (auto-approved at upload — no policy / no steps) and
    the version is not current, promote it now in its own session, using its
    ``pending_content_hash`` (promote_version's default lookup).

    On a promotion failure the job is moved ``succeeded -> failed`` with the
    reason and the version is left ``in_review`` (promote_version rolled its
    own session back).  The first-version hash reservation is deliberately
    kept: the data is ingested, a retry re-runs ingest + this promotion, and
    releasing it would let a duplicate upload in meanwhile.
    """
    from app.company_ingest.promote import PromotionError, promote_version

    async with factory() as s:
        row = (await s.execute(_LATEST_REQUEST_STATE_SQL,
                               {"c": job.company_id, "v": job.version_id})).mappings().first()
    if row is None or row["state"] != "approved" or row["is_current"]:
        return job
    error: Optional[str] = None
    try:
        async with factory() as s:
            await promote_version(s, job.company_id, job.doc_id, job.version_id,
                                  qdrant_client=qdrant_client, ctx=ctx, commit=True)
    except PromotionError as exc:
        error = f"promotion after auto-approval failed: {type(exc).__name__}: {exc}"
    except Exception as exc:  # never raise out of a BackgroundTask
        error = f"promotion after auto-approval failed unexpectedly: {type(exc).__name__}: {exc}"
        log.exception("auto-approved promotion of %s failed", job.version_id)
    if error is None:
        return job
    log.warning("ingest job %s: %s", job.job_id, error)
    try:
        async with factory() as s:
            await s.execute(_JOB_PROMOTION_FAILED_SQL, {"j": job.job_id, "err": error[:4000]})
            await s.commit()
    except Exception:
        log.exception("could not mark job %s failed after a promotion failure", job.job_id)
    return await jobs.get_job(job.job_id, session_factory=factory) or job


async def run_ingest_with_bookkeeping(
    job_id: str,
    *,
    markdown: str,
    register_spec: Optional[RegisterSpec] = None,
    session_factory: Any = None,
    r2_client: Any = None,
    ingest_fn: Any = None,
    qdrant_client: Any = None,
    **ingest_kwargs: Any,
) -> Optional["jobs.IngestJob"]:
    """BackgroundTask body for an upload or a retry.  Never raises.

    1. ``start_ingest_run(ctx)`` — own committed txn, one ``RunContext`` per attempt.
    2. ``jobs.run_ingest_job(job_id, ctx=ctx, ...)`` — commits or rolls back the
       ingest session before it returns; ``r2_client`` and *ingest_kwargs* are
       forwarded to ``service.ingest_document``.
    3. On success: promote if the version was auto-approved at upload
       (:func:`_promote_if_auto_approved`).
    4. ``finish_ingest_run(ctx, 'completed' | 'failed')`` — only now, after the
       ingest session has closed (task 5.8 pattern).

    ``session_factory`` / ``r2_client`` / ``qdrant_client`` default to the
    production ones (``AsyncSessionLocal``, ``store.r2``, the configured Qdrant).
    """
    from app.company_ingest.store.commit import finish_ingest_run, start_ingest_run

    factory = _resolve_factory(session_factory)
    r2c = _resolve_r2(r2_client)
    ctx = RunContext(company_id=_cid())
    try:
        await start_ingest_run(ctx, session_factory=factory)
    except Exception:  # bookkeeping must never block the ingest
        log.exception("could not record ingest_runs start for job %s", job_id)

    job = None
    try:
        job = await jobs.run_ingest_job(
            job_id, markdown=markdown, register_spec=register_spec, session_factory=factory,
            ctx=ctx, ingest_fn=ingest_fn, r2_client=r2c, **ingest_kwargs,
        )
        if job is not None and job.state == jobs.JOB_SUCCEEDED:
            job = await _promote_if_auto_approved(job, ctx, factory, qdrant_client)
    except Exception:
        log.exception("ingest job %s: unexpected error in the background wrapper", job_id)

    try:
        doc_ids = [job.doc_id] if job is not None else []
        if job is not None and job.state == jobs.JOB_SUCCEEDED:
            count = int((job.stats or {}).get("clause_count") or 0)
            await finish_ingest_run(ctx, "completed", doc_ids=doc_ids,
                                    unit_counts_by_doc={job.doc_id: count},
                                    r2_client=r2c, session_factory=factory)
        else:
            err = (job.error if job is not None else None) or \
                f"ingest job {job_id} did not run (state={getattr(job, 'state', None)!r})"
            await finish_ingest_run(ctx, "failed", error=err, doc_ids=doc_ids,
                                    r2_client=r2c, session_factory=factory)
    except Exception:
        log.exception("could not record ingest_runs finish for job %s", job_id)
    return job


def _schedule(background: BackgroundTasks, deps: UploadDeps, *, job_id: str,
              p: Prepared, **kwargs: Any) -> None:
    background.add_task(run_ingest_with_bookkeeping, job_id, markdown=p.markdown,
                        register_spec=p.register_spec, session_factory=deps.session_factory,
                        r2_client=deps.r2, ingest_fn=deps.ingest_fn,
                        qdrant_client=deps.qdrant_client, **kwargs)


# ---------------------------------------------------------------------------
# 6.1  POST /company/documents
# ---------------------------------------------------------------------------


@router.post("/documents", status_code=202)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    vertical: str = Form(...),
    acting_person_id: str = Form(..., min_length=1),
    title: Optional[str] = Form(None),
    doc_number: Optional[str] = Form(None),
    doc_class: Optional[str] = Form(None),
    register_spec: Optional[str] = Form(None),
    law_as_of: Optional[str] = Form(None),
    change_reason: Optional[str] = Form(None),
    policy_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    deps: UploadDeps = Depends(get_upload_deps),
):
    # ---- read-only pipeline (no R2 writes; one read-only verticals lookup) ----
    raw = await _read_capped(file)
    kind = _classify(file, raw)
    spec = _parse_spec(register_spec)
    p = await _prepare(raw, kind, file.filename or "", spec)
    vertical_name = _canonical_vertical(vertical, await fetch_vertical_slugs(db))
    law_date = _parse_law_as_of(law_as_of)
    doc_title = (title or "").strip() or (file.filename or "").rsplit(".", 1)[0] or None

    # ---- reads -----------------------------------------------------------
    await _require_person(db, acting_person_id)
    policy = await _explicit_policy(db, policy_id)
    holder = await _holder(db, p.content_hash)
    if holder:
        await db.rollback()
        return _duplicate(holder)
    await _after_dedupe_hook()

    # ---- the write transaction ------------------------------------------
    await _lock_content_hash(db, p.content_hash)
    holder = await _holder(db, p.content_hash)          # re-check under the lock
    if holder:
        await db.rollback()
        return _duplicate(holder)

    await _lock(db, f"strata:upload:doc_id:{_cid()}")    # race-safe MAX+1
    n = (await db.execute(_NEXT_DOC_NO_SQL, {"c": _cid()})).scalar()
    doc_id = f"DOC-{int(n or 1):06d}"
    version_id = str(uuid.uuid4())
    key = _raw_key(doc_id, 1, version_id, p.kind)
    try:
        await db.execute(_INSERT_DOC_SQL, {
            "c": _cid(), "d": doc_id, "title": doc_title, "doc_class": doc_class,
            "vertical": vertical_name, "doc_number": (doc_number or "").strip() or None,
            "h": p.content_hash, "lifecycle": jobs.LIFECYCLE_PENDING,
        })
    except IntegrityError as exc:
        # Partial unique index company_documents_content_hash_uq: a concurrent
        # identical upload (or a retry re-reservation) committed first.
        await db.rollback()
        if "company_documents_content_hash_uq" not in str(exc):
            raise
        holder = await _holder(db, p.content_hash)
        await db.rollback()
        return _duplicate(holder or {"doc_id": None, "title": "another document"})

    await db.execute(_INSERT_VERSION_SQL, {
        "v": version_id, "c": _cid(), "d": doc_id, "no": 1, "key": key, "h": p.content_hash,
        "law_as_of": law_date, "person": acting_person_id,
        "reason": (change_reason or "").strip() or None, "method": p.extraction_method,
        "supersedes": None,
    })
    job_id = await jobs.create_job(db, company_id=_cid(), doc_id=doc_id, version_id=version_id,
                                   register_spec=p.register_spec)
    request_id, request_state = await _open_approval_at_upload(
        db, {"doc_id": doc_id, "vertical": vertical_name, "doc_class": doc_class}, version_id,
        policy)
    registered = await _registered_doc_ids(db, doc_id)
    try:
        await _put_raw(deps, key, p, doc_id, 1)
    except Exception as exc:
        await db.rollback()
        log.exception("raw upload to R2 failed for %s", key)
        raise HTTPException(status_code=503, detail=MSG_STORAGE) from exc
    await db.commit()

    _schedule(background, deps, job_id=job_id, p=p,
              document_title=doc_title, law_as_of=law_date, source_r2_key=key,
              extraction_method=p.extraction_method, created_by_person_id=acting_person_id,
              registered_doc_ids=registered)
    return {"doc_id": doc_id, "version_id": version_id, "job_id": job_id, "status": "processing",
            "approval_request_id": request_id, "approval_state": request_state}


# ---------------------------------------------------------------------------
# 6.2  POST /company/documents/{doc_id}/versions
# ---------------------------------------------------------------------------

_DOC_SQL = text("""
    SELECT doc_id, title, doc_class, vertical, owner_id, reviewer_id, approver_id,
           current_version_id, current_content_hash, lifecycle_state
      FROM company.company_documents
     WHERE company_id = :c AND doc_id = :d
""")

#: The document's latest version tells us what kind it is (register vs prose)
#: and which RegisterSpec a re-upload inherits.
_LATEST_KIND_SQL = text("""
    SELECT v.source_r2_key,
           (SELECT j.register_spec FROM company.ingest_jobs j
             WHERE j.version_id = v.version_id ORDER BY j.created_at DESC LIMIT 1) AS register_spec
      FROM company.document_versions v
     WHERE v.company_id = :c AND v.doc_id = :d
     ORDER BY v.version_no DESC
     LIMIT 1
""")

_VERSIONS_SQL = text("""
    SELECT v.version_id, v.version_no, v.status, v.ingest_status, v.is_current,
           v.pending_content_hash, v.source_r2_key,
           (SELECT r.state FROM company.approval_requests r WHERE r.version_id = v.version_id
             ORDER BY r.created_at DESC LIMIT 1) AS approval_state,
           (SELECT j.job_id FROM company.ingest_jobs j WHERE j.version_id = v.version_id
             ORDER BY j.created_at DESC LIMIT 1) AS job_id
      FROM company.document_versions v
     WHERE v.company_id = :c AND v.doc_id = :d
     ORDER BY v.version_no
""")

_RETIRE_SQL = text("""
    UPDATE company.document_versions
       SET status = 'retired', pending_content_hash = NULL
     WHERE company_id = :c AND doc_id = :d AND version_id = CAST(:v AS uuid)
""")

_CANCEL_OPEN_SQL = text("""
    UPDATE company.approval_requests SET state = 'cancelled', completed_at = now()
     WHERE company_id = :c AND version_id = CAST(:v AS uuid) AND state = 'open'
""")


def _is_live_candidate(v: dict) -> bool:
    return (v["status"] == "in_review" and v["pending_content_hash"] is not None
            and (v["ingest_status"] or "pending") != "failed"
            and v["approval_state"] not in ("rejected", "cancelled"))


def _is_stale(v: dict) -> bool:
    """Failed or rejected in-review version: retired when a newer version is
    created (task 3.2 decision 1b)."""
    return (v["status"] == "in_review" and not v["is_current"]
            and ((v["ingest_status"] or "") == "failed" or v["approval_state"] == "rejected"))


def _spec_from_row(value: Any) -> Optional[RegisterSpec]:
    if value is None:
        return None
    if isinstance(value, (str, bytes)):
        value = json.loads(value)
    return RegisterSpec.model_validate(value)


async def _stored_raw_sha256(deps: UploadDeps, key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    try:
        data = await asyncio.to_thread(_r2(deps).get_bytes, key)
    except Exception:  # unreadable -> not "identical"; a new version is created
        log.warning("could not read stored raw file %s for the retry comparison", key)
        return None
    return hashlib.sha256(data).hexdigest()


_POLICY_BY_ID_SQL = text("""
    SELECT policy_id, name, applies_to_vertical, applies_to_doc_class
      FROM company.approval_policies
     WHERE company_id = :c AND policy_id = CAST(:p AS uuid)
""")


async def _explicit_policy(db: AsyncSession, policy_id: Optional[str]) -> Optional[dict]:
    """The optional ``policy_id`` form field: an explicit approval policy for this
    upload, overriding ``select_policy`` (same override ``org.open_approval`` has).
    ``None``/blank -> None (automatic selection). Unknown or malformed -> 422, checked
    before anything is written."""
    if policy_id is None or not policy_id.strip():
        return None
    try:
        pid = str(uuid.UUID(policy_id.strip()))
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown approval policy {policy_id!r}.")
    row = (await db.execute(_POLICY_BY_ID_SQL, {"c": _cid(), "p": pid})).mappings().first()
    if row is None:
        raise HTTPException(status_code=422, detail=f"Unknown approval policy {policy_id!r}.")
    return dict(row)


async def _open_approval_at_upload(db: AsyncSession, doc: dict, version_id: str,
                                   policy: Optional[dict] = None) -> tuple[str, str]:
    """Open the version's approval request per policy, inside the upload
    transaction (same selection + step materialisation as ``org.open_approval``).
    *policy* (from the ``policy_id`` form field) skips automatic selection.

    * A matching policy WITH steps -> an ``open`` request with its steps.
    * No matching policy, or one with no steps -> an ``approved`` request, but
      NO promotion here: ingest has not run, so ``promote_version`` would raise
      ``PromotionNotReady`` and roll back this whole transaction (erasing the
      version and job rows).  :func:`run_ingest_with_bookkeeping` promotes it
      once the ingest job has succeeded.

    Returns ``(request_id, state)``.
    """
    if policy is None:
        policy = await select_policy(db, doc.get("vertical"), doc.get("doc_class"))
    steps = await _policy_steps(db, str(policy["policy_id"])) if policy else []
    state = "open" if steps else "approved"
    if not steps:
        log.warning(
            "approval auto-approved at upload: no approval policy with steps matched doc_id=%s "
            "vertical=%r doc_class=%r version_id=%s - it promotes when its ingest succeeds",
            doc["doc_id"], doc.get("vertical"), doc.get("doc_class"), version_id,
        )
    rid = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO company.approval_requests "
        "(request_id, company_id, version_id, policy_id, state, completed_at) "
        "VALUES (CAST(:r AS uuid), :c, CAST(:v AS uuid), CAST(:p AS uuid), :s, "
        "CASE WHEN :s2 = 'open' THEN NULL ELSE now() END)"),
        {"r": rid, "c": _cid(), "v": version_id,
         "p": str(policy["policy_id"]) if policy else None, "s": state, "s2": state})
    for st in steps:
        assignee = await _role_holder(db, doc["doc_id"], st["required_role"],
                                     doc.get(_LEGACY_COL[st["required_role"]]))
        await db.execute(text(
            "INSERT INTO company.approval_steps (request_id, step_no, required_role, assignee_person_id) "
            "VALUES (CAST(:r AS uuid), :n, :role, :a)"),
            {"r": rid, "n": st["step_no"], "role": st["required_role"], "a": assignee})
    return rid, state


@router.post("/documents/{doc_id}/versions", status_code=202)
async def upload_version(
    doc_id: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    acting_person_id: str = Form(..., min_length=1),
    change_reason: Optional[str] = Form(None),
    register_spec: Optional[str] = Form(None),
    law_as_of: Optional[str] = Form(None),
    policy_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    deps: UploadDeps = Depends(get_upload_deps),
):
    # ---- read-only pipeline, part 1 --------------------------------------
    raw = await _read_capped(file)
    kind = _classify(file, raw)
    explicit_spec = _parse_spec(register_spec)
    law_date = _parse_law_as_of(law_as_of)

    # ---- reads: actor, document, its kind and inherited spec --------------
    await _require_person(db, acting_person_id)
    policy = await _explicit_policy(db, policy_id)
    doc_row = (await db.execute(_DOC_SQL, {"c": _cid(), "d": doc_id})).mappings().first()
    if doc_row is None:
        raise HTTPException(status_code=404, detail="document not found")
    latest = (await db.execute(_LATEST_KIND_SQL, {"c": _cid(), "d": doc_id})).mappings().first()
    existing_kind = None
    inherited_spec = None
    if latest is not None:
        key0 = (latest["source_r2_key"] or "").lower()
        existing_kind = _KIND_CSV if key0.endswith(".csv") else _KIND_DOCX if key0.endswith(".docx") else None
        try:
            inherited_spec = _spec_from_row(latest["register_spec"])
        except Exception:
            inherited_spec = None
        if inherited_spec is not None:
            existing_kind = _KIND_CSV
    if existing_kind is not None and existing_kind != kind:
        want = "a register CSV" if existing_kind == _KIND_CSV else "a .docx document"
        raise HTTPException(status_code=422, detail=f"{doc_id} is {want}; upload its new version in the same format.")
    spec = explicit_spec if explicit_spec is not None else (inherited_spec if kind == _KIND_CSV else None)

    # ---- read-only pipeline, part 2 (validate_register_spec re-runs on the NEW header) --
    p = await _prepare(raw, kind, file.filename or "", spec)

    # ---- the write transaction ------------------------------------------
    await _lock_content_hash(db, p.content_hash)
    doc_row = (await db.execute(text(str(_DOC_SQL) + " FOR UPDATE"),
                                {"c": _cid(), "d": doc_id})).mappings().first()
    if doc_row is None:
        await db.rollback()
        raise HTTPException(status_code=404, detail="document not found")
    doc = dict(doc_row)
    versions = [dict(r) for r in (await db.execute(_VERSIONS_SQL, {"c": _cid(), "d": doc_id})).mappings().all()]

    # (a) unchanged vs this document's current or live-candidate pending hash.
    # current_content_hash counts only once a version is current: before that
    # it is v1's upload reservation, which a rejection / cancellation does not
    # release — comparing it would answer "unchanged" with no current version.
    # An in-flight v1 is still caught via its own pending_content_hash.
    has_current = doc["current_version_id"] is not None
    if (has_current and doc["current_content_hash"] == p.content_hash) or any(
            _is_live_candidate(v) and v["pending_content_hash"] == p.content_hash for v in versions):
        await db.rollback()
        return JSONResponse(status_code=200, content={"status": "unchanged", "message": MSG_UNCHANGED})

    # (b) same content as a FAILED version of this doc, byte-identical -> point at retry
    for v in versions:
        if (v["status"] == "in_review" and (v["ingest_status"] or "") == "failed"
                and v["pending_content_hash"] == p.content_hash and v["job_id"] is not None
                and await _stored_raw_sha256(deps, v["source_r2_key"]) == p.raw_sha256):
            await db.rollback()
            return JSONResponse(status_code=409, content={
                "status": "retry_available",
                "message": (f"This exact file is already stored as version {v['version_no']}, whose "
                            "ingest failed. Retry that ingest instead of uploading it again."),
                "doc_id": doc_id, "version_id": str(v["version_id"]), "job_id": str(v["job_id"]),
            })

    # (c) cross-document duplicate (task 3.2 decision 3)
    holder = await _holder(db, p.content_hash, exclude=doc_id)
    if holder:
        await db.rollback()
        return _duplicate(holder)

    # ---- writes ------------------------------------------------------------
    version_no = max((int(v["version_no"]) for v in versions if v["version_no"] is not None), default=0) + 1
    retired: list[str] = []
    for v in versions:
        if _is_stale(v):
            await db.execute(_RETIRE_SQL, {"c": _cid(), "d": doc_id, "v": str(v["version_id"])})
            await db.execute(_CANCEL_OPEN_SQL, {"c": _cid(), "v": str(v["version_id"])})
            retired.append(str(v["version_id"]))

    version_id = str(uuid.uuid4())
    key = _raw_key(doc_id, version_no, version_id, p.kind)
    supersedes = str(doc["current_version_id"]) if doc["current_version_id"] else None
    await db.execute(_INSERT_VERSION_SQL, {
        "v": version_id, "c": _cid(), "d": doc_id, "no": version_no, "key": key, "h": p.content_hash,
        "law_as_of": law_date, "person": acting_person_id,
        "reason": (change_reason or "").strip() or None, "method": p.extraction_method,
        "supersedes": supersedes,
    })
    job_id = await jobs.create_job(db, company_id=_cid(), doc_id=doc_id, version_id=version_id,
                                   register_spec=p.register_spec)
    request_id, request_state = await _open_approval_at_upload(db, doc, version_id, policy)
    registered = await _registered_doc_ids(db, doc_id)
    try:
        await _put_raw(deps, key, p, doc_id, version_no)
    except Exception as exc:
        await db.rollback()
        log.exception("raw upload to R2 failed for %s", key)
        raise HTTPException(status_code=503, detail=MSG_STORAGE) from exc
    await db.commit()

    _schedule(background, deps, job_id=job_id, p=p,
              document_title=doc["title"] or doc_id, law_as_of=law_date, source_r2_key=key,
              extraction_method=p.extraction_method, created_by_person_id=acting_person_id,
              change_reason=(change_reason or "").strip() or None, registered_doc_ids=registered)
    return JSONResponse(status_code=202, content={
        "doc_id": doc_id, "version_id": version_id, "version_no": version_no, "job_id": job_id,
        "status": "processing", "approval_request_id": request_id,
        "approval_state": request_state, "retired_version_ids": retired,
    })
