"""
render_RPL-CS-PRO-011.py
Deterministic render script for RPL-CS-PRO-011 v2.3
Produces:
  render/RPL-CS-PRO-011_v2.3.docx
  render/RPL-CS-PRO-011_v2.3.pdf

Requires: python-docx, reportlab
"""

import re
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
RENDER_DIR = BASE_DIR / "render"
RENDER_DIR.mkdir(exist_ok=True)

MD_FILE = BASE_DIR / "RPL-CS-PRO-011_v2.3.md"
DOCX_OUT = RENDER_DIR / "RPL-CS-PRO-011_v2.3.docx"
PDF_OUT = RENDER_DIR / "RPL-CS-PRO-011_v2.3.pdf"

DOC_TITLE = "Customer Complaint & Dispute Resolution Procedure"
DOC_ID = "RPL-CS-PRO-011"
VERSION = "2.3"
EFFECTIVE = "2025-03-03"
COMPANY = "Rockridge Power & Light Company"
CLASSIFICATION = "Internal"


def strip_clause_comments(text: str) -> str:
    """Remove HTML clause-ID comments from text."""
    text = re.sub(r'<!--\s*clause:[^>]*-->', '', text)
    text = re.sub(r'<!--\s*table:[^>]*-->', '', text)
    text = re.sub(r'<!--\s*sheet:[^>]*-->', '', text)
    return text


def strip_yaml_frontmatter(text: str) -> str:
    """Remove YAML front matter block."""
    if text.startswith('---'):
        end = text.find('\n---\n', 3)
        if end != -1:
            return text[end + 5:]
    return text


def read_canonical() -> str:
    with open(MD_FILE, 'r', encoding='utf-8') as f:
        raw = f.read()
    raw = strip_yaml_frontmatter(raw)
    raw = strip_clause_comments(raw)
    return raw


# ─────────────────────────────────────────────────────────────────────────────
# DOCX RENDER
# ─────────────────────────────────────────────────────────────────────────────

def build_docx(body: str):
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import re

    doc = Document()

    # Set narrow margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    # Header
    for section in doc.sections:
        header = section.header
        header_para = header.paragraphs[0]
        header_para.text = f"{COMPANY}  |  {DOC_ID}  |  {DOC_TITLE}"
        header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = header_para.runs[0]
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    # Footer
    for section in doc.sections:
        footer = section.footer
        footer_para = footer.paragraphs[0]
        footer_para.text = (
            f"Version {VERSION}  |  Effective {EFFECTIVE}  |  "
            f"{CLASSIFICATION}  |  Uncontrolled when printed  |  Page"
        )
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer_para.runs[0]
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    # ─── COVER PAGE ───────────────────────────────────────────────────────────
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_para.add_run(COMPANY)
    run.font.size = Pt(14)
    run.bold = True

    doc.add_paragraph()

    title_para2 = doc.add_paragraph()
    title_para2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = title_para2.add_run(DOC_TITLE)
    run2.font.size = Pt(18)
    run2.bold = True

    doc.add_paragraph()

    # Document control table
    ctrl_table = doc.add_table(rows=9, cols=2)
    ctrl_table.style = 'Table Grid'
    rows_data = [
        ("Document ID", DOC_ID),
        ("Version", VERSION),
        ("Status", "Approved"),
        ("Effective Date", EFFECTIVE),
        ("Approved Date", "2025-02-26"),
        ("Law As-Of", "2024-12-31"),
        ("Owner", "Brian Kowalski — Manager, Customer Advocacy & Complaint Resolution (P17)"),
        ("Reviewer", "Karen Mitchell — Director, Customer Service (P13)"),
        ("Classification", CLASSIFICATION),
    ]
    for i, (label, value) in enumerate(rows_data):
        ctrl_table.rows[i].cells[0].text = label
        ctrl_table.rows[i].cells[0].paragraphs[0].runs[0].bold = True
        ctrl_table.rows[i].cells[1].text = value

    doc.add_paragraph()
    notice = doc.add_paragraph("Uncontrolled when printed — verify the current version in DCS before use.")
    notice.alignment = WD_ALIGN_PARAGRAPH.CENTER
    notice.runs[0].bold = True

    doc.add_page_break()

    # ─── BODY CONTENT ─────────────────────────────────────────────────────────
    lines = body.split('\n')
    in_code_block = False
    in_table = False

    for line in lines:
        stripped = line.strip()

        # Skip empty lines at start of code block handling
        if stripped.startswith('```'):
            if in_code_block:
                in_code_block = False
            else:
                in_code_block = True
                # Add a note about the diagram
                p = doc.add_paragraph('[Process Flow Diagram — see Section header]')
                p.runs[0].italic = True
                p.runs[0].font.color.rgb = RGBColor(0x44, 0x44, 0xAA)
            continue

        if in_code_block:
            # Add code block lines as styled paragraph
            p = doc.add_paragraph(stripped)
            p.runs[0].font.name = 'Courier New'
            p.runs[0].font.size = Pt(7)
            continue

        # YAML front matter already stripped

        # Headings
        if stripped.startswith('#### '):
            p = doc.add_heading(stripped[5:], level=4)
        elif stripped.startswith('### '):
            p = doc.add_heading(stripped[4:], level=3)
        elif stripped.startswith('## '):
            # Major section — new page for each
            doc.add_page_break()
            p = doc.add_heading(stripped[3:], level=2)
        elif stripped.startswith('# '):
            p = doc.add_heading(stripped[2:], level=1)

        # Horizontal rule
        elif stripped == '---':
            p = doc.add_paragraph('─' * 60)
            p.runs[0].font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)

        # Table rows
        elif stripped.startswith('|'):
            # Handle markdown tables
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if all(re.match(r'^[-:]+$', c) for c in cells if c):
                # Separator row — skip
                continue
            if not in_table:
                # Count columns from first row
                in_table = True
                num_cols = len(cells)
                tbl = doc.add_table(rows=0, cols=num_cols)
                tbl.style = 'Table Grid'
            row = tbl.add_row()
            for j, cell_text in enumerate(cells):
                if j < len(row.cells):
                    # Remove bold markers for header
                    cell_clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', cell_text)
                    row.cells[j].text = cell_clean

        else:
            if in_table:
                in_table = False
                doc.add_paragraph()  # Space after table

            if not stripped:
                # Empty line — small gap
                doc.add_paragraph()
                continue

            # Blockquote
            if stripped.startswith('>'):
                content = stripped.lstrip('> ').strip()
                p = doc.add_paragraph(content)
                p.paragraph_format.left_indent = Inches(0.5)
                p.runs[0].italic = True
                continue

            # Bullet list
            if stripped.startswith('- ') or stripped.startswith('* '):
                content = stripped[2:]
                content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
                p = doc.add_paragraph(content, style='List Bullet')
                continue

            # Numbered list
            m = re.match(r'^(\d+)\.\s+(.*)', stripped)
            if m:
                content = m.group(2)
                content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
                p = doc.add_paragraph(content, style='List Number')
                continue

            # Note / Caution callout
            if stripped.startswith('> **Note:**') or stripped.startswith('> **Caution:**'):
                content = stripped.lstrip('> ').strip()
                content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
                p = doc.add_paragraph(content)
                p.paragraph_format.left_indent = Inches(0.4)
                if p.runs:
                    p.runs[0].bold = True
                continue

            # Regular paragraph
            content = re.sub(r'\*\*([^*]+)\*\*', r'\1', stripped)
            content = re.sub(r'`([^`]+)`', r'\1', content)
            content = re.sub(r'\*([^*]+)\*', r'\1', content)
            if content:
                doc.add_paragraph(content)

    doc.save(str(DOCX_OUT))
    print(f"DOCX written: {DOCX_OUT}")


# ─────────────────────────────────────────────────────────────────────────────
# PDF RENDER  (reportlab)
# ─────────────────────────────────────────────────────────────────────────────

def build_pdf(body: str):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    import re

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle('DocTitle', parent=styles['Title'],
                                  fontSize=18, spaceAfter=12, alignment=TA_CENTER)
    company_style = ParagraphStyle('Company', parent=styles['Normal'],
                                    fontSize=12, spaceAfter=6, alignment=TA_CENTER)
    h1_style = ParagraphStyle('H1', parent=styles['Heading1'],
                               fontSize=14, spaceBefore=12, spaceAfter=6)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'],
                               fontSize=12, spaceBefore=10, spaceAfter=4)
    h3_style = ParagraphStyle('H3', parent=styles['Heading3'],
                               fontSize=11, spaceBefore=8, spaceAfter=3)
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
                                 fontSize=9, spaceAfter=4, leading=13)
    bullet_style = ParagraphStyle('Bullet', parent=styles['Normal'],
                                   fontSize=9, spaceAfter=3, leftIndent=20, leading=13)
    note_style = ParagraphStyle('Note', parent=styles['Normal'],
                                 fontSize=9, spaceAfter=4, leftIndent=30, leading=13,
                                 textColor=colors.HexColor('#333366'))
    code_style = ParagraphStyle('Code', parent=styles['Code'],
                                 fontSize=7, spaceAfter=2, fontName='Courier')
    control_label = ParagraphStyle('CtrlLabel', parent=styles['Normal'],
                                    fontSize=9, textColor=colors.HexColor('#555555'))

    story = []

    def header_footer(canvas, doc):
        canvas.saveState()
        # Header
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.HexColor('#555555'))
        canvas.drawCentredString(letter[0] / 2, letter[1] - 0.5 * inch,
                                  f"{COMPANY}  |  {DOC_ID}  |  {DOC_TITLE}")
        # Footer
        canvas.drawCentredString(letter[0] / 2, 0.4 * inch,
                                  f"Version {VERSION}  |  Effective {EFFECTIVE}  |  "
                                  f"{CLASSIFICATION}  |  Uncontrolled when printed  |  "
                                  f"Page {doc.page}")
        canvas.restoreState()

    # ─── COVER ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1 * inch))
    story.append(Paragraph(COMPANY, company_style))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(DOC_TITLE, title_style))
    story.append(Spacer(1, 0.5 * inch))

    ctrl_data = [
        ['Document ID', DOC_ID],
        ['Version', VERSION],
        ['Status', 'Approved'],
        ['Effective Date', EFFECTIVE],
        ['Approved Date', '2025-02-26'],
        ['Law As-Of', '2024-12-31'],
        ['Owner', 'Brian Kowalski — Manager, Customer Advocacy & Complaint Resolution (P17)'],
        ['Reviewer', 'Karen Mitchell — Director, Customer Service (P13)'],
        ['Supersedes', '2.2 (2024-03-18)'],
        ['Classification', CLASSIFICATION],
    ]
    ctrl_table = Table(ctrl_data, colWidths=[1.8 * inch, 4.5 * inch])
    ctrl_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F0F0F0')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(ctrl_table)
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        '<b>Uncontrolled when printed — verify the current version in DCS before use.</b>',
        ParagraphStyle('Notice', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER,
                       textColor=colors.HexColor('#AA0000'))
    ))
    story.append(PageBreak())

    # ─── BODY ─────────────────────────────────────────────────────────────────
    lines = body.split('\n')
    in_code_block = False
    table_rows = []
    in_table = False

    def flush_table():
        nonlocal table_rows, in_table
        if not table_rows:
            return
        # Determine column widths
        num_cols = max(len(r) for r in table_rows) if table_rows else 1
        col_w = 6.3 / num_cols * inch
        tbl = Table(table_rows, colWidths=[col_w] * num_cols)
        tbl.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8E8E8')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('WORDWRAP', (0, 0), (-1, -1), True),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 6))
        table_rows = []
        in_table = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('```'):
            if in_code_block:
                in_code_block = False
            else:
                in_code_block = True
                story.append(Paragraph('[Process Flow Diagram — Mermaid source in canonical .md file]',
                                        note_style))
            continue

        if in_code_block:
            if stripped:
                story.append(Paragraph(stripped.replace('<', '&lt;').replace('>', '&gt;'), code_style))
            continue

        if stripped.startswith('|'):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if all(re.match(r'^[-:]+$', c) for c in cells if c):
                continue  # separator row
            cells_clean = [re.sub(r'\*\*([^*]+)\*\*', r'\1', c) for c in cells]
            table_rows.append(cells_clean)
            in_table = True
            continue
        else:
            if in_table:
                flush_table()

        if stripped == '---':
            story.append(HRFlowable(width='100%', thickness=0.5, color=colors.grey))
            story.append(Spacer(1, 4))
            continue

        if not stripped:
            story.append(Spacer(1, 3))
            continue

        # Headings
        if stripped.startswith('## '):
            story.append(PageBreak())
            story.append(Paragraph(stripped[3:], h2_style))
            continue
        if stripped.startswith('### '):
            story.append(Paragraph(stripped[4:], h3_style))
            continue
        if stripped.startswith('# '):
            story.append(Paragraph(stripped[2:], h1_style))
            continue
        if stripped.startswith('#### '):
            story.append(Paragraph(stripped[5:], h3_style))
            continue

        # Blockquote / note
        if stripped.startswith('>'):
            content = stripped.lstrip('> ').strip()
            content = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', content)
            content = content.replace('&', '&amp;').replace('<b>', '<b>').replace('</b>', '</b>')
            story.append(Paragraph(content, note_style))
            continue

        # Bullet
        if stripped.startswith('- ') or stripped.startswith('* '):
            content = stripped[2:]
            content = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', content)
            content = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', content)
            story.append(Paragraph(f'• {content}', bullet_style))
            continue

        # Numbered list
        m = re.match(r'^(\d+)\.\s+(.*)', stripped)
        if m:
            content = m.group(2)
            content = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', content)
            content = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', content)
            story.append(Paragraph(f'{m.group(1)}. {content}', bullet_style))
            continue

        # Regular paragraph
        content = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', stripped)
        content = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', content)
        content = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', content)
        story.append(Paragraph(content, body_style))

    if in_table:
        flush_table()

    doc = SimpleDocTemplate(
        str(PDF_OUT),
        pagesize=letter,
        rightMargin=1.25 * inch,
        leftMargin=1.25 * inch,
        topMargin=1 * inch,
        bottomMargin=0.75 * inch,
    )
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"PDF written: {PDF_OUT}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    body = read_canonical()
    build_docx(body)
    build_pdf(body)
    print("Render complete.")
