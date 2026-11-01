"""Version history and ingest-job status endpoints (task 6.4; TDD §6.3, §7.4).

* ``GET  /company/documents/{doc_id}/versions`` — every version of a document,
  newest first, with its latest approval request (+ step progress) and its
  latest ingest job, so the version-history UI (task 8.3) can render status and
  disable "approve" until the job has ``succeeded``.
* ``GET  /company/ingest-jobs/{job_id}`` — poll an ingest job.  Shaped like
  ``GET /engine/runs/{id}`` (``{"job": {...}, "stats": {...}}``) and, like it,
  readable while unfinished — but an unknown id is **404**, never 409: the
  frontend polls this.  Every poll first calls ``jobs.reclaim_if_stale`` so a
  job killed shortly before a restart (which the startup sweep skips because
  it is younger than the threshold) is failed and its hash released once it
  does go stale.
* ``POST /company/ingest-jobs/{job_id}/retry`` — re-run a ``failed`` job from
  its immutable R2 raw bytes (task 5.7 wiring contract): ``prepare_retry``
  requeues the same ``job_id``, then ``run_ingest_job`` is scheduled as a
  BackgroundTask.  202 with the same ``job_id``.

The job endpoints go through ``app.company_ingest.jobs`` (its own sessions), not
``get_db``; the jobs module is referenced as ``jobs.<fn>`` at call time so tests
can replace its functions.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.company.upload import run_ingest_with_bookkeeping
from app.company_ingest import jobs
from app.db import get_db
from app.engine.config import engine_settings

router = APIRouter(prefix="/company", tags=["company-versions"])


def _cid() -> str:
    return engine_settings.ENGINE_COMPANY_ID


def _iso(v: Any) -> Optional[str]:
    return v.isoformat() if isinstance(v, (datetime, date)) else None


def _s(v: Any) -> Optional[str]:
    return str(v) if v is not None else None


def _job_uuid(job_id: str) -> str:
    try:
        return str(uuid.UUID(str(job_id)))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=404, detail="ingest job not found")


def _stale_minutes() -> int:
    """Same knob as the startup sweep (``jobs.startup_sweep``)."""
    try:
        return int(os.environ.get("INGEST_JOB_STALE_MINUTES", jobs.DEFAULT_STALE_MINUTES))
    except ValueError:
        return jobs.DEFAULT_STALE_MINUTES


# ------------------------------------------------------------ version history
_VERSIONS_SQL = text("""
    SELECT v.version_id, v.version_no, v.version, v.status, v.is_current,
           v.effective_date, v.approved_date, v.created_at, v.created_by_person_id,
           v.change_reason, v.supersedes_version_id, v.superseded_by, v.ingest_status,
           r.request_id, r.state AS request_state, r.created_at AS request_created_at,
           r.completed_at AS request_completed_at,
           r.steps_total, r.steps_decided, r.steps_approved, r.next_step_no,
           r.next_required_role, r.next_assignee_person_id,
           j.job_id, j.state AS job_state
      FROM company.document_versions v
      LEFT JOIN LATERAL (
            SELECT ar.request_id, ar.state, ar.created_at, ar.completed_at,
                   (SELECT count(*) FROM company.approval_steps s
                     WHERE s.request_id = ar.request_id) AS steps_total,
                   (SELECT count(*) FROM company.approval_steps s
                     WHERE s.request_id = ar.request_id AND s.decision IS NOT NULL) AS steps_decided,
                   (SELECT count(*) FROM company.approval_steps s
                     WHERE s.request_id = ar.request_id AND s.decision = 'approved') AS steps_approved,
                   nx.step_no AS next_step_no, nx.required_role AS next_required_role,
                   nx.assignee_person_id AS next_assignee_person_id
              FROM company.approval_requests ar
              LEFT JOIN LATERAL (
                    SELECT s.step_no, s.required_role, s.assignee_person_id
                      FROM company.approval_steps s
                     WHERE s.request_id = ar.request_id AND s.decision IS NULL
                     ORDER BY s.step_no LIMIT 1) nx ON ar.state = 'open'
             WHERE ar.company_id = v.company_id AND ar.version_id = v.version_id
             ORDER BY ar.created_at DESC, ar.request_id DESC
             LIMIT 1) r ON true
      LEFT JOIN LATERAL (
            SELECT ij.job_id, ij.state
              FROM company.ingest_jobs ij
             WHERE ij.version_id = v.version_id
             ORDER BY ij.created_at DESC, ij.job_id DESC
             LIMIT 1) j ON true
     WHERE v.company_id = :c AND v.doc_id = :d
     ORDER BY v.version_no DESC NULLS LAST, v.created_at DESC
""")


def _version_out(r: dict) -> dict:
    approval = None
    if r.get("request_id") is not None:
        approval = {
            "request_id": str(r["request_id"]),
            "state": r["request_state"],
            "created_at": _iso(r.get("request_created_at")),
            "completed_at": _iso(r.get("request_completed_at")),
            "steps_total": int(r.get("steps_total") or 0),
            "steps_decided": int(r.get("steps_decided") or 0),
            "steps_approved": int(r.get("steps_approved") or 0),
            "next_step_no": r.get("next_step_no"),
            "next_required_role": r.get("next_required_role"),
            "next_assignee_person_id": r.get("next_assignee_person_id"),
        }
    job = None
    if r.get("job_id") is not None:
        job = {"job_id": str(r["job_id"]), "state": r["job_state"]}
    return {
        "version_id": str(r["version_id"]),
        "version_no": r["version_no"],
        "version": r.get("version"),
        "status": r["status"],
        "is_current": bool(r["is_current"]),
        "effective_date": _iso(r.get("effective_date")),
        "approved_date": _iso(r.get("approved_date")),
        "created_at": _iso(r.get("created_at")),
        "created_by_person_id": r.get("created_by_person_id"),
        "change_reason": r.get("change_reason"),
        "supersedes_version_id": _s(r.get("supersedes_version_id")),
        "superseded_by": _s(r.get("superseded_by")),
        "ingest_status": r.get("ingest_status"),
        "ingest_job": job,
        "approval": approval,
    }


@router.get("/documents/{doc_id}/versions")
async def list_versions(doc_id: str, db: AsyncSession = Depends(get_db)):
    docs = (await db.execute(
        text("SELECT doc_id, current_version_id FROM company.company_documents "
             "WHERE company_id = :c AND doc_id = :d"),
        {"c": _cid(), "d": doc_id})).mappings().all()
    if not docs:
        raise HTTPException(status_code=404, detail="document not found")
    rows = (await db.execute(_VERSIONS_SQL, {"c": _cid(), "d": doc_id})).mappings().all()
    return {"doc_id": doc_id,
            "current_version_id": _s(docs[0]["current_version_id"]),
            "versions": [_version_out(dict(r)) for r in rows]}


# ---------------------------------------------------------------- ingest jobs
def job_session_factory() -> Optional[jobs.SessionFactory]:
    """Session factory handed to the jobs module.  ``None`` = the application's
    (``jobs._default_session_factory``); tests override this dependency."""
    return None


def _job_out(job: "jobs.IngestJob") -> dict:
    return {
        "job": {
            "job_id": job.job_id,
            "doc_id": job.doc_id,
            "version_id": job.version_id,
            "state": job.state,
            "error": job.error,
            "created_at": _iso(job.created_at),
            "started_at": _iso(job.started_at),
            "finished_at": _iso(job.finished_at),
        },
        "stats": job.stats or {},
    }


@router.get("/ingest-jobs/{job_id}")
async def get_ingest_job(job_id: str, factory=Depends(job_session_factory)):
    jid = _job_uuid(job_id)
    job = await jobs.reclaim_if_stale(jid, stale_minutes=_stale_minutes(), session_factory=factory)
    if job is None:
        raise HTTPException(status_code=404, detail="ingest job not found")
    return _job_out(job)


@router.post("/ingest-jobs/{job_id}/retry", status_code=202)
async def retry_ingest_job(job_id: str, background_tasks: BackgroundTasks,
                           factory=Depends(job_session_factory),
                           db: AsyncSession = Depends(get_db)):
    jid = _job_uuid(job_id)
    try:
        prepared = await jobs.prepare_retry(jid, session_factory=factory)
    except jobs.JobNotFoundError:
        raise HTTPException(status_code=404, detail="ingest job not found")
    except jobs.JobStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except jobs.RetryError as exc:
        # IntegrityError cause: another document now holds this content hash.
        code = 409 if isinstance(exc.__cause__, IntegrityError) else 422
        raise HTTPException(status_code=code, detail=str(exc))

    job = await jobs.get_job(prepared.job_id, session_factory=factory)
    extra: dict[str, Any] = {}
    if job is not None:
        # Same title / cross-document link targets a first upload would pass, so a
        # retry segments and resolves exactly like the original attempt.
        title = (await db.execute(
            text("SELECT title FROM company.company_documents WHERE company_id = :c AND doc_id = :d"),
            {"c": job.company_id, "d": job.doc_id})).mappings().all()
        if title and title[0]["title"]:
            extra["document_title"] = title[0]["title"]
        ids = (await db.execute(
            text("SELECT doc_id FROM company.company_documents WHERE company_id = :c ORDER BY doc_id"),
            {"c": job.company_id})).mappings().all()
        extra["registered_doc_ids"] = [r["doc_id"] for r in ids]

    background_tasks.add_task(
        # The bookkeeping wrapper (not jobs.run_ingest_job) so a retry also writes its
        # ingest_runs row and promotes an auto-approved version, exactly like an upload.
        run_ingest_with_bookkeeping, prepared.job_id,
        markdown=prepared.markdown, register_spec=prepared.register_spec,
        session_factory=factory, **extra,
    )
    return {"job_id": prepared.job_id,
            "doc_id": job.doc_id if job else None,
            "version_id": job.version_id if job else None,
            "state": job.state if job else jobs.JOB_QUEUED}
