# Audit — Group A (Customer & Tariff): T13, T14, T15, T17

**Spec audited:** `/home/claude/strata_synthetic_corpus_spec.md` v1.0 (2026-10-06), Sections 0–3 plus T13, T14, T15, T17
**Auditor role:** senior reviewer (utility regulatory and customer operations)
**Date:** 2026-10-06
**Constraint observed:** this report adds **no regulatory values** to the spec. Every number proposed below is a company-chosen operational value (fees, codes, sheet numbers, internal targets), a fictional identifier, or a real regulator *contact detail*, which §2.1 allows. Wherever a value could also be set by the IAC, the proposed text sends the agent to the pack.

---

## How to read this report

- **(a) Real-world anatomy** — what the real documents look like, with only URLs I opened in this session.
- **(b) Gaps** — severity is **critical** (the agent will produce a document that fails T90, contradicts a sibling document, or that a regulatory professional would reject on sight), **major** (realism or completeness clearly below a real document), or **minor**.
- **(c) Ready-to-paste spec text** — replacement Markdown for the task section. Paste it over the existing task section from `## Txx` down to the next `---`.
- **(d) Global recommendations** — at the end. Several task patches depend on the new **§1.6 Canonical shared operational data** proposed in (d). Apply (d) first.

### Sources opened (all tasks)

| # | Source | URL | Used for |
|---|---|---|---|
| S1 | NIPSCO, General Rules and Regulations Applicable to Electric Service (IURC Original Volume No. 16, eff. 2025-07-01) | https://www.nipsco.com/docs/librariesprovider11/rates-and-tariffs/electric-rates/2025-to-current/general-rules-and-regulations.pdf | T13, T15 |
| S2 | AES Indiana (IPL), Rules and Regulations for Electric Service, I.U.R.C. No. E-18 (eff. 2020-11-04) | https://www.aesindiana.com/sites/default/files/2021-02/Rules_and_Regulations_Effective_11-04-2020.pdf | T13, T14 |
| S3 | AES Indiana, Tariff Table of Contents (eff. 2021-04-07) | https://www.aesindiana.com/sites/default/files/2021-05/Table-of-Contents-50409-Effective-04-07-21.pdf | T13 |
| S4 | CenterPoint Energy Indiana South electric tariff, I.U.R.C. No. E-14 | https://www.centerpointenergy.com/en-us/Documents/RatesandTariffs/Indiana/Southwest/in-south-electric-tariff.pdf | T13 |
| S5 | Indiana Michigan Power, Indiana tariff book I.U.R.C. No. 20 (2024–2025 edition) | https://www.indianamichiganpower.com/lib/docs/ratesandtariffs/Indiana/IMINTB2004-30-2025.pdf | T13, T14, T15 |
| S6 | Indiana Michigan Power, Indiana tariff book (eff. 2022-02-23 edition) | https://www.indianamichiganpower.com/lib/docs/ratesandtariffs/Indiana/IMINTB1901-31-2024.pdf | T13 |
| S7 | Indiana Michigan Power tariffs on IURC site (I.U.R.C. No. 16, 2013) | https://secure.in.gov/iurc/files/Indiana-Michigan-Power-Tariffs.pdf | T13 (header pattern) |
| S8 | AES Ohio (DP&L) tariff sheet D6, Disconnection | https://www.aes-ohio.com/sites/default/files/2021-02/D6%20-%20Disconnection%2010-1-18.pdf | T14 |
| S9 | Washington Electric Co-op Policy #12, Disconnection of Electrical Service | https://www.washingtonelectric.coop/wp-content/uploads/2019/04/Disconnection-of-Electrical-Service.pdf | T14 |
| S10 | Indiana OUCC, Winter Disconnection Moratorium FAQ | https://secure.in.gov/oucc/about-your-rates/winter-disconnection-moratorium-frequently-asked-questions | T14 (context only) |
| S11 | Avista (Oregon) Rule No. 11, Discontinuance and Restoration of Service | https://www.myavista.com/-/media/myavista/content-documents/our-rates-and-tariffs/or/rule-11-discontinuance-and-restoration-of-service.pdf | T14 |
| S12 | Avista (Oregon) Rule No. 5, Special Information Required on Forms | https://www.myavista.com/-/media/myavista/content-documents/our-rates-and-tariffs/or/rule-05-special-information-required-on-forms.pdf | T14, T17 (notice language blocks) |
| S13 | Duquesne Light, Field Collections procedure filed with PA PUC (2025) | https://www.puc.pa.gov/pcdocs/1902417.pdf | T14 (internal procedure format) |
| S14 | Wisconsin Public Service (Michigan service), Medical Certification Form | https://www.wisconsinpublicservice.com/payment-bill/pdf/medical.pdf | T14 (form layout) |
| S15 | NJ BPU, Application for Electric Meter Test | https://www.nj.gov/bpu/pdf/reliability/Electric%20Meter%20Test%20request%20form%20as%20of%20January%2031%202022.pdf | T15 (form layout) |
| S16 | City of Le Sueur (MN), Electric Meter Testing Policy | https://www.cityoflesueur.com/DocumentCenter/View/1796/Electric-Meter-Testing-Policy-PDF | T15 |
| S17 | Marquette Board of Light & Power, Billing Adjustment Policy (amended 2025-06-17) | https://mblp.org/wp-content/uploads/2025/06/Appendix-D-BillingAdjustmentPolicy-25-06-17.pdf | T15 |
| S18 | IURC, Customer Assistance (Consumer Affairs) | https://secure.in.gov/iurc/customer-assistance | T17, T14 |
| S19 | IURC, Contact Us | https://secure.in.gov/iurc/contact-us | T17, T14 |
| S20 | OUCC news, "Consumer affairs process streamlined for the IURC and OUCC" (2011) | https://www.in.gov/oucc/news/consumer-affairs-process-streamlined-for-the-iurc-and-oucc | T17 |
| S21 | IURC Consumer Affairs Complaint Form, State Form 50488 (R3/2-21) | https://forms.in.gov/Download.aspx?id=11365 | T17 |
| S22 | Choptank Electric Cooperative, Board & Management Policy 501, Member Complaints | https://choptankelectric.coop/sites/choptankelectric/files/BP%20501%20Member%20Complaints.pdf | T17 |
| S23 | Pennsylvania PUC complaint process overview (bar association handout) | https://www.dcba-pa.org/pdfs/eventAds/16_PUC%20Complaint%20Process.pdf | T17 |

I tried a Maine PUC sample disconnection notice (`DisconnectionNotice_example.docx`) but could not read it, so it is not used. I found no public **internal** Indiana IOU SOP for disconnection, meter-test handling or complaints. Indiana IOUs publish tariffs, not SOPs. The procedure anatomy below therefore combines Indiana tariff content (S1, S2, S5) with internal-procedure formats filed elsewhere (S13), co-op and municipal policies (S9, S16, S17, S22) and regulator forms (S14, S15, S21).

**The study references carry other states' values.** S9 (Vermont temperature limits), S11 (Oregon disconnection hours, medical-certificate durations), S14 (Michigan hold days), S15 (NJ accuracy limit and load weighting) and S16/S17 (municipal accuracy and look-back limits) all contain numbers that differ from Indiana's. An agent that "studies" them will import those numbers. The task patches below forbid that explicitly.

---

## T13 — Tariff for Electric Service, IURC No. 12: General Rules and Regulations

### (a) Real-world anatomy

**NIPSCO GRR (S1).** About 40 sheets (Sheets 7–48) of a larger volume. Each sheet header reads: utility name · "Original/First Revised/Second Revised Sheet No. n" · tariff name · "Original Volume No. 16" · "Cancelling All Previously Approved Tariffs" · section title · "Applicable to Electric Service" · Issued date / Effective date. Revised sheets say "Superseding Original Sheet No. n". Sheets are revised independently: some sheets in one volume carry dates a year apart. There are 15 rules:
1. Definitions (100 numbered terms, 1.1–1.100, over 8 sheets)
2. Tariff on File / Special Conditions
3. Character of Service (standard installation, secondary ≤600 V, primary overhead and underground, and a voltages table by class)
4. Application, Service Request or Contract
5. Predication of Rates and Rate Schedule Selection (premise, two meters, multi-dwelling, combined residential and non-residential use, optional rates, resale, default schedule)
6. Service Extensions and Modifications (margin credit/cost method, contribution, deposit return, commission-review option, multi-phase developments, provisional, auxiliary and excess facilities)
7. Customer Installation
8. Equipment on Customer's Premise (incl. tampering/theft and customer generation)
9. Metering (meter testing, meter failure, demand meter accuracy, missed-appointment trip charge with exemptions)
10. Deposit (residential / non-residential, creditworthiness, re-evaluation, interest)
11. Rendering and Payment of Bills (payment after due date, billing disputes, levelized billing, Social Security payment plan)
12. Disconnection and Reconnection (without notice, with notice, reconnection charges)
13. Service Curtailments
14. Limitations of Liability, Indemnification and Insurance
15. Miscellaneous and Non-Recurring Charges

170 IAC is cited inline at sub-rule level, e.g. "in accordance with the IURC Rules (170 IAC 4-1-9)", "170 IAC 4-1-14(B)". Statutes are cited too (IC 8-1-2-24, IC 4-4-33).

**AES Indiana Rules & Regulations (S2, S3).** About 42 pages, I.U.R.C. No. E-18. Each page header shows company name, tariff number and street address. The footer shows the effective date and the sheet designation in the form "1st Revised No. 200 Superseding Original No. 200". There are 37 short numbered rules, among them: Deposit (residential / non-residential, installment option, interest, refund criteria) · Line Extensions (Plans A/B, underground practices) · Meters, including an **AMI opt-out** provision with a one-time fee and a monthly manual-read charge · Incorrect Registration of Meter · Continuity of Supply · Release from Liability · Company Right to Discontinue Supply (immediate grounds; grounds requiring notice; medical postponement) · Bills, with a **due-date deferral plan** and an itemized schedule of reconnection, trip, dishonored-check, fraud field-call and missing-stub charges by time of day and location (meter, pole/transformer, after hours, Sunday, holiday) · Estimated Bills · Disconnection After Continued Non-Reading · Cancellation of Prior Rules. The citation style is "Commission Rule 16 [170 IAC 4-1-16]". A separate **Table of Contents sheet** (S3) lists every rate schedule, rider and rule with its sheet numbers and revision notation.

**I&M Indiana tariff book (S5, S6, S7).** Each sheet header shows: I.U.R.C. No. · "Original Sheet No. 3.x" / "First Revised Sheet No." · "Cancels" · company and state · **"Issued by: <officer name>, President, Fort Wayne, Indiana"** · effective date · "Issued under authority of the IURC, Cause No. …". Sheet 1 is a title sheet stating the effective date; there is a Table of Contents. Terms & Conditions run to 23–27 numbered items, including: Bills · Deposits · Denial or Discontinuance of Service · **Service, Reconnect and Trip Charges** (a schedule broken out by AMI opt-out, vault/manhole, pole disconnect by shift and day type, no-power trip, meter test or change) · Miscellaneous Customer Charges · Inspection · Liability · Extension of Service · Temporary Service · Voltages · **Meter Testing** (a set number of free tests, then a charge) · Customer-Initiated Power Quality Investigations · AMI Opt-Out · Customer-Requested Disconnection/Reconnection · budget-billing and prepay plans.

**CenterPoint Indiana South (S4).** I.U.R.C. No. E-14. Rate schedules occupy sheets 10–39, riders 50–64 and adjustments 65–76. General Terms & Conditions are "RULE 1…19" and include Interruptions and Damages, Disconnecting Service, **Payment of Bills—Reconnection Charge**, **Payment of Bills—Charge for Returned Payments**, Meter Testing, Voltages, Curtailment and Facilities Extensions. Non-recurring charges sit in a separate **"Appendix D – Other Charges"**. Footers show the effective date and "Page X of Y".

**Common artifacts across Indiana tariffs:** a title sheet; an index/TOC sheet listing every sheet with its revision; a voltages table; a non-recurring charges schedule split by time of day and location; disconnection rules split into "without notice" and "with notice"; deposit rules split into residential and non-residential; budget billing; a due-date deferral or senior/fixed-income plan; AMI opt-out; a tampering charge; returned payment; trip charge; customer generation (by cross-reference); and inline 170 IAC citations at sub-rule level. Tone is legal-contractual, in the third person ("The Company", "the Customer"), with no internal process detail.

**Length.** A full IOU GRR runs 35–45 sheets. Measured on NIPSCO's sheet density, that is roughly 12,000–18,000 words.

### (b) Gaps

| # | Gap | Severity |
|---|---|---|
| 13-1 | **No canonical sheet map.** T14 and T15 run in parallel and must cite "Tariff Rule 16, Sheet No. __". Each agent will invent different sheet numbers, rule numbers and fee amounts, and cross-document consistency (T90 check 6) will fail. | critical |
| 13-2 | **No canonical non-recurring charge amounts.** T13 Rule 16, T14 §11 (reconnection charges) and T15 (meter test fee, outside the pack's conditions) each invent amounts independently. | critical |
| 13-3 | **Study references contain real Indiana values from later editions** (e.g., S1 is effective 2025-07-01; S5 is 2024–2025). An agent can copy a notice period, deposit criterion or late-charge formula from them that is not in the pack, or that differs from the 2024-12-31 text. The spec says "form only" but does not name the risk or define the check. | critical |
| 13-4 | **Cause-number logic is internally inconsistent.** Every sheet header carries "IURC Cause No. 99012, approved 2024-05-15", yet most sheets are "Original" effective 2019-07-01. Sheets carry the cause under which *they* were approved. | major |
| 13-5 | **"Issued by: Robert Haskins, Manager, Rates & Tariffs"** is unrealistic. Indiana sheets are issued by an officer (S5/S7 use the President; others use a VP of Regulatory). A manager-level issuer would stand out to a regulatory professional. | major |
| 13-6 | **Missing standard sheets and rules:** title sheet (Sheet 1); index sheets listing every GRR sheet and every rate schedule by name and sheet; service area description; resale; temporary service; budget/levelized billing; due-date deferral or fixed-income plan; AMI opt-out; tampering/unauthorized use; customer generation (cross-reference only); "Rules governing where tariff silent". | major |
| 13-7 | **Secondary voltages are not given** in §1.1, so the agent must invent the voltage table. This is engineering data, not regulatory. | major |
| 13-8 | **Rate schedule names for the index are not given** (the spec only says "Sheets 50 through 118"). The agent will invent inconsistent codes, and other documents may mention "Rate RS". | major |
| 13-9 | **Length 7,000–10,000 words is too short** for 16 rules, 40–60 definitions and a charges schedule. Real GRRs are 35–45 sheets. | major |
| 13-10 | **Dual-numbering ambiguity.** "Rule 13" (disconnection) in RPL vs. "Rule 12" in NIPSCO. Clause IDs need a fixed rule/sheet relationship, e.g. `RPL-TAR-GRR-012:R13.4(b)`. Without a scheme, T10, T12 and T90 cannot resolve references. | major |
| 13-11 | **No markers for deposit interest, late-payment charge or winter moratorium.** Agents "know" Indiana deposit interest is set by Commission order, the late-charge formula, and the Dec–Mar moratorium (statutory, IC 8-1-2-121, likely **not** in a 170 IAC pack). A tariff without a winter rule looks odd; one with dates not in the pack fails T90. No guardrail tells the agent how to handle it. | critical |
| 13-12 | **No rendering requirement.** A tariff is recognized by its sheet layout. Markdown alone cannot show one sheet per page, the header block, or the issued/effective footer. | major |
| 13-13 | **No anti-summary rubric.** There are no minimums per rule (sub-rules, citations), no banned phrasing, and no rule that each sub-rule be contractual operative text rather than description. | major |
| 13-14 | AES landing page reference (`/rates-tariffs`) is not a document. Replace it with direct PDFs (S2, S3). Add I&M (S5) as the best example of the issued-by and cause-number header. | minor |
| 13-15 | No **change legend** or revision-tracking convention for a "Revised" sheet's changed text. Optional; some IOUs mark changes with (C)/(N)/(I) symbols in the margin, but I did not see this in the Indiana sheets I opened. | minor |

### (c) Ready-to-paste spec text — T13

```markdown
## T13 — Tariff for Electric Service, IURC No. 12: General Rules and Regulations

**Doc ID:** RPL-TAR-GRR-012 · **Vertical:** Policy & Governance · **Wave:** 2 · **Grounding:** `corpus/grounding/T13.json`
**Owner/Reviewer/Approver:** Aisha Thompson (P11) / Robert Haskins (P10) / Jonathan Pierce (P03)
**Issuing officer printed on every sheet:** Thomas Whitfield, Vice President, Regulatory & Government Affairs (P07). Owner, reviewer and approver appear only in front matter and the basis file, never on the sheets.
**Outputs:**
- `corpus/docs/RPL-TAR-GRR-012/RPL-TAR-GRR-012_v2024-06-01.md` (canonical, clause-ID-bearing)
- `corpus/docs/RPL-TAR-GRR-012/RPL-TAR-GRR-012.basis.json`
- `corpus/docs/RPL-TAR-GRR-012/render/RPL-TAR-GRR-012_v2024-06-01.pdf` (rendered tariff, see "Rendering")
- `corpus/docs/RPL-TAR-GRR-012/scripts/render_tariff.py`

### What this document is in the real world

The binding terms of service that an Indiana investor-owned electric utility files with the IURC and the IURC approves. It is a volume of numbered **tariff sheets**. Sheets are revised one at a time; each revised sheet cancels the prior revision of the same sheet number. The General Rules and Regulations (GRR) occupy the front of the volume; rate schedules and riders follow on later sheets. The text is contractual and third-person ("The Company shall…", "The Customer may…"). It contains no internal process detail: no system names, queues or staff titles other than the issuing officer. Indiana tariffs cite IURC rules inline at sub-rule level, e.g. "…in accordance with 170 IAC 4-1-9" or "Commission Rule 16 [170 IAC 4-1-16]". Copy that pattern using the pack's citation format.

**Study for sheet layout, rule order and tone ONLY (never copy text; never take any number, period, percentage, temperature, date or condition from them):**
- NIPSCO GRR (15 rules, 100 definitions, sheet header, inline 170 IAC cites): https://www.nipsco.com/docs/librariesprovider11/rates-and-tariffs/electric-rates/2025-to-current/general-rules-and-regulations.pdf
- AES Indiana Rules & Regulations (charges schedule by time and location; AMI opt-out; "Superseding" footer): https://www.aesindiana.com/sites/default/files/2021-02/Rules_and_Regulations_Effective_11-04-2020.pdf
- AES Indiana Table of Contents sheet: https://www.aesindiana.com/sites/default/files/2021-05/Table-of-Contents-50409-Effective-04-07-21.pdf
- I&M Indiana tariff book ("Issued by" / Cause No. header; Service, Reconnect and Trip Charges schedule): https://www.indianamichiganpower.com/lib/docs/ratesandtariffs/Indiana/IMINTB2004-30-2025.pdf
- CenterPoint Indiana South ("Appendix D – Other Charges"; rule list): https://www.centerpointenergy.com/en-us/Documents/RatesandTariffs/Indiana/Southwest/in-south-electric-tariff.pdf

> **Caution — later-edition values.** These references postdate or differ from the 2024-12-31 rule text in your pack. Their notice periods, deposit criteria, late-payment formulas, accuracy limits, test frequencies, temperature limits and look-back periods are **not** your values. If you find yourself typing a number you remember from them, stop and find it in the pack. If it is not in the pack, it does not go in a regulatory clause.

### Purpose in the demo

The tariff is the company's legally binding customer contract. Findings here are high-stakes and route to Legal. Any change triggers a tariff filing with the IURC (a real-world second step the platform should show).

### Canonical sheet map (use exactly; T14, T15, T17, T10 and T12 reference these numbers)

| Sheet No(s). | Content | Revision level in force | Effective | Approved under |
|---|---|---|---|---|
| 1 | Title sheet | Third Revised (cancels Second Revised) | 2024-06-01 | Cause No. 99012 |
| 2–3 | Index of Sheets (all GRR sheets, then every rate schedule and rider by code, name and sheet range) | Third Revised | 2024-06-01 | Cause No. 99012 |
| 4 | Service Area (the 14 counties in §1.1, by county, "in whole or in part") | Original | 2019-07-01 | Cause No. 98876 |
| 5–11 | Rule 1 — Definitions | Sheets 5–9 Original; Sheets 10–11 First Revised | 2019-07-01 / 2024-06-01 | 98876 / 99012 |
| 12 | Rule 2 — Tariff on File; Commission Rules Govern | Original | 2019-07-01 | 98876 |
| 13–14 | Rule 3 — Character of Service | Original | 2019-07-01 | 98876 |
| 15–16 | Rule 4 — Application for Service; Contracts; Customer Identification | First Revised | 2021-10-01 | 98951 |
| 17–18 | Rule 5 — Rate Schedule Selection; Resale; Temporary Service | Original | 2019-07-01 | 98876 |
| 19–23 | Rule 6 — Line and Service Extensions | First Revised | 2021-10-01 | 98951 |
| 24 | Rule 7 — Customer Installation and Wiring; Inspection | Original | 2019-07-01 | 98876 |
| 25–26 | Rule 8 — Company Equipment on Customer Premises; Access; Meter Location; Tampering | Original | 2019-07-01 | 98876 |
| 27–29 | Rule 9 — Metering; Meter Tests; AMI Opt-Out | Second Revised | 2024-06-01 | 99012 |
| 30–31 | Rule 10 — Deposits and Creditworthiness | First Revised | 2021-10-01 | 98951 |
| 32–34 | Rule 11 — Billing and Payment; Delinquency; Estimated Bills; Budget Billing; Due-Date Extension | Second Revised | 2024-06-01 | 99012 |
| 35–36 | Rule 12 — Billing Adjustments | First Revised | 2024-06-01 | 99012 |
| 37–41 | Rule 13 — Disconnection and Reconnection of Service | Second Revised | 2024-06-01 | 99012 |
| 42–43 | Rule 14 — Service Interruptions; Continuity; Curtailment | Original | 2019-07-01 | 98876 |
| 44 | Rule 15 — Limitation of Liability; Indemnification | Original | 2019-07-01 | 98876 |
| 45–46 | Rule 16 — Schedule of Non-Recurring Charges | Second Revised | 2024-06-01 | 99012 |
| 47–49 | Reserved for Future Use | Original | 2019-07-01 | 98876 |
| 50–118 | Rate schedules and riders (named in the index only; not reproduced) | — | — | — |

Fictional prior causes: **Cause No. 98876** (general rate case, approved 2019-06-19); **Cause No. 98951** (tariff revisions, approved 2021-09-22). Current: **Cause No. 99012**, approved 2024-05-15, effective 2024-06-01. Every sheet in force must comply with the pack (law as of 2024-12-31), including Original sheets.

**Rate schedule index entries (Sheets 50–118, names only):** RS Residential Service (50–52) · RS-TOU Residential Time-of-Use (53–55) · GS General Service, Secondary (56–59) · GS-D General Service Demand (60–63) · LP Large Power, Primary (64–68) · LPT Large Power, Subtransmission 69 kV (69–72) · IS Interruptible Service Rider (73–75) · SL Street Lighting, Company-Owned (76–80) · MSL Municipal Street Lighting, Customer-Owned (81–83) · OL Outdoor Area Lighting (84–86) · Rider NM Net Metering (87–89) · Rider EDR Economic Development (90–92) · Rider PPA Purchased Power Adjustment (93–95) · Rider TDSIC Distribution System Improvement (96–98) · Rider EE Energy Efficiency (99–101) · Rider BB Budget Billing (102) · Rider SEC Securitization/Other Charges (103–105) · Reserved (106–118). Customer classes must reconcile with §1.1 counts. Do not state any rate values.

### Required structure

**Sheet header** — render at the top of every sheet as a fixed block. In Markdown, use a 2-column table immediately after a `<!-- sheet: n -->` comment.

    ROCKRIDGE POWER & LIGHT COMPANY                          IURC No. 12
    Lafayette, Indiana                                       <Revision> Sheet No. <n>
    Tariff for Electric Service                              Cancels <Prior Revision> Sheet No. <n>   (omit for Original)
    GENERAL RULES AND REGULATIONS — RULE <r>: <RULE TITLE>
    Issued: <date>                                           Effective: <date>
    Issued by: Thomas Whitfield, Vice President, Regulatory & Government Affairs
    Issued under authority of the Indiana Utility Regulatory Commission, Order in Cause No. <cause> dated <approval date>

- Issued date = 2 to 15 days after the approval date of that sheet's cause. Effective dates are as in the sheet map.
- A rule that runs past one sheet continues on the next sheet number with the same header and "(Continued)". A sheet ends with "(Continued on Sheet No. n+1)" where applicable.
- Clause IDs: `RPL-TAR-GRR-012:R<rule>.<sub>` (e.g., `R13.4`, `R13.4(b)`, `R16.T-3` for charge-table row 3). Each sheet also gets `<!-- sheet: n -->` so T10/T12 can resolve sheet references.

**Sheet 1 — Title sheet:** company name; "Tariff for Electric Service"; "IURC No. 12"; "Cancels IURC No. 11"; "Applicable in the territory described on Sheet No. 4"; statement that the rates, rules and regulations herein govern electric service; issuing officer; filing address (§1.1 HQ).

**Sheets 2–3 — Index:** a table `Sheet No. | Title | Revision in force | Effective`, covering every sheet 1–49 and then every rate schedule/rider range above.

**Sheet 4 — Service Area.**

**Rules** (each rule starts on a new sheet; clause-ID every sub-rule). Minimum sub-rules per rule in brackets.
1. **Definitions** [60–90 numbered terms, 1.1…]. Include every term the pack defines, with identical meaning and the pack's citation after the definition, plus operational terms used later (AMI, AMI opt-out, billing period, budget billing, business day, delinquent bill, field collection visit, meter tampering, premises, primary/secondary service, remote disconnection, returned payment, service drop, service lateral, temporary service, etc.). Where the pack and the Company's term differ, the pack's meaning governs.
2. **Tariff on file; Commission rules govern** [≥4]: tariff availability for inspection at HQ and on the web; conflicts; where the tariff is silent, the IURC's rules apply; Company's right to file changes; no agent may modify.
3. **Character of service** [≥6]: 60-hertz alternating current; standard secondary voltages from §1.6 Table V; primary (12.47 kV, 34.5 kV) and subtransmission (69 kV) availability conditions; voltage variation and frequency statements **only as stated in the pack** (if the pack states no limit, state none); single- vs. three-phase availability; customer responsibility for protective equipment.
4. **Application for service; contracts; customer identification** [≥6]: written or oral application; required identification (company practice — list acceptable forms); contract terms for non-residential; refusal of service grounds **only as in the pack**; change of occupancy; landlord/tenant accounts.
5. **Rate schedule selection; resale; temporary service** [≥6]: assistance in selecting a rate; customer's right to change schedules; multiple dwellings and combined use; resale prohibited except as permitted; temporary service charges at cost (company practice).
6. **Line and service extensions** [≥10]: restate the pack's extension rule terms, every variance, refund and commission-review provision; RPL's allowance and contribution methodology as company practice, with a worked formula; underground in subdivisions; relocation at customer request.
7. **Customer installation and wiring; inspection** [≥4].
8. **Company equipment on premises; access; meter location; tampering** [≥7]: meter location **per the pack**; access rights; customer's duty to protect; unauthorized use and tampering (charge by reference to Rule 16); customer-owned generation by reference to Rider NM only (no 170 IAC 4-4.x restatement).
9. **Metering; meter tests; AMI opt-out** [≥8]: Company furnishes meters; periodic testing by reference to the Company's meter testing program; customer-requested tests, every request condition, fee condition and commission-supervised test right **exactly as in the pack**; customer's right to witness if in the pack; AMI opt-out terms (company practice; fees from §1.6).
10. **Deposits and creditworthiness** [≥8 if the pack has a deposit section; otherwise ≥5 company-practice sub-rules with no citations]: residential vs. non-residential; when required; amount; installments; interest (only as the pack states — if the pack defers the rate to Commission order, say exactly that and state no rate); refund and review; transfer.
11. **Billing and payment; delinquency; estimated bills; budget billing; due-date extension** [≥10]: billing period; bill content **per the pack**; due date and delinquency **per the pack**; late payment charge **only as the pack states it** (if the pack is silent, Rule 11 states only "as set forth in the applicable rate schedule"); estimated bills and their limits per the pack; budget billing (Rider BB); due-date extension for fixed-income customers (company practice); payment channels from §1.5; returned payments.
12. **Billing adjustments** [≥6]: one sub-rule each for fast meter, slow meter, non-registering meter, and other billing errors (incl. wrong rate, multiplier, crossed meters); each with method, look-back period, refund/back-bill rule and interest **exactly as in the pack**; Company practice on payment arrangements for back-bills, labeled.
13. **Disconnection and reconnection** [≥14]: customer-requested disconnection; disconnection **without** notice (grounds per the pack); disconnection **with** notice (grounds, notice period, method and notice content per the pack); prohibited times and conditions per the pack; medical certification per the pack; energy-assistance and seasonal protections per the pack (see "Statutory protections" below); payment arrangements per the pack; disputes pending; reconnection timing and conditions per the pack; reconnection charges by reference to Rule 16; customer's right to contact the IURC (contact block from §1.6).
14. **Service interruptions; continuity; curtailment** [≥6]: no guarantee of continuous service; planned interruption notice per the pack; emergency curtailment priorities (company practice); restoration priorities.
15. **Limitation of liability; indemnification** [≥5]: company practice; no citations unless the pack supports one.
16. **Schedule of non-recurring charges** [the full table in §1.6 Table F, with `ID` column `R16.T-n`]: for each charge, state the amount and a **condition statement** ("This charge applies when… It does not apply when…") consistent with the pack. Where the pack restricts when a charge may be imposed (e.g., meter test fee conditions, reconnection), the condition text restates the pack with citation. If the pack sets or caps an amount, the pack's amount governs: use it, and report the deviation from §1.6 to the orchestrator in your final message.

### Statutory protections not in the pack

The winter disconnection protection for energy-assistance recipients and some customer-complaint rights come from Indiana statutes (Title 8), not from 170 IAC. If your pack contains the governing text, follow it like any other pack section. If it does not:
- Write a sub-rule stating that the Company complies with the protections in the named statute (e.g., "IC 8-1-2-121"), as an `out_of_scope_reference` clause.
- **State no dates, durations, eligibility thresholds or temperatures for it.**
- Record it under `out_of_scope_references` in the basis file.

Never fill the gap from memory or from the OUCC FAQ.

### Depth and anti-summary rules

- Length: **11,000–15,000 words** of body text (excluding front matter and HTML comments), across Sheets 1–49.
- Every sub-rule is operative contractual text (a duty, right, condition or charge), not a description of the rule.
- Banned phrasing: "this section describes", "in general", "as applicable" (without saying what applies), "relevant regulations", "etc." inside a regulatory sentence, "may be subject to" without the condition.
- At least **90 inline citations** in total. Rules 9, 11, 12 and 13 must carry a citation on every sub-rule that restates a requirement.
- Tables required: Index (Sheets 2–3), Standard Voltages (Rule 3), Extension allowance formula (Rule 6), Charges (Rule 16). Recommended: Deposit summary (Rule 10).

### Rendering (required)

Use the **`pdf` skill** (reportlab), deterministic, via `scripts/render_tariff.py` reading the canonical Markdown:
- US Letter, portrait. **One tariff sheet per PDF page.** Size each sheet's text to fit one page. If it cannot fit, add a decimal sub-sheet ("Sheet No. 38.1", the convention I&M uses) with the same revision and dates, list it in the Index, and never let a sheet span two PDF pages.
- Header block exactly as above, in a ruled box; rule title in bold caps.
- Footer: left "Issued: <date>", right "Effective: <date>", centre "IURC No. 12 — Sheet No. <n>".
- Strip `<!-- clause -->` and `<!-- sheet -->` comments. Clause IDs must **not** appear in the PDF.
- Body: serif font, 10.5–11 pt; numbered sub-rules hang-indented; charges table with ruled grid.
- Expected output: 49 pages (one per Sheet No. 1–49, reserved sheets included as "Reserved for Future Use" pages), plus one page for each continuation sheet you create.

The Markdown file remains canonical. The PDF is derived and must contain the same text.

### Self-check (in addition to §2.6 and §3.8)

1. Every sub-rule in Rules 9, 11, 12 and 13 carries a citation and appears in the basis file with parameters.
2. Every charge in Rule 16 has a condition statement consistent with the pack, and its amount equals §1.6 Table F (or the pack, if the pack sets it — reported).
3. Sheet numbers, revision levels, effective dates and causes match the canonical sheet map exactly. Every sheet with a "Revised" level has a "Cancels" line.
4. **Value ledger:** every number, percentage, time, day count and dollar amount in the document is in the basis file's `value_ledger` with source `pack` (with `s1_quote`), `section1` or `section1.6`. Anything else must be removed.
5. No number, date or temperature for a statutory protection appears unless it is in the pack.
6. The PDF renders with one sheet per page; a text-parity check (normalized PDF text contains every Markdown sentence) passes.
7. Word count and citation count meet the minimums.
```

---

## T14 — Disconnection, Reconnection & Winter Protection Procedure

### (a) Real-world anatomy

**Tariff-side disconnection terms (S2, S5, S8, S11).**
- AES Indiana (S2) splits **immediate** grounds (emergency, tampering/fraud, hazard, order) from grounds requiring **notice** (non-payment, rule violation, unsafe condition, contract breach). It adds a medical postponement/payment-extension clause and disconnection after continued non-reading, with reconnection and trip charges split by meter vs. pole/transformer and by business hours, after hours, Sunday and holiday.
- I&M (S5) adds safety restrictions on remote disconnection (days of week, temperature) as company tariff terms.
- AES Ohio (S8) has a separate fraud/tampering investigation notice with its own content elements and a customer meeting right.
- Avista (S11) lists the notice content elements (reasons, earliest disconnection date, amount to avoid disconnection, dispute procedure and the commission's toll-free number). It requires a good-faith personal contact attempt at the premises and a conspicuous notice if no one is reached, plus medical-certificate content and duration, time-payment agreements, restricted hours and days, and restoration conditions.
- Avista Rule 5 (S12) mandates **notice language blocks**: a bold "act now" line and **multilingual translation-assistance lines** with a phone number.

**Policy format (S9).** Washington Electric Co-op Policy #12 is organized as: Definitions (7) → General rule → Exceptions (8 enumerated prohibitions) → **Disconnection notice content (9 enumerated elements)** → Timing and field procedures (hours, contact on arrival) → Winter protections → Reconnection (time commitment) → Fees (visit, reconnect, overtime) → Dishonored checks → Reporting.

**Internal SOP format (S13).** Duquesne Light's Field Collections procedure, filed with the PA PUC in 2025, has: Document control table (version, date, change description, business-process-owner approval) → Objective → Scope → Regulatory requirements (code sections) → **numbered steps with role, system and decision branches** (door knock; apartment access; minor answers; no response; phone contact; leave posting; issue disconnect command through the CIS/mobile workforce/remote-disconnect systems; record notice placement; call scheduling with a named internal phone number) → **swimlane flow diagram** (Credit & Collections vs. Credit Field Operations) → dependencies and training schedule. Five pages including cover letter. It is a narrow process doc, so a full IOU disconnection SOP would bundle several of these.

**Forms.** The medical certification form (S14) has three signed sections: patient (with authorization to release health information), account holder (account number, service type), and certifying professional (condition category, equipment, license number, contact, signature). The utility's form carries instructions on the return deadline, the hold period and assistance links (211). Durations are state-specific — do not use.

**Indiana context (S10, context only).** The OUCC explains a winter protection tied to Energy Assistance Program eligibility, written proof from the EAP intake agency (local Community Action Agency, via IHCDA), a recommendation to make good-faith partial payments, and 211. Its dates and eligibility are **not** to be used. The protection is statutory (IC 8-1-2-121) and may not be in a 170 IAC pack.

**Artifacts a regulatory professional expects in an IOU disconnection SOP:**
- a collection-cycle timeline (bill → due → delinquent → notice → eligible → field order → disconnect → reconnect)
- a decision table of allowed and prohibited conditions with CIS hold codes
- the notice template with every required element
- a door tag
- the medical certificate
- an EAP protection letter
- a payment arrangement agreement
- a contact-center script
- field steps by system (CIS, AMI head-end, mobile work orders)
- remote-disconnect safety checks
- reconnection timing by method and time of day
- after-hours escalation
- erroneous-disconnection handling
- QA sampling
- a records list

### (b) Gaps

| # | Gap | Severity |
|---|---|---|
| 14-1 | **Winter protection is in the title, but its legal source is likely not in the pack** (statute IC 8-1-2-121 vs. 170 IAC). The agent will either invent dates from memory or OUCC (fails T90) or leave a hollow section (unrealistic). There is no rule for this case. | critical |
| 14-2 | **CIS hold codes, door-tag form number, letter form numbers, script ID and training module IDs are not canonical.** T17 (dispute hold) and T13 run in parallel and will diverge. `CS-F-012-DT` is used but is not in §1.5. | critical |
| 14-3 | **Reconnection charges by reference to Rule 16 have no sheet number or amounts** (see 13-1/13-2). | critical |
| 14-4 | **Study references carry other states' values** (Vermont temperatures in S9, Oregon hours and medical-certificate durations in S11, Ohio fraud notice periods in S8). No explicit prohibition. | critical |
| 14-5 | **No payment-arrangement section** (only inside §9 for EAP). Payment arrangements are central to Indiana disconnection practice and probably to the pack (170 IAC 4-1-16 family). Needs its own section and form (`CS-F-016`). | major |
| 14-6 | **No collection-cycle timeline table, no field order types, no remote-disconnect safety checks** (temperature/weather check, AMI connectivity, "meter on" verification, critical-care flag check, payment-posting sweep before dispatch). | major |
| 14-7 | **No notice language blocks:** Spanish translation line, TTY/Relay line, "act now" banner, IURC contact block, energy-assistance referral block (211/IHCDA). A notice without these looks fake to a regulator. | major |
| 14-8 | **Missing scenarios:** multi-unit/landlord-ratepayer buildings (third-party/occupant notice, if in the pack); non-residential accounts (different notice per the pack); customer-requested disconnection; disconnection for non-payment vs. safety/tampering (cross-ref to tariff R13); erroneous disconnection and restoration; deceased account holder; bankruptcy (company practice). | major |
| 14-9 | **No delegation-of-authority / override table** (who can release a hold, waive a reconnection charge, authorize after-hours reconnect, override a remote-disconnect safety check). | major |
| 14-10 | **No QA/monitoring section** (daily exception report, monthly sample audit of notices vs. field orders, KPI). | major |
| 14-11 | **Length 4,500–6,500 words including six templates is thin.** Full letter templates plus a decision table plus field steps reach ~9,000 words in a real document. | major |
| 14-12 | **No rendering requirement.** The door tag and letters need print-realistic layout. | major |
| 14-13 | The study references are tariff and policy documents, not SOPs. Add S13 as the SOP-format reference and S14 for form layout. | minor |
| 14-14 | Front-matter example in §3.1 uses T14 with `supersedes: "5.0 (2024-01-15)"`. Make this canonical in §1.4 so T03 matches without reconciliation. | minor |

### (c) Ready-to-paste spec text — T14

```markdown
## T14 — Disconnection, Reconnection & Winter Protection Procedure

**Doc ID:** RPL-CS-PRO-004 · **Vertical:** Policy & Governance · **Wave:** 2 · **Grounding:** `corpus/grounding/T14.json`
**Owner/Reviewer/Approver:** Jasmine Carter (P15) / Karen Mitchell (P13) / Jonathan Pierce (P03)
**Supersedes:** 5.0 (2024-01-15)
**Outputs:**
- `corpus/docs/RPL-CS-PRO-004/RPL-CS-PRO-004_v5.1.md` (canonical)
- `corpus/docs/RPL-CS-PRO-004/RPL-CS-PRO-004.basis.json`
- `corpus/docs/RPL-CS-PRO-004/render/RPL-CS-PRO-004_v5.1.docx` and `.pdf`
- `corpus/docs/RPL-CS-PRO-004/scripts/render_docx.js` (or `.py`)

### What this document is in the real world

The internal standard operating procedure that Credit & Collections, the Customer Contact Center and Field Service technicians follow before, during and after disconnecting service for non-payment: protections (medical, energy assistance, seasonal/weather where the law provides them), notices, payment arrangements, field execution (remote AMI and manual), and reconnection. It is the operational counterpart of Tariff Rule 13 (RPL-TAR-GRR-012, Sheets 37–41) and Rule 16 (Sheets 45–46). Regulators audit against it during complaint investigations. It is written for practitioners: numbered steps with an actor, a system action and a record for each.

**Study for structure and tone ONLY (never take any value from them — they are other states' rules or later editions):**
- Duquesne Light Field Collections procedure (internal SOP format: doc-control table, numbered steps with role and system, decision branches, swimlane): https://www.puc.pa.gov/pcdocs/1902417.pdf
- AES Indiana Rules & Regulations, Rules 25–28 (Indiana grounds with/without notice; reconnection and trip charge structure): https://www.aesindiana.com/sites/default/files/2021-02/Rules_and_Regulations_Effective_11-04-2020.pdf
- Washington Electric Co-op Policy #12 (enumerated prohibitions and notice elements): https://www.washingtonelectric.coop/wp-content/uploads/2019/04/Disconnection-of-Electrical-Service.pdf
- Avista Rule 11 and Rule 5 (notice content list; field contact; notice language blocks): https://www.myavista.com/-/media/myavista/content-documents/our-rates-and-tariffs/or/rule-11-discontinuance-and-restoration-of-service.pdf · https://www.myavista.com/-/media/myavista/content-documents/our-rates-and-tariffs/or/rule-05-special-information-required-on-forms.pdf
- WPS Medical Certification Form (three-signatory form layout only): https://www.wisconsinpublicservice.com/payment-bill/pdf/medical.pdf
- Indiana OUCC winter moratorium FAQ (context only: who certifies EAP eligibility, 211, good-faith payments): https://secure.in.gov/oucc/about-your-rates/winter-disconnection-moratorium-frequently-asked-questions

> **Caution.** These sources contain hours of day, days of week, temperatures, notice periods, hold durations and certificate validity periods from Pennsylvania, Vermont, Oregon, Michigan, Ohio and later Indiana editions. **None of them may appear in this document.** Every such value comes from the pack, or the clause states no value.

### Purpose in the demo

The single richest document for fine-print findings: notice periods, required notice content, protected periods, eligibility evidence, prohibited disconnection conditions and reconnection timing all live here and in its templates.

### Statutory protections not in the pack (winter protection)

Before drafting, check whether the pack contains the text governing the winter/seasonal protection for energy-assistance recipients.
- **If it does:** restate every parameter with citation, like any pack section.
- **If it does not:**
  - §9 still exists and is fully operational: eligibility evidence handling (what document RPL accepts from the EAP intake agency — company practice), CIS hold code `HEAP`, contact-center steps, letter `CS-F-013`, payment-arrangement offer.
  - The protected period itself is stated only as "the period provided by IC 8-1-2-121" (clause type `out_of_scope_reference`), with **no dates, durations or eligibility thresholds**.
  - The operating calendar uses the wording "the statutory protection period as published annually by Regulatory Affairs (P08)".

Never take the dates from memory, the OUCC FAQ or any utility website.

### Required structure

Follow §3.3 order. Minimum numbered clauses per section in brackets.

1. **Purpose** [1–2 paragraphs]
2. **Scope & applicability** [≥5]: residential and non-residential accounts; Credit & Collections, Contact Center, Field Service, Customer Advocacy; customer-requested and non-payment disconnections; safety/tampering disconnections (by reference to the tariff and RPL-SAF-PRO-009 where applicable); third-party collection vendors excluded.
3. **Definitions** [≥18], consistent with the pack (delinquent bill, disconnection, reconnection, remote disconnection, field collection visit, medical certificate, energy assistance recipient, payment arrangement, ratepayer/occupant where the pack distinguishes them, business day, etc.). Pack-defined terms carry the pack citation.
4. **Regulatory basis**: table `Citation | Heading | What it governs in this procedure | Clause IDs`.
5. **Roles & responsibilities**: table `Role | Named person or position | Responsibilities | Authority`. P15, P13, P17, P03, P14; Contact Center Team Leads; Field Service Technicians; Credit Analysts; Regulatory Affairs (P08) for the annual protection calendar.
6. **Collection cycle overview**: timeline table `Step | Day reference | System event | Actor | Record`. Day references that are regulatory come from the pack with citation; company scheduling is labeled "Company practice". Include the CIS batch jobs (bill print, delinquency flag, notice generation, eligibility sweep, field-order creation, payment-posting sweep before dispatch).
7. **Eligibility for disconnection** — decision table with columns `ID · Condition · Allowed? · Required evidence · Citation · CIS hold code · Who may release`. One row per permitted ground, per prohibited condition (time of day, day of week, pending dispute, medical certificate, energy assistance, seasonal/weather — each **only** as stated in the pack), and per company safety hold (critical-care flag `HCRT`, remote-disconnect safety checks). Minimum 15 rows.
8. **Notice requirements** [≥12]: timing, delivery method, one clause per required content element (each mapped to the `CS-F-012` field that carries it), second/final notice practice, notice to occupants or third parties where the pack requires it, non-residential notice, re-notice when an arrangement is broken (per the pack).
9. **Medical certification** [≥8]: who may certify, method of initial notice (oral/written per the pack), duration and renewals per the pack, required certificate content, CIS hold `HMED`, follow-up when the certificate expires, interaction with payment arrangements.
10. **Energy assistance and seasonal protections** [≥8]: per the pack; otherwise per "Statutory protections" above.
11. **Payment arrangements** [≥8]: terms the pack requires the utility to offer or allow; RPL's standard arrangement options (company practice, `CS-F-016`); breach and re-notice per the pack; CIS hold `HPAY`.
12. **Field disconnection steps** [≥15 numbered steps]: pre-dispatch verification in CIS (holds, payments, open disputes `HDSP`/`HIURC`, critical care) and AMI HES (meter status, connectivity); remote disconnect command and safety checks (company practice: weather check, AMI "load-side voltage absent" confirmation); manual disconnection; on-premise contact attempt; door tag `CS-F-012-DT`; customer presents payment proof or a medical claim at the door; unsafe conditions; photo and GPS capture in the mobile work order; close-out codes.
13. **Reconnection** [≥10]: conditions; timing commitments per the pack (and internal targets labeled); remote vs. field; after-hours handling and on-call escalation; charges by reference to Tariff Rule 16, Sheet Nos. 45–46 (amounts from §1.6 Table F); waiver authority; erroneous disconnection (immediate restoration, no charge, incident review).
14. **Disputes during the disconnection process** [≥5]: hand-off to RPL-CS-PRO-011; hold `HDSP` on disconnection while a dispute is pending if and as stated in the pack; IURC complaint hold `HIURC`; release rules.
15. **Delegation of authority and overrides**: table `Action | Who may authorize | Record`.
16. **Quality assurance and monitoring** [≥5]: daily exception report; monthly sample of 50 disconnections audited for notice compliance; KPI list reported to P13.
17. **Records & retention** [≥6]: record type, system of record, retention by reference to RPL-LEG-RRS-001 series IDs.
18. **Training**: CS-T-04 new hire; annual refresher; field technician module FS-T-12; completion tracked in the LMS.
19. **Related documents**: RPL-TAR-GRR-012 (Rules 13, 16), RPL-CS-PRO-011, RPL-LEG-RRS-001, RPL-CMP-REG-001, RPL-SAF-PRO-009.
20. **Revision history**: 3–4 entries, last = 5.0 (2024-01-15), current 5.1. Change reasons must not reference future law.
21. **Approval block**.

**Appendices (each field carries a clause ID `App-X.Fn`; every regulatory content element is a numbered field):**
- **App-A** Disconnection Notice `CS-F-012` (full letter). Include, in addition to every pack-required element: "ACT NOW" banner; account and service address block; amount to avoid disconnection; payment channels (§1.5); payment-arrangement and assistance block (211, IHCDA/EAP intake); medical-certificate block; dispute block (RPL Customer Advocacy contact); IURC Consumer Affairs contact block (§1.6 Table C); Spanish translation line; TTY/Relay line. The Spanish and TTY lines and the "ACT NOW" banner are company practice — no citation unless the pack requires them.
- **App-B** Door tag `CS-F-012-DT` (front and back; half-page layout; technician ID, date/time, reason code, reconnection instructions).
- **App-C** Medical Certificate `CS-F-015` (patient/occupant, account holder, certifying professional sections; content fields per the pack).
- **App-D** Energy Assistance Protection Letter `CS-F-013`.
- **App-E** Payment Arrangement Agreement `CS-F-016`.
- **App-F** Contact-center script `CS-S-04` (branching: can pay / arrangement / medical / EAP / dispute / already disconnected).
- **App-G** Reconnection Confirmation Letter `CS-F-014`.
- **App-H** Field close-out and CIS code reference (hold codes, field order types, close-out codes from §1.6 Table K).
- **App-I** Swimlane process flow (Contact Center · Credit & Collections · Field Service · Customer Advocacy), as a Mermaid diagram in the Markdown and an image in the rendering.

### Depth and anti-summary rules

- Length: **8,000–11,000 words** of body text including appendices.
- At least **45 clause IDs** in the body and **60 field IDs** across the appendices.
- Every pack-derived protection, notice element and timing rule appears both in the body and, where customer-facing, in the relevant template field. The basis file links both clause IDs.
- Every step in §12 names an actor, a system action and a record.
- Banned phrasing: "follow applicable regulations", "as required by law" (without a citation), "in a timely manner", "appropriate action", "etc.", "and so on".

### Rendering (required)

Use the **`docx` skill** to produce `render/RPL-CS-PRO-004_v5.1.docx` from the canonical Markdown, then convert it to PDF (LibreOffice headless) for `render/…pdf`:
- Cover page: title block and document-control table (Doc ID, title, version, effective, approved, law as-of, owner/reviewer/approver with titles, next review, classification, supersedes).
- Header on every page: "Rockridge Power & Light Company | RPL-CS-PRO-004 | Disconnection, Reconnection & Winter Protection Procedure".
- Footer on every page: "Version 5.1 | Effective 2025-02-10 | Internal | Uncontrolled when printed" and "Page X of Y".
- Auto table of contents after the cover.
- Each appendix starts on a new page. Forms use bordered tables with fill-in cells and signature/date lines. The door tag is a half-page, two-panel layout. Letters use RPL letterhead (name, HQ address, phone, web from §1.1).
- Clause-ID comments are stripped. Clause IDs do not appear.
- Expected length: 28–40 pages.

### Self-check (in addition to §2.6 and §3.8)

1. Every row in the §7 decision table has a citation, or is labeled company practice.
2. Every hold code, form number, script ID and fee matches §1.6 exactly.
3. The value ledger contains every number in the document. No hour of day, day of week, temperature or duration appears unless it comes from the pack or §1.6.
4. If the winter protection text is not in the pack, the document contains no protection dates or durations, and the basis file lists the statute under `out_of_scope_references`.
5. Every required notice element is a field in App-A and is mapped in the basis file.
6. The docx/pdf render passes text parity, and the page count is within range.
```

---

## T15 — Meter Test Request & Billing Adjustment Procedure

### (a) Real-world anatomy

**Indiana tariff side (S1, S5).**
- NIPSCO Rule 9 covers: meters installed by the Company; meter testing "in accordance with" 170 IAC 4-1-9; customer may request a test at reasonable intervals; adjustment for meter failure using estimated consumption by engineering calculation per 170 IAC 4-1-14; an adjustment-period formula; demand meter accuracy tolerance with correction of prior readings; missed-appointment trip charge with exemptions (cancellation notice, medical emergency), appointment windows and remote-read alternatives.
- I&M includes a Meter Testing term (a number of free tests, then a charge by reference to its charges item) and a "meter test or change" charge line.
- These are the clauses T15 operationalizes.

**Request forms (S15).** The NJ BPU "Application for Electric Meter Test" has: reference number, name/date, service address/phone, email, mailing address, utility, meter manufacturer and serial number. It also states the accuracy test basis (state-specific weighting — do not use), instructs the customer **not to allow meter removal until instructed**, explains that staff witness the test, and gives the submission channel and a fee statement. It has no signature line.

**Municipal policies (S16, S17).**
- Le Sueur: pre-test reread at no cost → formal test with deposit → refund and adjustment if inaccurate, forfeiture if accurate → look-back limit. A request form with signature acknowledging fee terms.
- Marquette BLP: sections for overcharging, back-billing, meter accuracy, test fees; a scenario table (overbilling, normal and undetectable underbilling, fast meter, slow meter, non-registering — estimated from similar periods); minimum amounts for refunds and back-bills; payment plans for back-bills; refunds to former customers at last known address; fraud/tampering exception.
- All their values are local and not usable.

**Practitioner content expected in an IOU procedure:**
- high-bill investigation before a test (AMI interval data review, register read, check for crossed meters or wrong multiplier)
- intake channels and the written-request rule
- eligibility and fee decision table
- appointment scheduling and witness rights
- in-place vs. shop test
- chain of custody (seal numbers, tag, sealed bag/box, storage, retention period of the removed meter)
- test equipment traceability
- test points (full load, light load, power factor, demand)
- as-found/as-left
- report letter content
- commission-supervised test handling
- billing adjustment method by scenario with CIS transaction codes, approval thresholds, refund method (credit vs. check), former-customer refunds, back-bill payment arrangements, and customer notice letter
- worked examples

### (b) Gaps

| # | Gap | Severity |
|---|---|---|
| 15-1 | **Fee amount and fee-condition consistency with T13 Rule 9/16 is not ensured**, since they are generated in parallel. Needs §1.6 Table F plus the rule "conditions and any amount the pack sets come from the pack". | critical |
| 15-2 | **High import risk for other jurisdictions' accuracy limits, load weighting, free-test frequency and look-back limits** (NJ, MN and MI sources). The agent may also apply NIPSCO's adjustment-period formula from memory. No explicit guardrail. | critical |
| 15-3 | **Worked examples (§13) have no computational check.** Numeric errors or a method inconsistent with the pack are likely, and T90's value check cannot catch arithmetic. Needs a script and a basis-file record. | critical |
| 15-4 | **No high-bill investigation pre-step.** In real practice most meter-test requests start as high-bill complaints and are triaged through AMI data first. Without it the document reads as a rule summary. | major |
| 15-5 | **No chain-of-custody specifics** (seal and tag numbers, `MTR-F-013` tag, storage location in the Meter Shop, retention of the removed meter, customer notice before disposal if the pack requires it). | major |
| 15-6 | **No billing adjustment authority table** (dollar thresholds for analyst, supervisor and director approval) and no CIS adjustment transaction codes. | major |
| 15-7 | **No handling of AMI vs. AMR vs. electromechanical meters**, despite §1.1 giving the fleet mix (7,350 legacy electromechanical). Test methods differ. | major |
| 15-8 | **Two-signature approval block format is undefined** (front matter has no approver field example; T03 needs an `approver_id` value). | major |
| 15-9 | **Missing scenarios:** demand meters; crossed meters/switched service; wrong multiplier; wrong rate schedule; unmetered load; tampering-caused registration error (exclude from the standard adjustment and route to theft — company practice unless the pack addresses it); former customers. | major |
| 15-10 | **No relationship to T18** (Meter Testing Program) for test equipment certification and standards traceability. | minor |
| 15-11 | **Length 3,500–5,500 words is thin** for 12 core sections, three worked examples and four templates. | major |
| 15-12 | **No rendering requirement.** | major |

### (c) Ready-to-paste spec text — T15

```markdown
## T15 — Meter Test Request & Billing Adjustment Procedure

**Doc ID:** RPL-CS-PRO-007 · **Vertical:** Policy & Governance · **Wave:** 2 · **Grounding:** `corpus/grounding/T15.json`
**Owner/Reviewer:** Luis Hernandez (P18) / Steven Park (P14) — two-signature document (front matter `approver: null`; approval block shows "Prepared and approved by" P18 and "Reviewed and approved by" P14, each with a date ≤ 2025-02-12)
**Supersedes:** 2.1 (2023-11-06)
**Outputs:**
- `corpus/docs/RPL-CS-PRO-007/RPL-CS-PRO-007_v3.0.md` (canonical)
- `corpus/docs/RPL-CS-PRO-007/RPL-CS-PRO-007.basis.json`
- `corpus/docs/RPL-CS-PRO-007/scripts/worked_examples.py` (computes §13; seed-free, deterministic)
- `corpus/docs/RPL-CS-PRO-007/render/RPL-CS-PRO-007_v3.0.docx` and `.pdf`

### What this document is in the real world

The procedure customer service and metering staff follow when a customer questions a bill or meter accuracy:
- high-bill triage
- intake of a meter test request
- eligibility and fees (when they may and may not be charged)
- scheduling and witnessing
- removal and chain of custody
- shop or in-place testing
- accuracy determination
- reporting results to the customer
- the customer's route to a commission-supervised test
- how bills are adjusted when a meter is found fast, slow or non-registering, or a billing error is found

It operationalizes Tariff Rules 9 and 12 (RPL-TAR-GRR-012, Sheets 27–29 and 35–36). Testing is done in the Meter Shop & Standards Laboratory, Lafayette HQ (§1.5), under the test equipment and standards controls of RPL-MTR-PGM-001.

**Study for structure ONLY (never take any value — accuracy limits, load weighting, free-test frequency, fees, look-back periods are jurisdiction-specific and must come from the pack):**
- NIPSCO GRR Rule 9 (how an Indiana tariff states metering, testing and adjustment terms with 170 IAC cites): https://www.nipsco.com/docs/librariesprovider11/rates-and-tariffs/electric-rates/2025-to-current/general-rules-and-regulations.pdf
- NJ BPU Application for Electric Meter Test (request form fields; "do not allow removal" instruction): https://www.nj.gov/bpu/pdf/reliability/Electric%20Meter%20Test%20request%20form%20as%20of%20January%2031%202022.pdf
- Marquette BLP Billing Adjustment Policy (scenario table layout; former-customer refunds): https://mblp.org/wp-content/uploads/2025/06/Appendix-D-BillingAdjustmentPolicy-25-06-17.pdf
- Le Sueur Electric Meter Testing Policy (reread-before-test step; request form acknowledgment): https://www.cityoflesueur.com/DocumentCenter/View/1796/Electric-Meter-Testing-Policy-PDF
- Tescometering, "Meter Testing 101" (test points, as-found/as-left terminology): https://www.tescometering.com/wp-content/uploads/2024/03/NC-Meter-School_Meter-Testing-101_Tom-Lawton_6.15.2022.pdf

> **Caution.** If the pack defines how average accuracy is computed (test points and weights) or the accuracy limit, use exactly that. If it does not, state the test points as company practice and **do not state a weighting or a limit as regulatory**. Never use the weighting or ± limit from the NJ form or any other source.

### Required structure

Minimum numbered clauses in brackets.

1. **Purpose** · 2. **Scope** [≥4: residential and non-residential; AMI, AMR and electromechanical meters (fleet per §1.1); demand meters; excludes T18 periodic and sample testing, cross-referenced] · 3. **Definitions** [≥15: as-found, as-left, full load, light load, power factor test point, average accuracy (the pack's method if defined), creep, non-registering, fast/slow meter, billing error, back-bill, refund, written request, commission-supervised test, meter seal; pack-defined terms carry citations] · 4. **Regulatory basis** (table) · 5. **Roles** (table: P18, P14, P19, P20; Contact Center agents; Billing Adjustment Analysts; Meter Technicians; Customer Advocacy P17)
6. **High-bill triage before a test** [≥6, company practice]: register read verification; AMI interval data review in AMI HES (usage spikes, weather normalization); check for crossed meters, wrong multiplier, estimated reads; customer usage education; offer of a meter test in all cases where the pack gives a right to one. Triage must never delay or replace a test the customer is entitled to.
7. **Customer request intake** [≥6]: phone, web, written; form `MTR-F-010`; what constitutes a written request per the pack; CIS service order type `MTR-TST`; acknowledgment.
8. **Eligibility and fees** — decision table `ID · Request situation · Fee charged? · Condition · Refund of fee? · Citation · CIS code`. One row per condition in the pack (first request, repeat request within the pack's window, outcome-dependent fee rules, any customer class differences). Fee amounts from §1.6 Table F only where the pack does not set them. Minimum 6 rows.
9. **Scheduling, removal and chain of custody** [≥10]: in-place vs. shop test; customer's right to witness (if in the pack) and how the appointment is offered; meter removal, replacement meter, seal numbers; tag `MTR-F-013`; sealed container; transport; secure storage in the Meter Shop cage; retention of the removed meter and any limit on disposal without consent (per the pack); photo record in WAM.
10. **Test execution and accuracy determination** [≥10]: test standard traceability (cross-reference RPL-MTR-PGM-001); test points; as-found test before any adjustment; calculation method and accuracy limits **as stated in the pack**; pass/fail determination; demand register test; AMI communications/firmware checks (company practice); as-left; test record in `MTR-F-011`.
11. **Reporting results to the customer** [≥6]: timing and content of report `MTR-F-011` per the pack; appeal rights to the Commission and the appeal window per the pack; IURC contact block from §1.6 Table C.
12. **Commission-supervised tests** [≥5]: how RPL responds when the IURC notifies it of a customer application (per the pack); who coordinates (P19); meter hold; records.
13. **Billing adjustments** — one subsection per scenario: 13.1 fast meter; 13.2 slow meter; 13.3 non-registering or partially registering meter; 13.4 demand register error; 13.5 other billing errors (wrong rate, wrong multiplier, crossed meters, estimated-read errors); 13.6 tampering-related registration (excluded from standard adjustment; routed to revenue protection — company practice unless the pack addresses it). For each: method, look-back period, refund vs. back-bill rule, interest if any, payment arrangement for back-bills, customer notice — **exactly as in the pack** — plus CIS adjustment transaction code (§1.6 Table K) and approval authority.
14. **Adjustment approval authority** (table, company practice): up to $500 Billing Adjustment Analyst; $500.01–$5,000 Supervisor, Metering Services (P18); above $5,000 Director, Customer Operations (P14); any adjustment on an account with an open IURC complaint is also copied to P17.
15. **Worked examples** — three numeric examples (one fast residential AMI meter, one non-registering electromechanical meter, one wrong-multiplier commercial demand account). Computed by `scripts/worked_examples.py`, which reads its method parameters from a `params` dict populated from the basis file. Show inputs, look-back dates, per-period calculation and total in a table. Fictional account numbers in the format `4xxxxxxxxx-x`.
16. **Records & retention** · 17. **Training** (CS-T-07; MTR-T-03 for technicians) · 18. **Related documents** (RPL-TAR-GRR-012 R9/R12/R16, RPL-MTR-PGM-001, RPL-CS-PRO-011, RPL-LEG-RRS-001) · 19. **Revision history** (2–3 entries; prior 2.1 dated 2023-11-06) · 20. **Approval block** (two signatures)

**Appendices (field IDs `App-X.Fn`):**
- App-A `MTR-F-010` Meter Test Request (customer, service address, account, meter number, reason, preferred contact, witness election if in the pack, fee acknowledgment where a fee may apply, signature/date, office-use block)
- App-B `MTR-F-011` Meter Test Report letter (every pack-required content element is a field; as-found results table by test point; determination; adjustment summary; appeal rights; IURC contact block)
- App-C `MTR-F-012` Billing Adjustment letter (refund and back-bill versions)
- App-D `MTR-F-013` Meter chain-of-custody tag
- App-E Contact-center script `CS-S-07` (high-bill call to test request)

### Depth and anti-summary rules

- Length: **6,000–8,500 words** including appendices.
- At least **40 clause IDs** in the body and **45 field IDs** in the appendices.
- Every scenario in §13 has its own clause ID per element (method, look-back, refund/back-bill, interest, notice).
- Banned phrasing: as in T14.

### Rendering (required)

As T14, with the `docx` skill (header text "RPL-CS-PRO-007 | Meter Test Request & Billing Adjustment Procedure"; footer "Version 3.0 | Effective 2025-02-17 | Internal | Uncontrolled when printed | Page X of Y"). Forms use bordered fill-in tables. The test report letter has an as-found results grid. Expected length: 20–30 pages.

### Self-check (in addition to §2.6 and §3.8)

1. Every condition in the pack's meter-test and adjustment sections appears as a decision-table row or §13 clause, with citation.
2. `worked_examples.py` re-runs and reproduces every number in §15. Its `params` match the basis file. The result is recorded in the basis file under `worked_examples`.
3. No accuracy limit, weighting, look-back period, test frequency or fee condition appears that is not in the pack. Fee amounts match §1.6 Table F (or the pack, if it sets them — reported).
4. Form numbers, CIS codes and tariff sheet references match §1.6 and the T13 sheet map.
5. Render text parity passes.
```

---

## T17 — Customer Complaint & Dispute Resolution Procedure

### (a) Real-world anatomy

**Indiana regulator side (S18–S21).**
- The IURC Consumer Affairs Division provides dispute resolution for individual customers on billing, service extension, deposits, termination, service quality and metering.
- Customers are told to try the utility first, then file online through the IURC portal or by phone during business hours. A formal petition route under IC 8-1-2-54 is mentioned.
- Since 2011 the IURC handles individual complaints, while the OUCC handles comments on pending cases and general consumer information (S20).
- The real complaint form is **State Form 50488** (sections: communication with utility and date; customer; service address; utility information; complaint description) (S21).
- Contact details are listed in §1.6 Table C below.

**Complaint process format (S22, S23).**
- Choptank's co-op policy is organized as: Purpose → Procedure (authority; informal process; formal process; additional remedies; publication) → Responsibility → Appendix A informal complaint form (account/meter numbers, incident description, remedy requested, signature) → Revision history.
- The PA PUC process shows the expected regulated-utility flow: utility first → utility investigates and may not issue termination notices on the disputed matter → commission referral → utility report to the commission within set times (shorter if service is off) → commission decision → appeal to the formal process.
- Values are Pennsylvania's and not usable. The pattern ("service-off cases are expedited") is a realistic company practice to state as an internal target.

**Notice language blocks (S12).** Bill and notice statements telling the customer how to question a bill and how to reach the regulator; translation-assistance lines.

**Artifacts a regulatory professional expects in an IOU complaint SOP:**
- complaint vs. inquiry vs. dispute classification with examples
- category and sub-category taxonomy codes
- priority levels (service off / disconnection pending / safety; standard)
- intake fields
- the acknowledgment
- investigation checklist by category (billing, meter, disconnection, vegetation, outage/reliability, conduct, deposits, line extension)
- holds placed on collection
- the written determination with required elements
- the customer's right to escalate to the IURC, with contact details
- the IURC referral (inbound complaint) response workflow with internal response-preparation targets
- executive and escalated complaints
- root-cause analysis and corrective action
- KPI definitions
- a regulatory complaint log
- records retention
- call recording reference
- training

### (b) Gaps

| # | Gap | Severity |
|---|---|---|
| 17-1 | **IURC contact details are not canonical** (phone, address, fax, hours, portal, State Form 50488). Agents will invent or recall them differently across T13, T14, T15 and T17. They are real public facts and allowed; they must also be as of early 2025. | critical |
| 17-2 | **Dispute hold codes and their relationship to T14 are not canonical** (T14 §14 and T17 §7 must use the same `HDSP`/`HIURC` codes and release rules). | critical |
| 17-3 | **The "Study for structure" line gives no real references**, so the agent will invent structure or generalize. Add S18–S23. | major |
| 17-4 | **No complaint taxonomy or priority model.** Real procedures classify by category and set expedited handling for service-off and disconnection-pending complaints. The spec only says "billing, service, disconnection, vegetation". | major |
| 17-5 | **No investigation checklist by category, no evidence list** (CIS notes, AMI data, call recordings, field order photos, vegetation work records from T16). | major |
| 17-6 | **IURC inbound complaint workflow lacks internal mechanics:** where referrals arrive (IURC portal), who logs them (P17's team), response package contents, internal draft/review/sign-off, and a regulatory complaint log. | major |
| 17-7 | **No root-cause / corrective-action loop, KPI definitions, or monthly report template** (§14 "monthly complaint KPI report to P13" is a one-liner). | major |
| 17-8 | **No language access / accessibility** (Spanish line, TTY/Relay, interpreter service) — expected in a customer-rights procedure. | major |
| 17-9 | **Scope-pack risk:** T17 scope is `170 IAC 16-` and `170 IAC 4-1-16`. If the pack's dispute rules sit elsewhere in 170 IAC 4-1 (e.g., a customer-information or billing-dispute section), the agent will either omit them or cite from memory. T00 should add a heading-based scope extension (heading contains "complaint", "dispute" or "information to customers") within 170 IAC 4-1. | major |
| 17-10 | **Snapshot risk:** agents tend to state "respond within X business days" from other states or from general practice as if regulatory. The spec has no explicit rule that internal response targets are labeled and never presented as IURC requirements. | critical |
| 17-11 | **Formal complaints (IC 8-1-2-54) and OUCC inquiries are not addressed.** A real procedure says how they are routed (Legal P03; Regulatory Affairs P08). They should be `out_of_scope_reference` with no values. | minor |
| 17-12 | **Length 3,000–4,500 words is thin** for 18 sections and 4 appendices. | major |
| 17-13 | **No rendering requirement.** | major |

### (c) Ready-to-paste spec text — T17

```markdown
## T17 — Customer Complaint & Dispute Resolution Procedure

**Doc ID:** RPL-CS-PRO-011 · **Vertical:** Policy & Governance · **Wave:** 2 · **Grounding:** `corpus/grounding/T17.json`
**Owner/Reviewer:** Brian Kowalski (P17) / Karen Mitchell (P13) — two-signature document (front matter `approver: null`; approval block "Prepared and approved by" P17, "Reviewed and approved by" P13)
**Supersedes:** 2.2 (2024-03-18)
**Outputs:**
- `corpus/docs/RPL-CS-PRO-011/RPL-CS-PRO-011_v2.3.md` (canonical)
- `corpus/docs/RPL-CS-PRO-011/RPL-CS-PRO-011.basis.json`
- `corpus/docs/RPL-CS-PRO-011/render/RPL-CS-PRO-011_v2.3.docx` and `.pdf`

### What this document is in the real world

How the utility receives, classifies, investigates and resolves customer complaints and disputes: billing, metering, disconnection, deposits, service quality and outages, vegetation work, line extensions and employee conduct. It covers what RPL must tell the customer and how quickly, what collection activity stops while a dispute is open, how the outcome is recorded, how a customer is told of their right to contact the IURC Consumer Affairs Division, and how RPL responds when the IURC forwards a complaint. Regulators review it when they mediate complaints. It ties to RPL-CS-PRO-004 (disconnection holds), RPL-CS-PRO-007 (meter disputes) and RPL-DO-PLN-002 (vegetation disputes).

**Study for structure ONLY (never take any value — response times in these sources are other states' or the IURC's general guidance, not the pack):**
- IURC Consumer Affairs — Customer Assistance (complaint channels; utility-first expectation; formal petition route): https://secure.in.gov/iurc/customer-assistance
- IURC Contact Us (contact block): https://secure.in.gov/iurc/contact-us
- IURC Complaint Form, State Form 50488 (fields a referral will contain): https://forms.in.gov/Download.aspx?id=11365
- OUCC/IURC division of complaint responsibilities (2011): https://www.in.gov/oucc/news/consumer-affairs-process-streamlined-for-the-iurc-and-oucc
- Choptank Electric Policy 501 (policy layout; informal complaint form fields): https://choptankelectric.coop/sites/choptankelectric/files/BP%20501%20Member%20Complaints.pdf
- Pennsylvania PUC complaint process overview (expedited handling for service-off complaints — pattern only): https://www.dcba-pa.org/pdfs/eventAds/16_PUC%20Complaint%20Process.pdf

> **Caution.** Every regulatory deadline (utility response, informal review, customer appeal window) and every required content element comes from the pack. Internal response targets are company practice: they begin with "Internal performance target:" and must be equal to or shorter than any pack deadline they sit next to.

### Required structure

Minimum numbered clauses in brackets.

1. **Purpose** · 2. **Scope** [≥5: residential and non-residential; all channels; complaints received directly and via the IURC; excludes formal Commission proceedings (routed to P03; IC 8-1-2-54 as `out_of_scope_reference`) and OUCC case comments (routed to P08)]
3. **Definitions** [≥14: complaint, dispute, inquiry, informal review, determination, escalated complaint, IURC referral, undisputed amount, service-off complaint, executive complaint, root cause, etc. — pack meanings govern, with citation]
4. **Regulatory basis** (table `Citation | Heading | What it governs here | Clause IDs`)
5. **Roles** (table: P17 and Complaint Resolution Specialists; Contact Center agents and Team Leads; P13; P15 for collection holds; P18/P19 for meter disputes; P22 for vegetation; P23 for outage complaints; P03 Legal; P08 Regulatory Affairs)
6. **Intake and classification** [≥10]: channels (phone, web form, email, letter, in person at service centers, IURC portal referral, executive office); inquiry vs. complaint vs. dispute decision table with examples; category codes and priority levels from §1.6 Table K; intake record `CS-F-030` in CIS (case type `CMP`); language access (Spanish line, interpreter service, TTY/Relay — company practice).
7. **Protection during a dispute** [≥6]: what collection/disconnection activity must stop and for how long; undisputed amounts the customer must pay (per the pack and 170 IAC 4-1-16 where it applies); CIS holds `HDSP` (RPL-level dispute) and `HIURC` (IURC complaint open), who places and who releases them; coordination with RPL-CS-PRO-004 §14.
8. **Investigation** [≥10]: steps and timelines (per the pack where it sets them; company practice otherwise, labeled); category checklists (billing, meter, disconnection, deposit, outage/reliability, vegetation, conduct, extension) naming the evidence pulled (CIS notes and history, AMI interval data, call recordings, field order photos, OMS event records, vegetation work records); service-off and disconnection-pending complaints handled the same day (internal target).
9. **Utility determination and customer notice** [≥8]: timing, method, one clause per required content element (each mapped to a `CS-F-032` field); information on the customer's right to contact the IURC and how (per the pack; contact block from §1.6 Table C).
10. **Escalation inside RPL** [≥6]: Team Lead → Complaint Resolution Specialist → P17 → P13; Legal (P03) triggers (threat of litigation, formal complaint, damage claim, media); executive complaints.
11. **IURC Consumer Affairs referrals and responses** [≥10]: receipt via the IURC portal; logging in the Regulatory Complaint Log (`RCL-yyyy-nnnn`); hold `HIURC`; response package contents (account history, timeline, documents, resolution offered); what RPL provides and by when (per the pack); internal draft/review/sign-off chain (Specialist → P17); closure and customer follow-up; handling a customer request for informal review or appeal (per the pack).
12. **Payment arrangements arising from disputes** [≥4] (per the pack if present; otherwise company practice, by reference to `CS-F-016` in RPL-CS-PRO-004).
13. **Root cause and corrective action** [≥5]: monthly trend review; RCA trigger (≥3 complaints with the same root-cause code in a month, or any IURC-substantiated complaint); corrective-action log; feedback to procedure owners.
14. **Reporting** [≥4]: monthly complaint KPI report to P13 (template in App-F); KPI definitions (volume by category, IURC referrals per 1,000 customers, % resolved at first contact, average days to determination, % determinations within the pack deadline, repeat complaints).
15. **Records & retention** · 16. **Training** (CS-T-11; annual refresher; de-escalation module) · 17. **Related documents** (RPL-CS-PRO-004, RPL-CS-PRO-007, RPL-DO-PLN-002, RPL-TAR-GRR-012 R11/R13, RPL-LEG-RRS-001, RPL-CMP-REG-001) · 18. **Revision history** (2–3 entries; prior 2.2 dated 2024-03-18) · 19. **Approval block** (two signatures)

**Appendices (field IDs `App-X.Fn`):**
- App-A `CS-F-030` Complaint Intake form (CIS screen layout rendered as a form)
- App-B `CS-F-031` Acknowledgment letter
- App-C `CS-F-032` Determination letter (every pack-required element a numbered field; IURC contact block; Spanish and TTY lines)
- App-D `CS-F-033` IURC referral information sheet (customer-facing: when and how to contact the IURC Consumer Affairs Division, using §1.6 Table C; mentions State Form 50488 and the online portal)
- App-E Complaint category and priority code table (from §1.6 Table K)
- App-F Monthly Complaint KPI report template (table with fictional January 2025 figures consistent with §1.1 customer counts)

### Depth and anti-summary rules

- Length: **5,500–7,500 words** including appendices.
- At least **35 clause IDs** in the body and **35 field IDs** in the appendices.
- Banned phrasing: as in T14, plus "promptly" or "as soon as possible" used in place of a stated timeframe.

### Rendering (required)

As T14, with the `docx` skill (header "RPL-CS-PRO-011 | Customer Complaint & Dispute Resolution Procedure"; footer "Version 2.3 | Effective 2025-03-03 | Internal | Uncontrolled when printed | Page X of Y"). Include a one-page process flow (intake → classify → hold → investigate → determine → notify → close/escalate → IURC referral loop). Expected length: 18–26 pages.

### Self-check (in addition to §2.6 and §3.8)

1. Every regulatory deadline and required content element in the pack appears in the body and in App-C, with citation.
2. Every internal target is labeled, and none is longer than the pack deadline next to it.
3. IURC contact details exactly match §1.6 Table C. Hold codes, form numbers and category codes match §1.6.
4. No response time appears as regulatory unless it is in the pack.
5. Render text parity passes.
```

---

## (d) Global recommendations for Sections 0–3

### G1 (critical). Add **§1.6 Canonical shared operational data (non-regulatory)**

Wave 2 runs in parallel. T13, T14, T15 and T17 all reference the same fees, sheet numbers, codes, forms and contact blocks, so these must be fixed before Wave 2 starts. Paste after §1.5:

```markdown
### 1.6 Canonical shared operational data (non-regulatory; use verbatim)

These are company choices or public contact facts, **not** regulatory values. If a grounding pack sets, caps or prohibits any item below, the pack governs. In that case, use the pack's value in your document and report the conflict in your final message so the orchestrator can reconcile sibling documents.

**Table F — Non-recurring charges (Tariff Rule 16, Sheets 45–46).** The condition text for each charge is written by T13 from the pack.

| ID | Charge | Amount |
|---|---|---|
| F-1 | Reconnection, remote (AMI), any time | $10.00 |
| F-2 | Reconnection at meter, field, regular hours (Mon–Fri 08:00–17:00 excl. Company holidays) | $45.00 |
| F-3 | Reconnection at meter, field, after hours weekdays | $70.00 |
| F-4 | Reconnection at meter, field, Saturday/Sunday/Company holiday | $120.00 |
| F-5 | Reconnection at pole, transformer or underground vault | $165.00 |
| F-6 | Field collection visit (no disconnection performed) | $20.00 |
| F-7 | Returned payment (check, ACH, card chargeback) | $20.00 |
| F-8 | Meter tampering / unauthorized use investigation (minimum, plus actual costs and unbilled energy) | $100.00 |
| F-9 | Customer-requested meter test, where the pack permits a charge | $40.00 (residential/single-phase); $95.00 (polyphase/demand) |
| F-10 | Missed appointment trip charge | $25.00 |
| F-11 | AMI opt-out: one-time / monthly manual read | $50.00 / $18.00 |
| F-12 | Account establishment (new service in customer's name) | $15.00 |

**Table V — Standard service voltages (engineering practice).** Secondary: 120/240 V 1-phase 3-wire; 120/208 V 3-phase 4-wire wye; 277/480 V 3-phase 4-wire wye; 240 V and 480 V 3-phase 3-wire delta (existing installations only). Primary: 7,200/12,470 V and 19,920/34,500 V 3-phase 4-wire wye. Subtransmission: 69,000 V 3-phase.

**Table K — CIS and field codes.**
- Holds: `HMED` medical certificate · `HEAP` energy assistance protection · `HPAY` payment arrangement active · `HDSP` dispute pending at RPL · `HIURC` IURC complaint open · `HCRT` critical-care / life-support flag (company practice) · `HLGL` legal/bankruptcy · `HWTH` weather/seasonal hold (use only if the pack or a statute provides the protection).
- Field order types: `DNP` disconnect non-pay · `DNP-R` remote disconnect · `RCN` reconnect · `RCN-AH` after-hours reconnect · `FCV` field collection visit · `MTR-TST` meter test · `MTR-INV` tamper investigation.
- Adjustment transaction codes: `ADJ-MF` meter fast · `ADJ-MS` meter slow · `ADJ-NR` non-registering · `ADJ-BE` billing error · `ADJ-RT` wrong rate · `ADJ-MX` multiplier.
- Complaint categories: `BIL` billing · `MTR` metering · `DSC` disconnection/collections · `DEP` deposit · `REL` outage/reliability · `PQ` power quality · `VEG` vegetation · `EXT` line extension/new service · `CON` employee conduct · `OTH` other.
- Complaint priorities: `P1` service off or disconnection pending or safety · `P2` all others.

**Form and ID catalog** (extends §1.5): `CS-F-012` Disconnection Notice · `CS-F-012-DT` Door Tag · `CS-F-013` Energy Assistance Protection Letter · `CS-F-014` Reconnection Confirmation · `CS-F-015` Medical Certificate · `CS-F-016` Payment Arrangement Agreement · `CS-F-030` Complaint Intake · `CS-F-031` Complaint Acknowledgment · `CS-F-032` Complaint Determination · `CS-F-033` IURC Referral Information Sheet · `MTR-F-010` Meter Test Request · `MTR-F-011` Meter Test Report · `MTR-F-012` Billing Adjustment Letter · `MTR-F-013` Meter Chain-of-Custody Tag. Scripts: `CS-S-04` (disconnection), `CS-S-07` (high bill / meter test), `CS-S-11` (complaints). Training: `CS-T-04`, `CS-T-07`, `CS-T-11`, `FS-T-12`, `MTR-T-03`. Regulatory Complaint Log ID format `RCL-2025-nnnn`.

**Table C — External customer-facing contacts** (public facts; orchestrator verifies against an archived early-2025 copy of the IURC page before Wave 2):
- IURC Consumer Affairs Division — 1-800-851-4268 (toll-free) · 317-232-2712 · fax 317-233-2410 · PNC Center, 101 W. Washington Street, Suite 1500E, Indianapolis, IN 46204 · 8:15 a.m.–4:45 p.m. ET, Monday–Friday · online complaints via the IURC Online Portal (iurc.portal.in.gov) · paper complaint form State Form 50488.
- OUCC — 1-888-441-2494 (pending cases and general consumer information; not individual complaints).
- Energy assistance — Indiana Energy Assistance Program through local intake agencies (Indiana Housing & Community Development Authority); dial 211.
- RPL Spanish-language line 1-800-555-0143 ("Para servicio en español, llame al 1-800-555-0143"); TTY users dial 711 (Relay Indiana — orchestrator to confirm).
- Written disputes: Rockridge Power, Customer Advocacy, 400 Wabash Commons Drive, Lafayette, IN 47901 (payments only to the P.O. Box in §1.5).

**Company holidays (2025):** Jan 1, Jan 20, May 26, Jul 4, Sep 1, Nov 27, Nov 28, Dec 24, Dec 25. (Whether disconnection is restricted on these days is a pack question.)

**Tariff references:** use the T13 canonical sheet map. Disconnection = Rule 13, Sheets 37–41; charges = Rule 16, Sheets 45–46; metering = Rule 9, Sheets 27–29; adjustments = Rule 12, Sheets 35–36; billing = Rule 11, Sheets 32–34.
```

Also add a `Supersedes` column to §1.4 with each document's prior version and date. Proposed: T13 "IURC No. 12 sheets eff. 2021-10-01"; T14 "5.0 (2024-01-15)"; T15 "2.1 (2023-11-06)"; T17 "2.2 (2024-03-18)". The other groups add theirs. This removes the T03 reconciliation step.

### G2 (critical). Add **§2.7 Statutory and other non-pack law**

```markdown
### 2.7 Law that is not in your pack

Real documents also rely on Indiana statutes (IC Title 8) and federal rules that are not in your grounding pack. When a real document would cover such a topic (e.g., a statutory winter disconnection protection, formal complaints under IC 8-1-2-54):
- Name the statute or rule and say the Company complies with it. Clause type `out_of_scope_reference`; record it in `out_of_scope_references`.
- State **no** values from it: no dates, durations, thresholds, temperatures or amounts.
- Build the full operational process around it (codes, forms, scripts, roles) as company practice.
- Never fill the value from memory, agency FAQs or other utilities' documents.
```

### G3 (critical). Add a **value ledger** to §3.4 and a check to §2.6/T90

Every number in a document is where Snapshot-1 misalignment shows up. Add to the basis schema:

```json
"value_ledger": [
  {"clause_id": "RPL-CS-PRO-004:13.4", "text": "$45.00", "source": "section1.6", "ref": "F-2"},
  {"clause_id": "RPL-CS-PRO-004:8.2", "text": "<value>", "source": "pack", "citation": "<cite>", "s1_quote": "<exact substring>"},
  {"clause_id": "RPL-CS-PRO-004:16.2", "text": "50", "source": "company_practice", "note": "monthly QA sample size"}
]
```

Allowed `source` values: `pack` · `section1` · `section1.6` · `company_practice` · `worked_example`.

Then add to §2.6:

> **6.** Extract every numeral, spelled-out number, percentage, time, date, temperature and dollar amount from the document body (regex over text excluding front matter and comments). Each must appear in `value_ledger`. A `company_practice` value may not sit in a sentence that cites a regulation unless that sentence begins "Internal performance target:" or "Company practice:".

### G4 (critical). Add a warning about study references to §2.1

Add to §2.1:

> Study references in each task (other utilities' tariffs, other states' rules and forms, agency FAQs) **contain values that are wrong for this corpus** — other jurisdictions, or later editions of Indiana's rules. Treat every number in them as contaminated. If a value in your draft matches something you read in a study reference and you cannot find it in your pack, delete it.

### G5 (major). Add **§3.7 Rendering standard** and **§3.8 Acceptance rubric**

```markdown
### 3.7 Rendered deliverable (in addition to the canonical Markdown)

The Markdown file is canonical and carries the clause IDs. Every task also produces a rendered copy that looks like the real thing, under `corpus/docs/<DOC_ID>/render/`, built by a deterministic script in `scripts/`:
- **Procedures and plans:** use the `docx` skill to produce `.docx`, then convert it to `.pdf` (LibreOffice headless). Cover page with document-control table; running header (company · doc ID · title); footer (version · effective date · classification · "Uncontrolled when printed" · Page X of Y); auto TOC; appendices on new pages; forms as bordered fill-in tables with signature lines; letters on RPL letterhead.
- **Tariff (T13):** use the `pdf` skill (reportlab): one tariff sheet per page, sheet header block, issued/effective footer.
- **Datasets:** CSV stays canonical. Optional `xlsx` rendering via the `xlsx` skill with a data-dictionary sheet.
- Strip `<!-- clause -->` / `<!-- sheet -->` comments. Clause IDs never appear in rendered output.
- **Text parity:** a normalized-text comparison must show every Markdown sentence in the rendering. T90 re-runs it.
- Diagrams: Mermaid in Markdown; rendered to PNG for the docx.

### 3.8 Acceptance rubric (reject and redo if any item fails)

1. Word count (body only, excluding front matter and HTML comments) within the task range.
2. Minimum clause-ID and field-ID counts met. Every numbered clause has an ID.
3. Every section in the task's required structure is present, in order, with at least its minimum clause count.
4. Every procedural step names an actor, a system or action, and a record. No section is a paragraph summary of a rule.
5. Banned-phrase scan returns zero hits: "this document aims", "in a timely manner", "as required by law" without a citation, "appropriate action", "applicable regulations" without a citation, "etc.", "and so on", "promptly" in place of a timeframe, "[TBD]", "XXX".
6. Value-ledger check (§2.6.6) passes.
7. Every §1 and §1.6 constant used matches verbatim (phone numbers, form numbers, codes, sheet numbers, fees).
8. Basis JSON validates against §3.4. Every `s1_quote` is an exact substring.
9. The rendered file exists, opens, falls within the task's page range, and passes text parity.
10. A "regulatory professional read": the agent rereads the document as an IURC Consumer Affairs analyst would. Any clause that a real Indiana utility would not write, or that lacks a detail it would include, is fixed before finishing.
```

### G6 (major). T00 scope additions for this group (headings only; no values)

- **T13:** keep the scope. Also include `170 IAC 16-` (the tariff's dispute and disconnection rules reference it).
- **T14:** add any `170 IAC 4-1-` section whose heading matches `disconnect|reconnect|deposit|payment arrangement|medical|bill` (the deposit and delinquency sections feed the eligibility table). Add `170 IAC 4-1-13` explicitly if not already covered.
- **T15:** confirm `170 IAC 4-1-14` captures all billing-adjustment scenarios. Add any `170 IAC 4-1-` section whose heading matches `meter|adjust|estimated`.
- **T17:** add any `170 IAC 4-1-` section whose heading matches `complaint|dispute|information to customer`, plus `170 IAC 4-1-13` (undisputed portion/billing).
- **For each pack:** include an `absent_topics` note for the orchestrator only (not the agent) when a topic named in the task title (e.g., "Winter Protection") has no governing section in scope, so the orchestrator knows §2.7 will apply.

### G7 (major). Two-signature documents

In §3.1, state the front matter for T15 and T17: `approver: null` plus `second_signatory: {id: P14, ...}`. Define the approval block format (two rows: "Prepared and approved by", "Reviewed and approved by"). T03 sets `approver_id` blank and `review_cycle` as listed.

### G8 (major). Measured length and density

Real documents of these types are 2–3x the current spec targets. Revised ranges are given in each patched task (T13 11–15k words / 47 sheets; T14 8–11k / 28–40 pp; T15 6–8.5k / 20–30 pp; T17 5.5–7.5k / 18–26 pp). Word count is measured body-only as in §3.8.1.

### G9 (minor). Research allowance and source logging

Add to §2.1:

> Agents may use web research for (a) document form and layout, (b) real public contact details and public program names, and (c) **typical ranges** for company-chosen operational values (fees, staffing, timeframes) **only where §1.6 does not already fix them**, and only from official sources (IURC/OUCC/IHCDA sites, utilities' own published tariffs). Log every URL opened in the basis file under `"form_sources": [{"url": "...", "used_for": "..."}]`. Research is never a source of a regulatory value.

### G10 (minor). Cross-group consistency hooks

T16 (vegetation disputes → T17 category `VEG`, P22) and T18 (meter program → T15 test standards) should reference §1.6 codes too. The orchestrator should give the T16 and T18 auditors §1.6 so they use the same codes.
