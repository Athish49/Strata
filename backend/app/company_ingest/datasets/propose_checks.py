"""Task 7.2.2 — Stage 4c: LLM-proposed dataset parameter checks."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.company_ingest.datasets.profile import DatasetProfile
from app.company_ingest.llm.client import call_structured
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are proposing SQL checks for a compliance dataset.

Each check is a SELECT statement that returns rows VIOLATING or NEWLY IN SCOPE for a regulatory parameter.
Rules:
- Use only column names from the provided schema
- Use {placeholder} syntax for parameter values; each placeholder must bind to a provided parameter_pk
- Write single SELECT or WITH...SELECT statements only; no semicolons, no DDL
- 0 to 5 checks per dataset
- Each check's purpose must be a complete sentence explaining what it validates
"""

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ColumnDescription(BaseModel):
    column_name: str
    semantic_role: str | None = None
    description: str | None = None


class ParameterBinding(BaseModel):
    placeholder: str     # the {placeholder} name in the SQL template
    parameter_pk: str    # identifies the parameter this binds to


class ProposedCheck(BaseModel):
    purpose: str
    sql_template: str
    param_bindings: list[ParameterBinding]

    @field_validator("param_bindings")
    @classmethod
    def bindings_match_template(cls, v: list[ParameterBinding], info: Any) -> list[ParameterBinding]:
        # Optionally validate that each placeholder appears in sql_template
        return v


class DatasetEnrichment(BaseModel):
    description: str
    columns: list[ColumnDescription] = Field(default_factory=list)
    checks: list[ProposedCheck] = Field(default_factory=list)

    @field_validator("checks")
    @classmethod
    def cap_checks(cls, v: list[ProposedCheck]) -> list[ProposedCheck]:
        return v[:5]  # max 5 checks


# ---------------------------------------------------------------------------
# CheckProposal dataclass
# ---------------------------------------------------------------------------


@dataclass
class CheckProposal:
    dataset_name: str
    doc_id: str | None
    purpose: str
    sql_template: str
    param_bindings: dict[str, str]   # {placeholder: parameter_pk}
    validated: bool = False
    method: str = "llm_proposed"
    s1_result: dict | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Helper: find describing clauses
# ---------------------------------------------------------------------------


def _find_describing_clauses(
    profile: DatasetProfile,
    all_units: list[ClauseUnit],
    clause_links: list,
    max_clauses: int = 25,
) -> list[ClauseUnit]:
    """Find clauses in the same document that mention the dataset by name or column name.

    Prefer clauses with verified parameters (len(unit.parameters) > 0).
    Cap at max_clauses.
    """
    # Step 1: Filter units where unit.doc_id == profile.doc_id (same document)
    if profile.doc_id is None:
        same_doc = [u for u in all_units if u.doc_id is None]
    else:
        same_doc = [u for u in all_units if u.doc_id == profile.doc_id]

    # Build set of column names from profile
    col_names = {cp.column_name for cp in profile.columns}

    # Build set of clause_ids for same-doc units
    same_doc_clause_ids = {u.clause_id for u in same_doc}

    # Step 2: Keep units where dataset name appears in text_raw, or any column name appears
    def _mentions_dataset(unit: ClauseUnit) -> bool:
        text = unit.text_raw
        if profile.name in text:
            return True
        for col in col_names:
            if col in text:
                return True
        return False

    matched: set[str] = {u.clause_id for u in same_doc if _mentions_dataset(u)}

    # Step 3: Include units linked by clause_ref columns
    # For each clause_link, if from_clause_id is in same_doc, include the to_clause_id unit (if it exists)
    same_doc_unit_map = {u.clause_id: u for u in same_doc}

    for link in clause_links:
        from_id = getattr(link, "from_clause_id", None)
        to_id = getattr(link, "to_clause_id", None)
        if from_id in same_doc_clause_ids and to_id is not None:
            if to_id in same_doc_unit_map:
                matched.add(to_id)

    # Collect matched units
    result_units = [u for u in same_doc if u.clause_id in matched]

    # Step 4: Sort — units with parameters first
    result_units.sort(key=lambda u: (0 if len(u.parameters) > 0 else 1, u.ordinal))

    # Step 5: Truncate to max_clauses
    return result_units[:max_clauses]


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


async def propose_checks(
    profile: DatasetProfile,
    all_units: list[ClauseUnit],
    clause_links: list,
    ctx: RunContext,
) -> tuple[str | None, list[CheckProposal]]:
    """Propose SQL checks for a dataset by calling the LLM.

    Returns (description, proposals). On LLM failure returns (None, []).
    """
    # Step 1: Find describing clauses
    describing_clauses = _find_describing_clauses(profile, all_units, clause_links)

    # Step 2: Build parameter_pk map
    # For each describing clause, for each ParameterEntry in clause.parameters,
    # assign pk = clause.clause_id + ":" + str(i) (0-indexed)
    parameter_pk_map: dict[str, Any] = {}
    for unit in describing_clauses:
        for i, param in enumerate(unit.parameters):
            pk = f"{unit.clause_id}:{i}"
            parameter_pk_map[pk] = param

    # Step 3: Build user message
    # Dataset info
    col_lines: list[str] = []
    for cp in profile.columns:
        line = f"  - {cp.column_name} ({cp.dtype}): null_rate={cp.null_rate:.3f}, distinct={cp.distinct_count}"
        if cp.top_values is not None and cp.distinct_count <= 50:
            vals = ", ".join(str(tv["value"]) for tv in cp.top_values[:5])
            line += f", top_values=[{vals}]"
        col_lines.append(line)

    col_section = "\n".join(col_lines) if col_lines else "  (none)"

    # Describing clauses info
    clause_lines: list[str] = []
    for unit in describing_clauses:
        preview = unit.text_raw[:300]
        clause_lines.append(f"\n  clause_id: {unit.clause_id}")
        clause_lines.append(f"  text: {preview}")
        if unit.parameters:
            for i, param in enumerate(unit.parameters):
                pk = f"{unit.clause_id}:{i}"
                clause_lines.append(f"    param_pk={pk}: {param}")

    clause_section = "\n".join(clause_lines) if clause_lines else "  (no describing clauses found)"

    user_msg = (
        f"Dataset: {profile.name}\n"
        f"Row count: {profile.row_count}\n"
        f"Columns:\n{col_section}\n\n"
        f"Describing clauses:{clause_section}\n\n"
        "Placeholder rules:\n"
        "- Use {{placeholder_name}} syntax in sql_template\n"
        "- Each placeholder must bind to a parameter_pk from the clauses above\n"
        "- Only use column names listed in Columns above\n"
    )

    # Step 4: Call LLM
    enrichment = await call_structured(
        "propose_checks",
        profile.name,
        SYSTEM_PROMPT,
        user_msg,
        DatasetEnrichment,
        ctx,
    )

    if enrichment is None:
        return None, []

    # Step 5: Process each ProposedCheck
    proposals: list[CheckProposal] = []

    for check in enrichment.checks:
        valid_bindings: dict[str, str] = {}

        for binding in check.param_bindings:
            placeholder = binding.placeholder
            param_pk = binding.parameter_pk

            # Validate: placeholder appears in sql_template in {placeholder} form
            if f"{{{placeholder}}}" not in check.sql_template:
                ctx.issue(
                    "warning",
                    "propose_checks",
                    "check_binding_invalid",
                    f"Placeholder '{{{placeholder}}}' not found in sql_template for dataset {profile.name}",
                    doc_id=profile.doc_id,
                )
                continue

            # Validate: parameter_pk is in the parameter_pk_map
            if param_pk not in parameter_pk_map:
                ctx.issue(
                    "warning",
                    "propose_checks",
                    "check_binding_invalid",
                    f"parameter_pk '{param_pk}' not found in parameter map for dataset {profile.name}",
                    doc_id=profile.doc_id,
                )
                continue

            valid_bindings[placeholder] = param_pk

        proposal = CheckProposal(
            dataset_name=profile.name,
            doc_id=profile.doc_id,
            purpose=check.purpose,
            sql_template=check.sql_template,
            param_bindings=valid_bindings,
            validated=False,
            method="llm_proposed",
        )
        proposals.append(proposal)
        ctx.count("checks_proposed")

    return enrichment.description, proposals
