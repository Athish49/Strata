"""Task 4.2 — DOCX → Markdown extraction (TDD §3.1).

Why DOCX only: measured on a synthetic register document (a 17-page PDF rendered from a
20-heading Markdown source), ``pypdf`` recovered **0** headings, while the DOCX
exposes ``Heading1`` ×2 / ``Heading2`` ×31 as ``w:pStyle`` values.  PDF is
therefore deferred (415) rather than silently producing one-clause documents.

Two public pieces live here:

``DocxExtractor``
    style-driven DOCX → Markdown.  Pure extraction: headings, lists,
    paragraphs and pipe tables, nothing identifier-dependent.

``anchor_clauses``
    a separate, pure pass that injects the ``<!-- clause: DOC:LOCAL -->`` /
    ``<!-- table: DOC:TID -->`` markers that ``parse/markdown_segmenter.py``
    needs in order to emit clauses.  It is deliberately **not** part of
    ``ExtractedDocument.markdown`` — see the note on that field in ``base.py``.
"""
from __future__ import annotations

import io
import re
from importlib.metadata import PackageNotFoundError, version as _pkg_version

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.company_ingest.extract.base import ExtractedDocument
from app.company_ingest.parse.markdown_segmenter import _DOC_ID_ANY as _SEGMENTER_DOC_ID

DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

# ---------------------------------------------------------------------------
# Style mapping (TDD §3.1)
# ---------------------------------------------------------------------------

#: Normalised style key -> heading level.
_HEADING_LEVELS: dict[str, int] = {
    "title": 1,
    "heading1": 1,
    "heading2": 2,
    "heading3": 3,
    "heading4": 4,
    "heading5": 5,
    "heading6": 6,
}

#: Normalised style key -> list bullet/number prefix.
_LIST_PREFIXES: dict[str, str] = {
    "listbullet": "- ",
    "listbullet2": "- ",
    "listbullet3": "- ",
    "listnumber": "1. ",
    "listnumber2": "1. ",
    "listnumber3": "1. ",
}

#: Nesting indent (in spaces) for the deeper list styles.
_LIST_INDENTS: dict[str, str] = {
    "listbullet2": "  ",
    "listbullet3": "    ",
    "listnumber2": "  ",
    "listnumber3": "    ",
}

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: Leading Markdown constructs that must be escaped in body text so the
#: segmenter does not mistake a sentence for a heading, a table row or — worst
#: of all — a code fence, which would swallow the rest of the document.
_ESCAPE_PREFIX_RE = re.compile(r"^(#{1,6}\s|#{1,6}$|`{3,}|~{3,}|\|)")

_WS_RE = re.compile(r"[\s ]+")


def _normalise_style_key(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"[\s\-_]+", "", name).lower()


def _style_keys(paragraph: Paragraph) -> list[str]:
    """Candidate normalised style keys for a paragraph.

    ``python-docx`` exposes the human style name (``"Heading 1"``) while the
    XML carries the style id (``"Heading1"``); documents produced by other
    tools may define only one of them, so both are tried.
    """
    keys: list[str] = []
    style = None
    try:
        style = paragraph.style
    except Exception:  # pragma: no cover - malformed style reference
        style = None
    if style is not None:
        for candidate in (getattr(style, "style_id", None), getattr(style, "name", None)):
            key = _normalise_style_key(candidate)
            if key and key not in keys:
                keys.append(key)
    # Direct pStyle value, in case the style is not defined in styles.xml.
    p_style = paragraph._p.find(f"{_W_NS}pPr/{_W_NS}pStyle")
    if p_style is not None:
        key = _normalise_style_key(p_style.get(f"{_W_NS}val"))
        if key and key not in keys:
            keys.append(key)
    return keys


def _has_numbering(paragraph: Paragraph) -> bool:
    return paragraph._p.find(f"{_W_NS}pPr/{_W_NS}numPr") is not None


def _clean(text: str) -> str:
    """Collapse all whitespace (including the ``\\n`` that cell text carries)."""
    return _WS_RE.sub(" ", text or "").strip()


def _escape_body(text: str) -> str:
    if _ESCAPE_PREFIX_RE.match(text):
        return "\\" + text
    return text


def _cell_markdown(text: str) -> str:
    """Cell text safe to place between pipes.

    A literal ``|`` must become an entity rather than ``\\|``:
    ``markdown_segmenter._parse_table_row`` splits on ``|`` without honouring
    backslash escapes, so an escaped pipe would still add a phantom cell and
    misalign the row against its header.
    """
    return _clean(text).replace("|", "&#124;")


class UnreadableDocumentError(ValueError):
    """Raised when the uploaded bytes are not a parsable DOCX package."""


class DocxExtractor:
    """Style-driven DOCX → Markdown extractor."""

    content_types: frozenset[str] = frozenset({DOCX_CONTENT_TYPE})
    extensions: frozenset[str] = frozenset({".docx"})

    @property
    def method(self) -> str:
        try:
            lib_version = _pkg_version("python-docx")
        except PackageNotFoundError:  # pragma: no cover - installed in all envs
            lib_version = "unknown"
        return f"python-docx/{lib_version}"

    # -- public -------------------------------------------------------------

    def extract(self, raw: bytes, filename: str = "") -> ExtractedDocument:
        try:
            document = docx.Document(io.BytesIO(raw))
        except Exception as exc:  # corrupt upload, or a renamed non-DOCX file
            raise UnreadableDocumentError(
                f"{filename or 'upload'} is not a readable DOCX file: {exc}"
            ) from exc
        blocks: list[str] = []

        # python-docx exposes ``document.paragraphs`` and ``document.tables``
        # as two independent sequences; iterating them separately loses the
        # interleaving and scrambles the document.  Walk the body in document
        # order instead and dispatch on the element tag.
        for child in document.element.body.iterchildren():
            tag = child.tag
            if tag == f"{_W_NS}p":
                block = self._paragraph_markdown(Paragraph(child, document))
                if block:
                    blocks.append(block)
            elif tag == f"{_W_NS}tbl":
                block = self._table_markdown(Table(child, document))
                if block:
                    blocks.append(block)
            # w:sectPr and anything else carries no body text.

        markdown = "\n\n".join(blocks)
        if markdown:
            markdown += "\n"
        return ExtractedDocument(
            markdown=markdown,
            method=self.method,
            page_count=None,  # DOCX does not store pagination
            confidence=1.0,
        )

    # -- internals ----------------------------------------------------------

    def _paragraph_markdown(self, paragraph: Paragraph) -> str:
        text = _clean(paragraph.text)
        if not text:
            return ""

        keys = _style_keys(paragraph)
        for key in keys:
            level = _HEADING_LEVELS.get(key)
            if level is not None:
                return f"{'#' * level} {text}"
        for key in keys:
            prefix = _LIST_PREFIXES.get(key)
            if prefix is not None:
                return f"{_LIST_INDENTS.get(key, '')}{prefix}{text}"
        # ListParagraph is Word's generic list container; it is only a list
        # item when it actually carries numbering.
        if "listparagraph" in keys and _has_numbering(paragraph):
            return f"- {text}"
        return _escape_body(text)

    def _table_markdown(self, table: Table) -> str:
        all_rows: list[list[str]] = []
        for row in table.rows:
            try:
                all_rows.append([_cell_markdown(c.text) for c in row.cells])
            except Exception:  # pragma: no cover - exotic merged layouts
                continue
        if not any(any(cells) for cells in all_rows):
            return ""

        # The first row is the header even when it is blank (dropping it would
        # promote a real data row); blank rows further down are noise.
        rows = [all_rows[0]] + [cells for cells in all_rows[1:] if any(cells)]

        width = max(len(r) for r in rows)
        header = list(rows[0]) + [""] * (width - len(rows[0]))
        # A blank header cell makes the segmenter drop that column from
        # ``row_cells``/``text_raw``, which can leave a clause with no text at
        # all; give it a positional name instead.
        header = [h or f"Column {i + 1}" for i, h in enumerate(header)]

        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join("---" for _ in header) + " |",
        ]
        for row in rows[1:]:
            padded = list(row) + [""] * (width - len(row))
            lines.append("| " + " | ".join(padded) + " |")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Clause anchoring (TDD §3.1, "clause_id without anchors")
# ---------------------------------------------------------------------------

#: The doc-id grammar the segmenter's explicit ``clause:`` / ``table:`` markers
#: accept (``markdown_segmenter._CLAUSE_EXPLICIT_RE`` / ``_TABLE_RE``), which are
#: the only forms :func:`anchor_clauses` emits.
MARKER_DOC_ID_RE = re.compile(r"^" + _SEGMENTER_DOC_ID + r"$")

_HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.*)")
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+){0,3})[.):]?(?:\s|$)")
_FENCE_LINE_RE = re.compile(r"^(`{3,}|~{3,})")


def marker_doc_id_supported(doc_id: str) -> bool:
    """Whether ``doc_id`` can appear in a segmenter marker.

    ``markdown_segmenter``'s explicit markers accept any id token made of
    letters, digits, ``_``, ``.`` and ``-`` (e.g. ``DOC-000123``); an id with
    whitespace or ``:`` cannot be anchored.  Callers should check this rather
    than discover it as a silently empty clause list.
    """
    return bool(MARKER_DOC_ID_RE.match(doc_id))


def anchor_clauses(markdown: str, doc_id: str) -> str:
    """Inject segmenter clause/table markers into extracted Markdown.

    The segmenter opens a clause only at a ``<!-- clause: DOC:LOCAL -->``
    marker and table rows only after a ``<!-- table: DOC:TID -->`` marker;
    headings alone update its heading stack but emit nothing.  Uploaded
    customer documents have no such anchors, so one is synthesized per
    heading: the heading's own section number where it has one (``7``,
    ``7.2``), otherwise a depth/ordinal id (``s1``, ``s1.1``) per TDD §3.1.

    Pure function; ``markdown`` is returned unchanged except for inserted
    marker lines.
    """
    if not marker_doc_id_supported(doc_id):
        raise ValueError(
            f"doc_id {doc_id!r} cannot be anchored: markdown_segmenter's clause "
            "and table markers only accept ids of letters, digits, '_', '.' and '-' "
            "(e.g. 'DOC-000123')"
        )

    out: list[str] = []
    counters: list[int] = []
    table_ordinal = 0
    in_table = False
    in_code = False
    fence = ""
    current_local_id: str | None = None
    continuations: dict[str, int] = {}

    def _continuation_id(base: str) -> str:
        """``7`` → ``7a``, ``7b``, … — still a valid numbered-section local_id."""
        n = continuations.get(base, 0)
        continuations[base] = n + 1
        letters = ""
        while True:
            letters = chr(ord("a") + n % 26) + letters
            n = n // 26 - 1
            if n < 0:
                break
        return f"{base}{letters}"

    after_table = False  # persists across blank lines, unlike ``in_table``

    for line in markdown.splitlines():
        stripped = line.strip()

        if not stripped:
            in_table = False
            out.append(line)
            continue

        fence_m = _FENCE_LINE_RE.match(stripped)
        if fence_m:
            if not in_code:
                in_code, fence = True, fence_m.group(1)[0] * 3
            elif stripped.startswith(fence):
                in_code = False
            in_table = after_table = False
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue

        if stripped.startswith("|"):
            if not in_table:
                table_ordinal += 1
                out.append(f"<!-- table: {doc_id}:T{table_ordinal} -->")
                in_table = True
            after_table = True
            out.append(line)
            continue
        in_table = False

        heading_m = _HEADING_LINE_RE.match(stripped)
        if heading_m:
            after_table = False
            level = len(heading_m.group(1))
            text = heading_m.group(2).strip()
            out.append(line)
            if not text:
                continue
            number_m = _NUMBERED_HEADING_RE.match(text)
            if number_m:
                local_id = number_m.group(1)
            else:
                del counters[level:]
                while len(counters) < level:
                    counters.append(0)
                counters[level - 1] += 1
                local_id = "s" + ".".join(str(c or 1) for c in counters[:level])
            out.append(f"<!-- clause: {doc_id}:{local_id} -->")
            current_local_id = local_id
            continue

        # Plain prose.  A table marker closes the open clause, so the first
        # prose line after a table would otherwise belong to no clause at all
        # and be dropped: re-open the section with a continuation clause
        # (``7`` → ``7a``), which keeps `_compute_parent_id` working.
        if current_local_id is None:
            # Preamble: cover-page / title prose before the first heading.
            after_table = False
            current_local_id = "s0"
            out.append(f"<!-- clause: {doc_id}:s0 -->")
        elif after_table:
            after_table = False
            out.append(
                f"<!-- clause: {doc_id}:{_continuation_id(current_local_id)} -->"
            )

        out.append(line)

    text = "\n".join(out)
    if markdown.endswith("\n"):
        text += "\n"
    return text
