"""Task 8.1.2 — In-memory commit helpers and R2 report writer.

Does NOT write to Neon (the database).  DB writes are orchestrated by the
CLI in 8.2.1.  This module builds the in-memory commit helpers and the R2
report writer.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.company_ingest.parse.models import ClauseUnit
    from app.company_ingest.run_context import RunContext
    from app.company_ingest.validate.checks import CheckOutcome


# ---------------------------------------------------------------------------
# value_source computation (SPEC §6.2)
# ---------------------------------------------------------------------------

_REGULATORY_ROLES = {"regulatory_restatement"}
_COMPANY_ROLES = {"internal_target", "company_position"}
_TEMPLATE_ROLES = {"template_field", "definition"}


def compute_value_source(unit: "ClauseUnit", param_entry) -> str:
    """
    Compute value_source for a ParameterEntry per SPEC §6.2 rule:

    - role in {regulatory_restatement} and has citations → "regulatory"
    - role in {internal_target, company_position}        → "company"
    - role in {template_field, definition}               → "template"
    - otherwise                                          → "company"
    """
    role = unit.role

    if role in _REGULATORY_ROLES and len(unit.citations) > 0:
        return "regulatory"
    if role in _COMPANY_ROLES:
        return "company"
    if role in _TEMPLATE_ROLES:
        return "template"
    return "company"


# ---------------------------------------------------------------------------
# finalize_parameters
# ---------------------------------------------------------------------------


def finalize_parameters(units: list["ClauseUnit"]) -> None:
    """
    Set value_source on all ParameterEntry objects in place.

    Called just before commit.
    """
    for unit in units:
        for entry in unit.parameters:
            entry.value_source = compute_value_source(unit, entry)


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------


def build_run_report(
    ctx: "RunContext",
    check_outcomes: list["CheckOutcome"],
    doc_ids: list[str],
    unit_counts_by_doc: dict[str, int],
) -> dict:
    """
    Build the report.json dict from ctx.to_report() plus check outcomes.
    """
    return {
        **ctx.to_report(),
        "checks": [
            {
                "check_number": o.check_number,
                "name": o.name,
                "passed": o.passed,
                "metric": o.metric,
                "details": o.details,
            }
            for o in check_outcomes
        ],
        "passed": all(o.passed for o in check_outcomes),
        "documents": {
            doc_id: {"clause_count": unit_counts_by_doc.get(doc_id, 0)}
            for doc_id in doc_ids
        },
    }


async def write_report(
    ctx: "RunContext",
    check_outcomes: list["CheckOutcome"],
    doc_ids: list[str],
    unit_counts_by_doc: dict[str, int],
    r2_client,
) -> str:
    """Write report.json to R2. Returns the R2 key."""
    from app.company_ingest.store.r2_keys import report_key

    key = report_key(ctx.company_id, str(ctx.run_id))
    report = build_run_report(ctx, check_outcomes, doc_ids, unit_counts_by_doc)
    data = json.dumps(report, default=str).encode("utf-8")

    r2_client.put_bytes(
        key,
        data,
        {
            "content_type": "application/json",
            "doc_id": "report",
            "version": "1",
            "profile": "report",
        },
        "application/json",
    )
    return key
