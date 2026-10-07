"""
render_RPL-CS-PRO-004.py
Deterministic rendering script for RPL-CS-PRO-004 v5.1
Produces:
  render/RPL-CS-PRO-004_v5.1.docx
  render/RPL-CS-PRO-004_v5.1.pdf

Requirements: python-docx, subprocess (LibreOffice headless or reportlab fallback)
Python: /Users/athish/Documents/Strata/backend/.venv/bin/python3
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DOC_DIR = SCRIPT_DIR.parent
MD_FILE = DOC_DIR / "RPL-CS-PRO-004_v5.1.md"
RENDER_DIR = DOC_DIR / "render"
DOCX_FILE = RENDER_DIR / "RPL-CS-PRO-004_v5.1.docx"
PDF_FILE = RENDER_DIR / "RPL-CS-PRO-004_v5.1.pdf"

RENDER_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Document metadata
# ---------------------------------------------------------------------------
DOC_META = {
    "doc_id": "RPL-CS-PRO-004",
    "title": "Disconnection, Reconnection & Winter Protection Procedure",
    "company": "Rockridge Power & Light Company",
    "version": "5.1",
    "effective_date": "2025-02-10",
    "approved_date": "2025-02-05",
    "law_as_of": "2024-12-31",
    "owner": "Jasmine Carter, Supervisor, Credit & Collections",
    "reviewer": "Karen Mitchell, Director, Customer Service",
    "approver": "Jonathan Pierce, Senior Counsel, Regulatory",
    "next_review": "2026-02-10",
    "classification": "Internal",
    "supersedes": "5.0 (2024-01-15)",
}

HEADER_TEXT = (
    "Rockridge Power & Light Company  |  RPL-CS-PRO-004  |  "
    "Disconnection, Reconnection & Winter Protection Procedure"
)
FOOTER_TEXT = (
    "Version 5.1  |  Effective 2025-02-10  |  Internal  |  "
    "Uncontrolled when printed"
)


# ---------------------------------------------------------------------------
# Read and clean Markdown
# ---------------------------------------------------------------------------
def read_md(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    # Strip YAML front matter
    if text.startswith("---"):
        end = text.index("---", 3)
        text = text[end + 3:].lstrip()
    # Remove clause-ID HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Remove Mermaid code blocks (replace with placeholder)
    text = re.sub(
        r"```mermaid.*?```",
        "[Process diagram — see digital version]",
        text,
        flags=re.DOTALL,
    )
    return text


# ---------------------------------------------------------------------------
# Build .docx
# ---------------------------------------------------------------------------
def build_docx(md_text: str, out_path: Path) -> None:
    try:
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        print("python-docx not installed; skipping .docx generation.")
        return

    doc = Document()

    # ---- Page margins ----
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.2)
        section.right_margin = Inches(1.0)

    # ---- Running header ----
    for section in doc.sections:
        header = section.header
        hp = header.paragraphs[0]
        hp.text = HEADER_TEXT
        hp.style.font.size = Pt(8)
        hp.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # ---- Running footer ----
    for section in doc.sections:
        footer = section.footer
        fp = footer.paragraphs[0]
        run = fp.add_run(FOOTER_TEXT + "     Page ")
        run.font.size = Pt(8)

        # Page number field
        fldChar1 = OxmlElement("w:fldChar")
        fldChar1.set(qn("w:fldCharType"), "begin")
        instrText = OxmlElement("w:instrText")
        instrText.text = "PAGE"
        fldChar2 = OxmlElement("w:fldChar")
        fldChar2.set(qn("w:fldCharType"), "end")
        r = fp.add_run()
        r._r.append(fldChar1)
        r._r.append(instrText)
        r._r.append(fldChar2)
        r.font.size = Pt(8)

        fp.add_run(" of ").font.size = Pt(8)

        fldChar3 = OxmlElement("w:fldChar")
        fldChar3.set(qn("w:fldCharType"), "begin")
        instrText2 = OxmlElement("w:instrText")
        instrText2.text = "NUMPAGES"
        fldChar4 = OxmlElement("w:fldChar")
        fldChar4.set(qn("w:fldCharType"), "end")
        r2 = fp.add_run()
        r2._r.append(fldChar3)
        r2._r.append(instrText2)
        r2._r.append(fldChar4)
        r2.font.size = Pt(8)

        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # ---- Cover page ----
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(DOC_META["company"])
    run.bold = True
    run.font.size = Pt(14)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(DOC_META["title"])
    run2.bold = True
    run2.font.size = Pt(16)

    doc.add_paragraph()

    # Document control table
    table = doc.add_table(rows=12, cols=2)
    table.style = "Table Grid"
    ctrl_data = [
        ("Document ID", DOC_META["doc_id"]),
        ("Version", DOC_META["version"]),
        ("Effective Date", DOC_META["effective_date"]),
        ("Approved Date", DOC_META["approved_date"]),
        ("Law As-Of", DOC_META["law_as_of"]),
        ("Owner", DOC_META["owner"]),
        ("Reviewer", DOC_META["reviewer"]),
        ("Approver", DOC_META["approver"]),
        ("Next Review", DOC_META["next_review"]),
        ("Classification", DOC_META["classification"]),
        ("Supersedes", DOC_META["supersedes"]),
        ("", "Uncontrolled when printed — verify the current version in DCS before use."),
    ]
    for i, (label, value) in enumerate(ctrl_data):
        row = table.rows[i]
        row.cells[0].text = label
        row.cells[0].paragraphs[0].runs[0].bold = True
        row.cells[1].text = value

    doc.add_page_break()

    # ---- TOC placeholder ----
    doc.add_heading("Table of Contents", level=1)
    doc.add_paragraph("[Table of Contents — generated automatically in Microsoft Word]")
    doc.add_page_break()

    # ---- Body: parse Markdown lines ----
    lines = md_text.split("\n")
    in_table = False
    table_rows = []
    in_code = False

    def flush_table():
        nonlocal table_rows, in_table
        if not table_rows:
            in_table = False
            table_rows = []
            return
        # Filter separator rows
        data_rows = [r for r in table_rows if not re.match(r"^\s*\|[-| :]+\|\s*$", r)]
        if not data_rows:
            in_table = False
            table_rows = []
            return
        parsed = []
        for row in data_rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            parsed.append(cells)
        if not parsed:
            in_table = False
            table_rows = []
            return
        max_cols = max(len(r) for r in parsed)
        t = doc.add_table(rows=len(parsed), cols=max_cols)
        t.style = "Table Grid"
        for ri, row in enumerate(parsed):
            for ci, cell in enumerate(row):
                if ci < max_cols:
                    t.rows[ri].cells[ci].text = cell
                    if ri == 0:
                        for para in t.rows[ri].cells[ci].paragraphs:
                            for run in para.runs:
                                run.bold = True
        doc.add_paragraph()
        in_table = False
        table_rows = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Code block toggle
        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
            else:
                in_code = False
            i += 1
            continue

        if in_code:
            doc.add_paragraph(line, style="No Spacing")
            i += 1
            continue

        # Flush pending table when non-table line seen
        if in_table and not line.strip().startswith("|"):
            flush_table()

        # Table row
        if line.strip().startswith("|"):
            in_table = True
            table_rows.append(line)
            i += 1
            continue

        # Headings
        hm = re.match(r"^(#{1,4})\s+(.*)", line)
        if hm:
            level = len(hm.group(1))
            text = hm.group(2).strip()
            # New page for ## headings that are appendices
            if level == 2 and text.startswith("App-"):
                doc.add_page_break()
            doc.add_heading(text, level=level)
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^---+$", line.strip()):
            doc.add_paragraph("_" * 60)
            i += 1
            continue

        # Blank line
        if not line.strip():
            doc.add_paragraph()
            i += 1
            continue

        # Bold paragraph (leading **)
        bm = re.match(r"^\*\*(.*?)\*\*(.*)", line)
        if bm:
            p = doc.add_paragraph()
            run_bold = p.add_run(bm.group(1))
            run_bold.bold = True
            rest = bm.group(2)
            if rest:
                p.add_run(rest)
            i += 1
            continue

        # Blockquote / Note / Caution
        if line.strip().startswith(">"):
            content = re.sub(r"^>\s*", "", line)
            p = doc.add_paragraph(content)
            p.style = doc.styles["Intense Quote"] if "Intense Quote" in [s.name for s in doc.styles] else doc.styles["Normal"]
            i += 1
            continue

        # List item
        if re.match(r"^(\s*[-*]|\s*\d+\.)\s", line):
            text = re.sub(r"^(\s*[-*]|\s*\d+\.)\s+", "", line)
            doc.add_paragraph(text, style="List Bullet")
            i += 1
            continue

        # Plain paragraph
        # Strip inline bold/italic markers for plain text
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"`(.+?)`", r"\1", text)
        doc.add_paragraph(text)
        i += 1

    # Flush any remaining table
    if in_table:
        flush_table()

    doc.save(str(out_path))
    print(f"Saved: {out_path}")


# ---------------------------------------------------------------------------
# Convert to PDF
# ---------------------------------------------------------------------------
def convert_to_pdf(docx_path: Path, output_dir: Path) -> bool:
    """Try LibreOffice headless first, then reportlab fallback."""
    result = subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(docx_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"PDF created via LibreOffice: {output_dir / docx_path.stem}.pdf")
        return True

    print(f"LibreOffice conversion failed (rc={result.returncode}): {result.stderr.strip()}")
    print("Attempting reportlab fallback...")
    return _reportlab_fallback(docx_path, output_dir / (docx_path.stem + ".pdf"))


def _reportlab_fallback(docx_path: Path, pdf_path: Path) -> bool:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
        from reportlab.lib import colors
    except ImportError:
        print("reportlab not installed; PDF not generated.")
        return False

    # Read raw Markdown for text content
    md_text = read_md(MD_FILE)
    lines = md_text.split("\n")

    styles = getSampleStyleSheet()
    heading1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=14, spaceAfter=6)
    heading2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceAfter=4)
    normal = ParagraphStyle("Normal", parent=styles["Normal"], fontSize=9, leading=12, spaceAfter=3)
    bold_style = ParagraphStyle("Bold", parent=normal, fontName="Helvetica-Bold")

    def make_header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.drawCentredString(LETTER[0] / 2, LETTER[1] - 36, HEADER_TEXT)
        canvas.drawCentredString(
            LETTER[0] / 2, 20,
            f"{FOOTER_TEXT}     Page {doc.page}"
        )
        canvas.restoreState()

    story = []

    # Cover page
    story.append(Paragraph(DOC_META["company"], heading1))
    story.append(Paragraph(DOC_META["title"], heading1))
    story.append(Spacer(1, 0.3 * inch))
    ctrl_data = [
        ["Document ID:", DOC_META["doc_id"]],
        ["Version:", DOC_META["version"]],
        ["Effective:", DOC_META["effective_date"]],
        ["Approved:", DOC_META["approved_date"]],
        ["Law As-Of:", DOC_META["law_as_of"]],
        ["Owner:", DOC_META["owner"]],
        ["Reviewer:", DOC_META["reviewer"]],
        ["Approver:", DOC_META["approver"]],
        ["Classification:", DOC_META["classification"]],
        ["Supersedes:", DOC_META["supersedes"]],
    ]
    t = Table(ctrl_data, colWidths=[1.5 * inch, 4.5 * inch])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Uncontrolled when printed — verify the current version in DCS before use.", normal))
    story.append(PageBreak())

    # Parse Markdown lines
    in_table = False
    table_rows = []
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        if in_table and not line.strip().startswith("|"):
            # Render table
            data_rows = [r for r in table_rows if not re.match(r"^\s*\|[-| :]+\|\s*$", r)]
            parsed = []
            for row in data_rows:
                cells = [c.strip() for c in row.strip().strip("|").split("|")]
                parsed.append(cells)
            if parsed:
                max_cols = max(len(r) for r in parsed)
                col_w = 6.0 / max_cols * inch
                t2 = Table(parsed, colWidths=[col_w] * max_cols)
                t2.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ]))
                story.append(t2)
                story.append(Spacer(1, 0.1 * inch))
            in_table = False
            table_rows = []

        if line.strip().startswith("|"):
            in_table = True
            table_rows.append(line)
            continue

        # Headings
        hm = re.match(r"^(#{1,4})\s+(.*)", line)
        if hm:
            level = len(hm.group(1))
            text = hm.group(2).strip()
            if level == 2 and text.startswith("App-"):
                story.append(PageBreak())
            style = heading1 if level <= 2 else heading2
            story.append(Paragraph(text, style))
            continue

        if re.match(r"^---+$", line.strip()):
            story.append(Spacer(1, 0.1 * inch))
            continue

        if not line.strip():
            story.append(Spacer(1, 0.05 * inch))
            continue

        # Plain text
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        text = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", text)
        try:
            story.append(Paragraph(text, normal))
        except Exception:
            story.append(Paragraph(re.sub(r"<[^>]+>", "", text), normal))

    # Flush final table
    if in_table and table_rows:
        data_rows = [r for r in table_rows if not re.match(r"^\s*\|[-| :]+\|\s*$", r)]
        parsed = [[c.strip() for c in r.strip().strip("|").split("|")] for r in data_rows]
        if parsed:
            max_cols = max(len(r) for r in parsed)
            col_w = 6.0 / max_cols * inch
            t3 = Table(parsed, colWidths=[col_w] * max_cols)
            t3.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]))
            story.append(t3)

    doc_obj = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        rightMargin=1.0 * inch,
        leftMargin=1.2 * inch,
        topMargin=1.0 * inch,
        bottomMargin=0.75 * inch,
    )
    doc_obj.build(story, onFirstPage=make_header_footer, onLaterPages=make_header_footer)
    print(f"PDF created via reportlab: {pdf_path}")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== RPL-CS-PRO-004 Render Script ===")
    if not MD_FILE.exists():
        print(f"ERROR: Markdown source not found: {MD_FILE}")
        sys.exit(1)

    md_text = read_md(MD_FILE)

    print("Building .docx ...")
    build_docx(md_text, DOCX_FILE)

    if DOCX_FILE.exists():
        print("Converting to PDF ...")
        convert_to_pdf(DOCX_FILE, RENDER_DIR)
    else:
        print("DOCX not produced; attempting direct PDF generation ...")
        _reportlab_fallback = _reportlab_fallback  # noqa: F821
        convert_to_pdf(MD_FILE, RENDER_DIR)

    print("=== Done ===")
