"""Task 4.1.1 — Citation extraction and resolution enrichment pass.

Public API
----------
    enrich_citations(
        units: list[ClauseUnit],
        ctx: RunContext,
        code_section_repo=None,
    ) -> None

Appends CitationEntry objects to unit.citations for every unit in *units*.
Never touches the database — persistence happens in task 8.1.2.

TODO: front-matter citations (from version.regulatory_basis) are added by the
8.1.2 commit stage, which has access to the version record. Skipped here.
"""
from __future__ import annotations

from typing import Callable

from app.company_ingest.enrich.citation_entry import CitationEntry
from app.company_ingest.enrich.citations_grammar import (
    ParsedCitation,
    find_citation_spans,
    parse_citation,
)
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _context_for_unit(unit: ClauseUnit) -> str:
    """Return the default citation context string for a given unit."""
    if unit.unit_kind == "register_row":
        return "register_column"
    if unit.section_kind == "regulatory_basis":
        return "regulatory_basis_table"
    return "inline"


def _resolve(
    parsed: ParsedCitation,
    ctx: RunContext,
    code_section_repo: Callable | None,
) -> tuple[str, str | None, bool]:
    """Resolve a single ParsedCitation against the optional repo.

    Returns (resolution_status, code_section_id, in_knowledge_base).
    """
    if parsed.source_system != "iac":
        return ("external", None, False)

    # IAC rule-level — no section to look up
    if parsed.granularity == "rule":
        return ("not_found", None, True)

    normalized_key = parsed.normalized_key
    cache_key = f"citation_lookup:{normalized_key}"

    if cache_key in ctx.llm_cache:
        cached = ctx.llm_cache[cache_key]
        return cached

    if code_section_repo is None:
        result = ("not_found", None, True)
    else:
        code_section = code_section_repo(normalized_key)
        if code_section is None:
            result = ("not_found", None, True)
        else:
            # Check if the section is repealed/expired
            status = getattr(code_section, "status", None)
            if status in ("repealed", "expired"):
                result = ("repealed_at_s1", None, True)
            else:
                pk = str(code_section.pk)
                result = ("resolved", pk, True)

    ctx.llm_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_citations(
    units: list[ClauseUnit],
    ctx: RunContext,
    code_section_repo: Callable | None = None,
) -> None:
    """Enrich *units* in-place by appending CitationEntry objects to unit.citations.

    Parameters
    ----------
    units:
        ClauseUnit instances produced by the segmenters (3.1.1 / 3.2.1).
    ctx:
        Active RunContext. Counters updated: citations_found, citations_resolved,
        citations_not_found, citations_external.
    code_section_repo:
        Optional callable ``(normalized_key: str) -> CodeSection | None``.
        When None the function runs in offline/test mode and all IAC citations
        are tagged not_found.
    """
    for unit in units:
        if unit.unit_kind == "register_row":
            _enrich_register_row(unit, ctx, code_section_repo)
        else:
            _enrich_prose_unit(unit, ctx, code_section_repo)


def _enrich_prose_unit(
    unit: ClauseUnit,
    ctx: RunContext,
    code_section_repo: Callable | None,
) -> None:
    """P1/prose path: scan text_raw for citation-shaped strings."""
    spans = find_citation_spans(unit.text_raw)
    context = _context_for_unit(unit)

    for span_start, span_end, raw in spans:
        parsed_list = parse_citation(raw)
        for parsed in parsed_list:
            resolution_status, code_section_id, in_kb = _resolve(
                parsed, ctx, code_section_repo
            )
            entry = CitationEntry(
                parsed=parsed,
                context=context,
                span_start=span_start,
                span_end=span_end,
                resolution_status=resolution_status,
                code_section_id=code_section_id,
                in_knowledge_base=in_kb,
            )
            unit.citations.append(entry)
            _count(ctx, resolution_status)


def _enrich_register_row(
    unit: ClauseUnit,
    ctx: RunContext,
    code_section_repo: Callable | None,
) -> None:
    """P2/register path: look for columns with role 'citation'."""
    if not unit.row_cells:
        return

    for col_name, cell_value in unit.row_cells.items():
        # Only process citation-role columns
        if not _is_citation_column(col_name, cell_value):
            continue

        cell_str = str(cell_value).strip() if cell_value is not None else ""
        if not cell_str:
            continue

        parsed_list = parse_citation(cell_str)
        for parsed in parsed_list:
            resolution_status, code_section_id, in_kb = _resolve(
                parsed, ctx, code_section_repo
            )
            entry = CitationEntry(
                parsed=parsed,
                context="register_column",
                span_start=0,
                span_end=len(cell_str),
                resolution_status=resolution_status,
                code_section_id=code_section_id,
                in_knowledge_base=in_kb,
            )
            unit.citations.append(entry)
            _count(ctx, resolution_status)


def _is_citation_column(col_name: str, _cell_value: object) -> bool:
    """Decide whether a row_cells column is a citation column.

    The column role is embedded in the key as produced by 3.2.1.
    Keys are either plain header strings or structured strings that
    include role information.  We accept a column if its lowercased
    name equals "citation" or ends with ":citation" (the structured form
    used by 3.2.1, e.g. "Regulatory Basis:citation").
    """
    if col_name is None:
        return False
    lower = col_name.lower()
    return lower == "citation" or lower.endswith(":citation")


def _count(ctx: RunContext, resolution_status: str) -> None:
    """Update ctx stats for one citation."""
    ctx.count("citations_found")
    if resolution_status == "resolved":
        ctx.count("citations_resolved")
    elif resolution_status == "not_found":
        ctx.count("citations_not_found")
    elif resolution_status == "external":
        ctx.count("citations_external")
