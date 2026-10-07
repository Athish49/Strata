"""Task 6.1.3 — document_scope rollup.

Builds DocumentScopeRow objects by aggregating IAC citation keys across
all ClauseUnits in a document version, plus any IAC citations found in the
front-matter regulatory basis strings.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.company_ingest.enrich.citations_grammar import parse_citation
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext


@dataclass
class DocumentScopeRow:
    doc_id: str
    version_id: str
    scope_key: str      # normalized_key (section) or rule_key (rule)
    scope_level: str    # "section" or "rule"
    sources: list[str]  # deduplicated source labels
    clause_count: int   # distinct clauses citing this key


def build_document_scope(
    doc_id: str,
    version_id: str,
    units: list[ClauseUnit],
    front_matter_regulatory_basis: list[str],
    ctx: RunContext,
) -> list[DocumentScopeRow]:
    """Build DocumentScopeRow objects for all IAC citations in *units* and
    *front_matter_regulatory_basis*.

    Returns one row per unique (scope_level, scope_key) pair found.
    """
    # Accumulators: {key: {"sources": set[str], "clause_ids": set[str]}}
    section_acc: dict[str, dict] = {}
    rule_acc: dict[str, dict] = {}

    def _add_section(key: str, label: str, clause_id: str | None) -> None:
        if key not in section_acc:
            section_acc[key] = {"sources": set(), "clause_ids": set()}
        section_acc[key]["sources"].add(label)
        if clause_id is not None:
            section_acc[key]["clause_ids"].add(clause_id)

    def _add_rule(key: str, label: str, clause_id: str | None) -> None:
        if key not in rule_acc:
            rule_acc[key] = {"sources": set(), "clause_ids": set()}
        rule_acc[key]["sources"].add(label)
        if clause_id is not None:
            rule_acc[key]["clause_ids"].add(clause_id)

    # --- Step 2: Accumulate from units ---
    for unit in units:
        for citation in unit.citations:
            # Skip non-IAC
            if citation.parsed.source_system != "iac":
                continue
            # Skip external resolutions
            if citation.resolution_status == "external":
                continue

            # Determine source label
            if citation.context == "regulatory_basis_table":
                label = "regulatory_basis_section"
            elif citation.context == "front_matter":
                label = "front_matter"
            else:
                label = "inline"

            normalized_key = citation.parsed.normalized_key
            rule_key = citation.parsed.rule_key

            _add_section(normalized_key, label, unit.clause_id)
            _add_rule(rule_key, label, unit.clause_id)

    # --- Step 3: Accumulate from front_matter_regulatory_basis ---
    for raw_str in front_matter_regulatory_basis:
        parsed_list = parse_citation(raw_str)
        for pc in parsed_list:
            if pc.source_system != "iac":
                continue
            _add_section(pc.normalized_key, "front_matter", None)
            _add_rule(pc.rule_key, "front_matter", None)

    # --- Step 4: Build rows ---
    rows: list[DocumentScopeRow] = []

    for scope_key, acc in section_acc.items():
        row = DocumentScopeRow(
            doc_id=doc_id,
            version_id=version_id,
            scope_key=scope_key,
            scope_level="section",
            sources=sorted(acc["sources"]),
            clause_count=len(acc["clause_ids"]),
        )
        rows.append(row)
        ctx.count("scope_rows_section")

    for scope_key, acc in rule_acc.items():
        row = DocumentScopeRow(
            doc_id=doc_id,
            version_id=version_id,
            scope_key=scope_key,
            scope_level="rule",
            sources=sorted(acc["sources"]),
            clause_count=len(acc["clause_ids"]),
        )
        rows.append(row)
        ctx.count("scope_rows_rule")

    return rows
