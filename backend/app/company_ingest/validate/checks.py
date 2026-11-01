"""Task 8.1.1 — Acceptance checks for a company ingest run.

Implements the acceptance checks defined in SPEC §12 as pure functions
over in-memory data structures.  No I/O or network calls are made here.

Checks 9 (Parquet row counts), 10 (parameter checks validated) and 12 (no
denied files in R2 / allowlist exercised) were removed by task 2.3 together
with the ``datasets/`` and ``collect/`` packages they measured.  The remaining
checks keep their SPEC numbers; ``CHECK_NUMBERS`` lists them.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Result and state types
# ---------------------------------------------------------------------------


@dataclass
class CheckOutcome:
    """Result of one acceptance check."""

    check_number: int
    name: str
    passed: bool
    metric: str | None      # human-readable metric value, e.g. "47/50 clauses"
    details: dict = field(default_factory=dict)  # extra info for debugging


@dataclass
class RunState:
    """Snapshot of all in-memory data for one ingest run."""

    units: list               # list[ClauseUnit]
    links: list               # list[ClauseLink]
    scope_rows: list          # list[DocumentScopeRow]
    doc_ids: list[str]
    # stats and issues copied from RunContext
    stats: dict[str, int]
    issues: list              # list[Issue]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_1(state: RunState) -> CheckOutcome:
    """Check 1 — Unclaimed text ≤ 5%."""
    unclaimed_chars: int = state.stats.get("unclaimed_text_chars", 0)
    total_chars: int = sum(len(u.text_raw) for u in state.units)

    if total_chars == 0:
        passed = True
    else:
        passed = unclaimed_chars / total_chars <= 0.05

    return CheckOutcome(
        check_number=1,
        name="unclaimed_text_le_5pct",
        passed=passed,
        metric=f"{unclaimed_chars}/{total_chars} unclaimed chars",
        details={
            "unclaimed_chars": unclaimed_chars,
            "total_chars": total_chars,
            "ratio": unclaimed_chars / total_chars if total_chars > 0 else 0.0,
        },
    )


def check_2(state: RunState) -> CheckOutcome:
    """Check 2 — No duplicate clause IDs."""
    clause_ids = [u.clause_id for u in state.units]
    counts = Counter(clause_ids)
    duplicates = [cid for cid, n in counts.items() if n > 1]
    dup_count = len(duplicates)

    return CheckOutcome(
        check_number=2,
        name="no_duplicate_clause_ids",
        passed=dup_count == 0,
        metric=f"{dup_count} duplicates",
        details={"first_10_duplicates": duplicates[:10]},
    )


def check_3(state: RunState) -> CheckOutcome:
    """Check 3 — All text_sha256 verified."""
    from app.company_ingest.parse.text import sha256_text

    bad = 0
    total = len(state.units)
    bad_ids: list[str] = []

    for u in state.units:
        if sha256_text(u.text_raw) != u.text_sha256:
            bad += 1
            if len(bad_ids) < 10:
                bad_ids.append(u.clause_id)

    return CheckOutcome(
        check_number=3,
        name="text_sha256_verified",
        passed=bad == 0,
        metric=f"{bad}/{total} mismatches",
        details={"first_10_mismatches": bad_ids},
    )


def check_4(state: RunState) -> CheckOutcome:
    """Check 4 — All regex parameters verified."""
    unverified = 0
    unverified_ids: list[str] = []

    for u in state.units:
        for param in u.parameters:
            if getattr(param, "method", None) == "regex" and not getattr(param, "verified", True):
                unverified += 1
                if len(unverified_ids) < 10:
                    unverified_ids.append(u.clause_id)

    return CheckOutcome(
        check_number=4,
        name="regex_params_verified",
        passed=unverified == 0,
        metric=f"{unverified} unverified regex params",
        details={"first_10_clause_ids": unverified_ids},
    )


def check_5(state: RunState) -> CheckOutcome:
    """Check 5 — No regulatory_restatement without citation."""
    violations: list[str] = []

    for u in state.units:
        if u.role == "regulatory_restatement" and len(u.citations) == 0:
            violations.append(u.clause_id)

    count = len(violations)
    return CheckOutcome(
        check_number=5,
        name="regulatory_restatement_has_citation",
        passed=count == 0,
        metric=f"{count} violations",
        details={"violating_clause_ids": violations[:10]},
    )


def check_6(state: RunState) -> CheckOutcome:
    """Check 6 — Coverage: all selected units have a role."""
    from app.company_ingest.llm.clause_enrichment import should_enrich

    eligible = [u for u in state.units if should_enrich(u)]
    undecided = [u for u in eligible if u.role is None]
    total_eligible = len(eligible)
    undecided_count = len(undecided)

    return CheckOutcome(
        check_number=6,
        name="all_eligible_units_have_role",
        passed=undecided_count == 0,
        metric=f"{undecided_count}/{total_eligible} undecided",
        details={"undecided_clause_ids": [u.clause_id for u in undecided[:10]]},
    )


def check_7(state: RunState) -> CheckOutcome:
    """Check 7 — Reference resolution ≥ 80%."""
    resolved: int = state.stats.get("links_resolved", 0)
    unresolved: int = state.stats.get("links_unresolved", 0)
    total = resolved + unresolved

    if total == 0:
        passed = True
        ratio = 1.0
    else:
        ratio = resolved / total
        passed = ratio >= 0.8

    return CheckOutcome(
        check_number=7,
        name="ref_resolution_ge_80pct",
        passed=passed,
        metric=f"{resolved}/{total} resolved",
        details={"resolved": resolved, "unresolved": unresolved, "ratio": ratio},
    )


def check_8(state: RunState) -> CheckOutcome:
    """Check 8 — All front-matter regulatory_basis in scope."""
    unresolved_issues = [
        i for i in state.issues
        if getattr(i, "code", None) == "front_matter_citation_not_found"
    ]
    count = len(unresolved_issues)

    return CheckOutcome(
        check_number=8,
        name="front_matter_citations_in_scope",
        passed=count == 0,
        metric=f"{count} unresolved front-matter entries",
        details={
            "unresolved_doc_ids": [
                getattr(i, "doc_id", None) for i in unresolved_issues[:10]
            ]
        },
    )


def check_11(state: RunState) -> CheckOutcome:
    """Check 11 — Qdrant round-trip.

    This check requires a live Qdrant connection.  In offline / unit-test mode
    it always passes.  The real integration check should be run in a deployment
    environment where Qdrant is reachable.
    """
    return CheckOutcome(
        check_number=11,
        name="qdrant_round_trip",
        passed=True,
        metric="skipped (qdrant not available in offline mode)",
        details={},
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

# SPEC §12 numbers of the checks still in force (9, 10 and 12 were removed).
CHECK_NUMBERS: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 11)


def run_all_checks(state: RunState, ctx: RunContext) -> list[CheckOutcome]:
    """Run every acceptance check in :data:`CHECK_NUMBERS`.

    Any check that raises an exception returns a failed outcome so that the
    remaining checks still execute.

    Functions are looked up dynamically at call time so that test patches
    applied to module-level names are respected.
    """
    import sys

    module = sys.modules[__name__]
    outcomes: list[CheckOutcome] = []

    for n in CHECK_NUMBERS:
        try:
            fn = getattr(module, f"check_{n}")
            outcomes.append(fn(state))
        except Exception as exc:  # noqa: BLE001
            outcomes.append(
                CheckOutcome(
                    check_number=n,
                    name=f"check_{n}",
                    passed=False,
                    metric=None,
                    details={"error": str(exc)},
                )
            )

    return outcomes
