"""RefEntry dataclass for task 4.1.3 — Reference extraction."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RefEntry:
    """A single reference found inside a ClauseUnit."""

    ref_type: str
    """LinkType value: references_doc | references_clause | references_tariff |
    references_form | references_record_series | references_obligation | restates"""

    raw: str
    """Exact matched string."""

    span_start: int
    """Byte offset of the match start inside unit.text_raw (0 for column-sourced refs)."""

    span_end: int
    """Byte offset of the match end inside unit.text_raw."""

    target_hint: str | None
    """Resolved hint: doc_id, clause_id, form_id, etc., as the pattern supplies it."""
