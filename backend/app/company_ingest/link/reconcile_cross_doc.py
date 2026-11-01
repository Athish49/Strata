"""Cross-document reference reconciliation (backlog-driven, run on promotion).

**Why this exists.** ``resolve_refs.resolve_references`` only ever sees the single
document being ingested in that call (TDD/architecture gap documented in
``findings_1.0_cross_document_links.md``, repo root). A ``references_clause`` ref
whose target lives in a *different* document can never resolve at ingest time, no
matter when that target document was ingested — the scoping, not timing, is the
problem. Every such miss is already recorded as an ``unresolved_ref`` warning in the
source clause's ingest run's ``report.json`` (R2), with a ``target_hint`` in
``doc_number:local_id`` form (e.g. ``"RPL-TAR-GRR-012:R01.D20"``).

This module re-reads that backlog — across every document currently live for a
company, not just the one just promoted — and retries resolution against the real
corpus via Neon (not an in-memory ``units`` list), using ``company_documents.doc_number``
to translate the hint's document prefix into an internal ``doc_id``. Resolved links
are written the same way ``store.neon.insert_clause_links`` would, with a dedicated
``method`` value (``"cross_doc_backlog"``) so they're distinguishable from same-document,
ingest-time links.

**Scope, deliberately narrow (task 1.0, option (c)):** only ``references_clause``.
That's the one link type ``app/engine/candidates.py``'s ``LINK_TYPES`` actually reads
for cross-document candidate propagation — the other four reference types and
``restates`` share the same architectural gap but have no proven engine consumer yet
(see the findings doc). Extending this to the other types is a follow-up, not this
task.

**Idempotent and best-effort.** ``link_pk`` is the same deterministic
``stable_uuid(...)`` the normal ingest path uses, so re-running this (e.g. on every
promotion) is a no-op for links already written (``ON CONFLICT DO NOTHING``). Every
step that can fail for one ref (a bad hint, a still-missing target) is caught and
counted, not raised — one bad entry in the backlog must never abort the sweep, and the
sweep itself must never abort a promotion (see ``promote.py``'s call site).
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.company_ingest.ids import stable_uuid

log = logging.getLogger(__name__)

_REF_TYPE = "references_clause"
_METHOD = "cross_doc_backlog"

_CURRENT_VERSIONS_SQL = text("""
    SELECT d.doc_id, d.current_version_id::text AS version_id, v.ingest_run_id::text AS ingest_run_id
    FROM company.company_documents d
    JOIN company.document_versions v ON v.version_id = d.current_version_id
    WHERE d.company_id = :company_id AND v.ingest_run_id IS NOT NULL
""")

_DOC_ID_BY_NUMBER_SQL = text("""
    SELECT doc_id FROM company.company_documents
    WHERE company_id = :company_id AND doc_number = :doc_number
""")

_CLAUSE_PK_CURRENT_SQL = text("""
    SELECT c.clause_pk::text AS clause_pk
    FROM company.clauses c
    JOIN company.company_documents d ON d.company_id = c.company_id AND d.doc_id = c.doc_id
    WHERE c.company_id = :company_id AND c.doc_id = :doc_id AND c.clause_id = :clause_id
      AND c.version_id = d.current_version_id
""")

_INSERT_LINK_SQL = text("""
    INSERT INTO company.clause_links
        (link_pk, company_id, from_clause_pk, to_clause_pk, to_doc_id,
         link_type, method, evidence, confidence)
    VALUES
        (:link_pk, :company_id, :from_clause_pk, :to_clause_pk, NULL,
         :link_type, :method, :evidence, 1.0)
    ON CONFLICT (link_pk) DO NOTHING
""")


@dataclass
class ReconcileResult:
    scanned: int = 0          # unresolved_ref/references_clause issues examined
    resolved: int = 0         # new clause_links rows inserted (or already present)
    still_unresolved: int = 0  # examined but target doc_number/clause not found
    skipped: int = 0          # hint missing a ':' (not a cross-document candidate) or malformed


def _default_r2_client():
    from app.company_ingest.store import r2  # lazy: boto3 client

    return r2


async def _fetch_report(r2_client, company_id: str, run_id: str) -> dict | None:
    from app.company_ingest.store.r2_keys import report_key

    key = report_key(company_id, run_id)
    try:
        data = await asyncio.to_thread(r2_client.get_bytes, key)
    except Exception:
        log.warning("cross-doc reconcile: could not fetch report %s", key, exc_info=True)
        return None
    try:
        return json.loads(data)
    except (ValueError, TypeError):
        log.warning("cross-doc reconcile: malformed report JSON at %s", key)
        return None


async def reconcile_unresolved_references(
    session: AsyncSession,
    company_id: str,
    *,
    r2_client=None,
) -> ReconcileResult:
    """Sweep every current document's ingest-time backlog of unresolved
    ``references_clause`` refs and resolve what the full corpus now makes possible.

    Safe to call repeatedly (idempotent) and safe to call on every promotion — the
    cost scales with the number of *documents*, not clauses, since it reads one
    ``report.json`` per current version.
    """
    r2_client = r2_client or _default_r2_client()
    result = ReconcileResult()

    current = (await session.execute(
        _CURRENT_VERSIONS_SQL, {"company_id": company_id}
    )).mappings().all()

    # doc_number -> doc_id translation cache (one company-wide lookup set, reused
    # across every backlog entry in this sweep rather than re-querying per entry).
    doc_number_cache: dict[str, str | None] = {}

    async def _doc_id_for_number(doc_number: str) -> str | None:
        if doc_number in doc_number_cache:
            return doc_number_cache[doc_number]
        row = (await session.execute(
            _DOC_ID_BY_NUMBER_SQL, {"company_id": company_id, "doc_number": doc_number}
        )).mappings().first()
        doc_id = row["doc_id"] if row else None
        doc_number_cache[doc_number] = doc_id
        return doc_id

    for row in current:
        from_doc_id = row["doc_id"]
        from_version_id = row["version_id"]
        run_id = row["ingest_run_id"]

        report = await _fetch_report(r2_client, company_id, run_id)
        if not report:
            continue

        for issue in report.get("issues", []):
            if issue.get("code") != "unresolved_ref":
                continue
            details = issue.get("details") or {}
            if details.get("ref_type") != _REF_TYPE:
                continue

            result.scanned += 1
            from_clause_id = issue.get("clause_id")
            hint = details.get("target_hint")
            if not from_clause_id or not hint or ":" not in hint:
                result.skipped += 1
                continue

            doc_number, local_id = hint.split(":", 1)
            target_doc_id = await _doc_id_for_number(doc_number)
            if target_doc_id is None:
                result.still_unresolved += 1
                continue

            target_clause_id = f"{target_doc_id}:{local_id}"
            to_row = (await session.execute(_CLAUSE_PK_CURRENT_SQL, {
                "company_id": company_id, "doc_id": target_doc_id, "clause_id": target_clause_id,
            })).mappings().first()
            if to_row is None:
                result.still_unresolved += 1
                continue

            from_row = (await session.execute(_CLAUSE_PK_CURRENT_SQL, {
                "company_id": company_id, "doc_id": from_doc_id, "clause_id": from_clause_id,
            })).mappings().first()
            if from_row is None:
                # The source clause is no longer in its document's current version
                # (e.g. renumbered/removed since this backlog entry was recorded).
                result.still_unresolved += 1
                continue

            link_pk = stable_uuid(
                company_id, from_version_id, from_clause_id, target_clause_id, _REF_TYPE,
            )
            await session.execute(_INSERT_LINK_SQL, {
                "link_pk": str(link_pk),
                "company_id": company_id,
                "from_clause_pk": from_row["clause_pk"],
                "to_clause_pk": to_row["clause_pk"],
                "link_type": _REF_TYPE,
                "method": _METHOD,
                "evidence": hint,
            })
            result.resolved += 1

    return result
