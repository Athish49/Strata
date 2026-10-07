"""Task 4.1.2 — ParameterEntry dataclass produced by the regex extraction pass."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ParameterEntry:
    """One numeric/unit parameter extracted from a ClauseUnit.

    Produced by enrich_parameters (4.1.2) and later enriched by the LLM pass
    (5.1.1) and verification pass (5.1.2).  Fields set in later stages are
    documented with the stage that owns them.
    """

    # --- classification ---
    kind: str               # ParameterKind value (e.g. "period", "amount")
    unit: Optional[str]     # canonical unit from UNIT_MAP, or None for bare numbers

    # --- value ---
    value_text: str         # exact substring from text_raw (may include unit phrase)
    value_num: Optional[float]  # parsed numeric value; None if parse failed
    value_source: Optional[str]  # None here; set by 8.1.2

    # --- qualifiers ---
    qualifier: Optional[str]  # Qualifier value, or None
    day_type: str             # DayType value (e.g. "business", "n_a")

    # --- provenance ---
    span_start: int           # char offset into text_raw (start, inclusive)
    span_end: int             # char offset into text_raw (end, exclusive)
    method: str               # always "regex" for this stage
    verified: bool            # True when find_verbatim confirms the offset
