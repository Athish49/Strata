#!/usr/bin/env python3
"""
render_fact_sheet.py — Generate company_fact_sheet.pdf using ReportLab.
Task T01: Rockridge Power & Light Company fact sheet.
Output: corpus/_global/render/company_fact_sheet.pdf
"""

import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PDF = SCRIPT_DIR / "company_fact_sheet.pdf"

# ---------------------------------------------------------------------------
# Colours — RPL corporate palette (fictional)
# ---------------------------------------------------------------------------
RPL_BLUE = colors.HexColor("#1a3a5c")
RPL_GOLD = colors.HexColor("#c8862a")
RPL_LIGHT = colors.HexColor("#f4f7fb")
RPL_RULE = colors.HexColor("#d0d9e3")
TEXT_DARK = colors.HexColor("#1c1c1c")
TEXT_MED = colors.HexColor("#4a4a4a")
TABLE_HEADER_BG = RPL_BLUE
TABLE_ALT_BG = colors.HexColor("#eef2f7")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
BASE_STYLES = getSampleStyleSheet()

def make_style(name, parent_name="Normal", **kwargs):
    parent = BASE_STYLES[parent_name]
    return ParagraphStyle(name, parent=parent, **kwargs)

STYLE_LETTERHEAD_COMPANY = make_style(
    "LetterheadCompany",
    fontSize=22,
    leading=28,
    textColor=RPL_BLUE,
    fontName="Helvetica-Bold",
    spaceAfter=0,
)
STYLE_LETTERHEAD_TAGLINE = make_style(
    "LetterheadTagline",
    fontSize=9,
    leading=12,
    textColor=RPL_GOLD,
    fontName="Helvetica-Oblique",
    spaceAfter=4,
)
STYLE_LETTERHEAD_ADDRESS = make_style(
    "LetterheadAddress",
    fontSize=8,
    leading=11,
    textColor=TEXT_MED,
    fontName="Helvetica",
)
STYLE_SECTION_HEADING = make_style(
    "SectionHeading",
    fontSize=10,
    leading=14,
    textColor=RPL_BLUE,
    fontName="Helvetica-Bold",
    spaceBefore=10,
    spaceAfter=4,
)
STYLE_BODY = make_style(
    "Body",
    fontSize=8.5,
    leading=13,
    textColor=TEXT_DARK,
    fontName="Helvetica",
    spaceAfter=6,
)
STYLE_BODY_SM = make_style(
    "BodySm",
    fontSize=7.5,
    leading=11,
    textColor=TEXT_MED,
    fontName="Helvetica",
    spaceAfter=4,
)
STYLE_FOOTER = make_style(
    "Footer",
    fontSize=7,
    leading=9,
    textColor=TEXT_MED,
    fontName="Helvetica-Oblique",
    alignment=TA_CENTER,
)
STYLE_DOC_LABEL = make_style(
    "DocLabel",
    fontSize=7.5,
    leading=10,
    textColor=TEXT_MED,
    fontName="Helvetica",
    alignment=TA_RIGHT,
)

# ---------------------------------------------------------------------------
# Table style helpers
# ---------------------------------------------------------------------------
STATS_TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
    ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
    ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE",   (0, 0), (-1, 0), 8),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT_BG]),
    ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE",   (0, 1), (-1, -1), 8),
    ("TEXTCOLOR",  (0, 1), (-1, -1), TEXT_DARK),
    ("ALIGN",      (1, 0), (-1, -1), "RIGHT"),
    ("ALIGN",      (0, 0), (0, -1), "LEFT"),
    ("GRID",       (0, 0), (-1, -1), 0.4, RPL_RULE),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
])

TERRITORY_TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
    ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
    ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE",   (0, 0), (-1, 0), 8),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT_BG]),
    ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE",   (0, 1), (-1, -1), 8),
    ("TEXTCOLOR",  (0, 1), (-1, -1), TEXT_DARK),
    ("ALIGN",      (0, 0), (-1, -1), "LEFT"),
    ("GRID",       (0, 0), (-1, -1), 0.4, RPL_RULE),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
])

SC_TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
    ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
    ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE",   (0, 0), (-1, 0), 8),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT_BG]),
    ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE",   (0, 1), (-1, -1), 8),
    ("TEXTCOLOR",  (0, 1), (-1, -1), TEXT_DARK),
    ("ALIGN",      (0, 0), (-1, -1), "LEFT"),
    ("GRID",       (0, 0), (-1, -1), 0.4, RPL_RULE),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
])

# ---------------------------------------------------------------------------
# Page callbacks
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = letter
MARGIN_LEFT  = 0.85 * inch
MARGIN_RIGHT = 0.85 * inch
MARGIN_TOP   = 0.75 * inch
MARGIN_BOT   = 0.65 * inch


def draw_page_frame(canvas, doc):
    """Draw header rule and footer on every page."""
    canvas.saveState()
    # Top blue rule
    canvas.setStrokeColor(RPL_BLUE)
    canvas.setLineWidth(2)
    canvas.line(MARGIN_LEFT, PAGE_H - MARGIN_TOP + 6,
                PAGE_W - MARGIN_RIGHT, PAGE_H - MARGIN_TOP + 6)
    # Gold accent rule
    canvas.setStrokeColor(RPL_GOLD)
    canvas.setLineWidth(1)
    canvas.line(MARGIN_LEFT, PAGE_H - MARGIN_TOP + 3,
                PAGE_W - MARGIN_RIGHT, PAGE_H - MARGIN_TOP + 3)
    # Bottom rule
    canvas.setStrokeColor(RPL_RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_LEFT, MARGIN_BOT - 4,
                PAGE_W - MARGIN_RIGHT, MARGIN_BOT - 4)
    # Footer text
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(TEXT_MED)
    footer_text = (
        "Rockridge Power & Light Company  ·  IURC Utility ID 99012  ·  "
        "400 Wabash Commons Drive, Lafayette, IN 47901  ·  www.rockridge-pl.example"
    )
    canvas.drawCentredString(PAGE_W / 2, MARGIN_BOT - 14, footer_text)
    page_label = f"Page {doc.page}"
    canvas.drawRightString(PAGE_W - MARGIN_RIGHT, MARGIN_BOT - 14, page_label)
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Content builders
# ---------------------------------------------------------------------------

def letterhead_block():
    """Return flowables for the company letterhead."""
    items = []
    items.append(Paragraph("Rockridge Power &amp; Light Company", STYLE_LETTERHEAD_COMPANY))
    items.append(Paragraph("Your west-central Indiana electric utility", STYLE_LETTERHEAD_TAGLINE))
    items.append(Paragraph(
        "400 Wabash Commons Drive, Lafayette, Indiana 47901  "
        "·  1-800-555-0142  ·  www.rockridge-pl.example",
        STYLE_LETTERHEAD_ADDRESS,
    ))
    items.append(Spacer(1, 8))
    items.append(HRFlowable(width="100%", thickness=0.5, color=RPL_RULE))
    items.append(Spacer(1, 4))
    # Document label
    items.append(Paragraph(
        "Company Fact Sheet  ·  Data as of December 31, 2024  ·  Appendix A",
        STYLE_DOC_LABEL,
    ))
    items.append(Spacer(1, 10))
    return items


def overview_block():
    items = []
    items.append(Paragraph("About Rockridge Power &amp; Light Company", STYLE_SECTION_HEADING))
    items.append(Paragraph(
        "Rockridge Power &amp; Light Company (RPL) is an Indiana investor-owned electric "
        "distribution utility regulated by the Indiana Utility Regulatory Commission (IURC) as "
        "a public utility under IC 8-1-2. RPL is a wholly owned subsidiary of Rockridge Energy "
        "Group, Inc. The Company provides retail electric distribution service to more than "
        "407,000 customers across 14 counties in the west-central region of Indiana.",
        STYLE_BODY,
    ))
    items.append(Paragraph(
        "RPL is exclusively an electric distribution company. It owns no generating units. "
        "The Company purchases its full-requirements wholesale power under a FERC-jurisdictional "
        "supply agreement and operates within the MISO footprint. RPL's owned infrastructure "
        "includes 69 kV subtransmission facilities (418 circuit miles) and 12.47 kV and 34.5 kV "
        "primary distribution facilities.",
        STYLE_BODY,
    ))
    return items


def stats_block(col_width):
    """Two-column statistics table block."""
    items = []
    items.append(Paragraph("Key Statistics", STYLE_SECTION_HEADING))

    col_gap = 0.2 * inch
    half = (col_width - col_gap) / 2.0

    # Left column — customer and meter stats
    left_data = [
        ["Customer Class", "Count"],
        ["Residential", "361,480"],
        ["Commercial", "44,215"],
        ["Industrial", "1,184"],
        ["Street & Highway Lighting", "612"],
        ["Total Customers", "407,491"],
    ]
    left_table = Table(left_data, colWidths=[half * 0.6, half * 0.4])
    left_table.setStyle(STATS_TABLE_STYLE)

    # Right column — distribution plant
    right_data = [
        ["Distribution Asset", "Quantity"],
        ["Substations", "112"],
        ["Circuits", "528"],
        ["Overhead circuit miles", "14,200"],
        ["Underground circuit miles", "4,900"],
        ["Oil-filled power transformers", "186"],
    ]
    right_table = Table(right_data, colWidths=[half * 0.65, half * 0.35])
    right_table.setStyle(STATS_TABLE_STYLE)

    # Nest in a two-column outer table
    outer = Table(
        [[left_table, Spacer(col_gap, 1), right_table]],
        colWidths=[half, col_gap, half],
    )
    outer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    items.append(outer)
    items.append(Spacer(1, 6))

    # Meter summary
    meter_data = [
        ["Meter Type", "Count"],
        ["Solid-state AMI", "371,200"],
        ["Solid-state AMR", "31,400"],
        ["Electromechanical (legacy)", "7,350"],
        ["Total meters in service*", "409,950"],
    ]
    # Half-width table, left-aligned
    meter_table = Table(meter_data, colWidths=[half * 0.6, half * 0.4])
    meter_table.setStyle(STATS_TABLE_STYLE)
    outer2 = Table([[meter_table, Spacer(col_gap + half, 1)]], colWidths=[half, col_gap + half])
    outer2.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    items.append(outer2)
    items.append(Paragraph("*Includes inactive premises.", STYLE_BODY_SM))
    return items


def territory_block(col_width):
    items = []
    items.append(Paragraph("Service Territory — 14 West-Central Indiana Counties", STYLE_SECTION_HEADING))

    counties = [
        "Benton", "Boone", "Carroll", "Clinton",
        "Fountain", "Hendricks", "Montgomery", "Parke",
        "Putnam", "Tippecanoe", "Vermillion", "Vigo",
        "Warren", "White",
    ]
    # Arrange in 2 columns of 7
    half_n = len(counties) // 2
    col_a = counties[:half_n]
    col_b = counties[half_n:]
    rows = [["County", "County"]]
    for a, b in zip(col_a, col_b):
        rows.append([a, b])

    col_gap = 0.2 * inch
    half = (col_width - col_gap) / 2.0
    t = Table(rows, colWidths=[half, half])
    t.setStyle(TERRITORY_TABLE_STYLE)
    items.append(t)
    return items


def service_centers_block(col_width):
    items = []
    items.append(Paragraph("Service Centers", STYLE_SECTION_HEADING))
    sc_data = [
        ["Code", "Location", "Role"],
        ["LAF", "Lafayette, IN", "Main / Headquarters"],
        ["CRW", "Crawfordsville, IN", "Service Center"],
        ["THT", "Terre Haute, IN", "Service Center"],
        ["FRK", "Frankfort, IN", "Service Center"],
        ["DAN", "Danville, IN", "Service Center"],
    ]
    col_w = [col_width * 0.12, col_width * 0.38, col_width * 0.50]
    t = Table(sc_data, colWidths=col_w)
    t.setStyle(SC_TABLE_STYLE)
    items.append(t)
    return items


def org_block():
    items = []
    items.append(Paragraph("Organization &amp; Operations", STYLE_SECTION_HEADING))
    items.append(Paragraph(
        "RPL employs approximately 1,450 people. The executive leadership team includes the "
        "President &amp; Chief Operating Officer, Vice Presidents for Operations, Regulatory &amp; "
        "Government Affairs, and Legal. Key operational departments include Distribution "
        "Operations, Metering, Customer Operations, Environmental Health &amp; Safety, Compliance, "
        "and Regulatory Affairs.",
        STYLE_BODY,
    ))
    items.append(Paragraph(
        "Field line and service crews are internal RPL employees. Vegetation management along "
        "RPL rights-of-way is performed by contracted line-clearance firms. The Company's fleet "
        "consists of approximately 640 vehicles, including 210 aerial/bucket and digger-derrick "
        "units, with fueling capability at all five service centers.",
        STYLE_BODY,
    ))
    items.append(Paragraph(
        "The Meter Shop &amp; Standards Laboratory at the Lafayette HQ campus handles meter accuracy "
        "testing and standards maintenance. The Distribution Control Center (DCC), also in "
        "Lafayette, operates 24/7 and coordinates grid monitoring, switching, and outage response "
        "across the entire service territory.",
        STYLE_BODY,
    ))
    return items


def systems_block(col_width):
    items = []
    items.append(Paragraph("Key Operating Systems", STYLE_SECTION_HEADING))
    sys_data = [
        ["System", "Function"],
        ["Customer Information System (CIS)", "Billing, account management, service orders"],
        ["Outage Management System (OMS)", "Outage detection, crew dispatch, restoration tracking"],
        ["AMI Head-End System (AMI HES)", "Two-way communication with 371,200 advanced meters"],
        ["Geographic Information System (GIS)", "Network mapping, asset location, environmental screening"],
        ["Work & Asset Management (WAM)", "Field work orders, asset records, maintenance tracking"],
        ["EHS Incident Management System (EHS-IMS)", "Environmental and safety incident tracking, CAPA"],
        ["Document Control System (DCS)", "Controlled document repository and revision history"],
    ]
    col_w = [col_width * 0.43, col_width * 0.57]
    t = Table(sys_data, colWidths=col_w)
    t.setStyle(STATS_TABLE_STYLE)
    items.append(t)
    return items


def contact_block():
    items = []
    items.append(Spacer(1, 6))
    items.append(HRFlowable(width="100%", thickness=0.5, color=RPL_RULE))
    items.append(Spacer(1, 4))
    items.append(Paragraph(
        "<b>Customer Service (24/7):</b> 1-800-555-0142  ·  "
        "<b>Outage Line:</b> 1-800-555-0177  ·  "
        "<b>Servicio en español:</b> 1-800-555-0143  ·  "
        "<b>Web:</b> www.rockridge-pl.example",
        STYLE_BODY_SM,
    ))
    items.append(Paragraph(
        "<b>Payments:</b> Rockridge Power, P.O. Box 6600, Lafayette, IN 47903  ·  "
        "<b>Correspondence:</b> 400 Wabash Commons Drive, Lafayette, IN 47901",
        STYLE_BODY_SM,
    ))
    items.append(Spacer(1, 4))
    items.append(Paragraph(
        "Rockridge Power &amp; Light Company is an investor-owned electric utility regulated by "
        "the Indiana Utility Regulatory Commission. This document does not contain regulatory "
        "or tariff rate information. All statistics as of December 31, 2024.",
        STYLE_BODY_SM,
    ))
    return items


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build_pdf(output_path: Path):
    doc = BaseDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOT,
        title="Rockridge Power & Light Company — Company Fact Sheet",
        author="Rockridge Power & Light Company",
        subject="Company Overview — Appendix A",
    )

    body_width = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT

    frame = Frame(
        MARGIN_LEFT, MARGIN_BOT,
        body_width,
        PAGE_H - MARGIN_TOP - MARGIN_BOT,
        id="main",
        leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0,
    )

    template = PageTemplate(id="main", frames=[frame], onPage=draw_page_frame)
    doc.addPageTemplates([template])

    story = []

    # --- Page 1 ---
    story += letterhead_block()
    story += overview_block()
    story += stats_block(body_width)
    story += territory_block(body_width)
    story += service_centers_block(body_width)

    # --- Page 2 ---
    story += org_block()
    story += systems_block(body_width)
    story += contact_block()

    doc.build(story)
    print(f"PDF written to: {output_path}")


if __name__ == "__main__":
    build_pdf(OUTPUT_PDF)
