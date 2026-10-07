"""Task 5.2.1 — Stage 4b: LLM-based column role classification for register CSVs."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.company_ingest.constants import ColumnRole
from app.company_ingest.llm.client import call_structured

if TYPE_CHECKING:
    from app.company_ingest.run_context import RunContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM response schemas
# ---------------------------------------------------------------------------


class ColumnRoleAssignment(BaseModel):
    column_name: str
    role: ColumnRole


class ColumnRolesResponse(BaseModel):
    assignments: list[ColumnRoleAssignment]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are classifying columns in a regulatory compliance register CSV.

Column roles:
- id: The row's primary identifier column
- citation: Contains regulatory citation strings (e.g. "170 IAC 4-1-16")
- regulatory_value: A threshold, deadline, or quantity from a regulation
- rule_quote: A verbatim quote from a regulation
- summary_text: Free-text description, title, or notes
- reference_list: Semicolon-separated list of document or clause IDs
- owner_person: Person ID (e.g. P01, P02) or name of responsible party
- date: A date value
- enum: A fixed vocabulary (status, priority, type)
- status: Current state (active, pending, compliant, etc.)
- free_text: Unstructured free text not fitting other categories
- ignore: Metadata, internal tracking, not useful for compliance analysis

Rules:
- Assign exactly one role per column
- Use the column name AND sample values together
- Only classify the columns listed in "Columns needing classification"
- Return only those columns in your response
"""


# ---------------------------------------------------------------------------
# User message builder
# ---------------------------------------------------------------------------


def _build_user_message(
    doc_id: str,
    headers: list[str],
    provisional_roles: dict[str, str | None],
    null_columns: list[str],
    sample_rows: list[dict[str, str]],
) -> str:
    """Build the user message for column role classification."""
    lines: list[str] = []

    lines.append(f"Document: {doc_id}")
    lines.append("")
    lines.append("All columns with current roles:")
    for col in headers:
        role = provisional_roles.get(col) or "unknown"
        lines.append(f"  {col}: {role}")

    lines.append("")
    lines.append("Columns needing classification:")
    for col in null_columns:
        lines.append(f"  {col}")

    lines.append("")
    lines.append("Sample rows (up to 5):")
    if sample_rows and null_columns:
        # Header row for just the null columns
        header_row = " | ".join(null_columns)
        lines.append(f"  {header_row}")
        lines.append("  " + "-" * len(header_row))
        for row in sample_rows:
            values = " | ".join(str(row.get(col, "")) for col in null_columns)
            lines.append(f"  {values}")
    else:
        lines.append("  (no sample rows available)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


async def run_column_roles(
    doc_id: str,
    headers: list[str],
    provisional_roles: dict[str, str | None],
    sample_rows: list[dict[str, str]],
    ctx: "RunContext",
) -> dict[str, str | None]:
    """For columns with null provisional roles, call the LLM to assign a ColumnRole.

    Returns updated roles dict: {column_name: role} for ALL columns (not just null ones).
    """
    # 1. Filter to only the columns with null provisional roles
    null_columns = [col for col in headers if provisional_roles.get(col) is None]

    # 2. If none need LLM help, return provisional_roles as-is
    if not null_columns:
        return dict(provisional_roles)

    # 3. Build user message
    user_msg = _build_user_message(
        doc_id=doc_id,
        headers=headers,
        provisional_roles=provisional_roles,
        null_columns=null_columns,
        sample_rows=sample_rows[:5],
    )

    # 4. Call the LLM
    result = await call_structured(
        "column_roles",
        doc_id,
        SYSTEM_PROMPT,
        user_msg,
        ColumnRolesResponse,
        ctx,
    )

    # 5. Start with a copy of provisional_roles
    updated: dict[str, str | None] = dict(provisional_roles)

    # 8. If call returns None (LLM failure), keep None for those columns
    if result is None:
        return updated

    # 5. Merge LLM results back into the copy
    llm_map = {a.column_name: a.role for a in result.assignments}
    for col in null_columns:
        if col in llm_map:
            updated[col] = llm_map[col]
            # 7. Count each LLM-classified column
            ctx.count("column_roles_llm_assigned")
        # 6. For any column the LLM didn't cover, keep None (already set)

    return updated
