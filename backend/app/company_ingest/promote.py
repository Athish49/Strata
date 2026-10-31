"""Promotion: the single routine that makes a document version live (TDD §6, §6.1).

Everything that makes a version "current" happens here, together, in the caller's
transaction:

1. ``SELECT … FOR UPDATE`` the ``company_documents`` row. This serializes concurrent
   promotions of the same document; the prior current version is read only *after*
   the lock, so the second of two promoters sees the first one's committed state.
2. Resolve the new version's canonical content hash (see "Where the hash comes from").
3. Prior current version -> ``status='superseded'``, ``is_current=false``,
   ``superseded_by=<new>``, ``pending_content_hash=NULL``. This runs *before* step 4
   because ``document_versions_current_uq`` is not deferrable.
4. New version -> ``status='effective'``, ``is_current=true``,
   ``supersedes_version_id=<prior>``, ``approved_date`` defaulted to today, and
   ``pending_content_hash=NULL`` (the hash now lives on ``company_documents``).
5. ``company_documents`` -> ``current_version_id``, ``current_content_hash``,
   ``lifecycle_state='active'``, ``updated_at`` — one statement, so the pointer and the
   hash can never disagree.
6. Qdrant, LAST: upsert the new version's points FIRST, then delete the document's
   points whose ``version_id`` differs (§6.1). On any Qdrant/embedding failure the
   session is rolled back and :class:`PromotionRetryableError` is raised. Because the
   upsert comes first, a failure leaves the prior live version's points intact (plus,
   at worst, some extra points for the new version); a retry is idempotent because
   point ids are deterministic and the sweep is by ``doc_id``.
7. **Commit is the caller's job** (``commit=True`` does it here). This deviates from the
   literal TDD §6 step 7 on purpose: the approval decision handler
   (``api/company/org.py::_finalize_approved``) must record the approval and promote in
   the *same* transaction, so promotion cannot commit on its own.

**Where the hash comes from.** The only *durable* hash is
``company_documents.current_content_hash``; an in-flight version's hash is parked in
``document_versions.pending_content_hash`` (set at upload by tasks 6.1 / 6.2, cleared
here). Resolution order (task 3.2):

* the explicit ``content_hash`` argument, when a caller has it in hand;
* otherwise ``document_versions.pending_content_hash`` of the version being promoted —
  the normal path for the approval handler, and the only one for a v2+ version;
* otherwise the first-version reservation from TDD §6.2: while a new document's first
  version is pending, its hash already sits on ``company_documents.current_content_hash``
  with ``lifecycle_state='pending'`` and ``current_version_id IS NULL``;
* otherwise :class:`PromotionHashUnavailable`. Promotion never keeps the previous
  version's hash and never writes NULL — either would silently break the duplicate gate.

**Live-only Qdrant.** Presence in ``company_clauses`` means live. Nothing else indexes:
ingest (task 5.1) never touches Qdrant, so the clauses are loaded back from
``company.clauses`` (which holds resolved citations) and indexed here.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext

log = logging.getLogger(__name__)

__all__ = [
    "PromotionConflict",
    "PromotionError",
    "PromotionHashUnavailable",
    "PromotionNotReady",
    "PromotionResult",
    "PromotionRetryableError",
    "load_version_units",
    "promote_version",
    "reindex_document",
]

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
# A version may only be promoted from these states. 'approved' is tolerated for rows
# written by the pre-5.6 approval handler, which set 'approved' without promoting.
_PROMOTABLE = ("in_review", "approved")


# --------------------------------------------------------------------- errors
class PromotionError(Exception):
    """Promotion did not happen. The session has been rolled back."""

    retryable = False


class PromotionNotReady(PromotionError):
    """Unknown version, wrong document, not ingested, or not in a promotable state."""


class PromotionHashUnavailable(PromotionError):
    """No pending content hash could be found for the version (see module docstring)."""


class PromotionConflict(PromotionError):
    """The new hash is already the live hash of another document."""


class PromotionRetryableError(PromotionError):
    """Qdrant (or embedding) failed. Postgres was rolled back; retrying is safe."""

    retryable = True


@dataclass(frozen=True)
class PromotionResult:
    version_id: str
    prior_version_id: Optional[str]
    content_hash: str
    points_indexed: int
    already_current: bool = False


# --------------------------------------------------------------------- SQL
_LOCK_DOC = text(
    "SELECT current_version_id, current_content_hash, lifecycle_state "
    "FROM company.company_documents WHERE company_id = :c AND doc_id = :d FOR UPDATE"
)
_TARGET = text(
    "SELECT doc_id, status, ingest_status, is_current, pending_content_hash "
    "FROM company.document_versions "
    "WHERE company_id = :c AND version_id = CAST(:v AS uuid)"
)
_SUPERSEDE = text(
    "UPDATE company.document_versions "
    "SET status = 'superseded', is_current = false, superseded_by = CAST(:v AS uuid), "
    "    pending_content_hash = NULL "
    "WHERE company_id = :c AND doc_id = :d AND version_id <> CAST(:v AS uuid) "
    "AND (is_current OR version_id = CAST(:cur AS uuid)) "
    "RETURNING version_id"
)
_MAKE_CURRENT = text(
    "UPDATE company.document_versions "
    "SET status = 'effective', is_current = true, pending_content_hash = NULL, "
    "    supersedes_version_id = COALESCE(CAST(:prior AS uuid), supersedes_version_id), "
    "    approved_date = COALESCE(approved_date, CURRENT_DATE), "
    # A version takes effect when it becomes current. A date set earlier (extraction or the
    # metadata PATCH) is kept; otherwise it would stay NULL on an `effective` version.
    "    effective_date = COALESCE(effective_date, CURRENT_DATE) "
    "WHERE company_id = :c AND version_id = CAST(:v AS uuid)"
)
_POINT_DOC = text(
    "UPDATE company.company_documents "
    "SET current_version_id = CAST(:v AS uuid), current_content_hash = :h, "
    "    lifecycle_state = 'active', updated_at = now() "
    "WHERE company_id = :c AND doc_id = :d"
)

_CLAUSES = text(
    "SELECT clause_pk, doc_id, clause_id, local_id, parent_clause_id, ordinal, unit_kind, "
    "heading_path, section_kind, sheet_no, table_id, row_cells, text_raw, text_norm, "
    "text_sha256, char_start, char_end, line_start, clause_role, role_method, assessable, "
    "normalized_statement, topic_terms "
    "FROM company.clauses WHERE company_id = :c AND doc_id = :d AND version_id = CAST(:v AS uuid) "
    "ORDER BY ordinal, clause_id"
)
_CITATIONS = text(
    "SELECT cc.clause_pk, cc.citation_raw, cc.source_system, cc.title, cc.article, cc.rule, "
    "cc.section FROM company.clause_citations cc JOIN company.clauses c ON c.clause_pk = cc.clause_pk "
    "WHERE c.company_id = :c AND c.doc_id = :d AND c.version_id = CAST(:v AS uuid) "
    "ORDER BY cc.span_start NULLS LAST, cc.citation_pk"
)
_PARAMS = text(
    "SELECT p.clause_pk, p.kind, p.unit FROM company.clause_parameters p "
    "JOIN company.clauses c ON c.clause_pk = p.clause_pk "
    "WHERE c.company_id = :c AND c.doc_id = :d AND c.version_id = CAST(:v AS uuid) "
    "ORDER BY p.span_start NULLS LAST, p.parameter_pk"
)
_TERMS = text(
    "SELECT tu.clause_pk, dt.term FROM company.term_usages tu "
    "JOIN company.defined_terms dt ON dt.term_pk = tu.term_pk "
    "JOIN company.clauses c ON c.clause_pk = tu.clause_pk "
    "WHERE c.company_id = :c AND c.doc_id = :d AND c.version_id = CAST(:v AS uuid) "
    "ORDER BY dt.term"
)


# --------------------------------------------------------------------- units
def _citation_keys(row: Any) -> tuple[Optional[str], Optional[str]]:
    """(normalized_key, rule_key) for a stored clause_citations row.

    IAC keys are rebuilt from the structured columns exactly as
    ``citations_grammar._make_iac`` builds them (``rule`` is stored as
    ``"<article>-<section>"``). Anything else is re-parsed from ``citation_raw``.
    """
    if row["source_system"] == "iac" and row["title"] is not None and row["article"]:
        base = f"{row['title']} IAC {row['article']}"
        if row["rule"]:
            return f"{row['title']} IAC {row['rule']}", base
        return base, base
    from app.company_ingest.enrich.citations_grammar import parse_citation

    parsed = parse_citation(row["citation_raw"] or "")
    if not parsed:
        return None, None
    return parsed[0].normalized_key, parsed[0].rule_key


async def load_version_units(
    session: AsyncSession, company_id: str, doc_id: str, version_id: str
) -> list[ClauseUnit]:
    """Rebuild the version's ``ClauseUnit``s from ``company.clauses`` for indexing.

    Only the attributes ``index.upsert`` reads are populated beyond the clause row:
    citations carry ``.parsed.normalized_key/.rule_key``, parameters ``.kind/.unit``,
    terms ``.term``.
    """
    p = {"c": company_id, "d": doc_id, "v": version_id}
    rows = (await session.execute(_CLAUSES, p)).mappings().all()
    units: dict[Any, ClauseUnit] = {}
    for r in rows:
        units[r["clause_pk"]] = ClauseUnit(
            version_id=version_id,
            doc_id=r["doc_id"],
            clause_id=r["clause_id"],
            local_id=r["local_id"] or "",
            parent_clause_id=r["parent_clause_id"],
            unit_kind=r["unit_kind"] or "",
            heading_path=list(r["heading_path"] or []),
            section_kind=r["section_kind"] or "",
            ordinal=r["ordinal"] or 0,
            char_start=r["char_start"] or 0,
            char_end=r["char_end"] or 0,
            line_start=r["line_start"] or 0,
            text_raw=r["text_raw"] or "",
            text_norm=r["text_norm"] or "",
            text_sha256=r["text_sha256"] or "",
            sheet_no=r["sheet_no"],
            table_id=r["table_id"],
            row_cells=r["row_cells"],
            role=r["clause_role"],
            role_method=r["role_method"],
            assessable=r["assessable"],
            normalized_statement=r["normalized_statement"],
            topic_terms=list(r["topic_terms"] or []),
        )
    if not units:
        return []
    for r in (await session.execute(_CITATIONS, p)).mappings().all():
        nk, rk = _citation_keys(r)
        units[r["clause_pk"]].citations.append(
            SimpleNamespace(parsed=SimpleNamespace(normalized_key=nk, rule_key=rk,
                                                   citation_raw=r["citation_raw"])))
    for r in (await session.execute(_PARAMS, p)).mappings().all():
        units[r["clause_pk"]].parameters.append(SimpleNamespace(kind=r["kind"], unit=r["unit"]))
    for r in (await session.execute(_TERMS, p)).mappings().all():
        units[r["clause_pk"]].terms.append(SimpleNamespace(term=r["term"]))
    return list(units.values())


# --------------------------------------------------------------------- Qdrant
async def reindex_document(
    company_id: str,
    doc_id: str,
    version_id: str,
    units: list[ClauseUnit],
    ctx: Optional[RunContext] = None,
    *,
    client: Any = None,
    batch_size: int = 128,
) -> int:
    """Upsert this version's points, THEN sweep every other point of this doc (TDD §6.1).

    Order matters (task 3.2). If the upsert fails, nothing has been deleted, so the
    prior live version — which Postgres is about to roll back to — keeps its points.
    If the sweep fails after the upsert, the collection briefly holds the new
    version's points *as well as* the old ones; the next promotion (or the retry)
    sweeps them. Extras are harmless; missing live points are not.

    * Point ids are ``stable_uuid(company_id, version_id, clause_id)`` with the real id,
      so the new version's points never overwrite the prior version's.
    * The sweep filters on ``project`` + ``company_id`` + ``doc_id`` with
      ``must_not version_id = <this version>`` — **not** on a specific old
      ``version_id`` — so orphans from v1's ``stable_uuid(company, "v1", clause)``
      scheme, and from any earlier version, are swept.
    * EVERY indexable unit is embedded, including clauses task 5.2 reused from the prior
      version. ``_reused`` / ``reuse.units_needing_embedding`` mean "skip the LLM"; they
      must not be applied here: the reused clause's old point belongs to the old
      ``version_id`` and is removed by the sweep. Re-embedding locally costs nothing.

    Returns the number of points written. Raises whatever the client raises.
    """
    from qdrant_client.models import (  # type: ignore[import-untyped]
        FieldCondition,
        Filter,
        FilterSelector,
        MatchValue,
    )

    from app.company_ingest.index import upsert as _upsert
    from app.config import settings

    ctx = ctx or RunContext(company_id=company_id)
    client = client or _upsert._make_client()
    batches = _upsert.build_points(units, company_id, version_id, batch_size)

    written = 0
    for points in batches:
        client.upsert(collection_name=_upsert.COMPANY_COLLECTION, points=points, wait=True)
        written += len(points)
        ctx.count("clauses_indexed", len(points))

    client.delete(
        collection_name=_upsert.COMPANY_COLLECTION,
        points_selector=FilterSelector(filter=Filter(
            must=[
                FieldCondition(key="project", match=MatchValue(value=settings.QDRANT_PROJECT_TAG)),
                FieldCondition(key="company_id", match=MatchValue(value=company_id)),
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
            ],
            # The same string build_points wrote into each payload's version_id.
            must_not=[FieldCondition(key="version_id", match=MatchValue(value=version_id))],
        )),
        wait=True,
    )
    return written


# --------------------------------------------------------------------- promotion
def _uuid_str(value: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise PromotionNotReady(f"invalid version_id {value!r}") from exc


async def promote_version(
    session: AsyncSession,
    company_id: str,
    doc_id: str,
    version_id: str,
    *,
    content_hash: Optional[str] = None,
    qdrant_client: Any = None,
    ctx: Optional[RunContext] = None,
    commit: bool = False,
) -> PromotionResult:
    """Make ``version_id`` the current version of ``doc_id``. One transaction (TDD §6).

    Runs inside the caller's transaction and does not commit unless ``commit=True``
    (see module docstring, step 7). On any :class:`PromotionError` the session has been
    rolled back — including the caller's own uncommitted writes, which is what the
    approval handler wants: the decision is not recorded unless promotion succeeds.

    ``content_hash``: the version's canonical ``hashing.content_hash``. Optional: when
    omitted, ``document_versions.pending_content_hash`` and then the first-version
    reservation are used (module docstring).
    """
    try:
        return await _promote(session, company_id, doc_id, _uuid_str(version_id),
                              content_hash, qdrant_client, ctx, commit)
    except PromotionError:
        await session.rollback()
        raise


async def _promote(session, company_id, doc_id, vid, content_hash, qdrant_client, ctx, commit):
    # 1. Serialize concurrent promotions of this document.
    doc = (await session.execute(_LOCK_DOC, {"c": company_id, "d": doc_id})).mappings().first()
    if doc is None:
        raise PromotionNotReady(f"document {doc_id!r} not found for company {company_id!r}")

    target = (await session.execute(_TARGET, {"c": company_id, "v": vid})).mappings().first()
    if target is None or target["doc_id"] != doc_id:
        raise PromotionNotReady(f"version {vid} is not a version of {doc_id}")

    cur = str(doc["current_version_id"]) if doc["current_version_id"] else None
    if target["is_current"] and cur == vid:
        # Lost a race to an identical promotion (or a retry after commit): nothing to do.
        return PromotionResult(vid, None, doc["current_content_hash"] or "", 0, already_current=True)
    if target["status"] not in _PROMOTABLE:
        raise PromotionNotReady(f"version {vid} is {target['status']!r}; only "
                                f"{'/'.join(_PROMOTABLE)} versions can be promoted")
    if target["ingest_status"] != "ingested":
        # Promoting a version with no clauses would make an empty version current (§6.2).
        raise PromotionNotReady(f"version {vid} ingest_status is {target['ingest_status']!r}, "
                                "not 'ingested'")

    # 2. The new version's canonical hash: argument -> pending_content_hash ->
    #    first-version reservation.
    pending = (target["pending_content_hash"] or "").strip() or None
    if content_hash is not None:
        if not _HEX64.match(content_hash):
            raise PromotionHashUnavailable("content_hash must be 64 lowercase hex characters")
        new_hash = content_hash
    elif pending is not None:
        if not _HEX64.match(pending):
            raise PromotionHashUnavailable(
                f"document_versions.pending_content_hash for {vid} is not 64 lowercase hex")
        new_hash = pending
    elif cur is None and doc["lifecycle_state"] == "pending" and doc["current_content_hash"]:
        new_hash = doc["current_content_hash"].strip()
    else:
        raise PromotionHashUnavailable(
            f"no pending content hash recorded for {doc_id} version {vid} "
            "(document_versions.pending_content_hash is NULL)")

    # 3. Supersede the prior current version (before 4: the partial unique index).
    superseded = (await session.execute(
        _SUPERSEDE, {"c": company_id, "d": doc_id, "v": vid, "cur": cur})).scalars().all()
    prior = cur if cur and cur != vid else (str(superseded[0]) if superseded else None)

    # 4. The new version becomes current.
    await session.execute(_MAKE_CURRENT, {"c": company_id, "v": vid, "prior": prior})

    # 5. Pointer and hash, in one statement.
    try:
        await session.execute(_POINT_DOC, {"c": company_id, "d": doc_id, "v": vid, "h": new_hash})
    except IntegrityError as exc:
        if "company_documents_content_hash_uq" in str(exc):
            raise PromotionConflict(
                f"another document already has this content as its live version "
                f"(hash {new_hash[:12]}…)") from exc
        raise

    # 6. Qdrant, last.
    units = await load_version_units(session, company_id, doc_id, vid)
    try:
        written = await reindex_document(company_id, doc_id, vid, units, ctx, client=qdrant_client)
    except Exception as exc:  # noqa: BLE001 — any index failure must undo Postgres
        log.exception("promotion of %s/%s rolled back: Qdrant reindex failed", doc_id, vid)
        raise PromotionRetryableError(
            f"Qdrant reindex failed for {doc_id} version {vid}; nothing was promoted, "
            "retry is safe") from exc

    # 7.
    if commit:
        await session.commit()
    log.info("promoted %s version %s (prior %s, %d points)", doc_id, vid, prior, written)
    return PromotionResult(vid, prior, new_hash, written)
