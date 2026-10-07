"""Task 6.1.1 — Resolve RefEntry objects into ClauseLink records.

Reads RefEntry objects already attached to ClauseUnit.refs and resolves
each one to a concrete ClauseLink by looking up the target in one of the
seven in-memory indexes built from the unit list.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass

from app.company_ingest.constants import LinkType, UnitKind
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext

logger = logging.getLogger(__name__)

# Pattern for form IDs embedded in text or heading paths
_FORM_ID_RE = re.compile(r"[A-Z]{2,4}-F-\d{3}")
# Pattern for rule local_ids like "R16.3"
_RULE_LOCAL_RE = re.compile(r"^(R\d+)\.")


@dataclass
class ClauseLink:
    """A resolved link between two clauses (or a clause and a document)."""

    from_clause_id: str
    to_clause_id: str | None    # full clause_id, or None if target is a doc
    to_doc_id: str | None       # populated for references_doc with no specific clause
    link_type: str              # LinkType value
    method: str                 # "regex" or "register_column"
    evidence: str               # raw matched string
    confidence: float           # 1.0 for deterministic


# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------

def _build_clause_index(units: list[ClauseUnit]) -> dict[str, ClauseUnit]:
    return {u.clause_id: u for u in units}


def _build_sheet_index(units: list[ClauseUnit]) -> dict[str, list[ClauseUnit]]:
    idx: dict[str, list[ClauseUnit]] = defaultdict(list)
    for u in units:
        if u.sheet_no is not None:
            idx[u.sheet_no].append(u)
    return dict(idx)


def _build_rule_index(units: list[ClauseUnit]) -> dict[str, list[ClauseUnit]]:
    idx: dict[str, list[ClauseUnit]] = defaultdict(list)
    for u in units:
        m = _RULE_LOCAL_RE.match(u.local_id)
        if m:
            idx[m.group(1)].append(u)
    return dict(idx)


def _build_form_index(units: list[ClauseUnit]) -> dict[str, ClauseUnit]:
    idx: dict[str, ClauseUnit] = {}
    for u in units:
        # Check heading_path last element first
        candidate: str | None = None
        if u.heading_path:
            m = _FORM_ID_RE.search(u.heading_path[-1])
            if m:
                candidate = m.group(0)
        # Fallback: first line of text_raw
        if candidate is None and u.text_raw:
            first_line = u.text_raw.split("\n", 1)[0]
            m = _FORM_ID_RE.search(first_line)
            if m:
                candidate = m.group(0)
        if candidate and candidate not in idx:
            idx[candidate] = u
    return idx


def _build_series_index(units: list[ClauseUnit]) -> dict[str, ClauseUnit]:
    _pat = re.compile(r"^RRS-[A-Z]+-\d+$")
    return {
        u.local_id: u
        for u in units
        if u.unit_kind == UnitKind.REGISTER_ROW and _pat.match(u.local_id)
    }


def _build_obligation_index(units: list[ClauseUnit]) -> dict[str, ClauseUnit]:
    _pat = re.compile(r"^OBL-\d+-\d+$")
    return {
        u.local_id: u
        for u in units
        if u.unit_kind == UnitKind.REGISTER_ROW and _pat.match(u.local_id)
    }


def _build_doc_index(units: list[ClauseUnit]) -> dict[str, list[ClauseUnit]]:
    idx: dict[str, list[ClauseUnit]] = defaultdict(list)
    for u in units:
        idx[u.doc_id].append(u)
    return dict(idx)


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------

def _method_for(unit: ClauseUnit) -> str:
    """Return "register_column" for register_row units, otherwise "regex"."""
    return "register_column" if unit.unit_kind == UnitKind.REGISTER_ROW else "regex"


def _expand_sheet_range(hint: str) -> list[str]:
    """Parse 'sheet:N' or 'sheet:N-M' → list of string sheet numbers."""
    body = hint[len("sheet:"):]
    if "-" in body:
        parts = body.split("-", 1)
        try:
            lo, hi = int(parts[0]), int(parts[1])
            return [str(n) for n in range(lo, hi + 1)]
        except ValueError:
            return [body]
    return [body]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def resolve_references(
    units: list[ClauseUnit],
    registered_doc_ids: list[str],
    ctx: RunContext,
) -> list[ClauseLink]:
    """Resolve all RefEntry objects attached to *units* into ClauseLink records.

    Parameters
    ----------
    units:
        All ClauseUnit objects for the ingestion run (may span multiple docs).
    registered_doc_ids:
        Doc IDs considered valid targets for references_doc links.
    ctx:
        RunContext — used for counting and issue logging.

    Returns
    -------
    Deduplicated list of ClauseLink records (first occurrence wins).
    """
    # Build indexes
    clause_index = _build_clause_index(units)
    sheet_index = _build_sheet_index(units)
    rule_index = _build_rule_index(units)
    form_index = _build_form_index(units)
    series_index = _build_series_index(units)
    obligation_index = _build_obligation_index(units)
    doc_index = _build_doc_index(units)

    registered_set = set(registered_doc_ids)

    links: list[ClauseLink] = []
    seen: set[tuple[str, str | None, str]] = set()  # (from, to_clause_id, link_type)

    def _add(link: ClauseLink) -> None:
        key = (link.from_clause_id, link.to_clause_id, link.link_type)
        if key not in seen:
            seen.add(key)
            links.append(link)
            ctx.count("links_resolved")

    def _warn(unit: ClauseUnit, ref_type: str, hint: str | None, msg: str) -> None:
        ctx.count("links_unresolved")
        ctx.issue(
            "warning",
            stage="6.1.1_resolve_refs",
            code="unresolved_ref",
            message=msg,
            doc_id=unit.doc_id,
            clause_id=unit.clause_id,
            details={"ref_type": ref_type, "target_hint": hint},
        )

    for unit in units:
        method = _method_for(unit)

        for ref in unit.refs:
            hint: str | None = ref.target_hint
            rtype: str = ref.ref_type

            # ------------------------------------------------------------------
            # references_doc
            # ------------------------------------------------------------------
            if rtype == LinkType.REFERENCES_DOC:
                if hint is None:
                    _warn(unit, rtype, hint, "references_doc with no target_hint")
                    continue
                if hint not in registered_set and hint not in doc_index:
                    _warn(unit, rtype, hint, f"references_doc target not found: {hint!r}")
                    continue
                _add(ClauseLink(
                    from_clause_id=unit.clause_id,
                    to_clause_id=None,
                    to_doc_id=hint,
                    link_type=rtype,
                    method=method,
                    evidence=ref.raw,
                    confidence=1.0,
                ))

            # ------------------------------------------------------------------
            # references_clause
            # ------------------------------------------------------------------
            elif rtype == LinkType.REFERENCES_CLAUSE:
                if hint is None:
                    _warn(unit, rtype, hint, "references_clause with no target_hint")
                    continue
                full_id = hint if ":" in hint else f"{unit.doc_id}:{hint}"
                if full_id not in clause_index:
                    _warn(unit, rtype, hint, f"references_clause target not found: {full_id!r}")
                    continue
                _add(ClauseLink(
                    from_clause_id=unit.clause_id,
                    to_clause_id=full_id,
                    to_doc_id=None,
                    link_type=rtype,
                    method=method,
                    evidence=ref.raw,
                    confidence=1.0,
                ))

            # ------------------------------------------------------------------
            # references_tariff
            # ------------------------------------------------------------------
            elif rtype == LinkType.REFERENCES_TARIFF:
                if hint is None:
                    _warn(unit, rtype, hint, "references_tariff with no target_hint")
                    continue

                if hint.startswith("sheet:"):
                    sheet_nos = _expand_sheet_range(hint)
                    found_any = False
                    for sno in sheet_nos:
                        targets = sheet_index.get(sno, [])
                        for t in targets:
                            found_any = True
                            _add(ClauseLink(
                                from_clause_id=unit.clause_id,
                                to_clause_id=t.clause_id,
                                to_doc_id=None,
                                link_type=rtype,
                                method=method,
                                evidence=ref.raw,
                                confidence=1.0,
                            ))
                    if not found_any:
                        _warn(unit, rtype, hint, f"references_tariff sheet not found: {hint!r}")

                elif hint.startswith("rule:"):
                    rule_no = hint[len("rule:"):]
                    prefix = f"R{rule_no}"
                    targets = rule_index.get(prefix, [])
                    if not targets:
                        _warn(unit, rtype, hint, f"references_tariff rule not found: {hint!r}")
                    for t in targets:
                        _add(ClauseLink(
                            from_clause_id=unit.clause_id,
                            to_clause_id=t.clause_id,
                            to_doc_id=None,
                            link_type=rtype,
                            method=method,
                            evidence=ref.raw,
                            confidence=1.0,
                        ))
                else:
                    _warn(unit, rtype, hint, f"references_tariff unrecognised hint format: {hint!r}")

            # ------------------------------------------------------------------
            # references_form
            # ------------------------------------------------------------------
            elif rtype == LinkType.REFERENCES_FORM:
                if hint is None:
                    _warn(unit, rtype, hint, "references_form with no target_hint")
                    continue
                target = form_index.get(hint)
                if target is None:
                    _warn(unit, rtype, hint, f"references_form target not found: {hint!r}")
                    continue
                _add(ClauseLink(
                    from_clause_id=unit.clause_id,
                    to_clause_id=target.clause_id,
                    to_doc_id=None,
                    link_type=rtype,
                    method=method,
                    evidence=ref.raw,
                    confidence=1.0,
                ))

            # ------------------------------------------------------------------
            # references_record_series
            # ------------------------------------------------------------------
            elif rtype == LinkType.REFERENCES_RECORD_SERIES:
                if hint is None:
                    _warn(unit, rtype, hint, "references_record_series with no target_hint")
                    continue
                target = series_index.get(hint)
                if target is None:
                    _warn(unit, rtype, hint, f"references_record_series target not found: {hint!r}")
                    continue
                _add(ClauseLink(
                    from_clause_id=unit.clause_id,
                    to_clause_id=target.clause_id,
                    to_doc_id=None,
                    link_type=rtype,
                    method=method,
                    evidence=ref.raw,
                    confidence=1.0,
                ))

            # ------------------------------------------------------------------
            # references_obligation
            # ------------------------------------------------------------------
            elif rtype == LinkType.REFERENCES_OBLIGATION:
                if hint is None:
                    _warn(unit, rtype, hint, "references_obligation with no target_hint")
                    continue
                target = obligation_index.get(hint)
                if target is None:
                    _warn(unit, rtype, hint, f"references_obligation target not found: {hint!r}")
                    continue
                _add(ClauseLink(
                    from_clause_id=unit.clause_id,
                    to_clause_id=target.clause_id,
                    to_doc_id=None,
                    link_type=rtype,
                    method=method,
                    evidence=ref.raw,
                    confidence=1.0,
                ))

            # ------------------------------------------------------------------
            # restates (pass-through — no resolution needed)
            # ------------------------------------------------------------------
            elif rtype == LinkType.RESTATES:
                if hint is None:
                    _warn(unit, rtype, hint, "restates with no target_hint")
                    continue
                full_id = hint if ":" in hint else f"{unit.doc_id}:{hint}"
                if full_id not in clause_index:
                    _warn(unit, rtype, hint, f"restates target not found: {full_id!r}")
                    continue
                _add(ClauseLink(
                    from_clause_id=unit.clause_id,
                    to_clause_id=full_id,
                    to_doc_id=None,
                    link_type=rtype,
                    method=method,
                    evidence=ref.raw,
                    confidence=1.0,
                ))

            else:
                _warn(unit, rtype, hint, f"unknown ref_type: {rtype!r}")

    return links
