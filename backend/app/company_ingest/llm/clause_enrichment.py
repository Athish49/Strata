"""Task 5.1.1 — Builder functions for per-clause LLM enrichment."""
from __future__ import annotations

import re
from typing import Any

from app.company_ingest.parse.models import ClauseUnit

# Rough estimate: 4 characters per token.
_CHARS_PER_TOKEN = 4

# Regex patterns for list item lines.
_BULLET_RE = re.compile(r"^\s*[-*•]\s+")
_ORDERED_RE = re.compile(r"^\s*\d+\.\s+")


def should_enrich(unit: ClauseUnit) -> bool:
    """Return True if this unit should be sent to the LLM.

    Skips units that are already classified as boilerplate or have no text.
    """
    if unit.role == "boilerplate":
        return False
    if not unit.text_raw.strip():
        return False
    return True


def build_clause_user_message(
    unit: ClauseUnit,
    parent_text: str | None,
    citations_found: list[Any],
    params_found: list[Any],
) -> str:
    """Build the user message for a single clause enrichment LLM call.

    Args:
        unit: The clause unit to enrich.
        parent_text: First 400 chars of the parent clause text, or None.
        citations_found: List of CitationEntry objects or dicts from stage 4.1.1.
        params_found: List of ParameterEntry objects or dicts from stage 4.1.2.

    Returns:
        Structured plain-text user message.
    """
    lines: list[str] = []

    lines.append(f"CLAUSE_ID: {unit.clause_id}")
    lines.append(f"LOCAL_ID: {unit.local_id}")
    lines.append(f"DOC_ID: {unit.doc_id}")
    lines.append(f"UNIT_KIND: {unit.unit_kind}")

    if unit.heading_path:
        heading_str = " > ".join(unit.heading_path)
        lines.append(f"HEADING_PATH: {heading_str}")
    else:
        lines.append("HEADING_PATH: (none)")

    if unit.role is not None:
        lines.append(f"PROVISIONAL_ROLE: {unit.role}")

    lines.append("")

    if parent_text is not None:
        truncated = parent_text[:400]
        lines.append("PARENT_CLAUSE (first 400 chars):")
        lines.append(truncated)
        lines.append("")

    lines.append("CLAUSE_TEXT:")
    lines.append(unit.text_raw)
    lines.append("")

    if citations_found:
        lines.append("CITATIONS_FOUND (deterministic, from stage 4.1.1):")
        for i, cit in enumerate(citations_found):
            if hasattr(cit, "citation_raw"):
                lines.append(f"  [{i}] {cit.citation_raw}")
            elif isinstance(cit, dict):
                lines.append(f"  [{i}] {cit.get('citation_raw', str(cit))}")
            else:
                lines.append(f"  [{i}] {cit}")
        lines.append("")

    if params_found:
        lines.append("PARAMETERS_FOUND (deterministic, from stage 4.1.2):")
        for i, param in enumerate(params_found):
            if hasattr(param, "kind") and hasattr(param, "value_text"):
                lines.append(f"  [{i}] kind={param.kind} value={param.value_text!r}")
            elif isinstance(param, dict):
                kind = param.get("kind", "?")
                value = param.get("value_text", str(param))
                lines.append(f"  [{i}] kind={kind} value={value!r}")
            else:
                lines.append(f"  [{i}] {param}")
        lines.append("")

    lines.append(
        "Return a JSON object matching the ClauseEnrichment schema. "
        "Do not include any prose outside the JSON."
    )

    return "\n".join(lines)


def build_doc_class_user_message(
    doc_id: str,
    doc_title: str,
    body_preview: str,
    heading_outline: list[str],
) -> str:
    """Build the user message for document classification.

    Args:
        doc_id: The document identifier.
        doc_title: The document title.
        body_preview: First 2000 characters of the document body.
        heading_outline: List of section headings in document order.

    Returns:
        Structured plain-text user message.
    """
    lines: list[str] = []

    lines.append(f"DOC_ID: {doc_id}")
    lines.append(f"DOC_TITLE: {doc_title}")
    lines.append("")

    lines.append("BODY_PREVIEW (first 2000 chars):")
    lines.append(body_preview[:2000])
    lines.append("")

    if heading_outline:
        lines.append("HEADING_OUTLINE:")
        for heading in heading_outline:
            lines.append(f"  - {heading}")
        lines.append("")

    lines.append(
        "Classify this document into one of the defined doc_class values. "
        "Return a JSON object matching the DocClassification schema."
    )

    return "\n".join(lines)


def split_if_long(unit: ClauseUnit, max_tokens: int = 1500) -> list[ClauseUnit]:
    """Split a long clause unit at top-level list items.

    If unit.text_raw exceeds max_tokens (estimated at 4 chars/token), attempt
    to split at bullet or ordered-list lines. Returns [unit] if no split is
    needed or if fewer than 2 splits result.

    Child units get:
        clause_id  = original clause_id + "#" + str(i)  (1-based)
        local_id   = original local_id  + "#" + str(i)
        parent_clause_id = original clause_id
        text_raw   = the list item's text
    """
    max_chars = max_tokens * _CHARS_PER_TOKEN

    if len(unit.text_raw) <= max_chars:
        return [unit]

    # Find list item boundaries in the text.
    lines = unit.text_raw.splitlines(keepends=True)
    item_indices: list[int] = []

    for idx, line in enumerate(lines):
        if _BULLET_RE.match(line) or _ORDERED_RE.match(line):
            item_indices.append(idx)

    if len(item_indices) < 2:
        return [unit]

    # Build segments: each segment starts at an item_index and ends before the next.
    segments: list[str] = []
    for seg_i, start in enumerate(item_indices):
        end = item_indices[seg_i + 1] if seg_i + 1 < len(item_indices) else len(lines)
        segment_text = "".join(lines[start:end]).strip()
        if segment_text:
            segments.append(segment_text)

    if len(segments) < 2:
        return [unit]

    # Create child ClauseUnit objects.
    children: list[ClauseUnit] = []
    for i, seg_text in enumerate(segments, start=1):
        import hashlib
        child = ClauseUnit(
            version_id=unit.version_id,
            doc_id=unit.doc_id,
            clause_id=unit.clause_id + f"#{i}",
            local_id=unit.local_id + f"#{i}",
            parent_clause_id=unit.clause_id,
            unit_kind=unit.unit_kind,
            heading_path=unit.heading_path,
            section_kind=unit.section_kind,
            ordinal=unit.ordinal,
            char_start=unit.char_start,
            char_end=unit.char_end,
            line_start=unit.line_start,
            text_raw=seg_text,
            text_norm=seg_text.lower(),
            text_sha256=hashlib.sha256(seg_text.encode()).hexdigest(),
            sheet_no=unit.sheet_no,
            table_id=unit.table_id,
            row_cells=unit.row_cells,
        )
        children.append(child)

    return children
