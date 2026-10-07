"""Bulk insert helpers for the company.* Neon schema.

All public functions accept an SQLAlchemy AsyncSession and return nothing
(or a mapping needed by downstream callers).  Call them inside a single
transaction managed by the CLI.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.company_ingest.ids import stable_uuid

if TYPE_CHECKING:
    from app.company_ingest.collect.collector import SourceFile
    from app.company_ingest.collect.reference import RegisterEntry
    from app.company_ingest.datasets.profile import DatasetProfile
    from app.company_ingest.datasets.propose_checks import CheckProposal
    from app.company_ingest.enrich.terms import TermEntry, TermUsage
    from app.company_ingest.link.document_scope import DocumentScopeRow
    from app.company_ingest.link.resolve_refs import ClauseLink
    from app.company_ingest.parse.models import ClauseUnit
    from app.company_ingest.run_context import RunContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ingest_runs
# ---------------------------------------------------------------------------


async def insert_ingest_run(
    session: AsyncSession,
    ctx: "RunContext",
    status: str,
    report_r2_key: str | None,
) -> None:
    """Upsert one row into company.ingest_runs."""
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


# ---------------------------------------------------------------------------
# company_documents + document_versions
# ---------------------------------------------------------------------------


async def insert_company_documents(
    session: AsyncSession,
    sources: list["SourceFile"],
    register_entries: list["RegisterEntry"],
    company_id: str,
    ctx: "RunContext",
) -> None:
    """Upsert one row per unique doc_id into company.company_documents."""
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
                     owner_id, reviewer_id, approver_id, review_cycle, current_version_id)
                VALUES
                    (:company_id, :doc_id, :title, :doc_class, :vertical,
                     :owner_id, :reviewer_id, :approver_id, :review_cycle, :current_version_id)
                ON CONFLICT (company_id, doc_id) DO UPDATE SET
                    title              = EXCLUDED.title,
                    doc_class          = EXCLUDED.doc_class,
                    owner_id           = EXCLUDED.owner_id,
                    reviewer_id        = EXCLUDED.reviewer_id,
                    approver_id        = EXCLUDED.approver_id,
                    current_version_id = EXCLUDED.current_version_id
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
                "current_version_id": str(stable_uuid(company_id, doc_id, (reg.version if reg else "v1"))),
            },
        )
    ctx.count("company_documents_upserted", len(seen))


async def insert_document_versions(
    session: AsyncSession,
    sources: list["SourceFile"],
    register_entries: list["RegisterEntry"],
    company_id: str,
    ctx: "RunContext",
) -> None:
    """Upsert one row per (company_id, doc_id) into company.document_versions."""
    reg_map: dict[str, Any] = {r.doc_id: r for r in register_entries}
    seen: set[str] = set()
    for sf in sources:
        doc_id = sf.doc_id
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        reg = reg_map.get(doc_id)
        version = reg.version if reg else "v1"
        version_id = str(stable_uuid(company_id, doc_id, version))

        def _date(s: str | None):
            if not s:
                return None
            try:
                from datetime import date
                return date.fromisoformat(s)
            except ValueError:
                return None

        reg_basis = []
        if reg and reg.regulatory_basis_sections:
            reg_basis = [s.strip() for s in reg.regulatory_basis_sections.split(";") if s.strip()]

        await session.execute(
            text("""
                INSERT INTO company.document_versions
                    (version_id, company_id, doc_id, version, status,
                     effective_date, approved_date, law_as_of, next_review, supersedes,
                     classification, regulatory_basis, source_r2_key, render_r2_keys,
                     file_sha256, ingest_status, ingested_at, ingest_run_id)
                VALUES
                    (:version_id, :company_id, :doc_id, :version, :status,
                     :effective_date, :approved_date, :law_as_of, :next_review, :supersedes,
                     :classification, :regulatory_basis, :source_r2_key, :render_r2_keys,
                     :file_sha256, :ingest_status, :ingested_at, :ingest_run_id)
                ON CONFLICT (version_id) DO UPDATE SET
                    ingest_status = EXCLUDED.ingest_status,
                    ingested_at   = EXCLUDED.ingested_at,
                    ingest_run_id = EXCLUDED.ingest_run_id
            """),
            {
                "version_id": version_id,
                "company_id": company_id,
                "doc_id": doc_id,
                "version": version,
                "status": reg.status if reg else "active",
                "effective_date": _date(reg.effective_date) if reg else None,
                "approved_date": _date(reg.approved_date) if reg else None,
                "law_as_of": _date(reg.law_as_of) if reg else None,
                "next_review": None,
                "supersedes": None,
                "classification": "internal",
                "regulatory_basis": reg_basis,
                "source_r2_key": getattr(sf, "r2_key", None),
                "render_r2_keys": [],
                "file_sha256": getattr(sf, "sha256", None),
                "ingest_status": "ingested",
                "ingested_at": datetime.now(timezone.utc),
                "ingest_run_id": str(ctx.run_id),
            },
        )
    ctx.count("document_versions_upserted", len(seen))


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
            citation_pk = stable_uuid(company_id, unit.clause_id, str(i), parsed.citation_raw)
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
            parameter_pk = stable_uuid(company_id, unit.clause_id, str(i), p.value_text)
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
    company_id: str,
    ctx: "RunContext",
) -> dict[str, uuid.UUID]:
    """Insert terms. Returns {definition_clause_id: term_pk}."""
    term_pk_map: dict[str, uuid.UUID] = {}

    for entry in terms:
        term_pk = stable_uuid(company_id, entry.doc_id, entry.term_norm)
        term_pk_map[entry.definition_clause_id] = term_pk
        def_clause_pk = clause_pk_map.get(entry.definition_clause_id)
        version_id = None
        # Derive version_id from clause_pk_map keys if possible — it's embedded in clause_pk
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

    ctx.count("terms_inserted", len(terms))
    return term_pk_map


async def insert_term_usages(
    session: AsyncSession,
    term_usages: list["TermUsage"],
    term_pk_map: dict[str, uuid.UUID],
    clause_pk_map: dict[str, uuid.UUID],
    ctx: "RunContext",
) -> None:
    """Insert term usages (term_pk, clause_pk) pairs."""
    count = 0
    for usage in term_usages:
        # term_pk_map keyed by definition_clause_id; find by term_norm
        term_pk = next(
            (pk for cid, pk in term_pk_map.items() if True),  # see below
            None,
        )
        # Rebuild lookup by term_norm using a separate map built at call time
        # The caller should pass term_norm_to_pk; but we can approximate here.
        clause_pk = clause_pk_map.get(usage.clause_id)
        if clause_pk is None:
            continue
        # term_pk is resolved by caller passing term_norm_to_pk; fall back gracefully
        if not hasattr(usage, "_term_pk"):
            continue
        await session.execute(
            text("""
                INSERT INTO company.term_usages (term_pk, clause_pk, occurrences)
                VALUES (:term_pk, :clause_pk, :occurrences)
                ON CONFLICT (term_pk, clause_pk) DO UPDATE SET occurrences = EXCLUDED.occurrences
            """),
            {
                "term_pk": str(usage._term_pk),
                "clause_pk": str(clause_pk),
                "occurrences": usage.occurrences,
            },
        )
        count += 1
    ctx.count("term_usages_inserted", count)


async def insert_term_usages_with_map(
    session: AsyncSession,
    terms: list["TermEntry"],
    term_usages: list["TermUsage"],
    clause_pk_map: dict[str, uuid.UUID],
    company_id: str,
    ctx: "RunContext",
) -> None:
    """Insert term usages, resolving term_pk from the term list."""
    # Build term_norm → term_pk mapping
    term_norm_pk: dict[str, uuid.UUID] = {
        e.term_norm: stable_uuid(company_id, e.doc_id, e.term_norm)
        for e in terms
    }

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
    company_id: str,
    ctx: "RunContext",
) -> None:
    """Insert clause links."""
    count = 0
    for link in links:
        from_pk = clause_pk_map.get(link.from_clause_id)
        to_pk = clause_pk_map.get(link.to_clause_id) if link.to_clause_id else None
        link_pk = stable_uuid(
            company_id,
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
# datasets + dataset_columns
# ---------------------------------------------------------------------------


async def insert_datasets(
    session: AsyncSession,
    dataset_profiles: list["DatasetProfile"],
    company_id: str,
    ctx: "RunContext",
) -> dict[str, uuid.UUID]:
    """Insert dataset profiles. Returns {name: dataset_pk}."""
    dataset_pk_map: dict[str, uuid.UUID] = {}

    for dp in dataset_profiles:
        dataset_pk = stable_uuid(company_id, dp.name, dp.file_sha256)
        dataset_pk_map[dp.name] = dataset_pk
        pk_list = [dp.primary_key] if dp.primary_key else []
        await session.execute(
            text("""
                INSERT INTO company.datasets
                    (dataset_pk, company_id, doc_id, name, r2_parquet_key, r2_source_key,
                     file_sha256, row_count, primary_key, description)
                VALUES
                    (:dataset_pk, :company_id, :doc_id, :name, :r2_parquet_key, :r2_source_key,
                     :file_sha256, :row_count, :primary_key, :description)
                ON CONFLICT (dataset_pk) DO UPDATE SET
                    row_count = EXCLUDED.row_count
            """),
            {
                "dataset_pk": str(dataset_pk),
                "company_id": company_id,
                "doc_id": dp.doc_id,
                "name": dp.name,
                "r2_parquet_key": dp.r2_parquet_key,
                "r2_source_key": dp.r2_source_key,
                "file_sha256": dp.file_sha256,
                "row_count": dp.row_count,
                "primary_key": pk_list,
                "description": None,
            },
        )

    ctx.count("datasets_inserted", len(dataset_profiles))
    return dataset_pk_map


async def insert_dataset_columns(
    session: AsyncSession,
    dataset_profiles: list["DatasetProfile"],
    dataset_pk_map: dict[str, uuid.UUID],
    ctx: "RunContext",
) -> None:
    """Insert column profiles for each dataset."""
    count = 0
    for dp in dataset_profiles:
        dataset_pk = dataset_pk_map.get(dp.name)
        if dataset_pk is None:
            continue
        for col in dp.columns:
            top_vals = json.dumps(col.top_values) if col.top_values else None
            await session.execute(
                text("""
                    INSERT INTO company.dataset_columns
                        (dataset_pk, column_name, dtype, null_rate, distinct_count,
                         min_value, max_value, top_values, semantic_role, fk_target, description)
                    VALUES
                        (:dataset_pk, :column_name, :dtype, :null_rate, :distinct_count,
                         :min_value, :max_value, CAST(:top_values AS jsonb), :semantic_role, :fk_target, :description)
                    ON CONFLICT (dataset_pk, column_name) DO UPDATE SET
                        semantic_role = EXCLUDED.semantic_role,
                        fk_target     = EXCLUDED.fk_target
                """),
                {
                    "dataset_pk": str(dataset_pk),
                    "column_name": col.column_name,
                    "dtype": col.dtype,
                    "null_rate": col.null_rate,
                    "distinct_count": col.distinct_count,
                    "min_value": col.min_value,
                    "max_value": col.max_value,
                    "top_values": top_vals,
                    "semantic_role": col.semantic_role,
                    "fk_target": col.fk_target,
                    "description": None,
                },
            )
            count += 1
    ctx.count("dataset_columns_inserted", count)


# ---------------------------------------------------------------------------
# parameter_checks
# ---------------------------------------------------------------------------


async def insert_parameter_checks(
    session: AsyncSession,
    proposals: list["CheckProposal"],
    parameter_pk_map: dict[str, uuid.UUID],
    dataset_pk_map: dict[str, uuid.UUID],
    company_id: str,
    ctx: "RunContext",
) -> None:
    """Insert validated (or proposed) parameter checks."""
    count = 0
    for prop in proposals:
        dataset_pk = dataset_pk_map.get(prop.dataset_name)
        check_pk = stable_uuid(company_id, prop.dataset_name, prop.purpose)
        # Resolve first parameter_pk from bindings
        first_param_pk_str = next(iter(prop.param_bindings.values()), None) if prop.param_bindings else None
        param_pk = parameter_pk_map.get(first_param_pk_str) if first_param_pk_str else None
        await session.execute(
            text("""
                INSERT INTO company.parameter_checks
                    (check_pk, company_id, parameter_pk, dataset_pk,
                     purpose, sql_template, param_bindings, s1_result, validated, method)
                VALUES
                    (:check_pk, :company_id, :parameter_pk, :dataset_pk,
                     :purpose, :sql_template, CAST(:param_bindings AS jsonb), CAST(:s1_result AS jsonb), :validated, :method)
                ON CONFLICT (check_pk) DO UPDATE SET
                    validated  = EXCLUDED.validated,
                    s1_result  = EXCLUDED.s1_result
            """),
            {
                "check_pk": str(check_pk),
                "company_id": company_id,
                "parameter_pk": str(param_pk) if param_pk else None,
                "dataset_pk": str(dataset_pk) if dataset_pk else None,
                "purpose": prop.purpose,
                "sql_template": prop.sql_template,
                "param_bindings": json.dumps(prop.param_bindings),
                "s1_result": json.dumps(prop.s1_result) if prop.s1_result else None,
                "validated": prop.validated,
                "method": prop.method,
            },
        )
        count += 1
    ctx.count("parameter_checks_inserted", count)


# ---------------------------------------------------------------------------
# High-level commit orchestrator
# ---------------------------------------------------------------------------


async def commit_run(
    session: AsyncSession,
    ctx: "RunContext",
    sources: list["SourceFile"],
    register_entries: list["RegisterEntry"],
    units: list["ClauseUnit"],
    links: list["ClauseLink"],
    scope_rows: list["DocumentScopeRow"],
    terms: list["TermEntry"],
    term_usages: list["TermUsage"],
    col_roles_map: dict[str, dict[str, str | None]],
    dataset_profiles: list["DatasetProfile"],
    proposals: list["CheckProposal"],
    report_r2_key: str | None,
) -> None:
    """Run all Neon writes in the current session (caller commits)."""
    company_id = ctx.company_id

    logger.info("Neon: inserting company documents and versions")
    await insert_company_documents(session, sources, register_entries, company_id, ctx)
    await insert_document_versions(session, sources, register_entries, company_id, ctx)

    logger.info("Neon: inserting clauses (%d units)", len(units))
    clause_pk_map = await insert_clauses_bulk(session, units, company_id, ctx)

    logger.info("Neon: inserting citations and parameters")
    citation_pk_map = await insert_clause_citations(session, units, clause_pk_map, company_id, ctx)
    parameter_pk_map = await insert_clause_parameters(session, units, clause_pk_map, company_id, ctx)

    logger.info("Neon: inserting terms and usages")
    term_pk_map = await insert_defined_terms(session, terms, clause_pk_map, company_id, ctx)
    await insert_term_usages_with_map(session, terms, term_usages, clause_pk_map, company_id, ctx)

    logger.info("Neon: inserting links and scope")
    await insert_clause_links(session, links, clause_pk_map, company_id, ctx)
    await insert_document_scope(session, scope_rows, company_id, ctx)

    logger.info("Neon: inserting table columns")
    await insert_table_columns(session, col_roles_map, company_id, ctx)

    logger.info("Neon: inserting datasets")
    dataset_pk_map = await insert_datasets(session, dataset_profiles, company_id, ctx)
    await insert_dataset_columns(session, dataset_profiles, dataset_pk_map, ctx)
    await insert_parameter_checks(session, proposals, parameter_pk_map, dataset_pk_map, company_id, ctx)

    logger.info("Neon: recording ingest run")
    await insert_ingest_run(session, ctx, "completed", report_r2_key)
