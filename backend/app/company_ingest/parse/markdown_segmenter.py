"""Task 3.1.1 — Markdown clause segmenter for P1 company documents.

Parses a Markdown body (after front-matter has been stripped) into ClauseUnit
objects using a linear scan. Handles two clause-marker formats, table markers,
heading-stack tracking, and section-kind detection.
"""
from __future__ import annotations

import re
import warnings
from typing import Optional

from app.company_ingest.constants import SectionKind, UnitKind
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.parse.text import normalize, sha256_text
from app.company_ingest.run_context import RunContext

# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------

# Matches both:
#   <!-- clause: DOC_ID:LOCAL_ID -->
#   <!-- DOC_ID:LOCAL_ID -->
# Skips any marker that contains '|' (e.g. front-matter comment blocks).
_CLAUSE_RE = re.compile(
    r"<!--\s*(?:clause:\s*)?([A-Z]+-[A-Z]+-[A-Z]+-\d+|[A-Z]+-[A-Z]+-\d+)"
    r":([^\s|>]+)\s*-->"
)

# <!-- table: DOC_ID:TID -->
_TABLE_RE = re.compile(
    r"<!--\s*table:\s*([A-Z]+-[A-Z]+-[A-Z]+-\d+|[A-Z]+-[A-Z]+-\d+)"
    r":([^\s|>]+)\s*-->"
)

# Heading: one or more '#' followed by space and text
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")

# Pipe-table row: starts with '|'
_TABLE_ROW_RE = re.compile(r"^\|")

# Separator row (all cells are dashes/colons): | --- | :---: | ... |
_TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|")

# Fenced code block delimiter
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")


# ---------------------------------------------------------------------------
# ID classification
# ---------------------------------------------------------------------------

def _classify_local_id(local_id: str) -> tuple[str, bool]:
    """Return (unit_kind, is_nonmatching).

    ``is_nonmatching`` is True when the ID didn't match any known grammar and
    we fell back to ``section``.
    """
    # App-A.F1 → form_field
    if re.match(r"^App-[A-Z]\.F\d+$", local_id):
        return UnitKind.FORM_FIELD, False
    # App-A.1 or App-A.something → appendix
    if re.match(r"^App-[A-Z]\.", local_id):
        return UnitKind.APPENDIX, False
    # T1-2 → table_row
    if re.match(r"^T\d+-\d+$", local_id):
        return UnitKind.TABLE_ROW, False
    # R01.D01 → tariff_subrule (letter-based sub-id)
    if re.match(r"^R\d+\.[A-Z]\d+$", local_id):
        return UnitKind.TARIFF_SUBRULE, False
    # R02.1 → tariff_subrule (numeric sub-id)
    if re.match(r"^R\d+\.\d+$", local_id):
        return UnitKind.TARIFF_SUBRULE, False
    # S01.1 → section (tariff sheet sections)
    if re.match(r"^S\d+\.\d+$", local_id):
        return UnitKind.SECTION, False
    # S50.IDX → other
    if re.match(r"^S\d+\.[A-Z]+$", local_id):
        return UnitKind.OTHER, False
    # OBL-001-002 → register_row
    if re.match(r"^OBL-\d+-\d+$", local_id):
        return UnitKind.REGISTER_ROW, False
    # EVT-001-002 → register_row
    if re.match(r"^EVT-\d+-\d+$", local_id):
        return UnitKind.REGISTER_ROW, False
    # RRS-ABC-001 → register_row
    if re.match(r"^RRS-[A-Z]+-\d+$", local_id):
        return UnitKind.REGISTER_ROW, False
    # Numbered sections: 1, 1.1, 7.2.3, 7.2.3a
    if re.match(r"^\d+(\.\d+){0,3}[a-z]?$", local_id):
        return UnitKind.SECTION, False
    # Non-matching → section with warning
    return UnitKind.SECTION, True


# ---------------------------------------------------------------------------
# Section-kind detection
# ---------------------------------------------------------------------------

_SK_KEYWORDS: list[tuple[str, str]] = [
    ("purpose", SectionKind.PURPOSE),
    ("scope", SectionKind.SCOPE),
    ("definition", SectionKind.DEFINITIONS),
    ("regulatory basis", SectionKind.REGULATORY_BASIS),
    ("regulatory framework", SectionKind.REGULATORY_BASIS),
    ("role", SectionKind.ROLES),
    ("responsibilit", SectionKind.ROLES),
    ("procedure", SectionKind.PROCEDURE),
    ("process", SectionKind.PROCEDURE),
    ("record", SectionKind.RECORDS),
    ("training", SectionKind.TRAINING),
    ("related document", SectionKind.RELATED_DOCS),
    ("cross-reference", SectionKind.RELATED_DOCS),
    ("revision history", SectionKind.REVISION_HISTORY),
    ("approval", SectionKind.APPROVAL),
    ("appendix", SectionKind.APPENDIX),
    ("front-matter", SectionKind.FRONT_MATTER),
]


def _detect_section_kind(heading_path: list[str]) -> str:
    """Match heading_path[-1] (and [-2] if available) against keyword list."""
    candidates = []
    if heading_path:
        candidates.append(heading_path[-1].lower())
    if len(heading_path) >= 2:
        candidates.append(heading_path[-2].lower())

    for candidate in candidates:
        for keyword, sk in _SK_KEYWORDS:
            if keyword in candidate:
                return sk
    return SectionKind.OTHER


# ---------------------------------------------------------------------------
# Parent-clause ID computation
# ---------------------------------------------------------------------------

def _compute_parent_id(
    local_id: str,
    doc_id: str,
    seen_ids: set[str],
) -> str | None:
    """Derive the parent clause ID from the local_id structure.

    Tries candidates from most specific to least and returns the first one
    that exists in ``seen_ids``.  Falls back to None.
    """
    # Numbered section: 7.2.3[a] → try 7.2, then 7
    base = local_id
    if base and base[-1].isalpha() and re.match(r"^\d", base):
        base = base[:-1]  # strip trailing lowercase letter
    if re.match(r"^\d+(\.\d+)+$", base):
        parts = base.split(".")
        for n in range(len(parts) - 1, 0, -1):
            candidate = ".".join(parts[:n])
            full = f"{doc_id}:{candidate}"
            if full in seen_ids:
                return full
        return None

    # App-A.F1 → App-A
    m = re.match(r"^(App-[A-Z])\.", local_id)
    if m:
        full = f"{doc_id}:{m.group(1)}"
        return full if full in seen_ids else None

    # R01.D01 or R02.1 → R01, R02
    m = re.match(r"^(R\d+)\.", local_id)
    if m:
        full = f"{doc_id}:{m.group(1)}"
        return full if full in seen_ids else None

    # S01.1 → no defined structural parent
    return None


# ---------------------------------------------------------------------------
# Pipe-table parsing helpers
# ---------------------------------------------------------------------------

def _parse_table_row(line: str) -> list[str]:
    """Split a pipe-table row into stripped cell values."""
    parts = line.split("|")
    # Remove leading/trailing empty strings from split on '|'
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [p.strip() for p in parts]


def _is_separator_row(cells: list[str]) -> bool:
    """Return True if every cell matches the --- / :---: separator pattern."""
    return bool(cells) and all(re.match(r"^[-:]+$", c) for c in cells if c)


# ---------------------------------------------------------------------------
# Core segmenter
# ---------------------------------------------------------------------------

def segment(
    version_id: str,
    doc_id: str,
    body_text: str,
    body_offset: int,
    *,
    _ctx: Optional[RunContext] = None,
) -> list[ClauseUnit]:
    """Parse a P1 Markdown body into ClauseUnit objects.

    Parameters
    ----------
    version_id:
        UUID of the document_versions row.
    doc_id:
        The document identifier (e.g. ``RPL-CS-PRO-004``).
    body_text:
        The Markdown body *after* front-matter has been stripped.
    body_offset:
        Character offset of ``body_text`` within the original file.  Used to
        set ``char_start`` / ``char_end`` so that
        ``full_file_text[unit.char_start:unit.char_end] == unit.text_raw``.
    _ctx:
        Optional :class:`RunContext`.  When supplied, non-matching IDs and
        unclaimed-text counts are logged there.

    Returns
    -------
    list[ClauseUnit]
        One unit per clause marker *and* one per table data row, in document
        order.
    """
    lines = body_text.splitlines(keepends=True)

    # Pre-compute the character start of each line within body_text.
    line_starts: list[int] = []
    pos = 0
    for line in lines:
        line_starts.append(pos)
        pos += len(line)
    # Sentinel: position just past end of body_text
    line_starts.append(pos)

    result: list[ClauseUnit] = []
    seen_clause_ids: set[str] = set()
    ordinal = 0

    # --- mutable state ---
    heading_stack: list[tuple[int, str]] = []  # (level, text)
    current_clause_local_id: str | None = None
    current_clause_doc_id: str | None = None   # from the marker's DOC_ID group
    current_clause_content_start: int | None = None   # char offset in body_text
    current_clause_content_line: int | None = None    # line index in body_text
    current_clause_heading_path: list[str] = []

    # Unclaimed text: chars between a heading and the first clause in that section
    unclaimed_text_chars: int = 0
    section_clause_seen: bool = True  # suppress unclaimed tracking before first heading

    in_code_block: bool = False
    code_fence: str = ""

    def _finalize_clause(end_char: int) -> None:
        """Emit a ClauseUnit for the currently open clause ending at *end_char*."""
        nonlocal ordinal
        if current_clause_local_id is None or current_clause_content_start is None:
            return

        text_raw = body_text[current_clause_content_start:end_char]
        full_id = f"{current_clause_doc_id}:{current_clause_local_id}"
        # Deduplicate: if this ID was already used, append an ordinal suffix.
        if full_id in seen_clause_ids:
            suffix = 2
            candidate = f"{full_id}_r{suffix}"
            while candidate in seen_clause_ids:
                suffix += 1
                candidate = f"{full_id}_r{suffix}"
            if _ctx is not None:
                _ctx.issue(
                    "warning",
                    "3.1.1",
                    "duplicate_clause_id",
                    f"Duplicate clause_id {full_id!r} renaming to {candidate!r}",
                    doc_id=doc_id,
                    clause_id=full_id,
                )
            full_id = candidate
        hp = list(current_clause_heading_path)
        sk = _detect_section_kind(hp)
        unit_kind, is_nonmatch = _classify_local_id(current_clause_local_id)

        if is_nonmatch and _ctx is not None:
            _ctx.issue(
                "warning",
                "3.1.1",
                "unknown_local_id",
                f"Unrecognised local_id pattern: {current_clause_local_id!r} "
                f"in {full_id}; defaulting to unit_kind=section",
                doc_id=doc_id,
                clause_id=full_id,
            )

        parent_id = _compute_parent_id(
            current_clause_local_id, doc_id, seen_clause_ids
        )

        row_cells: dict | None = None
        if "```mermaid" in text_raw:
            row_cells = {"has_mermaid": True}

        unit = ClauseUnit(
            version_id=version_id,
            doc_id=doc_id,
            clause_id=full_id,
            local_id=current_clause_local_id,
            parent_clause_id=parent_id,
            unit_kind=unit_kind,
            heading_path=hp,
            section_kind=sk,
            ordinal=ordinal,
            char_start=body_offset + current_clause_content_start,
            char_end=body_offset + end_char,
            line_start=current_clause_content_line or 0,
            text_raw=text_raw,
            text_norm=normalize(text_raw),
            text_sha256=sha256_text(text_raw),
            row_cells=row_cells,
        )
        result.append(unit)
        seen_clause_ids.add(full_id)
        ordinal += 1

    def _end_current_clause(end_char: int) -> None:
        """Finalize and reset the current open clause."""
        nonlocal current_clause_local_id, current_clause_doc_id
        nonlocal current_clause_content_start, current_clause_content_line
        nonlocal current_clause_heading_path
        _finalize_clause(end_char)
        current_clause_local_id = None
        current_clause_doc_id = None
        current_clause_content_start = None
        current_clause_content_line = None
        current_clause_heading_path = []

    def _start_clause(
        local_id: str, marker_doc_id: str, content_char: int, content_line: int
    ) -> None:
        """Open a new clause whose content starts at *content_char*."""
        nonlocal current_clause_local_id, current_clause_doc_id
        nonlocal current_clause_content_start, current_clause_content_line
        nonlocal current_clause_heading_path, section_clause_seen
        current_clause_local_id = local_id
        current_clause_doc_id = marker_doc_id
        current_clause_content_start = content_char
        current_clause_content_line = content_line
        current_clause_heading_path = [t for _, t in heading_stack]
        section_clause_seen = True

    # ------------------------------------------------------------------
    # Linear scan
    # ------------------------------------------------------------------
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\n").rstrip("\r")
        line_char_start = line_starts[i]
        line_char_end = line_starts[i + 1]  # end (exclusive) of this line

        # --- code-block toggling ---
        fence_m = _FENCE_RE.match(stripped)
        if fence_m:
            fence_str = fence_m.group(1)
            if not in_code_block:
                in_code_block = True
                code_fence = fence_str[0] * len(fence_str)  # normalise
            elif stripped.startswith(code_fence):
                in_code_block = False
            i += 1
            continue

        if in_code_block:
            i += 1
            continue

        # --- heading ---
        heading_m = _HEADING_RE.match(stripped)
        if heading_m:
            level = len(heading_m.group(1))
            text = heading_m.group(2).strip()

            # Determine whether this heading ends the current clause.
            # Current deepest heading level (0 if stack empty).
            current_depth = heading_stack[-1][0] if heading_stack else 0
            if current_clause_local_id is not None and level <= current_depth:
                # If the open clause has no non-blank content yet, absorb this
                # heading into it rather than emitting an empty clause.
                clause_so_far = body_text[current_clause_content_start:line_char_start]
                if not clause_so_far.strip():
                    # Absorb: update heading stack and clause heading path, keep clause open.
                    heading_stack[:] = [(l, t) for l, t in heading_stack if l < level]
                    heading_stack.append((level, text))
                    current_clause_heading_path = [t for _, t in heading_stack]
                    # section_clause_seen stays True — we're still inside the open clause.
                    i += 1
                    continue
                else:
                    _end_current_clause(line_char_start)

            # A new heading always starts a fresh section (clause not yet seen).
            section_clause_seen = False

            # Update heading_stack: pop all headings at the same or deeper level
            heading_stack[:] = [(l, t) for l, t in heading_stack if l < level]
            heading_stack.append((level, text))

            i += 1
            continue

        # --- table marker ---
        table_m = _TABLE_RE.search(stripped)
        if table_m:
            # End current clause at the start of the table-marker line
            _end_current_clause(line_char_start)

            table_doc_id = table_m.group(1)
            tid = table_m.group(2)
            table_heading_path = [t for _, t in heading_stack]

            # Parse the pipe table starting at the next non-blank line.
            # Some documents place a blank line between the table marker and the
            # first pipe row; skipping those blank lines avoids counting them and
            # the table data as unclaimed text.
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1  # skip blank lines before the table
            headers: list[str] | None = None
            row_ordinal = 0

            while j < len(lines):
                tline = lines[j].rstrip("\n").rstrip("\r")
                if not _TABLE_ROW_RE.match(tline):
                    break  # end of table

                cells = _parse_table_row(tline)
                if headers is None:
                    if not _is_separator_row(cells):
                        headers = cells
                    j += 1
                    continue

                if _is_separator_row(cells):
                    j += 1
                    continue

                # Data row
                if headers and cells:
                    id_cell = cells[0] if cells else ""
                    row_local_id = id_cell
                    row_clause_id = f"{table_doc_id}:{row_local_id}"
                    # Deduplicate: table first-cells may not be unique across tables.
                    if row_clause_id in seen_clause_ids:
                        suffix = 2
                        candidate = f"{row_clause_id}_{tid}_{suffix}"
                        while candidate in seen_clause_ids:
                            suffix += 1
                            candidate = f"{row_clause_id}_{tid}_{suffix}"
                        if _ctx is not None:
                            _ctx.issue(
                                "warning",
                                "3.1.1",
                                "duplicate_clause_id",
                                f"Duplicate table row clause_id {row_clause_id!r} "
                                f"renaming to {candidate!r}",
                                doc_id=doc_id,
                                clause_id=row_clause_id,
                            )
                        row_clause_id = candidate

                    row_cells_dict = {
                        h: c
                        for h, c in zip(headers, cells)
                        if h and c
                    }
                    text_raw_parts = [
                        f"{h}: {c}"
                        for h, c in zip(headers, cells)
                        if h and c
                    ]
                    text_raw = "\n".join(text_raw_parts)
                    text_row_char_start = line_starts[j]
                    text_row_char_end = line_starts[j + 1]

                    parent_id = _compute_parent_id(
                        row_local_id, doc_id, seen_clause_ids
                    )

                    sk = _detect_section_kind(table_heading_path)

                    unit = ClauseUnit(
                        version_id=version_id,
                        doc_id=doc_id,
                        clause_id=row_clause_id,
                        local_id=row_local_id,
                        parent_clause_id=parent_id,
                        unit_kind=UnitKind.TABLE_ROW,
                        heading_path=list(table_heading_path),
                        section_kind=sk,
                        ordinal=ordinal,
                        char_start=body_offset + text_row_char_start,
                        char_end=body_offset + text_row_char_end,
                        line_start=j,
                        text_raw=text_raw,
                        text_norm=normalize(text_raw),
                        text_sha256=sha256_text(text_raw),
                        table_id=tid,
                        row_cells=row_cells_dict,
                    )
                    result.append(unit)
                    seen_clause_ids.add(row_clause_id)
                    ordinal += 1
                    row_ordinal += 1

                j += 1

            i = j
            continue

        # --- clause marker ---
        clause_m = _CLAUSE_RE.search(stripped)
        if clause_m:
            # End current clause at the start of this marker line
            _end_current_clause(line_char_start)

            marker_doc_id = clause_m.group(1)
            local_id = clause_m.group(2)
            content_start = line_char_end   # content starts after marker line
            content_line = i + 1
            _start_clause(local_id, marker_doc_id, content_start, content_line)
            i += 1
            continue

        # --- plain content line ---
        if current_clause_local_id is None and not section_clause_seen:
            unclaimed_text_chars += line_char_end - line_char_start

        i += 1

    # End of body — close any open clause
    _end_current_clause(line_starts[-1])

    if _ctx is not None:
        _ctx.count("unclaimed_text_chars", unclaimed_text_chars)

    return result


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def segment_with_ctx(
    version_id: str,
    doc_id: str,
    body_text: str,
    body_offset: int,
    ctx: RunContext,
) -> list[ClauseUnit]:
    """Calls :func:`segment` and logs unclaimed-text count as a metric."""
    return segment(version_id, doc_id, body_text, body_offset, _ctx=ctx)
