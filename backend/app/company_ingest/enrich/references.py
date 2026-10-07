"""Task 4.1.3 — Reference extraction.

Pure in-memory enrichment pass: scans each ClauseUnit's text_raw (and any
reference_list columns for P2 register rows) for cross-document references
and appends RefEntry objects to unit.refs.  Nothing is resolved here —
resolution happens in task 6.1.1.
"""
from __future__ import annotations

import re
from typing import Sequence

from app.company_ingest.constants import LinkType
from app.company_ingest.enrich.ref_entry import RefEntry
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext

# ---------------------------------------------------------------------------
# Module-level compiled patterns (doc-id pattern built at call time)
# ---------------------------------------------------------------------------

# 2. Clause references
_RE_CLAUSE_EXPLICIT = re.compile(
    r"\b([A-Z]{3}-[A-Z]{2,4}-[A-Z]{2,4}-\d+):([A-Z0-9][A-Za-z0-9._-]*)"
)
_RE_CLAUSE_SECTION = re.compile(r"§(\d+(?:\.\d+)*)")

# 3. Tariff references
_RE_TARIFF_SHEET = re.compile(
    r"Sheets?\s+(?:No\.?|Nos\.?|Numbers?)?\s*(\d+(?:[–—\-]\d+)?)",
    re.IGNORECASE,
)
_RE_TARIFF_RULE = re.compile(r"\bRule\s+(\d+)\b")

# 4. Form references  (optional company-code prefix: RPL-DCC-F-042)
_RE_FORM = re.compile(r"\b((?:[A-Z]{2,4}-)?[A-Z]{2,4}-F-\d{3}(?:-[A-Z]{2})?)\b")

# 5. Record series references
_RE_RECORD_SERIES = re.compile(r"\b(RRS-[A-Z]{2,4}-\d{3})\b")

# 6. Obligation references
_RE_OBLIGATION = re.compile(r"\b(OBL-\d{4}-\d{4})\b|\b(OBL-\d{4})\b")

# Helpers for P2 column inference
_RE_DOC_ID_SHAPE = re.compile(r"^[A-Z]{2,5}-[A-Z]{2,5}-[A-Z]{2,5}-\d+$")
_RE_DOC_CLAUSE_SHAPE = re.compile(
    r"^([A-Z]{3}-[A-Z]{2,4}-[A-Z]{2,4}-\d+):([A-Z0-9][A-Za-z0-9._-]*)$"
)
_RE_FORM_SHAPE = re.compile(r"^(?:[A-Z]{2,4}-)?[A-Z]{2,4}-F-\d{3}(?:-[A-Z]{2})?$")
_RE_RULE_SHAPE = re.compile(r"^Rule\s+\d+$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_doc_id_pattern(registered_doc_ids: Sequence[str]) -> re.Pattern[str] | None:
    """Return a compiled regex that matches any registered doc_id, or None."""
    if not registered_doc_ids:
        return None
    alternation = "|".join(
        re.escape(d)
        for d in sorted(registered_doc_ids, key=len, reverse=True)
    )
    return re.compile(r"\b(?:" + alternation + r")\b")


def _infer_ref_type_from_part(
    part: str,
    doc_id_re: re.Pattern[str] | None,
) -> tuple[str, str | None]:
    """Infer ref_type and target_hint from a single cell token."""
    if doc_id_re and doc_id_re.fullmatch(part.strip()):
        return LinkType.REFERENCES_DOC, part.strip()
    if _RE_DOC_CLAUSE_SHAPE.match(part.strip()):
        return LinkType.REFERENCES_CLAUSE, part.strip()
    if part.strip().startswith("RRS-"):
        return LinkType.REFERENCES_RECORD_SERIES, part.strip()
    if part.strip().startswith("OBL-"):
        return LinkType.REFERENCES_OBLIGATION, part.strip()
    if _RE_FORM_SHAPE.match(part.strip()):
        return LinkType.REFERENCES_FORM, part.strip()
    if _RE_RULE_SHAPE.match(part.strip()):
        m = re.search(r"\d+", part)
        return LinkType.REFERENCES_TARIFF, f"rule:{m.group()}" if m else None
    # Fallback: treat as a doc reference by name
    return LinkType.REFERENCES_DOC, part.strip()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def enrich_references(
    units: list[ClauseUnit],
    registered_doc_ids: list[str],
    ctx: RunContext,
) -> None:
    """Append RefEntry objects to each unit's refs list.

    This is an in-place, pure-memory enrichment pass.  No I/O is performed.

    Parameters
    ----------
    units:
        ClauseUnit list produced by the segmenters.
    registered_doc_ids:
        Known company document IDs used to build the doc-id regex.
    ctx:
        RunContext for stats counting.
    """
    doc_id_re = _build_doc_id_pattern(registered_doc_ids)

    for unit in units:
        seen: set[tuple[str, str | None]] = set()
        new_refs: list[RefEntry] = []

        def _add(entry: RefEntry) -> None:
            key = (entry.ref_type, entry.target_hint)
            if key not in seen:
                seen.add(key)
                new_refs.append(entry)

        text = unit.text_raw

        # ------------------------------------------------------------------
        # 1. Document ID references (must appear in registered_doc_ids)
        # ------------------------------------------------------------------
        if doc_id_re:
            for m in doc_id_re.finditer(text):
                _add(RefEntry(
                    ref_type=LinkType.REFERENCES_DOC,
                    raw=m.group(),
                    span_start=m.start(),
                    span_end=m.end(),
                    target_hint=m.group(),
                ))

        # ------------------------------------------------------------------
        # 2. Clause references
        # ------------------------------------------------------------------
        for m in _RE_CLAUSE_EXPLICIT.finditer(text):
            doc_part = m.group(1)
            local_part = m.group(2)
            target = f"{doc_part}:{local_part}"
            _add(RefEntry(
                ref_type=LinkType.REFERENCES_CLAUSE,
                raw=m.group(),
                span_start=m.start(),
                span_end=m.end(),
                target_hint=target,
            ))

        for m in _RE_CLAUSE_SECTION.finditer(text):
            target = f"{unit.doc_id}:{m.group(1)}"
            _add(RefEntry(
                ref_type=LinkType.REFERENCES_CLAUSE,
                raw=m.group(),
                span_start=m.start(),
                span_end=m.end(),
                target_hint=target,
            ))

        # ------------------------------------------------------------------
        # 3. Tariff references
        # ------------------------------------------------------------------
        for m in _RE_TARIFF_SHEET.finditer(text):
            n = m.group(1)
            _add(RefEntry(
                ref_type=LinkType.REFERENCES_TARIFF,
                raw=m.group(),
                span_start=m.start(),
                span_end=m.end(),
                target_hint=f"sheet:{n}",
            ))

        for m in _RE_TARIFF_RULE.finditer(text):
            _add(RefEntry(
                ref_type=LinkType.REFERENCES_TARIFF,
                raw=m.group(),
                span_start=m.start(),
                span_end=m.end(),
                target_hint=f"rule:{m.group(1)}",
            ))

        # ------------------------------------------------------------------
        # 4. Form references
        # ------------------------------------------------------------------
        for m in _RE_FORM.finditer(text):
            _add(RefEntry(
                ref_type=LinkType.REFERENCES_FORM,
                raw=m.group(),
                span_start=m.start(),
                span_end=m.end(),
                target_hint=m.group(1),
            ))

        # ------------------------------------------------------------------
        # 5. Record series references
        # ------------------------------------------------------------------
        for m in _RE_RECORD_SERIES.finditer(text):
            _add(RefEntry(
                ref_type=LinkType.REFERENCES_RECORD_SERIES,
                raw=m.group(),
                span_start=m.start(),
                span_end=m.end(),
                target_hint=m.group(1),
            ))

        # ------------------------------------------------------------------
        # 6. Obligation references
        # ------------------------------------------------------------------
        for m in _RE_OBLIGATION.finditer(text):
            matched = m.group(1) or m.group(2)
            _add(RefEntry(
                ref_type=LinkType.REFERENCES_OBLIGATION,
                raw=m.group(),
                span_start=m.start(),
                span_end=m.end(),
                target_hint=matched,
            ))

        # ------------------------------------------------------------------
        # 7. P2 register_row: reference_list columns
        # ------------------------------------------------------------------
        if unit.row_cells:
            for col_name, cell_value in unit.row_cells.items():
                # Only process columns whose provisional role is reference_list
                if not isinstance(col_name, str):
                    continue
                if "reference_list" not in str(col_name).lower():
                    continue
                if not cell_value:
                    continue
                cell_str = str(cell_value)
                parts = re.split(r"[;,]", cell_str)
                cell_len = len(cell_str)
                for raw_part in parts:
                    part = raw_part.strip()
                    if not part:
                        continue
                    ref_type, target_hint = _infer_ref_type_from_part(
                        part, doc_id_re
                    )
                    _add(RefEntry(
                        ref_type=ref_type,
                        raw=part,
                        span_start=0,
                        span_end=cell_len,
                        target_hint=target_hint,
                    ))

        # ------------------------------------------------------------------
        # Commit and count
        # ------------------------------------------------------------------
        unit.refs.extend(new_refs)
        ctx.count("references_found", len(new_refs))
