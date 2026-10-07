# Audit — Group B (Operations): T16, T18, T19

**Spec audited:** `/home/claude/strata_synthetic_corpus_spec.md` v1.0 (2026-10-06)
**Reviewer scope:** T16 Vegetation Management Plan 2025 · T18 Meter Testing Program Plan + datasets · T19 Service Interruption Reporting Procedure + outage log + reliability indices
**Method:** Full read of §0–§3 and all three tasks; review of 26 public sources (all listed in §5 and actually opened); recomputation of profile-implied magnitudes; gap analysis; replacement spec text.

**Regulatory-value rule respected.** This report adds **no** Indiana regulatory values to the proposed spec text. Several sources opened (the IURC tree-trimming page, RUS/KY meter filings) contain regulatory numbers. They are deliberately left out of the proposed text. Every number in the ready-to-paste blocks is (a) a company-profile derivation, (b) a company-practice choice, or (c) an industry benchmark from a non-Indiana-rule source, labeled as such.

**Caveat on sources.** The PDFs were read through a summarizing fetch tool. Where a figure looked garbled, it is flagged "(verify)". Examples: CenterPoint's distribution cycle came back as "3-61 years", which is probably "3–6". Duke's 24 catastrophic exclusion days are attributed to Hurricanes Helene and Milton, which may be a system-wide note rather than Indiana-specific. Generator agents must re-open any benchmark they use and record it in the basis file (see G6).

---

## 0. Executive summary of findings

| # | Severity | Task | Finding |
|---|---|---|---|
| 1 | **Critical** | T16 × T19 | The two tasks run in parallel in Wave 2. Each one invents its own circuits, its own 2024 tree outages and its own reliability numbers. Nothing makes T16's `vm_tree_outages_2024.csv`, T16 §18 metrics, T19's event log and T19's indices reconcile. Circuit IDs (`LAF-012-3`) will also collide or diverge. **Fix:** a new Wave-1 task, T04, produces a canonical circuit master and base outage-event file. T16 and T19 both read them. |
| 2 | **Critical** | T19 | MED flags "per IEEE 1366 2.5-beta" cannot be computed. The method needs five prior years of daily SAIDI, and the spec supplies none. Agents will hand-pick MED days, so the indices will not recompute. **Fix:** T04 also emits 2019–2023 daily SAIDI history plus a TMED derivation, and the `med_flag` is computed, not assigned. |
| 3 | **Critical** | T19 | The event file has no way to model the structure that real reportability turns on. Missing: a storm/incident grouping (individual outage records rarely reach "tens of thousands" of customers), awareness and threshold-crossing timestamps, step restoration / CMI, critical-facility and municipality fields, and planned-outage notice fields. Strata's re-scoring under Snapshot 2 depends on these. |
| 4 | **Critical** | T18 | No meter-level registry exists. `meter_serial` in test results cannot be integrity-checked, and periodic-interval changes cannot be quantified per meter. The group-level `last_test_cycle_completed` is too coarse for "how many meters become overdue". |
| 5 | **Critical** | T18 | The sampling plan has no source of sample sizes. If the pack names a sampling standard, its tables are copyrighted and not in the pack. Agents will invent sample sizes. **Fix:** an orchestrator-verified reference table, or an explicit company-adopted table recorded in basis. |
| 6 | **Major** | T16/T18/T19 | Margin and "look-good" tuning risk. Baseline compliance will be produced with large uniform margins: every notice weeks early, every report minutes after the event, every meter group years from due. A real record clusters near deadlines, and Snapshot-2 tightening would then yield zero quantified impact. A compliance-margin distribution rule is needed. |
| 7 | **Major** | T16 | Structure is missing the elements every real Indiana annual VM filing has: budget vs. actual for the prior year, a complaint/inquiry table with handling, tree-related vs. all outages with and without MEDs, a 69 kV subtransmission ROW program, hazard-tree program, herbicide/IVM, contractor QA/QC, hours of work, and a notification step sequence. |
| 8 | **Major** | T18 | The test-results schema lacks as-left values, functional (non-accuracy) failures, test-board IDs and lot/sample IDs. There is no new-shipment lot file, no 2025 sample-selection list, and solid-state vs. electromechanical error parameters are unspecified. |
| 9 | **Major** | T19 | Cause taxonomy is too coarse (9 codes). It lacks power supply/69 kV, overload, tree inside vs. outside ROW (needed for the T16 handoff), equipment sub-causes, and customer equipment. Real taxonomies (RUS 1730A-119) have 8–10 categories with sub-causes. |
| 10 | **Major** | All three | No acceptance tests, no data dictionary standard, no benchmark ranges with sources, no minimum table or section counts, and no rendered outputs (xlsx/docx/pdf). |
| 11 | Minor | T19 | App-A sets the example form in a March 2024 event, but State Form 54646 now shows revision "R4 / 07-24". Either print the revision in effect at the event date or move the example event to after July 2024. |
| 12 | Minor | T16/T18 | Approval dates (T18 2025-01-08, T16 2025-01-22) are days after year-end. The 2024 results must be labeled "preliminary — data extracted <date>", as real early-January documents are. |

---

## 1. T16 — Vegetation Management Plan 2025

### 1(a) Real-world anatomy

**Indiana annual VM reports filed March 2025** (five IOUs, links on the OUCC page). Each is a cover letter, then a short annual report, then an attached program document.

| Source | Length | Section order / content | Tables | Magnitudes |
|---|---|---|---|---|
| Duke Energy Indiana 2024 VM Report | ~24 pp | Distribution program (pp 3–12), then transmission (13–24). Each part: goals/objectives · definitions · federal/state/local laws · property access rights · work quality & safety standards (ANSI A300, Z133, OSHA 1910.269, NESC) · management overview · inspections/monitoring | Budget vs. actual (dist/trans) · complaints by type with resolution · Tree SAIFI vs. total SAIFI | 5-yr cycle (~20% of miles/yr), ~16,000 distribution miles. 2024 distribution budget $57.2M, actual $49.1M; total $92.9M budget / $84.1M actual. Tree SAIFI 0.174 of 0.937 total (~18.5%, ex-MED). 10 complaints. Company clearance: primary ≥10 ft |
| AES Indiana 2024 VM Annual Report | ~29 pp (4 pp report + Exh A complaints 2 pp + Exh B program 10 pp + Exh C rule text) | I Expenditures · II Complaints · III Tree-related outages as % of SAIFI · IV Program (cycle, miles, clearance table by voltage, hazard response times, debris, staffing/contractors, control methods, hours of work, 4-step notification) | Budget/actual · CAD complaints by issue · 324 line-clearing inquiries by category · clearance by line type | 4-yr cycle; 3,674 circuit mi; 424 circuits; ~918 mi/yr. $24.7M budget / $25.5M actual. Veg 32.6% of SAIFI with MED, 24.2% ex-MED. 3,607 veg incidents (2,511 ex-MED). 3 MEDs, 18 storms |
| CenterPoint Indiana South 2024 Report & Plan (VEC-047) | ~19 pp (2 pp report + 17 pp plan) | Plan: 1 Introduction (scope, roles, definitions) · 2 Line clearance standards · 3 Distribution · 4 Transmission · 5 Contractor requirements · 6 References · 7 Appendices | Definitions table (brush vs. tree by DBH, trim types) · clearance by direction × species · transmission clearances · complaints by concern | $5.30M budget / $5.24M actual. Veg SAIFI 0.24 of 0.79 (~30%). 10 concerns, 1 IURC complaint. Cycle "3–6" years (verify) |
| NIPSCO 2024 Compliance Filing — Annual Report | 40+ pp (report + Exhibits A–I contractor specs) | Expenditures · complaints · tree outages · program · exhibits (crew requirements, herbicide specs, billing) | Budget/actual by category · 693 call entries by type · CAD complaints · tree vs. total outages with/without MED | $24.7M budget / $28.6M actual (distribution $25.1M). Tree outages 3,853 of 15,189 (25.4%) with MED; 2,936 of 12,841 (22.9%) ex-MED. Transmission 4–6-yr cycle. Herbicide ≥90% control spec |
| I&M 2024 VM Annual Report | ~21 pp (3 pp + 18 pp program guidelines) | Expenditures (capital vs. O&M × dist/trans) · cost trend graph · complaints · tree-related outages | Budget/actual 4-way split | $42.4M budget / $36.2M actual (IN). Tree outages 12.7% of total ex-MED. 2 complaints |
| Eversource NH 2025 VM Annual Filing (non-IN plan example) | 10 pp | Intro & reqs · 2025 budget · planned activities · program descriptions (scheduled maintenance trim, enhanced trim, mid-cycle, customer request, hot spot, ROW, hazard trees) · plan overview (workforce, contracts, cost drivers, technology) · budget table | Budget by program × region; miles/acres by region | $43.8M total: SMT $19.3M for 2,062 mi (~$9.35k/mi); hazard trees $18.6M; ROW mowing 1,447 acres $2.8M. 12,000 OH miles, 5-yr cycle, 6 contractors |

**Benchmark implications for RPL** (14,200 OH miles; 528 circuits; ~26.9 OH mi/circuit average; 418 mi of 69 kV):

| Metric | Implied / benchmark range | RPL spec value | Assessment |
|---|---|---|---|
| Distribution cycle | 4–5 yr (AES 4, Duke 5, Eversource 5; CNP 3–6 verify) | ~130 of 528 circuits/yr ⇒ ~4.1 yr | Consistent. Use 4-yr backbone / 5-yr laterals and reconcile counts |
| Miles trimmed per year | 14,200 / 4–5 ⇒ 2,840–3,550 mi | not stated | Must state; schedule sum must hit it |
| Total VM spend | Duke IN dist $49M (16k mi); I&M $36M; NIPSCO $28.6M; Eversource NH $43.8M (12k mi) | $41.6M | Plausible upper-middle; must include 69 kV ROW |
| Routine $/mile trimmed | ~$8k–$16k (Eversource SMT ~$9.35k; Duke ~$15k implied; AES ~$27k all-in urban) | not stated | Specify ~$7.5k–$9.5k for a rural west-central IN system |
| Tree share of SAIFI ex-MED | 12.7% (I&M) – ~30% (CNP); Duke 18.5%, AES 24.2%, NIPSCO 22.9% of outages | not stated | Target 20–27% (rural, high OH exposure) |
| Tree-related sustained outages ex-MED | AES 2,511 (~530k cust); NIPSCO 2,936 (~480k cust) | not stated | ~2,000–2,700 for RPL |
| Complaints/inquiries | Formal: 2–18 per utility/yr; inquiries 300–700 | not stated | Need a contacts/complaints dataset |

### 1(b) Gaps

| ID | Severity | Gap |
|---|---|---|
| T16-1 | **Critical** | No shared circuit master. `circuit_id`, `substation_id`, county and OH miles are invented independently of T19's outage log. |
| T16-2 | **Critical** | `vm_tree_outages_2024.csv` and §18 metrics are not derived from T19's event data. Values will disagree with T19's vegetation events and indices. |
| T16-3 | **Major** | No 2024 budget vs. actual. Every Indiana filing leads with it, and the 2025 budget needs a prior-year comparison and variance explanation. |
| T16-4 | **Major** | No complaints / customer-contact data. Every Indiana annual report tabulates complaints, CAD referrals and inquiries with handling. The plan's dispute section (§14) has nothing behind it. |
| T16-5 | **Major** | Missing program sections: hazard-tree program (identification, response tiers), IVM/herbicide (EPA-registered, applicator licensing as an out-of-scope reference), mid-cycle/hot-spot/customer-request work, 69 kV subtransmission ROW, contractor requirements and QA/QC audits, work planning (pre-planners, work packets), hours of operation, storm/mutual-assistance, tree replacement program, safety standards (Z133, OSHA 1910.269 as out-of-scope references). |
| T16-6 | **Major** | `vm_circuit_schedule_2025.csv` has no notice dates or work dates (`planned_start`, `notice_sent_date`, `followup_notice_date`). Notice-timing compliance cannot be tested, and Strata cannot quantify a notice-period change. |
| T16-7 | **Major** | Circuit-schedule internal consistency is unspecified. `last_trim_year` vs. `cycle_years`, sum of `overhead_miles` vs. annual miles, and sum of `est_cost_usd` vs. the routine budget line are not tied together. |
| T16-8 | **Major** | Budget breakdown is unspecified beyond five line names. Real filings split distribution and transmission (or subtransmission), O&M and capital, and routine, hazard and other. |
| T16-9 | Major | No minimums (tables, clearance-table rows, notice fields), benchmarks, acceptance tests or rendering. |
| T16-10 | Minor | §1 "Executive summary" is fine, but real plans also carry "Program goals and strategy" up front. Add it. |
| T16-11 | Minor | 2024 data in a plan approved 2025-01-22 must be labeled preliminary (extract date). |
| T16-12 | Minor | Snapshot-1 risk: clearance specifications and "power-line-compatible" planting lists can drift into restating rule content. Clearance distances must be labeled company practice unless the pack states them. |

### 1(c) Ready-to-paste spec text — replacement for the whole T16 section

```markdown
## T16 — Vegetation Management Plan 2025

**Doc ID:** RPL-DO-PLN-002 · **Vertical:** Policy & Governance · **Wave:** 2 · **Grounding:** `corpus/grounding/T16.json`
**Owner/Reviewer/Approver:** Rachel Stein (P22) / Patrick O'Neill (P21) / Jonathan Pierce (P03)
**Inputs (read-only, from T04):** `corpus/_global/ops/circuits_master.csv`, `corpus/_global/ops/outage_events_base.csv`, `corpus/_global/ops/med_days.csv`, `corpus/_global/ops/reliability_facts.yaml`
**Outputs:**
- `corpus/docs/RPL-DO-PLN-002/RPL-DO-PLN-002_v2025.1.md`, `RPL-DO-PLN-002.basis.json`
- `data/vm_circuit_schedule_2025.csv`, `data/vm_work_completed_2024.csv`, `data/vm_tree_outages_2024.csv`, `data/vm_budget_2024_2025.csv`, `data/vm_customer_contacts_2024.csv`, `data/README.md`
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
(URLs: Appendix A.)

### Required structure (minimum depth in brackets)

1. **Plan at a glance** — one table: circuits scheduled, OH miles scheduled, cycle by category, 2025 budget by category, contractors, key dates. [1 table]
2. **Program goals and strategy** — reliability, safety, customer-relations and cost objectives; prioritization logic (cycle due, tree CI history, worst-performing circuits); company practice. [≥250 words]
3. **Applicability** — one clause citing the pack's applicability section.
4. **Definitions** — identical meaning to the pack; add company terms (brush vs. tree by DBH, side/under/through/V-trim, directional pruning, hazard tree, hot spot, mid-cycle, IVM, work planner, lead sheet) labeled company practice. [≥20 terms, table]
5. **Regulatory basis** — table: citation · heading · governs §§. Also list industry standards and out-of-scope references (OSHA 29 CFR 1910.269, NESC, EPA/Office of Indiana State Chemist pesticide rules, NERC FAC-003 "not applicable — RPL owns no facilities ≥100 kV") as `out_of_scope_reference` clauses.
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
20. **Disputes** — before and after work; escalation to a second authorized representative; information to give the customer when unresolved (per the pack and its cross-reference to 170 IAC 16). App-C form.
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
| `vm_category` | enum | `backbone_3ph` \| `lateral_1ph` \| `subtrans_69kv` |
| `cycle_years` | int | per §8 category (company practice) |
| `last_trim_year` | int | normally `2025 − cycle_years`; ≤8% of rows may be one year late or early (deferrals and storm re-sequencing), each with a `schedule_note` |
| `scheduled_quarter_2025` | enum | Q1–Q4. Leaf-off Q1/Q4 weighted for laterals; distribution roughly 22/28/28/22% |
| `overhead_miles` | float(1) | from master |
| `contractor` | enum | Contractor A \| Contractor B (≈55/45 by miles; contiguous by service center) |
| `est_cost_usd` | int | `overhead_miles × unit_cost × density_factor`. Unit cost per company practice (§24); density factor lognormal, median 1.0, σ≈0.35, clipped 0.4–3.0 (urban/wooded circuits cost more) |
| `planned_start_date`, `planned_end_date` | date | inside the scheduled quarter; duration ≈ miles / (0.6–1.2 mi per crew-day × crews) |
| `notice_batch_id` | str | `VMN-2025-###`; one or more per circuit |
| `notice_letter_date`, `door_hanger_start_date` | date | satisfy the pack's notice timing for every row, with the margin distribution in §3.6 |
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

### Benchmarks (form and magnitude only; record each used source in basis `sources[]`)
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
5. Every notice date satisfies the pack's timing (`params` dict). At least 10% of rows have margins in the lowest 20% of the allowable window (§3.6 margin rule). None are non-compliant.
6. Every App-A field maps to a clause ID in basis. Every pack-required notice element appears in both §11 and App-A.
7. The App-D table equals the top-20 circuits by miles in the dataset.
8. The rendered docx/pdf/xlsx are regenerated from canonical md/csv, and table values match (§3.7).

### Length
6,500–9,500 words plus datasets (real Indiana plan documents run 17–29 pages).
```

---

## 2. T18 — Meter Testing Program Plan

### 2(a) Real-world anatomy

| Source | Length | Content / structure | Tables & fields | Magnitudes |
|---|---|---|---|---|
| Entergy Arkansas Meter Test Plan (Schedule P12) | 1 sheet | 12.1 new meters; 12.2 in-service (periodic for combination/3-phase, variable interval, statistical sampling for 1-ph kWh per ANSI C12.1) | none | 100% test of new demand meters; sampling for kWh-only |
| Grayson RECC (KY PSC 2009-00103) sample testing plan application | ~8 pp | Letter · introduction · rules · procedures · cost analysis | Group table: `group · manufacturer · type · population · sample` | 15,192 meters in 5 homogeneous groups (45–9,068). Z1.9-2003, Inspection Level II, std-dev method; AQL 2.5 existing, 1.0 new lots; escalation table (% within limits → next-year test %); tests at FL, LL, 50% PF |
| Kentucky Power 2023 Meter Test Reports (KY PSC) | 1-page table + letter | Annual results | `group · in-service count · sample size · X̄ · σ · pass/fail` | 20 groups (401–9,189 meters); n = 75 per group for lots ~4,800–9,189; X̄ 99.83–100.18%; σ 0.072–0.213; all pass; Z1.9 Level II, AQL 2.5 |
| Eversource NH 2023 Meter Testing Program Annual Report | 2 pp | Letter + 1-page summary | lot results | All lots within tolerance; only one lot (older electromechanical) σ > 0.1 (0.5867) — solid-state lots tight |
| Xcel (NSP) 2023 Meter Testing Results (ND PSC PU-24-152) | 4 pp | Letter + attachments A (summary) and B (lot detail) | `tested · within tolerance · slow · fast` (counts and %); 55 lots with sample sizes 3–200+ | 261 electric tests (181 random sample, 80 periodic for HV/high-demand), 100% within tolerance |
| PA PUC compliance letter (customer referee test) | 2 pp | Single-meter lab result | FL %, LL %, average %, test system make/serial, NIST traceability | FL at 100% TA, LL at 10% TA; 99.99 / 100.04 / 100.00 |
| Narragansett Electric RI (2004) & NH PUC Order 24,278 | 11 pp / order | Testimony proposing Z1.9 sampling; order approving | groups by manufacturer and type | ~2,900 fewer tests/yr; cost ~$21–$24 per meter test |
| Tescometering: In-Service/Statistical comparison; ECNE 2016 | slides | Periodic vs. variable vs. statistical; Z1.4 vs. Z1.9 | — | Sampling ≈ <30% of periodic volume; AQL 0.25–2.5 typical; master standards usually calibrated annually by external NIST-traceable lab; working standards checked monthly/quarterly against shop master; homogeneous lots, random selection; ECNE notes Indiana is among states referencing Z1.9/Z1.4 |

**Profile-implied magnitudes for RPL** (409,950 meters):

| Item | Expected magnitude | Basis |
|---|---|---|
| Homogeneous groups | 45–70 (manufacturer × model family × form × install-year band) | KY Power 20 groups for ~170k; Xcel 55 lots |
| In-service sample per AMI group (lots ~5k–35k) | ~75–150 per group (from the sampling standard's table; KY Power used 75 for lots 4.8k–9.2k) | KY Power |
| Annual in-service sample tests | ~2,500–4,000 | 35–45 sampled groups × 75–100 |
| Electromechanical / transformer-rated periodic tests | depends on pack interval; EM 7,350 + transformer-rated ~6–9k | profile |
| New-meter acceptance tests | ~1,000–1,500 (≈8–12k new meters/yr, lot samples) | growth + replacement ~2–3%/yr |
| Customer-requested tests | ~0.1–0.2% of meters/yr ⇒ 400–800 (spec 620 OK) | reviewer estimate (no source opened) |
| Solid-state average accuracy | mean ~100.00%, σ 0.05–0.20% per lot | KY Power, Eversource |
| Electromechanical | mean 99.6–99.9% (slow drift), σ 0.3–0.6% | Eversource NH (EM lot σ 0.587) |
| Accuracy failures | SS ≪0.5%; EM ~1–4% | KY, Xcel, Eversource |
| Functional failures (AMI: display/register/comm/disconnect switch) | dominate removals; separate from accuracy | reviewer judgement |
| Reference/portable standards | 2–4 lab reference standards; 6–10 shop test boards; 25–45 portable field standards for ~410k meters | reviewer estimate; ECNE traceability chain |
| Transformer-rated share | ~1.5–2.5% of meters (≈6,000–9,000) | 44k commercial + 1.2k industrial |

### 2(b) Gaps

| ID | Severity | Gap |
|---|---|---|
| T18-1 | **Critical** | No meter-level registry. Test `meter_serial`s cannot be validated. Per-meter last-test dates are missing, and Strata needs them to count meters made overdue by an interval change. |
| T18-2 | **Critical** | Sampling plan inputs are unspecified. No lot formation rule, sample-size table source, acceptance criterion inputs or switching/escalation rule. If the pack names a sampling standard, agents lack its tables and will fabricate them. |
| T18-3 | **Critical** | Population groups are not tied to the meter registry, test results or new-shipment lots. Counts by technology must sum to §1.1. Form/class/service-type mixes are unspecified, and agents will produce implausible mixes (e.g., many 1S/3S). |
| T18-4 | **Major** | The test-results schema lacks `as_left_*`, `functional_result`, `sample_lot_id`, `test_board_id`/standard chain, `pf_test_pct` semantics, `customer_request_id` FK and `removed_from_service`. The error-distribution parameters by technology are unspecified. |
| T18-5 | **Major** | Missing datasets: `new_meter_lots_2024.csv` (acceptance sampling by shipment) and `inservice_sample_selection_2025.csv` (random draw per group with seed — this is what a 2025 plan is). |
| T18-6 | **Major** | Missing sections: lot/group formation methodology, random selection procedure, lot rejection actions (expanded sampling → group replacement program), AMI functional/health monitoring (company practice), shop accreditation/traceability chain diagram, test-board certification, annual report to the commission (if in the pack), program KPIs. |
| T18-7 | **Major** | Customer requests: there is no `customer_request` FK into test results and no reconciliation with T15's procedure. Fee rules live in T15's pack (4-1-4…4-1-14), but T18's pack (4-1-3…4-1-11) overlaps. The agent must use only its own pack and cross-reference RPL-CS-PRO-007. |
| T18-8 | **Major** | "No group overdue" with no margin rule ⇒ every group will be freshly tested. Real populations span the interval. |
| T18-9 | Minor | Calibration file: there is no `standard_level` (reference/working/portable/test board), no `traceable_to`, no certificate number or accreditation, and no as-found deviation. |
| T18-10 | Minor | Approved 2025-01-08: label 2024 results preliminary (extract 2025-01-03). |

### 2(c) Ready-to-paste spec text — replacement for T18 from "Required structure" onward (keep header and "What this document is", replace the study list)

```markdown
**Study for structure, tables and magnitudes (do not copy text; never take regulatory values from these):**
- Entergy Arkansas Meter Test Plan (tariff-schedule form of a filed program)
- Grayson RECC sample-testing plan application, KY PSC Case 2009-00103 (group table; lot formation by manufacturer/type; escalation table)
- Kentucky Power 2023 Meter Test Reports (annual results table: group · in-service · sample · X̄ · σ · pass/fail)
- Xcel Energy (NSP) 2023 Meter Testing Results, ND PSC PU-24-152 (tested/within/slow/fast summary; lot detail)
- Eversource NH 2023 Meter Testing Program Annual Report (lot σ commentary)
- Tescometering: In-Service/Statistical Test Programs comparison; ECNE 2016 Meter Testing Programs (program types, traceability chain)
(URLs: Appendix A.)

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
If the pack names a sampling standard, the agent must not reconstruct its tables from memory. The orchestrator supplies `corpus/_global/reference/sampling_table.json`, a human-verified extract of the code-letter and sample-size table for the edition the pack names. The agent cites it in basis `sources[]`. If no such file is supplied, or the pack names no standard, RPL's sample-size table is written as **company practice** (labeled, no citation) and recorded in basis as `internal_procedure`.

### Datasets (deterministic script, seed 2024)

**`meter_registry_2024-12-31.csv`** (409,950 rows; gzip permitted as `.csv.gz`) — `meter_serial (e.g., RPL-A-0012345), meter_group_id, meter_technology, form, meter_class, service_type, vendor_family, install_date, premise_id, account_id (blank if inactive premise), service_center, county, circuit_id (FK T04), last_test_date (blank if never tested since install), last_test_reason, status (in_service)`.

**`meter_population_2024-12-31.csv`** (45–70 groups) — fields as before **plus** `group_rule` (text), `sample_size_2025`, `periodic_interval_basis`, `oldest_last_test_date`, `meters_due_2025_q1..q4`. `meter_count` = count of registry rows per group (exact).
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

**`inservice_sample_selection_2025.csv`** — `group_id, meter_serial, draw_rank, scheduled_quarter, location (field|shop)`, drawn from the registry with seed 2025.

**`customer_test_requests_2024.csv`** (~620 rows) — fields as before plus `premise_id, meter_technology, customer_request_id` (PK). Every request with a test has exactly one test_results row. Fee and timing comply with the pack for every row, with the §3.6 margin rule.

**`standards_calibration_2024.csv`** — `standard_id, standard_level (reference|working_test_board|portable), make_model_generic, serial, accuracy_class_generic, location, last_certified_date, certified_by (accredited external lab | RPL reference standard <id>), traceable_to, certificate_no, as_found_deviation_pct, next_due, certificate_on_file (Y|N)`. 2–4 reference, 6–10 test boards, 25–45 portable. Every standard used in test_results was in certification on the test date.

### Acceptance tests (`scripts/acceptance_tests.py`)
1. Registry row count = 409,950. Counts by technology = 371,200 / 31,400 / 7,350. Group `meter_count` = registry counts exactly.
2. Every test `meter_serial` exists in the registry or a `new_meter_lots_2024` lot. Every `test_board_or_standard_id` exists and was in certification on `test_date`.
3. Every customer request with a test date ↔ exactly one `customer_request` test row (same serial, same date).
4. Recompute `average_accuracy_pct` and `within_limits` from as-found values using `params` — 0 mismatches.
5. Every `within_limits = N` or functional failure has a corrective `action_taken`, and accuracy failures carry a `billing_review_ref`.
6. Baseline: no meter or group overdue on 2024-12-31 under `params`. At least 10% of periodically tested meters have `next_due` within the final 20% of their interval (margin rule).
7. Sampled groups: tested sample count ≥ `sample_size` per the sampling reference; draws reproducible from seed.
8. Each 2024 results table in the doc equals a recomputation from CSVs (script emits the tables; agent pastes them).
9. Distribution sanity: solid-state pooled σ ≤ 0.2; EM pooled σ 0.25–0.7; ≥1 EM accuracy failure exists; not all groups have identical X̄.
10. Rendered xlsx/docx/pdf values = canonical (§3.7).

### Length
5,000–7,500 words plus datasets.
```

---

## 3. T19 — Service Interruption Reporting Procedure

### 3(a) Real-world anatomy

| Source | Length | Content | Tables / fields | Magnitudes |
|---|---|---|---|---|
| IURC State Form 54646 "Report of Outage" (R4 / 07-24) | 2 pp (p.2 instructions, not filed) | Final Report Y/N · Name of utility · Utility contact representative · Contact phone · Est. total customers affected **and** customers still out as of this report · Interruption(s) start date/time · Duration · Location (county, city, address or other description) · Cause · Estimated restoration time · Reported by · Date/time · Notes | — | — |
| IURC Electric Reliability Report 2022 | 16 pp | Intro (compiled from IOU filings under 170 IAC 4-1-23) · index definitions · MED explanation · MED summary · territory map · MED history · per-utility tables and graphs with and without MED | per-utility multi-year SAIFI/SAIDI/CAIDI | 2022 ex-MED: SAIFI 0.77–1.37, SAIDI 103–160, CAIDI 82–157. With MED: SAIDI 147–454. MEDs 3–15 |
| IURC Electric Reliability Report 2025 | 15 pp | same pattern | same | 2025 ex-MED: SAIFI 0.71–0.92, SAIDI 76–178. With MED: SAIDI 267–949. MEDs 6–11 |
| NIPSCO 2024 VM report (outage counts) | — | tree vs. total outage counts | — | 15,189 total sustained outages with MED / 12,841 ex-MED (~480k customers) |
| NorthWestern Energy (MT) 2024 Reliability Report | 23 pp | Exec summary · methodology · per-division analyses · conclusion | indices with/without MED; cause rankings (10 causes) | TMED = e^(α+2.5β) = 6.960 SAIDI-min; 7 MEDs + 1 catastrophic event; SAIDI ex-MED 117.6 |
| SCE 2015 Annual Reliability Report | 59+ pp | 10-yr indices (all / ex-MED / distribution vs. transmission) · district tables · planned outages · map · worst-performing circuits | WPC table: circuit, district, customers, substation, miles, % OH/UG, breaker ops, rank, weighted SAIDI | TMED 1.736; 5 MEDs listed with cause and customers; SAIFI 0.86 ex-MED |
| LBNL (Eto) reliability metrics deck | slides | IEEE 1366 definitions (sustained >5 min), 2.5β method, ~2.3 MEDs/yr theoretical | — | 2015 US IOU avg: SAIFI 1.2 ex-MED / 1.4 with; SAIDI 136 ex-MED / 237 with |
| USDA RUS Bulletin 1730A-119 | bulletin | Interruption record fields; cause taxonomy; index computation; MED: multi-day interruptions accrue to start day; step restoration summed by step | record fields: received time, location/device, off time, cause and cause location, crew/truck, action, restoration steps, customers, customer-minutes, cause/equipment/weather codes | Cause categories: power supply · planned · equipment/installation/design · maintenance (incl. tree growth / tree failure) · weather (lightning, wind, ice, flood) · animals · public (vehicle, customer, vandalism, public tree cutting) · other · unknown |
| Colorado PUC incident page / Maine PUC contact protocol | (in spec already) | procedure framing, contact protocol | — | — |

**Profile-implied magnitudes for RPL** (407,491 customers; 528 circuits ⇒ **~772 customers per circuit average**; 112 substations ⇒ ~3,640 customers per substation):

| Quantity | Implied | Note |
|---|---|---|
| CI ex-MED (SAIFI 1.1) | ≈448,000 | target is at the high end of Indiana IOUs (0.71–1.37) — acceptable for a rural OH-heavy system |
| CMI ex-MED (SAIDI 140) | ≈57.0 M | CAIDI ≈127 min — within the Indiana range 82–157 |
| With MED | SAIFI 1.3–1.6, SAIDI 220–350 | Indiana 2022 with-MED SAIDI 147–454 |
| MED days 2024 | 3–8 | Indiana 3–15; theory ~2.3 |
| TMED | ~3–8 SAIDI-min/day | depends on 2019–2023 history; NWE 6.96 |
| Sustained outage records 2024 | 9,000–11,000 | NIPSCO 12.8k ex-MED for ~480k |
| Mean CI per record ex-MED | ~45 | requires heavy tail: median 4–8 (transformer/fuse), feeder lockouts 300–2,500, substation/69 kV events 2,000–15,000 |
| Max single-record customers | ≤ substation or 69 kV line exposure (~4k–15k) | "tens of thousands" only as an **aggregated storm/incident**, not a single record |

### 3(b) Gaps

| ID | Severity | Gap |
|---|---|---|
| T19-1 | **Critical** | No shared circuit master or customers-per-circuit. `customers_affected` can exceed circuit size; county and circuit pairs are arbitrary; T16 cannot reconcile. |
| T19-2 | **Critical** | MED cannot be computed (no 2019–2023 daily SAIDI history; no TMED). |
| T19-3 | **Critical** | No incident/storm grouping. Reportability is often judged on a combined interruption event in an area, and "tens of thousands" customers is only realistic as an aggregation. Needs `incident_id` and an incident-level file with the timestamps used for reporting. |
| T19-4 | **Critical** | Missing fields needed to evaluate any plausible reportability or timing rule without knowing the pack: `utility_aware_ts`, `threshold_crossed_ts` (when the incident first met a reportability criterion), `customers_out_by_hour` or step restoration, `critical_facilities_affected`, `municipality`, `etr_ts` and `etr_updates`. Planned interruptions lack `notice_sent_ts`/`notice_method`/`customers_noticed`. Without these, a Snapshot-2 change to the basis of a threshold or the timing trigger cannot be re-scored. |
| T19-5 | **Major** | CMI is implied as `duration × customers_affected`, which is wrong with step restoration. Add `customer_minutes` and a restoration-steps file. |
| T19-6 | **Major** | Cause taxonomy is too coarse. It lacks power supply (69 kV / MISO transmission supply), equipment sub-causes, overload, tree inside vs. outside ROW (T16 handoff), customer equipment, and "other". |
| T19-7 | **Major** | Index computation is ambiguous: denominator (year-end vs. average customers), which events count (sustained only; exclude momentaries; the pack's definitions govern), treatment of planned interruptions (include unless the pack says otherwise; show both), month attribution, and the 2025-01 rows (excluded from 2024 indices). |
| T19-8 | **Major** | Conflation risk: the pack's reportable "major event"/threshold concept vs. the IEEE 1366 MED used for normalized indices. The spec must keep them separate. |
| T19-9 | **Major** | The App-A example (March 2024 wind event) is not required to equal dataset rows, and the form revision is anachronistic (R4 / 07-24). |
| T19-10 | **Major** | Missing structure: shift-change handoff, OMS data-quality and close-out review (cause verification within N days — company practice), ETR policy, media/critical-customer notification, worst-performing circuits (company practice), DCC log retention, storm-mode (incident command) trigger, after-action report. |
| T19-11 | **Major** | Margin rule: report timestamps will be generated just after events. Real initial reports cluster in the later part of the allowed window during storms (crews and DCC saturated), and update counts vary. |
| T19-12 | Minor | Momentary interruptions/MAIFI: optional; if recorded, put them in a separate file so the sustained-event count is not inflated. |
| T19-13 | Minor | Timestamps "local Indiana Eastern" are ambiguous at the November DST fall-back. Add a UTC offset or UTC column. |

### 3(c) Ready-to-paste spec text — replacement for T19 from "Required structure" onward

```markdown
**Inputs (read-only, from T04):** `corpus/_global/ops/circuits_master.csv`, `outage_events_base.csv`, `outage_restoration_steps_base.csv`, `daily_saidi_history_2019_2023.csv`, `med_days.csv`, `reliability_facts.yaml`.
**Additional outputs:** `data/outage_incidents_2024-01-01_2025-01-31.csv`, `data/planned_interruption_notices_2024.csv`, `data/iurc_report_log_2024-01-01_2025-01-31.csv`, `data/README.md`, `scripts/acceptance_tests.py`, `render/` (see §3.7).

### Required structure (minimum depth in brackets)

1. Purpose · 2. Scope · 3. Definitions (interruption, sustained, momentary, intentional/planned, outage incident, customers affected, customer minutes, restoration step, major event and MED — **pack definitions verbatim in meaning**; IEEE 1366 terms for anything the pack leaves undefined, labeled company practice) [≥18 terms]
4. Regulatory basis · 5. Roles (DCC shift supervisor, DCC operators, DCC Manager P23, Director P21, Regulatory Affairs P08/P09, Corporate Communications, Key Accounts for critical customers) [RACI table]
6. **Outage data capture in OMS** — event creation (AMI last-gasp, SCADA, calls), device prediction, incident grouping rules, step restoration recording, cause assignment, close-out verification within an internal deadline (company practice). [field table]
7. **Reportability determination** — decision table using the pack's criteria **for investor-owned utilities**, evaluated at the **incident** level. The DCC tracks the moment the incident meets a criterion (`threshold_crossed_ts`). Show only RPL's applicable thresholds. [decision table: criterion · measure · source field · clause]
8. **Initial report** — timing (per the pack, measured from the trigger the pack uses), channel, content (map every content element to a State Form 54646 field and to the pack). [mapping table]
9. **Update reports** — interval and content until restoration (per the pack); DCC reminder timer practice.
10. **Final report** — trigger and content (per the pack).
11. **Restoration priorities** — public health and safety first (per the pack), then RPL tiers (critical facilities, transmission/substation, feeder backbones, laterals, individual services). [tier table]
12. **Intentional (planned) interruptions** — customer notice timing and method, exceptions (per the pack); planned-notice record.
13. **Storm mode** — activation criteria (company practice), incident command roles, reporting cadence under storm mode (still meets the pack), mutual assistance.
14. **Interruption records** — record content, system, retention (per the pack and 170 IAC 4-1-3). [table]
15. **Annual reliability indices** — SAIFI, SAIDI, CAIDI calculated per the pack's definitions. Denominator = customers served as stated in `reliability_facts.yaml`. Sustained interruptions only. Planned interruptions included or excluded per the pack (if silent, include, and also show an ex-planned view labeled company practice). MED identification per IEEE 1366 2.5β with TMED from 2019–2023 daily SAIDI (company practice unless the pack prescribes the method). Interruptions accrue to the day they begin. Present with and without MED. Show worked TMED derivation. [≥3 tables]
16. **Worst-performing circuits review** (company practice) — top 10 by CI and CMI ex-MED; action plans; link to T16 priorities. [table]
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
`incident_id, incident_type (single_event|storm|planned), first_start_ts, utility_aware_ts, threshold_crossed_ts (blank if never), peak_customers_out, peak_ts, total_customers_affected, counties_affected, municipalities_affected, critical_facilities_affected, restored_ts, reportable (Y|N under pack thresholds via params), criteria_met (list), etr_first_ts`.

**`iurc_report_log_2024-01-01_2025-01-31.csv`** — one row per submitted report: `report_id, incident_id, report_type (initial|update|final), submitted_ts, channel, form_revision, customers_affected_reported, customers_still_out_reported, etr_reported, cause_reported, reported_by_person_id`. Timeliness is computed from the pack's trigger in `params`. Non-reportable incidents have no rows. The previous event-level columns `iurc_initial_report_ts`, `iurc_update_count`, `iurc_final_report_ts` are kept on the incident file as derived summaries.

**`planned_interruption_notices_2024.csv`** — `incident_id, notice_method, notice_sent_ts, customers_noticed, customers_affected, exception_code (blank|emergency|safety|other per pack), scheduled_start_ts, actual_start_ts`. Every planned incident without an exception complies with the pack's notice rule, with the margin rule.

**`reliability_indices_2024.csv`** — rows: 12 months + annual; columns: `period, customers_served, ci_all, cmi_all, saifi_all, saidi_all, caidi_all, ci_ex_med, cmi_ex_med, saifi_ex_med, saidi_ex_med, caidi_ex_med, med_days, tmed_saidi_min, saifi_ex_med_ex_planned, saidi_ex_med_ex_planned`. 2024 calendar year only (January 2025 rows excluded). Annual SAIFI/SAIDI = Σ monthly.

**Targets** (match `reliability_facts.yaml` from T04): ex-MED SAIFI 1.05–1.15, SAIDI 130–150, CAIDI 115–140. With-MED SAIDI 220–350. 3–8 MED days, including the App-A wind event.

### Benchmarks (record used sources in basis `sources[]`)
| Metric | Range | Source |
|---|---|---|
| Indiana IOU SAIFI ex-MED | 0.71–1.37 | IURC Reliability Reports 2022, 2025 |
| Indiana IOU SAIDI ex-MED / with MED | 76–178 / 147–949 | same |
| Indiana IOU MED days per year | 3–15 | same |
| US IOU average (2015) | SAIFI 1.2 / SAIDI 136 ex-MED | LBNL (Eto) |
| Sustained outage records per year | NIPSCO 12,841 ex-MED (~480k customers) | NIPSCO 2024 VM report |
| TMED examples | 1.7–7.0 SAIDI-min | SCE 2015; NorthWestern 2024 |

### Acceptance tests (`scripts/acceptance_tests.py`)
1. Every `circuit_id`/`substation_id`/county matches `circuits_master.csv`. Customers-affected bounds hold.
2. T04 base values (times, customers, CMI, cause) are unchanged in the T19 event file (hash compare on those columns).
3. TMED recomputes from `daily_saidi_history_2019_2023.csv`. `med_flag` recomputes from 2024 daily SAIDI ≥ TMED. Every event on a MED day accrues by start date.
4. `reliability_indices_2024.csv` recomputes exactly from events. CAIDI = SAIDI/SAIFI. Annual = Σ months. Values equal `reliability_facts.yaml` and the T16 tree figures.
5. `reportable` recomputes from incidents with `params`. Every reportable incident has initial/update/final reports meeting `params` timing. ≥15% of reportable incidents use more than 60% of the allowed initial-report window (margin rule). Zero late or missing.
6. Planned notices comply. Margin rule applied.
7. App-A form values equal the incident and report-log rows for the stated incident ID.
8. Cause shares and monthly seasonality fall within the stated ranges. The top 1% of events by CI hold ≥25% of total CI (heavy-tail check).
9. Rendered outputs match canonical (§3.7).

### Length
5,000–7,000 words plus datasets.
```

---

## 4. Global recommendations for Sections 0–3

### G1 (Critical) — Add Wave-1 task **T04 "Shared operational master data"**

Ready-to-paste (insert after T03; add T04 to the §0.1 Wave 1 row and §0.2 index):

```markdown
## T04 — Shared operational master data

**Outputs:** `corpus/_global/ops/circuits_master.csv`, `substations_master.csv`, `outage_events_base.csv`, `outage_restoration_steps_base.csv`, `daily_saidi_history_2019_2023.csv`, `med_days.csv`, `reliability_facts.yaml`, `README.md`, `scripts/generate_ops_master.py` (seed 2024). **No regulatory content and no reportability fields.**

- `substations_master.csv`: 112 rows — `substation_id (e.g., LAF-012), service_center, county, primary_kv (12.47|34.5), supply_69kv_line_id, transformer_count, circuits`.
- `circuits_master.csv`: exactly 528 rows — `circuit_id (<SC>-<sub###>-<n>, e.g., LAF-012-3), substation_id, service_center (LAF|CRW|THT|FRK|DAN), county, voltage_kv, phase_type (backbone_3ph_with_laterals|1ph_dominant), oh_miles, ug_miles, customers_on_circuit, customers_residential, customers_nonresidential, critical_facilities, vm_category, last_trim_year`. Σ`oh_miles` = 14,200 ± 0.1. Σ`ug_miles` = 4,900 ± 0.1. Σ`customers_on_circuit` = 407,491 exactly. Customers allocated to counties in proportion to a plausible county split (Tippecanoe, Vigo, Hendricks, Boone largest; Benton, Warren, Carroll, Parke, Vermillion smallest). Urban circuits: higher customers and more UG; rural: long OH. `last_trim_year` consistent with the vegetation cycle categories (company practice, 4-yr backbone / 5-yr lateral).
- `daily_saidi_history_2019_2023.csv`: 1,826 daily rows of SAIDI (all causes); log-normal body; 2–7 days/yr far above body.
- `outage_events_base.csv`: 2024-01-01 → 2025-01-31 sustained outage records with physical fields only (see T19 schema minus `reportable` / IURC fields), plus `incident_id`. `outage_restoration_steps_base.csv` holds the step detail.
- `med_days.csv` and `reliability_facts.yaml`: TMED, 2024 MED dates, 2024 indices with and without MED, customers served denominator, and vegetation CI/CMI/SAIFI/SAIDI contributions (2022–2024; 2022–2023 as annual summaries).
- T16, T18 (circuit FK on meters) and T19 read these files and must not alter them.
```

Also extend §1.5 with: "Operational master data in `corpus/_global/ops/` (T04) is canonical for circuits, substations, outage history and reliability figures. Documents that state such figures must equal it."

### G2 (Major) — Replace §3.5 Datasets with a full data standard

```markdown
### 3.5 Datasets
- CSV is canonical: UTF-8, header row, comma, RFC 4180 quoting, no thousands separators, `.` decimal, empty string for null (no "NA"/"null"). Files > 25 MB may be `.csv.gz`.
- Dates `YYYY-MM-DD`. Timestamps `YYYY-MM-DDThh:mm` local time (America/Indiana/Indianapolis) **plus** a `utc_offset` column (`-05:00`/`-04:00`) wherever DST ambiguity is possible.
- IDs: one pattern per entity, declared in `data/README.md` and registered across documents (circuits `LAF-012-3`; meters `RPL-<vendor>-<7 digits>`; persons from §1.3; technicians `MT-###`; events `OE-2024-######`; incidents `INC-2024-#####`).
- Deterministic Python generator, fixed seed, `params` dict at top populated from the basis file (regulatory values never hard-coded twice). Company-practice parameters live in a separate `company_params` dict with comments.
- `data/README.md` contains, per dataset: purpose; row count; primary key; foreign keys; a data dictionary table (`field · type · unit · allowed values/range · source/derivation · nullable`); generation notes; and the acceptance-test results with timestamp.
- `data/_manifest.json`: file, rows, columns, sha256, generator script and seed.
- Each task's `scripts/acceptance_tests.py` exits non-zero on any failure. T90 re-runs it.
```

### G3 (Major) — Add §3.6a "Realism of compliance data" (anti-"look-good" rule)

```markdown
### 3.6a Realism of compliance data
- Baseline records comply 100% with Snapshot-1 parameters, but they must not be uniformly comfortable. For every timing, interval or count parameter tested by a dataset, the margin to the limit follows a realistic distribution: most records comfortable, and a documented share (task-specified, typically 10–20%) in the last 20% of the allowed window. No record is at or past the limit. Record each margin rule in `data/README.md`.
- Operational data shows ordinary imperfection that has no regulatory effect: unknown causes, re-coded causes, deferrals with notes, one rejected meter lot, budget variances with explanations, AMI functional failures. Do not "clean" data into perfection, and do not insert regulatory non-compliance.
- Do not tune results to flatter RPL. Use the benchmark ranges given in the task. Where RPL sits outside a benchmark, the document explains why (e.g., rural OH exposure).
```

### G4 (Major) — Add §3.7 "Rendered outputs" (Claude skills)

```markdown
### 3.7 Rendered outputs (derived; Markdown + CSV stay canonical)
After the canonical files pass acceptance tests, each operations/plan task (T16, T18, T19; optional for others) produces, under `corpus/docs/<DOC_ID>/render/`:
- **`<DOC_ID>_datasets.xlsx`** via the `xlsx` skill. Tabs: `README` (doc ID, version, extract date, seed, manifest); `Data_Dictionary` (from data/README.md); one tab per CSV (header frozen, filters on, ISO dates as real Excel dates, numeric types preserved, column widths set); `Summary` with live formulas (SUMIFS/COUNTIFS) reproducing every results table in the document; `Checks` tab showing formula-based reconciliations (e.g., Σ meters by technology vs. profile) that evaluate TRUE. Large files (meter registry) may be summarized by group, with a note pointing to the CSV.
- **Charts** via the `dataviz` skill, saved as PNG and SVG in `render/charts/`: T16 — monthly tree-related CI with and without MED; budget 2024 actual vs. 2025 by category; schedule miles by quarter × contractor. T18 — average-accuracy histogram by technology; group X̄ ± σ dot plot; tests by reason. T19 — monthly SAIFI/SAIDI with and without MED; daily SAIDI 2024 with TMED line; CI by cause; Pareto of incidents by CI. Every chart has a source line ("Source: RPL OMS extract 2025-02-10; dataset <file>").
- **`<DOC_ID>_v<version>.docx`** via the `docx` skill, and **`.pdf`** via the `pdf` skill (or docx→pdf conversion). Render: title block and document-control table on page 1; header (company, doc ID, version) and footer ("Uncontrolled when printed · Page X of Y"); numbered headings; real Word tables with repeated header rows; charts embedded at the section they illustrate with figure numbers; appendices as forms (bordered field tables); clause-ID HTML comments omitted from the rendering but clause numbers retained.
- A render check script asserts that every table value in the docx equals the canonical Markdown/CSV value. Rendered files are never edited by hand.
```

Update §0.3 layout to include `render/`, `data/README.md`, `data/_manifest.json`, `scripts/acceptance_tests.py`, and `_global/ops/`, `_global/reference/`.

### G5 (Major) — Strengthen §2.6 self-check with document depth rubric

Add items:
```markdown
6. Depth rubric (score each 0–2; all must score 2): (a) every required section present with the task's minimum tables/charts; (b) every procedure step names an owner role, system and record; (c) every form field is numbered and mapped; (d) every number stated in the text equals the datasets or §1; (e) each company-practice value is labeled and plausible against the task's benchmark table; (f) no section is a paraphrase of the rule without operational steps.
7. Dataset acceptance tests pass, and their output is appended to `data/README.md`.
8. Word count within the task's range (exclusive of data dictionaries).
```

### G6 (Major) — Formalize the research guardrail in §2.1 and §3.4

Add to §2.1:
```markdown
- Agents may research **form and magnitude** (structure, table design, typical volumes, distributions, costs, industry-standard definitions such as IEEE 1366 and ANSI C12 terminology) **only** from official or industry sources: state commission websites and dockets, *.gov, IEEE/ANSI/ASQ publications or summaries, EIA, national laboratories, and utility filings to regulators. No blogs, vendor marketing (except metering-test practitioner papers named in a task), forums or AI summaries.
- Research never supplies a regulatory value, even if a source states one; such values come only from the pack. If a source and the pack disagree, the pack wins silently.
- Every source used is recorded in the basis file under `sources[]`.
```
Add to the §3.4 schema:
```json
"sources": [
  {"url": "<url opened>", "title": "<title>", "accessed": "2025-01-xx", "used_for": "structure|magnitude|terminology", "notes": "<what was taken>"}
],
"company_practice_values": [
  {"clause_id": "<id>", "name": "<e.g., backbone trim cycle>", "value": "<value>", "benchmark_source": "<url or 'reviewer judgement'>"}
]
```
(Use a pre-2025-01 `accessed` value fiction-consistently, or record the real access date only in the basis file. The basis file is hidden, so real dates are acceptable there. Recommend real dates.)

### G7 (Major) — Separate "regulatory major event" from IEEE MED (glossary and §1.5)

Edit Appendix B: "**Major Event Day (MED)** — a day excluded from normalized reliability indices under IEEE 1366's 2.5-beta method (company reliability-reporting practice unless the pack prescribes it). Not the same as any reportability threshold or 'major event' definition in the IURC rules; use the pack's definition for reporting."

### G8 (Minor) — Preliminary-data labeling

Add to §1.2: "Documents approved in January–February 2025 that present 2024 results label them 'preliminary — data extracted <date ≤ approval date − 3 days>'. The extract dates are T18 2025-01-03, T16 2025-01-15 and T19 2025-02-10."

### G9 (Minor) — Orchestrator-verified industry reference files

Add a `corpus/_global/reference/` folder prepared by the orchestrator (human-verified, non-regulatory or as named by the pack): sampling-plan table extract (T18), IEEE 1366 MED method summary (T19). Generators cite these and never reconstruct paywalled standards from memory.

### G10 (Minor) — Appendix A additions

Add the URLs in §5 used by T16/T18/T19 to Appendix A, so generators study the same exemplars.

---

## 5. Sources actually opened

**Indiana**
1. IURC Electric Utility Reliability Report 2022 — https://secure.in.gov/iurc/files/2022-RELIABILITY-REPORT-Final-7-6-23.pdf
2. IURC Electric Reliability Report 2025 — https://secure.in.gov/iurc/files/2025-Reliability-Report_Final_7.1.26.pdf
3. OUCC, Tree trimming and vegetation management key cases — https://secure.in.gov/oucc/electric/key-cases-by-utility/tree-trimming-and-vegetation-management
4. IURC Tree Trimming page — https://secure.in.gov/iurc/tree-trimming (contains regulatory values; deliberately not transferred)
5. Duke Energy Indiana 2024 VM Report — https://iurc.portal.in.gov/_entity/sharepointdocumentlocation/d9117e76-f40b-f011-bae3-001dd803db57/bb9c6bba-fd52-45ad-8e64-a444aef13c39?file=43663_DEI_Submission%20of%202024%20Veg%20Management%20Report_032825.pdf
6. AES Indiana 2024 VM Annual Report — https://iurc.portal.in.gov/_entity/sharepointdocumentlocation/2419d113-f60e-f011-bae2-001dd80b1717/bb9c6bba-fd52-45ad-8e64-a444aef13c39?file=43663_AES%20IN_Submission%20of%20Vegetation%20Management%20Annual%20Report_033125.pdf
7. CenterPoint Indiana South 2024 VM Report and Plan — https://iurc.portal.in.gov/_entity/sharepointdocumentlocation/c668f043-f60e-f011-bae2-001dd80b1717/bb9c6bba-fd52-45ad-8e64-a444aef13c39?file=Cause%20No.%2043663_CEI%20South_2024%20Vegetation%20Managment%20Report%20and%20Plan_033125.pdf
8. NIPSCO 2024 VM Annual Report — https://iurc.portal.in.gov/_entity/sharepointdocumentlocation/e1f90252-6e0e-f011-bae2-001dd80846ac/bb9c6bba-fd52-45ad-8e64-a444aef13c39?file=43663_NIPSCO_Compliance%20Filing%20-%20Annual%20Report_03312025.pdf
9. I&M 2024 VM Annual Report — https://iurc.portal.in.gov/_entity/sharepointdocumentlocation/ee4365fe-4a0e-f011-bae2-001dd803db57/bb9c6bba-fd52-45ad-8e64-a444aef13c39?file=43663_IndMich_Submission%20of%20Annual%20Vegetation%20Management%20Report_033125.pdf
10. IURC State Form 54646 Report of Outage — https://forms.in.gov/Download.aspx?id=9574

**Other US — vegetation**
11. Eversource NH 2025 VM Annual Filing — https://puc.nh.gov/Regulatory/Docketbk/2019/19-057/LETTERS-MEMOS-TARIFFS/19-057-2024-11-15-EVERSOURCE-2025-VEGETATION-MANAGEMENT-ANNUAL-FILING.PDF

**Metering**
12. Entergy Arkansas Meter Test Plan — https://www.entergyarkansas.com/wp-content/uploads/2024/11/eal_ps12_mtp.pdf
13. Tescometering, In-Service/Statistical Test Programs — https://www.tescometering.com/wp-content/uploads/2024/03/Comparison-of-In-ServiceStatistical-Test-Programs-6-30-04.pdf
14. Tescometering, ECNE 2016 Meter Testing Programs — https://www.tescometering.com/wp-content/uploads/2024/04/ECNE-2016_Meter-Testing-Programs.pdf
15. Grayson RECC sample testing application (KY PSC 2009-00103) — https://psc.ky.gov/PSCSCF/2009%20cases/2009-00103/20090305_grayson_applicaton_.PDF
16. Narragansett Electric meter sampling filing (RI PUC D-04-16) — https://ripuc.ri.gov/sites/g/files/xkgbur841/files/eventsactions/docket/d-04-16-NEC%287.22.04%29.pdf
17. NH PUC Order 24,278 — https://www.puc.nh.gov/regulatory/Orders/2004orders/24278e.pdf
18. Eversource NH Meter Testing Program 2023 Annual Report — https://puc.nh.gov/regulatory/Docketbk/2018/18-162/LETTERS-MEMOS-TARIFFS/18-162_2023_12-28_EVERSOURCE_METER_TESTING_PROGRAM_2023_ANNUAL_RPT.PDF
19. Kentucky Power 2023 Meter Test Reports — https://psc.ky.gov/PSCSCF/Post Case Referenced Correspondence/2005 cases/2005-00276/20240314_Kentucky Power Company 2023 Meter Test Reports.pdf
20. PA PUC compliance letter, referee meter test — https://www.puc.pa.gov/pcdocs/1854076.pdf
21. Xcel/NSP 2023 Meter Testing Results (ND PSC PU-24-152) — https://www.psc.nd.gov/webdocs/case/24-0152/001-010.pdf
22. Open Exam Prep, ANSI/ASQ Z1.9 variables sampling (mechanics only) — https://open-exam-prep.com/study-guides/asq-cqi/ch8/variables-sampling-z1-9

**Reliability / outage records**
23. NorthWestern Energy 2024 Electric Reliability Report (MT PSC) — https://www.psc.mt.gov/_docs/Reports/Electric-Reliability/2024/2024_NWE_Electric_Reliability_Report.pdf
24. SCE 2015 Annual Reliability Report (CPUC) — https://files.cpuc.ca.gov/egy_Reliability_GO165Reports/ReliabilityRpts/2015/SCE_2015_%20Annual_Reliability_Report.pdf
25. LBNL (Eto), Reliability metrics and IEEE 1366 — https://eta-publications.lbl.gov/sites/default/files/7._eto_-_reliability_metrics_and_rvbp.pdf
26. USDA RUS Bulletin 1730A-119 — https://rd.usda.gov/sites/default/files/UEP_Bulletin_1730A-119.pdf

**Not verified by an opened source (reviewer judgement; agents must verify before use):** inside- vs. outside-ROW share of tree outages; customer-requested meter test rate (~0.1–0.2%/yr); counts of standards and test boards; exact Z1.9 code-letter/sample-size table (only n = 75 for lots ~4.8k–9.2k at Level II is evidenced by Kentucky Power).
