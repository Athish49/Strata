"""Task 4.1.4 — Deterministic clause-role markers.

Sets unit.role, unit.role_method, and unit.assessable on ClauseUnit
objects using marker-text, structural heuristics, and grammar patterns.
Never overwrites a role already set by a prior stage.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.company_ingest.parse.models import ClauseUnit
    from app.company_ingest.run_context import RunContext

# Section kinds that are always boilerplate
_BOILERPLATE_SECTIONS = {"revision_history", "approval", "related_docs", "front_matter"}

# Section kinds where assessable is always False regardless of role
_NON_ASSESSABLE_SECTIONS = {"revision_history", "approval", "related_docs"}

# Roles that are not assessable
_NON_ASSESSABLE_ROLES = {"boilerplate", "informational", "out_of_scope_reference"}

# Roles that are assessable
_ASSESSABLE_ROLES = {
    "internal_target",
    "company_position",
    "template_field",
    "definition",
    "regulatory_restatement",
}

_DEFINITION_GRAMMAR_RE = re.compile(r"^\*\*.+?\*\*\s+(means|is)\b")


def _determine_role(unit: ClauseUnit) -> tuple[str | None, str | None]:
    """Apply rules in order and return (role, role_method) or (None, None)."""
    text = unit.text_raw.lstrip()

    # Rule 1 — marker: internal performance target
    if text.startswith("Internal performance target:"):
        return "internal_target", "marker"

    # Rule 2 — marker: company position
    if text.startswith("Company position:"):
        return "company_position", "marker"

    # Rule 3 — structural: form field
    if unit.unit_kind == "form_field":
        return "template_field", "heuristic"

    # Rule 4 — structural: definitions section
    if unit.section_kind == "definitions":
        return "definition", "heuristic"

    # Rule 5 — grammar: bold term + means|is
    if _DEFINITION_GRAMMAR_RE.match(text):
        return "definition", "grammar"

    # Rule 6 — structural: boilerplate sections
    if unit.section_kind in _BOILERPLATE_SECTIONS:
        return "boilerplate", "heuristic"

    # Rule 7 — structural: register row with resolved citations → regulatory restatement
    # Without citations it cannot be a restatement; downgrade to internal_procedure.
    if unit.unit_kind == "register_row":
        if unit.citations:
            return "regulatory_restatement", "heuristic"
        return "internal_procedure", "heuristic"

    return None, None


def _determine_assessable(unit: ClauseUnit) -> bool:
    """Compute the assessable flag after role has been set."""
    # Section-based override beats everything else
    if unit.section_kind in _NON_ASSESSABLE_SECTIONS:
        return False

    if unit.role in _NON_ASSESSABLE_ROLES:
        return False

    # Covers explicit assessable roles AND role=None (provisional True)
    return True


def enrich_roles(units: list[ClauseUnit], ctx: RunContext) -> None:
    """Set role, role_method, and assessable on each unit (in-place).

    Skips any unit whose role is already set (assigned by a prior stage).
    Updates ctx.stats with 'roles_deterministic' and 'roles_undecided'.
    """
    for unit in units:
        # Never overwrite a role set by an earlier stage
        if unit.role is not None:
            continue

        role, role_method = _determine_role(unit)
        unit.role = role
        unit.role_method = role_method
        unit.assessable = _determine_assessable(unit)

        if role is not None:
            ctx.count("roles_deterministic")
        else:
            ctx.count("roles_undecided")
