"""Shared data models for the parse and enrich stages."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClauseUnit:
    """One clause or table row extracted from a company document.

    Produced by the segmenters (3.1.1, 3.2.1) and passed through all
    enrichment stages (4.x, 5.x). Each enrichment stage appends to its
    own attribute; no stage modifies another stage's attribute.
    """
    # --- identity ---
    version_id: str           # UUID of the document_versions row
    doc_id: str
    clause_id: str            # full: DOC_ID:LOCAL_ID
    local_id: str             # the part after the colon
    parent_clause_id: str | None

    # --- structure ---
    unit_kind: str            # UnitKind value
    heading_path: list[str]
    section_kind: str         # SectionKind value
    ordinal: int              # position within the document

    # --- position ---
    char_start: int           # byte offset in the body text
    char_end: int
    line_start: int

    # --- content ---
    text_raw: str
    text_norm: str
    text_sha256: str

    # --- table / register fields ---
    sheet_no: str | None = None
    table_id: str | None = None
    row_cells: dict[str, Any] | None = None  # {header: cell}

    # --- enrichment outputs (one attribute per stage, never cross-assigned) ---
    citations: list[Any] = field(default_factory=list)   # set by 4.1.1
    parameters: list[Any] = field(default_factory=list)  # set by 4.1.2 and 5.1.1
    refs: list[Any] = field(default_factory=list)        # set by 4.1.3
    role: str | None = None                               # set by 4.1.4 and 5.1.1
    role_method: str | None = None                        # marker|grammar|llm|heuristic
    assessable: bool | None = None                        # set by 4.1.4 and 5.1.2
    terms: list[Any] = field(default_factory=list)       # set by 4.1.5

    # --- LLM enrichment outputs (set by 5.1.1 / 5.1.2) ---
    normalized_statement: str | None = None
    topic_terms: list[str] = field(default_factory=list)
