"""Deterministic Markdown -> DOCX generator for the synthetic demo corpus (task 9.1 step 3).

Customer uploads are DOCX, so the seeder uploads DOCX. The pre-rendered
``corpus/docs/*/render/*.docx`` files are lossy (and one is a corrupt stub), so the
DOCX for each demo document is generated here from its ``.md`` source instead.

What the generator does, matched to the Markdown dialect the 12 corpus sources
actually use (surveyed construct by construct, see ``tests/synthetic``):

* YAML front matter (``---`` ... ``---`` at the top) is stripped. Front matter in
  any other form (an H1 plus a bold key/value block or a Field/Value table) is
  ordinary body content and is kept.
* Every HTML comment is stripped, including the hand-authored
  ``<!-- clause: ... -->`` / ``<!-- table: ... -->`` anchors and the HTML-comment
  tariff header: the ingest pipeline synthesizes its own anchors from headings.
  A comment line is a block boundary. No other ``<...>`` text is touched
  (``<vendor>``, ``<YYYY>`` are real content).
* ``#``..``######`` -> ``Heading 1``..``Heading 6``.
* Pipe tables -> real Word tables (``Table Grid``); first row is the header row,
  ``|---|`` separator rows are dropped, cell text keeps inline bold/italic/code.
  Consecutive tables are separated by an empty paragraph so Word cannot fuse them.
* ``-``/``*``/``+`` items -> ``List Bullet`` (``List Bullet 2``/``3`` when
  indented), ``1.``/``1)`` items -> ``List Number`` (numbering restarts at each
  new list, honouring the first item's number); ``[ ]``/``[x]`` task boxes become
  ``☐``/``☒``.
* ``>`` blockquotes -> ``Quote`` paragraphs (a bare ``>`` line splits paragraphs).
* Fenced code (including Mermaid) -> one plain monospace paragraph per line.
* ``---``/``***``/``___`` thematic breaks are dropped.
* Inline: ``**bold**``, ``***bold italic***``, ``*italic*``, ```code```, links
  (``[t](u)`` -> ``t (u)``, or just ``u`` when ``t == u``), backslash escapes and
  HTML entities (``&nbsp;``). Underscore emphasis is deliberately NOT parsed: the
  corpus uses none, and it is full of snake_case ids and ``_____`` form blanks.
* Lines inside one paragraph / list item keep their line structure as ``w:br``
  breaks (two-space hard breaks included); the extractor collapses them to spaces.

Determinism: core properties are fixed, and the package is re-zipped with fixed
member timestamps in the original member order, so two builds of the same source
are byte-identical.

Usage (from backend/): ``.venv/bin/python synthetic/make_docx.py OUT_DIR [MD ...]``
(no MD paths = all 12 corpus documents).
"""
from __future__ import annotations

import html
import io
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import docx
import yaml
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

HERE = Path(__file__).resolve().parent
DOCS_DIR = HERE / "corpus" / "docs"

#: Fixed document timestamps (core properties) and zip member timestamp.
FIXED_DATETIME = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
ZIP_DATE_TIME = (2025, 1, 1, 0, 0, 0)
DOCX_AUTHOR = "Rockridge Power & Light Company"
MONO_FONT = "Courier New"

# ---------------------------------------------------------------------------
# Source preprocessing
# ---------------------------------------------------------------------------

_YAML_CLOSE_RE = re.compile(r"^---\s*$", re.MULTILINE)


def split_yaml_front_matter(text: str) -> tuple[dict, str]:
    """Return ``(front_matter_dict, body)``. Only a leading ``---`` YAML block counts."""
    text = text.lstrip("﻿")
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        return {}, text
    close = _YAML_CLOSE_RE.search(text, 4)
    if close is None:
        return {}, text
    try:
        data = yaml.safe_load(text[4:close.start()]) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data, text[close.end():].lstrip("\r\n")


_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def strip_html_comments(body: str) -> str:
    """Remove every ``<!-- ... -->`` outside fenced code, leaving a blank line where
    a whole-line comment stood (so it still acts as a block boundary)."""
    out: list[str] = []
    in_comment = False
    fence: str | None = None
    for line in body.split("\n"):
        if fence is None and not in_comment:
            m = _FENCE_RE.match(line)
            if m:
                fence = m.group(1)[0] * 3
                out.append(line)
                continue
        elif fence is not None:
            if line.strip().startswith(fence):
                fence = None
            out.append(line)
            continue

        buf = []
        i = 0
        had_comment = in_comment
        while i < len(line):
            if in_comment:
                end = line.find("-->", i)
                if end < 0:
                    i = len(line)
                    break
                in_comment = False
                i = end + 3
            else:
                start = line.find("<!--", i)
                if start < 0:
                    buf.append(line[i:])
                    break
                had_comment = True
                buf.append(line[i:start])
                in_comment = True
                i = start + 4
        new = "".join(buf)
        if had_comment and not new.strip():
            new = ""
        out.append(new)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Block model
# ---------------------------------------------------------------------------


@dataclass
class Block:
    kind: str  # heading | para | quote | bullet | number | table | code
    text: str = ""
    level: int = 0  # heading level, or list nesting depth (0-based)
    start: int = 1  # first number of an ordered list item
    new_list: bool = False  # first item of a new ordered list
    rows: list[list[str]] = field(default_factory=list)


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_BULLET_RE = re.compile(r"^(\s*)([-*+])\s+(.*)$")
_NUMBER_RE = re.compile(r"^(\s*)(\d{1,9})[.)]\s+(.*)$")
_QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
_TASK_RE = re.compile(r"^\[([ xX])\]\s+")


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def split_table_row(line: str) -> list[str]:
    """Split a pipe-table row into stripped cells (``\\|`` is a literal pipe)."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells: list[str] = []
    cur: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if ch == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{1,}:?", c) for c in cells if c) and any(cells)


def _list_depth(indent: str) -> int:
    return min(len(indent.replace("\t", "    ")) // 2, 2)


def parse_blocks(body: str) -> list[Block]:
    """Parse the (front-matter- and comment-free) Markdown body into blocks."""
    lines = body.split("\n")
    blocks: list[Block] = []
    para: list[str] = []
    prev_list_kind: str | None = None  # for ordered-list restart detection

    def flush_para() -> None:
        if para:
            blocks.append(Block("para", "\n".join(para)))
            para.clear()

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para()
            # A blank line ends a list only if the next non-blank line is not an item.
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j >= n or not (_BULLET_RE.match(lines[j]) or _NUMBER_RE.match(lines[j])):
                prev_list_kind = None
            i += 1
            continue

        fence_m = _FENCE_RE.match(line)
        if fence_m:
            flush_para()
            prev_list_kind = None
            fence = fence_m.group(1)[0] * 3
            i += 1
            while i < n and not lines[i].strip().startswith(fence):
                if lines[i].strip():
                    blocks.append(Block("code", lines[i].rstrip()))
                i += 1
            i += 1  # closing fence
            continue

        heading_m = _HEADING_RE.match(stripped)
        if heading_m and line.startswith("#"):
            flush_para()
            prev_list_kind = None
            blocks.append(Block("heading", heading_m.group(2), level=len(heading_m.group(1))))
            i += 1
            continue

        if _HR_RE.match(line):
            flush_para()
            prev_list_kind = None
            i += 1
            continue

        if _is_table_line(line):
            flush_para()
            prev_list_kind = None
            rows: list[list[str]] = []
            while i < n and _is_table_line(lines[i]):
                cells = split_table_row(lines[i])
                if not is_separator_row(cells):
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append(Block("table", rows=rows))
            continue

        if _QUOTE_RE.match(line):
            flush_para()
            prev_list_kind = None
            q: list[str] = []
            while i < n and _QUOTE_RE.match(lines[i]):
                inner = _QUOTE_RE.match(lines[i]).group(1)
                if inner.strip():
                    q.append(inner.rstrip())
                elif q:
                    blocks.append(Block("quote", "\n".join(q)))
                    q = []
                i += 1
            if q:
                blocks.append(Block("quote", "\n".join(q)))
            continue

        bullet_m = _BULLET_RE.match(line)
        number_m = None if bullet_m else _NUMBER_RE.match(line)
        if bullet_m or number_m:
            flush_para()
            m = bullet_m or number_m
            depth = _list_depth(m.group(1))
            text = m.group(3)
            if bullet_m:
                task = _TASK_RE.match(text)
                if task:
                    text = ("☒ " if task.group(1).lower() == "x" else "☐ ") + text[task.end():]
                block = Block("bullet", text, level=depth)
            else:
                block = Block("number", text, level=depth, start=int(number_m.group(2)),
                              new_list=depth == 0 and prev_list_kind != "number")
            # ``prev_list_kind`` tracks the top-level list: nested items do not end it.
            if depth == 0:
                prev_list_kind = "bullet" if bullet_m else "number"
            i += 1
            # Lazy continuation lines belong to the item.
            cont: list[str] = [block.text]
            while i < n:
                nxt = lines[i]
                if (not nxt.strip() or _FENCE_RE.match(nxt) or nxt.startswith("#")
                        or _HR_RE.match(nxt) or _is_table_line(nxt) or _QUOTE_RE.match(nxt)
                        or _BULLET_RE.match(nxt) or _NUMBER_RE.match(nxt)):
                    break
                cont.append(nxt.strip())
                i += 1
            block.text = "\n".join(cont)
            blocks.append(block)
            continue

        prev_list_kind = None
        para.append(line.rstrip())
        i += 1

    flush_para()
    return blocks


# ---------------------------------------------------------------------------
# Inline formatting
# ---------------------------------------------------------------------------

_INLINE_RE = re.compile(
    r"(?P<code>`+)(?P<code_body>.+?)(?P=code)"
    r"|\\(?P<esc>[\\`*_{}\[\]()#+\-.!|>~])"
    r"|\[(?P<link_text>[^\]\n]+)\]\((?P<link_url>[^)\s]+)\)"
    r"|\*\*\*(?=\S)(?P<bi>.+?)(?<=\S)\*\*\*"
    r"|\*\*(?=\S)(?P<b>.+?)(?<=\S)\*\*"
    r"|(?<![*\w])\*(?=[^\s*])(?P<i>.+?)(?<=[^\s*])\*(?![*\w])"
)


@dataclass(frozen=True)
class Span:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False


def parse_inline(text: str, bold: bool = False, italic: bool = False) -> list[Span]:
    spans: list[Span] = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            spans.append(Span(html.unescape(text[pos:m.start()]), bold, italic))
        if m.group("code") is not None:
            spans.append(Span(m.group("code_body").strip(), bold, italic, code=True))
        elif m.group("esc") is not None:
            spans.append(Span(m.group("esc"), bold, italic))
        elif m.group("link_text") is not None:
            t, u = m.group("link_text"), m.group("link_url")
            spans.extend(parse_inline(t, bold, italic))
            if t.strip() != u.strip():
                spans.append(Span(f" ({u})", bold, italic))
        elif m.group("bi") is not None:
            spans.extend(parse_inline(m.group("bi"), True, True))
        elif m.group("b") is not None:
            spans.extend(parse_inline(m.group("b"), True, italic))
        elif m.group("i") is not None:
            spans.extend(parse_inline(m.group("i"), bold, True))
        pos = m.end()
    if pos < len(text):
        spans.append(Span(html.unescape(text[pos:]), bold, italic))
    return [s for s in spans if s.text]


def plain_text(md_inline: str) -> str:
    """Inline Markdown -> the visible text (used for titles and headings)."""
    return "".join(s.text for s in parse_inline(md_inline))


def _add_runs(paragraph, text: str) -> None:
    """Add ``text`` (may contain newlines) as formatted runs; newlines -> ``w:br``."""
    lines = text.split("\n")
    for idx, line in enumerate(lines):
        if idx:
            paragraph.add_run().add_break(WD_BREAK.LINE)
        for span in parse_inline(line.strip() if idx else line.rstrip()):
            run = paragraph.add_run(span.text)
            if span.bold:
                run.bold = True
            if span.italic:
                run.italic = True
            if span.code:
                run.font.name = MONO_FONT


# ---------------------------------------------------------------------------
# DOCX assembly
# ---------------------------------------------------------------------------


class _Numbering:
    """Creates a fresh ``w:num`` per ordered list so numbering restarts per list."""

    def __init__(self, document) -> None:
        self._numbering = document.part.numbering_part.element
        style = document.styles["List Number"]
        num_id = style._element.find(qn("w:pPr")).find(qn("w:numPr")).find(qn("w:numId")).get(qn("w:val"))
        self._abstract_id = None
        for num in self._numbering.findall(qn("w:num")):
            if num.get(qn("w:numId")) == num_id:
                self._abstract_id = num.find(qn("w:abstractNumId")).get(qn("w:val"))
        ids = [int(n.get(qn("w:numId"))) for n in self._numbering.findall(qn("w:num"))]
        self._next = max(ids, default=0) + 1

    def new_list(self, start: int) -> str:
        num = OxmlElement("w:num")
        num.set(qn("w:numId"), str(self._next))
        abstract = OxmlElement("w:abstractNumId")
        abstract.set(qn("w:val"), self._abstract_id)
        num.append(abstract)
        override = OxmlElement("w:lvlOverride")
        override.set(qn("w:ilvl"), "0")
        start_el = OxmlElement("w:startOverride")
        start_el.set(qn("w:val"), str(start))
        override.append(start_el)
        num.append(override)
        self._numbering.append(num)
        self._next += 1
        return num.get(qn("w:numId"))


def _set_num_id(paragraph, num_id: str) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    num_pr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    nid = OxmlElement("w:numId")
    nid.set(qn("w:val"), num_id)
    num_pr.append(ilvl)
    num_pr.append(nid)
    p_pr.append(num_pr)


def _add_table(document, rows: list[list[str]]) -> None:
    width = max(len(r) for r in rows)
    table = document.add_table(rows=len(rows), cols=width)
    table.style = document.styles["Table Grid"]
    for r_idx, cells in enumerate(rows):
        row = table.rows[r_idx]
        for c_idx in range(width):
            cell_md = cells[c_idx] if c_idx < len(cells) else ""
            paragraph = row.cells[c_idx].paragraphs[0]
            _add_runs(paragraph, cell_md)
            if r_idx == 0:
                for run in paragraph.runs:
                    run.bold = True
    # Mark the header row as a repeating table header.
    tr_pr = table.rows[0]._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tr_pr.append(tbl_header)


def _title_for(front: dict, blocks: list[Block], md_path: Path) -> str:
    if front.get("title"):
        return str(front["title"]).strip()
    for b in blocks:
        if b.kind == "heading":
            return plain_text(b.text).strip()
    return md_path.stem


def _deterministic_zip(raw: bytes) -> bytes:
    src = zipfile.ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():  # original order: [Content_Types].xml first
            zi = zipfile.ZipInfo(info.filename, date_time=ZIP_DATE_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.create_system = 3
            zi.external_attr = 0o644 << 16
            dst.writestr(zi, src.read(info.filename))
    return out.getvalue()


def build_docx_from_text(md_text: str, *, name: str = "document", title: str | None = None) -> bytes:
    front, body = split_yaml_front_matter(md_text)
    blocks = parse_blocks(strip_html_comments(body))

    document = docx.Document()
    numbering = _Numbering(document)
    current_num: str | None = None
    last_was_table = False

    for block in blocks:
        if block.kind == "table":
            if last_was_table:
                document.add_paragraph("")
            _add_table(document, block.rows)
            last_was_table = True
            continue
        last_was_table = False

        if block.kind == "heading":
            paragraph = document.add_paragraph(style=f"Heading {min(block.level, 6)}")
        elif block.kind == "para":
            paragraph = document.add_paragraph()
        elif block.kind == "quote":
            paragraph = document.add_paragraph(style="Quote")
        elif block.kind == "bullet":
            style = "List Bullet" if block.level == 0 else f"List Bullet {block.level + 1}"
            paragraph = document.add_paragraph(style=style)
        elif block.kind == "number":
            style = "List Number" if block.level == 0 else f"List Number {block.level + 1}"
            paragraph = document.add_paragraph(style=style)
            if block.level == 0:
                if block.new_list or current_num is None:
                    current_num = numbering.new_list(block.start)
                _set_num_id(paragraph, current_num)
        elif block.kind == "code":
            paragraph = document.add_paragraph()
            run = paragraph.add_run(block.text)
            run.font.name = MONO_FONT
            run.font.size = Pt(9)
            continue
        else:  # pragma: no cover - parse_blocks emits only the kinds above
            raise ValueError(block.kind)
        _add_runs(paragraph, block.text)

    cp = document.core_properties
    cp.author = DOCX_AUTHOR
    cp.last_modified_by = DOCX_AUTHOR
    cp.title = title or _title_for(front, blocks, Path(name))
    cp.subject = ""
    cp.keywords = ""
    cp.comments = ""
    cp.category = ""
    cp.revision = 1
    cp.created = FIXED_DATETIME.replace(tzinfo=None)
    cp.modified = FIXED_DATETIME.replace(tzinfo=None)
    cp.last_printed = FIXED_DATETIME.replace(tzinfo=None)

    buf = io.BytesIO()
    document.save(buf)
    return _deterministic_zip(buf.getvalue())


def build_docx(md_path: str | Path, *, title: str | None = None) -> bytes:
    """Build the DOCX bytes for one corpus ``.md`` source. Deterministic.

    ``title`` sets the core-properties title; by default it is the YAML ``title``,
    else the first heading (for RPL-TAR-GRR-012 that is the all-caps company
    banner, so the seeder should pass the document register title).
    """
    md_path = Path(md_path)
    return build_docx_from_text(md_path.read_text(encoding="utf-8"), name=md_path.stem, title=title)


def corpus_md_paths() -> list[Path]:
    return sorted(DOCS_DIR.glob("*/RPL-*_v*.md"))


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.split("Usage")[1].strip(), file=sys.stderr)
        return 2
    out_dir = Path(argv[0])
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [Path(p) for p in argv[1:]] or corpus_md_paths()
    for p in paths:
        target = out_dir / (p.stem + ".docx")
        target.write_bytes(build_docx(p))
        print(f"{target}  ({target.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
