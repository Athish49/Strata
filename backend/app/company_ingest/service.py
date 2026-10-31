"""Task 5.1 — the per-document ingest service (TDD §4).

``ingest_document`` ingests exactly ONE version of ONE document from text the
API layer already holds.  It replaces v1's corpus-walking batch
(``cli/ingest.py:_run``); the expensive stage functions are reused unchanged —
only intake and orchestration are new.

Preconditions owned by the caller (API layer, task 6.1):

* extraction, ``canonicalize`` / ``content_hash`` and the empty-extraction and
  duplicate guards have already run, so a duplicate never reaches this code;
* the ``company.company_documents`` row exists (``commit_run`` is called with
  no ``sources``, so it never writes that table);
* the caller commits — or rolls back — the session.  Nothing here commits.

What this service deliberately does NOT do:

* **no Qdrant indexing** — drafts and in-review versions must never be
  indexed; promotion (task 5.6) indexes the live version;
* never writes ``status``, ``is_current``, ``company_documents.current_version_id``
  or the content hash — promotion is their only writer;
* never reads the filesystem for corpus data.

Stage order actually executed (see ``ingest_document``)::

    0   document_versions row upserted BEFORE segmenting (+ law_as_of filled
        when the pre-existing row has NULL)
    1   split_front_matter                      (prose only)
    2   anchor_clauses -> segment_with_ctx      (prose)
        segment_register_text                   (registers, declared RegisterSpec)
    3   reuse_from_prior_version (task 5.2; LLM-derived fields only)
    4   enrich_citations -> enrich_parameters -> enrich_references
        -> enrich_roles -> extract_terms -> find_term_usages
    5   run_clause_enrichment (cache-backed)
    5b  run_column_roles (registers only, cache-backed)
    7   resolve_references -> find_restates_links -> build_document_scope
    8   finalize_parameters
    10  commit_run (Neon writes, caller's session, no commit)
    6   resolve_citations_for_version + read-back onto the units
    9   write_clause_snapshot (R2, keyed by the REAL version_id)

Stage 6 runs after stage 10 on purpose: the resolver reads
``company.clause_citations JOIN company.clauses`` from the database, so before
``commit_run`` has inserted those rows it would see nothing.  Running it on the
same session keeps everything in one transaction.  Its results are read back
onto the in-memory units so the R2 snapshot carries the resolved ids.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any, Iterable, Sequence

from sqlalchemy import text

from app.company_ingest.enrich.citations import enrich_citations
from app.company_ingest.enrich.parameters_regex import enrich_parameters
from app.company_ingest.enrich.references import enrich_references
from app.company_ingest.enrich.resolve_citations import resolve_citations_for_version
from app.company_ingest.enrich.resolve_citations_db import _parse_cfr_citation_raw
from app.company_ingest.enrich.roles import enrich_roles
from app.company_ingest.enrich.terms import extract_terms, find_term_usages
from app.company_ingest.extract.docx import anchor_clauses
from app.company_ingest.ids import stable_uuid
from app.company_ingest.link.document_scope import build_document_scope
from app.company_ingest.link.resolve_refs import resolve_references
from app.company_ingest.link.restates import find_restates_links
from app.company_ingest.llm.run_clause_enrichment import run_clause_enrichment
from app.company_ingest.llm.run_column_roles import run_column_roles
from app.company_ingest.parse.front_matter import split_front_matter
from app.company_ingest.parse.markdown_segmenter import segment_with_ctx
from app.company_ingest.parse.register_segmenter import segment_register_text
from app.company_ingest.register_spec import RegisterSpec
from app.company_ingest.run_context import RunContext
from app.company_ingest.store.commit import finalize_parameters
from app.company_ingest.store.neon import (
    DocumentVersionSpec,
    commit_run,
    insert_document_versions,
)
from app.company_ingest.store.snapshot import write_clause_snapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.company_ingest.parse.models import ClauseUnit

logger = logging.getLogger(__name__)

__all__ = [
    "CitationResolutionError",
    "IngestError",
    "IngestResult",
    "ingest_document",
]

#: Resolution statuses that link a citation to the knowledge base.
_RESOLVED_STATUSES = ("resolved", "resolved_rule")

#: Source systems whose citations the resolver can match against
#: ``public.code_sections``.  A prose document citing any of these must end up
#: with at least one resolved citation, or the ingest fails loudly.
_KB_SOURCE_SYSTEMS = frozenset({"iac", "cfr"})

#: Resolver outcomes meaning "the KB does not cover this title / cannot parse
#: it" — excluded from the must-resolve check.
_NOT_IN_SCOPE_STATUSES = frozenset({"out_of_scope_title", "unparsed"})


class IngestError(RuntimeError):
    """The document could not be ingested; the job should be marked failed."""


class CitationResolutionError(IngestError):
    """Citations were written but none resolved / none were visible.

    The resolver filters ``clauses.company_id = :company_id`` and returns
    ``{}`` on a mismatch instead of failing, so a ``company_id`` spelling
    difference would otherwise produce a silently empty link graph.
    """


@dataclass
class IngestResult:
    """Counters for one ingest; the job ``stats`` field is built from these."""

    version_id: str
    clause_count: int
    citations_resolved: int
    llm_calls: int
    llm_cache_hits: int
    reused_clauses: int = 0
    # --- extras (not in the TDD §4 signature, all defaulted) ---
    version_no: int | None = None
    citations_total: int = 0
    citation_status_counts: dict[str, int] = field(default_factory=dict)
    duplicate_clause_ids: int = 0
    terms: int = 0
    links: int = 0
    scope_rows: int = 0
    snapshot_r2_key: str | None = None
    stats: dict[str, int] = field(default_factory=dict)

    def to_stats(self) -> dict[str, Any]:
        """JSON-able dict for ``company.ingest_jobs.stats``."""
        return {
            "version_id": self.version_id,
            "version_no": self.version_no,
            "clause_count": self.clause_count,
            "citations_total": self.citations_total,
            "citations_resolved": self.citations_resolved,
            "citation_status_counts": dict(self.citation_status_counts),
            "llm_calls": self.llm_calls,
            "llm_cache_hits": self.llm_cache_hits,
            "reused_clauses": self.reused_clauses,
            "duplicate_clause_ids": self.duplicate_clause_ids,
            "terms": self.terms,
            "links": self.links,
            "scope_rows": self.scope_rows,
            "snapshot_r2_key": self.snapshot_r2_key,
        }


# ---------------------------------------------------------------------------
# Stage 0 — the document_versions row (inserted BEFORE segmenting)
# ---------------------------------------------------------------------------

_VERSION_ROW_SQL = text(
    """
    SELECT company_id, doc_id, version, version_no, source_r2_key,
           next_review, effective_date, approved_date, law_as_of,
           classification, regulatory_basis, render_r2_keys,
           extraction_r2_key, extraction_method, supersedes_version_id,
           created_by_person_id, change_reason
      FROM company.document_versions
     WHERE version_id = CAST(:version_id AS uuid)
    """
)

_NEXT_VERSION_NO_SQL = text(
    """
    SELECT COALESCE(MAX(version_no), 0) + 1
      FROM company.document_versions
     WHERE company_id = :company_id AND doc_id = :doc_id
    """
)

_CURRENT_VERSION_SQL = text(
    """
    SELECT current_version_id
      FROM company.company_documents
     WHERE company_id = :company_id AND doc_id = :doc_id
    """
)


_SET_LAW_AS_OF_SQL = text(
    """
    UPDATE company.document_versions
       SET law_as_of = :law_as_of
     WHERE version_id = CAST(:version_id AS uuid)
       AND law_as_of IS NULL
    """
)


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


async def _resolve_version_spec(
    session: "AsyncSession",
    *,
    company_id: str,
    doc_id: str,
    version_id: str,
    version_spec: DocumentVersionSpec | None,
    version_label: str | None,
    law_as_of: date | None,
    source_r2_key: str | None,
    extraction_r2_key: str | None,
    extraction_method: str | None,
    created_by_person_id: str | None,
    change_reason: str | None,
) -> DocumentVersionSpec:
    """Return the spec for this version's ``document_versions`` row.

    * An explicit *version_spec* wins (its ``version_id`` must match).
    * Otherwise an existing row (the API creates it at upload, TDD §7.1 step 7)
      is read back, so ``insert_document_versions``' ``ON CONFLICT`` — which
      overwrites ``source_r2_key`` / ``extraction_r2_key`` /
      ``extraction_method`` — re-writes the API's values instead of NULLs.
    * Otherwise a new spec is built with ``version_no = MAX + 1`` for
      ``(company_id, doc_id)`` and ``supersedes_version_id`` = the document's
      current version.
    """
    if version_spec is not None:
        if str(version_spec.version_id) != version_id:
            raise ValueError(
                f"version_spec.version_id {version_spec.version_id!r} != version_id {version_id!r}"
            )
        return version_spec

    row = (await session.execute(_VERSION_ROW_SQL, {"version_id": version_id})).mappings().first()
    if row is not None:
        if row["company_id"] != company_id or row["doc_id"] != doc_id:
            raise ValueError(
                f"version {version_id} belongs to ({row['company_id']!r}, {row['doc_id']!r}), "
                f"not ({company_id!r}, {doc_id!r})"
            )
        return DocumentVersionSpec(
            version_id=version_id,
            version_no=int(row["version_no"]),
            version=row["version"],
            source_r2_key=row["source_r2_key"] or source_r2_key,
            next_review=row["next_review"],
            effective_date=row["effective_date"],
            approved_date=row["approved_date"],
            law_as_of=row["law_as_of"] or law_as_of,
            classification=row["classification"] or "internal",
            regulatory_basis=list(row["regulatory_basis"] or []),
            render_r2_keys=list(row["render_r2_keys"] or []),
            extraction_r2_key=row["extraction_r2_key"] or extraction_r2_key,
            extraction_method=row["extraction_method"] or extraction_method,
            supersedes_version_id=_opt_str(row["supersedes_version_id"]),
            created_by_person_id=row["created_by_person_id"],
            change_reason=row["change_reason"],
        )

    version_no = (
        await session.execute(_NEXT_VERSION_NO_SQL, {"company_id": company_id, "doc_id": doc_id})
    ).scalar()
    current = (
        await session.execute(_CURRENT_VERSION_SQL, {"company_id": company_id, "doc_id": doc_id})
    ).scalar()
    return DocumentVersionSpec(
        version_id=version_id,
        version_no=int(version_no or 1),
        version=version_label,
        source_r2_key=source_r2_key,
        law_as_of=law_as_of,
        extraction_r2_key=extraction_r2_key,
        extraction_method=extraction_method,
        supersedes_version_id=_opt_str(current),
        created_by_person_id=created_by_person_id,
        change_reason=change_reason,
    )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Stage 3 — clause-level reuse (task 5.2)
# ---------------------------------------------------------------------------


async def _reuse_from_prior_version(
    session: "AsyncSession",
    company_id: str,
    doc_id: str,
    prior_version_id: str | None,
    units: list["ClauseUnit"],
    ctx: RunContext,
) -> int:
    """Stage 3 — clause-level reuse (task 5.2, TDD §4.2); see ``reuse.py``.

    Units whose ``text_sha256`` (+ structure) matches a clause of
    *prior_version_id* inherit its LLM-derived fields and get
    ``unit._reused = True``, so stage 5 skips them.  Citations, regex
    parameters and deterministic roles are NOT inherited — stage 4 (which runs
    after this) recomputes them from the identical text, so nothing is
    appended twice and every key is derived from the new ``version_id``.
    """
    from app.company_ingest.reuse import reuse_from_prior_version

    return await reuse_from_prior_version(
        session, company_id, doc_id, prior_version_id, units, ctx
    )


# ---------------------------------------------------------------------------
# Register citation columns (TDD §3.4 gap 2)
# ---------------------------------------------------------------------------


def _enrich_register_citations(
    units: list["ClauseUnit"],
    citation_columns: Iterable[str],
    ctx: RunContext,
) -> None:
    """Run ``enrich_citations`` over register rows, honouring the declared
    citation columns.

    ``enrich/citations._is_citation_column`` only recognises a column named
    literally ``citation`` (or ``*:citation``), so a declared column such as
    ``regulatory_authority`` would never be scanned.  The stage function is
    reused unchanged by presenting each row's citation-role cells under the
    ``"<col>:citation"`` key it does recognise, then restoring ``row_cells``.
    """
    cols = list(dict.fromkeys(citation_columns))
    saved: list[tuple["ClauseUnit", Any]] = []
    try:
        for unit in units:
            cells = unit.row_cells or {}
            saved.append((unit, unit.row_cells))
            unit.row_cells = {f"{c}:citation": cells.get(c) for c in cols if c in cells}
        enrich_citations(units, ctx)
    finally:
        for unit, cells in saved:
            unit.row_cells = cells


# ---------------------------------------------------------------------------
# Stage 6 read-back
# ---------------------------------------------------------------------------

#: Does the KB hold ANY snapshot of this title at or before the date the resolver
#: looked it up at (``law_as_of``, the resolver's global-MIN fallback, then
#: 2024-12-31; CFR gets the resolver's 14-day window)?  Asked only when a prose
#: document resolved nothing and some of its citations came back ``not_in_kb``.
_KB_TITLE_COVERED_SQL = text(
    """
    SELECT EXISTS (
        SELECT 1 FROM public.code_sections
         WHERE source_system = :source_system
           AND title_number = :title
           AND snapshot_date <= COALESCE(
                   CAST(:law_as_of AS date),
                   (SELECT MIN(law_as_of) FROM company.document_versions),
                   DATE '2024-12-31') + CAST(:window_days AS integer)
    )
    """
)

_CITATION_READBACK_SQL = text(
    """
    SELECT cc.citation_pk, cc.resolution_status, cc.code_section_id, cc.in_knowledge_base
      FROM company.clause_citations cc
      JOIN company.clauses cl ON cl.clause_pk = cc.clause_pk
     WHERE cl.version_id = CAST(:version_id AS uuid)
       AND cl.company_id = :company_id
    """
)


async def _zero_resolved_is_genuine(
    session: "AsyncSession",
    units: list["ClauseUnit"],
    law_as_of: date | None,
) -> bool:
    """True when a prose document's "0 resolved" is a real answer, not a fault.

    The must-resolve guard (TDD §5) exists to catch a resolver that could not
    look anything up: a ``company_id`` mismatch (caught earlier by the
    visibility check), rows left unprocessed (status NULL), or a ``law_as_of``
    that predates every KB snapshot.  ``not_in_kb`` alone cannot tell the last
    case from a document whose cited sections simply are not in the KB, so ask
    the KB: if it holds a snapshot of a ``not_in_kb`` citation's title at the
    lookup date, the lookup ran against real data and found nothing.
    """
    titles: set[tuple[str, str]] = set()
    for u in units:
        for c in u.citations:
            if c.resolution_status != "not_in_kb":
                continue
            ss = c.parsed.source_system
            if ss == "cfr":
                title = _parse_cfr_citation_raw(c.parsed.citation_raw or "")[0]
            else:
                title = None if c.parsed.title is None else str(c.parsed.title)
            if ss in _KB_SOURCE_SYSTEMS and title:
                titles.add((ss, title))
    for ss, title in sorted(titles):
        covered = (await session.execute(_KB_TITLE_COVERED_SQL, {
            "source_system": ss, "title": title, "law_as_of": law_as_of,
            "window_days": 14 if ss == "cfr" else 0,
        })).scalar()
        if covered:
            return True
    return False


async def _read_back_citations(
    session: "AsyncSession",
    company_id: str,
    version_id: str,
    units: list["ClauseUnit"],
) -> tuple[int, dict[str, int]]:
    """Copy resolver results from the DB onto the units.

    Returns ``(visible_rows, {status: count})`` over every citation row of
    this version visible under *company_id* — not only the rows the resolver
    touched this call, so a re-run (where everything is already terminal and
    the resolver returns ``{}``) reports the same totals.
    """
    rows = (
        await session.execute(
            _CITATION_READBACK_SQL, {"version_id": version_id, "company_id": company_id}
        )
    ).all()
    by_pk = {str(r[0]): r for r in rows}
    counts: dict[str, int] = {}
    for r in rows:
        status = r[1] or "unresolved"
        counts[status] = counts.get(status, 0) + 1

    for unit in units:
        for i, entry in enumerate(unit.citations):
            # Must mirror store/neon.py:insert_clause_citations exactly.
            pk = str(
                stable_uuid(
                    company_id, unit.version_id, unit.clause_id, str(i), entry.parsed.citation_raw
                )
            )
            row = by_pk.get(pk)
            if row is None:
                continue
            if row[1] is not None:
                entry.resolution_status = row[1]
            entry.code_section_id = _opt_str(row[2])
            if row[3] is not None:
                entry.in_knowledge_base = bool(row[3])
    return len(rows), counts


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def ingest_document(
    *,
    company_id: str,
    doc_id: str,
    version_id: str,
    markdown: str,
    register_spec: RegisterSpec | None,
    session: "AsyncSession",
    ctx: RunContext | None = None,
    # --- optional, keyword-only extras beyond the TDD §4 signature ---
    version_spec: DocumentVersionSpec | None = None,
    version_label: str | None = None,
    law_as_of: date | None = None,
    source_r2_key: str | None = None,
    extraction_r2_key: str | None = None,
    extraction_method: str | None = None,
    created_by_person_id: str | None = None,
    change_reason: str | None = None,
    document_title: str | None = None,
    register_table_id: str | None = None,
    registered_doc_ids: Sequence[str] | None = None,
    r2_client: Any = None,
) -> IngestResult:
    """Ingest one version of one document into the caller's session.

    Parameters
    ----------
    company_id
        Tenant id — use ``engine_settings.ENGINE_COMPANY_ID``.  Must equal
        ``ctx.company_id``; one spelling is used for every write, the cache
        key and the resolver filter.
    doc_id, version_id
        The system-assigned ``DOC-%06d`` id and the version's uuid.  Every
        clause is written under this ``version_id``.
    markdown
        The extractor's ``ExtractedDocument.markdown`` (UN-anchored — anchors
        are added here, after hashing).  For a register (``register_spec`` set)
        this is the decoded CSV text, already validated with
        ``validate_register_spec``.
    register_spec
        ``None`` for prose; the validated spec for a register CSV.
    session
        Caller-owned ``AsyncSession``.  Never committed here.
    ctx
        Built as ``RunContext(company_id=company_id)`` when omitted.

    The ``document_versions`` row is upserted before segmenting (``status``
    and ``is_current`` are never touched — see ``insert_document_versions``).
    Pass ``law_as_of`` when creating a new row: the resolver falls back to a
    guessed global minimum when it is NULL.
    """
    # ---- identity guards: one company_id spelling everywhere ------------
    if not company_id:
        raise ValueError("company_id is required")
    if ctx is None:
        ctx = RunContext(company_id=company_id)
    if ctx.company_id != company_id:
        raise ValueError(
            f"ctx.company_id {ctx.company_id!r} != company_id {company_id!r}; "
            "commit_run writes ctx.company_id while the resolver and LLM cache "
            "filter on company_id — they must be spelled identically"
        )
    if not doc_id:
        raise ValueError("doc_id is required")
    version_id = str(uuid.UUID(str(version_id)))  # validate + canonical form
    is_register = register_spec is not None

    stats_before = dict(ctx.stats)

    def _delta(key: str) -> int:
        return ctx.stats.get(key, 0) - stats_before.get(key, 0)

    # ---- stage 1 (prose): front matter --------------------------------------
    fm = None
    body, body_offset = markdown, 0
    if not is_register:
        fm, body, body_offset = split_front_matter(markdown, doc_id)
        if law_as_of is None:
            law_as_of = _parse_date(fm.law_as_of)

    # ---- stage 0: the document_versions row, BEFORE segmenting --------------
    spec = await _resolve_version_spec(
        session,
        company_id=company_id,
        doc_id=doc_id,
        version_id=version_id,
        version_spec=version_spec,
        version_label=version_label or (fm.version if fm else None),
        law_as_of=law_as_of,
        source_r2_key=source_r2_key,
        extraction_r2_key=extraction_r2_key,
        extraction_method=extraction_method,
        created_by_person_id=created_by_person_id,
        change_reason=change_reason,
    )
    await insert_document_versions(session, {doc_id: spec}, company_id, ctx)
    # insert_document_versions' ON CONFLICT list omits law_as_of, so a row the
    # API pre-created with NULL would keep NULL and the resolver would fall
    # back to a guessed date.  Fill it (only when NULL; nothing else touched).
    if spec.law_as_of is not None:
        await session.execute(
            _SET_LAW_AS_OF_SQL, {"law_as_of": spec.law_as_of, "version_id": version_id}
        )
    else:
        ctx.issue(
            "warning",
            "ingest_service",
            "law_as_of_missing",
            "document_versions.law_as_of is NULL; citation resolution falls back "
            "to the global MIN(law_as_of) (default 2024-12-31)",
            doc_id=doc_id,
        )

    # ---- stage 2: segment -----------------------------------------------------
    col_roles: dict[str, str | None] = {}
    if is_register:
        assert register_spec is not None
        units, col_roles = segment_register_text(
            version_id,
            doc_id,
            markdown,
            document_title or doc_id,
            ctx,
            table_id=register_table_id or doc_id,
            id_column=register_spec.id_column,
            citation_columns=register_spec.citation_columns,
        )
    else:
        anchored = anchor_clauses(body, doc_id)  # raises for an un-anchorable doc_id
        units = segment_with_ctx(version_id, doc_id, anchored, body_offset, ctx)

    if not units:
        raise IngestError(f"{doc_id}: segmentation produced no clauses")
    if any(u.version_id != version_id for u in units):  # defensive; commit_run relies on it
        raise IngestError("segmenter emitted a clause under a different version_id")
    # Table rows are keyed by their first cell, so two rows sharing it collapse
    # under ON CONFLICT (version_id, clause_id) and the second row's children
    # attach to the first's clause_pk.  Segmenter-owned; surface it loudly.
    dup_ids = sorted(cid for cid, n in Counter(u.clause_id for u in units).items() if n > 1)
    if dup_ids:
        ctx.count("duplicate_clause_ids", len(dup_ids))
        ctx.issue(
            "warning",
            "ingest_service",
            "duplicate_clause_id",
            f"{len(dup_ids)} clause_id(s) occur more than once and will collapse on write: "
            + ", ".join(dup_ids[:20]),
            doc_id=doc_id,
        )

    # ---- stage 3: clause-level reuse (task 5.2 hook) -------------------------
    reused = await _reuse_from_prior_version(
        session, company_id, doc_id, spec.supersedes_version_id, units, ctx
    )

    # ---- stage 4: deterministic enrichment -----------------------------------
    known_doc_ids = list(dict.fromkeys([doc_id, *(registered_doc_ids or [])]))
    if is_register:
        assert register_spec is not None
        citation_cols = [c for c, r in col_roles.items() if r == "citation"]
        _enrich_register_citations(units, citation_cols, ctx)
    else:
        enrich_citations(units, ctx)
    enrich_parameters(units, ctx)
    enrich_references(units, known_doc_ids, ctx)
    enrich_roles(units, ctx)
    terms = extract_terms(units, ctx)
    term_usages = find_term_usages(terms, units, ctx=ctx)

    # ---- stage 5: LLM clause enrichment (cache-backed) ------------------------
    to_enrich = [u for u in units if not getattr(u, "_reused", False)]
    await run_clause_enrichment(to_enrich, ctx, session=session)

    # ---- stage 5b: LLM column roles (registers only) --------------------------
    if is_register and not ctx.no_llm:
        sample_rows = [u.row_cells for u in units[:5] if u.row_cells]
        col_roles = await run_column_roles(
            doc_id, list(col_roles.keys()), col_roles, sample_rows, ctx, session=session
        )

    # ---- stage 7: links + scope ----------------------------------------------
    links = resolve_references(units, known_doc_ids, ctx)
    links.extend(find_restates_links(units, links, ctx))
    scope_rows = build_document_scope(
        doc_id, version_id, units, list(fm.regulatory_basis) if fm else [], ctx
    )

    # ---- stage 8 ---------------------------------------------------------------
    finalize_parameters(units)

    # ---- stage 10: Neon writes (no commit) ------------------------------------
    await commit_run(
        session=session,
        ctx=ctx,
        sources=[],            # company_documents is owned by the API layer
        register_entries=[],
        units=units,
        links=links,
        scope_rows=scope_rows,
        terms=terms,
        term_usages=term_usages,
        col_roles_map={doc_id: col_roles} if is_register else {},
        report_r2_key=None,
        version_specs={doc_id: spec},
    )

    # ---- stage 6: citation resolution (needs the rows commit_run wrote) ------
    await resolve_citations_for_version(session, company_id, version_id)
    visible, status_counts = await _read_back_citations(session, company_id, version_id, units)
    citations_total = sum(len(u.citations) for u in units)
    citations_resolved = sum(status_counts.get(s, 0) for s in _RESOLVED_STATUSES)

    if citations_total and not visible:
        raise CitationResolutionError(
            f"{doc_id}: {citations_total} citation(s) were written but none are visible "
            f"for company_id={company_id!r}, version_id={version_id} — company_id spelling mismatch?"
        )
    # In-scope = IAC/CFR citations whose title the KB covers (statuses come
    # from the read-back above).  A document citing only titles outside the
    # KB legitimately resolves 0 and must not fail.
    kb_citations = sum(
        1
        for u in units
        for c in u.citations
        if c.parsed.source_system in _KB_SOURCE_SYSTEMS
        and c.resolution_status not in _NOT_IN_SCOPE_STATUSES
    )
    if not is_register and kb_citations and citations_resolved == 0:
        if await _zero_resolved_is_genuine(session, units, spec.law_as_of):
            # Task 9.1: a real demo document cites a rule whose title is in the KB at
            # law_as_of but whose specific section is not, so 0 resolved is the correct
            # answer (v1 ingested it the same way), not a mis-keyed lookup.
            ctx.issue(
                "warning",
                "ingest_service",
                "citations_none_resolved",
                f"{kb_citations} in-scope IAC/CFR citation(s), none resolved: the KB covers "
                "the cited title(s) at law_as_of but not the cited sections/rules",
                doc_id=doc_id,
            )
        else:
            raise CitationResolutionError(
                f"{doc_id}: {kb_citations} in-scope IAC/CFR citation(s) but 0 resolved against "
                "public.code_sections — check company_id spelling, law_as_of and the KB snapshot"
            )

    # ---- stage 9: snapshot to R2, keyed by the real version_id ---------------
    if r2_client is None:
        from app.company_ingest.store import r2 as r2_client  # lazy: boto3 client
    snapshot_key = await asyncio.to_thread(
        write_clause_snapshot, units, doc_id, version_id, company_id, r2_client, ctx, True
    )

    return IngestResult(
        version_id=version_id,
        clause_count=len(units),
        citations_resolved=citations_resolved,
        llm_calls=_delta("llm_calls"),
        llm_cache_hits=_delta("llm_cache_hit"),
        reused_clauses=reused,
        version_no=spec.version_no,
        citations_total=citations_total,
        citation_status_counts=status_counts,
        duplicate_clause_ids=len(dup_ids),
        terms=len(terms),
        links=len(links),
        scope_rows=len(scope_rows),
        snapshot_r2_key=snapshot_key,
        stats={k: ctx.stats.get(k, 0) - stats_before.get(k, 0) for k in ctx.stats},
    )
