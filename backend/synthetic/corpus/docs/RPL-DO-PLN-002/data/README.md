# RPL-DO-PLN-002 Data Dictionary

**Document:** RPL-DO-PLN-002 Vegetation Management Plan 2025  
**Company:** Rockridge Power & Light Company  
**Data extract date:** 2025-01-15 (preliminary)  
**Generator:** `scripts/generate_vm_data.py`  
**Seed:** 2024  

All five datasets are synthetically generated, seeded at 2024, and consistent with the plan values stated in RPL-DO-PLN-002_v2025.1.md and the T16 grounding pack.

---

## 1. vm_circuit_schedule_2025.csv

**Description:** The 2025 routine cycle trimming schedule for Rockridge Power & Light Company's distribution system. Each row represents one distribution circuit scheduled for routine vegetation management in calendar year 2025. The 111 circuits represent the annual capacity-constrained target (~3,170 OH miles) out of 425 eligible circuits system-wide. Priority ranking follows the four-factor logic in §2.4: tree CI 2024, cycle overdue status, circuit category, and geographic contiguity.

**Row count:** 111  
**Primary key:** `circuit_id`  
**Source:** Generated (seed 2024); circuit IDs and service-center/county assignments consistent with RPL system geography. Priority ranks and tree CI values consistent with §25 Top-10 table in the plan document.

| Column | Type | Description |
|---|---|---|
| circuit_id | string | Unique circuit identifier (format: `{SC}-{SUB}-{NUM}`, e.g. DAN-004-1) |
| substation_id | string | Parent substation identifier |
| service_center | string | RPL service center code: DAN, LAF, FRK, CRW, THT |
| county | string | Indiana county name |
| voltage_kv | float | Nominal voltage (12.47 or 34.5 kV) |
| phase_type | string | Circuit phase configuration (e.g. backbone_3ph_with_laterals, 1ph_dominant) |
| vm_category | string | Vegetation management category: backbone, lateral_dominant, urban_ug_dominant |
| cycle_years | int | Assigned trim cycle in years (4, 5, or 6 per §8.1 company practice) |
| last_trim_year | int | Year of most recent completed trim cycle |
| scheduled_quarter_2025 | string | Planned work quarter: Q1, Q2, Q3, Q4 |
| overhead_miles | float | Overhead line miles in scope for this circuit |
| contractor | string | Assigned contractor: Contractor A (LAF/FRK/DAN) or Contractor B (CRW/THT) |
| est_cost_usd | int | Estimated cost in USD for this circuit's trim work |
| planned_start_date | date | Planned mobilization start date (YYYY-MM-DD) |
| planned_end_date | date | Planned completion date (YYYY-MM-DD) |
| notice_batch_id | string | WAM notice batch identifier (format VMN-2025-###) |
| notice_letter_date | date | Date VM-F-004 letter mailed to customers (>=21 days before planned start) |
| door_hanger_start_date | date | Date door-hanger delivery begins (3 days before planned start) |
| customers_on_circuit | int | Number of customers served by this circuit |
| tree_ci_2024 | int | Number of tree-related sustained customer interruption events in 2024 (OMS) |
| priority_rank | int | Circuit priority rank (1=highest) for 2025 scheduling |
| schedule_note | string | Optional note (e.g. overdue flag, hot-spot designation) |

---

## 2. vm_work_completed_2024.csv

**Description:** Summary of 2024 routine cycle trimming program results by circuit. Each row represents one circuit for which trimming work was completed or substantially completed in calendar year 2024. The 2024 program planned 3,152 distribution OH miles (per §8.2) and achieved 3,104 OH miles (98.5% of plan). Urban/UG circuits show a large negative variance (-51.2%) due to Q3 storm-restoration crew redeployment (§23.1).

**Row count:** 106  
**Primary key:** `circuit_id`  
**Source:** Generated (seed 2024); aggregate totals consistent with §23.1 budget-vs-actual tables in the plan document.

| Column | Type | Description |
|---|---|---|
| circuit_id | string | Unique circuit identifier |
| substation_id | string | Parent substation identifier |
| service_center | string | RPL service center code |
| county | string | Indiana county name |
| voltage_kv | float | Nominal voltage |
| vm_category | string | Vegetation management category |
| contractor | string | Contractor that performed the work |
| planned_miles | float | Overhead miles planned for 2024 |
| actual_miles | float | Overhead miles actually completed |
| completion_date | date | Date work was completed (YYYY-MM-DD) |
| actual_cost_usd | int | Actual cost in USD |
| audit_pass_pct | float | Post-work audit pass percentage (0–100) |

---

## 3. vm_tree_outages_2024.csv

**Description:** Monthly aggregated tree-related outage statistics for 2024, broken out by tree location (inside vs. outside ROW) and MED flag. Derived from the operational outage events base (`outage_events_base.csv`, vegetation cause_category, year 2024). Each row represents one combination of month, tree_location, and med_flag. Annual totals are consistent with §23.3 (tree SAIFI ex-MED = 0.292; tree share of all-cause SAIFI ex-MED = 26.6%; customers served = 405,805).

**Row count:** 51  
**Primary key:** Composite (`month`, `tree_location`, `med_flag`)  
**Source:** Generated (seed 2024); aggregate annual values match §23.3 outage table and §25.1 reliability trend table in the plan document.

| Column | Type | Description |
|---|---|---|
| month | int | Calendar month (1–12) |
| tree_location | string | Location relative to RPL ROW: inside_row, outside_row, unknown |
| med_flag | string | Major Event Day designation: Y (MED) or N (non-MED) |
| sustained_outages | int | Number of sustained tree-related outage events |
| customer_interruptions | int | Customer interruptions (CI) attributable to tree events |
| customer_minutes | int | Customer minutes interrupted (CMI) attributable to tree events |
| tree_saifi_contribution | float | SAIFI contribution from tree events this row (CI / 405,805 customers) |
| tree_saidi_contribution | float | SAIDI contribution from tree events this row (CMI / 405,805 customers) |
| all_cause_outages | int | Total all-cause outage events in this month |
| all_cause_ci | int | Total all-cause customer interruptions in this month |
| tree_share_of_saifi_pct | float | Tree CI as percentage of all-cause CI for this row |

---

## 4. vm_budget_2024_2025.csv

**Description:** Side-by-side budget comparison of 2024 actuals vs. 2025 plan for each of the eight VM program budget lines (BDG-001 through BDG-008). Values are consistent with §23.2 (2024 actuals) and §24 (2025 budget) in the plan document. 2024 total actual: $41,642,488; 2025 total budget: $41,600,000 (0.1% decrease).

**Row count:** 8  
**Primary key:** `line_id`  
**Source:** Generated (seed 2024); all dollar values match §23.2 and §24 tables in the plan document exactly.

| Column | Type | Description |
|---|---|---|
| line_id | string | Budget line identifier (BDG-001 through BDG-008) |
| category | string | Budget category description (matches §24 Table T24) |
| cost_type | string | Accounting classification: O&M or Capital |
| system | string | Applicable system: distribution or subtransmission |
| budget_2024_usd | int | Original 2024 budget in USD |
| actual_2024_usd | int | 2024 actual expenditure in USD |
| variance_usd | int | Variance: actual minus budget (negative = favorable) |
| variance_note | string | Explanation of significant variances |
| budget_2025_usd | int | Approved 2025 budget in USD (per §24 Table T24) |
| unit | string | Unit of measure for quantity-based lines (e.g. OH-miles, trees, acres) |
| units_2025 | int | Planned quantity in 2025 |
| unit_cost_2025 | float | Implied unit cost for 2025 (budget_2025_usd / units_2025) |

---

## 5. vm_customer_contacts_2024.csv

**Description:** Log of all 542 vegetation management customer contacts received by RPL in calendar year 2024. Each row represents one logged contact. Category distribution, escalation counts, and IURC CAD referral counts match §23.4 Table T23D. All 2024 easement documentation requests (29) were answered within 5 business days per §10.2 and 170 IAC 4-9-3(b). The single IURC CAD referral involved a removal dispute resolved at the Consumer Affairs level.

**Row count:** 542  
**Primary key:** `contact_id`  
**Source:** Generated (seed 2024); category totals and escalation/referral counts match §23.4 Table T23D in the plan document.

| Column | Type | Description |
|---|---|---|
| contact_id | string | Unique contact log identifier (format VMC-2024-####) |
| received_date | date | Date contact was received (YYYY-MM-DD) |
| channel | string | Intake channel: phone, written, in-person, online |
| circuit_id | string | Circuit associated with the contact (where applicable) |
| category | string | Contact category: notice_question, debris, customer_request_trim, tree_health, refusal_of_work, property_damage, storm_debris, easement_documentation_request, removal_dispute, other |
| escalated_to_second_rep | string | Whether a second authorized representative was involved: Y or N |
| iurc_cad_referral | string | Whether the contact escalated to an IURC Consumer Affairs Division referral: Y or N |
| resolution | string | Free-text description of how the contact was resolved |
| closed_date | date | Date the contact was closed (YYYY-MM-DD) |
| days_to_close | int | Calendar days from received_date to closed_date |
| iurc_info_provided | string | Whether IURC Consumer Affairs contact information was provided to the customer: Y or N |

---

## Margin Rules and Acceptance Tests

- Total OH miles in vm_circuit_schedule_2025.csv must sum to 3,169.7 ± 0.5 mi (within 2% of 3,152 annual target per §8.2).
- vm_circuit_schedule_2025.csv must contain exactly 111 rows.
- vm_customer_contacts_2024.csv must contain exactly 542 rows.
- vm_budget_2024_2025.csv sum of actual_2024_usd must equal 41,642,488.
- vm_budget_2024_2025.csv sum of budget_2025_usd must equal 41,600,000.
- vm_tree_outages_2024.csv sum of customer_interruptions where med_flag='N' must equal 118,607 (tree CI ex-MED per §23.3).
- No circuit_id in vm_circuit_schedule_2025.csv may appear in vm_work_completed_2024.csv (2025 schedule circuits are distinct from 2024 completed circuits; different cycle rotation).

---

*See Appendix F of RPL-DO-PLN-002_v2025.1.md for a summary table. Manifest and SHA-256 checksums: data/_manifest.json.*
