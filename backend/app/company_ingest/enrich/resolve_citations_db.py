"""
resolve_citations_db.py

Resolves company.clause_citations rows to public.code_sections rows.

Resolution logic:
- IAC  → match by normalized citation key; rule-level if no section
- CFR  → parse citation_raw; match by title/part/section_number
- IC   → not_monitored (not in scope)
- USC  → not_monitored (not in scope)
- external_standard → external (no KB lookup; set so no row is left NULL)
- unknown → unparsed

Idempotent: re-running skips rows already resolved to anything other than
'not_found' or the placeholder values set by prior partial runs.  We
re-process every row that is NOT already marked as one of the terminal
statuses: resolved, resolved_rule, not_in_kb, not_monitored, external,
out_of_scope_title, unparsed.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional


# --------------------------------------------------------------------------- #
# Status helpers
# --------------------------------------------------------------------------- #

# Statuses we consider "done" — safe to skip on a re-run.
_TERMINAL = frozenset(
    {
        "resolved",
        "resolved_rule",
        "not_in_kb",
        "not_monitored",
        "external",
        "out_of_scope_title",
        "unparsed",
    }
)

_IN_KB_FOR_STATUS = {
    "resolved": True,
    "resolved_rule": True,
    "not_in_kb": True,
    "out_of_scope_title": False,
    "not_monitored": False,
    "external": False,
    "unparsed": False,
}


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #

def _parse_cfr_citation_raw(citation_raw: str):
    """
    Parse a raw CFR citation string into (title_str, part_str, section_str).

    Examples
    --------
    "40 CFR 761.180" -> ("40", "761", "180")
    "18 CFR 35"      -> ("18", "35", None)   # whole-part ref
    "29 CFR 1910.269"-> ("29", "1910", "269")
    """
    # Strip parenthetical suffixes like "(subpart F)"
    clean = re.sub(r"\s*\(.*\)$", "", citation_raw.strip())
    parts = clean.split()
    if len(parts) < 3:
        return None, None, None

    title_str = parts[0]
    # The section reference is the last token; it may be "761.180" or "280"
    ref = parts[-1]

    if "." in ref:
        part_str, section_str = ref.split(".", 1)
    else:
        part_str = ref
        section_str = None

    return title_str, part_str, section_str


def _iac_normalized_key(title: int, article: str, section) -> Optional[str]:
    """Build the IAC citation key used in public.code_sections.

    E.g. title=170, article="4-1", section=17 -> "170 IAC 4-1-17"
    Returns None if section is None/NULL.
    """
    if section is None:
        return None
    # section is Decimal from psycopg2 — convert to int to avoid ".0" suffix
    try:
        sec_str = str(int(section))
    except (TypeError, ValueError):
        sec_str = str(section)
    return f"{title} IAC {article}-{sec_str}"


# --------------------------------------------------------------------------- #
# Main resolver
# --------------------------------------------------------------------------- #

def resolve_all_citations(conn, dry_run: bool = False) -> dict:
    """
    Resolve all unresolved rows in company.clause_citations.

    Parameters
    ----------
    conn : psycopg2 connection (autocommit=False is recommended for callers)
    dry_run : compute and return the counts but write nothing

    Returns
    -------
    dict  counts per resolution_status for rows touched this run
    """
    cur = conn.cursor()

    # ------------------------------------------------------------------ #
    # 1. Pre-load the set of ingested titles from code_sections           #
    # ------------------------------------------------------------------ #
    cur.execute(
        "SELECT DISTINCT source_system, title_number FROM public.code_sections"
    )
    ingested: dict[str, set] = defaultdict(set)
    for ss, tn in cur.fetchall():
        ingested[ss].add(str(tn))

    iac_titles = ingested["iac"]
    cfr_titles = ingested["cfr"]

    # ------------------------------------------------------------------ #
    # 2. Determine the fallback law_as_of for orphaned clauses            #
    #    (clauses whose version_id has no row in document_versions).      #
    #    All existing doc versions have law_as_of = 2024-12-31 (S1), so  #
    #    we default to that date for orphans.                             #
    # ------------------------------------------------------------------ #
    cur.execute(
        "SELECT MIN(law_as_of) FROM company.document_versions"
    )
    fallback_law_as_of: date = cur.fetchone()[0] or date(2024, 12, 31)

    # ------------------------------------------------------------------ #
    # 3. Fetch rows to process (skip already-terminal, skip external_std) #
    # ------------------------------------------------------------------ #
    cur.execute(
        """
        SELECT
            cc.citation_pk,
            cc.source_system,
            cc.title,
            cc.article,
            cc.rule,
            cc.section,          -- numeric
            cc.granularity,
            cc.citation_raw,
            cc.resolution_status,
            COALESCE(dv.law_as_of, %s) AS law_as_of
        FROM company.clause_citations cc
        LEFT JOIN company.clauses cl ON cl.clause_pk = cc.clause_pk
        LEFT JOIN company.document_versions dv ON dv.version_id = cl.version_id
        WHERE (
            cc.resolution_status IS NULL
            OR cc.resolution_status NOT IN %s
          )
          AND NOT (cc.source_system = 'external_standard'
                   AND cc.resolution_status IS NOT DISTINCT FROM 'external')
        """,
        (fallback_law_as_of, tuple(_TERMINAL - frozenset({"external"})))
    )
    rows = cur.fetchall()

    counts: dict[str, int] = defaultdict(int)
    updates = []  # list of (status, in_kb, code_section_id, citation_pk)

    for row in rows:
        (
            citation_pk,
            source_system,
            title,
            article,
            rule,
            section,
            granularity,
            citation_raw,
            _current_status,
            law_as_of,
        ) = row

        status: str
        code_section_id: Optional[str] = None

        # ------------------------------------------------------------------ #
        # IC / USC → not_monitored                                            #
        # ------------------------------------------------------------------ #
        if source_system in ("ic", "usc"):
            status = "not_monitored"

        # ------------------------------------------------------------------ #
        # external_standard → external (no KB lookup)                         #
        # ------------------------------------------------------------------ #
        elif source_system == "external_standard":
            status = "external"

        # ------------------------------------------------------------------ #
        # unknown → unparsed                                                  #
        # ------------------------------------------------------------------ #
        elif source_system == "unknown":
            status = "unparsed"

        # ------------------------------------------------------------------ #
        # IAC                                                                 #
        # ------------------------------------------------------------------ #
        elif source_system == "iac":
            title_str = str(title) if title is not None else None

            if title_str not in iac_titles:
                status = "out_of_scope_title"
            elif granularity in ("section", "subsection"):
                key = _iac_normalized_key(title, article, section)
                if key is None:
                    # Fallback: try rule-level
                    status = "out_of_scope_title"
                else:
                    # CFR snapshot window: use law_as_of (IAC snapshot matches exactly)
                    cur.execute(
                        """
                        SELECT id FROM public.code_sections
                        WHERE source_system = 'iac'
                          AND citation = %s
                          AND snapshot_date <= %s
                        ORDER BY snapshot_date DESC
                        LIMIT 1
                        """,
                        (key, law_as_of),
                    )
                    hit = cur.fetchone()
                    if hit:
                        status = "resolved"
                        code_section_id = str(hit[0])
                    else:
                        status = "not_in_kb"
            elif granularity == "rule":
                # Check if any section exists for this title+article
                if article is None:
                    status = "not_in_kb"
                else:
                    prefix = f"{title} IAC {article}-%"
                    cur.execute(
                        """
                        SELECT EXISTS(
                            SELECT 1 FROM public.code_sections
                            WHERE source_system = 'iac'
                              AND citation LIKE %s
                              AND snapshot_date <= %s
                        )
                        """,
                        (prefix, law_as_of),
                    )
                    exists = cur.fetchone()[0]
                    status = "resolved_rule" if exists else "not_in_kb"
            else:
                # Unknown granularity for IAC
                status = "unparsed"

        # ------------------------------------------------------------------ #
        # CFR                                                                 #
        # ------------------------------------------------------------------ #
        elif source_system == "cfr":
            title_str, part_str, section_str = _parse_cfr_citation_raw(
                citation_raw or ""
            )

            if title_str is None:
                status = "unparsed"
            elif title_str not in cfr_titles:
                status = "out_of_scope_title"
            elif section_str is not None:
                # Section-level match.  CFR S1 snapshot is 2025-01-02 while
                # law_as_of is 2024-12-31, so we allow a 14-day window.
                cfr_window = law_as_of + timedelta(days=14)
                cur.execute(
                    """
                    SELECT id FROM public.code_sections
                    WHERE source_system = 'cfr'
                      AND title_number = %s
                      AND part = %s
                      AND section_number = %s
                      AND snapshot_date <= %s
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                    """,
                    (title_str, part_str, section_str, cfr_window),
                )
                hit = cur.fetchone()
                if hit:
                    status = "resolved"
                    code_section_id = str(hit[0])
                else:
                    status = "not_in_kb"
            else:
                # Whole-part reference (no decimal in section ref)
                cfr_window = law_as_of + timedelta(days=14)
                cur.execute(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM public.code_sections
                        WHERE source_system = 'cfr'
                          AND title_number = %s
                          AND part = %s
                          AND snapshot_date <= %s
                    )
                    """,
                    (title_str, part_str, cfr_window),
                )
                exists = cur.fetchone()[0]
                status = "resolved_rule" if exists else "not_in_kb"

        else:
            # Any other source_system not explicitly handled
            status = "unparsed"

        in_kb = _IN_KB_FOR_STATUS.get(status, False)
        counts[status] += 1
        updates.append((status, in_kb, code_section_id, str(citation_pk)))

    # ------------------------------------------------------------------ #
    # 3. Batch-update                                                      #
    # ------------------------------------------------------------------ #
    if updates and not dry_run:
        cur.executemany(
            """
            UPDATE company.clause_citations
            SET resolution_status = %s,
                in_knowledge_base = %s,
                code_section_id   = %s
            WHERE citation_pk = %s::uuid
            """,
            updates,
        )
        conn.commit()

    cur.close()
    return dict(counts)
