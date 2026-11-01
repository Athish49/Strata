"""
resolve_citations.py

Async, per-version port of ``resolve_citations_db.resolve_all_citations``.

Resolves ``company.clause_citations`` rows belonging to a single
``document_versions.version_id`` against ``public.code_sections``, using the
caller's :class:`~sqlalchemy.ext.asyncio.AsyncSession`.  **It never commits** —
the caller owns the transaction (the ingest pipeline resolves citations inside
the same transaction that writes them).

Resolution logic is a straight port of the psycopg2 implementation and must
stay byte-for-byte equivalent in behaviour (TDD.md section 5):

- IAC  -> match by normalized citation key; rule-level if no section
- CFR  -> parse ``citation_raw``; match by title/part/section_number inside a
          14-day snapshot window (the CFR S1 snapshot is a couple of days
          after ``DEFAULT_LAW_AS_OF``, the fallback ``law_as_of``)
- IC / USC          -> ``not_monitored`` (not in scope)
- ``external_standard`` -> ``external`` (no KB lookup)
- ``unknown``       -> ``unparsed``

Idempotent: rows already sitting on one of the ``_TERMINAL`` statuses are not
re-processed, so a second call for the same version is a no-op.

The status constants and parsing helpers are imported from
``resolve_citations_db`` so there is exactly one definition of each.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.company_ingest.enrich.resolve_citations_db import (  # single source of truth
    DEFAULT_LAW_AS_OF,
    _IN_KB_FOR_STATUS,
    _TERMINAL,
    _iac_normalized_key,
    _parse_cfr_citation_raw,
)

__all__ = ["resolve_citations_for_version"]


# --------------------------------------------------------------------------- #
# Statements
# --------------------------------------------------------------------------- #

_INGESTED_TITLES_SQL = text(
    "SELECT DISTINCT source_system, title_number FROM public.code_sections"
)

_FALLBACK_LAW_AS_OF_SQL = text(
    "SELECT MIN(law_as_of) FROM company.document_versions"
)

# Rows to process for one version: skip already-terminal statuses, and skip
# external_standard rows that are already marked 'external'.  Note that
# 'external' is deliberately removed from the terminal set here (exactly as in
# the psycopg2 original) so that a *non*-external_standard row that somehow
# carries 'external' is still re-processed.
_ROWS_SQL = text(
    """
    SELECT
        cc.citation_pk,
        cc.source_system,
        cc.title,
        cc.article,
        cc.rule,
        cc.section,
        cc.granularity,
        cc.citation_raw,
        cc.resolution_status,
        COALESCE(dv.law_as_of, CAST(:fallback_law_as_of AS date)) AS law_as_of
    FROM company.clause_citations cc
    JOIN company.clauses cl ON cl.clause_pk = cc.clause_pk
    LEFT JOIN company.document_versions dv ON dv.version_id = cl.version_id
    WHERE cl.version_id = CAST(:version_id AS uuid)
      AND cl.company_id = :company_id
      AND (
        cc.resolution_status IS NULL
        OR cc.resolution_status NOT IN :terminal
      )
      AND NOT (cc.source_system = 'external_standard'
               AND cc.resolution_status IS NOT DISTINCT FROM 'external')
    """
).bindparams(bindparam("terminal", expanding=True))

_IAC_SECTION_SQL = text(
    """
    SELECT id FROM public.code_sections
    WHERE source_system = 'iac'
      AND citation = :key
      AND snapshot_date <= CAST(:law_as_of AS date)
    ORDER BY snapshot_date DESC
    LIMIT 1
    """
)

_IAC_RULE_EXISTS_SQL = text(
    """
    SELECT EXISTS(
        SELECT 1 FROM public.code_sections
        WHERE source_system = 'iac'
          AND citation LIKE :prefix
          AND snapshot_date <= CAST(:law_as_of AS date)
    )
    """
)

_CFR_SECTION_SQL = text(
    """
    SELECT id FROM public.code_sections
    WHERE source_system = 'cfr'
      AND title_number = :title
      AND part = :part
      AND section_number = :section
      AND snapshot_date <= CAST(:law_as_of AS date)
    ORDER BY snapshot_date DESC
    LIMIT 1
    """
)

_CFR_PART_EXISTS_SQL = text(
    """
    SELECT EXISTS(
        SELECT 1 FROM public.code_sections
        WHERE source_system = 'cfr'
          AND title_number = :title
          AND part = :part
          AND snapshot_date <= CAST(:law_as_of AS date)
    )
    """
)

_UPDATE_SQL = text(
    """
    UPDATE company.clause_citations
    SET resolution_status = :status,
        in_knowledge_base = :in_kb,
        code_section_id   = :code_section_id
    WHERE citation_pk = CAST(:citation_pk AS uuid)
    """
)


# --------------------------------------------------------------------------- #
# Per-row classification (the ported if/elif tree)
# --------------------------------------------------------------------------- #

async def _classify_row(
    session: AsyncSession,
    row: Any,
    iac_titles: set[str],
    cfr_titles: set[str],
) -> tuple[str, Optional[str]]:
    """Decide ``(resolution_status, code_section_id)`` for a single citation row.

    ``row`` is a mapping with the columns selected by ``_ROWS_SQL``.
    """
    source_system = row["source_system"]
    title = row["title"]
    article = row["article"]
    section = row["section"]
    granularity = row["granularity"]
    citation_raw = row["citation_raw"]
    law_as_of = row["law_as_of"]

    code_section_id: Optional[str] = None

    # ------------------------------------------------------------------ #
    # IC / USC -> not_monitored                                          #
    # ------------------------------------------------------------------ #
    if source_system in ("ic", "usc"):
        status = "not_monitored"

    # ------------------------------------------------------------------ #
    # external_standard -> external (no KB lookup)                       #
    # ------------------------------------------------------------------ #
    elif source_system == "external_standard":
        status = "external"

    # ------------------------------------------------------------------ #
    # unknown -> unparsed                                                #
    # ------------------------------------------------------------------ #
    elif source_system == "unknown":
        status = "unparsed"

    # ------------------------------------------------------------------ #
    # IAC                                                                #
    # ------------------------------------------------------------------ #
    elif source_system == "iac":
        title_str = str(title) if title is not None else None

        if title_str not in iac_titles:
            status = "out_of_scope_title"
        elif granularity in ("section", "subsection"):
            key = _iac_normalized_key(title, article, section)
            if key is None:
                status = "out_of_scope_title"
            else:
                # IAC snapshot matches law_as_of exactly: no window.
                hit = (
                    await session.execute(
                        _IAC_SECTION_SQL, {"key": key, "law_as_of": law_as_of}
                    )
                ).first()
                if hit:
                    status = "resolved"
                    code_section_id = str(hit[0])
                else:
                    status = "not_in_kb"
        elif granularity == "rule":
            if article is None:
                status = "not_in_kb"
            else:
                prefix = f"{title} IAC {article}-%"
                exists = (
                    await session.execute(
                        _IAC_RULE_EXISTS_SQL,
                        {"prefix": prefix, "law_as_of": law_as_of},
                    )
                ).scalar()
                status = "resolved_rule" if exists else "not_in_kb"
        else:
            # Unknown granularity for IAC
            status = "unparsed"

    # ------------------------------------------------------------------ #
    # CFR                                                                #
    # ------------------------------------------------------------------ #
    elif source_system == "cfr":
        title_str, part_str, section_str = _parse_cfr_citation_raw(citation_raw or "")

        if title_str is None:
            status = "unparsed"
        elif title_str not in cfr_titles:
            status = "out_of_scope_title"
        elif section_str is not None:
            # CFR S1 snapshot is a couple of days after DEFAULT_LAW_AS_OF,
            # so a 14-day window is allowed.  Do not "clean this up".
            cfr_window = law_as_of + timedelta(days=14)
            hit = (
                await session.execute(
                    _CFR_SECTION_SQL,
                    {
                        "title": title_str,
                        "part": part_str,
                        "section": section_str,
                        "law_as_of": cfr_window,
                    },
                )
            ).first()
            if hit:
                status = "resolved"
                code_section_id = str(hit[0])
            else:
                status = "not_in_kb"
        else:
            # Whole-part reference (no decimal in the section ref)
            cfr_window = law_as_of + timedelta(days=14)
            exists = (
                await session.execute(
                    _CFR_PART_EXISTS_SQL,
                    {
                        "title": title_str,
                        "part": part_str,
                        "law_as_of": cfr_window,
                    },
                )
            ).scalar()
            status = "resolved_rule" if exists else "not_in_kb"

    else:
        # Any other source_system not explicitly handled
        status = "unparsed"

    return status, code_section_id


# --------------------------------------------------------------------------- #
# Main resolver
# --------------------------------------------------------------------------- #

async def resolve_citations_for_version(
    session: AsyncSession,
    company_id: str,
    version_id: str,
) -> dict[str, int]:
    """Resolve ``company.clause_citations`` for one document version.

    Parameters
    ----------
    session
        Caller-owned :class:`AsyncSession`.  This function issues no COMMIT and
        no ROLLBACK; the caller owns the transaction boundary.
    company_id
        Tenant id; must match ``company.clauses.company_id``.
    version_id
        The single ``document_versions.version_id`` to scope to.  No rows
        outside this version are read or written.

    Returns
    -------
    dict[str, int]
        Counts per ``resolution_status`` for the rows touched this run.
    """
    # 1. In-scope titles from the knowledge base.
    ingested: dict[str, set[str]] = defaultdict(set)
    for ss, tn in (await session.execute(_INGESTED_TITLES_SQL)).all():
        ingested[ss].add(str(tn))

    iac_titles = ingested["iac"]
    cfr_titles = ingested["cfr"]

    # 2. Fallback law_as_of for clauses whose version row is missing.
    #    Deliberately the *global* MIN, not company-scoped.
    fallback_law_as_of: date = (
        await session.execute(_FALLBACK_LAW_AS_OF_SQL)
    ).scalar() or DEFAULT_LAW_AS_OF

    # 3. Rows to process, scoped to this version.
    rows = (
        await session.execute(
            _ROWS_SQL,
            {
                "fallback_law_as_of": fallback_law_as_of,
                "version_id": str(version_id),
                "company_id": company_id,
                "terminal": sorted(_TERMINAL - frozenset({"external"})),
            },
        )
    ).mappings().all()

    counts: dict[str, int] = defaultdict(int)
    updates: list[dict[str, Any]] = []

    for row in rows:
        status, code_section_id = await _classify_row(
            session, row, iac_titles, cfr_titles
        )
        counts[status] += 1
        updates.append(
            {
                "status": status,
                "in_kb": _IN_KB_FOR_STATUS.get(status, False),
                "code_section_id": code_section_id,
                "citation_pk": str(row["citation_pk"]),
            }
        )

    # 4. Batch-update.  No commit — the caller owns the transaction.
    if updates:
        await session.execute(_UPDATE_SQL, updates)

    return dict(counts)
