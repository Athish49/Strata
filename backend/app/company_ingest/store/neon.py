"""Bulk insert helpers for the company.* Neon schema.

All public functions accept an SQLAlchemy AsyncSession and return nothing
(or a mapping needed by downstream callers).  Call them inside a single
transaction managed by the CLI.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.company_ingest.ids import stable_uuid

if TYPE_CHECKING:
    from app.company_ingest.enrich.terms import TermEntry, TermUsage
    from app.company_ingest.link.document_scope import DocumentScopeRow
    from app.company_ingest.link.resolve_refs import ClauseLink
    from app.company_ingest.parse.models import ClauseUnit
    from app.company_ingest.run_context import RunContext

logger = logging.getLogger(__name__)

# The only status a freshly-ingested version may carry.  The DB enforces
# ``document_versions_status_ck`` over
# ('draft','in_review','approved','effective','superseded','retired'); the
# pre-v2 writer wrote 'active'/'Approved', both of which are now rejected.
NEW_VERSION_STATUS = "in_review"


@dataclass
class DocumentVersionSpec:
    """Everything the writer needs for ONE company.document_versions row.

    The caller owns ``version_id`` and ``version_no`` — they are *not* derived
    from a version label here.  ``version_no`` is the system-assigned
    sequential integer; ``version`` is the customer-facing label ("v5.1").

    A new version is always written ``status='in_review'`` and
    ``is_current=false``; promotion (task 5.6) is the only writer of
    ``is_current`` / ``company_documents.current_version_id``.
    """

    version_id: str
    version_no: int
    version: str | None = None
    source_r2_key: str | None = None
    next_review: date | None = None
    effective_date: date | None = None
    approved_date: date | None = None
    law_as_of: date | None = None
    classification: str = "internal"
    regulatory_basis: list[str] = field(default_factory=list)
    render_r2_keys: list[str] = field(default_factory=list)
    extraction_r2_key: str | None = None
    extraction_method: str | None = None
    supersedes_version_id: str | None = None
    created_by_person_id: str | None = None
    change_reason: str | None = None


def _term_pk(company_id: str, version_id: str, term_norm: str) -> uuid.UUID:
    """Version-scoped defined_terms primary key.

    Single source of truth: ``insert_defined_terms`` and
    ``insert_term_usages_with_map`` must agree, or every term_usages row points
    at a term that does not exist.
    """
    return stable_uuid(company_id, version_id, term_norm)


def build_clause_version_map(units: list["ClauseUnit"]) -> dict[str, str]:
    """{clause_id: version_id} for the units in this write.

    Raises if one clause_id appears under two version_ids: ``clause_pk_map``
    and the child maps are keyed by bare ``clause_id`` (``DOC:LOCAL``, identical
    across versions), so mixing two versions of one document into a single
    write silently attaches one version's children to the other's clause_pk.
    One version per document per call is the contract.
    """
    out: dict[str, str] = {}
    for unit in units:
        seen = out.get(unit.clause_id)
        if seen is not None and seen != unit.version_id:
            raise ValueError(
                f"clause_id {unit.clause_id!r} appears under two version_ids "
                f"({seen} and {unit.version_id}); write one version per "
                "document per call"
            )
        out[unit.clause_id] = unit.version_id
    return out


# ---------------------------------------------------------------------------
# ingest_runs
# ---------------------------------------------------------------------------


async def insert_ingest_run(
    session: AsyncSession,
    ctx: "RunContext",
    status: str,
    report_r2_key: str | None,
) -> None:
    """Upsert one row into company.ingest_runs (legacy one-shot writer).

    Kept for backward compatibility; the run lifecycle now goes through
    ``insert_ingest_run_started`` / ``update_ingest_run_finished`` (task 5.8).
    """
    flags = json.dumps({
        "no_llm": ctx.no_llm,
        "no_datasets": ctx.no_datasets,
        "rebuild": ctx.rebuild,
    })
    await session.execute(
        text("""
            INSERT INTO company.ingest_runs
                (run_id, company_id, started_at, finished_at, flags, status, report_r2_key)
            VALUES
                (:run_id, :company_id, :started_at, :finished_at, CAST(:flags AS jsonb), :status, :report_r2_key)
            ON CONFLICT (run_id) DO UPDATE SET
                finished_at    = EXCLUDED.finished_at,
                status         = EXCLUDED.status,
                report_r2_key  = EXCLUDED.report_r2_key
        """),
        {
            "run_id": str(ctx.run_id),
            "company_id": ctx.company_id,
            "started_at": ctx.started_at,
            "finished_at": datetime.now(timezone.utc),
            "flags": flags,
            "status": status,
            "report_r2_key": report_r2_key,
        },
    )


# Run lifecycle (task 5.8).  A run row is inserted ``running`` at START in its
# own short transaction (see ``store/commit.py:start_ingest_run``) so that a
# crashed or rolled-back ingest still leaves a trace, then moved to a terminal
# status by ``finish_ingest_run``.  ``commit_run`` no longer touches this table.
INGEST_RUN_RUNNING = "running"
INGEST_RUN_COMPLETED = "completed"
INGEST_RUN_FAILED = "failed"
INGEST_RUN_TERMINAL = frozenset({INGEST_RUN_COMPLETED, INGEST_RUN_FAILED})


async def insert_ingest_run_started(session: AsyncSession, ctx: "RunContext") -> None:
    """Insert the ``running`` row for ``ctx.run_id`` (``finished_at`` NULL).

    Idempotent: a second call for the same run_id is a no-op, and it never
    downgrades a row that already reached a terminal status.
    """
    flags = json.dumps({
        "no_llm": ctx.no_llm,
        "no_datasets": ctx.no_datasets,
        "rebuild": ctx.rebuild,
    })
    await session.execute(
        text("""
            INSERT INTO company.ingest_runs
                (run_id, company_id, started_at, finished_at, flags, status, report_r2_key)
            VALUES
                (:run_id, :company_id, :started_at, NULL, CAST(:flags AS jsonb), :status, NULL)
            ON CONFLICT (run_id) DO NOTHING
        """),
        {
            "run_id": str(ctx.run_id),
            "company_id": ctx.company_id,
            "started_at": ctx.started_at,
            "flags": flags,
            "status": INGEST_RUN_RUNNING,
        },
    )


async def update_ingest_run_finished(
    session: AsyncSession,
    ctx: "RunContext",
    status: str,
    report_r2_key: str | None,
    finished_at: datetime | None = None,
) -> None:
    """Move the run row to a terminal ``status`` and record ``report_r2_key``.

    An upsert, so it still records the outcome if the start row is missing
    (e.g. ``start_ingest_run`` itself failed).
    """
    if status not in INGEST_RUN_TERMINAL:
        raise ValueError(
            f"ingest run status must be one of {sorted(INGEST_RUN_TERMINAL)}, got {status!r}"
        )
    flags = json.dumps({
        "no_llm": ctx.no_llm,
        "no_datasets": ctx.no_datasets,
        "rebuild": ctx.rebuild,
    })
    await session.execute(
        text("""
            INSERT INTO company.ingest_runs
                (run_id, company_id, started_at, finished_at, flags, status, report_r2_key)
            VALUES
                (:run_id, :company_id, :started_at, :finished_at, CAST(:flags AS jsonb), :status, :report_r2_key)
            ON CONFLICT (run_id) DO UPDATE SET
                finished_at    = EXCLUDED.finished_at,
                status         = EXCLUDED.status,
                report_r2_key  = EXCLUDED.report_r2_key
        """),
        {
            "run_id": str(ctx.run_id),
            "company_id": ctx.company_id,
            "started_at": ctx.started_at,
            "finished_at": finished_at or datetime.now(timezone.utc),
            "flags": flags,
            "status": status,
            "report_r2_key": report_r2_key,
        },
    )


# ---------------------------------------------------------------------------
# company_documents + document_versions
# ---------------------------------------------------------------------------


async def insert_company_documents(
    session: AsyncSession,
    sources: list[Any],
    register_entries: list[Any],
    company_id: str,
    ctx: "RunContext",
) -> None:
    """Upsert one row per unique doc_id into company.company_documents.

    ``sources`` items need ``.doc_id`` (and optionally ``.doc_class``);
    ``register_entries`` items need ``.doc_id``, ``.title``, ``.owner_id``,
    ``.reviewer_id`` and ``.approver_id``.  (These were the deleted
    ``collect/`` package's ``SourceFile`` / ``RegisterEntry``; any duck-typed
    object works.)

    ``current_version_id`` is deliberately NOT written here.  A newly ingested
    version is ``in_review`` and must not become the document's current version
    until promotion (task 5.6) says so — the pre-v2 code set
    ``current_version_id = EXCLUDED.current_version_id`` on conflict, which made
    every freshly uploaded v2 current (and unapprovably live) on sight.
    """
    # Build a lookup from register entries
    reg_map: dict[str, Any] = {r.doc_id: r for r in register_entries}

    seen: set[str] = set()
    for sf in sources:
        doc_id = sf.doc_id
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        reg = reg_map.get(doc_id)
        await session.execute(
            text("""
                INSERT INTO company.company_documents
                    (company_id, doc_id, title, doc_class, vertical,
                     owner_id, reviewer_id, approver_id, review_cycle)
                VALUES
                    (:company_id, :doc_id, :title, :doc_class, :vertical,
                     :owner_id, :reviewer_id, :approver_id, :review_cycle)
                ON CONFLICT (company_id, doc_id) DO UPDATE SET
                    title       = EXCLUDED.title,
                    doc_class   = EXCLUDED.doc_class,
                    owner_id    = EXCLUDED.owner_id,
                    reviewer_id = EXCLUDED.reviewer_id,
                    approver_id = EXCLUDED.approver_id
            """),
            {
                "company_id": company_id,
                "doc_id": doc_id,
                "title": reg.title if reg else sf.doc_id,
                "doc_class": getattr(sf, "doc_class", None),
                "vertical": None,
                "owner_id": reg.owner_id if reg else None,
                "reviewer_id": reg.reviewer_id if reg else None,
                "approver_id": reg.approver_id if reg else None,
                "review_cycle": None,
            },
        )
    ctx.count("company_documents_upserted", len(seen))


async def insert_document_versions(
    session: AsyncSession,
    version_specs: dict[str, DocumentVersionSpec],
    company_id: str,
    ctx: "RunContext",
) -> None:
    """Insert one company.document_versions row per {doc_id: spec} entry.

    Schema notes (migration f7b2c91d4a08):

    * ``file_sha256`` is DROPPED — one hash per document, on
      ``company_documents.current_content_hash``, written at promotion (5.6).
    * ``supersedes`` (version *string*) is DROPPED, replaced by
      ``supersedes_version_id uuid``.
    * ``version_no int NOT NULL`` and ``is_current boolean NOT NULL`` are new.
    * ``status`` is CHECK-constrained; new versions are ``in_review``.

    ``ON CONFLICT (version_id) DO UPDATE`` touches only the ingest bookkeeping
    columns.  ``status`` and ``is_current`` are never in the update list: a
    re-ingest of an already promoted version must not demote it.
    """
    for doc_id, spec in version_specs.items():
        await session.execute(
            text("""
                INSERT INTO company.document_versions
                    (version_id, company_id, doc_id, version, version_no, status,
                     is_current, effective_date, approved_date, law_as_of, next_review,
                     supersedes_version_id, classification, regulatory_basis,
                     source_r2_key, render_r2_keys, extraction_r2_key, extraction_method,
                     created_by_person_id, change_reason,
                     ingest_status, ingested_at, ingest_run_id)
                VALUES
                    (:version_id, :company_id, :doc_id, :version, :version_no, :status,
                     false, :effective_date, :approved_date, :law_as_of, :next_review,
                     :supersedes_version_id, :classification, :regulatory_basis,
                     :source_r2_key, :render_r2_keys, :extraction_r2_key, :extraction_method,
                     :created_by_person_id, :change_reason,
                     :ingest_status, :ingested_at, :ingest_run_id)
                ON CONFLICT (version_id) DO UPDATE SET
                    ingest_status     = EXCLUDED.ingest_status,
                    ingested_at       = EXCLUDED.ingested_at,
                    ingest_run_id     = EXCLUDED.ingest_run_id,
                    source_r2_key     = EXCLUDED.source_r2_key,
                    extraction_r2_key = EXCLUDED.extraction_r2_key,
                    extraction_method = EXCLUDED.extraction_method
            """),
            {
                "version_id": spec.version_id,
                "company_id": company_id,
                "doc_id": doc_id,
                "version": spec.version,
                "version_no": spec.version_no,
                "status": NEW_VERSION_STATUS,
                "effective_date": spec.effective_date,
                "approved_date": spec.approved_date,
                "law_as_of": spec.law_as_of,
                "next_review": spec.next_review,
                "supersedes_version_id": spec.supersedes_version_id,
                "classification": spec.classification,
                "regulatory_basis": list(spec.regulatory_basis),
                "source_r2_key": spec.source_r2_key,
                "render_r2_keys": list(spec.render_r2_keys),
                "extraction_r2_key": spec.extraction_r2_key,
                "extraction_method": spec.extraction_method,
                "created_by_person_id": spec.created_by_person_id,
                "change_reason": spec.change_reason,
                "ingest_status": "ingested",
                "ingested_at": datetime.now(timezone.utc),
                "ingest_run_id": str(ctx.run_id),
            },
        )
    ctx.count("document_versions_upserted", len(version_specs))


# ---------------------------------------------------------------------------
# clauses
# ---------------------------------------------------------------------------


async def insert_clauses_bulk(
    session: AsyncSession,
    units: list["ClauseUnit"],
    company_id: str,
    ctx: "RunContext",
) -> dict[str, uuid.UUID]:
    """Insert all clauses. Returns {clause_id: clause_pk}."""
    clause_pk_map: dict[str, uuid.UUID] = {}

    for unit in units:
        clause_pk = stable_uuid(company_id, unit.version_id, unit.clause_id)
        clause_pk_map[unit.clause_id] = clause_pk

        await session.execute(
            text("""
                INSERT INTO company.clauses
                    (clause_pk, company_id, version_id, doc_id, clause_id, local_id,
                     parent_clause_id, ordinal, unit_kind, heading_path, section_kind,
                     sheet_no, table_id, row_cells, text_raw, text_norm, text_sha256,
                     char_start, char_end, line_start,
                     clause_role, role_method, assessable, normalized_statement, topic_terms)
                VALUES
                    (:clause_pk, :company_id, :version_id, :doc_id, :clause_id, :local_id,
                     :parent_clause_id, :ordinal, :unit_kind, :heading_path, :section_kind,
                     :sheet_no, :table_id, CAST(:row_cells AS jsonb), :text_raw, :text_norm, :text_sha256,
                     :char_start, :char_end, :line_start,
                     :clause_role, :role_method, :assessable, :normalized_statement, :topic_terms)
                ON CONFLICT (version_id, clause_id) DO UPDATE SET
                    clause_role           = EXCLUDED.clause_role,
                    role_method           = EXCLUDED.role_method,
                    assessable            = EXCLUDED.assessable,
                    normalized_statement  = EXCLUDED.normalized_statement,
                    topic_terms           = EXCLUDED.topic_terms
            """),
            {
                "clause_pk": str(clause_pk),
                "company_id": company_id,
                "version_id": unit.version_id,
                "doc_id": unit.doc_id,
                "clause_id": unit.clause_id,
                "local_id": unit.local_id,
                "parent_clause_id": unit.parent_clause_id,
                "ordinal": unit.ordinal,
                "unit_kind": unit.unit_kind,
                "heading_path": unit.heading_path,
                "section_kind": unit.section_kind,
                "sheet_no": unit.sheet_no,
                "table_id": unit.table_id,
                "row_cells": json.dumps(unit.row_cells) if unit.row_cells else None,
                "text_raw": unit.text_raw,
                "text_norm": unit.text_norm,
                "text_sha256": unit.text_sha256,
                "char_start": unit.char_start,
                "char_end": unit.char_end,
                "line_start": unit.line_start,
                "clause_role": unit.role,
                "role_method": unit.role_method,
                "assessable": unit.assessable,
                "normalized_statement": unit.normalized_statement,
                "topic_terms": unit.topic_terms,
            },
        )

    ctx.count("clauses_inserted", len(units))
    return clause_pk_map


# ---------------------------------------------------------------------------
# clause_citations
# ---------------------------------------------------------------------------


async def insert_clause_citations(
    session: AsyncSession,
    units: list["ClauseUnit"],
    clause_pk_map: dict[str, uuid.UUID],
    company_id: str,
    ctx: "RunContext",
) -> dict[tuple[str, int], uuid.UUID]:
    """Insert citations. Returns {(clause_id, index): citation_pk}."""
    citation_pk_map: dict[tuple[str, int], uuid.UUID] = {}
    count = 0

    for unit in units:
        clause_pk = clause_pk_map.get(unit.clause_id)
        if clause_pk is None:
            continue
        for i, c in enumerate(unit.citations):
            parsed = c.parsed
            # Version-scoped: without unit.version_id a second version's
            # citations collide with the first's and ON CONFLICT DO NOTHING
            # discards them silently (TDD 1.3).
            citation_pk = stable_uuid(
                company_id, unit.version_id, unit.clause_id, str(i), parsed.citation_raw
            )
            citation_pk_map[(unit.clause_id, i)] = citation_pk
            await session.execute(
                text("""
                    INSERT INTO company.clause_citations
                        (citation_pk, clause_pk, citation_raw, span_start, span_end,
                         source_system, title, article, rule, section, subsection_path,
                         granularity, in_knowledge_base, code_section_id,
                         resolution_status, context)
                    VALUES
                        (:citation_pk, :clause_pk, :citation_raw, :span_start, :span_end,
                         :source_system, :title, :article, :rule, :section, :subsection_path,
                         :granularity, :in_knowledge_base, :code_section_id,
                         :resolution_status, :context)
                    ON CONFLICT (citation_pk) DO NOTHING
                """),
                {
                    "citation_pk": str(citation_pk),
                    "clause_pk": str(clause_pk),
                    "citation_raw": parsed.citation_raw,
                    "span_start": c.span_start,
                    "span_end": c.span_end,
                    "source_system": parsed.source_system,
                    "title": parsed.title,
                    "article": parsed.article,
                    "rule": parsed.rule,
                    "section": float(parsed.section) if parsed.section is not None else None,
                    "subsection_path": parsed.subsection_path,
                    "granularity": parsed.granularity,
                    "in_knowledge_base": c.in_knowledge_base,
                    "code_section_id": c.code_section_id,
                    "resolution_status": c.resolution_status,
                    "context": c.context,
                },
            )
            count += 1

    ctx.count("citations_inserted", count)
    return citation_pk_map


# ---------------------------------------------------------------------------
# clause_parameters
# ---------------------------------------------------------------------------


async def insert_clause_parameters(
    session: AsyncSession,
    units: list["ClauseUnit"],
    clause_pk_map: dict[str, uuid.UUID],
    company_id: str,
    ctx: "RunContext",
) -> dict[str, uuid.UUID]:
    """Insert parameters. Returns {clause_id:index str → parameter_pk}."""
    parameter_pk_map: dict[str, uuid.UUID] = {}
    count = 0

    for unit in units:
        clause_pk = clause_pk_map.get(unit.clause_id)
        if clause_pk is None:
            continue
        for i, p in enumerate(unit.parameters):
            # Version-scoped (TDD 1.3).
            parameter_pk = stable_uuid(
                company_id, unit.version_id, unit.clause_id, str(i), p.value_text
            )
            pk_key = f"{unit.clause_id}:{i}"
            parameter_pk_map[pk_key] = parameter_pk
            await session.execute(
                text("""
                    INSERT INTO company.clause_parameters
                        (parameter_pk, clause_pk, kind, name, value_text,
                         span_start, span_end, value_num, unit, qualifier, day_type,
                         supported_by_citation_pk, value_source, method, verified)
                    VALUES
                        (:parameter_pk, :clause_pk, :kind, :name, :value_text,
                         :span_start, :span_end, :value_num, :unit, :qualifier, :day_type,
                         :supported_by_citation_pk, :value_source, :method, :verified)
                    ON CONFLICT (parameter_pk) DO UPDATE SET
                        value_source = EXCLUDED.value_source,
                        verified     = EXCLUDED.verified
                """),
                {
                    "parameter_pk": str(parameter_pk),
                    "clause_pk": str(clause_pk),
                    "kind": p.kind,
                    "name": getattr(p, "name", None),
                    "value_text": p.value_text,
                    "span_start": p.span_start,
                    "span_end": p.span_end,
                    "value_num": p.value_num,
                    "unit": p.unit,
                    "qualifier": p.qualifier,
                    "day_type": p.day_type,
                    "supported_by_citation_pk": None,
                    "value_source": getattr(p, "value_source", None),
                    "method": p.method,
                    "verified": p.verified,
                },
            )
            count += 1

    ctx.count("parameters_inserted", count)
    return parameter_pk_map


# ---------------------------------------------------------------------------
# defined_terms + term_usages
# ---------------------------------------------------------------------------


async def insert_defined_terms(
    session: AsyncSession,
    terms: list["TermEntry"],
    clause_pk_map: dict[str, uuid.UUID],
    clause_version_map: dict[str, str],
    company_id: str,
    ctx: "RunContext",
) -> dict[str, uuid.UUID]:
    """Insert terms. Returns {definition_clause_id: term_pk}.

    ``term_pk`` is version-scoped (TDD 1.3) and ``version_id`` is now actually
    written to the row — it used to be hardcoded to ``None``.  The version comes
    from the defining clause via ``clause_version_map``; a term whose defining
    clause is not in this write is skipped rather than keyed without a version,
    because an unversioned key is exactly the bug being fixed.
    """
    term_pk_map: dict[str, uuid.UUID] = {}
    count = 0

    for entry in terms:
        version_id = clause_version_map.get(entry.definition_clause_id)
        if version_id is None:
            ctx.issue(
                "warning",
                "store.neon",
                "term_version_unknown",
                "skipping defined term with no version for its defining clause",
                doc_id=entry.doc_id,
                clause_id=entry.definition_clause_id,
            )
            continue
        term_pk = _term_pk(company_id, version_id, entry.term_norm)
        term_pk_map[entry.definition_clause_id] = term_pk
        def_clause_pk = clause_pk_map.get(entry.definition_clause_id)
        count += 1
        await session.execute(
            text("""
                INSERT INTO company.defined_terms
                    (term_pk, company_id, doc_id, version_id, term, term_norm,
                     definition_clause_pk, cites_regulatory_definition, citation_pk)
                VALUES
                    (:term_pk, :company_id, :doc_id, :version_id, :term, :term_norm,
                     :definition_clause_pk, :cites_regulatory_definition, :citation_pk)
                ON CONFLICT (term_pk) DO UPDATE SET
                    term                        = EXCLUDED.term,
                    cites_regulatory_definition = EXCLUDED.cites_regulatory_definition
            """),
            {
                "term_pk": str(term_pk),
                "company_id": company_id,
                "doc_id": entry.doc_id,
                "version_id": version_id,
                "term": entry.term,
                "term_norm": entry.term_norm,
                "definition_clause_pk": str(def_clause_pk) if def_clause_pk else None,
                "cites_regulatory_definition": entry.cites_regulatory_definition,
                "citation_pk": None,
            },
        )

    ctx.count("terms_inserted", count)
    return term_pk_map


async def insert_term_usages_with_map(
    session: AsyncSession,
    terms: list["TermEntry"],
    term_usages: list["TermUsage"],
    clause_pk_map: dict[str, uuid.UUID],
    clause_version_map: dict[str, str],
    company_id: str,
    ctx: "RunContext",
) -> None:
    """Insert term usages, resolving term_pk from the term list.

    Must derive ``term_pk`` identically to ``insert_defined_terms`` — hence the
    shared ``_term_pk`` helper.  A mismatch here produces term_usages rows that
    reference a term row that was never written.
    """
    # Build term_norm → term_pk mapping, version-scoped via the defining clause.
    term_norm_pk: dict[str, uuid.UUID] = {}
    for e in terms:
        version_id = clause_version_map.get(e.definition_clause_id)
        if version_id is None:
            continue
        term_norm_pk[e.term_norm] = _term_pk(company_id, version_id, e.term_norm)

    count = 0
    for usage in term_usages:
        term_pk = term_norm_pk.get(usage.term_norm)
        clause_pk = clause_pk_map.get(usage.clause_id)
        if term_pk is None or clause_pk is None:
            continue
        await session.execute(
            text("""
                INSERT INTO company.term_usages (term_pk, clause_pk, occurrences)
                VALUES (:term_pk, :clause_pk, :occurrences)
                ON CONFLICT (term_pk, clause_pk) DO UPDATE SET occurrences = EXCLUDED.occurrences
            """),
            {
                "term_pk": str(term_pk),
                "clause_pk": str(clause_pk),
                "occurrences": usage.occurrences,
            },
        )
        count += 1
    ctx.count("term_usages_inserted", count)


# ---------------------------------------------------------------------------
# clause_links
# ---------------------------------------------------------------------------


async def insert_clause_links(
    session: AsyncSession,
    links: list["ClauseLink"],
    clause_pk_map: dict[str, uuid.UUID],
    clause_version_map: dict[str, str],
    company_id: str,
    ctx: "RunContext",
) -> None:
    """Insert clause links.

    ``link_pk`` is version-scoped (TDD 1.3) using the version of the *source*
    clause.  A link whose source clause is not in this write is skipped — an
    unversioned key would be silently dropped by ON CONFLICT DO NOTHING on the
    next version.
    """
    count = 0
    skipped = 0
    for link in links:
        version_id = clause_version_map.get(link.from_clause_id)
        if version_id is None:
            skipped += 1
            continue
        from_pk = clause_pk_map.get(link.from_clause_id)
        to_pk = clause_pk_map.get(link.to_clause_id) if link.to_clause_id else None
        link_pk = stable_uuid(
            company_id,
            version_id,
            link.from_clause_id,
            link.to_clause_id or link.to_doc_id or "",
            link.link_type,
        )
        await session.execute(
            text("""
                INSERT INTO company.clause_links
                    (link_pk, company_id, from_clause_pk, to_clause_pk, to_doc_id,
                     link_type, method, evidence, confidence)
                VALUES
                    (:link_pk, :company_id, :from_clause_pk, :to_clause_pk, :to_doc_id,
                     :link_type, :method, :evidence, :confidence)
                ON CONFLICT (link_pk) DO NOTHING
            """),
            {
                "link_pk": str(link_pk),
                "company_id": company_id,
                "from_clause_pk": str(from_pk) if from_pk else None,
                "to_clause_pk": str(to_pk) if to_pk else None,
                "to_doc_id": link.to_doc_id,
                "link_type": link.link_type,
                "method": link.method,
                "evidence": link.evidence,
                "confidence": link.confidence,
            },
        )
        count += 1
    if skipped:
        ctx.issue(
            "warning",
            "store.neon",
            "link_version_unknown",
            f"skipped {skipped} clause link(s) whose source clause is not in this write",
        )
    ctx.count("links_inserted", count)


# ---------------------------------------------------------------------------
# document_scope
# ---------------------------------------------------------------------------


async def insert_document_scope(
    session: AsyncSession,
    scope_rows: list["DocumentScopeRow"],
    company_id: str,
    ctx: "RunContext",
) -> None:
    """Insert document scope rows."""
    for row in scope_rows:
        await session.execute(
            text("""
                INSERT INTO company.document_scope
                    (company_id, doc_id, version_id, scope_level, scope_key,
                     code_section_id, sources, clause_count)
                VALUES
                    (:company_id, :doc_id, :version_id, :scope_level, :scope_key,
                     :code_section_id, :sources, :clause_count)
                ON CONFLICT (version_id, scope_level, scope_key) DO UPDATE SET
                    sources      = EXCLUDED.sources,
                    clause_count = EXCLUDED.clause_count
            """),
            {
                "company_id": company_id,
                "doc_id": row.doc_id,
                "version_id": row.version_id,
                "scope_level": row.scope_level,
                "scope_key": row.scope_key,
                "code_section_id": row.scope_key if row.scope_level == "rule" else None,
                "sources": row.sources,
                "clause_count": row.clause_count,
            },
        )
    ctx.count("scope_rows_inserted", len(scope_rows))


# ---------------------------------------------------------------------------
# table_columns
# ---------------------------------------------------------------------------


async def insert_table_columns(
    session: AsyncSession,
    col_roles_map: dict[str, dict[str, str | None]],
    company_id: str,
    ctx: "RunContext",
) -> None:
    """Insert column role assignments for P2 register tables."""
    count = 0
    for doc_id, col_roles in col_roles_map.items():
        for col_name, role in col_roles.items():
            if role is None:
                continue
            await session.execute(
                text("""
                    INSERT INTO company.table_columns
                        (company_id, doc_id, table_name, column_name, column_role, role_method)
                    VALUES
                        (:company_id, :doc_id, :table_name, :column_name, :column_role, :role_method)
                    ON CONFLICT (company_id, doc_id, table_name, column_name) DO UPDATE SET
                        column_role = EXCLUDED.column_role
                """),
                {
                    "company_id": company_id,
                    "doc_id": doc_id,
                    "table_name": doc_id,
                    "column_name": col_name,
                    "column_role": role,
                    "role_method": "llm" if not None else "heuristic",
                },
            )
            count += 1
    ctx.count("table_columns_inserted", count)


# ---------------------------------------------------------------------------
# High-level commit orchestrator
# ---------------------------------------------------------------------------


async def commit_run(
    session: AsyncSession,
    ctx: "RunContext",
    sources: list[Any],
    register_entries: list[Any],
    units: list["ClauseUnit"],
    links: list["ClauseLink"],
    scope_rows: list["DocumentScopeRow"],
    terms: list["TermEntry"],
    term_usages: list["TermUsage"],
    col_roles_map: dict[str, dict[str, str | None]],
    report_r2_key: str | None,  # deprecated, ignored — see finish_ingest_run
    version_specs: dict[str, DocumentVersionSpec] | None = None,
    dataset_profiles: Any = None,  # deprecated, ignored — tables dropped in 3.1
    proposals: Any = None,         # deprecated, ignored — tables dropped in 3.1
) -> None:
    """Run all Neon writes in the current session (caller commits).

    Contract: **one version per document per call.**  The clause/citation/
    parameter maps are keyed by bare ``clause_id`` (``DOC:LOCAL``, identical
    across versions), so mixing two versions of one document into a single call
    would attach one version's children to the other's clause_pk.
    ``build_clause_version_map`` raises if that happens.

    ``version_specs`` maps doc_id → :class:`DocumentVersionSpec` and is
    required; there is no ``version_no=1`` default, because guessing a version
    number is how a second version ends up overwriting the first.
    """
    if not version_specs:
        raise ValueError(
            "commit_run requires version_specs={doc_id: DocumentVersionSpec}; "
            "version_id/version_no/source_r2_key are owned by the caller"
        )
    company_id = ctx.company_id
    clause_version_map = build_clause_version_map(units)

    logger.info("Neon: inserting company documents and versions")
    await insert_company_documents(session, sources, register_entries, company_id, ctx)
    await insert_document_versions(session, version_specs, company_id, ctx)

    logger.info("Neon: inserting clauses (%d units)", len(units))
    clause_pk_map = await insert_clauses_bulk(session, units, company_id, ctx)

    logger.info("Neon: inserting citations and parameters")
    await insert_clause_citations(session, units, clause_pk_map, company_id, ctx)
    await insert_clause_parameters(session, units, clause_pk_map, company_id, ctx)

    logger.info("Neon: inserting terms and usages")
    await insert_defined_terms(
        session, terms, clause_pk_map, clause_version_map, company_id, ctx
    )
    await insert_term_usages_with_map(
        session, terms, term_usages, clause_pk_map, clause_version_map, company_id, ctx
    )

    logger.info("Neon: inserting links and scope")
    await insert_clause_links(
        session, links, clause_pk_map, clause_version_map, company_id, ctx
    )
    await insert_document_scope(session, scope_rows, company_id, ctx)

    logger.info("Neon: inserting table columns")
    await insert_table_columns(session, col_roles_map, company_id, ctx)

    # company.ingest_runs is deliberately NOT written here (task 5.8).  The old
    # in-transaction upsert stamped 'completed' before the caller committed
    # (and before stage 6 could still raise), wrote report_r2_key=NULL, and
    # held a row lock that would block finish_ingest_run's own session.  The
    # run row is owned by store/commit.py:start_ingest_run/finish_ingest_run.
    # ``report_r2_key`` is accepted and ignored for signature compatibility.
