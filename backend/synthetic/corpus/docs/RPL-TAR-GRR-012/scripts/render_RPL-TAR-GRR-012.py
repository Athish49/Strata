"""
render_RPL-TAR-GRR-012.py

Deterministic ReportLab renderer for IURC Tariff No. 12
Rockridge Power & Light Company — General Rules and Regulations

Usage:
    /Users/athish/Documents/Strata/backend/.venv/bin/python3 \
        render_RPL-TAR-GRR-012.py

Output:
    ../render/RPL-TAR-GRR-012_v2024-06-01.pdf

Requirements:
    reportlab >= 3.x  (available in project venv)

Design notes:
    - Seed-free and deterministic: no random elements.
    - Running twice produces byte-identical output if the source .md is unchanged.
    - Pages: cover page + one page per Sheet section.
    - Times fonts for professional appearance.
"""

import os
import re
import sys
from pathlib import Path

# Determine paths
SCRIPT_DIR = Path(__file__).resolve().parent
DOC_DIR = SCRIPT_DIR.parent
SOURCE_MD = DOC_DIR / "RPL-TAR-GRR-012_v2024-06-01.md"
RENDER_DIR = DOC_DIR / "render"
OUTPUT_PDF = RENDER_DIR / "RPL-TAR-GRR-012_v2024-06-01.pdf"

RENDER_DIR.mkdir(parents=True, exist_ok=True)

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable
    )
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.lib.colors import HexColor, black, white, gray
except ImportError as e:
    print(f"ERROR: reportlab import failed: {e}")
    print("Install with: pip install reportlab")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS & STYLE DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

COMPANY_NAME = "Rockridge Power & Light Company"
TARIFF_TITLE = "IURC Tariff No. 12"
DOC_SUBTITLE = "General Rules and Regulations — Electric Service"
CAUSE_NO = "99012"
FILED = "2024-04-30"
EFFECTIVE = "2024-06-01"
APPROVED = "2024-05-15"
SUPERSEDES = "IURC No. 12 effective 2021-10-01"
ISSUER = "Thomas Whitfield, Vice President, Regulatory & Government Affairs"
ADDRESS = "400 Wabash Commons Drive, Lafayette, IN 47901"
PHONE = "1-800-555-0142"
WEB = "www.rockridge-pl.example"

DARK_BLUE = HexColor("#1A3A5C")
MID_BLUE = HexColor("#2B5E9E")
LIGHT_GRAY = HexColor("#F0F2F5")
RULE_GRAY = HexColor("#CCCCCC")
TEXT_BLACK = HexColor("#1C1C1C")

PAGE_W, PAGE_H = letter  # 8.5 × 11 inches

MARGIN = 0.85 * inch

STYLES = getSampleStyleSheet()

def make_styles():
    """Return a dict of named ParagraphStyles used throughout the document."""
    base = STYLES["Normal"]

    cover_company = ParagraphStyle(
        "CoverCompany",
        parent=base,
        fontName="Times-Bold",
        fontSize=16,
        leading=20,
        textColor=DARK_BLUE,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    cover_title = ParagraphStyle(
        "CoverTitle",
        parent=base,
        fontName="Times-Bold",
        fontSize=14,
        leading=18,
        textColor=DARK_BLUE,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    cover_subtitle = ParagraphStyle(
        "CoverSubtitle",
        parent=base,
        fontName="Times-Italic",
        fontSize=11,
        leading=15,
        textColor=MID_BLUE,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    cover_meta = ParagraphStyle(
        "CoverMeta",
        parent=base,
        fontName="Times-Roman",
        fontSize=9,
        leading=13,
        textColor=TEXT_BLACK,
        alignment=TA_CENTER,
        spaceAfter=3,
    )
    sheet_header = ParagraphStyle(
        "SheetHeader",
        parent=base,
        fontName="Times-Bold",
        fontSize=11,
        leading=14,
        textColor=DARK_BLUE,
        spaceAfter=2,
        spaceBefore=6,
    )
    rule_heading = ParagraphStyle(
        "RuleHeading",
        parent=base,
        fontName="Times-Bold",
        fontSize=10,
        leading=13,
        textColor=DARK_BLUE,
        spaceAfter=2,
        spaceBefore=4,
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=base,
        fontName="Times-Bold",
        fontSize=9,
        leading=12,
        textColor=TEXT_BLACK,
        spaceAfter=2,
        spaceBefore=3,
    )
    body = ParagraphStyle(
        "TariffBody",
        parent=base,
        fontName="Times-Roman",
        fontSize=8.5,
        leading=12,
        textColor=TEXT_BLACK,
        alignment=TA_JUSTIFY,
        spaceAfter=4,
        spaceBefore=1,
    )
    body_indent = ParagraphStyle(
        "TariffBodyIndent",
        parent=base,
        fontName="Times-Roman",
        fontSize=8.5,
        leading=12,
        textColor=TEXT_BLACK,
        alignment=TA_JUSTIFY,
        spaceAfter=3,
        spaceBefore=1,
        leftIndent=14,
    )
    table_header = ParagraphStyle(
        "TableHeader",
        parent=base,
        fontName="Times-Bold",
        fontSize=8,
        leading=11,
        textColor=white,
        alignment=TA_CENTER,
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=base,
        fontName="Times-Roman",
        fontSize=8,
        leading=11,
        textColor=TEXT_BLACK,
        alignment=TA_LEFT,
    )
    table_cell_center = ParagraphStyle(
        "TableCellCenter",
        parent=base,
        fontName="Times-Roman",
        fontSize=8,
        leading=11,
        textColor=TEXT_BLACK,
        alignment=TA_CENTER,
    )
    footer = ParagraphStyle(
        "Footer",
        parent=base,
        fontName="Times-Roman",
        fontSize=7,
        leading=10,
        textColor=gray,
        alignment=TA_CENTER,
    )
    return {
        "cover_company": cover_company,
        "cover_title": cover_title,
        "cover_subtitle": cover_subtitle,
        "cover_meta": cover_meta,
        "sheet_header": sheet_header,
        "rule_heading": rule_heading,
        "section_heading": section_heading,
        "body": body,
        "body_indent": body_indent,
        "table_header": table_header,
        "table_cell": table_cell,
        "table_cell_center": table_cell_center,
        "footer": footer,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PAGE TEMPLATE CALLBACKS (header / footer on each page)
# ─────────────────────────────────────────────────────────────────────────────

def on_page(canvas, doc):
    """Draw running header and footer on every page except the cover."""
    canvas.saveState()

    page_num = canvas.getPageNumber()

    if page_num == 1:
        # Cover page — draw decorative horizontal rules only
        canvas.setStrokeColor(DARK_BLUE)
        canvas.setLineWidth(2)
        canvas.line(MARGIN, PAGE_H - MARGIN * 0.7,
                    PAGE_W - MARGIN, PAGE_H - MARGIN * 0.7)
        canvas.line(MARGIN, MARGIN * 0.65,
                    PAGE_W - MARGIN, MARGIN * 0.65)
        canvas.restoreState()
        return

    # Running header
    canvas.setFillColor(DARK_BLUE)
    canvas.setFont("Times-Bold", 7.5)
    canvas.drawString(MARGIN, PAGE_H - MARGIN * 0.55,
                      COMPANY_NAME + " | IURC Tariff No. 12")
    canvas.setFont("Times-Roman", 7.5)
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN * 0.55,
                           f"Effective: {EFFECTIVE} | Cause No. {CAUSE_NO}")
    canvas.setStrokeColor(MID_BLUE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, PAGE_H - MARGIN * 0.65,
                PAGE_W - MARGIN, PAGE_H - MARGIN * 0.65)

    # Running footer
    canvas.setFont("Times-Roman", 7)
    canvas.setFillColor(gray)
    canvas.line(MARGIN, MARGIN * 0.65, PAGE_W - MARGIN, MARGIN * 0.65)
    canvas.drawString(MARGIN, MARGIN * 0.45,
                      f"RPL-TAR-GRR-012 | Filed: {FILED} | {ADDRESS}")
    canvas.drawRightString(PAGE_W - MARGIN, MARGIN * 0.45,
                           f"Page {page_num}")

    canvas.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
# CONTENT BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_cover_page(S):
    """Return list of Flowables for the cover page."""
    story = []

    story.append(Spacer(1, 1.6 * inch))

    # Decorative block
    story.append(Paragraph(COMPANY_NAME, S["cover_company"]))
    story.append(Spacer(1, 0.08 * inch))
    story.append(HRFlowable(width="70%", thickness=1.5, color=MID_BLUE,
                             hAlign="CENTER"))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(TARIFF_TITLE, S["cover_title"]))
    story.append(Paragraph(DOC_SUBTITLE, S["cover_subtitle"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(HRFlowable(width="50%", thickness=0.5, color=RULE_GRAY,
                             hAlign="CENTER"))
    story.append(Spacer(1, 0.2 * inch))

    meta_rows = [
        ("Cause No.", CAUSE_NO),
        ("Filed:", FILED),
        ("Approved:", APPROVED),
        ("Effective:", EFFECTIVE),
        ("Supersedes:", SUPERSEDES),
    ]
    for label, value in meta_rows:
        story.append(Paragraph(f"<b>{label}</b> {value}", S["cover_meta"]))

    story.append(Spacer(1, 0.25 * inch))
    story.append(HRFlowable(width="50%", thickness=0.5, color=RULE_GRAY,
                             hAlign="CENTER"))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph(f"Issued by: {ISSUER}", S["cover_meta"]))
    story.append(Paragraph(ADDRESS, S["cover_meta"]))
    story.append(Paragraph(f"Customer Service: {PHONE} | {WEB}", S["cover_meta"]))

    story.append(Spacer(1, 0.25 * inch))

    # IURC Box
    iurc_data = [
        [Paragraph("<b>Indiana Utility Regulatory Commission</b>", S["table_cell"])],
        [Paragraph("PNC Center, 101 W. Washington Street, Suite 1500E, Indianapolis, IN 46204", S["table_cell"])],
        [Paragraph("Consumer Affairs: 1-800-851-4268 | 317-232-2712 | iurc.portal.in.gov", S["table_cell"])],
        [Paragraph("Hours: 8:15 a.m.–4:45 p.m. ET, Mon–Fri | State Form 50488", S["table_cell"])],
    ]
    iurc_table = Table(iurc_data, colWidths=[5.5 * inch])
    iurc_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, DARK_BLUE),
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(iurc_table)

    story.append(PageBreak())
    return story


def sheet_header_block(sheet_nos, rule_no, title, revision, effective, cause, S):
    """Return Flowables for a sheet header block."""
    items = []
    items.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE,
                             spaceAfter=4))
    items.append(Paragraph(
        f"<b>Sheet(s) {sheet_nos}</b> &nbsp;|&nbsp; "
        f"Rule {rule_no} — {title} &nbsp;|&nbsp; "
        f"{revision} &nbsp;|&nbsp; "
        f"Effective: {effective} &nbsp;|&nbsp; Cause No. {cause}",
        S["sheet_header"]
    ))
    items.append(HRFlowable(width="100%", thickness=0.5, color=MID_BLUE,
                             spaceBefore=2, spaceAfter=6))
    return items


def parse_markdown_to_paragraphs(md_text, S):
    """
    Parse the tariff Markdown into a flat list of ReportLab Flowables.
    This is a simplified parser that handles:
      - ## / ### headings
      - Plain paragraphs
      - Table rows  |...|...|
      - HTML comment clause IDs (stripped)
      - Horizontal rules ---
      - Bold text **...**
      - List items starting with (a)/(b)/(1)/(2) etc.
    """
    story = []
    lines = md_text.split("\n")
    in_table = False
    table_rows = []
    table_col_count = 0

    def flush_table():
        nonlocal table_rows, table_col_count, in_table
        if not table_rows:
            in_table = False
            return
        # Filter separator rows (--- cells)
        data_rows = [r for r in table_rows
                     if not all(re.match(r'^[-: ]+$', c.strip()) for c in r)]
        if not data_rows:
            in_table = False
            table_rows = []
            return

        col_count = max(len(r) for r in data_rows)
        # Normalize all rows to same col count
        normed = [r + [""] * (col_count - len(r)) for r in data_rows]

        # Convert first row to header
        header = normed[0]
        body_data = normed[1:]

        # Compute column widths evenly
        available = PAGE_W - 2 * MARGIN - 0.2 * inch
        col_w = [available / col_count] * col_count

        tbl_data = []
        # Header row
        hdr_row = [Paragraph(f"<b>{cell.strip()}</b>", S["table_header"])
                   for cell in header]
        tbl_data.append(hdr_row)
        for row in body_data:
            tbl_data.append([Paragraph(cell.strip(), S["table_cell"])
                              for cell in row])

        tbl = Table(tbl_data, colWidths=col_w, repeatRows=1)
        tbl_style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [LIGHT_GRAY, white]),
            ("GRID", (0, 0), (-1, -1), 0.4, RULE_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
        tbl.setStyle(tbl_style)
        story.append(Spacer(1, 4))
        story.append(tbl)
        story.append(Spacer(1, 6))
        table_rows = []
        in_table = False

    i = 0
    while i < len(lines):
        line = lines[i]
        raw = line.rstrip()

        # Skip HTML comments (clause IDs)
        if re.match(r'^\s*<!--.*-->\s*$', raw):
            i += 1
            continue

        # Section break via horizontal rule ---
        if re.match(r'^---+\s*$', raw):
            if in_table:
                flush_table()
            story.append(HRFlowable(width="100%", thickness=0.4,
                                     color=RULE_GRAY, spaceBefore=6,
                                     spaceAfter=6))
            i += 1
            continue

        # Page break triggers: ## Sheet N heading  (start new page per sheet group)
        # Detect major headings that map to sheet sections
        h2_match = re.match(r'^## (Sheet[s]? .+)', raw)
        if h2_match:
            if in_table:
                flush_table()
            story.append(PageBreak())
            text = h2_match.group(1)
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            story.append(Paragraph(text, S["rule_heading"]))
            i += 1
            continue

        # # Heading level 1 — document title
        h1_match = re.match(r'^# (.+)', raw)
        if h1_match:
            if in_table:
                flush_table()
            text = h1_match.group(1)
            story.append(Paragraph(text, S["cover_company"]))
            i += 1
            continue

        # ### Heading level 3
        h3_match = re.match(r'^### (.+)', raw)
        if h3_match:
            if in_table:
                flush_table()
            text = h3_match.group(1)
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            story.append(Paragraph(text, S["cover_subtitle"]))
            i += 1
            continue

        # Bold section heading **text**
        bold_line = re.match(r'^\*\*(.+)\*\*\s*$', raw)
        if bold_line:
            if in_table:
                flush_table()
            story.append(Paragraph(f"<b>{bold_line.group(1)}</b>",
                                   S["section_heading"]))
            i += 1
            continue

        # Table row
        if raw.startswith("|"):
            cells = [c for c in raw.split("|")[1:-1]]
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(cells)
            i += 1
            continue
        else:
            if in_table:
                flush_table()

        # Empty line
        if not raw.strip():
            story.append(Spacer(1, 4))
            i += 1
            continue

        # Indented list item (a), (b), (1), (2)…
        indent_match = re.match(r'^(\s{2,}|\t)\(?[a-zA-Z0-9]+\)', raw)
        if indent_match:
            text = raw.strip()
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
            story.append(Paragraph(text, S["body_indent"]))
            i += 1
            continue

        # General body paragraph
        text = raw.strip()
        if not text:
            i += 1
            continue
        # Replace markdown bold/italic
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        # Escape ampersands not already escaped
        text = text.replace("&nbsp;", " ")
        text = re.sub(r'&(?!#|[a-zA-Z]+;)', '&amp;', text)
        story.append(Paragraph(text, S["body"]))
        i += 1

    if in_table:
        flush_table()

    return story


def build_document():
    """Build and save the complete PDF."""
    S = make_styles()

    # invariant=True pins the PDF creation timestamp and disables random file ID,
    # ensuring identical byte output on repeated runs with the same source.
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=f"{COMPANY_NAME} — IURC Tariff No. 12",
        author=COMPANY_NAME,
        subject=DOC_SUBTITLE,
        creator="RPL-TAR-GRR-012 render script v2024-06-01",
        producer="ReportLab",
        invariant=True,
    )

    story = []

    # ── Cover page ──────────────────────────────────────────────────────────
    story.extend(build_cover_page(S))

    # ── Body from Markdown ───────────────────────────────────────────────────
    with open(SOURCE_MD, "r", encoding="utf-8") as fh:
        md_text = fh.read()

    # Remove the document-level comment block at top (lines starting with <!-- on their own)
    md_text = re.sub(r'<!--.*?-->\n', '', md_text, flags=re.DOTALL)

    body_story = parse_markdown_to_paragraphs(md_text, S)
    story.extend(body_story)

    # ── Build PDF ────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF written to: {OUTPUT_PDF}")
    size_bytes = OUTPUT_PDF.stat().st_size
    size_kb = size_bytes / 1024
    print(f"PDF size: {size_kb:.1f} KB ({size_bytes:,} bytes)")


if __name__ == "__main__":
    build_document()
