"""Task 8.1.2 / 5.8 — In-memory commit helpers, R2 report writer, run lifecycle.

The ingest data itself is written to Neon by ``store/neon.py:commit_run`` in
the caller's single transaction.  The ``company.ingest_runs`` row is NOT part
of that transaction: ``start_ingest_run`` / ``finish_ingest_run`` each open
their own short session and commit, so a crashed or rolled-back ingest still
leaves a ``running`` (or ``failed``) row behind.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from app.company_ingest.parse.models import ClauseUnit
    from app.company_ingest.run_context import RunContext
    from app.company_ingest.validate.checks import CheckOutcome

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# value_source computation (SPEC §6.2)
# ---------------------------------------------------------------------------

_REGULATORY_ROLES = {"regulatory_restatement"}
_COMPANY_ROLES = {"internal_target", "company_position"}
_TEMPLATE_ROLES = {"template_field", "definition"}


def compute_value_source(unit: "ClauseUnit", param_entry) -> str:
    """
    Compute value_source for a ParameterEntry per SPEC §6.2 rule:

    - role in {regulatory_restatement} and has citations → "regulatory"
    - role in {internal_target, company_position}        → "company"
    - role in {template_field, definition}               → "template"
    - otherwise                                          → "company"
    """
    role = unit.role

    if role in _REGULATORY_ROLES and len(unit.citations) > 0:
        return "regulatory"
    if role in _COMPANY_ROLES:
        return "company"
    if role in _TEMPLATE_ROLES:
        return "template"
    return "company"


# ---------------------------------------------------------------------------
# finalize_parameters
# ---------------------------------------------------------------------------


def finalize_parameters(units: list["ClauseUnit"]) -> None:
    """
    Set value_source on all ParameterEntry objects in place.

    Called just before commit.
    """
    for unit in units:
        for entry in unit.parameters:
            entry.value_source = compute_value_source(unit, entry)


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------


def build_run_report(
    ctx: "RunContext",
    check_outcomes: list["CheckOutcome"],
    doc_ids: list[str],
    unit_counts_by_doc: dict[str, int],
    *,
    status: str | None = None,
    error: str | None = None,
    finished_at: datetime | None = None,
) -> dict:
    """
    Build the report.json dict from ctx.to_report() plus check outcomes.

    ``status`` / ``error`` / ``finished_at`` are filled by ``finish_ingest_run``;
    a failed run is never reported as ``passed``.
    """
    report = {
        **ctx.to_report(),
        "checks": [
            {
                "check_number": o.check_number,
                "name": o.name,
                "passed": o.passed,
                "metric": o.metric,
                "details": o.details,
            }
            for o in check_outcomes
        ],
        "passed": all(o.passed for o in check_outcomes) and status != "failed",
        "documents": {
            doc_id: {"clause_count": unit_counts_by_doc.get(doc_id, 0)}
            for doc_id in doc_ids
        },
    }
    if status is not None:
        report["status"] = status
    if error is not None:
        report["error"] = error
    if finished_at is not None:
        report["finished_at"] = finished_at.isoformat()
    return report


def _default_r2_client():
    from app.company_ingest.store import r2  # lazy: boto3 client

    return r2


async def write_report(
    ctx: "RunContext",
    check_outcomes: list["CheckOutcome"],
    doc_ids: list[str],
    unit_counts_by_doc: dict[str, int],
    r2_client=None,
    *,
    status: str | None = None,
    error: str | None = None,
    finished_at: datetime | None = None,
) -> str:
    """Write ``ingest_runs/{run_id}/report.json`` to R2. Returns the R2 key.

    The key is unique per run_id and the report is regenerable, so the
    write-once guard is bypassed (``force=True``); the blocking boto3 call
    runs in a worker thread.
    """
    from app.company_ingest.store.r2_keys import report_key

    if r2_client is None:
        r2_client = _default_r2_client()
    key = report_key(ctx.company_id, str(ctx.run_id))
    report = build_run_report(
        ctx, check_outcomes, doc_ids, unit_counts_by_doc,
        status=status, error=error, finished_at=finished_at,
    )
    data = json.dumps(report, default=str).encode("utf-8")

    await asyncio.to_thread(
        r2_client.put_bytes,
        key,
        data,
        {
            "content_type": "application/json",
            "doc_id": "report",
            "version": str(ctx.run_id),
            "profile": "report",
        },
        "application/json",
        force=True,
    )
    return key


# ---------------------------------------------------------------------------
# ingest_runs lifecycle (task 5.8)
# ---------------------------------------------------------------------------


def _default_session_factory() -> Callable[[], Any]:
    from app.db import AsyncSessionLocal  # lazy: production engine

    return AsyncSessionLocal


async def start_ingest_run(
    ctx: "RunContext",
    *,
    session_factory: Callable[[], Any] | None = None,
) -> None:
    """Record ``ctx.run_id`` as ``running`` in its OWN committed transaction.

    Call BEFORE opening the ingest session / calling ``ingest_document``.
    Because it commits independently, the row survives a crash or a rollback
    of the ingest transaction.  Idempotent per run_id.
    """
    from app.company_ingest.store.neon import insert_ingest_run_started

    factory = session_factory or _default_session_factory()
    async with factory() as session:
        await insert_ingest_run_started(session, ctx)
        await session.commit()


async def finish_ingest_run(
    ctx: "RunContext",
    status: str,
    *,
    error: str | None = None,
    doc_ids: Iterable[str] = (),
    unit_counts_by_doc: dict[str, int] | None = None,
    check_outcomes: Iterable["CheckOutcome"] = (),
    r2_client=None,
    session_factory: Callable[[], Any] | None = None,
) -> str | None:
    """Write report.json to R2, then move the run row to ``status``.

    ``status`` is ``'completed'`` or ``'failed'``.  Call AFTER the ingest
    session has been committed (completed) or rolled back (failed) — never
    while it is still open.  Opens its own session and commits.

    A report-write failure is logged and recorded with ``report_r2_key=NULL``
    rather than raised, so an R2 hiccup can never leave the row ``running``.
    Returns the report key (or None if the report could not be written).
    """
    from app.company_ingest.store.neon import INGEST_RUN_TERMINAL, update_ingest_run_finished

    if status not in INGEST_RUN_TERMINAL:
        raise ValueError(
            f"ingest run status must be one of {sorted(INGEST_RUN_TERMINAL)}, got {status!r}"
        )
    finished_at = datetime.now(timezone.utc)
    report_r2_key: str | None
    try:
        report_r2_key = await write_report(
            ctx,
            list(check_outcomes),
            list(doc_ids),
            dict(unit_counts_by_doc or {}),
            r2_client,
            status=status,
            error=error,
            finished_at=finished_at,
        )
    except Exception:  # noqa: BLE001 — the status update must still happen
        logger.exception("ingest run %s: report.json write failed", ctx.run_id)
        report_r2_key = None

    factory = session_factory or _default_session_factory()
    async with factory() as session:
        await update_ingest_run_finished(
            session, ctx, status, report_r2_key, finished_at=finished_at
        )
        await session.commit()
    return report_r2_key
