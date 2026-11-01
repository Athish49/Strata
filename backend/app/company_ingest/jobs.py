"""Task 5.7 — ingest jobs, failure semantics and recovery (TDD §6.2, §6.3).

Ingest runs in the web process via ``BackgroundTasks``: there is no queue and
a restart kills in-flight work.  This module makes a failed or killed ingest
leave nothing that blocks the customer.

Session separation (the important part)
---------------------------------------

=====================  ==================================================  ==========
transition             session                                             commits
=====================  ==================================================  ==========
``create_job``         the CALLER's session — same transaction as the      caller
                       document + version insert (TDD §7.1 step 7)
queued -> running      its own short session                               here
running -> succeeded   INSIDE the ingest transaction, conditional on       here (with
                       ``state = 'running'``                               the data)
* -> failed            a FRESH session, opened only after the ingest       here
                       session has been rolled back and closed; the
                       hash release happens in the same transaction
=====================  ==================================================  ==========

* ``failed`` is never written through the ingest session, so the ingest
  rollback cannot erase it.
* ``succeeded`` IS written through the ingest session, so it is atomic with the
  clauses: there is no window where data is committed but the job still says
  ``running`` (which the sweep would then mark ``failed`` and release the hash
  of a fully ingested document).  The update is conditional on
  ``state = 'running'``; if the sweep reclaimed the job meanwhile, it matches
  no row, :class:`JobReclaimedError` is raised and the ingest rolls back.
  Row locks serialise the two: whichever commits first wins.
* The failure session is opened after rollback because stage 0 of the service
  upserts the ``document_versions`` row — the ingest transaction holds that
  row lock, and the failure path updates the same row.

``run_ingest_job`` never raises (it is a BackgroundTask body) except for
``CancelledError``, which is re-raised after a best-effort ``failed`` mark.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.company_ingest.register_spec import RegisterSpec
from app.company_ingest.run_context import RunContext

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

__all__ = [
    "JOB_FAILED",
    "JOB_QUEUED",
    "JOB_RUNNING",
    "JOB_SUCCEEDED",
    "LIFECYCLE_FAILED",
    "LIFECYCLE_PENDING",
    "IngestJob",
    "JobError",
    "JobNotFoundError",
    "JobReclaimedError",
    "JobStateError",
    "PreparedRetry",
    "RetryError",
    "create_job",
    "get_job",
    "mark_failed",
    "mark_running",
    "mark_succeeded",
    "prepare_retry",
    "reclaim_if_stale",
    "release_reservation",
    "retry_job",
    "run_ingest_job",
    "startup_sweep",
    "sweep_orphaned_jobs",
]

JOB_QUEUED, JOB_RUNNING, JOB_SUCCEEDED, JOB_FAILED = "queued", "running", "succeeded", "failed"

#: ``company_documents.lifecycle_state`` while a first version's hash is reserved.
LIFECYCLE_PENDING = "pending"
#: ...and after a failed first-version ingest released it.  TDD §6.2 defines no
#: vocabulary beyond ``pending``/``active``; ``failed`` is what the UI (8.2) shows.
LIFECYCLE_FAILED = "failed"

#: Default age after which a ``running`` (or never-started ``queued``) job is
#: considered orphaned.  Non-zero because Render's zero-downtime deploy runs the
#: old instance alongside the new one for a while.
DEFAULT_STALE_MINUTES = 15

_MAX_ERROR_CHARS = 4000

SessionFactory = Callable[[], "AsyncSession"]
IngestFn = Callable[..., Awaitable[Any]]


class JobError(RuntimeError):
    """Base class for job-layer errors."""


class JobNotFoundError(JobError):
    pass


class JobStateError(JobError):
    """The job is not in a state that allows the requested transition."""


class JobReclaimedError(JobError):
    """The job stopped being ``running`` while its ingest was in flight."""


class RetryError(JobError):
    """A retry could not be prepared (raw bytes missing, unsupported type, duplicate)."""


@dataclass(frozen=True)
class IngestJob:
    job_id: str
    company_id: str
    doc_id: str
    version_id: str
    state: str
    error: str | None = None
    stats: dict | None = None
    created_at: Any = None
    started_at: Any = None
    finished_at: Any = None

    @classmethod
    def _from_row(cls, row: Any) -> "IngestJob":
        m = dict(row)
        stats = m.get("stats")
        if isinstance(stats, str):
            stats = json.loads(stats)
        return cls(
            job_id=str(m["job_id"]),
            company_id=m["company_id"],
            doc_id=m["doc_id"],
            version_id=str(m["version_id"]),
            state=m["state"],
            error=m.get("error"),
            stats=stats,
            created_at=m.get("created_at"),
            started_at=m.get("started_at"),
            finished_at=m.get("finished_at"),
        )


def _default_session_factory() -> SessionFactory:
    """The application's session factory, resolved lazily.

    Lazy so importing this module never touches ``app.db`` (which reads the
    production ``.env``); tests inject their own factory.
    """
    from app.db import AsyncSessionLocal

    return AsyncSessionLocal


def _factory(session_factory: SessionFactory | None) -> SessionFactory:
    return session_factory if session_factory is not None else _default_session_factory()


def _error_text(exc: BaseException) -> str:
    msg = f"{type(exc).__name__}: {exc}"
    return msg if len(msg) <= _MAX_ERROR_CHARS else msg[: _MAX_ERROR_CHARS - 3] + "..."


_COLS = "job_id, company_id, doc_id, version_id, state, error, stats, created_at, started_at, finished_at"


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------


async def create_job(
    session: "AsyncSession",
    *,
    company_id: str,
    doc_id: str,
    version_id: str,
    job_id: str | None = None,
    register_spec: RegisterSpec | None = None,
) -> str:
    """Insert a ``queued`` job row through the CALLER's session; returns ``job_id``.

    *register_spec* (a register-CSV upload's declared intent) is stored on the
    row as ``jsonb`` so :func:`prepare_retry` can re-ingest the raw CSV later
    without the caller having to supply it again (task 3.2).  NULL for documents.

    Does not commit.  The caller commits it together with the document /
    version rows and only THEN schedules :func:`run_ingest_job`, so the poll
    endpoint can never 404 (unlike ``engine/run.py``, which inserts inside the
    task).
    """
    job_id = str(uuid.UUID(job_id)) if job_id else str(uuid.uuid4())
    await session.execute(
        text(
            """
            INSERT INTO company.ingest_jobs
                   (job_id, company_id, doc_id, version_id, state, register_spec)
            VALUES (CAST(:job_id AS uuid), :company_id, :doc_id, CAST(:version_id AS uuid),
                    'queued', CAST(:register_spec AS jsonb))
            """
        ),
        {"job_id": job_id, "company_id": company_id, "doc_id": doc_id,
         "version_id": str(version_id),
         "register_spec": register_spec.model_dump_json() if register_spec is not None else None},
    )
    return job_id


async def get_job(job_id: str, *, session_factory: SessionFactory | None = None) -> IngestJob | None:
    async with _factory(session_factory)() as s:
        row = (
            await s.execute(
                text(f"SELECT {_COLS} FROM company.ingest_jobs WHERE job_id = CAST(:j AS uuid)"),
                {"j": str(job_id)},
            )
        ).mappings().first()
    return IngestJob._from_row(row) if row else None


async def mark_running(job_id: str, *, session_factory: SessionFactory | None = None) -> IngestJob:
    """queued -> running in its own committed session.  Raises JobStateError otherwise."""
    async with _factory(session_factory)() as s:
        row = (
            await s.execute(
                text(
                    f"""
                    UPDATE company.ingest_jobs
                       SET state = 'running', started_at = now(), error = NULL
                     WHERE job_id = CAST(:j AS uuid) AND state = 'queued'
                 RETURNING {_COLS}
                    """
                ),
                {"j": str(job_id)},
            )
        ).mappings().first()
        await s.commit()
    if row is None:
        job = await get_job(job_id, session_factory=session_factory)
        if job is None:
            raise JobNotFoundError(job_id)
        raise JobStateError(f"job {job_id} is {job.state!r}, not 'queued'")
    return IngestJob._from_row(row)


async def mark_succeeded(session: "AsyncSession", job_id: str, stats: dict[str, Any]) -> None:
    """running -> succeeded, written through the INGEST session (not committed here).

    Raises :class:`JobReclaimedError` when the job is no longer ``running``
    (the sweep reclaimed it), so the caller rolls the ingest back.
    """
    res = await session.execute(
        text(
            """
            UPDATE company.ingest_jobs
               SET state = 'succeeded', stats = CAST(:stats AS jsonb),
                   error = NULL, finished_at = now()
             WHERE job_id = CAST(:j AS uuid) AND state = 'running'
            """
        ),
        {"j": str(job_id), "stats": json.dumps(stats, default=str)},
    )
    if res.rowcount != 1:
        raise JobReclaimedError(f"job {job_id} is no longer 'running'; ingest discarded")


_RELEASE_HASH_SQL = text(
    """
    UPDATE company.company_documents
       SET current_content_hash = NULL, lifecycle_state = :failed, updated_at = now()
     WHERE company_id = :company_id AND doc_id = :doc_id
       AND lifecycle_state = :pending
       AND current_version_id IS NULL
       AND NOT EXISTS (
             SELECT 1 FROM company.document_versions ov
              WHERE ov.company_id = :company_id AND ov.doc_id = :doc_id
                AND ov.version_id <> CAST(:version_id AS uuid))
    """
)

_VERSION_FAILED_SQL = text(
    """
    UPDATE company.document_versions
       SET ingest_status = 'failed'
     WHERE version_id = CAST(:version_id AS uuid)
       AND COALESCE(ingest_status, '') <> 'ingested'
    """
)


async def release_reservation(
    session: "AsyncSession", *, company_id: str, doc_id: str, version_id: str
) -> bool:
    """Apply the failure semantics of TDD §6.2 in *session* (not committed).

    * First version — decided from THIS version, not the document's state:
      the document has no current version, is ``pending``, and no other
      version of it exists (a v2 uploaded while v1 is still in review must not
      release v1's reservation).  Then release the reserved hash and move ``lifecycle_state`` to ``failed``, so
      the same file can be uploaded again.  Returns True.
    * Later version: the document already has a current version and is not
      ``pending``, so nothing on ``company_documents`` changes; the version
      simply stays ``in_review`` (its ``status`` is never touched here).

    In both cases the version row (if it survived the rollback because the API
    pre-created it) gets ``ingest_status = 'failed'``.
    """
    res = await session.execute(
        _RELEASE_HASH_SQL,
        {"company_id": company_id, "doc_id": doc_id, "version_id": str(version_id),
         "pending": LIFECYCLE_PENDING, "failed": LIFECYCLE_FAILED},
    )
    await session.execute(_VERSION_FAILED_SQL, {"version_id": str(version_id)})
    return res.rowcount > 0


async def mark_failed(
    job_id: str, error: str, *, session_factory: SessionFactory | None = None
) -> IngestJob | None:
    """queued|running -> failed plus :func:`release_reservation`, in a FRESH
    session that is committed here.  Returns the job, or None when it was
    already terminal (nothing changed)."""
    async with _factory(session_factory)() as s:
        row = (
            await s.execute(
                text(
                    f"""
                    UPDATE company.ingest_jobs
                       SET state = 'failed', error = :err, finished_at = now()
                     WHERE job_id = CAST(:j AS uuid) AND state IN ('queued', 'running')
                 RETURNING {_COLS}
                    """
                ),
                {"j": str(job_id), "err": error[:_MAX_ERROR_CHARS]},
            )
        ).mappings().first()
        if row is None:
            await s.rollback()
            return None
        job = IngestJob._from_row(row)
        await release_reservation(
            s, company_id=job.company_id, doc_id=job.doc_id, version_id=job.version_id
        )
        await s.commit()
    return job


# ---------------------------------------------------------------------------
# The BackgroundTask body
# ---------------------------------------------------------------------------


async def run_ingest_job(
    job_id: str,
    *,
    markdown: str,
    register_spec: RegisterSpec | None = None,
    session_factory: SessionFactory | None = None,
    ctx: RunContext | None = None,
    ingest_fn: IngestFn | None = None,
    **ingest_kwargs: Any,
) -> IngestJob | None:
    """Run ``service.ingest_document`` for a queued job and record the outcome.

    *ingest_kwargs* are forwarded to ``ingest_document`` (e.g. ``document_title``,
    ``registered_doc_ids``, ``r2_client``).  ``company_id`` / ``doc_id`` /
    ``version_id`` come from the job row.  Returns the final job row; never
    raises for ingest failures.
    """
    factory = _factory(session_factory)
    if ingest_fn is None:
        from app.company_ingest.service import ingest_document as ingest_fn

    try:
        job = await mark_running(job_id, session_factory=factory)
    except JobError as exc:
        logger.warning("ingest job %s not started: %s", job_id, exc)
        return await get_job(job_id, session_factory=factory)

    from app.company_ingest.service import CitationResolutionError, IngestError

    if ctx is None:
        ctx = RunContext(company_id=job.company_id)

    error: str | None = None
    try:
        async with factory() as s:
            try:
                result = await ingest_fn(
                    company_id=job.company_id,
                    doc_id=job.doc_id,
                    version_id=job.version_id,
                    markdown=markdown,
                    register_spec=register_spec,
                    session=s,
                    ctx=ctx,
                    **ingest_kwargs,
                )
                await mark_succeeded(s, job_id, result.to_stats())
                await s.commit()
            except BaseException:
                # Roll back BEFORE the failure session opens: the ingest
                # transaction holds the document_versions row lock.
                await s.rollback()
                raise
    except (IngestError, CitationResolutionError, ValueError, JobReclaimedError) as exc:
        # Expected failures: IngestError/CitationResolutionError from the
        # service, ValueError from anchor_clauses / id guards / the R2
        # write-once guard, JobReclaimedError when the sweep won the race.
        error = _error_text(exc)
        logger.warning("ingest job %s failed: %s", job_id, error)
    except asyncio.CancelledError:
        await _best_effort_fail(job_id, "CancelledError: ingest task was cancelled", factory)
        raise
    except Exception as exc:  # never leave a job 'running'
        error = _error_text(exc)
        logger.exception("ingest job %s failed unexpectedly", job_id)

    if error is not None:
        await _best_effort_fail(job_id, error, factory)
    return await get_job(job_id, session_factory=factory)


async def _best_effort_fail(job_id: str, error: str, factory: SessionFactory) -> None:
    try:
        await mark_failed(job_id, error, session_factory=factory)
    except Exception:  # the startup sweep is the backstop
        logger.exception("could not mark ingest job %s failed", job_id)


# ---------------------------------------------------------------------------
# Orphan sweep
# ---------------------------------------------------------------------------

def _sweep_sql(single_job: bool) -> Any:
    one = "AND job_id = CAST(:j AS uuid)" if single_job else ""
    return text(
        f"""
        UPDATE company.ingest_jobs
           SET state = 'failed', finished_at = now(),
               error = 'orphaned: ' || state || :err_suffix
         WHERE ((state = 'running'
                 AND COALESCE(started_at, created_at) < now() - make_interval(mins => :minutes))
             OR (state = 'queued' AND created_at < now() - make_interval(mins => :minutes)))
           {one}
     RETURNING {_COLS}
        """
    )


async def sweep_orphaned_jobs(
    *,
    stale_minutes: int = DEFAULT_STALE_MINUTES,
    session_factory: SessionFactory | None = None,
    job_id: str | None = None,
) -> list[IngestJob]:
    """Mark ``running`` jobs started more than *stale_minutes* ago ``failed``
    and apply :func:`release_reservation` to each, in one transaction.

    Never-started ``queued`` jobs older than the threshold are reclaimed too:
    a process killed between the upload commit and the task start would
    otherwise leave the hash reserved forever.  *job_id* restricts the sweep to
    one job (see :func:`reclaim_if_stale`).
    """
    sql = _sweep_sql(job_id is not None)
    params: dict[str, Any] = {
        "minutes": int(stale_minutes),
        "err_suffix": f" for more than {int(stale_minutes)} minutes (process restarted mid-ingest?)",
    }
    if job_id is not None:
        params["j"] = str(job_id)
    async with _factory(session_factory)() as s:
        rows = (await s.execute(sql, params)).mappings().all()
        jobs = [IngestJob._from_row(r) for r in rows]
        for job in jobs:
            await release_reservation(
                s, company_id=job.company_id, doc_id=job.doc_id, version_id=job.version_id
            )
        await s.commit()
    for job in jobs:
        logger.warning("reclaimed orphaned ingest job %s (%s)", job.job_id, job.doc_id)
    return jobs


async def reclaim_if_stale(
    job_id: str,
    *,
    stale_minutes: int = DEFAULT_STALE_MINUTES,
    session_factory: SessionFactory | None = None,
) -> IngestJob | None:
    """Sweep a single job; for the poll endpoint (6.4), since the startup sweep
    misses a job killed less than *stale_minutes* before the restart.  Returns
    the (possibly updated) job."""
    await sweep_orphaned_jobs(
        stale_minutes=stale_minutes, session_factory=session_factory, job_id=job_id
    )
    return await get_job(job_id, session_factory=session_factory)


async def startup_sweep(*, timeout_s: float = 10.0) -> None:
    """App-startup hook.  Never raises and never blocks boot for long.

    ``INGEST_STARTUP_SWEEP=0`` disables it; ``INGEST_JOB_STALE_MINUTES``
    overrides the threshold.
    """
    if os.environ.get("INGEST_STARTUP_SWEEP", "1").strip().lower() in ("0", "false", "no", "off"):
        return
    try:
        minutes = int(os.environ.get("INGEST_JOB_STALE_MINUTES", DEFAULT_STALE_MINUTES))
        jobs = await asyncio.wait_for(sweep_orphaned_jobs(stale_minutes=minutes), timeout_s)
        if jobs:
            logger.warning("startup sweep reclaimed %d orphaned ingest job(s)", len(jobs))
    except Exception:
        logger.exception("ingest-job startup sweep failed; continuing startup")


# ---------------------------------------------------------------------------
# Retry from the immutable R2 raw bytes
# ---------------------------------------------------------------------------

_JOB_VERSION_SQL = text(
    f"""
    SELECT j.job_id, j.company_id, j.doc_id, j.version_id, j.state, j.register_spec,
           v.source_r2_key, v.status AS version_status, d.current_version_id, d.lifecycle_state
      FROM company.ingest_jobs j
      LEFT JOIN company.document_versions v ON v.version_id = j.version_id
      LEFT JOIN company.company_documents d
             ON d.company_id = j.company_id AND d.doc_id = j.doc_id
     WHERE j.job_id = CAST(:j AS uuid)
    """
)

_REQUEUE_SQL = text(
    """
    UPDATE company.ingest_jobs
       SET state = 'queued', error = NULL, stats = NULL,
           started_at = NULL, finished_at = NULL
     WHERE job_id = CAST(:j AS uuid) AND state = 'failed'
    """
)

_RESERVE_HASH_SQL = text(
    """
    UPDATE company.company_documents
       SET current_content_hash = :h, lifecycle_state = :pending, updated_at = now()
     WHERE company_id = :company_id AND doc_id = :doc_id AND current_version_id IS NULL
       AND NOT EXISTS (
             SELECT 1 FROM company.document_versions ov
              WHERE ov.company_id = :company_id AND ov.doc_id = :doc_id
                AND ov.version_id <> CAST(:version_id AS uuid))
    """
)


@dataclass(frozen=True)
class PreparedRetry:
    job_id: str
    markdown: str
    register_spec: RegisterSpec | None


def _stored_register_spec(value: Any) -> RegisterSpec | None:
    """``ingest_jobs.register_spec`` (jsonb; asyncpg hands it back as ``str``)."""
    if value is None:
        return None
    if isinstance(value, (str, bytes)):
        value = json.loads(value)
    try:
        return RegisterSpec.model_validate(value)
    except Exception as exc:
        raise RetryError(f"stored register_spec is invalid: {_error_text(exc)}") from exc


def _markdown_from_raw(key: str, raw: bytes, register_spec: RegisterSpec | None) -> str:
    lower = key.lower()
    if lower.endswith(".csv"):
        if register_spec is None:
            raise RetryError(f"{key} is a register CSV; retry needs its register_spec")
        return raw.decode("utf-8-sig")
    from app.company_ingest.extract import DOCX_CONTENT_TYPE, extractor_for

    if lower.endswith(".docx"):
        extractor = extractor_for(DOCX_CONTENT_TYPE)
        assert extractor is not None
        return extractor.extract(raw, key.rsplit("/", 1)[-1]).markdown
    raise RetryError(f"cannot re-extract {key!r}: unsupported file type")


async def prepare_retry(
    job_id: str,
    *,
    register_spec: RegisterSpec | None = None,
    session_factory: SessionFactory | None = None,
    get_bytes: Callable[[str], bytes] | None = None,
) -> PreparedRetry:
    """Validate a ``failed`` job, re-read its raw bytes from R2, re-extract,
    and requeue it (same ``job_id``) — re-reserving the hash for a first
    version.  Commits.  Raises before changing anything if the job is not
    ``failed`` or the bytes are unavailable; raises :class:`RetryError` (job
    stays ``failed``) if another document took the hash meanwhile.

    *register_spec*: by default the spec stored on the job row by
    :func:`create_job` is used; an explicit argument overrides it.
    """
    factory = _factory(session_factory)
    async with factory() as s:
        row = (await s.execute(_JOB_VERSION_SQL, {"j": str(job_id)})).mappings().first()
    if row is None:
        raise JobNotFoundError(job_id)
    if row["state"] != JOB_FAILED:
        raise JobStateError(f"job {job_id} is {row['state']!r}; only 'failed' jobs can be retried")
    if row["version_status"] == "retired":
        # A cancelled approval or a newer upload retired this version. Re-ingesting it
        # would only be stopped later by promote_version's status check, after paying
        # for extraction and LLM calls.
        raise JobStateError(f"version {row['version_id']} was retired; upload a new version instead of retrying")
    if register_spec is None:
        register_spec = _stored_register_spec(row["register_spec"])
    key = row["source_r2_key"]
    if not key:
        raise RetryError(f"version {row['version_id']} has no source_r2_key; re-upload required")

    if get_bytes is None:
        from app.company_ingest.store.r2 import get_bytes
    try:
        raw = await asyncio.to_thread(get_bytes, key)
    except Exception as exc:
        raise RetryError(f"could not read raw bytes {key!r}: {_error_text(exc)}") from exc
    try:
        markdown = _markdown_from_raw(key, raw, register_spec)
    except RetryError:
        raise
    except Exception as exc:
        raise RetryError(f"could not re-extract {key!r}: {_error_text(exc)}") from exc

    # Re-reserve only for a genuine first version (the SQL also requires that
    # no other version exists, so a v2 retry never overwrites v1's hash).
    first_version = row["current_version_id"] is None
    async with factory() as s:
        try:
            if first_version:
                from app.company_ingest.hashing import content_hash

                await s.execute(
                    _RESERVE_HASH_SQL,
                    {"h": content_hash(markdown), "pending": LIFECYCLE_PENDING,
                     "company_id": row["company_id"], "doc_id": row["doc_id"],
                     "version_id": str(row["version_id"])},
                )
            res = await s.execute(_REQUEUE_SQL, {"j": str(job_id)})
            if res.rowcount != 1:
                raise JobStateError(f"job {job_id} changed state during retry preparation")
            await s.execute(
                text(
                    "UPDATE company.document_versions SET ingest_status = 'pending' "
                    "WHERE version_id = CAST(:v AS uuid)"
                ),
                {"v": str(row["version_id"])},
            )
            await s.commit()
        except IntegrityError as exc:
            await s.rollback()
            raise RetryError(
                "this content is now held by another document; it cannot be re-ingested here"
            ) from exc
        except BaseException:
            await s.rollback()
            raise
    return PreparedRetry(job_id=str(job_id), markdown=markdown, register_spec=register_spec)


async def retry_job(
    job_id: str,
    *,
    register_spec: RegisterSpec | None = None,
    session_factory: SessionFactory | None = None,
    get_bytes: Callable[[str], bytes] | None = None,
    ingest_fn: IngestFn | None = None,
    ctx: RunContext | None = None,
    **ingest_kwargs: Any,
) -> IngestJob | None:
    """Retry a ``failed`` job from the immutable R2 raw bytes, to completion.

    Equivalent to :func:`prepare_retry` followed by :func:`run_ingest_job`.  An
    endpoint that must answer 202 quickly should ``await prepare_retry(...)``
    and schedule ``run_ingest_job(job_id, markdown=p.markdown, ...)`` itself.
    """
    prepared = await prepare_retry(
        job_id, register_spec=register_spec, session_factory=session_factory, get_bytes=get_bytes
    )
    return await run_ingest_job(
        prepared.job_id,
        markdown=prepared.markdown,
        register_spec=prepared.register_spec,
        session_factory=session_factory,
        ctx=ctx,
        ingest_fn=ingest_fn,
        **ingest_kwargs,
    )
