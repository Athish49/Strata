# Strata v1 — Synthetic Company Corpus: Generation Spec

**Client (fictional):** Rockridge Power & Light Company ("RPL", "Rockridge Power")
**Purpose:** Generate the company-side documents that Strata's intelligence layer will assess when Indiana regulations change between knowledge-layer Snapshot 1 and Snapshot 2.
**Spec version:** 2.0 · 2026-10-06
**Companion file (orchestrator only, never given to worker agents):** `strata_corpus_orchestrator_appendix.md` (Appendix O)

---

## 0. How to use this file

### 0.1 For the orchestrator

This file is designed so that **one agent executes one task**. Every task is self-contained *together with* Sections 0–3 (the global context, alignment protocol and output standard), which every agent must read first. Appendix O lives in the separate orchestrator-only file `strata_corpus_orchestrator_appendix.md` and is never given to worker agents.

**Prompt to give each worker agent** (replace `Txx`):

> You are generating one deliverable for a fictional Indiana electric utility. Read Sections 0, 1, 2 and 3 of `strata_synthetic_corpus_spec.md` in full, then read **Task Txx** in full. Execute only Task Txx. Do not read any other *task section* of the spec, Appendix O, or any file under `corpus/eval/` or `corpus/grounding/_orchestrator_report.json`.
> You may read: `corpus/_global/**`; your own grounding pack `corpus/grounding/Txx.json` (if your task has one); and the files listed under **Inputs** in your task. Do not read any other grounding pack.
> If your task has a grounding pack and it is missing or empty, stop and report that. Never substitute your own knowledge of the Indiana Administrative Code, any other edition of it, or any other state's rules.
> Write outputs exactly to the paths the task specifies. Before finishing, run the self-checks in §2.6 and §3.8 and write `corpus/qa/<DOC_ID>/selfcheck.json`. In your final message, report: outputs written, self-check results, `basis.gaps`, `basis.interpretations`, and any conflict between §1 and your pack.

**Execution waves** (tasks within a wave run in parallel):

| Wave | Tasks | Depends on | Exit gate |
|---|---|---|---|
| 0 | T00 | Strata database access | T00 leak test passes; orchestrator reviews Appendix O items and applies any §1.4 date adjustments; fills and removes every "orchestrator to confirm/list" placeholder in §1.6 (Appendix O-7) |
| 1 | T01, T02, T03, T04 | Sections 0–3 | Schema checks pass; T04 acceptance tests pass |
| 2 | T13–T21 | T00, Wave 1 (incl. T04 master data) | Per-document QA loop (§0.4) passes; then the **clause-ID freeze**: `corpus/qa/clause_id_freeze.json` lists every clause ID and its text hash for Wave 2 |
| 3a | T10 | Freeze | QA loop passes |
| 3b | T11, T12 | T10 | QA loop passes |
| 4 | T90 | Waves 2–3 | All checks pass, including the realism rubric |
| 5 | T91 | T90 passed; Snapshot-2 access | Isolated. Dual annotation and adjudication complete. **Its output is never shown to generator agents or to the Strata engine.** |

**After the freeze:** a fix to a Wave 2 document may change clause *text*, but it may not delete, renumber or reuse a frozen clause ID. A new clause gets a new ID (e.g. `7.2a`). If a fix must remove a clause, the orchestrator records the mapping in `clause_id_freeze.json` (`"retired": {"old": "...", "replaced_by": "..."}`) and re-runs the QA loop for T10–T12.

**Information barriers:** the Strata engine sees only `corpus/docs/*/*.md`, `corpus/docs/*/data/*.csv` and `corpus/docs/*/render/**` (**not** basis files, `scripts/`, `data/README.md` or `_manifest.json`), `corpus/_global/**` and its own knowledge layer. It never sees grounding packs, basis files, `corpus/qa/**`, Appendix O or `corpus/eval/**`.

### 0.2 Task index

| Task | Doc ID | Document | Vertical |
|---|---|---|---|
| T00 | — | Snapshot-1 grounding packs | Infrastructure |
| T01 | — | Company profile and fact sheet | Infrastructure |
| T02 | — | People directory and org chart | Infrastructure |
| T03 | — | Document register | Infrastructure |
| T04 | — | Shared operational master data (circuits, substations, outage history, reliability facts) | Infrastructure |
| T10 | RPL-CMP-REG-001 | Regulatory Obligations Register | Compliance & Legal |
| T11 | RPL-REG-CAL-2025 | Regulatory Reporting Calendar 2025 | Compliance & Legal |
| T12 | RPL-LEG-RRS-001 | Records Retention Schedule | Compliance & Legal |
| T13 | RPL-TAR-GRR-012 | Tariff for Electric Service, IURC No. 12 — General Rules and Regulations | Policy & Governance |
| T14 | RPL-CS-PRO-004 | Disconnection, Reconnection & Winter Protection Procedure | Policy & Governance |
| T15 | RPL-CS-PRO-007 | Meter Test Request & Billing Adjustment Procedure | Policy & Governance |
| T16 | RPL-DO-PLN-002 | Vegetation Management Plan 2025 | Policy & Governance |
| T17 | RPL-CS-PRO-011 | Customer Complaint & Dispute Resolution Procedure | Policy & Governance |
| T18 | RPL-MTR-PGM-001 | Meter Testing Program Plan + datasets | Operations & Processes |
| T19 | RPL-DCC-PRO-003 | Service Interruption Reporting Procedure + outage datasets | Operations & Processes |
| T20 | RPL-ENV-PRO-005 | Spill Response & Reporting Procedure | Environmental |
| T21 | RPL-SAF-PRO-009 | Electrical Accident & Incident Reporting Procedure | Workforce & Safety |
| T90 | — | Baseline validation report | Validation |
| T91 | — | Expected-findings answer key (restricted) | Evaluation |

Task sections appear below in wave order (T00–T04, then T13–T21, then T10–T12, T90, T91).

### 0.3 Output folder layout

```
corpus/
  _global/
    company_profile.yaml, company_fact_sheet.md, render/company_fact_sheet.pdf   (T01)
    people_directory.csv, org_chart.md                                            (T02)
    document_register.csv                                                         (T03)
    ops/  circuits_master.csv, substations_master.csv, outage_incidents_base.csv, outage_events_base.csv,
          outage_restoration_steps_base.csv, daily_saidi_history_2019_2023.csv,
          med_days.csv, reliability_facts.yaml, README.md, _manifest.json, scripts/               (T04)
    reference/   human-verified industry extracts supplied by the orchestrator (e.g., sampling_table.json, ieee1366_med_method.md)
    contacts_sources.md                                                           (orchestrator: verification of §1.6 public contacts)
  grounding/
    T10.json … T21.json                       (T00 — one pack per document task)
    _normalizer.py, _scope.py, _leaktest.py, _leaktest_report.json   (T00)
    _orchestrator_report.json                 (T00 — orchestrator only)
  docs/
    <DOC_ID>/
      <DOC_ID>_v<version>.md                  (canonical document, carries clause IDs)
      <DOC_ID>.basis.json                     (hidden ground-truth sidecar, §3.4)
      data/*.csv, data/README.md, data/_manifest.json      (datasets, where required)
      scripts/*.py                            (dataset generators, acceptance_tests.py, render_<DOC_ID>.py)
      render/                                 (.docx / .pdf / .xlsx / charts — what a user would open, §3.7)
  qa/
    validate.py                               (orchestrator, written once)
    clause_id_freeze.json
    exemplar_anatomy/<class>.yaml             (orchestrator, before Wave 2)
    <DOC_ID>/selfcheck.json, validate.json, review_fidelity.md, review_realism.json, fixlog.md
  validation/
    T90_baseline_report.md, T90_results.json
  eval/                                       (T91 only — restricted)
    expected_findings.json, expected_findings.md, scoring.py, adjudication_log.md
```

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
   - dates (no past-event date after approval; prior-version revision entries ordered and earlier than approval)
   - Output: `corpus/qa/<DOC_ID>/validate.json`.
3. **Independent fidelity review.** A fresh agent receives the document and the pack only (not the basis file and not this spec's task text). It lists every clause that conflicts with, omits a condition of, or overstates the pack, quoting both texts. Target: zero issues. Output: `review_fidelity.md`.
4. **Independent realism review.** A fresh agent receives the document, the task section, §3.6 and the exemplar anatomy checklist for the document class (§3.8 part C). It scores §3.8 part B and runs the exemplar comparison and the auditor-question test. Output: `review_realism.json`.
5. **Fix.** The original worker (or a fixer agent with the same read permissions) receives the three reports. It may change only the flagged clauses and anything needed to stay consistent. It must preserve clause IDs (post-freeze rules apply in Wave 3), and it logs each change in `corpus/qa/<DOC_ID>/fixlog.md` (clause ID, issue, change).
6. **Re-run steps 2–4** on the changed document.
7. **PASS** = validate.json has zero errors, review_fidelity has zero issues, and review_realism meets §3.8 thresholds. The orchestrator records the pass with a timestamp and the document's SHA-256.

Reviewers in steps 3–4 never see each other's output or earlier iterations' reviews, so they don't anchor on them.

---

## 1. Global context (canonical — every agent uses these facts verbatim)

Nothing in this section may be altered or embellished in ways that contradict it. Agents may add plausible detail that does not conflict (e.g., a street name for a service center), but must not change any number, name, date or ID given here, and **must not create new named individuals** (use role titles for anyone not in §1.3).

### 1.1 Company profile

| Field | Value |
|---|---|
| Legal name | Rockridge Power & Light Company |
| Short names | RPL; Rockridge Power (customer-facing) |
| Entity type | Indiana corporation; **investor-owned public utility** under IC 8-1-2, financed by the sale of securities and overseen by a board representing shareholders |
| Parent | Rockridge Energy Group, Inc. (holding company) |
| Regulator | Indiana Utility Regulatory Commission (IURC) |
| IURC utility ID | 99012 (fictional) |
| Headquarters | 400 Wabash Commons Drive, Lafayette, Indiana 47901 |
| Customer service | 1-800-555-0142 (24/7) · customercare@rockridge-pl.example |
| Outage line | 1-800-555-0177 |
| Web | www.rockridge-pl.example |
| Business model | **Electric distribution only.** RPL owns **no generating units**. It buys full-requirements wholesale power under a FERC-jurisdictional agreement and operates inside the MISO footprint. |
| Owned voltage levels | 69 kV subtransmission (418 circuit miles); 12.47 kV and 34.5 kV primary distribution |
| Service territory | 14 west-central Indiana counties: Tippecanoe, Clinton, Carroll, White, Benton, Warren, Fountain, Montgomery, Boone, Hendricks, Putnam, Parke, Vermillion, Vigo |
| Service centers | Lafayette (HQ), Crawfordsville, Terre Haute, Frankfort, Danville |
| Customers (2024-12-31) | Residential 361,480 · Commercial 44,215 · Industrial 1,184 · Public street & highway lighting 612 · **Total 407,491** |
| Distribution plant | 112 distribution substations · 528 distribution circuits · 14,200 overhead circuit miles · 4,900 underground circuit miles · ~212,000 poles · ~118,400 distribution transformers (pole-mount and padmount) · 186 oil-filled substation power transformers |
| Meters in service (2024-12-31) | 409,950 total: 371,200 solid-state AMI · 31,400 solid-state AMR · 7,350 electromechanical (legacy, mostly rural) |
| Standby generation | Three diesel emergency standby generators (HQ data center 750 kW; Crawfordsville and Terre Haute service centers 350 kW each), each with a double-walled belly tank. These are emergency/backup units, not generating stations. |
| Employees | ~1,450 |
| Core systems (generic names only) | Customer Information System ("CIS"); Outage Management System ("OMS"); AMI head-end ("AMI HES"); Geographic Information System ("GIS"); Work & Asset Management ("WAM"); EHS Incident Management System ("EHS-IMS"); Document Control System ("DCS") |
| Regulatory contacts (external) | IURC (incl. Consumer Affairs Division); Indiana Office of Utility Consumer Counselor (OUCC); Indiana Department of Environmental Management (IDEM); Indiana 811 |

**Do not** use the name, logo, service area or text of any real utility. Real regulators, real public programs (e.g., Indiana's Energy Assistance Program) and real public forms (e.g., IURC State Form 54646 "Report of Outage") may be named.

### 1.2 Timeline and the "law as-of" rule

| Date | Meaning |
|---|---|
| **2024-12-31** | **Law as-of date for every document.** Every regulatory statement reflects the Indiana Administrative Code as it stood on this date, exactly as provided in your grounding pack. |
| 2025-01-03 → 2025-03-14 | Window in which every v1 document was last approved (exact dates in §1.4). Exception: the tariff (T13), whose current sheets were approved by the IURC on 2024-05-15. |

**Rule:** Every document reads as if RPL staff wrote it in early 2025. No document may anticipate, mention or hedge about rule changes, rulemakings or later editions. If you recall any version of an Indiana rule other than the text in your pack, ignore it: the pack is the law for this corpus.

**Preliminary data labeling.** Documents approved in January–February 2025 that present 2024 results label them "preliminary — data extracted <date>". Extract dates: T18 2025-01-03 · T16 2025-01-15 · T19 2025-02-10.

### 1.3 People directory (canonical)

Email format: `first.last@rockridge-pl.example`. Phone extensions are fictional.

| Person ID | Name | Title | Department | Reports to |
|---|---|---|---|---|
| P01 | William Hartley | President & Chief Operating Officer | Executive | — |
| P02 | Catherine Brandt | Vice President & General Counsel | Legal | P01 |
| P03 | Jonathan Pierce | Senior Counsel, Regulatory | Legal | P02 |
| P04 | Margaret Ellison | Chief Compliance Officer | Compliance | P01 |
| P05 | David Okafor | Manager, Regulatory Compliance | Compliance | P04 |
| P06 | Priya Raman | Senior Compliance Analyst | Compliance | P05 |
| P07 | Thomas Whitfield | Vice President, Regulatory & Government Affairs | Regulatory Affairs | P01 |
| P08 | Elena Vasquez | Manager, Regulatory Affairs | Regulatory Affairs | P07 |
| P09 | Marcus Lee | Regulatory Affairs Analyst | Regulatory Affairs | P08 |
| P10 | Robert Haskins | Manager, Rates & Tariffs | Regulatory Affairs | P07 |
| P11 | Aisha Thompson | Senior Rates & Tariffs Analyst | Regulatory Affairs | P10 |
| P12 | Linda Nguyen | Records & Information Manager | Legal | P02 |
| P13 | Karen Mitchell | Director, Customer Service | Customer Operations | P16 |
| P14 | Steven Park | Director, Customer Operations | Customer Operations | P16 |
| P15 | Jasmine Carter | Supervisor, Credit & Collections | Customer Operations | P14 |
| P16 | Michael Brennan | Vice President, Operations | Operations | P01 |
| P17 | Brian Kowalski | Manager, Customer Advocacy & Complaint Resolution | Customer Operations | P13 |
| P18 | Luis Hernandez | Supervisor, Metering Services | Metering | P20 |
| P19 | Gregory Walsh | Manager, Meter Shop & Standards Laboratory | Metering | P20 |
| P20 | Angela Ruiz | Director, Metering | Metering | P16 |
| P21 | Patrick O'Neill | Director, Distribution Operations | Distribution Operations | P16 |
| P22 | Rachel Stein | Manager, Vegetation Management Program | Distribution Operations | P21 |
| P23 | Kevin Adeyemi | Manager, Distribution Control Center | Distribution Operations | P21 |
| P24 | Sandra Kim | Director, Environmental, Health & Safety | EHS | P16 |
| P25 | Daniel Foster | Manager, Environmental Services | EHS | P24 |
| P26 | Hannah Brooks | Senior Environmental Specialist | EHS | P25 |
| P27 | Tyrone Jackson | Manager, Safety | EHS | P24 |

### 1.4 Document register (canonical)

"Approved" is the date of the approval that put the current version in force. All documents carry `Law as-of: 2024-12-31`. "Supersedes" is the prior version every document's revision history must end with.

| Task | Doc ID | Title | Version | Effective | Approved | Owner | Reviewer | Approver | Review cycle | Supersedes |
|---|---|---|---|---|---|---|---|---|---|---|
| T10 | RPL-CMP-REG-001 | Regulatory Obligations Register | 4.0 | 2025-03-14 | 2025-03-13 | P06 | P05 | P04 | Quarterly | 3.3 (2024-12-16) |
| T11 | RPL-REG-CAL-2025 | Regulatory Reporting Calendar 2025 | 1.2 | 2025-03-17 | 2025-03-14 | P09 | P08 | P07 | Annual (rolled each January); revised when a source procedure changes | 1.1 (2025-02-24) |
| T12 | RPL-LEG-RRS-001 | Records Retention Schedule | 7.2 | 2025-03-17 | 2025-03-14 | P12 | P03 | P02 | Biennial | 7.1 (2023-03-20) |
| T13 | RPL-TAR-GRR-012 | Tariff for Electric Service, IURC No. 12 — General Rules and Regulations | Sheets as revised through 2024-06-01 | 2024-06-01 | 2024-05-15 (IURC approval, fictional Cause No. 99012) | P11 | P10 | P03 | On change; reviewed annually | IURC No. 12 sheets eff. 2021-10-01 |
| T14 | RPL-CS-PRO-004 | Disconnection, Reconnection & Winter Protection Procedure | 5.1 | 2025-02-10 | 2025-02-05 | P15 | P13 | P03 | Annual | 5.0 (2024-01-15) |
| T15 | RPL-CS-PRO-007 | Meter Test Request & Billing Adjustment Procedure | 3.0 | 2025-02-17 | 2025-02-12 | P18 | P14 | — (two-signature document, §3.1) | Annual | 2.1 (2023-11-06) |
| T16 | RPL-DO-PLN-002 | Vegetation Management Plan 2025 | 2025.1 | 2025-01-27 | 2025-01-22 | P22 | P21 | P03 | Annual | 2024.2 (2024-07-15) |
| T17 | RPL-CS-PRO-011 | Customer Complaint & Dispute Resolution Procedure | 2.3 | 2025-03-03 | 2025-02-26 | P17 | P13 | — (two-signature document, §3.1) | Annual | 2.2 (2024-03-18) |
| T18 | RPL-MTR-PGM-001 | Meter Testing Program Plan | 6.0 | 2025-01-13 | 2025-01-08 | P19 | P20 | P16 | Annual | 5.2 (2024-02-05) |
| T19 | RPL-DCC-PRO-003 | Service Interruption Reporting Procedure | 4.2 | 2025-02-24 | 2025-02-19 | P23 | P21 | P08 | Annual | 4.1 (2024-04-22) |
| T20 | RPL-ENV-PRO-005 | Spill Response & Reporting Procedure | 3.1 | 2025-03-10 | 2025-03-05 | P26 | P25 | P24 | Annual | 3.0 (2024-03-11) |
| T21 | RPL-SAF-PRO-009 | Electrical Accident & Incident Reporting Procedure | 2.0 | 2025-03-17 | 2025-03-12 | P27 | P24 | P08 | Annual | 1.2 (2023-10-02) |

The orchestrator may adjust approval/effective dates before Wave 2 under rules held in the orchestrator appendix; if it does, this table is updated before any worker starts.

### 1.5 Cross-document consistency facts

Use these where relevant so documents agree with each other:

- Customer-facing phone numbers, addresses and website are as in §1.1.
- Customer payment channels: online portal, auto-pay, phone (IVR), authorized pay stations, mail to "Rockridge Power, P.O. Box 6600, Lafayette, IN 47903".
- Field crews are internal; vegetation work is performed by two contracted line-clearance firms referred to only as "Contractor A" and "Contractor B".
- Meter testing is performed in the Meter Shop & Standards Laboratory at the Lafayette HQ campus.
- The Distribution Control Center (DCC) is in Lafayette and is staffed 24/7.
- Internal form numbers: Spill Report `EHS-F-201`; Incident Report `EHS-F-101`; Meter Test Request `MTR-F-010`; Meter Test Report `MTR-F-011`; Complaint Intake `CS-F-030`; Vegetation Notice `VM-F-004`; Disconnection Notice `CS-F-012`; Medical Certificate `CS-F-015`.
- Operational master data in `corpus/_global/ops/` (T04) is canonical for circuits, substations, outage history and reliability figures. Any document stating such a figure must equal it.

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

**Tariff references:** use exactly these sheet numbers (they match the T13 sheet map). Disconnection = Rule 13, Sheets 37–41; charges = Rule 16, Sheets 45–46; metering = Rule 9, Sheets 27–29; adjustments = Rule 12, Sheets 35–36; billing = Rule 11, Sheets 32–34.

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
ID formats: `SAF-LL-2025-nn` (safety lessons-learned bulletins) · CIS case type `CMP` (complaint case) · OMS paging/on-call groups `ENV-ONCALL`, `SAF-ONCALL`, `REG-ONCALL`, `DCC-ESCALATION` · `INC-2025-nnnnn` (EHS-IMS incidents) · `SPL-2025-nnnn` (spills) · `CAPA-2025-nnnn` · `OBL-nnnn` · `CTL-<dept>-nnn` · `CAL-2025-nnn`.

**Table X — External EHS and regulatory contacts (public facts; the orchestrator verifies against an archived early-2025 copy of each page before Wave 2 and records the URL in `corpus/_global/contacts_sources.md`)**
- IDEM Emergency Response (24-hour spill line): (888) 233-7745 · (317) 233-7745 — https://www.in.gov/idem/cleanups/investigation-and-cleanup-programs/emergency-response/
- National Response Center: (800) 424-8802 (listed on IDEM's quick-reference sheet) — referenced only via RPL-ENV-PRO-008
- U.S. EPA Region 5 (as listed on IDEM's quick-reference sheet; orchestrator to confirm current number)
- IURC Energy Division: (317) 232-2785 — https://www.in.gov/iurc/energy-division/electricity-industry/annual-report-filing-electricity/ ; IURC filings via the IURC Electronic Filing System (iurc.portal.in.gov)
- IURC office hours for operational "business hours": 8:15 a.m.–4:45 p.m. ET, Monday–Friday (as Table C; orchestrator confirms); State of Indiana holidays for 2025 (orchestrator to list)
- Emergency services: 911

**Rules for all §1.6 data:** use it verbatim. If a pack sets, caps or prohibits any item, the pack governs; report the conflict. **Do not create new named individuals.** Use role titles for anyone not in §1.3. Fictional phone numbers use the 555-0100 to 555-0199 range (e.g. 765-555-0123).

---

## 2. Snapshot-1 alignment protocol (mandatory for T10–T21)

The goal: **the corpus must produce zero findings when assessed against Snapshot 1**, and must restate the fine print (conditions, exceptions, content elements) of every rule it covers. These rules achieve both.

### 2.1 The grounding pack is the only source of regulatory truth

Each task has a grounding pack at `corpus/grounding/Txx.json` (built by T00). It contains, for every IAC section in the task's scope, the Snapshot-1 heading, status, full body text, subsection spans, cross-references and a `coverage_priority` flag.

- Use **only** the pack for regulatory content: every value, wording, condition and citation. Never use web pages, memory, agency FAQs, other utilities' documents, other states' rules or any other edition of the IAC.
- This spec deliberately states **no regulatory values**.
- **Contamination warning.** Study references and web pages contain values from other states, federal law or later Indiana editions. Treat every number in them as contaminated. If a value in your draft matches something you read outside the pack and you cannot find it in the pack, delete it.
- **Research permissions.** Web research is allowed only for: (a) document form, layout, vocabulary and table design; (b) real public regulator contact details and public program names, and only where §1.6 does not already fix them; (c) magnitudes and typical ranges for company-chosen operational values that §1, §1.6 and T04 do not fix, plus industry-standard definitions (IEEE 1366, ANSI C12 terminology). Use official or primary sources only: regulator .gov sites and dockets, utilities' own published filings and tariffs, IEEE/ANSI/ASQ publications, EIA, national laboratories. No blogs, forums, vendor marketing (except practitioner papers a task names) or AI summaries.
- Research **never** supplies a regulatory value, citation or wording, even when a source states one. If a source and the pack disagree, the pack wins silently.
- Never reconstruct paywalled standards (sampling tables, IEEE methods) from memory. Use the human-verified extracts in `corpus/_global/reference/`; if none is supplied, write the item as labeled company practice.
- **Post-2024 references.** Study references dated 2025 or later may quote later editions of Indiana rules. Use them for layout only, and never open or follow their IAC citations.
- Log every URL opened in `basis.sources` (§3.4).

### 2.2 Build a parameter table before writing

Before drafting, extract from the pack every regulatory parameter relevant to the document into a working table (it goes into the basis file, §3.4):

- numbers and units (days, hours, months, years, percent, dollars, customer counts, temperatures)
- whether periods are **calendar** days, **business** days or **working** days
- comparison words ("at least", "not less than", "within", "not more than", "prior to")
- triggers and conditions ("upon written request", "if the meter was tested within…")
- required content elements of notices, reports and records
- parties (who must notify whom; who may request)
- exceptions and carve-outs
- applicability limits (e.g., a rule applying to investor-owned utilities only)

### 2.3 How regulatory content must be written

1. **Exact equivalence.** Any clause that restates a regulatory requirement must state the same value, unit, qualifier and condition as the Snapshot-1 text. Plain-English rewording is fine; changing meaning is not ("shall" ≠ "should"; "10 days" ≠ "10 business days"; "at least 14" ≠ "14").
2. **Cite at clause level.** Every clause that restates a requirement ends with its citation in the form used by the pack, at the most specific level supported by the text, e.g. `(170 IAC 4-1-16(b))`. Real Indiana tariffs do exactly this.
3. **No phantom requirements.** Never write "as required by <citation>" unless the pack's text for that citation actually contains the requirement. Company practices that go beyond the rule are written as company practice, without a citation.
4. **Internal targets are labeled.** Where RPL holds itself to a tighter standard, write it as a separate sentence starting `Internal performance target:` and never let it contradict the regulatory statement next to it.
5. **Restate fine print.** Include the exceptions, conditions and edge cases from the rule text that matter to the process — fine print is where changes land.
6. **Do not cite repealed sections.** If a section's Snapshot-1 status is `repealed`, it does not exist for this document.
7. **Applicability.** If a section in scope does not apply to RPL (e.g., applies only to REMCs, gas utilities or generating stations), do not restate it as an obligation. Where a real company would note it (the register, T10), mark it "Not applicable" with the reason.

### 2.4 Coverage rules

Every active section in your pack receives exactly one **disposition** in the basis file:
- `covered`: cited by exact citation in at least one clause.
- `not_applicable`: the section does not apply to RPL (§2.3.7), with the reason and the T01 attribute.
- `considered_no_obligation`: the section applies to RPL but creates nothing this document type must implement (e.g., a complaint-handling rule in the reporting calendar). Give a one-line reason.

**Parameter parity.** For every `covered` section, restate **every** material parameter (§2.2) that bears on this document's process, in body text, a table or a template. This applies equally to every covered section. Sections flagged `coverage_priority: "high"` must be `covered` (never `considered_no_obligation`) and must restate **all** their material parameters. Do not write high-priority sections at greater length or with more emphasis than comparable standard sections. Never mention the flag.

### 2.5 Forbidden content

- Any mention of Strata, snapshots, synthetic data, AI, test scenarios, future editions, pending rulemakings or "upcoming changes".
- Text copied verbatim from any real utility's document (imitate structure and tone only).
- Real people's names, real utility names in RPL's documents (regulator names are fine), real IURC cause numbers.
- Placeholder text such as `[TBD]`, `[Insert]`, `XXX`, "lorem ipsum".
- Named individuals other than the 27 people in §1.3 (use role titles). Fictional phone numbers must use the 555-0100 to 555-0199 range.

### 2.6 Self-check before finishing (every task)

1. Every parameter in the basis file has an `s1_quote` that is an **exact substring** of the pack's `body_text_s1` for that citation.
2. Every high-priority citation appears in the document, and every one of its material parameters appears in the basis file.
3. No event the document reports as having happened is dated after its approval date in §1.4 (forward-looking dates such as effective date, next review, 2025 schedules and due dates are allowed), and no document text implies knowledge after 2024-12-31.
4. All names, IDs and numbers from §1 are used verbatim.
5. The document reads like a real internal utility document: specific, procedural, with owners, steps, forms and records — not a summary of the law.
6. **Value ledger.** Every numeral, spelled-out number, percentage, time, date, temperature and dollar amount in the body is in `basis.value_ledger` with its source.
7. **No phantom citations.** Every citation string in the body appears in a basis clause whose `citations` include it, and every `regulatory_restatement` clause cites something.
8. **Subsection placement.** Each `s1_quote` lies inside the span of the subsection the clause cites (use the pack's `subsections`).
9. **Company positions.** Every `Company position:` sentence is listed in `basis.interpretations` and carries no citation.
10. **Contamination.** No value in the document comes from a study reference or memory (re-read §2.1).
11. **Datasets** (where the task has them): `scripts/acceptance_tests.py` passes and its output is appended to `data/README.md`.
12. **Rubric gates:** run the §3.8 Part A gates on your own output (use `corpus/qa/validate.py` if the orchestrator has provided it) and write `corpus/qa/<DOC_ID>/selfcheck.json`.

### 2.7 Law that is not in your pack

Real documents also rely on Indiana statutes (IC Title 8) and federal rules that are not in your grounding pack. When a real document would cover such a topic (e.g., a statutory winter disconnection protection, formal complaints under IC 8-1-2-54):
- Name the statute or rule and say the Company complies with it. Clause type `out_of_scope_reference`; record it in `out_of_scope_references`.
- State **no** values from it: no dates, durations, thresholds, temperatures or amounts.
- Build the full operational process around it (codes, forms, scripts, roles) as company practice.
- Never fill the value from memory, agency FAQs or other utilities' documents.

### 2.8 Company positions on how a rule applies to RPL

Some rules depend on classifications they do not make for utility assets (e.g., whether a pole-mount transformer is a "facility", where a "facility boundary" is, whether a fluid falls within a defined substance category, what "business hours" means in practice). When applying a pack provision requires such a classification:
1. If the pack's text decides it, cite the text.
2. If not, write one sentence beginning `Company position:` with **no citation**. Choose the reading that makes the obligation apply more broadly (more releases reportable, more notices given, records kept longer). Never contradict pack text.
3. Record it in `basis.interpretations`: `{"clause_id", "question", "position", "pack_citations_considered", "rationale"}`.

Company positions are assessed for conflict with the pack (T90 check 13) but are never restated as regulatory requirements.

---

## 3. Output standard

### 3.1 Document file

- Format: Markdown (`.md`), UTF-8, file name `<DOC_ID>_v<version>.md` (use `_` for spaces in the version string).
- Begins with YAML front matter:

```yaml
---
doc_id: RPL-CS-PRO-004
title: Disconnection, Reconnection & Winter Protection Procedure
company: Rockridge Power & Light Company
version: "5.1"
status: Approved
effective_date: 2025-02-10
approved_date: 2025-02-05
law_as_of: 2024-12-31
owner: {id: P15, name: Jasmine Carter, title: "Supervisor, Credit & Collections"}
reviewer: {id: P13, name: Karen Mitchell, title: "Director, Customer Service"}
approver: {id: P03, name: Jonathan Pierce, title: "Senior Counsel, Regulatory"}
next_review: 2026-02-10
classification: Internal
regulatory_basis: ["170 IAC 4-1-16", "..."]   # section-level list, from the basis file
supersedes: "5.0 (2024-01-15)"
---
```

- Then a document-control block as a real company would print it (title block, doc ID, version, effective date, owner/reviewer/approver with titles, "Uncontrolled when printed" notice).
- Then the body.

**Two-signature documents (T15, T17).** Front matter sets `approver: null` and adds the reviewer as the final signatory. The approval block has two rows: "Prepared and approved by" (owner) and "Reviewed and approved by" (reviewer). Findings on these documents route owner → reviewer.

**Tariff (T13).** The front matter carries owner/reviewer/approver as in §1.4. The sheets themselves print only the issuing officer named in T13.

### 3.2 Clause identifiers

**Grammar.** `CLAUSE_ID := <DOC_ID> ":" LOCAL`, where LOCAL is one of:
- section clause: `\d+(\.\d+){0,3}[a-z]?` (e.g., `7.2`, `7.2.3`, `7.2a` for post-freeze insertions)
- appendix clause: `App-[A-Z](\.\d+){0,2}`; form field: `App-[A-Z]\.F\d+` (e.g., `App-A.F12`)
- table row: `T<section>-<n>` (e.g., `T7-4`), always prefixed with the doc ID in the basis file and in the HTML comment
- tariff sub-rule (T13): `R\d+\.\d+(\([a-z0-9]+\))?` (e.g., `R13.4`, `R13.4(b)`); tariff charge-table row: `R16.T-\d+`. Sheet numbers are carried by `<!-- sheet: n -->` comments, not by the clause ID.
- dataset or register row: `<row key>` (e.g., `OBL-0042`, `CAL-2025-007`, `RRS-ENV-001`)

**Markers.**
- Markdown: an HTML comment on the line immediately before the clause, `<!-- clause: RPL-ENV-PRO-005:7.2 -->`.
- Table rows: the first column `ID` holds the LOCAL part, and a comment before the table lists `<!-- table: RPL-ENV-PRO-005:T7 -->`.
- CSV: the `clause_id` column.

**Boundaries.** A clause's text runs from its marker to the next marker of any level, not inclusive. A parent clause (`7.2`) therefore holds only its lead-in text, and its children are separate clauses. Every regulatory value sits in exactly one clause.

**Stability.** IDs are never reused or renumbered after the Wave 2 freeze (§0.1). IDs never appear in rendered output.

### 3.3 Standard sections for procedures and plans

Unless a task says otherwise, procedures and plans include, in this order: Purpose · Scope & applicability · Definitions · Regulatory basis (list of citations with headings) · Roles & responsibilities (named people from §1.3) · Procedure / requirements (numbered) · Records & retention · Training · Related documents (other RPL doc IDs from §1.4) · Revision history (2–4 prior versions, dates before the current approval date, change reasons that do not reference future law) · Approval block (names, titles, dates) · Appendices (forms, templates, scripts, contact sheets).

### 3.4 Basis sidecar (`<DOC_ID>.basis.json`)

The hidden ground truth. It is **not** part of the document, is never shown to the Strata engine, and must not be referenced by the document.

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
    {"clause_id": "<id>", "text": "<value>", "source": "pack|section1|section1.6|ops_master|company_practice|worked_example|dataset", "ref": "<citation, table ref or note>"}
  ],
  "gaps": [],
  "sources": [{"url": "<url opened>", "title": "<title>", "accessed": "<real access date>", "used_for": "structure|magnitude|terminology|contact", "notes": "<what was taken>"}],
  "company_practice_values": [{"clause_id": "<id>", "name": "<e.g., backbone trim cycle>", "value": "<value>", "benchmark_source": "<url or reviewer judgement>"}],
  "considered_no_obligation": [{"citation": "<subsection>", "reason": "<one line>"}],
  "worked_examples": [{"clause_id": "<id>", "script": "<path>", "inputs": {}, "outputs": {}}],
  "notes": ""
}
```

Rules for the schema:
- `considered_no_obligation` holds subsection-level entries (T10, T11); section-level dispositions stay in `coverage`.
- `derived` is used when the document value is computed from a pack value (e.g., a 2025 due date): `{"from_parameter": "<parameter_id>", "method": "<computation>"}`.
- **Numeral normalization for the value check:** spelled-out numbers become digits, "ten (10)" collapses to 10, and unit synonyms (`hrs`/`hours`) are canonicalized.
- `route_override` routes a clause to someone other than the document's default (e.g., a customer letter template routed to P03).
- `cross_doc_refs` lists clauses in other documents that restate or depend on this clause, so a single change is routed to all of them.
- **Value ledger.** Every numeral, spelled-out number, percentage, time, date, temperature and dollar amount in the body appears in `value_ledger` with its source: `pack` (with citation and `s1_quote`), `section1`, `section1.6`, `ops_master` (T04 files), `company_practice`, `worked_example` or `dataset`. A `company_practice` value may not sit in a sentence that cites a regulation unless that sentence begins `Internal performance target:`.
- Allowed `clause_type` values: `regulatory_restatement` · `internal_procedure` · `internal_target` · `template_field` · `out_of_scope_reference` · `company_position` · `definition`.

### 3.5 Datasets
- CSV is canonical: UTF-8, header row, comma, RFC 4180 quoting, no thousands separators, `.` decimal, empty string for null (no "NA"/"null"). Files > 25 MB may be `.csv.gz`.
- Dates `YYYY-MM-DD`. Timestamps `YYYY-MM-DDThh:mm` local time (America/Indiana/Indianapolis) **plus** a `utc_offset` column (`-05:00`/`-04:00`) wherever DST ambiguity is possible.
- IDs: one pattern per entity, declared in `data/README.md` and registered across documents (circuits `LAF-012-3`; meters `RPL-<vendor>-<7 digits>`; persons from §1.3; technicians `MT-###`; outage events `OE-2024-######`; outage incidents `OI-2024-#####`; EHS incidents `INC-2024-#####`).
- Deterministic Python generator, fixed seed, `params` dict at top populated from the basis file (regulatory values never hard-coded twice). Company-practice parameters live in a separate `company_params` dict with comments.
- `data/README.md` contains, per dataset: purpose; row count; primary key; foreign keys; a data dictionary table (`field · type · unit · allowed values/range · source/derivation · nullable`); generation notes; and the acceptance-test results with timestamp.
- `data/_manifest.json`: file, rows, columns, sha256, generator script and seed.
- Each task's `scripts/acceptance_tests.py` exits non-zero on any failure. T90 re-runs it.

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
- Running header (company · doc ID · title) and footer (version · effective · classification · "Uncontrolled when printed" · page X of Y) in the rendering.
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

### 3.6a Realism of compliance data
- Baseline records comply 100% with Snapshot-1 parameters, but they must not be uniformly comfortable. For every timing, interval or count parameter tested by a dataset, the margin to the limit follows a realistic distribution: most records comfortable, and a documented share (task-specified, typically 10–20%) in the last 20% of the allowed window. No record is at or past the limit. Record each margin rule in `data/README.md`.
- Operational data shows ordinary imperfection that has no regulatory effect: unknown causes, re-coded causes, deferrals with notes, one rejected meter lot, budget variances with explanations, AMI functional failures. Do not "clean" data into perfection, and do not insert regulatory non-compliance.
- Do not tune results to flatter RPL. Use the benchmark ranges given in the task. Where RPL sits outside a benchmark, the document explains why (e.g., rural OH exposure).

### 3.7 Rendered deliverable (in addition to the canonical Markdown)

The Markdown file is canonical and carries the clause IDs. Every task also produces a rendered copy that looks like the real thing, under `corpus/docs/<DOC_ID>/render/`, built by a deterministic script in `scripts/`:
- **Procedures and plans:** use the `docx` skill to produce `.docx`, then convert it to `.pdf` (LibreOffice headless). Cover page with document-control table; running header (company · doc ID · title); footer (version · effective date · classification · "Uncontrolled when printed" · Page X of Y); auto TOC; appendices on new pages; forms as bordered fill-in tables with signature lines; letters on RPL letterhead.
- **Tariff (T13):** use the `pdf` skill (reportlab): one tariff sheet per page, sheet header block, issued/effective footer.
- **Datasets:** CSV stays canonical. Optional `xlsx` rendering via the `xlsx` skill with a data-dictionary sheet.
- Strip `<!-- clause -->` / `<!-- sheet -->` comments. Clause IDs never appear in rendered output.
- **Text parity:** a normalized-text comparison must show every Markdown sentence in the rendering. T90 re-runs it.
- Diagrams: Mermaid in Markdown; rendered to PNG for the docx.

**Operations and plan tasks (T16, T18, T19; recommended for T20, T21):**
After the canonical files pass acceptance tests, each operations/plan task (T16, T18, T19; optional for others) produces, under `corpus/docs/<DOC_ID>/render/`:
- **`<DOC_ID>_datasets.xlsx`** via the `xlsx` skill. Tabs: `README` (doc ID, version, extract date, seed, manifest); `Data_Dictionary` (from data/README.md); one tab per CSV (header frozen, filters on, ISO dates as real Excel dates, numeric types preserved, column widths set); `Summary` with live formulas (SUMIFS/COUNTIFS) reproducing every results table in the document; `Checks` tab showing formula-based reconciliations (e.g., Σ meters by technology vs. profile) that evaluate TRUE. Large files (meter registry) may be summarized by group, with a note pointing to the CSV.
- **Charts** via the `dataviz` skill, saved as PNG and SVG in `render/charts/`: T16 — monthly tree-related CI with and without MED; budget 2024 actual vs. 2025 by category; schedule miles by quarter × contractor. T18 — average-accuracy histogram by technology; group X̄ ± σ dot plot; tests by reason. T19 — monthly SAIFI/SAIDI with and without MED; daily SAIDI 2024 with TMED line; CI by cause; Pareto of incidents by CI. Every chart has a source line ("Source: RPL OMS extract 2025-02-10; dataset <file>").
- **`<DOC_ID>_v<version>.docx`** via the `docx` skill, and **`.pdf`** via the `pdf` skill (or docx→pdf conversion). Render: title block and document-control table on page 1; header and footer as in the procedures bullet above; numbered headings; real Word tables with repeated header rows; charts embedded at the section they illustrate with figure numbers; appendices as forms (bordered field tables); clause-ID HTML comments omitted from the rendering but clause numbers retained.
- A render check script asserts that every table value in the docx equals the canonical Markdown/CSV value. Rendered files are never edited by hand.

**Skills and scripts (all tasks):**
- **Skills by deliverable:**
  - procedures, plans and memos: `docx` → PDF
  - tariff: `pdf` (reportlab)
  - fillable forms (EHS-F-101/102/201, CS-, MTR- forms where the task requires them) and pocket cards: `pdf` with AcroForm fields named by field clause ID
  - registers, calendars, schedules and dataset companions: `xlsx` (frozen headers, autofilter, data validation from enumerations, a Lookups sheet, a Change Log sheet)
  - charts in plans and appendices: `dataviz`, rendered to PNG for docx
  - `pptx` is optional and used only for a training module named in a task
  - `frontend-design` is used only for the T90 dashboard (optional)
- **Render script:** each task writes `scripts/render_<DOC_ID>.py`. Rendering is deterministic from the canonical files.
- **Parity:** T90 re-extracts text from each rendering and confirms every canonical sentence and every CSV row is present (files a task allows to be summarized must match group totals instead) (normalized whitespace and punctuation).

### 3.8 Realism & depth rubric

**Part A — Deterministic gates (all must pass; computed by `validate.py`)**

| Gate | Pass condition |
|---|---|
| A1 Length | Body words within the task range |
| A2 Structure | Every required section and appendix present in order; each required section meets the bracketed minimum the task states, otherwise ≥ 2 clauses |
| A3 Clause density | ≥ 1 clause ID per 120 body words; 100% of numbered clauses have IDs |
| A4 Artifacts | §3.6 R3 minimums met (tables, forms, flowchart, checklists, examples, callouts) |
| A5 Triad ratio | (not applied to T13 or T10–T12) ≥ 90% of numbered procedure steps contain actor + timeframe + system/channel/form + record (heuristic tagger; flagged steps go to the realism reviewer) |
| A6 Specificity | ≥ 12 specific tokens per 250 words (§3.6 R4); for T13 count citations, sheet/rule numbers, amounts and defined terms |
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

For each document class the orchestrator keeps `corpus/qa/exemplar_anatomy/<class>.yaml`: the ordered elements observed in real exemplars, from real exemplar documents. The reviewer:
1. Marks each element present / absent / not applicable with the clause ID. B1 is scored from this.
2. **Swap test:** given the exemplar's table of contents (headings only), list every element the exemplar has that the RPL document lacks. Each must be added or justified in `review_realism.json`.
3. **Auditor-question test:** write 10 questions an IURC or IDEM staff member or internal auditor would ask of this document type (e.g., "Who calls IDEM at 02:00 and how do they know the release is reportable?"). The document must answer ≥ 9 with a clause ID. Unanswered questions become fix items.
4. **Discrimination test (optional, recommended for T13, T14, T20):** a blind judge receives one RPL section and one structurally similar real section (real names redacted, values masked) and guesses which is real. Record the result. Three successive confident "RPL is synthetic" verdicts trigger a revision.

---

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
   - A scope entry is either `rule:<title> IAC <article>-<rule>` (the whole rule), `section:<cite>` (one section, with an explicit list of decimals to include), or `range:<cite_from>..<cite_to>` (numeric, inclusive, decimals between bounds included), or `heading:<rule>:<regex>` (sections of a rule whose S1 heading matches the regex, case-insensitive).
   - Never use SQL `LIKE` or string comparison on citations.
   - Apply the same parser to Snapshot-2 rows to find S2 sections new to each scope.

   | Pack | Scope |
   |---|---|
   | T13 | rule:170 IAC 4-1; rule:170 IAC 16-1; 170 IAC 1 sections whose heading matches `tariff|schedule|thirty|30-day|rate|time|computation|filing` |
   | T14 | section:170 IAC 4-1-13; section:170 IAC 4-1-15; section:170 IAC 4-1-16 [16, 16.5, 16.6]; rule:170 IAC 16-1 |
   | T15 | range:170 IAC 4-1-4..170 IAC 4-1-14 |
   | T16 | rule:170 IAC 4-9; rule:170 IAC 16-1; section:170 IAC 4-1-26 |
   | T17 | rule:170 IAC 16-1; section:170 IAC 4-1-13; section:170 IAC 4-1-16 [16, 16.5, 16.6] |
   | T18 | range:170 IAC 4-1-3..170 IAC 4-1-11 |
   | T19 | section:170 IAC 4-1-3; section:170 IAC 4-1-23; section:170 IAC 4-1-24; section:170 IAC 4-9-7 |
   | T20 | rule:327 IAC 2-6.1 |
   | T21 | section:170 IAC 4-1-3; section:170 IAC 4-1-24 |
   | T10, T11 | union of T13–T21 |
   | T12 | union of T13–T21 |

   **Heading-matched additions**: also include any `170 IAC 4-1` section whose S1 heading matches — T14: `disconnect|reconnect|deposit|payment arrangement|medical|bill`; T15: `meter|adjust|estimated`; T17: `complaint|dispute|information to customer` (case-insensitive). Unions (T10–T12) inherit these.

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
    - `absent_topics`: topics named in a task title or required structure (e.g., winter disconnection protection, deposit interest) with no governing section in that pack, so the orchestrator knows §2.7 will apply
    - tasks with zero genuine changes ("cleared" documents), stated prominently

---

## T01 — Company profile

**Outputs:** `corpus/_global/company_profile.yaml`, `corpus/_global/company_fact_sheet.md`, `corpus/_global/render/company_fact_sheet.pdf`.

- `company_profile.yaml`: every field in §1.1 as structured YAML, plus `applicability_attributes` used by Strata's applicability gate:
  ```yaml
  applicability_attributes:
    jurisdiction: IN
    utility_type: electric
    ownership: investor_owned        # not REMC, not municipal
    owns_generating_units: false
    operates_transmission_above_100kv: false
    has_gas_operations: false
    has_water_operations: false
    customer_count_total: 407491
    has_emergency_standby_generators: true
    standby_generator_count: 3
    has_oil_filled_equipment: true
    has_underground_facilities: true
    iurc_jurisdictional: true
    has_fleet_vehicles: true
    fleet_vehicle_count: 640
    has_aboveground_fuel_storage: true
    has_spcc_plans: true
    pcb_equipment_possible: true          # legacy equipment status tracked in WAM
    state_osha_plan: IOSHA
    owns_customer_meters: true
    meters_in_service_total: 409950
    has_vegetation_management_program: true
  ```
- `company_fact_sheet.md`: a one-to-two-page "About Rockridge Power" fact sheet as found in an investor or regulatory filing appendix: overview, service territory, customer and plant statistics (from §1.1), organization summary, key systems. 500–800 words. No regulatory content.
- Render the fact sheet to a 2-page PDF (`docx` skill → PDF): company letterhead, two-column statistics table, territory list. No regulatory content.

## T02 — People directory and org chart

**Outputs:** `corpus/_global/people_directory.csv`, `corpus/_global/org_chart.md`.

- CSV columns: `person_id, name, title, department, reports_to_id, email, phone_ext, location, document_roles` where `document_roles` lists, semicolon-separated, every `DOC_ID:role` from §1.4 (e.g., `RPL-CS-PRO-004:approver`).
- Use exactly the 27 people in §1.3. Locations: assign a service center from §1.1 (most staff in Lafayette; field-facing supervisors may sit elsewhere). Extensions: 4-digit, unique.
- `org_chart.md`: indented hierarchy from P01 down, plus a table "Document ownership matrix" (rows = documents, columns = owner/reviewer/approver names).
- Add columns `oncall_roles` (e.g., `ENV-ONCALL;DCC-ESCALATION`) and `alternate_person_id` for every person with a document role or an on-call role.
- Mobile numbers are not listed for individuals. On-call groups are reached through the DCC (§1.1 numbers) and OMS paging groups (`ENV-ONCALL`, `SAF-ONCALL`, `REG-ONCALL`).
- `org_chart.md` also includes a Mermaid org chart and, in the "Document ownership matrix", each document's default route (owner → reviewer → approver), used by T91 for routing.

## T03 — Document register

**Output:** `corpus/_global/document_register.csv`.

Columns: `doc_id, title, vertical, version, status, effective_date, approved_date, law_as_of, owner_id, reviewer_id, approver_id, review_cycle, next_review_date, supersedes_version, supersedes_date, file_path, regulatory_basis_sections`.

- Values exactly as in §1.4 (`law_as_of` = 2024-12-31 for all). `vertical` per §0.2. `status` = Approved.
- `next_review_date` = effective date + review cycle (for "on change" use effective date + 1 year).
- Also include `render_path`, `record_series_ids` (from §1.6 Table R) and `coverage_dispositions_summary`. `supersedes_version`/`supersedes_date` are taken from the §1.4 Supersedes column.
- `regulatory_basis_sections` and `coverage_dispositions_summary` (e.g., `covered:14;not_applicable:3;considered_no_obligation:2`) are filled by T90 from the basis files.

## T04 — Shared operational master data

**Wave:** 1 · **Grounding:** none · **No regulatory content.** This task never states, computes or implies a reportability flag, regulatory threshold, deadline or limit.
**Purpose:** One canonical physical history of the network and its 2024 outages, so that T16 (vegetation), T18 (meters, circuit foreign key) and T19 (interruption reporting) state the same circuits, outages and reliability figures. Those tasks read these files and must not alter them.
**Inputs:** §1.1, §1.5, §1.6 of this spec; `corpus/_global/reference/ieee1366_med_method.md` if the orchestrator supplied it.
**Outputs (all under `corpus/_global/ops/`):** `substations_master.csv`, `circuits_master.csv`, `daily_saidi_history_2019_2023.csv`, `med_days.csv`, `outage_incidents_base.csv`, `outage_events_base.csv`, `outage_restoration_steps_base.csv`, `reliability_facts.yaml`, `README.md` (data dictionary per §3.5), `_manifest.json`, `scripts/generate_ops_master.py` (seed 2024), `scripts/acceptance_tests.py`.

### Files and fields

- **`substations_master.csv`** — exactly 112 rows: `substation_id (e.g., LAF-012), substation_name (generic, e.g., "Wea Creek"), service_center (LAF|CRW|THT|FRK|DAN), county, primary_kv (12.47|34.5), supply_69kv_line_id, transformer_count, circuit_count`.
- **`circuits_master.csv`** — exactly 528 rows: `circuit_id (<SC>-<sub###>-<n>, e.g., LAF-012-3), substation_id, service_center, county, voltage_kv, phase_type (backbone_3ph_with_laterals|1ph_dominant), oh_miles, ug_miles, customers_on_circuit, customers_residential, customers_nonresidential, critical_facilities, vm_category (backbone|lateral_dominant|urban_ug_dominant), last_trim_year`.
  - Σ`oh_miles` = 14,200 ± 0.1; Σ`ug_miles` = 4,900 ± 0.1; Σ`customers_on_circuit` = 407,491 exactly; Σ residential = 361,480 and Σ non-residential = 46,011 (commercial + industrial + lighting) exactly.
  - Customers allocated to counties in a plausible split (Tippecanoe, Vigo, Hendricks and Boone largest; Benton, Warren, Carroll, Parke and Vermillion smallest). Urban circuits have more customers and more underground; rural circuits have long overhead mileage.
  - `last_trim_year` follows RPL's company-practice cycles (backbone 4 years, laterals 5 years), with a realistic minority (5–10%) one year behind the cycle.
- **`daily_saidi_history_2019_2023.csv`** — 1,826 rows: `date, customers_served, cmi_all, saidi_all_min`. Lognormal body; 2–7 days per year far above the body (storms).
- **`med_days.csv`** — `year, tmed_saidi_min, med_date, daily_saidi_min`. TMED for 2024 computed with the IEEE 1366 2.5-beta method from the 2019–2023 history (natural log of daily SAIDI excluding zero days; α = mean, β = standard deviation; TMED = e^(α + 2.5β)). 2024 major event days are the days whose daily SAIDI exceeds TMED: **3–8 days**, including a **March 2024 wind storm** (T19 uses it as its worked example).
- **`outage_incidents_base.csv`** — one row per incident (a storm aggregates many events): `incident_id, incident_type (single_event|storm|planned), first_start_ts, utc_offset, utility_aware_ts, peak_customers_out, peak_ts, total_customers_affected, counties_affected, municipalities_affected, critical_facilities_affected, restored_ts, etr_first_ts, primary_cause_category`.
- **`outage_events_base.csv`** — one row per sustained outage record or device operation, 2024-01-01 to 2025-01-31, 9,500–12,000 rows: `event_id, incident_id, start_ts, end_ts, utc_offset, duration_min, customers_affected, customer_minutes, restoration_steps, circuit_id, substation_id, service_center, county, municipality (or 'unincorporated'), device_type (substation_breaker|feeder_breaker|recloser|sectionalizer|fuse|transformer|service|69kv_line), device_id, outage_level (supply|substation|feeder|lateral|transformer|service), cause_category, cause_code, tree_location (inside_row|outside_row|unknown|n/a), weather_code, intentional (Y|N), critical_facilities_affected (int), detection_source (ami_last_gasp|scada|customer_call|field), med_flag (Y|N), med_date, notes`.
- **`outage_restoration_steps_base.csv`** — `event_id, step_no, step_ts, customers_restored, customers_remaining`. Σ`customers_restored` per event = `customers_affected`.
- **`reliability_facts.yaml`** — monthly customers-served denominators for 2024 (back-cast from the §1.1 year-end total at ≈0.9%/yr growth); 2024 monthly and annual CI, CMI, SAIFI, SAIDI and CAIDI with and without MED and excluding planned; TMED; MED dates; vegetation CI/CMI/SAIFI/SAIDI contributions for 2022–2024 (2022 and 2023 as annual summaries) with the inside/outside-right-of-way split.

### Generation rules (company practice; benchmark-checked)

- **Cause taxonomy** (canonical; T16 and T19 use exactly this). `cause_category` → `cause_code`:
  - `vegetation` → `tree_inside_row_growth`, `tree_inside_row_failure`, `tree_outside_row_fallin`, `tree_unknown_location`
  - `weather` → `wind`, `lightning`, `ice_snow`, `flood`, `heat`
  - `equipment` → `oh_conductor`, `ug_cable`, `transformer`, `cutout_fuse`, `arrester`, `insulator`, `pole`, `connector`, `recloser_breaker`, `substation_equipment`
  - `animal` → `squirrel`, `bird`, `snake_raccoon_other`
  - `public` → `vehicle`, `dig_in`, `vandalism_theft`, `fire`, `customer_equipment`, `third_party_contact`
  - `power_supply` → `69kv_line`, `transmission_supply_miso`, `substation_supply`
  - `operational` → `overload`, `switching_error`, `protection_miscoordination`
  - `planned` → `maintenance`, `construction`, `emergency_switching_for_safety`
  - `unknown` → `unknown_patrolled_no_cause`
  - 2024 shares of sustained outage records, ex-MED: vegetation 20–27%, equipment 25–33%, animal 12–18%, weather 8–14%, public 5–9%, power supply 1–3%, operational 1–3%, planned 5–10%, unknown 6–12%. MED days skew strongly to vegetation and weather.
- **Size (heavy tail):** lognormal/Pareto mixture by `outage_level`. Medians: transformer/service 1–8 customers; fuse/lateral 15–60; feeder 300–2,500; substation/supply 2,000–15,000. `customers_affected` ≤ `customers_on_circuit` for feeder level and below; substation and supply events ≤ the sum over the circuits served.
- **Duration:** lognormal by level and cause, median 75–140 minutes ex-MED; MED-day medians 3–10× longer; 0.5–1.5% of events exceed 24 hours.
- **Seasonality:** storm-driven peaks April–August; an optional winter ice event. Thunderstorm outages peak 14:00–22:00. Animal outages peak in spring and fall.
- **Customer minutes** = Σ over restoration steps (customers restored × minutes out), not customers × duration.
- **Targets (2024):** ex-MED SAIFI 1.05–1.15, SAIDI 130–150 min, CAIDI 115–140 min; with-MED SAIDI 220–350 min; vegetation share of ex-MED SAIFI 13–30% (Indiana IOUs report 0.71–1.37 SAIFI and 76–178 min SAIDI ex-MED).
- **Imperfection (§3.6a):** some causes unknown or re-coded, a few events with notes on late cause assignment, ordinary data noise. No regulatory fields.

### Acceptance tests (`scripts/acceptance_tests.py`; all must pass)

1. Row counts and the exact sums above (miles, customers, residential/non-residential split).
2. Referential integrity: every event's `circuit_id`/`substation_id` exists; every event has an `incident_id` that exists; every event has ≥ 1 restoration step and steps sum to `customers_affected`.
3. `customer_minutes` recomputes from steps exactly.
4. TMED and MED dates recompute from the history; 3–8 MED days in 2024 including one in March.
5. `reliability_facts.yaml` indices recompute from the events file within 0.001; targets met.
6. No column name or value refers to reportability, IURC reports or regulatory thresholds.

---

## T13 — Tariff for Electric Service, IURC No. 12: General Rules and Regulations

**Doc ID:** RPL-TAR-GRR-012 · **Vertical:** Policy & Governance · **Wave:** 2 · **Grounding:** `corpus/grounding/T13.json`
**Owner/Reviewer/Approver:** Aisha Thompson (P11) / Robert Haskins (P10) / Jonathan Pierce (P03)
**Issuing officer printed on every sheet:** Thomas Whitfield, Vice President, Regulatory & Government Affairs (P07). Owner, reviewer and approver appear only in front matter and the basis file, never on the sheets.
**Outputs:**
- `corpus/docs/RPL-TAR-GRR-012/RPL-TAR-GRR-012_v2024-06-01.md` (canonical, clause-ID-bearing)
- `corpus/docs/RPL-TAR-GRR-012/RPL-TAR-GRR-012.basis.json`
- `corpus/docs/RPL-TAR-GRR-012/render/RPL-TAR-GRR-012_v2024-06-01.pdf` (rendered tariff, see "Rendering")
- `corpus/docs/RPL-TAR-GRR-012/scripts/render_RPL-TAR-GRR-012.py`

### What this document is in the real world

The binding terms of service that an Indiana investor-owned electric utility files with the IURC and the IURC approves. It is a volume of numbered **tariff sheets**. Sheets are revised one at a time; each revised sheet cancels the prior revision of the same sheet number. The General Rules and Regulations (GRR) occupy the front of the volume; rate schedules and riders follow on later sheets. The text is contractual and third-person ("The Company shall…", "The Customer may…"). It contains no internal process detail: no system names, queues or staff titles other than the issuing officer. Indiana tariffs cite IURC rules inline at sub-rule level, e.g. "…in accordance with 170 IAC 4-1-9" or "Commission Rule 16 [170 IAC 4-1-16]". Copy that pattern using the pack's citation format.

**Study for sheet layout, rule order and tone ONLY (never copy text; never take any number, period, percentage, temperature, date or condition from them):**
- NIPSCO GRR (15 rules, 100 definitions, sheet header, inline 170 IAC cites): https://www.nipsco.com/docs/librariesprovider11/rates-and-tariffs/electric-rates/2025-to-current/general-rules-and-regulations.pdf
- AES Indiana Rules & Regulations (charges schedule by time and location; AMI opt-out; "Superseding" footer): https://www.aesindiana.com/sites/default/files/2021-02/Rules_and_Regulations_Effective_11-04-2020.pdf
- AES Indiana Table of Contents sheet: https://www.aesindiana.com/sites/default/files/2021-05/Table-of-Contents-50409-Effective-04-07-21.pdf
- I&M Indiana tariff book ("Issued by" / Cause No. header; Service, Reconnect and Trip Charges schedule): https://www.indianamichiganpower.com/lib/docs/ratesandtariffs/Indiana/IMINTB2004-30-2025.pdf
- CenterPoint Indiana South ("Appendix D – Other Charges"; rule list): https://www.centerpointenergy.com/en-us/Documents/RatesandTariffs/Indiana/Southwest/in-south-electric-tariff.pdf

> **Caution — later-edition values.** These references postdate or differ from the 2024-12-31 rule text in your pack. Their notice periods, deposit criteria, late-payment formulas, accuracy limits, test frequencies, temperature limits and look-back periods are **not** your values. If you find yourself typing a number you remember from them, stop and find it in the pack. If it is not in the pack, it does not go in a regulatory clause.

### Canonical sheet map (use exactly; T14, T15, T17, T10 and T12 reference these numbers)

| Sheet No(s). | Content | Revision level in force | Effective | Approved under |
|---|---|---|---|---|
| 1 | Title sheet | Second Revised (cancels First Revised) | 2024-06-01 | Cause No. 99012 |
| 2–3 | Index of Sheets (all GRR sheets, then every rate schedule and rider by code, name and sheet range) | Second Revised | 2024-06-01 | Cause No. 99012 |
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

Use the **`pdf` skill** (reportlab), deterministic, via `scripts/render_RPL-TAR-GRR-012.py` reading the canonical Markdown:
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
4. **Value ledger:** every number, percentage, time, day count and dollar amount in the document is in the basis file's `value_ledger` with a source from the §3.4 enum. `company_practice` and `worked_example` values appear only in sub-rules labeled company practice (e.g., Rule 6 allowance method, Rule 4 ID list) and never in a cited sentence. Sheet-map facts use `company_practice` with ref "T13 sheet map".
5. No number, date or temperature for a statutory protection appears unless it is in the pack.
6. The PDF renders with one sheet per page; a text-parity check (normalized PDF text contains every Markdown sentence) passes.
7. Word count and citation count meet the minimums.

---

## T14 — Disconnection, Reconnection & Winter Protection Procedure

**Doc ID:** RPL-CS-PRO-004 · **Vertical:** Policy & Governance · **Wave:** 2 · **Grounding:** `corpus/grounding/T14.json`
**Owner/Reviewer/Approver:** Jasmine Carter (P15) / Karen Mitchell (P13) / Jonathan Pierce (P03)
**Supersedes:** 5.0 (2024-01-15)
**Outputs:**
- `corpus/docs/RPL-CS-PRO-004/RPL-CS-PRO-004_v5.1.md` (canonical)
- `corpus/docs/RPL-CS-PRO-004/RPL-CS-PRO-004.basis.json`
- `corpus/docs/RPL-CS-PRO-004/render/RPL-CS-PRO-004_v5.1.docx` and `.pdf`
- `corpus/docs/RPL-CS-PRO-004/scripts/render_RPL-CS-PRO-004.py`

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
- Every step in §12 names an actor, a timeframe, a system action and a record (§3.6 R2).
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

---

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

1. **Purpose** · 2. **Scope** [≥4: residential and non-residential; AMI, AMR and electromechanical meters (fleet per §1.1); demand meters; excludes periodic and sample testing under RPL-MTR-PGM-001, cross-referenced] · 3. **Definitions** [≥15: as-found, as-left, full load, light load, power factor test point, average accuracy (the pack's method if defined), creep, non-registering, fast/slow meter, billing error, back-bill, refund, written request, commission-supervised test, meter seal; pack-defined terms carry citations] · 4. **Regulatory basis** (table) · 5. **Roles** (table: P18, P14, P19, P20; Contact Center agents; Billing Adjustment Analysts; Meter Technicians; Customer Advocacy P17)
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
- Banned phrasing: §3.6 R5, plus "follow applicable regulations" and "as required by law" without a citation.

### Rendering (required)

Per §3.7 (procedures): `docx` skill → PDF via LibreOffice headless; cover page with document-control table; auto TOC; each appendix on a new page; forms as bordered fill-in tables with signature/date lines; letters on RPL letterhead (§1.1); clause-ID comments stripped (header text "RPL-CS-PRO-007 | Meter Test Request & Billing Adjustment Procedure"; footer "Version 3.0 | Effective 2025-02-17 | Internal | Uncontrolled when printed | Page X of Y"). Forms use bordered fill-in tables. The test report letter has an as-found results grid. Expected length: 20–30 pages.

### Self-check (in addition to §2.6 and §3.8)

1. Every condition in the pack's meter-test and adjustment sections appears as a decision-table row or §13 clause, with citation.
2. `worked_examples.py` re-runs and reproduces every number in §15. Its `params` match the basis file. The result is recorded in the basis file under `worked_examples`.
3. No accuracy limit, weighting, look-back period, test frequency or fee condition appears that is not in the pack. Fee amounts match §1.6 Table F (or the pack, if it sets them — reported).
4. Form numbers, CIS codes and tariff sheet references match §1.6 (Tariff references and catalogs).
5. Render text parity passes.

---

## T16 — Vegetation Management Plan 2025

**Doc ID:** RPL-DO-PLN-002 · **Vertical:** Policy & Governance · **Wave:** 2 · **Grounding:** `corpus/grounding/T16.json`
**Owner/Reviewer/Approver:** Rachel Stein (P22) / Patrick O'Neill (P21) / Jonathan Pierce (P03)
**Inputs (read-only, from T04):** `corpus/_global/ops/circuits_master.csv`, `corpus/_global/ops/substations_master.csv`, `corpus/_global/ops/outage_events_base.csv`, `corpus/_global/ops/med_days.csv`, `corpus/_global/ops/reliability_facts.yaml`
**Outputs:**
- `corpus/docs/RPL-DO-PLN-002/RPL-DO-PLN-002_v2025.1.md`, `RPL-DO-PLN-002.basis.json`
- `data/vm_circuit_schedule_2025.csv`, `data/vm_work_completed_2024.csv`, `data/vm_tree_outages_2024.csv`, `data/vm_budget_2024_2025.csv`, `data/vm_customer_contacts_2024.csv`, `data/README.md`, `data/_manifest.json`
- `scripts/generate_vm_data.py` (seed 2024), `scripts/acceptance_tests.py`
- `render/RPL-DO-PLN-002_v2025.1.docx`, `render/RPL-DO-PLN-002_v2025.1.pdf`, `render/RPL-DO-PLN-002_datasets.xlsx`, `render/charts/*.png` (see §3.7)

### What this document is in the real world

The annual plan an Indiana investor-owned electric utility maintains under the IURC's vegetation management rule. It sets the standards contractors follow, trim cycles, customer notification and consent, easement documentation, debris handling, dispute resolution, customer education, budget and reporting to the commission. Field supervisors, contractor general foremen, work planners and the contact center all work from it. Real Indiana IOU filings pair a short annual report with an attached program document. The annual report covers prior-year budget vs. actual, complaints and how they were handled, and tree-related vs. all outages with and without major event days. The program document covers definitions, laws, property access rights, work-quality standards, clearance tables, hazard trees, herbicide, notification steps, debris, contractor requirements and QA. RPL's plan combines both: the "2024 Program Results" part plays the role of the annual report.

**Study for structure, table design and magnitudes (do not copy text; never take regulatory values from these):**
- Duke Energy Indiana, 2024 Vegetation Management Report (IURC, filed 2025-03-28) — distribution + transmission program layout, budget/actual, Tree SAIFI share
- AES Indiana, 2024 Vegetation Management Annual Report (filed 2025-03-31) — clearance table by line type, inquiry categories, 4-step notification sequence, staffing
- CenterPoint Energy Indiana South, 2024 Report and Vegetation Management Plan VEC-047 — plan section order, definitions table, clearance by species × direction
- NIPSCO, 2024 Annual Report compliance filing — budget categories, tree vs. total outages with/without MED, contractor specification exhibits
- Indiana Michigan Power, 2024 Annual VM Report — capital vs. O&M × distribution/transmission budget split
- Eversource NH, 2025 Vegetation Management Annual Filing (NH PUC Docket 19-057) — program-by-program budget, miles and $/mile
URLs:
- Duke Energy Indiana 2024 VM Report: https://iurc.portal.in.gov/_entity/sharepointdocumentlocation/d9117e76-f40b-f011-bae3-001dd803db57/bb9c6bba-fd52-45ad-8e64-a444aef13c39?file=43663_DEI_Submission%20of%202024%20Veg%20Management%20Report_032825.pdf
- AES Indiana 2024 VM Annual Report: https://iurc.portal.in.gov/_entity/sharepointdocumentlocation/2419d113-f60e-f011-bae2-001dd80b1717/bb9c6bba-fd52-45ad-8e64-a444aef13c39?file=43663_AES%20IN_Submission%20of%20Vegetation%20Management%20Annual%20Report_033125.pdf
- CenterPoint Indiana South 2024 VM Report and Plan: https://iurc.portal.in.gov/_entity/sharepointdocumentlocation/c668f043-f60e-f011-bae2-001dd80b1717/bb9c6bba-fd52-45ad-8e64-a444aef13c39?file=Cause%20No.%2043663_CEI%20South_2024%20Vegetation%20Managment%20Report%20and%20Plan_033125.pdf
- NIPSCO 2024 VM Annual Report: https://iurc.portal.in.gov/_entity/sharepointdocumentlocation/e1f90252-6e0e-f011-bae2-001dd80846ac/bb9c6bba-fd52-45ad-8e64-a444aef13c39?file=43663_NIPSCO_Compliance%20Filing%20-%20Annual%20Report_03312025.pdf
- I&M 2024 VM Annual Report: https://iurc.portal.in.gov/_entity/sharepointdocumentlocation/ee4365fe-4a0e-f011-bae2-001dd803db57/bb9c6bba-fd52-45ad-8e64-a444aef13c39?file=43663_IndMich_Submission%20of%20Annual%20Vegetation%20Management%20Report_033125.pdf
- Eversource NH 2025 VM Annual Filing: https://puc.nh.gov/Regulatory/Docketbk/2019/19-057/LETTERS-MEMOS-TARIFFS/19-057-2024-11-15-EVERSOURCE-2025-VEGETATION-MANAGEMENT-ANNUAL-FILING.PDF

### Required structure (minimum depth in brackets)

1. **Plan at a glance** — one table: circuits scheduled, OH miles scheduled, cycle by category, 2025 budget by category, contractors, key dates. [1 table]
2. **Program goals and strategy** — reliability, safety, customer-relations and cost objectives; prioritization logic (cycle due, tree CI history, worst-performing circuits); company practice. [≥250 words]
3. **Applicability** — one clause citing the pack's applicability section.
4. **Definitions** — identical meaning to the pack; add company terms (brush vs. tree by DBH, side/under/through/V-trim, directional pruning, hazard tree, hot spot, mid-cycle, IVM, work planner, lead sheet) labeled company practice. [≥20 terms, table]
5. **Regulatory basis** — table: citation · heading · governs §§. Also list industry standards and out-of-scope references (OSHA 29 CFR 1910.269, NESC, EPA/Office of Indiana State Chemist pesticide rules, NERC FAC-003 "not applicable — RPL owns no Bulk Electric System transmission facilities") as `out_of_scope_reference` clauses.
6. **Roles & responsibilities** — P22, P21, P17, the DCC (P23 for storm work), Contractor A/B general foremen, RPL work planners/foresters (titles only), contact center. [RACI table]
7. **Pruning and clearance standards** — the industry standards the pack requires, named exactly as the pack does. RPL clearance specification table (company practice) by voltage class (69 kV, 34.5 kV, 12.47 kV three-phase, 12.47 kV single-phase, secondary/service) × direction (side, under, overhang) × species growth class (fast/slow), plus a "years of growth" basis. How locality, facility and tree health are considered (as in the pack). [clearance table ≥10 rows]
8. **Trim cycles** — cycle by circuit category (company choice: e.g., three-phase backbone 4 yr, single-phase laterals 5 yr, 69 kV ROW floor/side 5 yr), reasoning, and how cycle affects clearance and appearance (as the pack requires it to be explained). Include a table reconciling cycle to annual miles: `category · OH miles · cycle · miles/yr`. [2 tables]
9. **Work planning and execution** — pre-planning, lead sheets, circuit patrol, work packets, hours of work (company practice), traffic control, sensitive areas, coordination with communications attachers.
10. **Legal authority before work** — easements, rights-of-way, statutory authority, consent; the customer's right to request documentation and RPL's response time (per the pack). App-B letter.
11. **Customer notification for routine work** — step sequence (company practice: e.g., letter → door hanger → day-of contact), with timing per the pack, method, content checklist (one clause per required element), estimated-day follow-up timing, and exceptions (each its own clause). [sequence table + checklist]
12. **Notice for changes in line voltage or expansion of the work area** (if in the pack).
13. **Tree removal and consent** — when removal requires owner consent; non-agreement path (per the pack); stump treatment practice; tree replacement program (company practice).
14. **Hazard tree program** — identification (patrols, reports, LiDAR/imagery if used — generic), risk tiers with RPL response targets labeled `Internal performance target:`, outside-ROW trees and owner engagement.
15. **Integrated vegetation management / herbicide and brush** — methods, EPA-registered products (generic), licensed applicators (out-of-scope reference), sensitive-area exclusions, efficacy audits (company practice).
16. **Debris handling** — time limit and exceptions (per the pack); routine vs. storm debris; wood/chip requests.
17. **Emergency and storm vegetation work** — definition (per the pack), DCC dispatch, rules that still apply, post-storm follow-up.
18. **69 kV subtransmission ROW program** — ROW widths (company practice), floor management, inspection frequency (company practice), access.
19. **Contractor requirements and quality assurance** — qualifications (line-clearance qualified, ISA Certified Arborist on staff), crew audits, post-work audit sample rate and pass criteria (company practice), invoicing controls, KPIs. [audit KPI table]
20. **Disputes** — before and after work; escalation to a second authorized representative; information to give the customer when unresolved (per the pack, including any cross-reference it makes). App-C form.
21. **Customer education plan** — each topic the pack requires, with channel, frequency and owner. [table: topic · channel · frequency · owner · clause]
22. **Reporting to the IURC** — annual tree-related outage report due date and content elements (each a clause), and the plan-change filing trigger (per the pack). Map each content element to the dataset or table that supplies it.
23. **2024 program results (preliminary, data extracted 2025-01-15)** — tables from the datasets: miles completed vs. plan, budget vs. actual with variance explanations, tree-related vs. all outages with and without MED, inside vs. outside ROW, customer contacts and complaints by category and outcome. [≥4 tables, ≥2 charts]
24. **2025 budget** — total **$41.6 million**, by category × O&M/capital (see dataset spec), with $/mile and year-over-year variance. [1 table]
25. **Performance metrics** — tree-related CI, CMI, SAIFI and SAIDI contributions, 2022–2024, with and without MED, from `reliability_facts.yaml`. Top 10 circuits by tree CI 2024 and their 2025 treatment. [2 tables, 1 chart]
26. Records & retention · 27. Training (contractor orientation, contact-center module) · 28. Related documents (RPL-DCC-PRO-003, RPL-CS-PRO-011, RPL-LEG-RRS-001, RPL-TAR-GRR-012) · 29. Revision history · 30. Approval block

**Appendices:**
- App-A: Routine vegetation work notice `VM-F-004` — letter version and door-hanger version; every required content element a numbered field (`App-A.F1…`)
- App-B: Easement documentation request response letter
- App-C: Vegetation dispute log form (fields: log ID, date, account/premise, circuit, contractor, issue category, first representative, second representative, resolution, IURC info provided Y/N and date)
- App-D: 2025 circuit schedule summary (top 20 circuits by scheduled OH miles, from the dataset; columns as dataset)
- App-E: Clearance specification diagrams (described in text plus a simple table; rendered as a figure in the docx/pdf)
- App-F: Data dictionary (or reference to `data/README.md`)

### Datasets (deterministic script, seed 2024)

All circuit, substation and county values come from `circuits_master.csv` (T04). Do not create circuits.

**`vm_circuit_schedule_2025.csv`** — one row per circuit scheduled for 2025 routine cycle work.
| Field | Type | Spec |
|---|---|---|
| `circuit_id` | str | FK → circuits_master |
| `substation_id`, `service_center`, `county`, `voltage_kv`, `phase_type` | str | copied from master (no divergence) |
| `vm_category` | enum | copied from master (`backbone` \| `lateral_dominant` \| `urban_ug_dominant`); 69 kV ROW work is scheduled in §18 by `supply_69kv_line_id`, not as circuit rows |
| `cycle_years` | int | per §8 category (company practice) |
| `last_trim_year` | int | normally `2025 − cycle_years`; copied from master (T04 sets 5–10% one year behind); early rows ≤ 3% with a `schedule_note` (deferrals and storm re-sequencing), each with a `schedule_note` |
| `scheduled_quarter_2025` | enum | Q1–Q4. Leaf-off Q1/Q4 weighted for laterals; distribution roughly 22/28/28/22% |
| `overhead_miles` | float(1) | from master |
| `contractor` | enum | Contractor A \| Contractor B (≈55/45 by miles; contiguous by service center) |
| `est_cost_usd` | int | `overhead_miles × unit_cost × density_factor`. Unit cost per company practice (§24); density factor lognormal, median 1.0, σ≈0.35, clipped 0.4–3.0 (urban/wooded circuits cost more) |
| `planned_start_date`, `planned_end_date` | date | inside the scheduled quarter; duration ≈ miles / (0.6–1.2 mi per crew-day × crews) |
| `notice_batch_id` | str | `VMN-2025-###`; one or more per circuit |
| `notice_letter_date`, `door_hanger_start_date` | date | satisfy the pack's notice timing for every row, with the margin distribution in §3.6a |
| `customers_on_circuit` | int | from master |
| `tree_ci_2024` | int | from the T04 outage base (vegetation causes) |
| `priority_rank` | int | 1 = highest; consistent with §2 prioritization logic |
| `schedule_note` | str | blank or short reason |

Rows ≈ 528 / weighted cycle (expect 115–140). Sum of `overhead_miles` = §8 "miles/yr" ± 2%. Sum of `est_cost_usd` = the 2025 "routine cycle — distribution" budget line ± 0.5%.

**`vm_work_completed_2024.csv`** — circuits completed in 2024 (planned vs. actual miles, completion date, contractor, actual cost, audit pass %). Every row has `last_trim_year = 2024` in a master-consistent sense: no circuit appears in both 2024 completed and the 2025 schedule unless it is a flagged hot spot/mid-cycle row.

**`vm_tree_outages_2024.csv`** — **derived, not generated.** Aggregate T04 `outage_events_base.csv` for 2024 rows where `cause_category = vegetation`:
`month, tree_location (inside_row|outside_row|unknown), med_flag (Y|N), sustained_outages, customer_interruptions, customer_minutes, tree_saifi_contribution, tree_saidi_contribution, all_cause_outages, all_cause_ci, tree_share_of_saifi_pct`. Denominator = the customers-served figure in `reliability_facts.yaml`.

**`vm_budget_2024_2025.csv`** — `line_id, category, cost_type (O&M|capital), system (distribution|subtransmission_69kv), budget_2024_usd, actual_2024_usd, variance_usd, variance_note, budget_2025_usd, unit, units_2025, unit_cost_2025`.
2025 total = **41,600,000** exactly. Indicative split (company practice; adjust ±15% per line but keep total):
| Category | ~2025 $M | Units |
|---|---|---|
| Routine cycle trimming — distribution | 27.9 | ~3,300–3,500 OH mi |
| Hazard tree removal (incl. outside-ROW) | 6.2 | trees |
| Herbicide / brush / mowing (IVM) | 2.6 | acres |
| Mid-cycle, hot spot and customer-request work | 2.0 | work orders |
| Storm/emergency vegetation (non-MED) | 1.5 | — |
| 69 kV subtransmission ROW | 0.9 | ROW mi |
| Contractor oversight, work planning and QA/QC audits | 0.4 | audits |
| Customer education and communications | 0.1 | — |
2024 actual within −10% to +12% of 2024 budget overall (benchmarks: Duke −9.5%, AES +3%, NIPSCO +15.5%); each line variance ≥5% has a note.

**`vm_customer_contacts_2024.csv`** — one row per logged contact: `contact_id, received_date, channel, circuit_id, category (notice_question|debris|property_damage|refusal_of_work|tree_health|storm_debris|customer_request_trim|easement_documentation_request|removal_dispute|other), escalated_to_second_rep (Y|N), iurc_cad_referral (Y|N), resolution, closed_date, days_to_close, iurc_info_provided (Y|N)`. Volume 300–700 contacts; formal disputes 10–40; IURC CAD referrals 2–15 (Indiana benchmarks: 2–18). Every easement-documentation request is answered within the pack's response time, and every unresolved dispute row shows the customer information required by the pack.

### Benchmarks (form and magnitude only; record each used source in basis `sources`)
| Metric | Range | Source |
|---|---|---|
| Distribution cycle | 4–5 yr | AES IN, Duke IN, Eversource NH |
| Tree share of SAIFI (ex-MED) | 13–30% | I&M, Duke IN, AES IN, CNP IN-South, NIPSCO |
| Routine trim $/OH mile | ~$7.5k–$16k | Eversource NH 2025, Duke IN 2024 (implied) |
| VM complaints formally escalated / IURC referrals | 2–18 per utility-year | Indiana 2024 reports |

### Specific instructions
- All clearance distances, cycle lengths, response targets, audit rates and unit costs are company practice. They carry no citation unless the pack states them.
- 2024 figures are "preliminary, data extracted 2025-01-15" and must equal the T04-derived values.
- Do not name real contractors, real herbicide brands or real utilities.

### Acceptance tests (`scripts/acceptance_tests.py`; all must pass, results appended to `data/README.md`)
1. Every `circuit_id` in every VM dataset exists in `circuits_master.csv`, with identical substation, county, voltage, phase and miles.
2. Schedule row count is within 528/weighted-cycle ± 10%. Σ`overhead_miles` reconciles to §8 ± 2%. Σ`est_cost_usd` reconciles to the routine budget line ± 0.5%.
3. `vm_budget_2024_2025.csv` 2025 total = 41,600,000. Every number in doc §24 and §1 equals the CSV.
4. `vm_tree_outages_2024.csv` recomputes exactly from `outage_events_base.csv`. Doc §23/§25 tree SAIFI/SAIDI equal `reliability_facts.yaml`.
5. Every notice date satisfies the pack's timing (`params` dict). At least 10% of rows have margins in the lowest 20% of the allowable window (§3.6a margin rule). None are non-compliant.
6. Every App-A field maps to a clause ID in basis. Every pack-required notice element appears in both §11 and App-A.
7. The App-D table equals the top-20 circuits by miles in the dataset.
8. The rendered docx/pdf/xlsx are regenerated from canonical md/csv, and table values match (§3.7).

### Length
6,500–9,500 words plus datasets (real Indiana plan documents run 17–29 pages).

---

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
7. **Protection during a dispute** [≥6]: what collection/disconnection activity must stop and for how long; undisputed amounts the customer must pay (per the pack); CIS holds `HDSP` (RPL-level dispute) and `HIURC` (IURC complaint open), who places and who releases them; coordination with RPL-CS-PRO-004 §14.
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
- Banned phrasing: §3.6 R5, plus "follow applicable regulations", "promptly" or "as soon as possible" used in place of a stated timeframe.

### Rendering (required)

Per §3.7 (procedures): `docx` skill → PDF via LibreOffice headless; cover page with document-control table; auto TOC; each appendix on a new page; forms as bordered fill-in tables with signature/date lines; letters on RPL letterhead (§1.1); clause-ID comments stripped (header "RPL-CS-PRO-011 | Customer Complaint & Dispute Resolution Procedure"; footer "Version 2.3 | Effective 2025-03-03 | Internal | Uncontrolled when printed | Page X of Y"). Include a one-page process flow (intake → classify → hold → investigate → determine → notify → close/escalate → IURC referral loop). Expected length: 18–26 pages.

### Self-check (in addition to §2.6 and §3.8)

1. Every regulatory deadline and required content element in the pack appears in the body and in App-C, with citation.
2. Every internal target is labeled, and none is longer than the pack deadline next to it.
3. IURC contact details exactly match §1.6 Table C. Hold codes, form numbers and category codes match §1.6.
4. No response time appears as regulatory unless it is in the pack.
5. Render text parity passes.

---

## T18 — Meter Testing Program Plan (with datasets)

**Doc ID:** RPL-MTR-PGM-001 · **Vertical:** Operations & Processes · **Wave:** 2 · **Grounding:** `corpus/grounding/T18.json`
**Owner/Reviewer/Approver:** Gregory Walsh (P19) / Angela Ruiz (P20) / Michael Brennan (P16)
**Outputs:** `corpus/docs/RPL-MTR-PGM-001/RPL-MTR-PGM-001_v6.0.md`, `RPL-MTR-PGM-001.basis.json`, every dataset listed under "Datasets" below (in `data/`), `data/README.md`, `data/_manifest.json`, `scripts/generate_meter_data.py` (seed 2024), `scripts/acceptance_tests.py`, and the §3.7 renders in `render/`.
**Inputs (read-only):** `corpus/_global/ops/circuits_master.csv` (T04; circuit foreign key for the meter registry); `corpus/_global/reference/sampling_table.json` if supplied.

### What this document is in the real world

The metering department's program document describing how the utility keeps its meter population accurate and documented: meter records, new-meter acceptance testing, in-service testing (periodic and/or statistical sampling, as the rule allows), accuracy limits, test equipment and reference/portable standards with calibration traceability, customer-requested tests, and annual program reporting. It is backed by the meter population and test-result data the regulator can audit.

**Study for structure, tables and magnitudes (do not copy text; never take regulatory values from these):**
- Entergy Arkansas Meter Test Plan (tariff-schedule form of a filed program)
- Grayson RECC sample-testing plan application, KY PSC Case 2009-00103 (group table; lot formation by manufacturer/type; escalation table)
- Kentucky Power 2023 Meter Test Reports (annual results table: group · in-service · sample · X̄ · σ · pass/fail)
- Xcel Energy (NSP) 2023 Meter Testing Results, ND PSC PU-24-152 (tested/within/slow/fast summary; lot detail)
- Eversource NH 2023 Meter Testing Program Annual Report (lot σ commentary)
- Tescometering: In-Service/Statistical Test Programs comparison; ECNE 2016 Meter Testing Programs (program types, traceability chain)
URLs:
- Entergy Arkansas Meter Test Plan: https://www.entergyarkansas.com/wp-content/uploads/2024/11/eal_ps12_mtp.pdf
- Grayson RECC sample testing application (KY PSC 2009-00103): https://psc.ky.gov/PSCSCF/2009%20cases/2009-00103/20090305_grayson_applicaton_.PDF
- Kentucky Power 2023 Meter Test Reports: https://psc.ky.gov/PSCSCF/Post%20Case%20Referenced%20Correspondence/2005%20cases/2005-00276/20240314_Kentucky%20Power%20Company%202023%20Meter%20Test%20Reports.pdf
- Xcel/NSP 2023 Meter Testing Results (ND PSC PU-24-152): https://www.psc.nd.gov/webdocs/case/24-0152/001-010.pdf
- Eversource NH Meter Testing Program 2023 Annual Report: https://puc.nh.gov/regulatory/Docketbk/2018/18-162/LETTERS-MEMOS-TARIFFS/18-162_2023_12-28_EVERSOURCE_METER_TESTING_PROGRAM_2023_ANNUAL_RPT.PDF
- Tescometering, In-Service/Statistical Test Programs: https://www.tescometering.com/wp-content/uploads/2024/03/Comparison-of-In-ServiceStatistical-Test-Programs-6-30-04.pdf
- Tescometering, ECNE 2016 Meter Testing Programs: https://www.tescometering.com/wp-content/uploads/2024/04/ECNE-2016_Meter-Testing-Programs.pdf

### Required structure (minimum depth in brackets)

1. Purpose · 2. Scope (all 409,950 meters by technology, form and service type — table) · 3. Definitions (as-found, as-left, full load, light load, power-factor test, average/weighted accuracy, homogeneous group, lot, sample, AQL if used, test board, reference/working/portable standard — pack definitions verbatim in meaning) [≥18 terms] · 4. Regulatory basis (plus industry standards: ANSI C12.1, C12.20; sampling standard only as named by the pack or labeled company practice) · 5. Organization & roles (P20, P19, P18, meter technicians, AMI operations, records)
6. **Meter records** — the record kept for each meter from purchase to retirement (table of record fields); systems of record (WAM + AMI HES + CIS); retention (per the pack).
7. **Meter location and accessibility standards** (per the pack).
8. **New and repaired meter acceptance** — shipment lot formation, manufacturer test data review, RPL acceptance sampling (company practice unless the pack states it), lot rejection and return; repaired-meter testing (per the pack). [table: meter class × acceptance method × sample basis]
9. **In-service testing program**
   9.1 Group formation rules (manufacturer · model family · technology · form · service type · install-year band); minimum and maximum group size.
   9.2 Method by group (periodic or sampling — **only methods the pack permits**). [table: group family · method · interval or sample basis · clause]
   9.3 Sample size determination — source table identified (see "Sampling reference" below); random selection procedure (seeded, documented, auditable).
   9.4 Acceptance determination and actions on a failed group — expanded sample, accelerated testing, group replacement (company practice where the pack is silent). [decision table]
   9.5 Periodic schedule management — due-date computation, WAM work-order generation, field vs. shop.
10. **Accuracy limits and average-accuracy method** — exactly as in the pack; one table per meter technology and service type; worked calculation example.
11. **Test equipment and standards** — traceability chain (national standard → accredited calibration lab → RPL reference standard → shop test boards / portable standards → meters), recalibration intervals (per the pack; company practice where open, labeled), certificate control, out-of-tolerance standard impact review. [chain diagram + table]
12. **AMI meter health monitoring** (company practice: HES event flags, zero-consumption and tamper analytics feeding removal-for-test) — labeled; not a substitute for any pack requirement.
13. **Customer-requested and commission-supervised tests** — summary with cross-reference to RPL-CS-PRO-007; do not restate fee rules.
14. **2024 program results (preliminary, data extracted 2025-01-03)** — computed from datasets: tests by reason × technology; pass/fail by group; average-accuracy distribution (histogram bins ±0.1%); fast/slow/within counts; functional failures by mode; customer requests by outcome; group acceptance summary (KY-Power-style table: group · in-service · sample · X̄ · σ · result). [≥6 tables, ≥2 charts]
15. **2025 test plan** — meters due by group and quarter (periodic) and sample sizes by group (sampled), from datasets; workload in technician-hours; field vs. shop split. [≥2 tables]
16. Program KPIs (company practice) · 17. Records & retention · 18. Training & technician qualification · 19. Related documents · 20. Revision history · 21. Approval block
**Appendices:** App-A Meter Test Report `MTR-F-011` (shop/field test record layout) · App-B Group acceptance worksheet · App-C Standards certification register summary · App-D Data dictionary.

### Sampling reference (guardrail)
If the pack names a sampling standard, the agent must not reconstruct its tables from memory. The orchestrator supplies `corpus/_global/reference/sampling_table.json`, a human-verified extract of the code-letter and sample-size table for the edition the pack names. The agent cites it in basis `sources`. If no such file is supplied, or the pack names no standard, RPL's sample-size table is written as **company practice** (labeled, no citation) and recorded in basis as `internal_procedure`.

### Datasets (deterministic script, seed 2024)

**`meter_registry_2024-12-31.csv`** (409,950 rows; gzip permitted as `.csv.gz`) — `meter_serial (e.g., RPL-A-0012345), meter_group_id, meter_technology, form, meter_class, service_type, vendor_family, install_date, premise_id, account_id (blank if inactive premise), service_center, county, circuit_id (FK T04), last_test_date (blank if never tested since install), last_test_reason, status (in_service)`.

**`meter_population_2024-12-31.csv`** (45–70 groups) — `meter_group_id` (PK), `vendor_family`, `meter_technology`, `form`, `meter_class`, `service_type`, `install_year_band`, `meter_count`, `test_method` (periodic|sample) **plus** `group_rule` (text), `sample_size_2025`, `periodic_interval_basis`, `oldest_last_test_date`, `meters_due_2025_q1..q4`. `meter_count` = count of registry rows per group (exact).
Required mix (company-profile realism):
| Technology | Total (exact) | Install years | Form/class mix |
|---|---|---|---|
| solid_state_AMI | 371,200 | 2016–2024 (deployment wave 2017–2021; ~8–12k/yr after) | 2S CL200 ≈ 86%; 2S CL320 ≈ 2%; 12S CL200 ≈ 4%; 16S CL200/CL320 ≈ 4%; 9S CL20 ≈ 2.5%; 3S/4S/1S ≤1.5% combined |
| solid_state_AMR | 31,400 | 2005–2015 | 2S CL200 ≈ 90%; 12S/16S ≈ 7%; 9S ≈ 3% |
| electromechanical | 7,350 | 1972–2004 | 2S CL200 ≈ 93%; remainder 1S/12S; mostly rural service centers |
Transformer-rated meters total 6,000–9,000. Vendor families: AMI mostly Vendor A (≈70%) and B; AMR Vendor B/C; EM Vendor C plus "legacy-other" grouped.

**`meter_test_results_2024.csv`** (~5,000–6,000 rows) — `test_id, meter_serial (FK registry or new-lot serial), meter_group_id, sample_lot_id (blank unless in_service sample or new_acceptance), customer_request_id (FK, customer_request rows only), test_date, test_reason (in_service_sample|in_service_periodic|new_acceptance|repaired|customer_request|removal_as_found|commission_supervised), test_location (shop|field), test_board_or_standard_id (FK standards), technician_id (MT-###), as_found_fl_pct, as_found_ll_pct, as_found_pf_pct, average_accuracy_pct, within_limits (Y|N), functional_result (pass|display_fail|register_fail|comm_fail|disconnect_switch_fail|physical_damage), adjusted (Y|N; EM only), as_left_fl_pct, as_left_ll_pct, as_left_pf_pct, action_taken (returned_to_service|retired|adjusted_returned|replaced_billing_review), billing_review_ref (when outside limits)`.
- `average_accuracy_pct` and `within_limits` are computed with the pack's method and limits, from `params`.
- Error model (as-found, % registration):
  - Solid-state: per-group bias ~N(100.00, 0.03), within-group σ 0.05–0.15. ≈0.2% of rows drawn from a wide tail (t-dist, ν=3, scale 0.6).
  - Electromechanical: bias drifting slow ≈ −0.02%/yr of age; σ 0.3–0.6. Light load is more dispersed than full load. ≈1–4% outside limits.
  - Removal_as_found and customer_request: slightly wider tails than random samples (selection bias).
  - Functional failures: AMI ~0.5–1.5% of removal tests; not accuracy failures.
- Mix: in-service sample 2,500–4,000; periodic per pack; new acceptance 900–1,600; customer_request = exactly the tested rows of the requests file; commission_supervised 0–6.

**`new_meter_lots_2024.csv`** — `lot_id, vendor_family, technology, form, meter_class, received_date, lot_size, sample_size, sample_failures, lot_result (accepted|rejected), disposition`. Lot sizes 500–6,000; ≤1 rejected lot per year, returned to vendor.

**`inservice_sample_selection_2025.csv`** — `meter_group_id, meter_serial, draw_rank, scheduled_quarter, location (field|shop)`, drawn from the registry with seed 2025.

**`customer_test_requests_2024.csv`** (~620 rows) — `customer_request_id` (PK), `account_id`, `premise_id`, `meter_serial`, `meter_technology`, `service_type`, `request_date`, `request_channel` (phone|web|written), `written_request` (Y|N), `prior_request_in_pack_window` (Y|N), `fee_charged_usd`, `fee_refunded` (Y|N), `test_date`, `witness_requested` (Y|N), `result` (within|fast|slow|non_registering|functional_fail), `report_sent_date`, `adjustment_ref`. Every request with a test has exactly one test_results row. Fee and timing comply with the pack for every row, with the §3.6a margin rule.

**`standards_calibration_2024.csv`** — `standard_id, standard_level (reference|working_test_board|portable), make_model_generic, serial, accuracy_class_generic, location, last_certified_date, certified_by (accredited external lab | RPL reference standard <id>), traceable_to, certificate_no, as_found_deviation_pct, next_due, certificate_on_file (Y|N)`. 2–4 reference, 6–10 test boards, 25–45 portable. Every standard used in test_results was in certification on the test date.

### Acceptance tests (`scripts/acceptance_tests.py`)
1. Registry row count = 409,950. Counts by technology = 371,200 / 31,400 / 7,350. Group `meter_count` = registry counts exactly.
2. Every test `meter_serial` exists in the registry or a `new_meter_lots_2024` lot. Every `test_board_or_standard_id` exists and was in certification on `test_date`.
3. Every customer request with a test date ↔ exactly one `customer_request` test row (same serial, same date).
4. Recompute `average_accuracy_pct` and `within_limits` from as-found values using `params` — 0 mismatches.
5. Every `within_limits = N` or functional failure has a corrective `action_taken`, and accuracy failures carry a `billing_review_ref`.
6. Baseline: no meter or group overdue on 2024-12-31 under `params`. At least 10% of periodically tested meters have a computed next-due date (`last_test_date` + interval from `params`) within the final 20% of their interval (margin rule).
7. Sampled groups: tested sample count ≥ `sample_size` per the sampling reference; draws reproducible from seed.
8. Each 2024 results table in the doc equals a recomputation from CSVs (script emits the tables; agent pastes them).
9. Distribution sanity: solid-state pooled σ ≤ 0.2; EM pooled σ 0.25–0.7; ≥1 EM accuracy failure exists; not all groups have identical X̄.
10. Rendered xlsx/docx/pdf values = canonical (§3.7).

### Length
5,000–7,500 words plus datasets.

---

## T19 — Service Interruption Reporting Procedure (with outage log)

**Doc ID:** RPL-DCC-PRO-003 · **Vertical:** Operations & Processes · **Wave:** 2 · **Grounding:** `corpus/grounding/T19.json`
**Owner/Reviewer/Approver:** Kevin Adeyemi (P23) / Patrick O'Neill (P21) / Elena Vasquez (P08)
**Outputs:** `corpus/docs/RPL-DCC-PRO-003/RPL-DCC-PRO-003_v4.2.md`, `RPL-DCC-PRO-003.basis.json`, every dataset listed under "Datasets" below (in `data/`), `scripts/generate_outage_data.py` (seed 2024).

### What this document is in the real world

The Distribution Control Center's procedure for deciding when a service interruption must be reported to the IURC, how quickly, with what content and how often to update until restoration, how intentional (planned) interruptions are handled and noticed, which interruption records are kept, restoration priorities, and how annual reliability indices are compiled. In Indiana, interruption reports are made to the IURC using **State Form 54646, "Report of Outage"**, which captures utility contact, customers affected and still out, interruption start, duration and estimated restoration, location (county/city), cause, report author and time, and whether the report is initial or final.

**Study for structure (do not copy text):**
- IURC State Form 54646, Report of Outage: https://forms.in.gov/Download.aspx?id=9574
- Colorado PUC electric incident reporting (procedure framing): https://puc.colorado.gov/electricincident
- Maine PUC utility contact protocol (escalation/contact protocol format): https://www.maine.gov/mpuc/sites/maine.gov.mpuc/files/inline-files/Contact%20Protocol%20April%202021%20Letter_0.pdf
- IURC Electric Utility Reliability Report 2022 (Indiana benchmark magnitudes and table design): https://secure.in.gov/iurc/files/2022-RELIABILITY-REPORT-Final-7-6-23.pdf
- NorthWestern Energy 2024 Electric Reliability Report (MT PSC): https://www.psc.mt.gov/_docs/Reports/Electric-Reliability/2024/2024_NWE_Electric_Reliability_Report.pdf
- SCE 2015 Annual Reliability Report (CPUC): https://files.cpuc.ca.gov/egy_Reliability_GO165Reports/ReliabilityRpts/2015/SCE_2015_%20Annual_Reliability_Report.pdf
- LBNL (Eto), Reliability metrics and IEEE 1366: https://eta-publications.lbl.gov/sites/default/files/7._eto_-_reliability_metrics_and_rvbp.pdf
- USDA RUS Bulletin 1730A-119 (outage cause-code taxonomy): https://rd.usda.gov/sites/default/files/UEP_Bulletin_1730A-119.pdf

**Inputs (read-only, from T04):** `corpus/_global/ops/circuits_master.csv`, `outage_incidents_base.csv`, `outage_events_base.csv`, `outage_restoration_steps_base.csv`, `daily_saidi_history_2019_2023.csv`, `med_days.csv`, `reliability_facts.yaml`.
**Additional outputs:** `data/outage_incidents_2024-01-01_2025-01-31.csv`, `data/planned_interruption_notices_2024.csv`, `data/iurc_report_log_2024-01-01_2025-01-31.csv`, `data/README.md`, `data/_manifest.json`, `scripts/acceptance_tests.py`, `render/` (see §3.7).

### Required structure (minimum depth in brackets)

1. Purpose · 2. Scope · 3. Definitions (interruption, sustained, momentary, intentional/planned, outage incident, customers affected, customer minutes, restoration step, major event and MED — **pack definitions verbatim in meaning**; IEEE 1366 terms for anything the pack leaves undefined, labeled company practice) [≥18 terms]
4. Regulatory basis · 5. Roles (DCC shift supervisor, DCC operators, DCC Manager P23, Director P21, Regulatory Affairs P08/P09, Corporate Communications, Key Accounts for critical customers) [RACI table]
6. **Outage data capture in OMS** — event creation (AMI last-gasp, SCADA, calls), device prediction, incident grouping rules, step restoration recording, cause assignment, close-out verification within an internal deadline (company practice). [field table]
7. **Reportability determination** — decision table using the pack's criteria **for investor-owned utilities**, evaluated at the **incident** level. The DCC tracks the moment the incident meets a criterion (`threshold_crossed_ts`). Show only RPL's applicable thresholds. [decision table: criterion · measure · source field · clause]
8. **Initial report** — timing (per the pack, measured from the trigger the pack uses), channel, content (map every content element to a State Form 54646 field and to the pack). [mapping table]
9. **Update reports** — interval and content until restoration (per the pack); DCC reminder timer practice.
10. **Final report** — trigger and content (per the pack).
11. **Restoration priorities** — as the pack orders them, if it does; otherwise public health and safety first (company practice), then RPL tiers (critical facilities, transmission/substation, feeder backbones, laterals, individual services). [tier table]
12. **Intentional (planned) interruptions** — customer notice timing and method, exceptions (per the pack); planned-notice record.
13. **Storm mode** — activation criteria (company practice), incident command roles, reporting cadence under storm mode (still meets the pack), mutual assistance.
14. **Interruption records** — record content, system, retention (per the pack's records provisions). [table]
15. **Annual reliability indices** — SAIFI, SAIDI, CAIDI calculated per the pack's definitions. Denominator = customers served as stated in `reliability_facts.yaml`. Sustained interruptions only. Planned interruptions included or excluded per the pack (if silent, include, and also show an ex-planned view labeled company practice). MED identification per IEEE 1366 2.5β with TMED from 2019–2023 daily SAIDI (company practice unless the pack prescribes the method). Interruptions accrue to the day they begin. Present with and without MED. Show worked TMED derivation. [≥3 tables]
16. **Worst-performing circuits review** (company practice) — top 10 by CI and CMI ex-MED; action plans; link to the circuit prioritization in RPL-DO-PLN-002 (vegetation management). [table]
17. **Tree-related outage data handoff** to the Vegetation Management Program (RPL-DO-PLN-002): fields, inside/outside ROW coding, monthly extract, reconciliation sign-off.
18. **2024 performance summary (preliminary, data extracted 2025-02-10)** — from datasets: indices with/without MED; MED list (date, cause, CI, CMI); outages, CI and CMI by cause; monthly profile; reportable incidents with report timeliness. [≥5 tables, ≥3 charts]
19. Training & drills (annual reporting drill; new-operator qualification) · 20. Related documents · 21. Revision history · 22. Approval block
**Appendices:** App-A Completed example State Form 54646 (initial, one update and final) for a **fictional 2024 wind event that exists in the dataset** (incident ID stated; values equal the dataset; use the form revision in effect on the event date, or omit the revision line) · App-B DCC reporting checklist · App-C Notification contact sheet (IURC contacts by role — real public numbers only from official .gov pages; internal escalation list) · App-D OMS cause-code table · App-E Data dictionary.

### Cause-code taxonomy (company practice; App-D)
`cause_category` → `cause_code`:
- `vegetation` → `tree_inside_row_growth`, `tree_inside_row_failure`, `tree_outside_row_fallin`, `tree_unknown_location`
- `weather` → `wind`, `lightning`, `ice_snow`, `flood`, `heat`
- `equipment` → `oh_conductor`, `ug_cable`, `transformer`, `cutout_fuse`, `arrester`, `insulator`, `pole`, `connector`, `recloser_breaker`, `substation_equipment`
- `animal` → `squirrel`, `bird`, `snake_raccoon_other`
- `public` → `vehicle`, `dig_in`, `vandalism_theft`, `fire`, `customer_equipment`, `third_party_contact`
- `power_supply` → `69kv_line`, `transmission_supply_miso`, `substation_supply`
- `operational` → `overload`, `switching_error`, `protection_miscoordination`
- `planned` → `maintenance`, `construction`, `emergency_switching_for_safety`
- `unknown` → `unknown_patrolled_no_cause`
Target 2024 shares of sustained **outage records** (ex-MED): vegetation 20–27%, equipment 25–33%, animal 12–18%, weather 8–14%, public 5–9%, power supply 1–3%, operational 1–3%, planned 5–10%, unknown 6–12%. MED days skew strongly to vegetation and weather.

### Datasets (deterministic script, seed 2024)

The T04 base event file is the canonical physical history. T19 adds regulatory fields and must not alter T04 values.

**`outage_events_2024-01-01_2025-01-31.csv`** (one row per sustained outage record/device operation; 9,500–12,000 rows):
`event_id, incident_id, start_ts, end_ts, utc_offset, duration_min, customers_affected, customer_minutes, restoration_steps, circuit_id, substation_id, service_center, county, municipality (or 'unincorporated'), device_type (substation_breaker|feeder_breaker|recloser|sectionalizer|fuse|transformer|service|69kv_line), device_id, outage_level (supply|substation|feeder|lateral|transformer|service), cause_category, cause_code, tree_location (inside_row|outside_row|unknown|n/a), weather_code, intentional (Y|N), critical_facilities_affected (int), detection_source (ami_last_gasp|scada|customer_call|field), med_flag (Y|N), med_date, reportable (Y|N — copied from incident), notes`.
- `customers_affected` ≤ `customers_on_circuit` for feeder-level and below. Substation and supply events ≤ the sum over the circuits served.
- Heavy tail: lognormal/Pareto mixture by `outage_level` (transformer/service median 1–8; fuse/lateral median 15–60; feeder 300–2,500; substation/supply 2,000–15,000).
- Duration: lognormal by level and cause, median 75–140 min ex-MED; MED-day medians 3–10× longer; 0.5–1.5% exceed 24 h.
- Seasonality: storm-driven peaks April–August, with a secondary winter ice event optional. Diurnal: thunderstorm outages peak 14:00–22:00. Animal outages peak in spring and fall.
- `customer_minutes` = Σ over restoration steps (customers restored × minutes out) — not customers × duration.

**`outage_incidents_2024-01-01_2025-01-31.csv`** (one row per incident; storms aggregate many events):
all T04 `outage_incidents_base.csv` columns unchanged, plus `threshold_crossed_ts`, `reportable`, `criteria_met`, `iurc_initial_report_ts`, `iurc_update_count`, `iurc_final_report_ts`: `incident_id, incident_type (single_event|storm|planned), first_start_ts, utc_offset, utility_aware_ts, threshold_crossed_ts (blank if never), peak_customers_out, peak_ts, total_customers_affected, counties_affected, municipalities_affected, critical_facilities_affected, restored_ts, reportable (Y|N under pack thresholds via params), criteria_met (list), etr_first_ts`.

**`iurc_report_log_2024-01-01_2025-01-31.csv`** — one row per submitted report: `report_id, incident_id, report_type (initial|update|final), submitted_ts, channel, form_revision, customers_affected_reported, customers_still_out_reported, etr_reported, cause_reported, reported_by_person_id`. Timeliness is computed from the pack's trigger in `params`. Non-reportable incidents have no rows. The incident-file columns `iurc_initial_report_ts`, `iurc_update_count`, `iurc_final_report_ts` are derived summaries of this log.

**`planned_interruption_notices_2024.csv`** — `incident_id, notice_method, notice_sent_ts, customers_noticed, customers_affected, exception_code (blank|emergency|safety|other per pack), scheduled_start_ts, actual_start_ts`. Every planned incident without an exception complies with the pack's notice rule, with the margin rule.

**`reliability_indices_2024.csv`** — rows: 12 months + annual; columns: `period, customers_served, ci_all, cmi_all, saifi_all, saidi_all, caidi_all, ci_ex_med, cmi_ex_med, saifi_ex_med, saidi_ex_med, caidi_ex_med, med_days, tmed_saidi_min, saifi_ex_med_ex_planned, saidi_ex_med_ex_planned`. 2024 calendar year only (January 2025 rows excluded). Annual SAIFI/SAIDI = Σ monthly.

**Targets** (match `reliability_facts.yaml` from T04): ex-MED SAIFI 1.05–1.15, SAIDI 130–150, CAIDI 115–140. With-MED SAIDI 220–350. 3–8 MED days, including the App-A wind event.

### Benchmarks (record used sources in basis `sources`)
| Metric | Range | Source |
|---|---|---|
| Indiana IOU SAIFI ex-MED | 0.71–1.37 | IURC Reliability Report 2022 |
| Indiana IOU SAIDI ex-MED / with MED | 76–178 / 147–949 | same |
| Indiana IOU MED days per year | 3–15 | same |
| US IOU average (2015) | SAIFI 1.2 / SAIDI 136 ex-MED | LBNL (Eto) |
| Sustained outage records per year | NIPSCO 12,841 ex-MED (~480k customers) | NIPSCO 2024 VM report |
| TMED examples | 1.7–7.0 SAIDI-min | SCE 2015; NorthWestern 2024 |

### Acceptance tests (`scripts/acceptance_tests.py`)
1. Every `circuit_id`/`substation_id`/county matches `circuits_master.csv`. Customers-affected bounds hold.
2. T04 base values (times, customers, CMI, cause) are unchanged in the T19 event file (hash compare on those columns).
3. TMED recomputes from `daily_saidi_history_2019_2023.csv`. `med_flag` recomputes from 2024 daily SAIDI ≥ TMED. Every event on a MED day accrues by start date.
4. `reliability_indices_2024.csv` recomputes exactly from events. CAIDI = SAIDI/SAIFI. Annual = Σ months. Values, including the vegetation CI/CMI/SAIFI/SAIDI contributions, equal `reliability_facts.yaml`.
5. `reportable` recomputes from incidents with `params`. Every reportable incident has initial/update/final reports meeting `params` timing. ≥15% of reportable incidents use more than 60% of the allowed initial-report window (margin rule). Zero late or missing.
6. Planned notices comply. Margin rule applied.
7. App-A form values equal the incident and report-log rows for the stated incident ID.
8. Cause shares and monthly seasonality fall within the stated ranges. The top 1% of events by CI hold ≥25% of total CI (heavy-tail check).
9. Rendered outputs match canonical (§3.7).

### Length
5,000–7,000 words plus datasets.

---

## T20 — Spill Response & Reporting Procedure

**Doc ID:** RPL-ENV-PRO-005 · **Vertical:** Environmental · **Wave:** 2 · **Grounding:** `corpus/grounding/T20.json`
**Owner/Reviewer/Approver:** Hannah Brooks (P26) / Daniel Foster (P25) / Sandra Kim (P24)
**Outputs:** `corpus/docs/RPL-ENV-PRO-005/RPL-ENV-PRO-005_v3.1.md`, `RPL-ENV-PRO-005.basis.json`, `data/spill_events_2024.csv`, `data/README.md`, `scripts/generate_spill_data.py` (seed 2024), `scripts/acceptance_tests.py`, `data/_manifest.json`, `render/RPL-ENV-PRO-005_v3.1.docx`, `render/RPL-ENV-PRO-005_v3.1.pdf`, `render/EHS-F-201_Spill_Report.pdf` (fillable), `render/RPL-ENV-PRO-005_App-B_Crew_Card.pdf`

### What this document is in the real world

The procedure that field crews, the Distribution Control Center (DCC), fleet and Environmental Services follow when oil or another substance is released. Typical RPL sources: mineral-oil dielectric fluid from pole-mount and padmount distribution transformers (vehicle strikes, storms, lightning, failures, theft/vandalism); substation power transformers, regulators, breakers and capacitors; diesel from the three standby generator belly tanks and from fleet fueling; gasoline/diesel and hydraulic fluid from fleet vehicles and bucket/digger-derrick trucks. It covers immediate response, de-energization and isolation, containment, the reportability determination, state notification and updates, third-party notifications, follow-up and written reports, cleanup and confirmation, waste disposal, close-out (including any compliance confirmation the pack provides for), and records. Crews use it from a pocket card. Environmental Services uses it from the full text and the spill report form.

**Study for structure and vocabulary only (do not copy text; every number in these is from another jurisdiction or federal law and is contaminated for this corpus):**
- Florida DEP, Mineral Oil Dielectric Fluid Emergency Response Protocol: https://floridadep.gov/sites/default/files/MinOilFluidEmergRespProtocol_13Sep16.pdf (emergency vs. non-emergency tracks; records list)
- SDG&E Spill Response and Notification Plan (CPUC filing): https://ia.cpuc.ca.gov/environment/info/dudek/CNF/20160801_CNF%20PLRP_Spill%20Response%20and%20Notification%20Plan_REDACTED.pdf (spill-kit table; notification matrix; notification form)
- National Grid first-responder bulletin on oil releases: https://outreach.ngridsafety.com/wp-content/uploads/2025/12/17661_NGrid_FR_MC_ebulletin_Oil_releases_flyer_el_1225.pdf (equipment list; isolate before contain; assume PCB until known)
- IDEM Emergency Response program page and quick-reference sheet: https://www.in.gov/idem/cleanups/investigation-and-cleanup-programs/emergency-response/ · https://www.extension.purdue.edu/news/inprepared/2021/04/_docs/er_quick_ref_sheet.pdf (caller-information headings; real contact numbers)
- ND DEQ incident summary for a utility transformer release (field list for a spill record): https://deq.nd.gov/FOIA/Spills/Summary_Reports/EIR5299_Summary_Report.pdf

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

5,500–8,000 words body including appendices (measured per §3.6 R9). Rendered 20–32 pages.

### Self-check (in addition to §2.6)

- Every element of any defined report-content term in the pack maps to an EHS-F-201 field.
- Every 7.2 row, 7.3 exclusion and the §9 third-party duty carry a citation and parameters in the basis file.
- Every 7.1 row is either cited or written as a `Company position:` row and listed in `basis.interpretations`.
- No number from a study reference appears in the document (§2.1).

---

## T21 — Electrical Accident & Incident Reporting Procedure

**Doc ID:** RPL-SAF-PRO-009 · **Vertical:** Workforce & Safety · **Wave:** 2 · **Grounding:** `corpus/grounding/T21.json`
**Owner/Reviewer/Approver:** Tyrone Jackson (P27) / Sandra Kim (P24) / Elena Vasquez (P08), with concurrence by Michael Brennan (P16) shown in the approval block (not in front matter)
**Outputs:** `corpus/docs/RPL-SAF-PRO-009/RPL-SAF-PRO-009_v2.0.md`, `RPL-SAF-PRO-009.basis.json`, `data/incident_log_2024.csv`, `data/README.md`, `scripts/generate_incident_data.py` (seed 2024), `scripts/acceptance_tests.py`, `data/_manifest.json`, `render/RPL-SAF-PRO-009_v2.0.docx`, `render/RPL-SAF-PRO-009_v2.0.pdf`, `render/EHS-F-101_Incident_Report.pdf` (fillable), `render/EHS-F-102_IURC_Notification_Log.pdf` (fillable)

### What this document is in the real world

The Safety department's procedure for reporting, classifying and investigating incidents connected with RPL's electric facilities and work: employee and contractor injuries, members of the public contacting RPL facilities, vehicle incidents, property damage, energized-line contacts, dig-ins and near misses. It covers immediate actions, the internal notification matrix, the IURC notification decision and telephone/written reports, other external notifications (by reference), investigation, corrective and preventive actions (CAPA) and records. Workplace injury and illness recordkeeping and severe-injury reporting to Indiana OSHA (IOSHA) are handled in RPL-SAF-PRO-010 and only referenced here.

**Study for structure and form layout only (do not copy text; every threshold and time limit in these is from another state and is contaminated for this corpus):**
- PA PUC Electric Accident Report Form UCTA-8: https://www.puc.pa.gov/documents/utility-files/275/UCTA-8_Electric_Accident_Report_8-2023.pdf
- Missouri PSC Electrical Contact Reporting Form: https://psc.mo.gov/CMSInternetData/Electric/Electrical%20Contact%20Reporting%20Form%202024.pdf
- OSHA Forms 300/301 (field layout for EHS-F-101 Part B): https://www.osha.gov/sites/default/files/OSHA-RK-Forms-Package.pdf

### Assessment scope (state this in §2)

IURC accident reporting (as the pack's accident section provides) and the associated record retention (as the pack's records section provides) are covered in full. These are referenced in one clause each and recorded under `out_of_scope_references`, with **no values**:
- the statutory duty the pack quotes (name the IC section only);
- IOSHA/OSHA recordkeeping and severe-injury reporting (RPL-SAF-PRO-010);
- DOT post-accident testing for CDL drivers (RPL-HR-PRO-015);
- Indiana 811 damage reporting (RPL-DO-PRO-020);
- third-party claims (RPL-CLM-PRO-001).

### Rules specific to this task

1. **Report only what the pack makes reportable.** The IURC decision table in §8 lists every incident category in §1.6 Table S-INC. For each category, the `Reportable to IURC?` column is "Yes" **only** where the pack's text makes it reportable, quoting the condition exactly. Every other category reads "No — not reportable to the IURC under <pack citation>; internal and other-agency reporting per §7, §10 and §13". Do not import any injury, dollar, customer-count, hospitalization or outage threshold from any other source.
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
- IURC-reportable events: 0 or 1 in 2024. If 1, it is a fictional public-contact event, its timestamps comply with the pack, and it is the App-D example with no personal details; the member of the public is identified by role only (e.g., "a tree-service worker").
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

---

## T10 — Regulatory Obligations Register

**Doc ID:** RPL-CMP-REG-001 · **Vertical:** Compliance & Legal · **Wave:** 3a (after Wave 2 clause-ID freeze) · **Grounding:** `corpus/grounding/T10.json`
**Owner/Reviewer/Approver:** Priya Raman (P06) / David Okafor (P05) / Margaret Ellison (P04)
**Inputs (read-only):** `corpus/_global/**`; every Wave 2 document and basis file (`corpus/docs/*/*.md`, `corpus/docs/*/*.basis.json`); `corpus/qa/clause_id_freeze.json`
**Outputs:** `corpus/docs/RPL-CMP-REG-001/RPL-CMP-REG-001_v4.0.md` (cover memo + methodology), `data/obligations_register.csv`, `data/controls.csv`, `data/README.md`, `RPL-CMP-REG-001.basis.json`, `render/RPL-CMP-REG-001_v4.0.xlsx`, `render/RPL-CMP-REG-001_v4.0_Memo.pdf`

### What this document is in the real world

The compliance function's master list of regulatory obligations (a "compliance obligations register" in ISO 37301 terms), exported from RPL's GRC tool. Each row is one obligation derived from a specific provision, with its type, trigger, timing, key parameters, applicability decision, accountable owner, the implementing documents and controls, the evidence, the review dates and a risk rating. The CCO uses it to answer "are we covered?" and to route regulatory changes to owners.

**Study for column design (do not copy text):**
- Camms Compliance Obligations Register field definitions: https://camms.atlassian.net/wiki/spaces/CD/pages/77496321
- Legal & Regulatory Requirements Register template: https://www.securityscientist.net/blog/legal-and-regulatory-requirements-register-template/
- ServiceNow Policy & Compliance data model (authority document → citation → control objective → control): https://www.servicenow.com/community/grc-articles/policy-and-compliance-management-architecture-and-data-model/ta-p/3605503

### Decomposition rule (deterministic)

1. For every active section in the pack, read the body text by subsection (use the pack's `subsections` spans).
2. Create one obligation row for each subsection or list item that imposes a duty, prohibition, permission-with-condition, customer right or record/report requirement on a utility. If a subsection holds several distinct duties with different triggers or parties, create one row per duty.
3. Definitions, purpose and saving clauses do not create rows. Record them in `basis.considered_no_obligation` with the reason.
4. A section that applies only to other utility types gets **one** `Not applicable` row, with the rationale citing the applicability text (§2.3.7) and the T01 attribute used.
5. Expected size: 150–260 rows. If you land outside this range, re-check the rule. Do not pad or merge to hit the range.

### Register columns (`obligations_register.csv`)

`clause_id` (`RPL-CMP-REG-001:OBL-nnnn`, primary key) · `obligation_id` (`OBL-nnnn`) · `citation` (most specific level) · `section_heading` · `regulator` (IURC|IDEM) · `jurisdiction` (IN) · `obligation_title` (≤ 10 words) · `obligation_summary` (one or two sentences, faithful to the pack) · `obligation_type` (report|notice|record|test|standard|prohibition|procedure|customer_right) · `trigger` · `frequency_or_deadline` · `key_parameters` (values exactly as in the pack, `; `-separated) · `applicability` (Applies|Not applicable) · `applicability_rationale` · `applicability_attribute` (T01 attribute key, if used) · `accountable_owner_id` (P-ID) · `process_owner_department` · `implementing_documents` (`DOC_ID:clause` list, frozen IDs only) · `control_ids` (`CTL-xx-nnn` list → `controls.csv`) · `evidence_record` (record series ID from §1.6 Table R) · `risk_rating` (High|Medium|Low; company assessment of impact × likelihood of non-compliance) · `review_frequency` (Quarterly|Semi-annual|Annual) · `last_reviewed` (2025-03-12 to 2025-03-13) · `next_review` · `compliance_status` (Compliant | Compliant – control test scheduled; never a gap status) · `last_control_test` (date in 2024 or blank for new controls) · `notes`

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
- `Change Log` (v3.3 → v4.0 changes)
- `Statistics` (a pivot-style summary; one bar chart via the `dataviz` skill palette)

The memo goes to PDF via the `docx` skill. CSV stays canonical.

### Self-check (in addition to §2.6)

- CSV primary keys match the clause-ID grammar (§3.2) and are unique.
- Every `implementing_documents` entry resolves to the freeze file.
- Every `Not applicable` row's rationale quotes or cites the pack's applicability text or a T01 attribute.
- Row count is between 150 and 260, or the deviation is explained in `basis.notes`.

---

## T11 — Regulatory Reporting Calendar 2025

**Doc ID:** RPL-REG-CAL-2025 · **Vertical:** Compliance & Legal · **Wave:** 3b (after T10) · **Grounding:** `corpus/grounding/T11.json` (same scope as T10)
**Owner/Reviewer/Approver:** Marcus Lee (P09) / Elena Vasquez (P08) / Thomas Whitfield (P07)
**Version / dates (per §1.4):** v1.2 · effective 2025-03-17 · approved 2025-03-14 · revision history (prior versions): v1.0 2025-01-03 (annual roll from RPL-REG-CAL-2024), v1.1 2025-02-24 (aligned to RPL-DCC-PRO-003 v4.2); current v1.2 change summary: aligned to RPL-ENV-PRO-005 v3.1 and RPL-SAF-PRO-009 v2.0
**Inputs (read-only):** `corpus/_global/**`; T10 outputs; Wave 2 documents and basis files; `corpus/qa/clause_id_freeze.json`
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

- `xlsx` skill workbook: `Calendar` (filters, validation), `By Month`, `Event Clocks`, `Lookups`, `Change Log` (v1.1 → v1.2).
- One-page landscape month-grid PDF via the `pdf` skill. Optionally a 12-month timeline strip via the `dataviz` skill.
- The `.md` memo goes to PDF via `docx`.

### Self-check (in addition to §2.6)

- Every assessed row maps to a T10 obligation, a frozen `source_procedure` clause and a basis parameter with `s1_quote`.
- No `tracked_external` row carries a citation, a regulatory due rule or a `due_date_2025`.
- Computed dates follow the stated computation rule.

---

## T12 — Records Retention Schedule

**Doc ID:** RPL-LEG-RRS-001 · **Vertical:** Compliance & Legal · **Wave:** 3b (after T10) · **Grounding:** `corpus/grounding/T12.json` (union of T13–T21 scopes)
**Owner/Reviewer/Approver:** Linda Nguyen (P12) / Jonathan Pierce (P03) / Catherine Brandt (P02)
**Inputs (read-only):** `corpus/_global/**` (including §1.6 Table R); T10 register (`obligation_type = record` rows); every Wave 2 document and basis file; `corpus/qa/clause_id_freeze.json`
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

---

## T90 — Baseline validation (Snapshot 1 must produce zero findings)

**Wave:** 4 · **Inputs:** `corpus/docs/**`, `corpus/grounding/**` (packs, not the orchestrator report), `corpus/_global/**`, `corpus/qa/**` · **Outputs:** `corpus/validation/T90_baseline_report.md`, `corpus/validation/T90_results.json`; fills `regulatory_basis_sections` and `coverage_dispositions_summary` in `document_register.csv`. Optional: `corpus/validation/T90_dashboard.html` (`frontend-design` + `dataviz`).

### Checks

Deterministic checks (re-run `validate.py` across the corpus):
1. **Quote and placement.** Every `s1_quote` is an exact substring of the cited section's `body_text_s1` and lies inside the cited subsection span.
2. **Value.** Every `doc_value` appears verbatim inside its clause boundary (§3.2). After numeral normalization (§3.4), the numbers, units, qualifiers and day types equal those in `s1_quote`. `derived` values are recomputed.
3. **Coverage and dispositions.** Every pack citation has exactly one disposition. Every `high` citation is `covered` with all material parameters. Report parameter-count parity between high and standard covered sections (the ratio of parameters per covered section; flag if high/standard > 1.5).
4. **Citation validity.** No cited section is repealed, absent from S1, or outside the pack. No phantom citations.
5. **Value ledger.** 100% of body numbers ledgered. `company_practice` values never sit in a cited sentence unless prefixed `Internal performance target:`.
6. **Clause IDs.** Grammar, uniqueness, boundaries; all Wave 3 references resolve against `clause_id_freeze.json`; no retired ID is referenced.
7. **Cross-document consistency.** §1 and §1.6 constants; people and roles (no unknown named persons); forms; record series (every Wave 2 records clause maps to a T12 series); register `implementing_documents` and calendar `source_procedure` resolve; `cross_doc_refs` are symmetric.
8. **Dates.** No past-event date after approval; revision histories ordered and earlier than approval; T03 matches §1.4.
9. **Datasets.** Re-run each script with the same seed; byte-identical outputs; row counts within range; every row complies with the pack parameters (no overdue meter group, no late reportable outage, spill or accident report, no fee charged in violation).
10. **Render parity.** Every rendering opens and contains 100% of the canonical sentences and rows.

LLM checks:

11. **Independent fidelity review** (as §0.4 step 3; fresh agent per document). Target: zero issues.
12. **Realism & depth rubric** (§3.8 Parts A–C; a fresh agent per document, not the one used in the QA loop). Report scores per criterion; pass thresholds per §3.8.
13. **Company positions.** For every `basis.interpretations` entry, the fidelity reviewer confirms that it does not contradict pack text.

Isolated checks (run by a separate isolated contamination-check agent with Snapshot-2 access, not one of the T91 annotators; T90 receives only pass/fail and clause IDs, never S2 text):

14. **Snapshot-2 contamination.** For every changed citation, confirm that no document value or phrase matches an S2-only value or 6-word shingle. Any hit fails the document, because the generator used knowledge beyond the pack.

Engine check:

15. **Strata baseline run (if available).** Run the engine with Snapshot 1 as current law. Expected: zero non-informational findings. Every informational finding is listed with the reason.

### Report format

- Per document: pass/fail per check, rubric scores, issues with clause IDs and quotes, and the fix applied (with a pointer to `fixlog.md`).
- Corpus summary: counts by check; realism score distribution; the high/standard parity ratio per document.
- Re-run until all checks pass; record the final pass with a timestamp and the corpus SHA-256 (hash of all `corpus/docs/**` files).
- Fixes go back to the orchestrator. The validator never edits documents.

---

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
             "citation": "<citation>",
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
         "decoys_correctly_unchanged": ["<citation>"]
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

---

## Appendix A — Reference index

| Doc | Reference | URL |
|---|---|---|
| T13 | NIPSCO General Rules and Regulations (electric) | https://www.nipsco.com/docs/librariesprovider11/rates-and-tariffs/electric-rates/2025-to-current/general-rules-and-regulations.pdf |
| T13 | AES Indiana rates, rules and regulations | https://www.aesindiana.com/rates-tariffs |
| T13 | CenterPoint Energy Indiana South electric tariff | https://www.centerpointenergy.com/en-us/Documents/RatesandTariffs/Indiana/Southwest/in-south-electric-tariff.pdf |
| T14 | AES Ohio disconnection rule | https://www.aes-ohio.com/sites/default/files/2021-02/D6%20-%20Disconnection%2010-1-18.pdf |
| T14 | Washington Electric Co-op disconnection policy | https://www.washingtonelectric.coop/wp-content/uploads/2019/04/Disconnection-of-Electrical-Service.pdf |
| T14 | Indiana OUCC winter moratorium FAQ | https://secure.in.gov/oucc/about-your-rates/winter-disconnection-moratorium-frequently-asked-questions |
| T15, T18 | Tescometering meter-testing materials | https://www.tescometering.com/wp-content/uploads/2024/03/NC-Meter-School_Meter-Testing-101_Tom-Lawton_6.15.2022.pdf |
| T16 | IURC Tree Trimming | https://secure.in.gov/iurc/tree-trimming |
| T16 | 170 IAC 4-9 rulemaking comments | https://www.in.gov/iurc/files/Indiana_Tree_Alliance_-_Baker.pdf |
| T18 | Entergy Arkansas Meter Test Plan | https://www.entergyarkansas.com/wp-content/uploads/2024/11/eal_ps12_mtp.pdf |
| T18 | Tescometering in-service/statistical program comparison | https://www.tescometering.com/wp-content/uploads/2024/03/Comparison-of-In-ServiceStatistical-Test-Programs-6-30-04.pdf |
| T19 | IURC State Form 54646, Report of Outage | https://forms.in.gov/Download.aspx?id=9574 |
| T19 | Colorado PUC electric incident reporting | https://puc.colorado.gov/electricincident |
| T20 | Florida DEP mineral oil emergency response protocol | https://floridadep.gov/sites/default/files/MinOilFluidEmergRespProtocol_13Sep16.pdf |
| T20 | CPUC-filed Spill Response and Notification Plan | https://ia.cpuc.ca.gov/environment/info/dudek/CNF/20160801_CNF%20PLRP_Spill%20Response%20and%20Notification%20Plan_REDACTED.pdf |
| T10 | Legal & regulatory requirements register template | https://www.securityscientist.net/blog/legal-and-regulatory-requirements-register-template/ |
| T10 | Camms compliance obligations register | https://camms.atlassian.net/wiki/spaces/CD/pages/77496321 |
| T11 | CPUC filing due-dates table | https://www.cpuc.ca.gov/-/media/cpuc-website/files/legacyfiles/2/6442466765-2021-ra-filing-due-dates.docx |
| T12 | Washington State public utilities retention schedule | https://sos.wa.gov/sites/default/files/2025-02/public-utilities-records-retention-schedule-v.1.0-%28december-2010%29-superseded.pdf |
| T12 | Colorado State Archives Schedule No. 60 | https://archives.colorado.gov/sites/archives/files/documents/Schedule%20No.%2060.pdf |

This index is non-exhaustive; where it differs from a task's own study list, the task list governs. References are for structure, layout, vocabulary and tone. They are never a source of regulatory values; the grounding pack is.

Additional verified sources for each task are listed inside that task. The audit reports that produced v2.0 (with full source lists) are kept in `corpus/qa/audit_reports/` for the orchestrator.

## Appendix B — Glossary for agents

- **IAC** — Indiana Administrative Code. Citations look like `170 IAC 4-1-16(b)`: Title 170 (IURC), Article 4 (electric utilities), Rule 1, Section 16, subsection (b).
- **IURC** — Indiana Utility Regulatory Commission. **OUCC** — Office of Utility Consumer Counselor. **IDEM** — Indiana Department of Environmental Management.
- **IOU** — investor-owned utility (RPL). **REMC** — rural electric membership corporation (not RPL).
- **Tariff sheet** — one numbered page of a filed tariff; revisions cancel and replace earlier sheets.
- **SAIFI / SAIDI / CAIDI** — system average interruption frequency / duration index; customer average interruption duration index.
- **Major event day (MED)** — a day excluded from normalized reliability indices under IEEE 1366's 2.5-beta method (company reliability-reporting practice unless the pack prescribes it). Not the same as any reportability threshold or "major event" definition in the IURC rules; use the pack's definition for reporting.
- **As-found / as-left** — meter accuracy measured before / after adjustment.
- **Snapshot 1 / Snapshot 2** — internal to this spec only; never appear in any document.
