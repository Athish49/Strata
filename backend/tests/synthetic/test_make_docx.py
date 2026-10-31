"""Fidelity tests for ``synthetic/make_docx.py`` (task 9.1 step 3).

Each of the 12 demo ``.md`` sources is built to DOCX, run through the production
``DocxExtractor``, and compared with the ``.md`` using measurements that do NOT
reuse the generator's own parser (independent tokenizer / heading / table scans).

Word retention is a MULTISET measure: ``sum(min(md[w], docx[w])) / sum(md[w])``
over lower-cased ``\\w+`` tokens of the ``.md`` body after removing the YAML
front matter and every HTML comment and unescaping HTML entities.

The suite skips cleanly when ``backend/synthetic/`` is absent (it is deletable,
architecture.md section 10). Run with ``-s`` (or read the ``test_zz_report``
output, which bypasses capture) for the per-document fidelity table.
"""
from __future__ import annotations

import html
import itertools
import re
import zipfile
import io
from collections import Counter
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
SYNTHETIC = BACKEND / "synthetic"
if not (SYNTHETIC / "make_docx.py").is_file():
    pytest.skip("backend/synthetic/ is absent", allow_module_level=True)

import docx  # noqa: E402

from app.company_ingest.extract.docx import DocxExtractor, anchor_clauses  # noqa: E402
from app.company_ingest.hashing import canonicalize, content_hash  # noqa: E402
from app.company_ingest.parse.front_matter import split_front_matter  # noqa: E402
from app.company_ingest.parse.markdown_segmenter import segment_with_ctx  # noqa: E402
from app.company_ingest.run_context import RunContext  # noqa: E402
from synthetic import make_docx  # noqa: E402

pytestmark = pytest.mark.corpus

MD_PATHS = sorted((SYNTHETIC / "corpus" / "docs").glob("*/RPL-*_v*.md"))
UPLOAD_DOC_ID = "DOC-000123"
VERSION_ID = "00000000-0000-0000-0000-000000000091"
MIN_WORD_RETENTION = 0.98
REPORT: dict[str, dict] = {}


def _doc_id(md_path: Path) -> str:
    return md_path.stem.split("_v", 1)[0]


# ---------------------------------------------------------------------------
# Independent measurements of the .md source
# ---------------------------------------------------------------------------

_YAML_RE = re.compile(r"\A---\r?\n.*?\r?\n---[ \t]*\r?\n", re.DOTALL)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_WORD_RE = re.compile(r"\w+")


def _md_body(md_text: str) -> str:
    """Front matter and comments removed; a whole-line comment leaves a blank line."""
    return _COMMENT_RE.sub("", _YAML_RE.sub("", md_text, count=1))


def _words(text: str) -> Counter:
    return Counter(w.lower() for w in _WORD_RE.findall(html.unescape(text)))


def _norm(text: str) -> str:
    text = html.unescape(text).replace("\\", "")
    text = re.sub(r"[*`]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _scan(markdown: str) -> tuple[list[str], list[list[str]]]:
    """(heading texts, tables as lists of normalised first cells) outside fences."""
    headings: list[str] = []
    tables: list[list[str]] = []
    in_fence = False
    in_table = False
    for line in markdown.split("\n"):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            in_table = False
            continue
        if in_fence:
            continue
        s = line.strip()
        if s.startswith("|"):
            if not in_table:
                tables.append([])
                in_table = True
            parts = s.strip("|").split("|")
            cells = [p.strip() for p in parts]
            if cells and all(re.fullmatch(r":?-+:?", c) for c in cells if c) and any(cells):
                continue  # separator row
            if tables[-1] and not any(cells):
                continue  # wholly blank spacer row (the extractor drops these); a blank header is kept
            tables[-1].append(_norm(cells[0]) if cells else "")
            continue
        in_table = False
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            headings.append(_norm(m.group(2)))
    return headings, tables


def _md_clauses(md_text: str, doc_id: str) -> list:
    _fm, body, offset = split_front_matter(md_text, doc_id)
    return segment_with_ctx(VERSION_ID, doc_id, body, offset, RunContext())


def _docx_clauses(extracted: str) -> list:
    anchored = anchor_clauses(extracted, UPLOAD_DOC_ID)
    return segment_with_ctx(VERSION_ID, UPLOAD_DOC_ID, anchored, 0, RunContext())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built() -> dict[str, tuple[bytes, str]]:
    """doc_id -> (docx bytes, extracted markdown)."""
    out = {}
    for p in MD_PATHS:
        raw = make_docx.build_docx(p)
        out[_doc_id(p)] = (raw, DocxExtractor().extract(raw, p.stem + ".docx").markdown)
    return out


def test_twelve_sources():
    assert len(MD_PATHS) == 12, [p.name for p in MD_PATHS]


@pytest.mark.parametrize("md_path", MD_PATHS, ids=_doc_id)
def test_fidelity(md_path: Path, built):
    doc_id = _doc_id(md_path)
    raw, extracted = built[doc_id]
    md_text = md_path.read_text(encoding="utf-8")
    body = _md_body(md_text)

    # valid, non-empty package
    assert zipfile.ZipFile(io.BytesIO(raw)).testzip() is None
    docx.Document(io.BytesIO(raw))
    assert extracted.strip()
    assert len(canonicalize(extracted)) >= 50  # empty-extraction guard (TDD 3.2)

    md_headings, md_tables = _scan(body)
    dx_headings, dx_tables = _scan(extracted)

    # every .md heading appears as a heading (as a multiset, and nothing extra)
    missing_h = Counter(md_headings) - Counter(dx_headings)
    assert not missing_h, f"headings lost: {list(missing_h)[:10]}"
    assert len(dx_headings) == len(md_headings)

    # same number of tables; every row's first-cell text present
    assert len(dx_tables) == len(md_tables)
    dx_first = Counter(itertools.chain.from_iterable(dx_tables))
    md_first = Counter(c for c in itertools.chain.from_iterable(md_tables) if c)
    missing_c = md_first - dx_first
    assert not missing_c, f"first cells lost: {list(missing_c)[:10]}"
    md_rows = sum(len(t) for t in md_tables)
    dx_rows = sum(len(t) for t in dx_tables)
    assert dx_rows == md_rows

    # word retention
    md_words = _words(body)
    dx_words = _words(extracted)
    kept = sum((md_words & dx_words).values())
    total = sum(md_words.values())
    retention = kept / total
    lost = (md_words - dx_words).most_common(8)

    # clause counts (informational, bounded)
    md_units = _md_clauses(md_text, doc_id)
    dx_units = _docx_clauses(extracted)
    REPORT[doc_id] = {
        "headings": (len(md_headings), len(dx_headings)),
        "tables": (len(md_tables), len(dx_tables)),
        "rows": (md_rows, dx_rows),
        "words": (total, kept, retention),
        "lost": lost,
        "clauses": (len(md_units), len(dx_units)),
        "kinds_md": Counter(u.unit_kind for u in md_units),
        "kinds_dx": Counter(u.unit_kind for u in dx_units),
        "bytes": len(raw),
    }
    assert retention >= MIN_WORD_RETENTION, f"{doc_id}: retention {retention:.4f}, lost {lost}"
    assert md_units, "the .md itself segments to zero clauses"
    assert dx_units, "the DOCX segments to zero clauses"


#: Documents whose clause ratio is outside [0.5, 2.0] for a reason that is not a
#: rendering loss. RPL-REG-CAL-2025's .md has NO ``<!-- table: -->`` anchors: its
#: 104 calendar table rows sit inside 7 hand-anchored section clauses (36 clauses
#: in all), while the uploaded DOCX path anchors every table, giving 104
#: ``table_row`` + 21 section clauses = 125 (3.47x). All 115 rows, 16 headings and
#: 100% of the words survive, so this is finer granularity, not loss. Strict xfail:
#: if the ratio ever comes back inside the band, this entry must be removed.
CLAUSE_RATIO_EXCEPTIONS = {
    "RPL-REG-CAL-2025": "md folds 104 unanchored table rows into 7 section clauses; docx anchors each row",
}


@pytest.mark.parametrize(
    "md_path",
    [
        pytest.param(p, marks=pytest.mark.xfail(strict=True, reason=CLAUSE_RATIO_EXCEPTIONS[_doc_id(p)]))
        if _doc_id(p) in CLAUSE_RATIO_EXCEPTIONS else p
        for p in MD_PATHS
    ],
    ids=_doc_id,
)
def test_clause_ratio(md_path: Path, built):
    """Informational counts, bounded: docx clauses within 50%..200% of the .md's own."""
    doc_id = _doc_id(md_path)
    md_n = len(_md_clauses(md_path.read_text(encoding="utf-8"), doc_id))
    dx_n = len(_docx_clauses(built[doc_id][1]))
    ratio = dx_n / md_n
    assert 0.5 <= ratio <= 2.0, f"{doc_id}: docx {dx_n} vs md {md_n} clauses ({ratio:.2f}x)"


def test_hand_authored_anchors_are_stripped(built):
    for doc_id, (_raw, extracted) in built.items():
        assert "<!--" not in extracted, doc_id
        assert not re.search(r"\b(?:clause|table):\s*\S+:\S+\s*-->", extracted), doc_id


def test_deterministic_bytes():
    for p in MD_PATHS:
        a = make_docx.build_docx(p)
        b = make_docx.build_docx(p)
        assert a == b, p.name
        zf = zipfile.ZipFile(io.BytesIO(a))
        names = zf.namelist()
        assert names[0] == "[Content_Types].xml"
        # Fixed timestamps on every member, so builds in different seconds also match.
        assert {i.date_time for i in zf.infolist()} == {make_docx.ZIP_DATE_TIME}, p.name
        cp = docx.Document(io.BytesIO(a)).core_properties
        assert cp.author == make_docx.DOCX_AUTHOR
        assert cp.created == make_docx.FIXED_DATETIME
        assert cp.modified == make_docx.FIXED_DATETIME
        assert cp.title


def test_titles_from_front_matter(built):
    titles = {
        _doc_id(p): docx.Document(io.BytesIO(built[_doc_id(p)][0])).core_properties.title
        for p in MD_PATHS
    }
    assert titles["RPL-CS-PRO-004"] == "Disconnection, Reconnection & Winter Protection Procedure"
    assert titles["RPL-LEG-RRS-001"] == "Records Retention Schedule"  # first H1 (no YAML)
    assert all(titles.values())
    explicit = make_docx.build_docx(next(p for p in MD_PATHS if _doc_id(p) == "RPL-TAR-GRR-012"), title="Tariff X")
    assert docx.Document(io.BytesIO(explicit)).core_properties.title == "Tariff X"


def test_content_hashes_pairwise_distinct(built):
    hashes = {doc_id: content_hash(md) for doc_id, (_raw, md) in built.items()}
    assert len(set(hashes.values())) == len(hashes) == 12


def test_empty_source_is_guarded():
    """A source with no body text yields an extraction the 422 guard would reject."""
    raw = make_docx.build_docx_from_text("---\ntitle: x\n---\n<!-- clause: X:1 -->\n\n---\n")
    md = DocxExtractor().extract(raw).markdown
    assert len(canonicalize(md)) < 50


def test_inline_and_block_constructs():
    src = (
        "---\ntitle: T\n---\n"
        "<!-- clause: RPL-X-Y-001:1 -->\n"
        "# Top\n\n## 7.2 Records <!-- inline -->\n\n"
        "Para **bold** and *ital* and `code_x` and [https://a.b/](https://a.b/) a&nbsp;b.\n"
        "second line \\*literal\\* <vendor> ____ snake_case_id\n\n"
        "- [ ] task\n- item\n   - nested\n\n"
        "3. three\n4. four\n\n"
        "> **Note:** quoted\n>\n> second\n\n"
        "| | |\n|---|---|\n| **K** | v1 |\n| K2 | a, b |\n\n"
        "<!-- table: RPL-X-Y-001:T2 -->\n| H |\n|---|\n| r |\n\n"
        "```mermaid\nA --> B\n```\n\n---\n\ntail\n"
    )
    raw = make_docx.build_docx_from_text(src)
    d = docx.Document(io.BytesIO(raw))
    styles = [p.style.name for p in d.paragraphs if p.text.strip()]
    texts = [p.text for p in d.paragraphs if p.text.strip()]
    assert styles[:2] == ["Heading 1", "Heading 2"]
    assert texts[1] == "7.2 Records"
    para = d.paragraphs[2]
    assert [r.text for r in para.runs if r.bold] == ["bold"]
    assert [r.text for r in para.runs if r.italic] == ["ital"]
    assert "code_x" in para.text and "https://a.b/" in para.text and "(https" not in para.text
    assert "*literal*" in para.text and "<vendor>" in para.text and "____ snake_case_id" in para.text
    assert "a\xa0b" in para.text
    assert ("List Bullet", "☐ task") in zip(styles, texts)
    assert ("List Bullet 2", "nested") in zip(styles, texts)
    assert ("List Number", "three") in zip(styles, texts)
    assert ("Quote", "Note: quoted") in zip(styles, texts)
    assert ("Quote", "second") in zip(styles, texts)
    assert "A --> B" in texts and "tail" in texts
    assert len(d.tables) == 2
    t = d.tables[0]
    assert [c.text for c in t.rows[1].cells] == ["K", "v1"]
    assert t.rows[2].cells[1].text == "a, b"
    assert all(not ("<!--" in x) for x in texts)


def test_zz_report(capsys):
    """Prints the per-document fidelity table (runs last in this module)."""
    if not REPORT:
        pytest.skip("fidelity tests did not run")
    lines = [
        "",
        f"{'doc':<18} {'head md/dx':>10} {'tbl md/dx':>9} {'rows md/dx':>11} "
        f"{'words':>6} {'kept %':>7} {'clauses md/dx':>13} {'ratio':>5}",
    ]
    for doc_id in sorted(REPORT):
        r = REPORT[doc_id]
        total, _kept, ret = r["words"]
        md_c, dx_c = r["clauses"]
        lines.append(
            f"{doc_id:<18} {r['headings'][0]:>4}/{r['headings'][1]:<5} {r['tables'][0]:>4}/{r['tables'][1]:<4} "
            f"{r['rows'][0]:>5}/{r['rows'][1]:<5} {total:>6} {ret * 100:>7.2f} {md_c:>6}/{dx_c:<6} {dx_c / md_c:>5.2f}"
        )
    md_sum = sum(r["clauses"][0] for r in REPORT.values())
    dx_sum = sum(r["clauses"][1] for r in REPORT.values())
    lines.append(f"{'TOTAL':<18} {'':>10} {'':>9} {'':>11} {'':>6} {'':>7} {md_sum:>6}/{dx_sum:<6} {dx_sum / md_sum:>5.2f}")
    kinds_md = sum((r["kinds_md"] for r in REPORT.values()), Counter())
    kinds_dx = sum((r["kinds_dx"] for r in REPORT.values()), Counter())
    lines.append(f"md kinds total {dict(kinds_md)}; docx kinds total {dict(kinds_dx)}")
    lines.append("")
    for doc_id in sorted(REPORT):
        r = REPORT[doc_id]
        lines.append(f"{doc_id}: md kinds {dict(r['kinds_md'])} | docx kinds {dict(r['kinds_dx'])} | lost {r['lost']}")
    with capsys.disabled():
        print("\n".join(lines))
