"""Task 5.1.2 — Stage 4a runner: per-clause LLM enrichment."""
from __future__ import annotations

import logging
from pathlib import Path

from app.company_ingest.enrich.parameter_entry import ParameterEntry
from app.company_ingest.llm.clause_enrichment import (
    build_clause_user_message,
    should_enrich,
    split_if_long,
)
from app.company_ingest.llm.client import call_structured
from app.company_ingest.llm.schemas import ClauseEnrichment
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.parse.text import find_verbatim
from app.company_ingest.run_context import RunContext

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    Path(__file__).parent / "prompts" / "clause_enrichment.md"
).read_text()

# Roles that make assessable=False.
_NON_ASSESSABLE_ROLES = frozenset(
    {"boilerplate", "informational", "out_of_scope_reference"}
)


def _recompute_assessable(unit: ClauseUnit) -> None:
    """Set unit.assessable based on unit.role."""
    if unit.role in _NON_ASSESSABLE_ROLES:
        unit.assessable = False
    else:
        unit.assessable = True


async def _process_unit(
    unit: ClauseUnit,
    all_units: list[ClauseUnit],
    ctx: RunContext,
) -> None:
    """Run LLM enrichment on a single unit and mutate it in place."""
    # Find parent text.
    parent_text: str | None = None
    if unit.parent_clause_id is not None:
        for u in all_units:
            if u.clause_id == unit.parent_clause_id:
                parent_text = u.text_raw[:400]
                break

    user_msg = build_clause_user_message(
        unit, parent_text, unit.citations, unit.parameters
    )

    ctx.count("units_enriched_llm")

    result: ClauseEnrichment | None = await call_structured(
        "clause_enrichment",
        unit.clause_id,
        _SYSTEM_PROMPT,
        user_msg,
        ClauseEnrichment,
        ctx,
    )

    if result is None:
        return

    # Post-verification of SemanticParam values.
    for param in result.parameters:
        spans = find_verbatim(unit.text_raw, param.value_text)
        if spans:
            entry = ParameterEntry(
                kind=param.kind,
                value_text=param.value_text,
                value_num=None,
                unit=None,
                day_type="n_a",
                qualifier=None,
                span_start=spans[0][0],
                span_end=spans[0][1],
                method="llm",
                verified=True,
                value_source=None,
            )
            unit.parameters.append(entry)
        else:
            ctx.count("params_dropped_not_verbatim")
            ctx.issue(
                "info",
                "clause_enrichment",
                "param_not_verbatim",
                f"Parameter value not verbatim in clause {unit.clause_id}: {param.value_text!r}",
                clause_id=unit.clause_id,
            )

    # Post-verification of citation_links.
    valid_citation_raws: set[str] = set()
    for entry in unit.citations:
        if hasattr(entry, "parsed") and hasattr(entry.parsed, "citation_raw"):
            valid_citation_raws.add(entry.parsed.citation_raw)

    for link in result.citation_links:
        if link.citation_raw not in valid_citation_raws:
            ctx.issue(
                "info",
                "clause_enrichment",
                "citation_link_unmatched",
                (
                    f"Citation link not matched in clause {unit.clause_id}: "
                    f"{link.citation_raw!r}"
                ),
                clause_id=unit.clause_id,
            )

    # Role assignment — only when no prior role was set.
    if result.clause_role is not None and unit.role is None:
        role_str = str(result.clause_role)
        if role_str == "regulatory_restatement" and len(unit.citations) == 0:
            role_str = "internal_procedure"
            ctx.issue(
                "warning",
                "clause_enrichment",
                "restatement_without_citation",
                (
                    f"LLM assigned regulatory_restatement but no citations found "
                    f"for {unit.clause_id}"
                ),
                clause_id=unit.clause_id,
            )
        unit.role = role_str
        unit.role_method = "llm"
        ctx.count("roles_llm")

    # Propagate normalised statement and topic terms.
    if result.normalized_statement is not None:
        unit.normalized_statement = result.normalized_statement
    if result.topic_terms:
        unit.topic_terms = result.topic_terms


async def run_clause_enrichment(units: list[ClauseUnit], ctx: RunContext) -> None:
    """Run LLM clause enrichment on eligible units. Mutates units in place."""
    if ctx.no_llm:
        for unit in units:
            ctx.count("units_skipped_no_llm")
            if unit.role is None:
                if len(unit.citations) > 0:
                    unit.role = "regulatory_restatement"
                else:
                    unit.role = "internal_procedure"
                unit.role_method = "heuristic"
            _recompute_assessable(unit)
        return

    for unit in units:
        if not should_enrich(unit):
            continue

        children = split_if_long(unit)
        is_split = len(children) > 1

        if is_split:
            for child in children:
                await _process_unit(child, units, ctx)
            # Merge first child's role/statement to original unit.
            first_child = children[0]
            if unit.role is None and first_child.role is not None:
                unit.role = first_child.role
                unit.role_method = first_child.role_method
            if first_child.normalized_statement is not None:
                unit.normalized_statement = first_child.normalized_statement
            # Collect all parameters from all children into the original unit.
            for child in children:
                unit.parameters.extend(child.parameters)
        else:
            await _process_unit(unit, units, ctx)

        _recompute_assessable(unit)
