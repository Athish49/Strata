"""Task 7.1.2 — Foreign-key and clause-reference detection.

Runs after 7.1.1 (DatasetProfile objects already built).
Mutates ColumnProfile objects in place by setting semantic_role and fk_target.
"""
from __future__ import annotations

import re
import logging
from typing import TYPE_CHECKING

from app.company_ingest.run_context import RunContext

if TYPE_CHECKING:
    from app.company_ingest.datasets.profile import DatasetProfile, ColumnProfile

logger = logging.getLogger(__name__)

# Regex patterns for clause-ID-like values
_CLAUSE_PATTERNS = [
    re.compile(r"^\d+(\.\d+){0,2}[a-z]?$"),   # e.g. "7.2.1", "3a"
    re.compile(r"^App-[A-Z]\.\d+$"),             # e.g. "App-A.1"
    re.compile(r"^S\d+\.\d+$"),                  # e.g. "S1.2"
]


def _matches_clause_pattern(value: str) -> bool:
    """Return True if value looks like a clause/section ID."""
    for pat in _CLAUSE_PATTERNS:
        if pat.match(value):
            return True
    return False


def _top_values_set(column: "ColumnProfile") -> set[str] | None:
    """Return the set of non-null string values from top_values, or None if unavailable."""
    if column.top_values is None:
        return None
    return {entry["value"] for entry in column.top_values if entry["value"] not in (None, "None")}


def _detect_fk(
    profiles: list["DatasetProfile"],
    ctx: RunContext,
) -> None:
    """Detect foreign-key columns across all datasets."""
    # Build a quick lookup: dataset_name -> DatasetProfile
    by_name: dict[str, "DatasetProfile"] = {p.name: p for p in profiles}

    for dataset in profiles:
        pk_col = dataset.primary_key  # the dataset's own PK column name

        for col in dataset.columns:
            name = col.column_name
            name_lower = name.lower()

            # Must end in _id or _serial
            if not (name_lower.endswith("_id") or name_lower.endswith("_serial")):
                continue

            # Skip if this column IS the dataset's own primary key
            if pk_col is not None and name == pk_col:
                continue

            # Skip if top_values is None (too many distinct values — can't safely confirm)
            if col.top_values is None:
                continue

            candidate_values = _top_values_set(col)
            if candidate_values is None:
                continue

            # Search for a matching dataset E whose primary_key == name (heuristic)
            for other in profiles:
                if other.name == dataset.name:
                    continue
                if other.primary_key is None:
                    continue

                # Heuristic: column name matches or ends with other.primary_key
                if not (name == other.primary_key or name_lower.endswith(other.primary_key.lower())):
                    continue

                # Confirm with top_values if available
                other_pk_col = next(
                    (c for c in other.columns if c.column_name == other.primary_key), None
                )
                if other_pk_col is not None and other_pk_col.top_values is not None:
                    other_pk_values = _top_values_set(other_pk_col) or set()
                    if len(candidate_values) == 0:
                        # All values are null-like; skip
                        break
                    matching = candidate_values & other_pk_values
                    match_rate = len(matching) / len(candidate_values)
                    if match_rate < 0.90:
                        # Not enough overlap — not a FK
                        continue

                    # FK integrity warning: values that don't appear in target
                    missing_count = len(candidate_values - other_pk_values)
                    if missing_count > 0:
                        ctx.issue(
                            severity="warning",
                            stage="7.1.2",
                            code="fk_integrity_violation",
                            message=(
                                f"{dataset.name}.{name}: {missing_count} values "
                                f"not in {other.name}.{other.primary_key}"
                            ),
                            details={"count": missing_count},
                        )
                else:
                    # No top_values on target PK — heuristic match only, accept
                    pass

                # Mark as FK
                col.semantic_role = "foreign_key"
                col.fk_target = f"{other.name}.{other.primary_key}"
                ctx.count("fk_detected")
                break  # first match wins


def _detect_clause_refs(
    profiles: list["DatasetProfile"],
    clause_ids_by_doc: dict[str, set[str]],
    ctx: RunContext,
) -> None:
    """Detect clause-reference columns across all datasets."""
    for dataset in profiles:
        doc_id = dataset.doc_id

        for col in dataset.columns:
            # Must be a text (string) column
            if col.dtype != "text":
                continue

            # Must have top_values available
            if col.top_values is None:
                continue

            # Must have at most 200 distinct values
            if col.distinct_count > 200:
                continue

            # Collect non-null values
            non_null_values = [
                entry["value"]
                for entry in col.top_values
                if entry["value"] not in (None, "None")
            ]
            if not non_null_values:
                continue

            # Count how many match clause-ID patterns
            matching = [v for v in non_null_values if _matches_clause_pattern(v)]
            match_rate = len(matching) / len(non_null_values)

            if match_rate < 0.90:
                continue

            # Need a doc_id to anchor the clause reference
            if doc_id is None:
                continue

            # Find which doc's clause IDs cover ≥ 80% of the matching values
            matched_doc: str | None = None
            for candidate_doc_id, clause_id_set in clause_ids_by_doc.items():
                hits = sum(1 for v in matching if v in clause_id_set)
                if len(matching) > 0 and hits / len(matching) >= 0.80:
                    matched_doc = candidate_doc_id
                    break

            if matched_doc is None:
                continue

            col.semantic_role = "clause_ref"
            col.fk_target = f"clause:{matched_doc}:{col.column_name}"
            ctx.count("clause_ref_detected")


def detect_keys(
    profiles: list["DatasetProfile"],
    clause_ids_by_doc: dict[str, set[str]],
    ctx: RunContext,
) -> None:
    """For each dataset, detect foreign-key columns and clause-reference columns.

    Mutates ColumnProfile objects in place by setting semantic_role and fk_target.

    Parameters
    ----------
    profiles:
        List of DatasetProfile objects already built by task 7.1.1.
    clause_ids_by_doc:
        Maps each doc_id to the set of local clause IDs registered for that document
        (e.g. ``{"RPL-DCC-PRO-003": {"1.1", "1.2", "7.2.1", ...}}``).
    ctx:
        RunContext for logging issues and incrementing stats.
    """
    _detect_fk(profiles, ctx)
    _detect_clause_refs(profiles, clause_ids_by_doc, ctx)
