# Audit — Group C (Compliance, EHS & Global Design): T20, T21, T10, T11, T12, T00–T03, T90–T91, Sections 0–3

**Spec audited:** `/home/claude/strata_synthetic_corpus_spec.md` v1.0 (2026-10-06)
**Scope:** T20, T21, T10, T11, T12; T00–T03; T90–T91; global Sections 0–3
**Date:** 2026-10-06
**Constraint observed:** none of the ready-to-paste text adds a regulatory value. Every number proposed is one of three kinds: a company-chosen operational value, a fictional identifier, or a real regulator *contact detail* (which §2.1 allows). Where this report's *findings* describe what a real rule contains (so the spec owner can judge risk), the description is for the spec owner only. It is never placed in paste text.

**Coordination with Group A** (`/home/claude/audit/group_A_customer_tariff.md`): this report builds on Group A's G1 (§1.6 canonical shared operational data), G2 (§2.7 non-pack law), G3 (value ledger), G4 (study-reference contamination warning), G5 (§3.7 rendering, §3.8 rubric) and G9 (`form_sources`). Where both reports touch the same section, the text here is meant to **merge with** Group A's version, not compete with it. In particular, §3.6 here (Document Realism Standard) and §3.8 here (Realism & Depth Rubric) are supersets of Group A's §3.8. Apply Group A's G1–G4 first, then this report's (d).

---

## How to read this report

- **(a) Real-world anatomy**: what real documents look like. It lists only URLs I opened in this session.
- **(b) Gaps**: each is rated **critical** (will cause T90 failures, false findings, a Snapshot-2 leak, or a document an auditor would reject on sight), **major** (realism or completeness clearly below a real document), or **minor**.
- **(c) Ready-to-paste spec text**: a replacement for the task section, from `## Txx` down to the next `---`.
- **(d) Global findings**: replacement or added text for §0–§3, T00–T03 and T90–T91, including the full **Document Realism Standard** and **Realism & Depth Rubric**.

### Sources opened (this report)

| # | Source | URL | Used for |
|---|---|---|---|
| C1 | 327 IAC 2-6.1 rule index (Justia mirror; section list) | https://regulations.justia.com/states/indiana/title-327/article-2/rule-6-1/ | T20 structure, T00 scope |
| C2 | 327 IAC 2-6.1-1 Applicability | https://regulations.justia.com/states/indiana/title-327/article-2/rule-6-1/section-1 | T20 |
| C3 | 327 IAC 2-6.1-3 Exclusions | https://regulations.justia.com/states/indiana/title-327/article-2/rule-6-1/section-3 | T20 |
| C4 | 327 IAC 2-6.1-4 Definitions | https://regulations.justia.com/states/indiana/title-327/article-2/rule-6-1/section-4 | T20 |
| C5 | 327 IAC 2-6.1-5 Reportable spills; facility | https://regulations.justia.com/states/indiana/title-327/article-2/rule-6-1/section-5 | T20 |
| C6 | 327 IAC 2-6.1-6 Reportable spills; transportation | https://regulations.justia.com/states/indiana/title-327/article-2/rule-6-1/section-6 | T20 |
| C7 | 327 IAC 2-6.1-7 Reportable spills; responsibilities | https://regulations.justia.com/states/indiana/title-327/article-2/rule-6-1/section-7 | T20 |
| C8 | 327 IAC 2-6.1-8 Emergency spill response actions | https://regulations.justia.com/states/indiana/title-327/article-2/rule-6-1/section-8 | T20 |
| C9 | 327 IAC 2-6.1-9 Compliance confirmation | https://regulations.justia.com/states/indiana/title-327/article-2/rule-6-1/section-9 | T20 |
| C10 | IDEM Emergency Response program page | https://www.in.gov/idem/cleanups/investigation-and-cleanup-programs/emergency-response/ | T20 contacts and practice |
| C11 | IDEM Emergency Response Quick Reference Sheet (Feb 2017, via Purdue Extension) | https://www.extension.purdue.edu/news/inprepared/2021/04/_docs/er_quick_ref_sheet.pdf | T20 caller-information checklist, contacts |
| C12 | IDEM Emergency Spill Hotline flyer (via USDA FSA) | https://www.fsa.usda.gov/sites/default/files/documents/idem_emergency_spill_hotline.pdf | T20 |
| C13 | IDEM State Form 48373, Bypass/Overflow Incident Report | https://forms.in.gov/Download.aspx?id=5462 | T20 (IDEM form layout conventions) |
| C14 | Florida DEP, Mineral Oil Dielectric Fluid Emergency Response Protocol | https://floridadep.gov/sites/default/files/MinOilFluidEmergRespProtocol_13Sep16.pdf | T20 |
| C15 | Florida DEP, MODEF Cleanup Protocols page | https://floridadep.gov/waste/district-business-support/content/mineral-oil-dielectric-fluid-modef-cleanup-protocols | T20 |
| C16 | CPUC-filed (SDG&E) Spill Response and Notification Plan | https://ia.cpuc.ca.gov/environment/info/dudek/CNF/20160801_CNF%20PLRP_Spill%20Response%20and%20Notification%20Plan_REDACTED.pdf | T20 |
| C17 | National Grid first-responder bulletin, oil releases from electrical equipment | https://outreach.ngridsafety.com/wp-content/uploads/2025/12/17661_NGrid_FR_MC_ebulletin_Oil_releases_flyer_el_1225.pdf | T20 |
| C18 | ND DEQ Environmental Incident Summary Report (Montana-Dakota Utilities transformer release) | https://deq.nd.gov/FOIA/Spills/Summary_Reports/EIR5299_Summary_Report.pdf | T20 spill-record fields |
| C19 | Snohomish County PUD, 2023 Oil Spill Summary | https://www.snopud.com/wp-content/uploads/2024/09/2023OilSpillSummary.pdf | T20 annual volumes and cause taxonomy |
| C20 | Minnesota PCA, PCB leaks and spills guidance (w-hw4-48g) | https://www.pca.state.mn.us/sites/default/files/w-hw4-48g.pdf | T20 PCB cross-reference pattern |
| C21 | 170 IAC 4-1 rule index (Justia mirror) | https://regulations.justia.com/states/indiana/title-170/article-4/rule-1/ | T00 scope, T21, T12 |
| C22 | 170 IAC 4-1-24 (Justia mirror) | https://regulations.justia.com/states/indiana/title-170/article-4/rule-1/section-24 | T21 |
| C23 | 170 IAC 4-1-3 (Justia mirror) | https://regulations.justia.com/states/indiana/title-170/article-4/rule-1/section-3 | T12, T21 |
| C24 | 170 IAC 4-9 rule index (Justia mirror) | https://regulations.justia.com/states/indiana/title-170/article-4/rule-9/ | T11 |
| C25 | 170 IAC 16 article index (Justia mirror) | https://regulations.justia.com/states/indiana/title-170/article-16/ | T11 must-cover problem |
| C26 | Kentucky PSC Electric Incident Notification Guidelines | https://psc.ky.gov/agencies/psc/forms/incident_guidelines_03162015/electric-incident_notification_guidelines.pdf | T21 (other-state contamination risk) |
| C27 | PA PUC Form UCTA-8, Electric Accident Report Form "D" (rev. 8/2023) | https://www.puc.pa.gov/documents/utility-files/275/UCTA-8_Electric_Accident_Report_8-2023.pdf | T21 form anatomy |
| C28 | Missouri PSC Electrical Contact Reporting Form (9/24/24) | https://psc.mo.gov/CMSInternetData/Electric/Electrical%20Contact%20Reporting%20Form%202024.pdf | T21 form anatomy |
| C29 | OSHA Recordkeeping Forms Package (300/300A/301) | https://www.osha.gov/sites/default/files/OSHA-RK-Forms-Package.pdf | T21 EHS-F-101 fields |
| C30 | Camms, Compliance Obligations Register (field definitions) | https://camms.atlassian.net/wiki/spaces/CD/pages/77496321 | T10 |
| C31 | Security Scientist, Legal & Regulatory Requirements Register template | https://www.securityscientist.net/blog/legal-and-regulatory-requirements-register-template/ | T10 |
| C32 | Euronext Corporate Solutions, Compliance obligations register | https://www.corporatesolutions.euronext.com/blog/compliance-obligations-register/ | T10 |
| C33 | ServiceNow Policy & Compliance data model (authority document → citation → control objective → control) | https://www.servicenow.com/community/grc-articles/policy-and-compliance-management-architecture-and-data-model/ta-p/3605503 | T10 data model |
| C34 | IURC, Annual Report Filing: Electricity | https://www.in.gov/iurc/energy-division/electricity-industry/annual-report-filing-electricity/ | T11 out-of-scope rows, IURC channel |
| C35 | Colorado PUC Utility Forms (annual report due-date conventions) | https://puc.colorado.gov/utilityforms | T11 |
| C36 | NM PRC, PRCe360 Compliance Filings (docket-per-rule-per-year convention) | https://www.prc.nm.gov/prce360/prce360-compliance-filings/ | T11 |
| C37 | 18 CFR 125.3 (Cornell LII) | https://www.law.cornell.edu/cfr/text/18/125.3 | T12 structure |
| C38 | Washington State Public Utilities Records Retention Schedule v1.0 (2010, superseded) | https://sos.wa.gov/sites/default/files/2025-02/public-utilities-records-retention-schedule-v.1.0-%28december-2010%29-superseded.pdf | T12 |
| C39 | Washington State Utility Services Records Retention Schedule (current) | https://www.sos.wa.gov/sites/default/files/2025-06/utility-services-records-retention-schedule.PDF | T12 utility series |
| C40 | Colorado State Archives Schedule No. 60 | https://archives.colorado.gov/sites/archives/files/documents/Schedule%20No.%2060.pdf | T12 |
| C41 | NRECA model Record Retention & Destruction Policy 01-04 | https://www.electric.coop/wp-content/uploads/2018/03/Policy-01_04-Record-Retention-and-Destruction-Policy.pdf | T12 policy/legal hold |
| C42 | Florida PSC Notice of Proposed Rule Development, 25-6.015 (IOU records retention exceptions to FERC schedule) | https://www.floridapsc.com/library/FILINGS/2003/06876-2003/06876-2003.PDF | T12 (state overlay on 18 CFR 125) |

These sources did not load and are not used: the CPUC RA filing due-dates `.docx` (binary, and a proxy 403 on direct download), IDEM `/cleanups/spills/` (404) and the Oregon PUC schedule (404). **I found no public internal spill or accident procedure from an Indiana IOU.** The anatomies below therefore combine Indiana rule structure (C1–C9, C21–C23), Indiana agency practice (C10–C13, C34), other-state and other-utility procedures, plans and forms (C14–C20, C26–C29), and the GRC and records-management standards (C30–C33, C37–C42).

**Contamination warning (applies to every study reference for these tasks).** C14 (Florida volumes and timelines), C20 (Minnesota PCB tiers), C26 (Kentucky injury, dollar and customer thresholds), C28 (Missouri timelines) and C38–C40 (Washington and Colorado retention periods) all contain other states' or federal values. An agent that "studies" them will import those values. The task text below forbids that explicitly.

---

## T20 — Spill Response & Reporting Procedure

### (a) Real-world anatomy

**Indiana rule structure (C1–C9). This is what the T20 pack will contain; describing it here is not adding values to the spec.** 327 IAC 2-6.1 has nine sections:
1. Applicability. It covers hazardous substances, extremely hazardous substances, petroleum and objectionable substances, and states that the rule does not affect other federal, state or local reporting or cleanup requirements.
2. Special areas.
3. Exclusions. There are seven, including permitted discharges, *de minimis* volumes, vehicle and equipment operating fluids under a volume condition, and releases during authorized response.
4. Definitions. There are 18 terms, including *facility*, *facility boundary*, *mode of transportation*, *reportable quantity*, *spill*, *spill response* and **"spill report" (11 subdivisions)**.
5. Reportable spills; facility. Tiers by harm, wellhead protection areas, proximity to sensitive waters, receiving medium (surface water / soil beyond the facility boundary / soil within it), and spills with no response done.
6. Reportable spills; transportation. A parallel tier structure.
7. Responsibilities. Who reports, to which IDEM office, by what channel and within what time; updates; written copy on request; due diligence to notify downstream water users and affected property owners.
8. Emergency response takes precedence over reporting, and the responsible person carries the burden of proving that a delay was needed.
9. Compliance confirmation. A letter from IDEM on request.

Implications for the spec:
- **The required content of the state notification sits in the *definition* of "spill report" (section 4), not in section 7.** The current task text points the agent at "Notification to the state … (per the pack)", and an agent may look only in section 7.
- **The thresholds depend on classifications the rule does not make for utility equipment.** Is a pole-mount transformer on a right-of-way a "facility"? Where is its "facility boundary"? Is a bucket truck a "mode of transportation"? Is mineral-oil dielectric fluid "petroleum"? (*Petroleum* is not among the 18 defined terms.) An agent that resolves these silently creates false-finding risk at Snapshot 1.
- **One tier refers to the federal reportable quantity**, which is defined outside the pack (40 CFR 302.4). It must be referenced without values.
- **Third-party notification** of downstream water users and property owners is a substantive obligation. The current required structure omits it.

**Agency practice (C10–C12).** IDEM's 24-hour Emergency Response line is **(888) 233-7745 / (317) 233-7745** (C10). IDEM's quick-reference sheet (C11) groups what a caller should have ready under four headings: *Contacts* (spiller, property owner, location, contractors), *Circumstances* (material and SDS, time, cause, threats, whether stopped, actions taken), *Spill characteristics* (area, volume spilled vs. contained, recovered) and *Environmental pathways* (surface water, soil type, wells, utilities, storm drains/sewers). It also lists the National Response Center at **800-424-8802** and the EPA Region 5 line. IDEM's practice message is "report when in doubt". IDEM forms (C13, State Form 48373) follow a fixed pattern: general information, release information with coordinates, type, impact, cause, mitigation, recurrence prevention, and a certification signature.

**Utility spill protocols and plans (C14, C16, C17).**
- The Florida MODEF protocol (C14) is short (about 4 pages plus attachments) and procedural. It has emergency vs. non-emergency tracks, cleanup steps and confirmation sampling, and a records list: discharge or discovery date, location, PCB status determination, quantity, free product recovered, soil and groundwater volumes, disposal facility and manifests.
- The SDG&E plan (C16) is 9 pages plus attachments. Its sections are Introduction → Objectives → Mitigation measures → Implementation (materials and storage locations; hazard identification; containment; cleanup; labeling; accumulation and storage; notification) → References. It has a **Table 1** spill-kit materials list with storage locations, a **Table 2** notification matrix (scenario → agency → trigger), an emergency contact attachment, and an **Attachment C** "Spill or Release Notification" form (business, caller, chemical and quantity, containment, waterway or drain entry, location, date/time, injuries/evacuation, cleanup party, federal notification block).
- The National Grid bulletin (C17) adds utility-specific content: equipment types (transformers, regulators, capacitors, switchgear, reclosers), isolation perimeters, the rule "contain only after de-energization is confirmed", PCB label colour conventions, and "assume PCBs until proven otherwise".

**Real spill records and annual summaries (C18, C19).**
- A regulator's incident record for a utility transformer release (C18) carries: incident no., type, volume, contaminant, cause, risk evaluation, potential impacts, action taken/planned, waste disposal location, responsible party, county, legal description (Twp/Rng/Sec), lat/long and method, duration, EHS-substance flag, fatalities/injuries, affected medium, contained (Y/N), reported to NRC (Y/N), other agencies, and a dated update log with updated volume.
- A utility's annual spill summary (C19; about 370k customers, about 70 incidents per year) groups incidents by cause (human, natural, equipment malfunction, other). It reports gallons by fluid (transformer oil, hydraulic oil, coolant) and cubic yards of contaminated soil.

**Typical real procedure length.** Internal utility spill procedures run about 12–25 pages before forms. With the spill report form, quick-reference card, notification matrix and contact sheet, the rendered document is 20–35 pages. The spec's 3,500–5,000 words is at the thin end.

### (b) Gaps

| # | Sev. | Gap |
|---|---|---|
| T20-1 | **critical** | **Classification decisions are unaddressed.** Is utility equipment a *facility* or a *mode of transportation*? Where is the *facility boundary* for poles, padmounts and right-of-way assets? Is a fleet vehicle or bucket truck a *mode of transportation*? Is mineral oil, diesel or hydraulic fluid "petroleum"? Every threshold row depends on these answers, and the pack does not answer them for utility assets. Without an instruction, agents decide silently, and the T90 LLM reviewer may call the decision "overstates/understates the rule". Fix: a mandatory **"Company position"** classification table (new global §2.8), applying the more protective reading, recorded in `basis.interpretations`. |
| T20-2 | **critical** | **The report content elements are in the definitions section.** The task says "what information must be provided (each element a clause, per the pack)" but does not tell the agent the elements may be defined as a term in the definitions section. The likely failure is an EHS-F-201 form missing required elements. That fails coverage at S1 and misses S2 changes to the definition. |
| T20-3 | **critical** | **The federal reportable quantity** is referenced by a pack threshold but defined in federal law outside the pack. Without §2.7 (Group A G2) applied here, agents will fill in RQ numbers from memory. |
| T20-4 | **critical** | **Third-party notification** (downstream water users, affected property owners) and **"response takes precedence / burden of proving delay"** are not in the required structure. Both are substantive pack obligations and likely change targets. |
| T20-5 | major | **Compliance confirmation** (requesting the IDEM letter) is missing from close-out. Real utilities use it as the close-out record. |
| T20-6 | major | **No shared operational data.** Missing: spill kit inventory and locations, on-call rotation, emergency cleanup contractor, lab, waste hauler, SPCC plan IDs, PCB status codes in WAM, equipment oil-volume ranges, GIS layers for wellhead protection areas and sensitive waters. Each agent will invent these differently, and T12 and T21 will disagree. |
| T20-7 | major | **No spill log dataset.** T19 and T18 get quantified-impact datasets. T20 does not, although a reportability-threshold or timing change is exactly what a re-score would show ("N of 2024's 94 releases would now be reportable"). Real utilities keep such logs (C18, C19). |
| T20-8 | major | **Study references carry Florida and Minnesota values** (cleanup timelines, PCB tiers). No contamination warning. |
| T20-9 | major | **Related documents** (SPCC Plans, PCB Management Procedure, Waste Procedure, Federal Release Notification Protocol) have no canonical IDs, so T12, T20 and T21 will cite inconsistent IDs. |
| T20-10 | major | **App-B quick-reference card and App-C contact sheet are under-specified.** Real cards are 1–2 pages with a flowchart and a phone tree. The contact sheet must carry verified IDEM, NRC and EPA numbers (C10, C11). |
| T20-11 | minor | The current length (3,500–5,000 words) is thin against real procedures plus forms. Proposed: 5,500–8,000 words, rendered 20–32 pp. |
| T20-12 | minor | No rendering instructions (fillable spill report form, pocket card). |

### (c) Ready-to-paste spec text — T20

```markdown
## T20 — Spill Response & Reporting Procedure

**Doc ID:** RPL-ENV-PRO-005 · **Vertical:** Environmental · **Wave:** 2 · **Grounding:** `corpus/grounding/T20.json`
**Owner/Reviewer/Approver:** Hannah Brooks (P26) / Daniel Foster (P25) / Sandra Kim (P24)
**Outputs:** `corpus/docs/RPL-ENV-PRO-005/RPL-ENV-PRO-005_v3.1.md`, `RPL-ENV-PRO-005.basis.json`, `data/spill_events_2024.csv`, `data/README.md`, `scripts/generate_spill_data.py`, `render/RPL-ENV-PRO-005_v3.1.docx`, `render/RPL-ENV-PRO-005_v3.1.pdf`, `render/EHS-F-201_Spill_Report.pdf` (fillable), `render/RPL-ENV-PRO-005_App-B_Crew_Card.pdf`

### What this document is in the real world

The procedure that field crews, the Distribution Control Center (DCC), fleet and Environmental Services follow when oil or another substance is released. Typical RPL sources: mineral-oil dielectric fluid from pole-mount and padmount distribution transformers (vehicle strikes, storms, lightning, failures, theft/vandalism); substation power transformers, regulators, breakers and capacitors; diesel from the three standby generator belly tanks and from fleet fueling; gasoline/diesel and hydraulic fluid from fleet vehicles and bucket/digger-derrick trucks. It covers immediate response, de-energization and isolation, containment, the reportability determination, state notification and updates, third-party notifications, follow-up and written reports, cleanup and confirmation, waste disposal, close-out (including any compliance confirmation the pack provides for), and records. Crews use it from a pocket card. Environmental Services uses it from the full text and the spill report form.

**Study for structure and vocabulary only (do not copy text; every number in these is from another jurisdiction or federal law and is contaminated for this corpus):**
- Florida DEP, Mineral Oil Dielectric Fluid Emergency Response Protocol: https://floridadep.gov/sites/default/files/MinOilFluidEmergRespProtocol_13Sep16.pdf (emergency vs. non-emergency tracks; records list)
- SDG&E Spill Response and Notification Plan (CPUC filing): https://ia.cpuc.ca.gov/environment/info/dudek/CNF/20160801_CNF%20PLRP_Spill%20Response%20and%20Notification%20Plan_REDACTED.pdf (spill-kit table; notification matrix; notification form)
- National Grid first-responder bulletin on oil releases: https://outreach.ngridsafety.com/wp-content/uploads/2025/12/17661_NGrid_FR_MC_ebulletin_Oil_releases_flyer_el_1225.pdf (equipment list; isolate before contain; assume PCB until known)
- IDEM Emergency Response program page and quick-reference sheet: https://www.in.gov/idem/cleanups/investigation-and-cleanup-programs/emergency-response/ · https://www.extension.purdue.edu/news/inprepared/2021/04/_docs/er_quick_ref_sheet.pdf (caller-information headings; real contact numbers)
- ND DEQ incident summary for a utility transformer release (field list for a spill record): https://deq.nd.gov/FOIA/Spills/Summary_Reports/EIR5299_Summary_Report.pdf

### Purpose in the demo

Reportability tiers, notification timing, report content (including content defined as a term), third-party notification duties, exclusions and the emergency-response precedence rule are all clause-level change targets. The spill log lets Strata quantify the effect of a changed threshold or timing rule on 2024 events.

### Assessment scope (state this in §2)

The state reporting, containment and response obligations of 327 IAC 2-6.1 are covered in full. These are referenced in one clause each, as out of assessed scope, and recorded under `out_of_scope_references`, with **no values** stated from them:
- federal release notification (National Response Center), handled under RPL-ENV-PRO-008;
- federal reportable quantities;
- SPCC requirements (RPL-ENV-PLN-010/011);
- PCB requirements (RPL-ENV-PRO-006);
- hazardous waste rules (RPL-ENV-PRO-007).

### Company positions you must state (see §2.8)

Before drafting, read the pack's definitions section in full. Then write §7.1 "Classification of RPL release sources". It is a table with columns `Source · RPL classification for this procedure · Basis · Clause ID`, with one row for each of:
- pole-mount transformer
- padmount transformer / switchgear
- substation equipment inside a fenced substation
- standby generator belly tank at a service center
- fleet fueling at a service center
- fleet vehicle or bucket truck in transit
- the same vehicle parked at a work site
- an oil release discovered on customer property

For each row, state which pack category it is treated as (for example, the pack's facility or transportation provisions) and where the "facility boundary" is taken to be for that source. Do the same for whether each RPL fluid is treated as falling within a pack substance category.
- Where the pack's text answers a question, cite it.
- Where it does not, write the row as `Company position:` with no citation, choose the reading that makes **more** releases reportable, and record it in `basis.interpretations`.
- Never state a position that contradicts pack text.

### Required structure

1. Purpose
2. Scope & assessment scope (as above; sources, sites and personnel covered; contractors' obligations by reference to contract terms)
3. Definitions. Every term the pack defines that this procedure uses, with **identical meaning**, cited to the definitions section at subdivision level. Then company terms (release, spill kit, on-call Environmental Specialist, WAM PCB status code), labeled as company definitions.
4. Regulatory basis. Table: citation · heading · what it governs here. Then the out-of-scope references.
5. Roles & responsibilities. First responder/crew lead; DCC shift supervisor; on-call Environmental Specialist; Hannah Brooks (P26); Daniel Foster (P25); Sandra Kim (P24); Fleet Services; Contractor E (emergency response and remediation); Corporate Communications (role only). Include a RACI table.
6. **Immediate response.** Life safety, de-energize and isolate (no containment until the equipment is confirmed de-energized), stop the source, contain, protect drains and waterways, call the DCC. Company practice, *except* that where the pack states that emergency response actions take precedence over reporting, or places a burden of proof on delayed reporting, restate that with its citation in its own clause.
7. **Reportability determination**
   - 7.1 Classification of RPL release sources (company positions, above)
   - 7.2 Decision table, one clause ID per row: `Row · Substance category · Location / receiving medium · Condition or quantity (exactly as in pack) · Reportable? · Citation`. Cover every tier in the pack's facility and transportation sections, including tiers by harm, special or protected areas, receiving medium, inside vs. beyond a facility boundary, and releases where no response was done. Where a tier refers to a quantity defined outside the pack (for example, a federal reportable quantity), name the external term, record it as an out-of-scope reference, and state no number.
   - 7.3 Exclusions: one clause per exclusion, stating every condition attached to it exactly as in the pack. Add a Caution callout: an exclusion applies only when every one of its conditions is met.
   - 7.4 How to measure: estimating volume released (WAM nameplate volume, residual level, staining area method; company practice). Use the volume convention the pack or definitions require, if any.
   - 7.5 GIS screening: the GIS layers (§1.6 Table S) the on-call specialist checks to decide whether a special or protected area tier applies.
   - 7.6 When in doubt: Internal performance target. RPL reports any release whose reportability cannot be determined within the pack's time window.
8. **Notification to the state.** Who notifies (on-call Environmental Specialist; DCC as backup), channel and office (exactly as the pack names them), time limit and when the clock starts (exactly as in the pack), and updates when significant new information is found (exactly as in the pack). **Required content.** The pack may list report content in the definition of a term such as "spill report" rather than in the reporting section. Find it wherever it is and make one clause per element. Each element maps to a numbered field on EHS-F-201 (mapping table: element · citation · EHS-F-201 field).
9. **Notification of other affected parties.** Downstream water users, affected property owners and any others the pack requires, with the distance, condition and diligence standard exactly as in the pack. Include how RPL finds and documents them (GIS parcel layer, door-to-door log on EHS-F-201 Part F).
10. **Containment, response and cleanup obligations.** One clause per obligation the pack imposes. Company cleanup practice (excavation, confirmation sampling by Laboratory L, restoration) is labeled company practice.
11. **Follow-up and written reports.** Triggers, timing and content exactly as in the pack (including any written copy on request). Then RPL's internal 30-day closure package (company practice).
12. **Close-out.** Closure criteria, any compliance confirmation the pack provides for and how RPL requests it, and file closure in EHS-IMS.
13. **Waste handling and disposal.** Company practice; PCB-status handling by reference to RPL-ENV-PRO-006; waste by reference to RPL-ENV-PRO-007.
14. **Federal and other notifications.** A single out-of-scope clause naming the federal notification protocol (RPL-ENV-PRO-008), with no values.
15. Records & retention. Record series from §1.6 Table R, with retention by reference to RPL-LEG-RRS-001.
16. Training & drills. Annual ENV-T-01 refresher for all line, substation and fleet personnel; HAZWOPER awareness by reference; one tabletop drill per year per service center.
17. Related documents. §1.4 and §1.6 Table D IDs only.
18. Revision history (3.0, 2.x, 1.x; reasons do not reference future law)
19. Approval block

**Appendices (each field carries a clause ID):**
- App-A `EHS-F-201` Spill Report (Rev. 03/2025). Parts:
  - A Reporter & discovery
  - B Source & equipment (WAM asset ID, kVA, nameplate gallons, PCB status code, label colour)
  - C Substance & volumes (released / recovered / remaining)
  - D Location & pathways (address, county, lat/long and method, receiving medium, drains, distance to wells/waters per GIS screening)
  - E Reportability determination (7.2 row number, classification row from 7.1, exclusion considered)
  - F Notifications log (IDEM: date/time, call-taker, incident no.; updates; other affected parties; NRC per RPL-ENV-PRO-008; property owner; local fire)
  - G Response & cleanup (Contractor E ticket, soil/absorbent quantities, samples, manifests)
  - H Close-out (closure criteria, compliance confirmation request/receipt, sign-offs P26/P25)
  - Every state-required content element is a numbered field.
- App-B Crew quick-reference card (2 pages): one-page flowchart (safe → isolate → contain → call DCC → DCC pages on-call specialist); "Do / Do not" list; phone tree. No thresholds on the card: the card says "the on-call Environmental Specialist decides reportability".
- App-C Notification contact sheet (§1.6 Table X for external; §1.3 for internal; on-call rotation by role).
- App-D Spill kit inventory and locations (§1.6 Table S).
- App-E Worked examples: three fictional 2024 releases from the dataset (one padmount vehicle strike reaching a storm drain; one pole-mount failure on soil; one bucket-truck hydraulic hose failure). Each walks through 7.1 → 7.2 → 7.3 → 8 → 9 → 12, using only pack values.
- App-F Data dictionary for `spill_events_2024.csv`.

### Dataset (deterministic script, seed 2024)

`spill_events_2024.csv`, 80–110 rows, columns:
- `event_id` (`SPL-2024-nnnn`), `discovered_ts`, `stopped_ts`, `service_center`, `county`
- `source_type` (pole_transformer|padmount_transformer|substation_equipment|standby_generator|fleet_vehicle|bucket_truck_hydraulic|fueling), `rpl_classification` (from 7.1)
- `substance` (mineral_oil|diesel|gasoline|hydraulic_fluid|other), `pcb_status_code` (§1.6 Table S codes)
- `volume_released_gal`, `volume_recovered_gal`
- `receiving_medium` (impervious|soil_inside_boundary|soil_beyond_boundary|surface_water|storm_drain|sewer), `special_area_flag` (Y|N), `cause` (vehicle_strike|storm_wind|lightning|equipment_failure|vandalism_theft|hose_failure|overfill|other)
- `reportable` (Y|N, computed from the pack via `params`), `decision_row` (7.2 row ID), `exclusion_applied` (blank or 7.3 clause ID)
- `idem_report_ts`, `idem_incident_no`, `update_count`, `third_party_notice_required` (Y|N), `third_party_notice_ts`, `closed_date`, `compliance_confirmation_requested` (Y|N)

Rules:
- About 75% mineral oil.
- Volume distribution: most pole-mount releases are small. Padmount and substation releases are rarer and larger, bounded by §1.6 Table S nameplate ranges.
- Baseline state: every reportable event has an IDEM report within the pack's time limit and every required update. Non-reportable events have blank report fields.
- Thresholds, timing and exclusion conditions are read from `params`, which is populated from the basis file.

### Depth and anti-summary rules (in addition to §3.6)

- Every pack obligation appears as an operational step: who, when (clock start and limit), how (system, channel), and what record. A sentence that only restates the rule fails.
- The 7.2 decision table must be usable by the on-call specialist at 02:00 with a crew on the phone.

### Rendering (§3.7)

- `docx` skill → .docx → .pdf for the procedure.
- `pdf` skill for EHS-F-201 as a fillable AcroForm (field names = clause field IDs, e.g. `App-A.F12`) and for the App-B card (two pages, large type).
- Optional: the `dataviz` skill for one chart in App-E (2024 releases by cause and month).

### Length

5,500–8,000 words body including appendices (measured per §3.8). Rendered 20–32 pages.

### Self-check (in addition to §2.6)

- Every element of any defined report-content term in the pack maps to an EHS-F-201 field.
- Every 7.2 row, 7.3 exclusion and the §9 third-party duty carry a citation and parameters in the basis file.
- Every 7.1 row is either cited or written as a `Company position:` row and listed in `basis.interpretations`.
- No number from a study reference appears in the document (§2.1).
```

---

## T21 — Electrical Accident & Incident Reporting Procedure

### (a) Real-world anatomy

**Indiana rule (C21–C23); for the spec owner only.** 170 IAC 4-1-24, "Accident reports", is **a single short section with no subsections**. It quotes the statutory duty (IC 8-1-2-114) and requires telephone notice to the commission for a narrow class of accidents, with different timing depending on whether the accident happens during or outside business hours. It names one specific content item and requires a written report "as soon as all pertinent information has been accumulated". 170 IAC 4-1-3 is the general records-retention rule: a minimum period, an exception for other provisions and the statute, records kept in Indiana at the principal office or another location notified to the commission, and records open to commission examination.

Consequence: the "IURC reportability decision table" will legitimately have **very few reportable rows**, and most accident categories (non-fatal injuries, property damage, public contacts without a fatality) will be "not reportable to the IURC under the pack — internal reporting only". **This is the highest Snapshot-1 risk in Group C.** Other states' rules (C26 Kentucky: injury, property-damage and outage thresholds with a two-hour notice; C28 Missouri: first-business-day notice plus a 10-business-day written report; C27 Pennsylvania) are exactly what an agent will "fill in" from research or memory. Separately, the decision between business hours and after hours needs an operational definition of IURC business hours. That is a contact fact, not a pack value.

**Real accident-report forms.**
- PA UCTA-8 (C27): company, date of accident, date of report, location; fatality block (name, age, residence, category); injured block (same); causes and circumstances narrative; officer signature, name, title, phone.
- MO Electrical Contact Reporting Form (C28): utility, authorized representative, city/county/address, date/time, number injured / hospital admissions / fatalities, outage Y/N with consumers affected and restoration estimate, narrative (injury specifics, cause, equipment, work performed, weather, land use), signature.
- OSHA 301 (C29): 18 fields (employee identity and demographics, treating provider and facility, ER, overnight stay, case no., date, time began work, time of event, activity before, how it happened, injury description, object/substance, date of death).
- OSHA 300 (C29): columns A–L.

A real internal Incident Report (EHS-F-101) combines OSHA 301 fields with utility specifics: event class, voltage and equipment, circuit, work being performed, grounding and PPE, witnesses, police/fire report numbers, and a notification log.

**Typical internal procedure anatomy (utility EHS practice).** Purpose and scope; definitions and a severity classification (tiers 1–4 or A–D, including near misses and "serious injury and fatality potential"); immediate actions; an internal notification matrix (tier × role × time); external notifications (commission, state OSHA, police, Indiana 811 for dig-ins, insurers); scene preservation and evidence; investigation by tier (ICAM or TapRooT style; timelines); CAPA tracking and effectiveness review; lessons-learned bulletin; records; training. 12–25 pages plus forms.

Indiana is an **IOSHA state-plan state**, so a real Indiana document refers to IOSHA rather than federal OSHA alone. That is a realism point, and it stays out of scope (no values).

### (b) Gaps

| # | Sev. | Gap |
|---|---|---|
| T21-1 | **critical** | **The task framing invites invented reportability categories.** The "What this document is" text lists injuries, property damage and energized contacts, then says "which accidents must be reported to the IURC". With no guard, the agent will add other states' injury, dollar or outage thresholds (C26, C28). Fix: require that every category the pack does not make reportable is shown as "Not reportable to the IURC under the pack; internal reporting only", and forbid importing thresholds. |
| T21-2 | **critical** | **No definition of "business hours".** The pack's timing differs by business hours, but no shared fact defines them. Agents will invent hours or interpret them silently. Fix: an IURC business-hours contact fact in §1.6 Table X (orchestrator-verified), plus a company position for edge cases (holidays, weekends). |
| T21-3 | **critical** | **"Definitions identical to the pack where defined" cannot work.** The T21 pack (`4-1-3`, `4-1-24`) contains no definitions section. T00 must add `170 IAC 4-1-0.5`, `4-1-1` and `4-1-2` as context sections. The task must say that terms such as "serious injury" are company definitions. |
| T21-4 | major | **App-B "IURC accident report content checklist (every pack-required element a numbered field)" will be a near-empty form.** Real practice is an **IURC Telephone Notification Log** (time informed, business-hours determination, time called, IURC person reached, details given) plus the **written report template**. Restructure. |
| T21-5 | major | **No severity tiers, notification matrix times, incident ID format, CAPA ID format, investigation timelines, claims hand-off or Corporate Communications role.** All are company practice and will be invented inconsistently with T19 (DCC) and T20 (EHS-IMS). |
| T21-6 | major | **IOSHA vs. federal OSHA** is not addressed; Indiana 811 dig-in reporting and police/fire report numbers are missing. |
| T21-7 | major | **No incident log dataset.** An optional `incident_log_2024.csv` would let Strata quantify any S2 broadening of reportable accidents ("N 2024 events would now be IURC-reportable"). This mirrors T19. |
| T21-8 | minor | §1.4 approver P08 (Manager, Regulatory Affairs) ranks below reviewer P24 (Director, EHS). That is unusual but defensible: Regulatory Affairs owns the IURC relationship. Keep it for routing, but show P08's signature as "Approved (IURC reporting)" and add P16 as "Concurrence". No §1.4 change is needed. |
| T21-9 | minor | Length 3,000–4,500 is thin. Proposed: 4,500–6,500 words, 16–26 pp. |

### (c) Ready-to-paste spec text — T21

```markdown
## T21 — Electrical Accident & Incident Reporting Procedure

**Doc ID:** RPL-SAF-PRO-009 · **Vertical:** Workforce & Safety · **Wave:** 2 · **Grounding:** `corpus/grounding/T21.json`
**Owner/Reviewer/Approver:** Tyrone Jackson (P27) / Sandra Kim (P24) / Elena Vasquez (P08), with concurrence by Michael Brennan (P16) shown in the approval block (not in front matter)
**Outputs:** `corpus/docs/RPL-SAF-PRO-009/RPL-SAF-PRO-009_v2.0.md`, `RPL-SAF-PRO-009.basis.json`, `data/incident_log_2024.csv`, `data/README.md`, `scripts/generate_incident_data.py`, `render/RPL-SAF-PRO-009_v2.0.docx`, `render/RPL-SAF-PRO-009_v2.0.pdf`, `render/EHS-F-101_Incident_Report.pdf` (fillable), `render/EHS-F-102_IURC_Notification_Log.pdf` (fillable)

### What this document is in the real world

The Safety department's procedure for reporting, classifying and investigating incidents connected with RPL's electric facilities and work: employee and contractor injuries, members of the public contacting RPL facilities, vehicle incidents, property damage, energized-line contacts, dig-ins and near misses. It covers immediate actions, the internal notification matrix, the IURC notification decision and telephone/written reports, other external notifications (by reference), investigation, corrective and preventive actions (CAPA) and records. Workplace injury and illness recordkeeping and severe-injury reporting to Indiana OSHA (IOSHA) are handled in RPL-SAF-PRO-010 and only referenced here.

**Study for structure and form layout only (do not copy text; every threshold and time limit in these is from another state and is contaminated for this corpus):**
- PA PUC Electric Accident Report Form UCTA-8: https://www.puc.pa.gov/documents/utility-files/275/UCTA-8_Electric_Accident_Report_8-2023.pdf
- Missouri PSC Electrical Contact Reporting Form: https://psc.mo.gov/CMSInternetData/Electric/Electrical%20Contact%20Reporting%20Form%202024.pdf
- OSHA Forms 300/301 (field layout for EHS-F-101 Part B): https://www.osha.gov/sites/default/files/OSHA-RK-Forms-Package.pdf

### Purpose in the demo

The IURC accident rule is short. Any change to which accidents are reportable, the timing, the channel, or the content changes this document's decision table, notification log and written-report template. The incident log lets Strata quantify how many 2024 events a broadened rule would capture.

### Assessment scope (state this in §2)

IURC accident reporting (as the pack's accident section provides) and the associated record retention (as the pack's records section provides) are covered in full. These are referenced in one clause each and recorded under `out_of_scope_references`, with **no values**:
- the statutory duty the pack quotes (name the IC section only);
- IOSHA/OSHA recordkeeping and severe-injury reporting (RPL-SAF-PRO-010);
- DOT post-accident testing for CDL drivers (RPL-HR-PRO-015);
- Indiana 811 damage reporting (RPL-DO-PRO-020);
- third-party claims (RPL-CLM-PRO-001).

### Rules specific to this task

1. **Report only what the pack makes reportable.** The IURC decision table in §8 lists every incident category in §1.6 Table S-INC. For each category, the `Reportable to IURC?` column is "Yes" **only** where the pack's text makes it reportable, quoting the condition exactly. Every other category reads "No — not reportable to the IURC under <pack citation>; internal and other-agency reporting per §7 and §12". Do not import any injury, dollar, customer-count, hospitalization or outage threshold from any other source.
2. **Business hours.** Where the pack's timing depends on business hours, use the IURC office hours in §1.6 Table X as the operational definition, stated as `Company position:`. Treat weekends and the State of Indiana holidays listed in Table X as outside business hours. Record this in `basis.interpretations`.
3. **Definitions.** Use the pack's definitions with identical meaning where the pack defines a term. Terms the pack does not define (serious injury, near miss, SIF potential, energized contact) are company definitions, labeled as such, with no citation.

### Required structure

1. Purpose
2. Scope & assessment scope
3. Definitions
4. Regulatory basis (table) and out-of-scope references
5. Roles & responsibilities: crew lead / person in charge; DCC shift supervisor; Kevin Adeyemi (P23); Tyrone Jackson (P27); Sandra Kim (P24); Elena Vasquez (P08) and Marcus Lee (P09) for IURC contact; Jonathan Pierce (P03) for legal privilege; Michael Brennan (P16); Corporate Communications (role); Claims (role). RACI table.
6. **Immediate actions.** Make safe (de-energize, ground, establish a clear zone); emergency medical services; preserve the scene and evidence (photos, equipment tagged "Do not alter — EHS hold"); notify the DCC. Company practice.
7. **Severity classification and internal notification matrix.** Tiers from §1.6 Table S-INC, with a table `Tier · Examples · Who is called · Within (company target) · By whom · Logged in`. Company practice, written as `Internal performance target:` where a time is given.
8. **IURC notification decision.** Decision table `Category · Reportable to IURC? · Condition (exact pack text) · Citation · Clause ID` (Rule 1 above). A business-hours determination step (Rule 2).
9. **IURC telephone notice and written report.** Who calls (P08, or P09 as alternate; DCC shift supervisor after hours if the pack's timing requires it), the timing branch for each business-hours case exactly as in the pack, the content exactly as the pack requires (one clause per element), and the written report trigger exactly as in the pack. Then RPL's internal practice for compiling the written report (EHS-F-102 Part C), labeled company practice.
10. **Other external notifications.** A single list clause referencing the out-of-scope procedures (IOSHA, DOT, Indiana 811, police/fire, insurers), with no values.
11. **Investigation.** By tier (company practice): investigation lead, team, ICAM-style analysis, timeline targets, privileged review by P03 for Tier 1–2, and the report format.
12. **Corrective and preventive actions.** CAPA IDs `CAPA-2025-nnnn` in EHS-IMS, owner assignment, due dates, effectiveness review, closure approval, and a lessons-learned bulletin (`SAF-LL-2025-nn`).
13. **OSHA/IOSHA recordkeeping and reporting.** A single out-of-scope clause.
14. Records & retention: record series from §1.6 Table R, with any period the pack sets stated exactly and cited; otherwise by reference to RPL-LEG-RRS-001.
15. Training: SAF-T-05 annual; new supervisor module SAF-T-06; DCC drill twice a year on the IURC notification branch.
16. Related documents
17. Revision history (1.2, 1.1, 1.0)
18. Approval block (P27 prepared; P24 reviewed; P08 approved for IURC reporting; P16 concurrence)

**Appendices (each field carries a clause ID):**
- App-A `EHS-F-101` Incident Report (Rev. 03/2025). Parts:
  - A Event (EHS-IMS ID `INC-2025-nnnnn`, date/time, location with address/county/lat-long/pole or asset ID, tier, category)
  - B Person(s) involved (employee / contractor / public; OSHA 301-style fields for employees, with no regulatory values)
  - C Electrical details (voltage class, equipment, circuit ID, energized Y/N, grounds installed, PPE, minimum approach distance practice reference)
  - D Narrative (activity before, what happened, object or energy source)
  - E Witnesses and evidence
  - F Outage caused (OMS event ID cross-reference to RPL-DCC-PRO-003)
  - G Notification log (internal matrix times; IURC decision row from §8; police/fire report no.)
  - H Sign-offs
- App-B `EHS-F-102` IURC Accident Notification Log & Written Report. Parts:
  - A Decision (category, §8 row, reportable Y/N)
  - B Telephone notice (time RPL was informed; business-hours determination; time called; IURC person reached; each pack-required content element as a numbered field)
  - C Written report (one numbered field per pack-required element, followed by company sections: narrative, causes, actions, attachments)
  - D Filing record (date filed, channel, filed by)
- App-C Notification contact sheet (§1.6 Table X; internal on-call rotation by role)
- App-D Worked example: a fictional 2024 event from the dataset walked through §6–§12, using only pack values.
- App-E Data dictionary for `incident_log_2024.csv`

### Dataset (deterministic script, seed 2024)

`incident_log_2024.csv`, 260–340 rows, columns:
- `incident_id`, `event_ts`, `service_center`, `county`
- `person_type` (employee|contractor|public|none), `category` (§1.6 Table S-INC codes), `tier` (1–4)
- `energized_contact` (Y|N), `voltage_class`, `injury_severity` (none|first_aid|medical_treatment|restricted|lost_time|hospitalized|fatal)
- `property_damage_est_usd`, `outage_event_id`
- `iurc_reportable` (Y|N computed from the pack via `params`), `informed_ts`, `business_hours` (Y|N per Rule 2), `iurc_phone_ts`, `iurc_written_ts`
- `capa_count`, `investigation_closed_date`

Rules:
- Mostly near misses, vehicle incidents and first-aid cases.
- IURC-reportable events: 0 or 1 in 2024. If 1, it is a fictional public-contact event, its timestamps comply with the pack, and it is the App-D example with no personal details beyond a fictional name.
- Baseline: every IURC-reportable row complies with the pack's timing.

### Rendering (§3.7)

- `docx` skill → .docx → .pdf for the procedure.
- `pdf` skill for the fillable EHS-F-101 and EHS-F-102 (field names = clause field IDs).

### Length

4,500–6,500 words body including appendices. Rendered 16–26 pages.

### Self-check (in addition to §2.6)

- §8 has one row for every Table S-INC category. Only pack-supported rows say "Yes".
- Every pack-required content element appears in §9 and as a field in EHS-F-102 Parts B and C.
- No threshold, time limit or dollar amount from any source other than the pack or §1.6 appears in §8–§9.
```

---

## T10 — Regulatory Obligations Register

### (a) Real-world anatomy

- **Register columns in practice** (C30–C32):
  - Ref/code; requirement or obligation title and description in plain language; source (law/standard/contract); type; applies to (business area); how we comply (control or implementing process); owner or responsible officer; status (C30 offers Pending Review, Due for Review, Non Compliant, Partially Compliant, Fully Compliant, Non Applicable); priority or risk rating (impact × likelihood); frequency or deadlines; evidence; last reviewed; monitoring status.
  - C31 recommends trigger-based review: "whenever a law, regulator or major contract changes".
- **GRC data model** (C33, ServiceNow): Authority Document → **Citations** (specific requirements) ↔ **Control Objectives** (the hub where external requirements and internal policy converge) → **Controls** applied to **Entities** (department, system, process), with many-to-many bridges. A real utility register exported from a GRC tool is therefore *normalized*: obligation rows reference control IDs and entity IDs, and a single control can satisfy several obligations.
- **Typical size.** An enterprise register at an IOU holds thousands of rows across all regimes. For this corpus's scope (170 IAC 4-1, 4-9, 16, selected 170 IAC 1, 327 IAC 2-6.1, which is about 60–70 sections), an obligation-per-requirement decomposition gives roughly **150–260 rows**, with 15–30% "Not applicable" (REMC-, municipal- or generation-only provisions).
- **Deliverable form.** A filterable workbook (Register, Controls, Not Applicable rationale, Lookups, Change Log, Instructions), plus a cover memo to the CCO with summary statistics and an attestation.

### (b) Gaps

| # | Sev. | Gap |
|---|---|---|
| T10-1 | **critical** | **Clause-ID form for CSV rows is undefined.** §3.2 says "the row's primary key is its clause ID", but the register uses `OBL-0001`. Without the `RPL-CMP-REG-001:OBL-0001` form, the engine and T91 cannot route register findings. |
| T10-2 | **critical** | **Clause-ID drift after T90 fixes.** T10 references Wave 2 clause IDs. If the T90 fix loop renumbers a Wave 2 clause, T10 breaks silently. Fix: a clause-ID freeze after the Wave 2 QA pass (global §0.1). |
| T10-3 | **critical** | **The worker prompt forbids reading files outside one's own pack and task.** T10 needs `corpus/_global/company_profile.yaml` (applicability attributes) and all Wave 2 docs and basis files. The prompt does not authorize the `_global` read. |
| T10-4 | major | **Uniform `compliance_status = Compliant`** with no risk rating, review frequency, control testing or next-review date reads as a stub. Real registers carry risk and testing fields. Add non-gap status detail without implying non-compliance. |
| T10-5 | major | **No decomposition rule.** "One row per distinct obligation" is ambiguous, so row counts will vary 3× between runs. Give a deterministic rule: one row per subsection or sentence containing an obligation verb, plus definitions rows excluded. |
| T10-6 | major | **No separate controls table.** A real register is normalized (C33). Add `controls.csv`. |
| T10-7 | major | **"List it in the T90 report"** asks a Wave 3 generator to write into a Wave 4 artifact. It should go to `basis.gaps` and the agent's final message. |
| T10-8 | major | **Decoy consistency.** The T10 pack is a union. If T00 samples decoys per pack, T10's high set differs from component packs, and T91's `decoys_correctly_unchanged` becomes ambiguous. Fixed in T00 (global sampling per citation). |
| T10-9 | minor | No rendering (xlsx workbook with validation, filters, frozen header). |

### (c) Ready-to-paste spec text — T10

```markdown
## T10 — Regulatory Obligations Register

**Doc ID:** RPL-CMP-REG-001 · **Vertical:** Compliance & Legal · **Wave:** 3a (after Wave 2 clause-ID freeze) · **Grounding:** `corpus/grounding/T10.json`
**Owner/Reviewer/Approver:** Priya Raman (P06) / David Okafor (P05) / Margaret Ellison (P04)
**Inputs (read-only):** `corpus/_global/*`; every Wave 2 document and basis file (`corpus/docs/*/*.md`, `corpus/docs/*/*.basis.json`); `corpus/qa/clause_id_freeze.json`
**Outputs:** `corpus/docs/RPL-CMP-REG-001/RPL-CMP-REG-001_v4.0.md` (cover memo + methodology), `data/obligations_register.csv`, `data/controls.csv`, `data/README.md`, `RPL-CMP-REG-001.basis.json`, `render/RPL-CMP-REG-001_v4.0.xlsx`, `render/RPL-CMP-REG-001_v4.0_Memo.pdf`

### What this document is in the real world

The compliance function's master list of regulatory obligations (a "compliance obligations register" in ISO 37301 terms), exported from RPL's GRC tool. Each row is one obligation derived from a specific provision, with its type, trigger, timing, key parameters, applicability decision, accountable owner, the implementing documents and controls, the evidence, the review dates and a risk rating. The CCO uses it to answer "are we covered?" and to route regulatory changes to owners.

**Study for column design (do not copy text):**
- Camms Compliance Obligations Register field definitions: https://camms.atlassian.net/wiki/spaces/CD/pages/77496321
- Legal & Regulatory Requirements Register template: https://www.securityscientist.net/blog/legal-and-regulatory-requirements-register-template/
- ServiceNow Policy & Compliance data model (authority document → citation → control objective → control): https://www.servicenow.com/community/grc-articles/policy-and-compliance-management-architecture-and-data-model/ta-p/3605503

### Decomposition rule (deterministic)

1. For every section in the pack (active or not), read the body text by subsection (use the pack's `subsections` spans).
2. Create one obligation row for each subsection or list item that imposes a duty, prohibition, permission-with-condition, customer right or record/report requirement on a utility. If a subsection holds several distinct duties with different triggers or parties, create one row per duty.
3. Definitions, purpose and saving clauses do not create rows. Record them in `basis.considered_no_obligation` with the reason.
4. A section that applies only to other utility types gets **one** `Not applicable` row, with the rationale citing the applicability text (§2.3.7) and the T01 attribute used.
5. Expected size: 150–260 rows. If you land outside this range, re-check the rule. Do not pad or merge to hit the range.

### Register columns (`obligations_register.csv`)

`clause_id` (`RPL-CMP-REG-001:OBL-nnnn`, primary key) · `obligation_id` (`OBL-nnnn`) · `citation` (most specific level) · `section_heading` · `regulator` (IURC|IDEM) · `jurisdiction` (IN) · `obligation_title` (≤ 10 words) · `obligation_summary` (one or two sentences, faithful to the pack) · `obligation_type` (report|notice|record|test|standard|prohibition|procedure|customer_right) · `trigger` · `frequency_or_deadline` · `key_parameters` (values exactly as in the pack, `; `-separated) · `applicability` (Applies|Not applicable) · `applicability_rationale` · `applicability_attribute` (T01 attribute key, if used) · `accountable_owner_id` (P-ID) · `process_owner_department` · `implementing_documents` (`DOC_ID:clause` list, frozen IDs only) · `control_ids` (`CTL-xx-nnn` list → `controls.csv`) · `evidence_record` (record series ID from §1.6 Table R) · `risk_rating` (High|Medium|Low; company assessment of impact × likelihood of non-compliance) · `review_frequency` (Quarterly|Semi-annual|Annual) · `last_reviewed` (2025-03-14 to 2025-03-20) · `next_review` · `compliance_status` (Compliant | Compliant – control test scheduled; never a gap status) · `last_control_test` (date in 2024 or blank for new controls) · `notes`

### Controls table (`controls.csv`)

`control_id` · `control_title` · `control_description` · `control_type` (preventive|detective) · `nature` (manual|automated|IT-dependent manual) · `frequency` · `control_owner_id` · `system` (§1.1 core systems) · `evidence_record` · `obligation_ids` (list). Expected 60–110 controls. One control may serve several obligations.

### Rules

- Every active section in the pack yields at least one row or one `considered_no_obligation` entry.
- `implementing_documents` must resolve to clause IDs in `clause_id_freeze.json`. If an applicable obligation has no implementing clause, set the field to `DEPT-PROCESS:<department>` and list it in `basis.gaps` and in your final message. **Do not invent clause IDs.**
- Every `key_parameters` value matches the pack exactly and is recorded in the basis file with `s1_quote`.
- `accountable_owner_id` for an obligation implemented by a Wave 2 document is that document's §1.4 owner, unless the obligation sits in a section another document owns more directly. Record the reason in `notes`.
- Cover memo (`.md`, 2,000–3,000 words): purpose; scope (IURC Title 170 rules in scope; IDEM 327 IAC 2-6.1); methodology (decomposition rule, applicability analysis using T01 attributes, mapping to documents and controls, risk rating method); applicability decisions summary; ownership model and change-routing workflow (who is notified when a cited provision changes; reviewer and approver per owner); review cadence; summary statistics (rows by type, regulator, applicable vs. not applicable, risk rating; obligations per implementing document); known limitations (the `basis.gaps` list in prose, with no future-law references); attestation and sign-off.

### Rendering (§3.7)

`xlsx` skill: workbook with sheets
- `Instructions`
- `Register` (frozen header, autofilter, data validation lists for enumerated columns, conditional formatting on `risk_rating` and `next_review`)
- `Controls`
- `Not Applicable` (filtered view)
- `Lookups`
- `Change Log` (v3.0 → v4.0 changes)
- `Statistics` (a pivot-style summary; one bar chart via the `dataviz` skill palette)

The memo goes to PDF via the `docx` skill. CSV stays canonical.

### Self-check (in addition to §2.6)

- CSV primary keys match the clause-ID grammar (§3.2) and are unique.
- Every `implementing_documents` entry resolves to the freeze file.
- Every `Not applicable` row's rationale quotes or cites the pack's applicability text or a T01 attribute.
- Row count is between 150 and 260, or the deviation is explained in `basis.notes`.
```

---

## T11 — Regulatory Reporting Calendar 2025

### (a) Real-world anatomy

- **Indiana practice** (C34): the IURC annual report for electric utilities is filed electronically through the IURC Electronic Filing System (iurc.portal.in.gov). IOUs also file a Periodic Review form and FERC Form 1 supplemental pages. The page states a due date. *This report records it only as an example of an out-of-scope row type; it must not enter the spec as a value.*
- **Other commissions:** due-date conventions are "due April 30 for the prior calendar year" or "within 30 days after receiving the auditor's report" (C35). Some open a compliance docket per rule per year (C36).
- **Real calendar shape.** A master list with columns for item, regulator, rule, frequency, period covered, due date, internal draft date, preparer, reviewer, signatory, channel, docket/form, status; month-by-month views; event-driven "clocks" (notification windows) kept separately as response playbooks. A Regulatory Affairs calendar at an IOU commonly has 80–200 dated items a year. It includes many internal checkpoints (drafts, legal review, officer sign-off) that are company practice.

### (b) Gaps

| # | Sev. | Gap |
|---|---|---|
| T11-1 | **critical** | **Date contradiction.** T11 v1.0 is approved 2025-01-03, but its `source_procedure` references the clause IDs of T19, T20 and T21 versions approved 2025-02-19, 2025-03-05 and 2025-03-12. A dated calendar cannot cite procedure versions that did not yet exist, and §3.3 also requires 2–4 prior versions, which is impossible for a v1.0. Fix §1.4: T11 becomes v1.2, approved 2025-03-14, effective 2025-03-17, with a revision history v1.0 (2025-01-03, annual roll) → v1.1 → v1.2. |
| T11-2 | **critical** | **Must-cover contradiction.** The T11 pack is the union of the T16, T19, T20 and T21 scopes, which includes `170 IAC 16-` (complaints) and rules with no reporting duty. §2.4 requires every active applicable section to be cited at least once, which forces phantom references. Fix: the global `considered_no_obligation` category (§2.4) and a T11 rule. |
| T11-3 | **critical** | **The scope misses report obligations in other packs.** Any reporting or notice-to-regulator duty in T13/T14/T15/T18 scopes (e.g., the 4-1-4 "records and reports of meter purchases and tests" heading) is invisible to T11. Fix: build T11 from T10's register (rows of type `report`/`notice` whose recipient is a regulator), so T11 runs in Wave 3b after T10. Its pack becomes the T10 union. |
| T11-4 | major | **Thin output.** With only pack-derived recurring items, the CSV will hold about 3–8 dated rows. Real calendars are dense. Add internal checkpoints and company recurring compliance activities (register quarterly reviews, KPI reports, drills, training deadlines) as `type=internal`, and out-of-scope filings as `type=tracked_external` with **internal target dates only** (no regulatory due rule), `assessed=false`. |
| T11-5 | major | **Due-date computation needs a time-computation rule** (weekends, holidays). If the IURC procedural rules on computing time are not in scope, agents will invent one. Fix: T00 adds 170 IAC 1 sections whose headings match time computation and filing. If none exists, the agent uses a `Company position:` roll-back to the preceding business day. |
| T11-6 | major | **`due_rule` "verbatim from the pack"** conflicts with §2.3 plain-English rewording. Define it as an exact quote ≤ 40 words, which then serves as the parameter's `s1_quote`. |
| T11-7 | minor | No rendering. A real calendar is an xlsx plus a printable month grid. |

### (c) Ready-to-paste spec text — T11

```markdown
## T11 — Regulatory Reporting Calendar 2025

**Doc ID:** RPL-REG-CAL-2025 · **Vertical:** Compliance & Legal · **Wave:** 3b (after T10) · **Grounding:** `corpus/grounding/T11.json` (same scope as T10)
**Owner/Reviewer/Approver:** Marcus Lee (P09) / Elena Vasquez (P08) / Thomas Whitfield (P07)
**Version / dates (per §1.4 as amended):** v1.2 · effective 2025-03-17 · approved 2025-03-14 · revision history: v1.0 2025-01-03 (annual roll from RPL-REG-CAL-2024), v1.1 2025-02-24 (aligned to RPL-DCC-PRO-003 v4.2), v1.2 2025-03-14 (aligned to RPL-ENV-PRO-005 v3.1 and RPL-SAF-PRO-009 v2.0)
**Inputs (read-only):** `corpus/_global/*`; T10 outputs; Wave 2 documents and basis files; `corpus/qa/clause_id_freeze.json`
**Outputs:** `corpus/docs/RPL-REG-CAL-2025/RPL-REG-CAL-2025_v1.2.md`, `data/reporting_calendar_2025.csv`, `data/README.md`, `RPL-REG-CAL-2025.basis.json`, `render/RPL-REG-CAL-2025_v1.2.xlsx`, `render/RPL-REG-CAL-2025_Month_View.pdf`

### What this document is in the real world

Regulatory Affairs' master calendar of every recurring and event-driven report or notice the company owes regulators in 2025, plus the internal checkpoints that produce them. It gives due dates or response clocks, preparers, reviewers, signatories, submission channels and the procedure that produces each item. Teams work from it daily, and it is reviewed in the monthly compliance meeting.

### Row types

| `type` | What | Regulatory values? | `assessed` |
|---|---|---|---|
| `recurring` | Periodic reports or filings required by the pack | Due rule quoted from the pack; date computed | true |
| `event_driven` | Notices or reports triggered by an event (interruption, spill, accident, plan change) | Timing rule quoted from the pack; no date | true |
| `internal` | Company checkpoints and recurring compliance activities (draft due, legal review, register quarterly review, monthly complaint KPI report, DCC and spill drills, annual training completion) | None; company dates | false |
| `tracked_external` | Filings outside the assessed scope (IURC annual report and periodic review via the IURC Electronic Filing System; FERC Form 1; EIA surveys; IOSHA/OSHA summaries; IDEM non-spill reports) | **None.** `due_rule` = "Per <agency> instructions; tracked by <owner>"; `due_date_2025` blank; `internal_target_date` = company date | false |

### Calendar columns (`reporting_calendar_2025.csv`)

`clause_id` (`RPL-REG-CAL-2025:CAL-2025-nnn`, primary key) · `calendar_id` · `type` · `report_name` · `regulator` · `citation` (`recurring` and `event_driven` only) · `trigger_or_period` · `due_rule` (exact pack quote ≤ 40 words for assessed rows) · `due_date_2025` (computed for `recurring`; blank otherwise) · `internal_target_date` · `internal_draft_due` · `preparer_id` · `reviewer_id` · `signatory_id` · `submission_channel` · `form` (e.g. State Form 54646; EHS-F-201; EHS-F-102) · `source_procedure` (`DOC_ID:clause`, frozen) · `register_obligation_ids` (T10 `OBL-` list) · `status` (Scheduled|Standing — event-driven) · `assessed` (true|false)

### Rules

- Assessed rows are exactly the T10 register rows with `obligation_type` in (report, notice) whose recipient is a regulator and `applicability = Applies`. One calendar row per obligation; event-driven obligations with several clocks (initial / update / final) get one row per clock.
- Every other section in the pack that creates no report or notice to a regulator goes in `basis.considered_no_obligation` with a one-line reason. Do not cite it in the calendar.
- Date computation: if the pack contains a rule on computing time or filing deadlines, apply it and cite it. Otherwise write a `Company position:` rule (deadlines falling on a weekend or State holiday are met on the preceding business day) and record it in `basis.interpretations`.
- `internal_draft_due` is 10 business days before the regulatory due date for recurring items (company practice). For `internal` and `tracked_external` rows, use plausible company dates.
- Expected size: 45–90 rows in total, of which assessed rows are whatever the register yields. Do not invent assessed rows.
- The `.md` (1,500–2,500 words): purpose; how the calendar is built from the register; maintenance (owner, monthly review, change log); escalation rule for missed internal drafts (P09 → P08 → P07, with company timings); event-driven response clocks in a playbook table (`Event · Clock · Rule (quoted) · Procedure`); a month-by-month view (January–December table); out-of-scope tracked items; approval block.

### Rendering (§3.7)

- `xlsx` skill workbook: `Calendar` (filters, validation), `By Month`, `Event Clocks`, `Lookups`.
- One-page landscape month-grid PDF via the `pdf` skill. Optionally a 12-month timeline strip via the `dataviz` skill.
- The `.md` memo goes to PDF via `docx`.

### Self-check (in addition to §2.6)

- Every assessed row maps to a T10 obligation, a frozen `source_procedure` clause and a basis parameter with `s1_quote`.
- No `tracked_external` row carries a citation, a regulatory due rule or a `due_date_2025`.
- Computed dates follow the stated computation rule.
```

---

## T12 — Records Retention Schedule

### (a) Real-world anatomy

- **18 CFR 125.3** (C37): numbered items grouped under functional headings (Corporate and General; IT Management; General Accounting; Insurance; Operations and Maintenance; Plant and Depreciation; Purchase and Stores; Revenue Accounting and Collection; Tax; Treasury; Miscellaneous). Two columns (item/description; retention). Conventions: "years after…", "for life of corporation", "after plant is retired", "Destroy at option".
- **Washington State utility schedules** (C38, C39): function → activity hierarchy. Columns: **Disposition Authority Number (DAN)**, Description of Records (with scope notes and inclusions), **Retention and Disposition Action** ("Retain for N years after <trigger> then Destroy"), **Designation** (Archival / Non-Archival; Essential / Non-Essential; OPR / OFM). About 200+ series over about 50 pages, with a glossary and indexes. Series include outage logs, apparatus failure reports, meter shop reports, PCB transformer history and termination notices.
- **Colorado Schedule No. 60** (C40): decimal numbering (60.010…). Front-matter rules (no destruction during investigations or proceedings; retention applies to content regardless of format). Authority cited in brackets (CFR, NERC, CRS).
- **Florida PSC overlay** (C42): a state commission adopting 18 CFR 125 with listed exceptions. This shows the real IOU pattern of a **state overlay on the FERC schedule**.
- **Policy body** (C41): policy and scope; procedures; destruction verification; **legal holds** issued by counsel that override schedules, with recipient acknowledgments and release notices.
- **IOU reality:** one company retention period per series (often longer than the regulatory minimum), with the regulatory driver and citation recorded separately.

### (b) Gaps

| # | Sev. | Gap |
|---|---|---|
| T12-1 | **critical** | **Circular references between Wave 2 and T12.** Wave 2 documents say "retention by reference to RPL-LEG-RRS-001", but no series IDs exist until T12 runs, so each Wave 2 document will invent different series IDs and names. Fix: a canonical **records series catalog (IDs and titles only, no periods)** in §1.6 Table R, used by Wave 2 and filled by T12. |
| T12-2 | major | **`retention_period` = regulatory minimum, with longer company retention only in `description`, is unrealistic.** Real schedules state the company's retention in the retention column. Proposed: `regulatory_minimum` (exact pack value, cited) plus `rpl_retention`. `rpl_retention` equals the minimum unless a named business reason applies (capped at 20% of regulatory rows, each recorded in basis). This keeps change-sensitivity: an S2 increase above `rpl_retention` produces a finding. |
| T12-3 | major | **No function → activity hierarchy, designation (vital/archival), media or privacy columns, or event-trigger vocabulary.** Real schedules have all of these. |
| T12-4 | major | **Size not bounded.** Proposed: 120–180 series (regulatory 25–45; business 70–110; out-of-scope regulatory 15–30). |
| T12-5 | major | **The statute named in the general retention section** (IC 8-1-2-40 in the real rule) and **18 CFR 125** must be §2.7 out-of-scope references with no values. 18 CFR 125 item numbers may be cited as references in out-of-scope rows (not assessed). |
| T12-6 | major | **The records-location duty** in the general retention section (records kept in Indiana; location notified) is an obligation the schedule's policy must restate if the pack contains it. The spec does not ask for it. |
| T12-7 | minor | No rendering (xlsx and a landscape PDF appendix). |

### (c) Ready-to-paste spec text — T12

```markdown
## T12 — Records Retention Schedule

**Doc ID:** RPL-LEG-RRS-001 · **Vertical:** Compliance & Legal · **Wave:** 3b (after T10) · **Grounding:** `corpus/grounding/T12.json` (union of T13–T21 scopes)
**Owner/Reviewer/Approver:** Linda Nguyen (P12) / Jonathan Pierce (P03) / Catherine Brandt (P02)
**Inputs (read-only):** `corpus/_global/*` (including §1.6 Table R); T10 register (`obligation_type = record` rows); every Wave 2 document and basis file; `corpus/qa/clause_id_freeze.json`
**Outputs:** `corpus/docs/RPL-LEG-RRS-001/RPL-LEG-RRS-001_v7.2.md`, `data/retention_schedule.csv`, `data/README.md`, `RPL-LEG-RRS-001.basis.json`, `render/RPL-LEG-RRS-001_v7.2.xlsx`, `render/RPL-LEG-RRS-001_v7.2.pdf`

### What this document is in the real world

Legal's Records & Information Management policy and schedule. For each record series it states how long RPL keeps the record and why (regulatory minimum and citation, or business need), the event that starts the clock, the system of record, the owner, the media, vital-record status and the disposition. It sets the rules for legal holds, destruction and certification. Investor-owned utilities overlay state commission rules on the FERC retention schedule and add business needs.

**Study for format only (retention periods in these are other jurisdictions' and are contaminated for this corpus):**
- 18 CFR 125.3 (item structure and wording conventions): https://www.law.cornell.edu/cfr/text/18/125.3
- Washington State Utility Services Records Retention Schedule: https://www.sos.wa.gov/sites/default/files/2025-06/utility-services-records-retention-schedule.PDF
- Colorado State Archives Schedule No. 60: https://archives.colorado.gov/sites/archives/files/documents/Schedule%20No.%2060.pdf
- NRECA model Record Retention & Destruction Policy (legal hold structure): https://www.electric.coop/wp-content/uploads/2018/03/Policy-01_04-Record-Retention-and-Destruction-Policy.pdf

### Schedule columns (`retention_schedule.csv`)

`clause_id` (`RPL-LEG-RRS-001:<series_id>`, primary key) · `series_id` (from §1.6 Table R for every listed series; new series continue the numbering per department) · `function` · `activity` · `record_series` · `description` (scope notes, inclusions and exclusions) · `examples` · `system_of_record` (§1.1 systems or a named file location) · `media` (electronic|paper|hybrid) · `record_owner_department` · `retention_trigger` (controlled vocabulary: after creation; after calendar year end; after closure/resolution; after meter retirement; after asset retirement; after superseded; after employee separation; permanent) · `regulatory_minimum` (exact pack value, `regulatory` rows only) · `citation` (`regulatory` rows only) · `rpl_retention` (stated as "N years after <trigger>" or "Permanent") · `retention_driver` (regulatory|business|out_of_scope_regulatory) · `extended_retention_reason` (required if `rpl_retention` exceeds `regulatory_minimum`) · `disposition` (Destroy – confidential shred|Destroy – secure delete|Transfer to archives|Review) · `vital_record` (Y|N) · `privacy_class` (Public|Internal|Confidential|Restricted-PII) · `legal_hold_eligible` (Y) · `related_documents` (DOC_IDs) · `register_obligation_ids` (T10 `OBL-` list)

### Rules

- **Coverage of Wave 2 records:** every record named in any Wave 2 "Records & retention" section maps to a series, and every §1.6 Table R series appears.
- **Regulatory rows:** where the pack sets a retention period (in the general records section or scattered in other sections), the row is `retention_driver = regulatory`, cites the provision at the most specific level, and states `regulatory_minimum` exactly. `rpl_retention` equals `regulatory_minimum` unless a named business reason applies (litigation exposure, asset life, rate-case support). At most 20% of regulatory rows may be extended, each recorded in the basis file under `value_ledger` with `source: company_practice`.
- **Statutes and federal rules** named by the pack or used by a real schedule (e.g., the statute the pack's general records section names; 18 CFR Part 125; IOSHA/OSHA recordkeeping; TSCA PCB records) are `out_of_scope_regulatory` rows. Name the reference (an 18 CFR 125.3 item number is allowed), set `rpl_retention` to a company period labeled "company period; federal/statutory schedule governs if longer", and state **no** period as the regulatory value.
- **Business rows** (HR, finance, fleet, IT, facilities, corporate): realistic, no citations.
- If the pack's general records section imposes where records are kept or how the commission is told their location, restate it in the policy with its citation and make RPL's current records-location notice a series.
- Expected size: 120–180 series.
- **The `.md` (3,000–4,500 words):** policy statement; scope; definitions (record, non-record, vital record, legal hold, disposition); roles (P12, department records coordinators, IT, P03, P02); general rules (format neutrality; no destruction during investigations, audits or proceedings); records location (as above); legal holds (issuance by P03, acknowledgment within 5 business days (company practice), suspension of disposition in DCS and system purge jobs, release notice); annual destruction cycle and Certificate of Destruction form `LEG-F-021` (template appendix); exceptions and schedule change requests (`LEG-F-022`); schedule summary by department; approval block. The full schedule appears as a landscape appendix table.

### Rendering (§3.7)

- `xlsx` skill: `Schedule` (grouped by function, filters, validation), `Regulatory Basis` (regulatory rows only), `Index` (A–Z by series title), `Change Log` (7.1 → 7.2).
- `docx` skill → PDF for the policy, with the schedule as a landscape appendix.

### Self-check (in addition to §2.6)

- Every `regulatory_minimum` has an `s1_quote` parameter.
- `rpl_retention` is never shorter than `regulatory_minimum`.
- Every Table R series is present. Every Wave 2 records clause maps to a series.
- No `out_of_scope_regulatory` row asserts a regulatory period.
```

---

## (d) Global findings and replacement text

### Summary of global gaps

| # | Sev. | Area | Gap |
|---|---|---|---|
| G-1 | **critical** | §0.1 prompt | The prompt says "if your grounding pack is missing, stop". T01–T03 and T90 have no pack, so they would stop. It forbids reading `corpus/_global/*`, which Wave 2 and 3 need. Wave 3 needs other tasks' outputs, but the prompt says "do not read any other task section" without distinguishing *spec sections* from *output files*. |
| G-2 | **critical** | §1.2 / §1.4 | **Snapshot-2 information is exposed to generators.** §1.2 lists Snapshot-2 dates and "IAC (2026 edition)", and the §1.4 trailing paragraph describes S2 changes taking effect before approval. Generators read both. That tells an LLM that a 2026 edition exists and invites recall of real 2025 amendments. Move both to an orchestrator-only appendix. |
| G-3 | **critical** | T00 | **Range scopes break under string matching.** `4-1-4 to 4-1-14` fails lexicographically and decimal sections (`16.5`) are mishandled; new S2 sections in a range are undefined. **Decoys are sampled per pack**, so union packs (T10–T12) disagree with component packs. **No subsection spans**, although citations and findings are subsection-level. **No status enum** ("approved" is not an IAC status). **No leak test.** No renumber detection without `prior_version_id`. No list of external refs (IC, CFR) for §2.7. |
| G-4 | **critical** | §3.2 / §3.4 | **Clause boundaries are undefined** (does `5.3` include `5.3.2`?). Table and CSV IDs lack the doc prefix, and there is no ID grammar. Basis has no text span or hash, no subsection mapping, no cross-document dependencies, no routing override, no interpretations, and no `considered_no_obligation`. |
| G-5 | **critical** | §2.4 | **Must-cover vs. register-type documents.** T11 and T12 cannot "cite at least once" sections that create no report or record duty. Add a `considered_no_obligation` disposition. |
| G-6 | **critical** | §2 | **No rule for interpretive classifications** (T20 facility vs. transportation, mineral oil as petroleum; T21 business hours). Add §2.8 "Company positions". |
| G-7 | **critical** | §0.1 / QA | **No clause-ID freeze** between Wave 2 QA and Wave 3. T90 fixes can silently break T10–T12 references. |
| G-8 | major | §2.4 / decoys | **Depth asymmetry is a signal.** Requiring full parameter restatement only for "high" sections makes changed sections visibly denser than others. Decoys at 50% leave P(changed \| high) = 2/3. Proposed: **coverage parity** (restate every material parameter of every applicable section the document's process touches) plus a 1:1 decoy ratio sampled globally per citation. |
| G-9 | major | §1.4 | T11 version and dates contradiction (see T11-1). No `Supersedes` column (Group A G1 also proposes one). |
| G-10 | major | §1.6 | Missing shared EHS, records and referenced-document data (Tables S, S-INC, R, D, X). |
| G-11 | major | §3.6 | The realism standard is 4 bullets. No measurable anti-summary rules, artifact minimums, banned phrases or Definition of Done. |
| G-12 | major | T90 | **The checks would not catch thin or unrealistic documents.** There is no realism rubric and no exemplar comparison. The numeric check fails on "ten (10)" and on derived dates. There is no check for phantom or uncited regulatory sentences, subsection placement, render parity, ID grammar, revision-history dates, or Snapshot-2 contamination. |
| G-13 | major | T91 | **The key cannot support unambiguous precision/recall.** It lacks: acceptable alternative clause IDs; parent/child tolerance; a negative set (clauses that must *not* be flagged); cross-document propagation (register, calendar and retention rows); severity; doc-level `new_requirement_gap` anchors; dual annotation and adjudication; a scoring formula; and a corpus hash. |
| G-14 | major | People | Agents may invent named people (e.g., a Corporate Communications manager). Add a rule: **no new named individuals; use role titles**. Fictional phone numbers must use the 555-0100–0199 range. |
| G-15 | minor | T01–T03 | Applicability attributes are missing items T20/T21 need. T02 lacks on-call alternates. T03 lacks `render_path` and canonical supersedes. |

---

### §0.1 — replacement for the worker prompt and execution waves

```markdown
### 0.1 For the orchestrator

This file is designed so that **one agent executes one task**. Every task is self-contained *together with* Sections 0–3 (the global context, alignment protocol and output standard), which every agent must read first. Appendix O (orchestrator-only) is never given to worker agents.

**Prompt to give each worker agent** (replace `Txx`):

> You are generating one deliverable for a fictional Indiana electric utility. Read Sections 0, 1, 2 and 3 of `strata_synthetic_corpus_spec.md` in full, then read **Task Txx** in full. Execute only Task Txx. Do not read any other *task section* of the spec, Appendix O, or any file under `corpus/eval/` or `corpus/grounding/_orchestrator_report.json`.
> You may read: `corpus/_global/*`; your own grounding pack `corpus/grounding/Txx.json` (if your task has one); and the files listed under **Inputs** in your task. Do not read any other grounding pack.
> If your task has a grounding pack and it is missing or empty, stop and report that. Never substitute your own knowledge of the Indiana Administrative Code, any other edition of it, or any other state's rules.
> Write outputs exactly to the paths the task specifies. Before finishing, run the self-checks in §2.6 and §3.8 and write `corpus/qa/<DOC_ID>/selfcheck.json`. In your final message, report: outputs written, self-check results, `basis.gaps`, `basis.interpretations`, and any conflict between §1 and your pack.

**Execution waves** (tasks within a wave run in parallel):

| Wave | Tasks | Depends on | Exit gate |
|---|---|---|---|
| 0 | T00 | Strata database access | T00 leak test passes; orchestrator reviews Appendix O items and applies any §1.4 date adjustments |
| 1 | T01, T02, T03 | Sections 0–3 | Schema checks pass |
| 2 | T13–T21 | T00, Wave 1 | Per-document QA loop (§0.4) passes; then the **clause-ID freeze**: `corpus/qa/clause_id_freeze.json` lists every clause ID and its text hash for Wave 2 |
| 3a | T10 | Freeze | QA loop passes |
| 3b | T11, T12 | T10 | QA loop passes |
| 4 | T90 | Waves 2–3 | All checks pass, including the realism rubric |
| 5 | T91 | T90 passed; Snapshot-2 access | Isolated. Dual annotation and adjudication complete. **Its output is never shown to generator agents or to the Strata engine.** |

**After the freeze:** a fix to a Wave 2 document may change clause *text*, but it may not delete, renumber or reuse a frozen clause ID. A new clause gets a new ID (e.g. `7.2a`). If a fix must remove a clause, the orchestrator records the mapping in `clause_id_freeze.json` (`"retired": {"old": "...", "replaced_by": "..."}`) and re-runs the QA loop for T10–T12.

**Information barriers:** the Strata engine sees only `corpus/docs/**` (documents and datasets, **not** basis files), `corpus/_global/**` and its own knowledge layer. It never sees grounding packs, basis files, `corpus/qa/**`, Appendix O or `corpus/eval/**`.
```

### §0.4 — new: orchestrator QA loop

```markdown
### 0.4 Per-document QA loop (Waves 2–3)

For each document, the orchestrator runs this loop. It stops at **PASS** or after 3 iterations; on a third failure it escalates to a human.

1. **Generate.** The worker agent produces the outputs, `basis.json` and `corpus/qa/<DOC_ID>/selfcheck.json`.
2. **Deterministic validation** (`corpus/qa/validate.py`, written once by the orchestrator, no LLM):
   - front matter and basis schema
   - clause-ID grammar, uniqueness and boundaries (§3.2)
   - `s1_quote` substring check and subsection placement
   - value check with numeral normalization (§3.4)
   - value ledger: every number in the body is ledgered (§2.6.6)
   - phantom-citation scan: every citation string in the body appears in the basis file with a matching clause
   - banned-phrase scan (§3.6 R5)
   - length and density metrics (§3.8 part A)
   - §1 constants verbatim
   - render exists and passes text parity
   - dates (no date after approval; revision history ordered and earlier than approval)
   - Output: `corpus/qa/<DOC_ID>/validate.json`.
3. **Independent fidelity review.** A fresh agent receives the document and the pack only (not the basis file and not this spec's task text). It lists every clause that conflicts with, omits a condition of, or overstates the pack, quoting both texts. Target: zero issues. Output: `review_fidelity.md`.
4. **Independent realism review.** A fresh agent receives the document, the task section, §3.6 and the exemplar anatomy checklist for the document class (§3.8 part C). It scores §3.8 part B and runs the exemplar comparison and the auditor-question test. Output: `review_realism.json`.
5. **Fix.** The original worker (or a fixer agent with the same read permissions) receives the three reports. It may change only the flagged clauses and anything needed to stay consistent. It must preserve clause IDs (post-freeze rules apply in Wave 3), and it logs each change in `corpus/qa/<DOC_ID>/fixlog.md` (clause ID, issue, change).
6. **Re-run steps 2–4** on the changed document.
7. **PASS** = validate.json has zero errors, review_fidelity has zero issues, and review_realism meets §3.8 thresholds. The orchestrator records the pass with a timestamp and the document's SHA-256.

Reviewers in steps 3–4 never see each other's output or earlier iterations' reviews, so they don't anchor on them.
```

### §1.2 — replacement (generator-facing; S2 rows moved to Appendix O)

```markdown
### 1.2 Timeline and the "law as-of" rule

| Date | Meaning |
|---|---|
| **2024-12-31** | **Law as-of date for every document.** Every regulatory statement reflects the Indiana Administrative Code as it stood on this date, exactly as provided in your grounding pack. |
| 2025-01-03 → 2025-03-21 | Window in which every v1 document was last approved (exact dates in §1.4). Exception: the tariff (T13), whose current sheets were approved by the IURC on 2024-05-15. |

**Rule:** Every document reads as if RPL staff wrote it in early 2025. No document may anticipate, mention or hedge about rule changes, rulemakings or later editions. If you recall any version of an Indiana rule other than the text in your pack, ignore it: the pack is the law for this corpus.
```

### §1.4 — amendments

```markdown
Replace the T11 row with:

| T11 | RPL-REG-CAL-2025 | Regulatory Reporting Calendar 2025 | 1.2 | 2025-03-17 | 2025-03-14 | P09 | P08 | P07 | Annual (rolled each January); revised when a source procedure changes |

Add a `Supersedes` column. Values for Group C documents:
T10 "3.3 (2024-12-16)" · T11 "1.1 (2025-02-24)" · T12 "7.1 (2023-03-20)" · T20 "3.0 (2024-03-11)" · T21 "1.2 (2023-10-02)".
(Group A supplies T13–T15 and T17; Group B supplies T16, T18 and T19.)

Delete the trailing paragraph beginning "If T00 reports …" and move it to Appendix O, item O-3.
```

### §1.6 — additions (extend Group A's §1.6 with these tables)

```markdown
**Table S — EHS operational data (non-regulatory; company facts)**

- **On-call Environmental Specialist rotation:** weekly, Monday 08:00 handover; pool: Hannah Brooks (P26) plus two Environmental Specialists (role titles only, not named) based in Lafayette and Terre Haute; backup is Daniel Foster (P25). The DCC pages on-call via the OMS paging group `ENV-ONCALL`.
- **Spill kits:** every line and substation truck carries a 20-gal kit (absorbent pads, socks, drain cover, nitrile gloves, disposal bags). Each service center keeps a 95-gal overpack kit and 100 ft of boom. Lafayette HQ keeps the trailer `SK-T1` (boom, 2 drain plugs, 55-gal drums, sorbent bulk). Kit inspection is monthly, recorded in WAM (work type `ENV-INSP`).
- **Contractors and vendors (generic names only):** Contractor E (24/7 emergency response and remediation; contract `RPL-C-2023-118`); Laboratory L (accredited analytical laboratory); Disposal Facility D (licensed non-hazardous oily waste and soil); Hauler H (licensed waste transporter).
- **WAM PCB status codes** (definitions live in RPL-ENV-PRO-006; no concentrations are stated in other documents): `NP-T` non-PCB (tested) · `NP-M` non-PCB (manufacturer certified) · `UNK` untested / assume PCB · `PCB-C` PCB-contaminated · `PCB` PCB equipment. Label colours: blue = non-PCB; yellow = PCB; no label = treat as `UNK`.
- **Typical nameplate oil volumes (RPL asset data, fictional):** pole-mount 10–50 kVA: 8–25 gal · pole-mount 75–167 kVA: 25–55 gal · padmount 1-phase 25–167 kVA: 20–60 gal · padmount 3-phase 75–2,500 kVA: 60–650 gal · substation power transformer: 1,800–12,000 gal · voltage regulator (substation): 60–250 gal · standby generator belly tank: HQ 1,500 gal, Crawfordsville 660 gal, Terre Haute 660 gal.
- **GIS screening layers:** `ENV_WellheadProtection`, `ENV_PrivateWellBuffer` (from county records), `ENV_SensitiveWaters`, `ENV_StormInlets` (municipal data where available), `ENV_Parcels`.
- **Fleet:** about 640 vehicles, including 210 aerial/bucket and digger-derrick units; fueling at all five service centers (aboveground tanks covered by RPL-ENV-PLN-011).
- **SPCC coverage:** 41 substations with SPCC plans under RPL-ENV-PLN-010; service centers under RPL-ENV-PLN-011.

**Table S-INC — Incident categories and severity tiers (company practice)**

Categories: `INJ-EMP` employee injury · `INJ-CON` contractor injury · `PUB-CON` public contact with RPL facilities · `PUB-INJ` public injury, other · `VEH` vehicle incident · `PROP` property damage (RPL or third party) · `EC` energized contact or flash (no injury) · `DIG` dig-in / damage to RPL underground facilities · `NM` near miss · `FIRE` equipment fire.

Tiers: **Tier 1** fatality or life-altering injury, or serious public contact · **Tier 2** lost-time or hospitalization, energized contact with injury, property damage over $250,000 (company threshold) · **Tier 3** recordable injury, vehicle incident with injury, property damage $10,000–$250,000 · **Tier 4** first aid, near miss, minor property damage. (Company tiers. They are not regulatory reporting thresholds.)

**Table R — Records series catalog (IDs and titles; T12 assigns retention)**

| Series ID | Title | Primary documents |
|---|---|---|
| RRS-CS-001 | Customer account and billing records | T13, T14, T15 |
| RRS-CS-004 | Disconnection notices, door tags and field orders | T14 |
| RRS-CS-005 | Medical certificates and energy-assistance protection records | T14 |
| RRS-CS-007 | Billing adjustment records | T15 |
| RRS-CS-011 | Customer complaint and dispute files (incl. IURC CAD referrals) | T17 |
| RRS-MTR-001 | Meter history records (purchase, installation, test, retirement) | T18, T15 |
| RRS-MTR-002 | Meter test reports (in-service, acceptance, customer-requested) | T18, T15 |
| RRS-MTR-003 | Standards certification and calibration records | T18 |
| RRS-DO-002 | Vegetation work notices, consent and easement documentation | T16 |
| RRS-DO-003 | Vegetation dispute logs | T16 |
| RRS-DO-004 | Tree-related outage report filings | T16 |
| RRS-DCC-001 | Service interruption records and IURC interruption reports | T19 |
| RRS-DCC-002 | Reliability index workpapers | T19 |
| RRS-ENV-001 | Spill reports, notification logs and IDEM correspondence | T20 |
| RRS-ENV-002 | Spill cleanup, sampling and waste disposal records | T20 |
| RRS-ENV-003 | Spill kit inspection records | T20 |
| RRS-SAF-001 | Incident reports and investigation files | T21 |
| RRS-SAF-002 | IURC accident notification logs and written reports | T21 |
| RRS-SAF-003 | CAPA records | T21 |
| RRS-REG-001 | Regulatory filings and correspondence (IURC, IDEM) | T11, T13 |
| RRS-REG-002 | Tariff sheets and filing history | T13 |
| RRS-CMP-001 | Obligations register versions and review evidence | T10 |
| RRS-LEG-001 | Legal hold notices and acknowledgments | T12 |
| RRS-LEG-002 | Certificates of destruction | T12 |
| RRS-LEG-003 | Records-location notices to the commission | T12 |
| RRS-TRN-001 | Training completion records | all |
| RRS-DOC-001 | Controlled document masters and revision history | all |

**Table D — Referenced RPL documents that are not generated (cite by ID and title only; never describe their contents beyond the title)**

RPL-ENV-PLN-010 SPCC Plan — Distribution Substations · RPL-ENV-PLN-011 SPCC Plan — Service Centers & Fleet Fueling · RPL-ENV-PRO-006 PCB Management Procedure · RPL-ENV-PRO-007 Waste Management & Disposal Procedure · RPL-ENV-PRO-008 Federal Release Notification Protocol · RPL-SAF-PRO-002 Electrical Safety Rulebook · RPL-SAF-PRO-010 OSHA/IOSHA Recordkeeping & Reporting Procedure · RPL-HR-PRO-015 Drug & Alcohol Testing Procedure (incl. DOT post-accident) · RPL-DO-PRO-020 Damage Prevention & Indiana 811 Procedure · RPL-CLM-PRO-001 Third-Party Claims Procedure · RPL-EMR-PLN-001 Emergency Response & Storm Restoration Plan · RPL-COM-PRO-002 Media & Public Communications Procedure · RPL-LEG-POL-001 Records & Information Management Policy · RPL-LEG-PRO-003 Legal Hold Procedure · RPL-CMP-POL-001 Compliance Program Charter.
Training codes: ENV-T-01 Spill Response (annual) · SAF-T-05 Incident Reporting (annual) · SAF-T-06 Incident Investigation for Supervisors · REG-T-02 Regulatory Calendar Users · LEG-T-01 Records Management (annual).
Forms: EHS-F-101 Incident Report · EHS-F-102 IURC Accident Notification Log & Written Report · EHS-F-201 Spill Report · LEG-F-021 Certificate of Destruction · LEG-F-022 Retention Schedule Change Request.
ID formats: `INC-2025-nnnnn` (EHS-IMS incidents) · `SPL-2025-nnnn` (spills) · `CAPA-2025-nnnn` · `OBL-nnnn` · `CTL-<dept>-nnn` · `CAL-2025-nnn`.

**Table X — External EHS and regulatory contacts (public facts; the orchestrator verifies against an archived early-2025 copy of each page before Wave 2 and records the URL in `corpus/_global/contacts_sources.md`)**
- IDEM Emergency Response (24-hour spill line): (888) 233-7745 · (317) 233-7745 — https://www.in.gov/idem/cleanups/investigation-and-cleanup-programs/emergency-response/
- National Response Center: (800) 424-8802 (listed on IDEM's quick-reference sheet) — referenced only via RPL-ENV-PRO-008
- U.S. EPA Region 5 (as listed on IDEM's quick-reference sheet; orchestrator to confirm current number)
- IURC Energy Division: (317) 232-2785 — https://www.in.gov/iurc/energy-division/electricity-industry/annual-report-filing-electricity/ ; IURC filings via the IURC Electronic Filing System (iurc.portal.in.gov)
- IURC office hours for operational "business hours" (orchestrator to confirm from the IURC contact page and enter here); State of Indiana holidays for 2025 (orchestrator to list)
- Emergency services: 911

**Rules for all §1.6 data:** use it verbatim. If a pack sets, caps or prohibits any item, the pack governs; report the conflict. **Do not create new named individuals.** Use role titles for anyone not in §1.3. Fictional phone numbers use the 555-0100 to 555-0199 range (e.g. 765-555-0123).
```

### §2.1 — additions (merge with Group A G4 and G9)

```markdown
- **Contamination.** Study references and web pages contain values from other states, federal law or later Indiana editions. Treat every number in them as contaminated. If a value in your draft matches something you read outside the pack and you cannot find it in the pack, delete it.
- **Research permissions.** Web research is allowed only for (a) document form and layout, (b) real public regulator contact details and program names, and (c) typical ranges for company-chosen operational values that §1.6 does not fix. Use official or primary sources only (regulator .gov sites, utilities' own published documents, standards bodies). Log every URL opened in `basis.form_sources` as `{"url", "accessed", "used_for"}`. Research is **never** a source for a regulatory value, citation or wording.
```

### §2.4 — replacement (coverage parity and dispositions)

```markdown
### 2.4 Coverage rules

Every active section in your pack receives exactly one **disposition** in the basis file:
- `covered`: cited by exact citation in at least one clause.
- `not_applicable`: the section does not apply to RPL (§2.3.7), with the reason and the T01 attribute.
- `considered_no_obligation`: the section applies to RPL but creates nothing this document type must implement (e.g., a complaint-handling rule in the reporting calendar). Give a one-line reason.

**Parameter parity.** For every `covered` section, restate **every** material parameter (§2.2) that bears on this document's process, in body text, a table or a template. This applies equally to every covered section. Sections flagged `coverage_priority: "high"` must be `covered` (never `considered_no_obligation`) and must restate **all** their material parameters. Do not write high-priority sections at greater length or with more emphasis than comparable standard sections. Never mention the flag.
```

### §2.6 — additions

```markdown
6. **Value ledger** (Group A G3). Every numeral, spelled-out number, percentage, time, date and dollar amount in the body is in `basis.value_ledger` with its source.
7. **No phantom citations.** Every citation string in the body appears in a basis clause whose `citations` include it, and every `regulatory_restatement` clause cites something.
8. **Subsection placement.** Each `s1_quote` lies inside the span of the subsection the clause cites (use the pack's `subsections`).
9. **Company positions.** Every `Company position:` sentence is listed in `basis.interpretations` and carries no citation.
10. **Contamination.** No value in the document comes from a study reference or memory (re-read §2.1).
```

### §2.8 — new: company positions (interpretations)

```markdown
### 2.8 Company positions on how a rule applies to RPL

Some rules depend on classifications they do not make for utility assets (e.g., whether a pole-mount transformer is a "facility", where a "facility boundary" is, whether a fluid falls within a defined substance category, what "business hours" means in practice). When applying a pack provision requires such a classification:
1. If the pack's text decides it, cite the text.
2. If not, write one sentence beginning `Company position:` with **no citation**. Choose the reading that makes the obligation apply more broadly (more releases reportable, more notices given, records kept longer). Never contradict pack text.
3. Record it in `basis.interpretations`: `{"clause_id", "question", "position", "pack_citations_considered", "rationale"}`.

Company positions are assessed for conflict with the pack (T90 check 5) but are never restated as regulatory requirements.
```

### §3.2 — replacement (clause-ID grammar and boundaries)

```markdown
### 3.2 Clause identifiers

**Grammar.** `CLAUSE_ID := <DOC_ID> ":" LOCAL`, where LOCAL is one of:
- section clause: `\d+(\.\d+){0,3}[a-z]?` (e.g., `7.2`, `7.2.3`, `7.2a` for post-freeze insertions)
- appendix clause: `App-[A-Z](\.\d+){0,2}`; form field: `App-[A-Z]\.F\d+` (e.g., `App-A.F12`)
- table row: `T<section>-<n>` (e.g., `T7-4`), always prefixed with the doc ID in the basis file and in the HTML comment
- tariff sub-rule: `S<sheet>.R<rule>.<n>` (T13)
- dataset or register row: `<row key>` (e.g., `OBL-0042`, `CAL-2025-007`, `RRS-ENV-001`)

**Markers.**
- Markdown: an HTML comment on the line immediately before the clause, `<!-- clause: RPL-ENV-PRO-005:7.2 -->`.
- Table rows: the first column `ID` holds the LOCAL part, and a comment before the table lists `<!-- table: RPL-ENV-PRO-005:T7 -->`.
- CSV: the `clause_id` column.

**Boundaries.** A clause's text runs from its marker to the next marker of any level, not inclusive. A parent clause (`7.2`) therefore holds only its lead-in text, and its children are separate clauses. Every regulatory value sits in exactly one clause.

**Stability.** IDs are never reused or renumbered after the Wave 2 freeze (§0.1). IDs never appear in rendered output.
```

### §3.4 — replacement basis schema (v2)

```json
{
  "schema_version": "2.0",
  "doc_id": "RPL-ENV-PRO-005",
  "version": "3.1",
  "law_as_of": "2024-12-31",
  "grounding_pack": "corpus/grounding/T20.json",
  "doc_sha256": "<hash of the .md>",
  "default_route": {"owner": "P26", "reviewer": "P25", "approver": "P24"},
  "clauses": [
    {
      "clause_id": "RPL-ENV-PRO-005:8.3",
      "clause_type": "regulatory_restatement",
      "text_sha256": "<hash of clause text per §3.2 boundaries>",
      "line_start": 412,
      "citations": ["<citation at most specific level>"],
      "subsection_labels": ["(a)"],
      "assessed": true,
      "route_override": null,
      "depends_on": ["RPL-ENV-PRO-005:App-A.F7"],
      "cross_doc_refs": ["RPL-REG-CAL-2025:CAL-2025-031"],
      "parameters": [
        {
          "parameter_id": "RPL-ENV-PRO-005:8.3#p1",
          "kind": "number|period|qualifier|condition|party|channel|content_element|exception|applicability|threshold",
          "name": "<plain name>",
          "doc_value": "<exactly as written in the clause>",
          "unit": "<as written>",
          "qualifier": "<e.g., 'within', 'at least'>",
          "day_type": "calendar|business|working|hours|n/a",
          "s1_quote": "<exact substring of body_text_s1, ≤60 words>",
          "s1_span": [1234, 1302],
          "derived": null
        }
      ]
    }
  ],
  "coverage": [
    {"citation": "<section>", "disposition": "covered|not_applicable|considered_no_obligation", "coverage_priority": "high|standard", "clause_ids": ["..."], "reason": null}
  ],
  "interpretations": [
    {"clause_id": "RPL-ENV-PRO-005:T7-1", "question": "...", "position": "...", "pack_citations_considered": ["..."], "rationale": "..."}
  ],
  "out_of_scope_references": [
    {"clause_id": "<id>", "reference": "<name of statute/CFR part>", "note": "Outside the v1 knowledge layer; not assessed"}
  ],
  "value_ledger": [
    {"clause_id": "<id>", "text": "<value>", "source": "pack|section1|section1.6|company_practice|worked_example|dataset", "ref": "<citation, table ref or note>"}
  ],
  "gaps": [],
  "form_sources": [{"url": "...", "accessed": "2026-10-06", "used_for": "..."}]
}
```

Rules for the schema:
- `derived` is used when the document value is computed from a pack value (e.g., a 2025 due date): `{"from_parameter": "<parameter_id>", "method": "<computation>"}`.
- **Numeral normalization for the value check:** spelled-out numbers become digits, "ten (10)" collapses to 10, and unit synonyms (`hrs`/`hours`) are canonicalized.
- `route_override` routes a clause to someone other than the document's default (e.g., a customer letter template routed to P03).
- `cross_doc_refs` lists clauses in other documents that restate or depend on this clause, so a single change is routed to all of them.

### §3.6 — replacement: Document Realism Standard (DRS)

```markdown
### 3.6 Document Realism Standard

Every deliverable must be something an experienced utility practitioner, an IURC or IDEM staff member, or an internal auditor would accept as a real RPL document. That means the right layout, sections, depth, data, forms, tone and length. A summary of the law is a failure.

**R1 — Reader and voice.** Write for the person who does the work at 02:00 with the document open. Use precise, procedural, slightly formal, imperative steps ("The DCC shift supervisor pages ENV-ONCALL."). Use present tense and active voice, and give an actor in every instruction. No marketing tone, rhetorical summaries or "this document aims to".

**R2 — Anti-summary rule (the operational triad).** Every regulatory statement is followed, in the same or the next clause, by the operational step that implements it. The step names:
(a) **who** (role or §1.3 person);
(b) **when** (clock start and limit, or schedule);
(c) **how** (system, channel, form, queue, code);
(d) **what record** results (record series ID).
A clause that restates a rule with no triad fails. At least 90% of numbered procedure steps must contain all four elements.

**R3 — Minimum artifacts by document class.**

| Class | Tasks | Minimum artifacts |
|---|---|---|
| Procedure | T14, T15, T17, T19, T20, T21 | Document-control block; TOC; RACI or roles table; ≥ 1 decision table; ≥ 1 flowchart (Mermaid); ≥ 2 forms or templates with numbered fields; ≥ 1 checklist; ≥ 1 contact sheet; ≥ 2 worked examples where the task involves thresholds or calculations; ≥ 3 "Note:" or "Caution:" callouts; records table with series IDs; training table; revision history (dates, version, author, change summary); approval block with signature lines and dates; distribution list |
| Plan or program | T16, T18 | All Procedure artifacts except the contact sheet. Also: an executive summary with numbers; ≥ 3 data tables computed from datasets; ≥ 1 chart; a budget or resource table where relevant |
| Tariff | T13 | Per T13: sheet headers, sheet index, cancels/supersedes lines, inline citations |
| Controlled list | T10, T11, T12 | Cover memo with methodology and statistics; the list as CSV plus a rendered workbook; lookups/enumerations sheet; change log from the prior version; approval or attestation |
| Infrastructure | T01–T03 | Per task |

**R4 — Required specificity.** Every timeframe is a number with a unit and a day type. Every actor is a role or §1.3 person. Every system is a §1.1 system. Every form has an ID from §1.5/§1.6. Every record has a §1.6 Table R series ID. Every cross-reference names a document ID and clause or section. Specificity density: ≥ 12 specific tokens (numbers, IDs, systems, roles, forms, codes) per 250 words of body.

**R5 — Banned phrasings** (zero tolerance; case-insensitive):
- "this document aims", "this procedure aims", "in a timely manner", "as soon as possible" (unless quoting the pack), "promptly" or "immediately" without a stated limit (unless quoting the pack)
- "appropriate action", "appropriate personnel", "relevant stakeholders", "as needed", "as necessary", "where applicable" without the condition
- "applicable regulations", "as required by law", "in accordance with regulations" without a citation
- "etc.", "and so on", "various", "best practices", "robust", "leverage", "ensure compliance" as a step
- "[TBD]", "[Insert", "XXX", "lorem", "TBD", "N/A" in a required field without a reason
- any mention of Strata, snapshots, synthetic data, AI, models, test scenarios, future or upcoming changes, pending rulemakings

**R6 — Document furniture.**
- Front matter per §3.1.
- Printed control block: title, doc ID, version, effective date, owner/reviewer/approver with titles, classification, "Uncontrolled when printed — verify the current version in DCS".
- Running header (company · doc ID · title) and footer (version · effective · page X of Y) in the rendering.
- Revision history as a table with 2–4 prior versions dated before approval, each with a concrete non-future reason (reorganization, system change, audit finding, title change, form revision).
- Approval block with name, title, signature line and date.

**R7 — Forms standard.**
- Form ID and revision ("EHS-F-201 (Rev. 03/2025)").
- Parts lettered A, B, C…; fields numbered, with field type shown (checkbox ☐, date `YYYY-MM-DD`, time `hh:mm`, text).
- Every pack-required content element is its own field.
- An "Office use only" block and a signature/date block.
- Fillable in the rendering.

**R8 — Rendering** (§3.7). Markdown and CSV are canonical and carry the clause IDs. The rendering is what a user would open.

**R9 — Length and density.**
- Body word counts are measured excluding front matter, HTML comments and CSV.
- Hitting the minimum with padding fails R2 and R4. When short, add procedural depth (steps, edge cases, decision rows, examples), never prose.

**R10 — Definition of Done (per document).** The document is done only when every item below is true:
1. All task outputs exist at the specified paths, including renderings.
2. The required structure is present in order, and every required appendix exists.
3. `validate.py` reports zero errors (schema, IDs, quotes, values, ledger, phantom citations, banned phrases, constants, dates, render parity).
4. The fidelity review reports zero issues.
5. The realism review meets the §3.8 thresholds, including the exemplar comparison and the auditor-question test.
6. Every §2.4 disposition is recorded. `gaps` and `interpretations` are reported in the final message.
7. No clause ID changed after the freeze, or the mapping is recorded.
```

### §3.7 — rendering (merge with Group A G5; Group C additions)

```markdown
Additions to §3.7:
- **Skills by deliverable:**
  - procedures, plans and memos: `docx` → PDF
  - tariff: `pdf` (reportlab)
  - fillable forms (EHS-F-101/102/201, CS-, MTR- forms where the task requires them) and pocket cards: `pdf` with AcroForm fields named by field clause ID
  - registers, calendars, schedules and dataset companions: `xlsx` (frozen headers, autofilter, data validation from enumerations, a Lookups sheet, a Change Log sheet)
  - charts in plans and appendices: `dataviz`, rendered to PNG for docx
  - `pptx` is optional and used only for a training module named in a task
  - `frontend-design` is used only for the T90 dashboard (optional)
- **Render script:** each task writes `scripts/render_<DOC_ID>.py`. Rendering is deterministic from the canonical files.
- **Parity:** T90 re-extracts text from each rendering and confirms every canonical sentence and every CSV row is present (normalized whitespace and punctuation).
```

### §3.8 — Realism & Depth Rubric (supersedes Group A's §3.8 list; keeps all of its items)

```markdown
### 3.8 Realism & depth rubric

**Part A — Deterministic gates (all must pass; computed by `validate.py`)**

| Gate | Pass condition |
|---|---|
| A1 Length | Body words within the task range |
| A2 Structure | Every required section and appendix present in order; each required section ≥ 2 clauses (≥ 4 for sections the task marks in bold) |
| A3 Clause density | ≥ 1 clause ID per 120 body words; 100% of numbered clauses have IDs |
| A4 Artifacts | §3.6 R3 minimums met (tables, forms, flowchart, checklists, examples, callouts) |
| A5 Triad ratio | ≥ 90% of numbered procedure steps contain actor + timeframe + system/channel/form + record (heuristic tagger; flagged steps go to the realism reviewer) |
| A6 Specificity | ≥ 12 specific tokens per 250 words (§3.6 R4) |
| A7 Banned phrases | 0 hits (§3.6 R5) |
| A8 Constants | 100% of §1 and §1.6 constants verbatim; no unknown person names (NER against §1.3 and role list) |
| A9 Ledger and citations | Value ledger complete; zero phantom citations; zero subsection misplacements |
| A10 Sentence shape | Median sentence 12–28 words; ≤ 10% of paragraphs over 120 words outside definitions |
| A11 Render | Rendering exists, opens, is within the task page range, and parity is 100% |

**Part B — Scored criteria (independent realism reviewer; each 0–3)**

| # | Criterion | 3 = | 1 = |
|---|---|---|---|
| B1 | Exemplar structural fidelity | ≥ 90% of exemplar anatomy elements present (Part C) | < 70% |
| B2 | Operational depth | A trained new hire could perform every step without asking; edge cases handled | Steps are headings with prose |
| B3 | Decision support | Decision tables are complete, mutually exclusive, and usable under time pressure | Tables restate rules without decisions |
| B4 | Forms and templates | Real-form quality: parts, numbered typed fields, every required element, signature/office-use blocks | Field lists without structure |
| B5 | Invented data plausibility | Numbers, counts, budgets, volumes and timings fit §1/§1.6 and utility norms, are internally consistent and bounded | Implausible or inconsistent |
| B6 | Cross-document coherence | Correct references to sibling docs, forms, series, codes and roles | Broken or generic references |
| B7 | Voice and tone | Indistinguishable from a practitioner-written controlled document | Reads as explanatory or AI prose |
| B8 | Regulatory texture | Fine print, exceptions and conditions present and operationalized; company practice clearly labeled | Rules summarized; practice and law blurred |
| B9 | Records and evidence | Every obligation leaves a named record in a named system and series | Records generic |
| B10 | Visual realism (rendered) | Looks like a controlled utility document (layout, headers, tables, forms) | Plain text dump |

**Pass threshold:** total ≥ 24/30, **and** B2, B3, B8 ≥ 2, **and** no criterion is 0.

**Part C — Comparison to real exemplar**

For each document class the orchestrator keeps `corpus/qa/exemplar_anatomy/<class>.yaml`: the ordered elements observed in real exemplars, from the audit reports' (a) sections. The reviewer:
1. Marks each element present / absent / not applicable with the clause ID. B1 is scored from this.
2. **Swap test:** given the exemplar's table of contents (headings only), list every element the exemplar has that the RPL document lacks. Each must be added or justified in `review_realism.json`.
3. **Auditor-question test:** write 10 questions an IURC or IDEM staff member or internal auditor would ask of this document type (e.g., "Who calls IDEM at 02:00 and how do they know the release is reportable?"). The document must answer ≥ 9 with a clause ID. Unanswered questions become fix items.
4. **Discrimination test (optional, recommended for T13, T14, T20):** a blind judge receives one RPL section and one structurally similar real section (real names redacted, values masked) and guesses which is real. Record the result. Three successive confident "RPL is synthetic" verdicts trigger a revision.
```

### Appendix O — new (orchestrator only; never given to workers)

```markdown
## Appendix O — Orchestrator-only information

O-1. **Snapshot dates.** IAC Snapshot 1 = 2024-12-31; IAC Snapshot 2 = 2025-12-31 (2026 edition); eCFR Snapshot 1 = 2025-01-02; eCFR Snapshot 2 = 2026-10-02. No v1 document is assessed against federal text.
O-2. **Decoy and change information** lives only in `corpus/grounding/_orchestrator_report.json`.
O-3. **Approval-date adjustment.** If the orchestrator report shows a Snapshot-2 change to any section in a document's pack scope (including a new S2 section in scope) with an S2 effective date on or before that document's §1.4 approval date, move the document's approval and effective dates to the latest working day before the S2 effective date, no earlier than 2025-01-03, and update §1.4 before Wave 2. If that is impossible (the S2 effective date is on or before 2025-01-03), keep the dates and record the document as `lagging_at_approval` for T91, which classifies the resulting finding as `stale_at_approval`.
O-4. **Information barriers** per §0.1.
O-5. **Exemplar anatomy files** under `corpus/qa/exemplar_anatomy/` are built from the audit reports' (a) sections before Wave 2.
```

---

### T00 — replacement text

```markdown
## T00 — Snapshot-1 grounding packs

**Type:** Data export (read access to the Strata PostgreSQL database). **Orchestrator-supervised.**
**Outputs:** `corpus/grounding/T10.json` … `T21.json`, `corpus/grounding/_orchestrator_report.json`, `corpus/grounding/_normalizer.py`, `corpus/grounding/_scope.py`, `corpus/grounding/_leaktest.py`, `corpus/grounding/_leaktest_report.json`

### Purpose

Give each document agent exactly the Snapshot-1 law it must align to, structured to subsection level, plus a neutral flag marking sections that must be covered — without revealing any Snapshot-2 content.

### Steps

1. **Confirm snapshot dates and granularity.**
   ```sql
   SELECT snapshot_date, count(*) FROM code_sections
   WHERE source_system = 'iac' GROUP BY 1 ORDER BY 1;
   ```
   Expect 2024-12-31 and 2025-12-31; stop and report if different.
   - Confirm that rows are **sections** (not rules or subsections). Record the distinct `status` values and map them to the enum `active | repealed | expired | transferred | reserved`. Stop and report any unmapped value.

2. **Scope parser (`_scope.py`).** Parse every citation into `(title, article, rule, section)`, with the section held as a Decimal (`16.5`).
   - A scope entry is either `rule:<title> IAC <article>-<rule>` (the whole rule), `section:<cite>` (one section, with an explicit list of decimals to include), or `range:<cite_from>..<cite_to>` (numeric, inclusive, decimals between bounds included).
   - Never use SQL `LIKE` or string comparison on citations.
   - Apply the same parser to Snapshot-2 rows to find S2 sections new to each scope.

   | Pack | Scope |
   |---|---|
   | T13 | rule:170 IAC 4-1; rule:170 IAC 16-1; 170 IAC 1 sections whose heading matches `tariff|schedule|thirty|30-day|rate|time|computation|filing` |
   | T14 | section:170 IAC 4-1-13; 4-1-15; 4-1-16 (+16.5, 16.6); rule:170 IAC 16-1 |
   | T15 | range:170 IAC 4-1-4..170 IAC 4-1-14 |
   | T16 | rule:170 IAC 4-9; rule:170 IAC 16-1; section:170 IAC 4-1-26 |
   | T17 | rule:170 IAC 16-1; section:170 IAC 4-1-13; 4-1-16 (+16.5, 16.6) |
   | T18 | range:170 IAC 4-1-3..170 IAC 4-1-11 |
   | T19 | section:170 IAC 4-1-3; 4-1-23; 4-1-24; 170 IAC 4-9-7 |
   | T20 | rule:327 IAC 2-6.1 |
   | T21 | section:170 IAC 4-1-3; 4-1-24 |
   | T10, T11 | union of T13–T21 |
   | T12 | union of T13–T21 |

   **Context sections.** Add `170 IAC 4-1-0.5`, `4-1-1` and `4-1-2` to every pack that has any 170 IAC 4-1 section, and the definitions/applicability sections of every other rule in scope. Mark them `role: "context"`. They receive dispositions like any other section.

3. **Normalizer (`_normalizer.py`).** Inspect at least 30 sections across Titles 170 and 327, including at least 10 that were readopted between the snapshots. Strip:
   - the trailing history parenthetical
   - `Authority:` and `Affected:` lines
   - DIN strings, Indiana Register citations, "Filed" and "Readopted" stamps
   - the leading `Sec. n.` label
   - typographic variants (curly quotes, en/em dashes, non-breaking spaces, `§`)
   - whitespace and punctuation-only differences
   Keep the raw text.
   - Unit tests in the file: ≥ 10 known readoption-only pairs must normalize equal, and ≥ 5 pairs with one-word substantive edits must differ.
   - Emit, for each changed pair, a word-level diff and a classification hint (`numeric`, `qualifier`, `list_item_added/removed`, `cross_ref_only`, `heading_only`, `status_only`, `other`) **into the orchestrator report only**.

4. **Subsection spans.** For each S1 body, compute `subsections: [{"label": "(b)(2)", "start": int, "end": int}]` by parsing `(a)`, `(1)`, `(A)`, `(i)` markers in order. Record parse confidence; flag low-confidence sections in the orchestrator report.

5. **External references.** Extract IC, CFR and U.S.C. references and incorporated standards (e.g., ANSI, IEEE) from each S1 body into `external_refs_s1` (strings only). Agents handle them under §2.7.

6. **Compute change status (orchestrator report only).** For each S1 row:
   - **changed:** an S2 row with `prior_version_id` = this row's id exists and its normalized body, status or heading differs.
   - **repealed_in_s2:** the S2 status is repealed or expired.
   - **renumbered:** there is no `prior_version_id` successor, but an S2 row in any scope has normalized-text Jaccard ≥ 0.8 (5-gram shingles). Record both citations.
   - **new_in_scope (S2 only):** S2 sections inside a pack's scope with no S1 predecessor. Count and cite them in the orchestrator report; they never enter packs.

7. **Coverage flag (global, per citation).** Let C = the set of genuinely changed, repealed or renumbered S1 citations across all scopes. Sample decoys D from unchanged active non-context citations across all scopes, with |D| = max(|C|, 2 × number of packs with |C ∩ scope| = 0) and fixed seed 20250101. Within each pack, also ensure ≥ 2 high citations where the scope has ≥ 2 eligible citations, topping up from that pack's unchanged citations into D. A citation's flag is the **same in every pack** that contains it. `high` = C ∪ D.

8. **Write each pack:**
   ```json
   {
     "task": "T20",
     "law_as_of": "2024-12-31",
     "sections": [
       {
         "citation": "327 IAC 2-6.1-7",
         "heading": "<S1 heading>",
         "role": "scope|context",
         "status_s1": "active",
         "effective_date_s1": "<date or null>",
         "body_text_s1": "<raw S1 body>",
         "body_text_s1_normalized": "<normalized>",
         "subsections": [{"label": "(a)", "start": 0, "end": 412}],
         "iac_cross_refs_s1": ["..."],
         "external_refs_s1": ["IC 13-...", "40 CFR ..."],
         "coverage_priority": "high|standard"
       }
     ],
     "must_cover": ["<all active citations in the pack, scope and context>"]
   }
   ```
   **Never include** S2 text, S2 dates, S2 citations, rulemaking information, change hints or decoy membership. Sort sections by parsed citation, so the order carries no signal.

9. **Leak test (`_leaktest.py`), which must pass before Wave 1:**
   (a) No pack contains any S2-only 6-word shingle (shingles present in an S2 body but absent from the matching S1 body).
   (b) No pack contains any citation that exists only in S2.
   (c) No pack field other than those listed in step 8 exists.
   (d) The flag rate among changed vs. decoy citations is reported, and per-pack high counts are ≥ 2 where possible.
   Write `_leaktest_report.json`.

10. **Orchestrator report (`_orchestrator_report.json`)**, per task:
    - counts: in scope, context, active, high (real + decoy)
    - changed citations with diff classification and S2 effective date
    - repealed, renumbered and new-in-scope citations
    - decoys
    - **documents whose approval date is on or after an S2 effective date in their scope** (feeds Appendix O-3)
    - tasks with zero genuine changes ("cleared" documents), stated prominently
```

### T01 — additions

```markdown
Add to `applicability_attributes`:
  has_fleet_vehicles: true
  fleet_vehicle_count: 640
  has_aboveground_fuel_storage: true
  has_spcc_plans: true
  pcb_equipment_possible: true          # legacy equipment status tracked in WAM
  state_osha_plan: IOSHA
  owns_customer_meters: true
  meters_in_service_total: 409950
  has_vegetation_management_program: true

The fact sheet is rendered to a 2-page PDF via the `docx` skill (company letterhead, two-column statistics table, territory list). No regulatory content.
```

### T02 — additions

```markdown
- Add columns `oncall_roles` (e.g., `ENV-ONCALL;DCC-ESCALATION`) and `alternate_person_id` for every person with a document role or an on-call role.
- Mobile numbers are not listed for individuals. On-call groups are reached through the DCC (§1.1 numbers) and OMS paging groups (`ENV-ONCALL`, `SAF-ONCALL`, `REG-ONCALL`).
- `org_chart.md` also includes a Mermaid org chart and, in the "Document ownership matrix", each document's default route (owner → reviewer → approver), used by T91 for routing.
```

### T03 — additions

```markdown
- Add columns `render_path`, `record_series_ids` (from §1.6 Table R) and `supersedes_version`/`supersedes_date` **taken from the §1.4 Supersedes column** (no reconciliation step).
- `regulatory_basis_sections` and `coverage_dispositions_summary` (e.g., `covered:14;not_applicable:3;considered_no_obligation:2`) are filled by T90 from the basis files.
```

### T90 — replacement text

```markdown
## T90 — Baseline validation (Snapshot 1 must produce zero findings)

**Wave:** 4 · **Inputs:** `corpus/docs/**`, `corpus/grounding/**` (packs, not the orchestrator report), `corpus/_global/**`, `corpus/qa/**` · **Outputs:** `corpus/validation/T90_baseline_report.md`, `corpus/validation/T90_results.json`; fills `regulatory_basis_sections` and `coverage_dispositions_summary` in `document_register.csv`. Optional: `corpus/validation/T90_dashboard.html` (`frontend-design` + `dataviz`).

### Checks

Deterministic checks (re-run `validate.py` across the corpus):
1. **Quote and placement.** Every `s1_quote` is an exact substring of the cited section's `body_text_s1` and lies inside the cited subsection span.
2. **Value.** Every `doc_value` appears verbatim inside its clause boundary (§3.2). After numeral normalization (§3.4), the numbers, units, qualifiers and day types equal those in `s1_quote`. `derived` values are recomputed.
3. **Coverage and dispositions.** Every pack citation has exactly one disposition. Every `high` citation is `covered` with all material parameters. Report parameter-count parity between high and standard covered sections (the ratio of parameters per covered section; flag if high/standard > 1.5).
4. **Citation validity.** No cited section is repealed, absent from S1, or outside the pack. No phantom citations.
5. **Value ledger.** 100% of body numbers ledgered. `company_practice` values never sit in a cited sentence unless prefixed `Internal performance target:` or `Company position:`.
6. **Clause IDs.** Grammar, uniqueness, boundaries; all Wave 3 references resolve against `clause_id_freeze.json`; no retired ID is referenced.
7. **Cross-document consistency.** §1 and §1.6 constants; people and roles (no unknown named persons); forms; record series (every Wave 2 records clause maps to a T12 series); register `implementing_documents` and calendar `source_procedure` resolve; `cross_doc_refs` are symmetric.
8. **Dates.** No date after approval; revision histories ordered and earlier than approval; T03 matches §1.4.
9. **Datasets.** Re-run each script with the same seed; byte-identical outputs; row counts within range; every row complies with the pack parameters (no overdue meter group, no late reportable outage, spill or accident report, no fee charged in violation).
10. **Render parity.** Every rendering opens and contains 100% of the canonical sentences and rows.

LLM checks:

11. **Independent fidelity review** (as §0.4 step 3; fresh agent per document). Target: zero issues.
12. **Realism & depth rubric** (§3.8 Parts A–C; a fresh agent per document, not the one used in the QA loop). Report scores per criterion; pass thresholds per §3.8.
13. **Company positions.** For every `basis.interpretations` entry, the fidelity reviewer confirms that it does not contradict pack text.

Isolated checks (run by the T91 isolated agent at T90's request; T90 receives only pass/fail and clause IDs, never S2 text):

14. **Snapshot-2 contamination.** For every changed citation, confirm that no document value or phrase matches an S2-only value or 6-word shingle. Any hit fails the document, because the generator used knowledge beyond the pack.

Engine check:

15. **Strata baseline run (if available).** Run the engine with Snapshot 1 as current law. Expected: zero non-informational findings. Every informational finding is listed with the reason.

### Report format

- Per document: pass/fail per check, rubric scores, issues with clause IDs and quotes, and the fix applied (with a pointer to `fixlog.md`).
- Corpus summary: counts by check; realism score distribution; the high/standard parity ratio per document.
- Re-run until all checks pass; record the final pass with a timestamp and the corpus SHA-256 (hash of all `corpus/docs/**` files).
- Fixes go back to the orchestrator. The validator never edits documents.
```

### T91 — replacement text

```markdown
## T91 — Expected-findings answer key (restricted)

**Wave:** 5 · **Runs in an isolated agent.** Outputs are never shown to generator agents, never placed in a generator's context, and never provided to the Strata engine.
**Inputs:** all basis files, documents, datasets, `clause_id_freeze.json`, `_orchestrator_report.json`, Snapshot-2 IAC text (read directly from the database), and the T90 corpus SHA-256.
**Outputs:** `corpus/eval/expected_findings.json`, `corpus/eval/expected_findings.md`, `corpus/eval/scoring.py`, `corpus/eval/adjudication_log.md`

### Steps

1. **Pair sections.** Pair each S1 citation with its S2 successor using `prior_version_id`, then the renumber map. Normalize both. Diff at subsection level using S1 spans and S2 spans computed the same way.
2. **Classify each changed parameter:** unchanged · value changed · qualifier or day-type changed · condition changed · content element added or removed · requirement removed · section repealed · section or subsection renumbered · new section in scope.
3. **Expected findings per clause.** For every assessed clause citing a changed citation, assign `finding_type` (`parameter_change` · `required_content_change` · `conflict` · `stale_citation` · `new_requirement_gap` · `stale_at_approval` · `informational`) and `severity` (high: customer-facing or regulator-facing obligation; medium: internal process; low: informational).
   - Set `acceptable_clause_ids`: the primary clause plus every other clause in the same document that restates the same parameter, such as a template field. A detection on any of these counts once.
   - Set `parent_tolerance`: true when a detection on the immediate parent clause is acceptable.
4. **Propagation.** Using `cross_doc_refs`, `implementing_documents`, `source_procedure` and T12 `citation`, add the expected finding for every dependent row in T10, T11 and T12, and for tariff sub-rules ↔ procedure clauses. Mark `propagated_from`.
5. **New requirements.** For each new S2 section in a document's scope, add `new_requirement_gap` anchored at the document level with `insertion_point` (the section where a real author would add it) and `acceptable_clause_ids` = that section's clauses.
6. **Negative set.** List every assessed clause whose citations are all unchanged (including decoys) as `must_not_flag`. List decoy citations under `decoys_correctly_unchanged`.
7. **Quantified impacts.** For dataset documents (T18, T19, T20, T21), re-run the dataset logic with S2 parameters and record expected counts with tolerance (exact for deterministic counts).
8. **Cleared documents.** Record "expected: cleared" with the S2 changes considered and why they do not affect the document.
9. **Dual annotation.** Two independent isolated agents produce keys A and B. A third adjudicates disagreements in `adjudication_log.md`. Report inter-annotator agreement (Cohen's κ on finding_type at clause level). Target κ ≥ 0.8 before release.
10. **Write `expected_findings.json`:**
   ```json
   {
     "corpus_sha256": "<from T90>",
     "documents": [
       {
         "doc_id": "RPL-CS-PRO-004",
         "expected_status": "flagged|cleared",
         "findings": [
           {
             "finding_id": "EF-0001",
             "clause_id": "RPL-CS-PRO-004:7.2",
             "acceptable_clause_ids": ["RPL-CS-PRO-004:7.2", "RPL-CS-PRO-004:App-A.F4"],
             "parent_tolerance": true,
             "citation": "170 IAC 4-1-16(c)",
             "finding_type": "parameter_change",
             "severity": "high",
             "s1_quote": "...",
             "s2_quote": "...",
             "doc_value": "...",
             "expected_action": "Update notice period in §7.2 and App-A field F4",
             "route_to": {"owner": "P15", "reviewer": "P13", "approver": "P03"},
             "propagated_from": null
           }
         ],
         "must_not_flag": ["RPL-CS-PRO-004:6.3", "..."],
         "quantified_impacts": [],
         "decoys_correctly_unchanged": ["170 IAC 4-1-13"]
       }
     ]
   }
   ```
11. **`scoring.py` and `expected_findings.md`.**
   - A system finding **matches** an expected finding when the document is the same, the clause is in `acceptable_clause_ids` (or is its parent, if `parent_tolerance`), and the citation is at the same section. `finding_type` agreement is scored separately.
   - Each expected finding matches at most one system finding; extra detections on the same expected finding are ignored, not counted as false positives.
   - **Precision** = matched / (system non-informational findings). **Recall** = matched / (expected non-informational findings), reported overall, by severity, by document and for propagated vs. primary findings.
   - **False-positive rate on the negative set** = flagged `must_not_flag` clauses / |must_not_flag|. Target: 0.
   - **Routing accuracy** = matched findings with correct `route_to` / matched.
   - **Quantified-impact accuracy** = exact-match rate.
   - **Baseline requirement:** a run against S1 must yield zero non-informational findings (from T90 check 15).
   - The `.md` holds a summary table (documents × expected status × count by finding type and severity) and these scoring instructions.
```

---

## Notes for the orchestrator (not spec text)

1. **Expected "cleared" risk for T20 and T21.** The real 327 IAC 2-6.1 and 170 IAC 4-1-24 texts may be unchanged between the snapshots. That is fine: T00 step 10 makes it visible. Decoys still apply, and the documents become the demo's "cleared with reasoning" cases.
2. **Highest Snapshot-1 false-finding risks in this group, in order:**
   1. T21 importing other-state accident thresholds.
   2. T20 classification of utility assets under facility/transportation and petroleum.
   3. T20 federal RQ values filled from memory.
   4. T12 stating regulatory periods for statutes or FERC rules.
   5. T11 stating regulatory due dates for out-of-scope filings.
   Each is addressed by explicit task rules plus T90 checks 5, 13 and 14.
3. **Coordination.** §1.6 Tables S, S-INC, R, D and X must be in place before Wave 2. Groups A and B tasks also cite Table R series and Table D documents.
