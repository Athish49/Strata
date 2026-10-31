#!/usr/bin/env python3
"""
RPL-MTR-PGM-001 Render File Generator
Produces:
  render/RPL-MTR-PGM-001_v6.0.docx      — python-docx
  render/RPL-MTR-PGM-001_v6.0.pdf       — reportlab
  render/RPL-MTR-PGM-001_datasets.xlsx  — openpyxl (5 sheets)
"""
import os
import sys
import pandas as pd

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DOC_DIR   = os.path.abspath(os.path.join(BASE_DIR, ".."))
DATA_DIR  = os.path.join(DOC_DIR, "data")
RENDER_DIR = os.path.join(DOC_DIR, "render")
os.makedirs(RENDER_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Document control metadata
# ---------------------------------------------------------------------------
META = {
    "doc_id":       "RPL-MTR-PGM-001",
    "title":        "Meter Testing Program Plan",
    "version":      "6.0",
    "effective":    "2025-01-13",
    "approved":     "2025-01-08",
    "owner":        "Gregory Walsh",
    "owner_title":  "Manager, Meter Shop & Standards Laboratory",
    "reviewer":     "Angela Ruiz",
    "reviewer_title": "Director, Metering",
    "approver":     "Michael Brennan",
    "approver_title": "Vice President, Operations",
    "company":      "Rockridge Power & Light Company",
    "supersedes":   "RPL-MTR-PGM-001 v5.2 (2024-02-05)",
    "law_as_of":    "2024-12-31",
    "classification": "Internal",
}

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print("Loading data...")
pop   = pd.read_csv(os.path.join(DATA_DIR, "meter_population_2024-12-31.csv"))
sel   = pd.read_csv(os.path.join(DATA_DIR, "inservice_sample_selection_2025.csv"))
tests = pd.read_csv(os.path.join(DATA_DIR, "meter_test_results_2024.csv"), low_memory=False)
cust  = pd.read_csv(os.path.join(DATA_DIR, "customer_test_requests_2024.csv"))
stds  = pd.read_csv(os.path.join(DATA_DIR, "standards_calibration_2024.csv"))

# ---------------------------------------------------------------------------
# 1. DOCX
# ---------------------------------------------------------------------------
print("Generating DOCX...")
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document()

# Page margins
for section in doc.sections:
    section.top_margin    = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin   = Inches(1.25)
    section.right_margin  = Inches(1.25)

styles = doc.styles
# Adjust Normal
normal = styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11)

# ---- Cover Page ----
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run(META["company"])
run.bold = True
run.font.size = Pt(14)

doc.add_paragraph()

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run(META["title"])
run.bold = True
run.font.size = Pt(18)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run(f"Document ID: {META['doc_id']}  |  Version {META['version']}")
run.font.size = Pt(13)

doc.add_paragraph()

# Document control table
ctrl_table = doc.add_table(rows=1, cols=2)
ctrl_table.style = "Table Grid"
hdr = ctrl_table.rows[0].cells
hdr[0].text = "Field"
hdr[1].text = "Value"
for cell in hdr:
    for para in cell.paragraphs:
        for run in para.runs:
            run.bold = True

fields = [
    ("Document Title",    META["title"]),
    ("Document ID",       META["doc_id"]),
    ("Version",           META["version"]),
    ("Effective Date",    META["effective"]),
    ("Approved Date",     META["approved"]),
    ("Law As-Of Date",    META["law_as_of"]),
    ("Classification",    META["classification"]),
    ("Owner",             f"{META['owner']}, {META['owner_title']}"),
    ("Reviewer",          f"{META['reviewer']}, {META['reviewer_title']}"),
    ("Approver",          f"{META['approver']}, {META['approver_title']}"),
    ("Supersedes",        META["supersedes"]),
]
for label, value in fields:
    row = ctrl_table.add_row().cells
    row[0].text = label
    row[1].text = value

doc.add_paragraph()
p = doc.add_paragraph("Uncontrolled when printed — verify the current version in DCS before use.")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
for run in p.runs:
    run.italic = True

doc.add_page_break()

# ---- TOC Placeholder ----
h = doc.add_heading("Table of Contents", level=1)
toc_items = [
    ("1",  "Purpose"),
    ("2",  "Scope"),
    ("3",  "Definitions"),
    ("4",  "Regulatory Basis and Industry Standards"),
    ("5",  "Organization and Roles"),
    ("6",  "Meter Records"),
    ("7",  "Meter Location and Accessibility Standards"),
    ("8",  "New and Repaired Meter Acceptance"),
    ("9",  "In-Service Testing Program"),
    ("10", "Accuracy Limits and Average-Accuracy Method"),
    ("11", "Test Equipment and Standards"),
    ("12", "AMI Meter Health Monitoring"),
    ("13", "Customer-Requested and Commission-Supervised Tests"),
    ("14", "2024 Program Results (Preliminary)"),
    ("15", "2025 Test Plan"),
    ("16", "Program KPIs"),
    ("17", "Records and Retention"),
    ("18", "Training and Technician Qualification"),
    ("19", "Related Documents"),
    ("20", "Revision History"),
    ("21", "Approval Block"),
]
for num, title in toc_items:
    doc.add_paragraph(f"{num}.  {title}", style="List Number" if False else "Normal")

doc.add_page_break()

# ---- Body Sections ----
def add_section(number, title, body_paragraphs):
    doc.add_heading(f"{number}. {title}", level=1)
    for para in body_paragraphs:
        doc.add_paragraph(para)

add_section("1", "Purpose", [
    "This Meter Testing Program Plan describes how Rockridge Power & Light Company (RPL) ensures "
    "the accuracy, integrity, and regulatory compliance of its meter population. The plan governs "
    "new-meter acceptance testing, in-service testing (periodic and statistical sampling), test "
    "equipment calibration and traceability, customer-requested testing, and annual program "
    "reporting. It applies to all 409,950 revenue meters in RPL's service territory as of 2024-12-31."
])

add_section("2", "Scope", [
    "This plan covers the full RPL revenue meter fleet: 371,200 solid-state AMI meters, "
    "31,400 solid-state AMR meters, and 7,350 electromechanical meters (total: 409,950) within "
    "RPL's 14-county service territory in west-central Indiana. Transformer-rated meters (16S, "
    "12S CT-connected) constitute approximately 6,400–8,600 units within the counts above."
])

add_section("3", "Definitions", [
    "As-Found Accuracy: The measured percentage registration of a meter at the time it is removed "
    "from service or tested in place, before any adjustment. (170 IAC 4-1-8(a))",
    "Average Accuracy: Arithmetic mean of FL and LL percentage registration: (FL + LL) ÷ 2. "
    "(170 IAC 4-1-8(a))",
    "Full Load (FL): Load of approximately 100% of rated test amperes. (170 IAC 4-1-8(a))",
    "Light Load (LL): Load of approximately 10% of rated test amperes. (170 IAC 4-1-8(a))",
    "Homogeneous Group: Subdivision of the in-service meter population with similar operating "
    "characteristics. (170 IAC 4-1-10(c)(1))",
    "Lot: Subset of meters within a homogeneous group; minimum 301 meters. (170 IAC 4-1-10(c)(2))",
    "AQL: Acceptable Quality Level for lot testing: 2.50 AQL. (170 IAC 4-1-10(c)(4))",
    "U / L: Upper/Lower Specification Limits for Method B: U = 102%, L = 98%. "
    "(170 IAC 4-1-10(c)(5))",
    "Method A: All meters tested on a fixed schedule of not more than 16 years. "
    "(170 IAC 4-1-10(b))",
    "Method B: Statistical sampling — annual sample drawn from each homogeneous group lot and "
    "tested against the AQL criterion. (170 IAC 4-1-10(c))",
])

add_section("4", "Regulatory Basis and Industry Standards", [
    "Indiana Administrative Code 170 IAC 4-1 governs all metering requirements; law as of "
    "2024-12-31. Key sections: §3 (records retention), §4 (test records), §5 (meter location), "
    "§6 (new/repaired meter testing), §7 (test equipment), §8 (accuracy method), §9 (accuracy "
    "limits), §10 (in-service testing), §11 (customer-requested tests).",
    "ANSI C12.1, ANSI C12.20 referenced as company practice for test procedures and performance "
    "requirements. ANSI/ASQC Z1.9-1993 cited in 170 IAC 4-1-10(c)(3); RPL applies an internal "
    "sampling plan consistent with its Inspection Level II principles (see §9.3).",
])

add_section("5", "Organization and Roles", [
    "Gregory Walsh (P19), Manager, Meter Shop & Standards Laboratory: day-to-day program "
    "management, test schedule, equipment calibration, record integrity.",
    "Angela Ruiz (P20), Director, Metering: program ownership, IURC interface, Method B "
    "commission notification, annual report approval.",
    "Luis Hernandez (P18), Supervisor, Metering Services: field testing coordination, "
    "technician supervision, WAM work order management.",
    "Michael Brennan (P16), Vice President, Operations: approver; informed of annual results "
    "and any commission action.",
    "Meter Technicians (MT-### series): 14 certified technicians performing in-service testing "
    "(shop and field), new-meter acceptance, and customer tests.",
])

add_section("6", "Meter Records", [
    "Whenever any meter in service is tested, a record shall be preserved containing: (1) meter "
    "identification; (2) reason for test; (3) pre-test meter reading; and (4) test result with "
    "all data necessary to calculate average accuracy. (170 IAC 4-1-4(a))",
    "Permanent records are kept in WAM and include: meter serial, vendor family, technology, "
    "form factor, meter class, install date, premise ID, service center, circuit ID, county, "
    "group ID, status, last test date, last test reason, and retirement date/reason.",
    "Annual tabulations of test results are prepared by Gregory Walsh (P19) each January for "
    "the prior year, ready for IURC submission within 15 calendar days of year-end.",
])

add_section("7", "Meter Location and Accessibility Standards", [
    "Meters should be installed outdoors where practical. (170 IAC 4-1-5(A)) RPL's AMI rollout "
    "placed 98% of meters in outdoor socket positions.",
    "Mounting height: not less than 4 feet nor more than 6 feet above standing surface, measured "
    "from center of meter cover. (170 IAC 4-1-5(B),(C))",
    "Minimum center-to-center spacing on a meter board: 7.5 inches. (170 IAC 4-1-5(C))",
    "Meters shall be easily accessible for reading, testing, and adjustments. (170 IAC 4-1-5(C))",
])

add_section("8", "New and Repaired Meter Acceptance", [
    "Each new non-self-contained watthour meter shall be inspected, tested, and adjusted before "
    "installation. (170 IAC 4-1-6(a)) Self-contained single-phase meters may rely on certified "
    "manufacturer test data; RPL also performs acceptance sampling per §9.3.",
    "Lot formation: each purchase order from a single vendor = one acceptance lot. Minimum lot "
    "size for sampling: 25 meters; below 25 = 100% tested.",
    "If acceptance sample fails §9.4 criteria, Gregory Walsh (P19) places the lot on hold, "
    "notifies vendor in writing within 5 business days, and initiates return-to-vendor.",
    "All removed meters shall be inspected, cleaned, repaired as necessary, and tested before "
    "return to service. (170 IAC 4-1-6(b))",
    "Non-self-contained meters must be tested prior to installation or within 60 days after "
    "installation. (170 IAC 4-1-6(c),(d))",
])

add_section("9", "In-Service Testing Program", [
    "Meter groups (homogeneous groups) are formed by: technology, vendor family, form factor, "
    "meter class, service type, and install-year band. Minimum group size: 301 meters. "
    "(170 IAC 4-1-10(c)(2)) RPL maintains 53 active homogeneous groups as of 2024-12-31.",
    "Method B is used for all solid-state (AMI and AMR) self-contained groups. Method A "
    "16-year periodic is used for electromechanical meters and all demand-register classes.",
    "Sample size table (company practice — RPL Meter Sampling Plan, consistent with ANSI/ASQC "
    "Z1.9-1993 Inspection Level II principles): lot size 2–8 → n=3; 9–15 → n=4; 16–25 → n=5; "
    "26–50 → n=7; 51–90 → n=10; 91–150 → n=15; 151–280 → n=25; 281–500 → n=35; "
    "501–1200 → n=50; 1201–3200 → n=75; 3201–10000 → n=100; 10001–35000 → n=150; "
    "35001–150000 → n=200; 150001–500000 → n=300.",
    "Lot acceptance uses Double Specification Limit–Variability Unknown–Standard Deviation Method "
    "at 2.50 AQL with U=102%, L=98%. (170 IAC 4-1-10(c)(4),(5)) If rejected, accelerated testing "
    "is required within a maximum of 96 months. (170 IAC 4-1-10(c)(7))",
])

add_section("10", "Accuracy Limits and Average-Accuracy Method", [
    "Average percentage accuracy = (FL + LL) ÷ 2. (170 IAC 4-1-8(a))",
    "Limits: average error ≤ ±2.00%; FL error ≤ ±1.00%; LL error ≤ ±3.00%. "
    "(170 IAC 4-1-9(b)(1)(A),(B),(C))",
    "No-load prohibition: no meter that registers more than one revolution at no-load with "
    "voltage < 110% of standard service voltage. (170 IAC 4-1-9(a))",
    "Power-factor test for CT-metered installations: tested at 100% rated current, 50% lagging "
    "PF; error must not exceed ±2.00%. (170 IAC 4-1-9(b)(5))",
    "Demand register limits: integrating demand — timing element ≤ ±2% for full billing period; "
    "TOU register — max 10-minute time error; electromagnetic lagged ≤ ±2% full scale; "
    "thermal lagged ≤ ±4% full scale. (170 IAC 4-1-9(b)(3),(4))",
])

add_section("11", "Test Equipment and Standards", [
    "Test equipment hierarchy: NIST → Accredited External Laboratory → RPL Reference Standards "
    "(3 units) → Shop Test Boards (8 units) → Portable Standards (32 units) → Revenue meters.",
    "Reference standards recalibrated at least every 2 years by a recognized standardizing "
    "laboratory. (170 IAC 4-1-7(C))",
    "Portable standards checked before each field campaign. If found in error more than ±1%, "
    "immediately taken out of service for recalibration. (170 IAC 4-1-7(D))",
    "All calibration certificates are filed in WAM asset records and physically at the Meter "
    "Shop & Standards Laboratory (records series RRS-MTR-003).",
])

add_section("12", "AMI Meter Health Monitoring", [
    "Company practice (supplements but does not replace Method B annual sample).",
    "AMI HES continuously collects event data. Flags triggering removal-for-test after 14 "
    "consecutive days: zero-consumption, tamper event, power quality disturbance, metrology "
    "diagnostic fault, disconnect switch failure.",
    "Analytics engine (company practice) flags meters whose 30-day rolling consumption deviates "
    "by more than ±35% from prior 12-month baseline adjusted for degree-days.",
])

add_section("13", "Customer-Requested and Commission-Supervised Tests", [
    "Each customer may request a meter accuracy test in writing. First and second tests in any "
    "12-month period are free. (170 IAC 4-1-11(a))",
    "Subsequent tests may be billed if meter was tested within prior 36 months and found in "
    "compliance. (170 IAC 4-1-11(b)) Fee (company tariff §1.6): $40.00 residential/single-phase; "
    "$95.00 polyphase/demand.",
    "Written test report to customer within 10 days of test completion. (170 IAC 4-1-11(d))",
    "Customer may appeal test result to IURC within 5 days of report date. "
    "(170 IAC 4-1-11(e))",
])

add_section("14", "2024 Program Results (Preliminary)", [
    "Data extracted 2025-01-03. Total tests: 5,724 (AMI: 4,303; AMR: 843; EM: 578).",
    "Within-limits rates: AMI 99.73%; AMR 99.76%; EM 95.33%. No group acceptance failure "
    "in 2024. EM meters show highest error rate consistent with age profile (1972–2004).",
    "Customer tests: 620. New acceptance lots: per new_meter_lots_2024.csv.",
    "Full test results: data/meter_test_results_2024.csv.",
])

add_section("15", "2025 Test Plan", [
    "Annual sample draw executed by January 15, 2025 by Gregory Walsh (P19). Sample selections "
    "documented in data/inservice_sample_selection_2025.csv (3,750 meters selected across 53 groups).",
    "Method A periodic tests scheduled via WAM work order MTR-TST for meters within 60 days of "
    "their next-due date. Quarterly distribution of EM periodic tests per population file.",
])

add_section("16", "Program KPIs", [
    "Annual sample completion rate ≥ 98% by December 31.",
    "Test report issuance within 10 days for customer tests: 100% compliance.",
    "Reference standard recalibration on schedule: 100%.",
    "No unresolved billing review actions outstanding > 90 days.",
])

add_section("17", "Records and Retention", [
    "All meter test records retained for a minimum of 3 years. (170 IAC 4-1-3)",
    "Records kept in Indiana and available for IURC inspection. (170 IAC 4-1-3)",
    "Records series: RRS-MTR-001 (new meter lot records), RRS-MTR-002 (in-service and "
    "customer test records), RRS-MTR-003 (calibration certificates).",
])

add_section("18", "Training and Technician Qualification", [
    "All meter technicians (MT-### series) hold current AEMC certification or equivalent RPL "
    "qualification as verified by Gregory Walsh (P19) annually.",
    "Technicians performing field testing must complete hands-on competency evaluation for "
    "portable standard use before each field season.",
])

add_section("19", "Related Documents", [
    "RPL-CS-PRO-007: Meter Test Request & Billing Adjustment Procedure",
    "MTR-F-010: Customer Meter Test Request Form",
    "MTR-F-011: Meter Test Report",
    "App-B: Group Acceptance Worksheet",
    "App-C: Standards Certification Register Summary",
    "circuits_master.csv: Service territory circuit reference file",
])

add_section("20", "Revision History", [
    "v6.0 (2025-01-08): Updated for 2024-12-31 law snapshot; updated fleet count to 409,950; "
    "added AMI HES monitoring section; updated sampling table to internal procedure.",
    "v5.2 (2024-02-05): Annual update; minor corrections to group counts.",
])

# ---- Approval Block ----
doc.add_heading("21. Approval Block", level=1)
approval_table = doc.add_table(rows=1, cols=3)
approval_table.style = "Table Grid"
header_row = approval_table.rows[0].cells
header_row[0].text = "Role"
header_row[1].text = "Name / Title"
header_row[2].text = "Signature / Date"
for cell in header_row:
    for para in cell.paragraphs:
        for run in para.runs:
            run.bold = True

approvals = [
    ("Owner",    f"{META['owner']}\n{META['owner_title']}",       "Signed: 2025-01-08"),
    ("Reviewer", f"{META['reviewer']}\n{META['reviewer_title']}", "Signed: 2025-01-08"),
    ("Approver", f"{META['approver']}\n{META['approver_title']}", "Signed: 2025-01-08"),
]
for role, name, sig in approvals:
    row = approval_table.add_row().cells
    row[0].text = role
    row[1].text = name
    row[2].text = sig

docx_path = os.path.join(RENDER_DIR, "RPL-MTR-PGM-001_v6.0.docx")
doc.save(docx_path)
print(f"  Wrote {docx_path} ({os.path.getsize(docx_path):,} bytes)")

# ---------------------------------------------------------------------------
# 2. PDF via reportlab
# ---------------------------------------------------------------------------
print("Generating PDF...")
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)

pdf_path = os.path.join(RENDER_DIR, "RPL-MTR-PGM-001_v6.0.pdf")
pdf_doc  = SimpleDocTemplate(
    pdf_path,
    pagesize=letter,
    leftMargin=1.25*inch, rightMargin=1.25*inch,
    topMargin=1.0*inch,   bottomMargin=1.0*inch,
    title=f"{META['doc_id']} {META['title']} v{META['version']}",
    author=META["company"],
)

base_styles = getSampleStyleSheet()
h1_style = ParagraphStyle("H1", parent=base_styles["Heading1"],
                           fontSize=14, spaceAfter=6, spaceBefore=12, textColor=colors.HexColor("#1a3a5c"))
h2_style = ParagraphStyle("H2", parent=base_styles["Heading2"],
                           fontSize=12, spaceAfter=4, spaceBefore=8, textColor=colors.HexColor("#1a3a5c"))
body_style = ParagraphStyle("Body", parent=base_styles["Normal"],
                             fontSize=10, spaceAfter=6, leading=14)
small_style = ParagraphStyle("Small", parent=base_styles["Normal"],
                              fontSize=9, spaceAfter=4, leading=12)
center_style = ParagraphStyle("Center", parent=base_styles["Normal"],
                               alignment=1, fontSize=11, spaceAfter=6)
title_style = ParagraphStyle("Title", parent=base_styles["Normal"],
                              alignment=1, fontSize=20, spaceAfter=12,
                              textColor=colors.HexColor("#1a3a5c"), fontName="Helvetica-Bold")
subtitle_style = ParagraphStyle("Subtitle", parent=base_styles["Normal"],
                                 alignment=1, fontSize=14, spaceAfter=6)

story = []

# Cover
story.append(Spacer(1, 0.5*inch))
story.append(Paragraph(META["company"], center_style))
story.append(Spacer(1, 0.25*inch))
story.append(Paragraph(META["title"], title_style))
story.append(Paragraph(f"{META['doc_id']} · Version {META['version']}", subtitle_style))
story.append(Spacer(1, 0.25*inch))
story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a3a5c")))
story.append(Spacer(1, 0.2*inch))

ctrl_data = [["Field", "Value"]] + [[k, v] for k, v in fields]
ctrl_ts = TableStyle([
    ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a3a5c")),
    ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
    ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE",   (0,0), (-1,-1), 9),
    ("GRID",       (0,0), (-1,-1), 0.5, colors.grey),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
    ("LEFTPADDING",  (0,0), (-1,-1), 6),
    ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ("TOPPADDING",   (0,0), (-1,-1), 3),
    ("BOTTOMPADDING",(0,0), (-1,-1), 3),
])
ctrl_tbl = Table(ctrl_data, colWidths=[2.2*inch, 4.0*inch])
ctrl_tbl.setStyle(ctrl_ts)
story.append(ctrl_tbl)
story.append(Spacer(1, 0.15*inch))
story.append(Paragraph("<i>Uncontrolled when printed — verify the current version in DCS before use.</i>", center_style))
story.append(PageBreak())

# TOC
story.append(Paragraph("Table of Contents", h1_style))
for num, title in toc_items:
    story.append(Paragraph(f"{num}.   {title}", body_style))
story.append(PageBreak())

# Body sections — reuse data from docx build
body_sections = [
    ("1",  "Purpose", [
        "This Meter Testing Program Plan describes how Rockridge Power &amp; Light Company (RPL) ensures "
        "the accuracy, integrity, and regulatory compliance of its meter population. The plan governs "
        "new-meter acceptance testing, in-service testing (periodic and statistical sampling), test "
        "equipment calibration and traceability, customer-requested testing, and annual program "
        "reporting. It applies to all 409,950 revenue meters in RPL's service territory as of 2024-12-31."
    ]),
    ("2",  "Scope", [
        "This plan covers the full RPL revenue meter fleet: 371,200 solid-state AMI meters, "
        "31,400 solid-state AMR meters, and 7,350 electromechanical meters (total: 409,950) within "
        "RPL's 14-county service territory in west-central Indiana."
    ]),
    ("3",  "Definitions", [
        "<b>As-Found Accuracy:</b> Measured percentage registration before any adjustment. (170 IAC 4-1-8(a))",
        "<b>Average Accuracy:</b> (FL + LL) ÷ 2. (170 IAC 4-1-8(a))",
        "<b>Full Load (FL):</b> 100% of rated test amperes. <b>Light Load (LL):</b> 10% of rated test amperes.",
        "<b>AQL:</b> 2.50 (170 IAC 4-1-10(c)(4)). <b>U/L:</b> 102%/98% (170 IAC 4-1-10(c)(5)).",
        "<b>Method A:</b> 16-year periodic. <b>Method B:</b> Annual statistical sampling.",
    ]),
    ("4",  "Regulatory Basis", [
        "Governing regulation: 170 IAC 4-1 (Indiana Administrative Code), law as of 2024-12-31. "
        "ANSI C12.1, ANSI C12.20, and ANSI/ASQC Z1.9-1993 referenced as company practice.",
    ]),
    ("5",  "Organization and Roles", [
        "Gregory Walsh (P19) — Manager, Meter Shop &amp; Standards Laboratory: day-to-day program management.",
        "Angela Ruiz (P20) — Director, Metering: program ownership, IURC interface.",
        "Luis Hernandez (P18) — Supervisor, Metering Services: field testing coordination.",
        "Michael Brennan (P16) — VP Operations: approver.",
    ]),
    ("6",  "Meter Records", [
        "Test records must include: meter ID, reason for test, pre-test reading, and all accuracy data. "
        "(170 IAC 4-1-4(a)) Records are maintained in WAM. Minimum retention: 3 years. (170 IAC 4-1-3)",
    ]),
    ("7",  "Meter Location and Accessibility", [
        "Outdoor installation preferred. (170 IAC 4-1-5(A)) Mounting height: 4–6 ft above standing surface. "
        "(170 IAC 4-1-5(B),(C)) Minimum board spacing: 7.5 in. (170 IAC 4-1-5(C))",
    ]),
    ("8",  "New and Repaired Meter Acceptance", [
        "New non-self-contained meters: inspected, tested, adjusted before installation. (170 IAC 4-1-6(a)) "
        "RPL also performs acceptance sampling on each lot per §9.3.",
        "Non-self-contained meters: tested prior to installation or within 60 days. (170 IAC 4-1-6(c),(d))",
    ]),
    ("9",  "In-Service Testing Program", [
        "53 homogeneous groups; minimum group size 301 meters. (170 IAC 4-1-10(c)(2))",
        "Method B for all solid-state groups; Method A 16-year periodic for EM meters.",
        "Sample size table (company practice, consistent with ANSI/ASQC Z1.9-1993 Inspection Level II).",
        "Lot acceptance: 2.50 AQL, U=102%, L=98% DSL method. (170 IAC 4-1-10(c)(4),(5))",
        "Rejected lot accelerated testing: maximum 96 months. (170 IAC 4-1-10(c)(7))",
    ]),
    ("10", "Accuracy Limits and Average-Accuracy Method", [
        "Average: ≤ ±2.00%; FL: ≤ ±1.00%; LL: ≤ ±3.00%. (170 IAC 4-1-9(b)(1))",
        "PF test (CT meters): 100% rated current, 50% lagging PF, ≤ ±2.00%. (170 IAC 4-1-9(b)(5))",
        "No-load prohibition: &lt; 1 revolution at no-load, voltage &lt; 110% standard. (170 IAC 4-1-9(a))",
    ]),
    ("11", "Test Equipment and Standards", [
        "Traceability: NIST → Accredited Lab → Reference Standards (3) → Test Boards (8) → Portables (32).",
        "Reference standard recal interval: ≤ 2 years. (170 IAC 4-1-7(C))",
        "Portable standard out-of-service if error &gt; ±1%. (170 IAC 4-1-7(D))",
    ]),
    ("12", "AMI Meter Health Monitoring", [
        "Company practice supplementing Method B. AMI HES flags: zero-consumption, tamper, power quality, "
        "metrology diagnostic, disconnect switch failure. Removal-for-test after 14 consecutive days.",
    ]),
    ("13", "Customer-Requested Tests", [
        "First and second tests in any 12-month period are free. (170 IAC 4-1-11(a))",
        "Written report within 10 days. (170 IAC 4-1-11(d)) Customer appeal within 5 days. (170 IAC 4-1-11(e))",
        "Fee (where applicable): $40.00 residential/single-phase; $95.00 polyphase/demand.",
    ]),
    ("14", "2024 Program Results", [
        "Total tests: 5,724. Within-limits rates: AMI 99.73%; AMR 99.76%; EM 95.33%. "
        "No group acceptance failure in 2024. Customer tests: 620.",
    ]),
    ("15", "2025 Test Plan", [
        "Annual sample draw executed by 2025-01-15. 3,750 meters selected across 53 groups "
        "(data/inservice_sample_selection_2025.csv). Method A EM periodic tests scheduled in WAM.",
    ]),
    ("16–21", "KPIs, Records, Training, Related Documents, Revision History, Approval", [
        "KPIs: ≥98% annual sample completion; 100% customer test report compliance; 100% reference standard "
        "recal on schedule. Records retention: 3-year minimum. (170 IAC 4-1-3)",
        "Revision: v6.0 (2025-01-08) — updated for 2024-12-31 law snapshot.",
    ]),
]

for num, title, paras in body_sections:
    story.append(Paragraph(f"{num}. {title}", h1_style))
    for p_text in paras:
        story.append(Paragraph(p_text, body_style))
    story.append(Spacer(1, 0.1*inch))

# Approval table
story.append(Paragraph("21. Approval Block", h1_style))
appr_data = [["Role", "Name / Title", "Date"]] + [
    [role, name.replace("\n", "\n"), sig.replace("Signed: ", "")] for role, name, sig in approvals
]
appr_tbl = Table(appr_data, colWidths=[1.5*inch, 3.0*inch, 1.5*inch])
appr_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a3a5c")),
    ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
    ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
    ("GRID",       (0,0), (-1,-1), 0.5, colors.grey),
    ("FONTSIZE",   (0,0), (-1,-1), 9),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
    ("LEFTPADDING",  (0,0), (-1,-1), 6),
    ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ("TOPPADDING",   (0,0), (-1,-1), 4),
    ("BOTTOMPADDING",(0,0), (-1,-1), 4),
]))
story.append(appr_tbl)

pdf_doc.build(story)
print(f"  Wrote {pdf_path} ({os.path.getsize(pdf_path):,} bytes)")

# ---------------------------------------------------------------------------
# 3. XLSX — 5 sheets
# ---------------------------------------------------------------------------
print("Generating XLSX...")
from openpyxl import Workbook
from openpyxl.styles import (Font, Alignment, PatternFill, Border, Side,
                              numbers)
from openpyxl.utils import get_column_letter

wb = Workbook()
wb.remove(wb.active)  # remove default sheet

HEADER_FILL = PatternFill("solid", fgColor="1A3A5C")
ALT_FILL    = PatternFill("solid", fgColor="EEF3F8")
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
BODY_FONT   = Font(name="Calibri", size=10)
TITLE_FONT  = Font(name="Calibri", bold=True, size=12, color="1A3A5C")
THIN = Side(border_style="thin", color="CCCCCC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def set_header_row(ws, headers, row=1, col_start=1):
    for i, h in enumerate(headers):
        c = ws.cell(row=row, column=col_start+i, value=h)
        c.font    = HEADER_FONT
        c.fill    = HEADER_FILL
        c.border  = BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

def write_data_rows(ws, df, start_row=2, col_start=1):
    for r_idx, row_data in enumerate(df.itertuples(index=False), start=start_row):
        fill = ALT_FILL if r_idx % 2 == 0 else PatternFill()
        for c_idx, val in enumerate(row_data, start=col_start):
            c = ws.cell(row=r_idx, column=c_idx, value=val)
            c.font   = BODY_FONT
            c.fill   = fill
            c.border = BORDER
            c.alignment = Alignment(vertical="center", wrap_text=False)

def auto_width(ws, min_w=8, max_w=40):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_w, max(min_w, max_len + 2))

def add_title_row(ws, title_text, n_cols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    c = ws.cell(row=1, column=1, value=title_text)
    c.font = TITLE_FONT
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 20

# ---------- Sheet 1: Meter Population ----------
ws1 = wb.create_sheet("Meter Population")
add_title_row(ws1, f"RPL-MTR-PGM-001 — Meter Population (2024-12-31)  |  {META['doc_id']} v{META['version']}", len(pop.columns))
set_header_row(ws1, list(pop.columns), row=2)
write_data_rows(ws1, pop, start_row=3)
auto_width(ws1)
ws1.freeze_panes = "A3"

# ---------- Sheet 2: Sample Selections 2025 ----------
ws2 = wb.create_sheet("Sample Selections 2025")
add_title_row(ws2, f"In-Service Sample Selection 2025  |  {META['doc_id']} v{META['version']}", len(sel.columns))
set_header_row(ws2, list(sel.columns), row=2)
write_data_rows(ws2, sel, start_row=3)
auto_width(ws2)
ws2.freeze_panes = "A3"

# ---------- Sheet 3: Test Results Summary ----------
# Join group tech info from population, then summarize by reason+group
pop_lookup = pop[["meter_group_id", "meter_technology"]].drop_duplicates()
tests_ext = tests.merge(pop_lookup, on="meter_group_id", how="left")
tr_summary = (
    tests_ext.groupby(["meter_technology", "meter_group_id", "test_reason"])
    .agg(
        test_count=("test_id", "count"),
        within_Y=("within_limits", lambda x: (x == "Y").sum()),
        within_N=("within_limits", lambda x: (x == "N").sum()),
        avg_accuracy_mean=("average_accuracy_pct", lambda x: round(pd.to_numeric(x, errors="coerce").mean(), 4)),
        avg_accuracy_min=("average_accuracy_pct",  lambda x: round(pd.to_numeric(x, errors="coerce").min(), 4)),
        avg_accuracy_max=("average_accuracy_pct",  lambda x: round(pd.to_numeric(x, errors="coerce").max(), 4)),
    )
    .reset_index()
)
tr_summary["within_pct"] = (tr_summary["within_Y"] / tr_summary["test_count"] * 100).round(2)

ws3 = wb.create_sheet("Test Results Summary")
add_title_row(ws3, f"Test Results Summary 2024 (by Technology & Group)  |  {META['doc_id']} v{META['version']}", len(tr_summary.columns))
set_header_row(ws3, list(tr_summary.columns), row=2)
write_data_rows(ws3, tr_summary, start_row=3)
auto_width(ws3)
ws3.freeze_panes = "A3"

# ---------- Sheet 4: Customer Test Requests ----------
ws4 = wb.create_sheet("Customer Test Requests")
add_title_row(ws4, f"Customer Test Requests 2024  |  {META['doc_id']} v{META['version']}", len(cust.columns))
set_header_row(ws4, list(cust.columns), row=2)
write_data_rows(ws4, cust, start_row=3)
auto_width(ws4)
ws4.freeze_panes = "A3"

# ---------- Sheet 5: Standards Calibration ----------
ws5 = wb.create_sheet("Standards Calibration")
add_title_row(ws5, f"Standards Calibration Register 2024  |  {META['doc_id']} v{META['version']}", len(stds.columns))
set_header_row(ws5, list(stds.columns), row=2)
write_data_rows(ws5, stds, start_row=3)
auto_width(ws5)
ws5.freeze_panes = "A3"

xlsx_path = os.path.join(RENDER_DIR, "RPL-MTR-PGM-001_datasets.xlsx")
wb.save(xlsx_path)
print(f"  Wrote {xlsx_path} ({os.path.getsize(xlsx_path):,} bytes)")

print("\nAll render files generated successfully.")
print(f"  docx: {os.path.getsize(os.path.join(RENDER_DIR,'RPL-MTR-PGM-001_v6.0.docx')):,} bytes")
print(f"  pdf:  {os.path.getsize(os.path.join(RENDER_DIR,'RPL-MTR-PGM-001_v6.0.pdf')):,} bytes")
print(f"  xlsx: {os.path.getsize(os.path.join(RENDER_DIR,'RPL-MTR-PGM-001_datasets.xlsx')):,} bytes")
