"""Task 2.2.1 — Front-matter parser for company corpus documents.

Supports three styles:
  1. YAML front matter (8 docs) — delimited by leading and closing '---' lines
  2. HTML comment header (1 doc, RPL-TAR-GRR-012) — consecutive HTML comment lines
  3. Marker-based (3 docs) — '<!-- DOC_ID:section -->' marker with bold key-values or a table
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------

@dataclass
class FrontMatter:
    doc_id: str | None = None
    title: str | None = None
    version: str | None = None
    status: str | None = None
    effective_date: str | None = None
    approved_date: str | None = None
    law_as_of: str | None = None
    next_review: str | None = None
    classification: str | None = None
    regulatory_basis: list[str] = field(default_factory=list)
    supersedes: str | None = None
    owner_id: str | None = None
    reviewer_id: str | None = None
    approver_id: str | None = None   # None for two-signature docs
    vertical: str | None = None
    review_cycle: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RE_PERSON_ID = re.compile(r'\b(P\d+)\b')


def _first_person_id(text: str | None) -> str | None:
    """Return the first Pxx person ID found in *text*, or None."""
    if not text:
        return None
    m = _RE_PERSON_ID.search(text)
    return m.group(1) if m else None


def _str_or_none(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _to_str_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v).strip() for v in val if v is not None]
    s = str(val).strip()
    return [s] if s else []


# ---------------------------------------------------------------------------
# Style 1 — YAML front matter
# ---------------------------------------------------------------------------

_RE_YAML_OPEN = re.compile(r'^---\s*\n')
# Closing --- on its own line (may have trailing spaces)
_RE_YAML_CLOSE = re.compile(r'\n---\s*\n')


def _parse_yaml_fm(md_text: str) -> tuple[FrontMatter, str, int] | None:
    """Parse YAML front matter delimited by --- lines.

    Returns (FrontMatter, body_text, body_char_offset) or None if not this style.
    """
    if not md_text.startswith('---\n') and not md_text.startswith('---\r\n'):
        return None

    # Find closing ---
    close_m = _RE_YAML_CLOSE.search(md_text, 3)
    if close_m is None:
        return None

    yaml_text = md_text[4:close_m.start()]  # skip opening '---\n'
    body_offset = close_m.end()
    body_text = md_text[body_offset:]

    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        data = {}

    # Extract owner/reviewer/approver — may be dict {id: PXX, ...} or null or str
    def _extract_id_from_field(val: Any) -> str | None:
        if val is None:
            return None
        if isinstance(val, dict):
            return _str_or_none(val.get('id')) or _first_person_id(str(val))
        return _first_person_id(str(val))

    fm = FrontMatter(
        doc_id=_str_or_none(data.get('doc_id')),
        title=_str_or_none(data.get('title')),
        version=_str_or_none(data.get('version')),
        status=_str_or_none(data.get('status')),
        effective_date=_str_or_none(data.get('effective_date')),
        approved_date=_str_or_none(data.get('approved_date')),
        law_as_of=_str_or_none(data.get('law_as_of')),
        next_review=_str_or_none(data.get('next_review')),
        classification=_str_or_none(data.get('classification')),
        regulatory_basis=_to_str_list(data.get('regulatory_basis')),
        supersedes=_str_or_none(data.get('supersedes')),
        owner_id=_extract_id_from_field(data.get('owner')),
        reviewer_id=_extract_id_from_field(data.get('reviewer')),
        approver_id=_extract_id_from_field(data.get('approver')),
        vertical=_str_or_none(data.get('vertical')),
        review_cycle=_str_or_none(data.get('review_cycle')),
    )
    return fm, body_text, body_offset


# ---------------------------------------------------------------------------
# Style 2 — HTML comment header (tariff style)
# ---------------------------------------------------------------------------

# All front-matter lines are HTML comments at start of file
_RE_HTML_COMMENT_LINE = re.compile(r'^<!--.*?-->\s*\n?', re.DOTALL)
_RE_COMMENT_BLOCK_LINE = re.compile(r'^<!--[^\n]*-->\s*$', re.MULTILINE)


def _parse_html_comment_fm(md_text: str) -> tuple[FrontMatter, str, int] | None:
    """Parse HTML-comment-only header at start of file (tariff style).

    Returns (FrontMatter, body_text, body_char_offset) or None if not this style.
    """
    if not md_text.startswith('<!--'):
        return None

    # Collect consecutive HTML comment lines at the top
    pos = 0
    comment_lines: list[str] = []
    for line in md_text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith('<!--') and stripped.endswith('-->'):
            comment_lines.append(stripped)
            pos += len(line)
        else:
            break

    if not comment_lines:
        return None

    # Must have at least the header line starting with <!-- RPL-
    if not any(re.match(r'<!-- RPL-', l) for l in comment_lines):
        return None

    # Skip blank lines after comments to find body start
    body_offset = pos
    while body_offset < len(md_text) and md_text[body_offset] in (' ', '\t', '\n', '\r'):
        body_offset += 1
    body_text = md_text[body_offset:]

    # Parse fields from comment lines
    all_text = ' '.join(comment_lines)

    # Extract roles line: <!-- Owner: P11 (Aisha Thompson) | Reviewer: P10 (Robert Haskins) | Approver: P03 (Jonathan Pierce) -->
    owner_id = reviewer_id = approver_id = None
    for line in comment_lines:
        if 'Owner:' in line:
            # Owner: PXX or Owner: PXX (Name)
            m_owner = re.search(r'Owner:\s*(P\d+)', line)
            if m_owner:
                owner_id = m_owner.group(1)
            m_reviewer = re.search(r'Reviewer:\s*(P\d+)', line)
            if m_reviewer:
                reviewer_id = m_reviewer.group(1)
            m_approver = re.search(r'Approver:\s*(P\d+)', line)
            if m_approver:
                approver_id = m_approver.group(1)
            break

    # Law-as-of
    law_as_of = None
    m_law = re.search(r'Law-as-of:\s*([\d]{4}-[\d]{2}-[\d]{2})', all_text)
    if m_law:
        law_as_of = m_law.group(1)

    # Effective date: "Effective: YYYY-MM-DD"
    effective_date = None
    m_eff = re.search(r'Effective:\s*([\d]{4}-[\d]{2}-[\d]{2})', all_text)
    if m_eff:
        effective_date = m_eff.group(1)

    # doc_id from first comment line: <!-- RPL-TAR-GRR-012 | ...
    doc_id = None
    m_docid = re.match(r'<!-- (RPL-[A-Z0-9-]+)', comment_lines[0])
    if m_docid:
        doc_id = m_docid.group(1)

    fm = FrontMatter(
        doc_id=doc_id,
        title=None,   # Not in header comments; register fallback
        version=None, # Not in header comments; register fallback
        status=None,
        effective_date=effective_date,
        approved_date=None,
        law_as_of=law_as_of,
        next_review=None,
        classification=None,
        regulatory_basis=[],
        supersedes=None,
        owner_id=owner_id,
        reviewer_id=reviewer_id,
        approver_id=approver_id,
        vertical=None,
        review_cycle=None,
    )
    return fm, body_text, body_offset


# ---------------------------------------------------------------------------
# Style 3 — Marker-based (<!-- DOC_ID:section --> with bold key-values or table)
# ---------------------------------------------------------------------------

# Matches <!-- RPL-XXXX-YYYY-ZZZ:something --> style markers
_RE_FM_MARKER = re.compile(
    r'<!--\s*(RPL-[A-Z0-9-]+):(meta|front-matter|\d+\.\d+|\d+\.0|1\.0)\s*-->'
)


def _parse_marker_fm(md_text: str, doc_id: str) -> tuple[FrontMatter, str, int] | None:
    """Parse marker-based front matter (CMP-REG-001, LEG-RRS-001, REG-CAL-2025 styles).

    Returns (FrontMatter, body_text, body_char_offset) or None if not this style.
    """
    m = _RE_FM_MARKER.search(md_text)
    if m is None:
        # Also try explicit doc_id match for any section marker
        m = re.search(
            r'<!--\s*' + re.escape(doc_id) + r':(meta|front-matter|1\.0)\s*-->',
            md_text,
        )
    if m is None:
        return None

    marker_end = m.end()

    # Find the text after the marker and before the next '---' separator or section heading
    # The metadata block ends at the first '---\n' or at a blank line followed by ##
    after_marker = md_text[marker_end:]

    # Determine if this is a table-style (REG-CAL-2025) or key-value style
    # Table style has a '| Field | Value |' pattern
    is_table_style = bool(re.search(r'^\|[^\n]+\|[^\n]+\|\s*$', after_marker, re.MULTILINE))

    if is_table_style:
        kv = _parse_table_metadata(after_marker)
    else:
        kv = _parse_bold_kv_metadata(after_marker)

    # Find body_offset: position after the metadata section
    # Look for first '---' line after the marker
    sep_m = re.search(r'\n---\s*\n', md_text[marker_end:])
    if sep_m:
        body_offset = marker_end + sep_m.end()
    else:
        # Fall back to end of metadata block
        body_offset = marker_end

    body_text = md_text[body_offset:]

    def _kv_person_id(keys: list[str]) -> str | None:
        for k in keys:
            v = kv.get(k)
            if v:
                pid = _first_person_id(v)
                if pid:
                    return pid
        return None

    def _kv_val(keys: list[str]) -> str | None:
        for k in keys:
            v = kv.get(k)
            if v:
                return v.strip()
        return None

    # Normalise keys to lowercase for lookup
    kv_lower = {k.lower(): v for k, v in kv.items()}

    def _lkv(keys: list[str]) -> str | None:
        for k in keys:
            v = kv_lower.get(k.lower())
            if v:
                return v.strip()
        return None

    def _lkv_pid(keys: list[str]) -> str | None:
        for k in keys:
            v = kv_lower.get(k.lower())
            if v:
                pid = _first_person_id(v)
                if pid:
                    return pid
        return None

    fm = FrontMatter(
        doc_id=_lkv(['document id', 'doc id', 'document_id', 'doc_id']) or doc_id,
        title=_lkv(['title']),
        version=_lkv(['version']),
        status=_lkv(['status']),
        effective_date=_lkv(['effective', 'effective date', 'effective_date']),
        approved_date=_lkv(['approved', 'approved date', 'approved_date']),
        law_as_of=_lkv([
            'law as of date', 'law as-of', 'law as of', 'law_as_of', 'law-as-of',
        ]),
        next_review=_lkv(['next review', 'next_review', 'next review date']),
        classification=_lkv(['classification']),
        regulatory_basis=[],  # Not typically in marker style
        supersedes=_lkv(['supersedes']),
        owner_id=_lkv_pid(['owner', 'prepared by', 'prepared_by']),
        reviewer_id=_lkv_pid(['reviewer']),
        approver_id=_lkv_pid(['approver']),
        vertical=_lkv(['vertical']),
        review_cycle=_lkv(['review cycle', 'review_cycle']),
    )
    return fm, body_text, body_offset


def _parse_bold_kv_metadata(text: str) -> dict[str, str]:
    """Extract **Key:** value pairs from markdown text.

    Handles both:
    - Single key per line: **Key:** value
    - Multiple keys per line separated by |: **Key1:** val1 | **Key2:** val2
    """
    kv: dict[str, str] = {}
    # Pattern: **Key:** value (key may have spaces, value goes to end of segment)
    _RE_KV = re.compile(r'\*\*([^*]+)\*\*\s*[:\|]?\s*([^*\n|]+?)(?=\*\*|$|\||\n)', re.MULTILINE)
    # Split text into segments by | within lines, then by newlines
    for match in _RE_KV.finditer(text):
        key = match.group(1).strip().rstrip(':')
        val = match.group(2).strip()
        if key and val:
            kv[key] = val
    return kv


def _parse_table_metadata(text: str) -> dict[str, str]:
    """Extract key-value pairs from a markdown table with Field | Value columns."""
    kv: dict[str, str] = {}
    # Match table rows: | **Key** | value |
    _RE_TABLE_ROW = re.compile(r'^\|\s*\*\*([^*|]+)\*\*\s*\|\s*([^|]+?)\s*\|', re.MULTILINE)
    for match in _RE_TABLE_ROW.finditer(text):
        key = match.group(1).strip()
        val = match.group(2).strip()
        if key and val and not key.startswith('-') and val != 'Value':
            kv[key] = val
    return kv


# ---------------------------------------------------------------------------
# Public split_front_matter()
# ---------------------------------------------------------------------------

def split_front_matter(md_text: str, doc_id: str) -> tuple[FrontMatter, str, int]:
    """Parse front matter from a markdown document.

    Detects and handles three front-matter styles:
      1. YAML (--- delimited)
      2. HTML comment header (tariff)
      3. Marker-based (<!-- DOC_ID:section -->)

    Returns:
        (FrontMatter, body_text, body_char_offset)
        body_char_offset: character offset in md_text where body starts.
    """
    # Style 1: YAML
    result = _parse_yaml_fm(md_text)
    if result is not None:
        return result

    # Style 2: HTML comment header
    result = _parse_html_comment_fm(md_text)
    if result is not None:
        return result

    # Style 3: Marker-based
    result = _parse_marker_fm(md_text, doc_id)
    if result is not None:
        return result

    # Fallback: no recognised front matter
    fm = FrontMatter(doc_id=doc_id)
    return fm, md_text, 0
