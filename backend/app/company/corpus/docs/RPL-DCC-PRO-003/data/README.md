# RPL-DCC-PRO-003 Dataset Documentation

**Document:** RPL-DCC-PRO-003 v4.2 — Service Interruption Reporting Procedure  
**Extract date:** 2025-02-10 (preliminary — 2024 data)  
**Generator:** `scripts/generate_outage_data.py`, seed 2024  
**Regulatory basis:** 170 IAC 4-1-23; 170 IAC 4-1-3; 170 IAC 4-9-7  
**Law as-of:** 2024-12-31  

---

## Datasets Overview

| File | Rows | Primary Key | Purpose |
|---|---|---|---|
| `outage_incidents_2024-01-01_2025-01-31.csv` | 9,509 | `incident_id` | T04 incident base + IURC regulatory columns |
| `outage_events_2024-01-01_2025-01-31.csv` | 10,928 | `event_id` | T04 event base + med_flag override + reportable |
| `iurc_report_log_2024-01-01_2025-01-31.csv` | 59 | `report_id` | One row per IURC report submission |
| `planned_interruption_notices_2024.csv` | 623 | `incident_id` | One row per planned interruption |
| `reliability_indices_2024.csv` | 13 | `period` | Monthly (×12) + annual reliability indices |

---

## 1. `outage_incidents_2024-01-01_2025-01-31.csv`

**Purpose:** One row per outage incident (a group of related outage events). All T04 base columns are preserved unchanged. T19 adds regulatory columns: `threshold_crossed_ts`, `reportable`, `criteria_met`, `iurc_initial_report_ts`, `iurc_update_count`, `iurc_final_report_ts`.

**Row count:** 9,509 (2024-01-01 through 2025-01-31)  
**Primary key:** `incident_id`  
**Foreign keys:** None (self-contained; events join via `incident_id`)

### Data Dictionary

| Field | Type | Unit | Allowed Values / Range | Source / Derivation | Nullable |
|---|---|---|---|---|---|
| `incident_id` | string | — | `INC-2024-nnnnn` | T04 base | No |
| `incident_type` | enum | — | `single_event`, `storm`, `planned` | T04 base | No |
| `first_start_ts` | datetime | local | `YYYY-MM-DDThh:mm:ss` | T04 base | No |
| `utc_offset` | string | — | `-05:00`, `-04:00` | T04 base | No |
| `utility_aware_ts` | datetime | local | `YYYY-MM-DDThh:mm:ss` | T04 base | No |
| `peak_customers_out` | int | customers | ≥ 1 | T04 base | No |
| `peak_ts` | datetime | local | `YYYY-MM-DDThh:mm:ss` | T04 base | No |
| `total_customers_affected` | int | customers | ≥ 1 | T04 base | No |
| `counties_affected` | string | — | pipe-delimited county names | T04 base | No |
| `municipalities_affected` | string | — | pipe-delimited or empty | T04 base | Yes |
| `critical_facilities_affected` | int | facilities | ≥ 0 | T04 base | No |
| `restored_ts` | datetime | local | `YYYY-MM-DDThh:mm:ss` | T04 base | No |
| `etr_first_ts` | datetime | local | `YYYY-MM-DDThh:mm:ss` | T04 base | No |
| `primary_cause_category` | enum | — | vegetation, equipment, animal, weather, public, power_supply, operational, planned, unknown | T04 base | No |
| `threshold_crossed_ts` | datetime | local | `YYYY-MM-DDThh:mm` or empty | T19: `first_start_ts` + 120 min if both criteria met | Yes |
| `reportable` | enum | — | `Y`, `N` | T19: computed from params (170 IAC 4-1-23(b)(1)(A)) | No |
| `criteria_met` | string | — | pipe-delimited criteria labels or empty | T19: `peak_customers>=5000\|duration_min>=120` if reportable | Yes |
| `iurc_initial_report_ts` | datetime | local | `YYYY-MM-DDThh:mm` or empty | T19: derived from report_log | Yes |
| `iurc_update_count` | int | reports | ≥ 0 or empty | T19: count of update reports in report_log | Yes |
| `iurc_final_report_ts` | datetime | local | `YYYY-MM-DDThh:mm` or empty | T19: derived from report_log | Yes |

### Generation Notes

- T04 base columns are hash-checked in acceptance test T2 and must not be altered.
- `reportable = "Y"` when: `incident_type != "planned"` AND `peak_customers_out >= 5,000` AND `(restored_ts - first_start_ts) >= 120 minutes`. Source: 170 IAC 4-1-23(b)(1)(A).
- `threshold_crossed_ts` = `first_start_ts` + 120 minutes (the later of the two criterion clocks; peak ≥ 5,000 is treated as simultaneous with start since the T04 base records the peak at `first_start_ts`).
- `iurc_initial_report_ts` / `iurc_final_report_ts` are summary columns derived from the IURC report log.

### Margin Rule

Per §3.6a, 15–20% of reportable incidents use more than 60% of the allowed initial-report window (the interval between `threshold_crossed_ts` and the next scheduled reporting time). In this dataset, 2 of 10 reportable incidents (20%) use 75% of the window. The remaining incidents use 5–35% of the window.

---

## 2. `outage_events_2024-01-01_2025-01-31.csv`

**Purpose:** One row per sustained outage record / device operation. All T04 base columns preserved. T19 overrides `med_flag` and `med_date` to align with the computed MED dates (some T04 base events on MED days were incorrectly flagged N for non-storm incidents; T19 corrects these using the confirmed MED date list from `reliability_facts.yaml`). T19 adds `reportable` (copied from the parent incident).

**Row count:** 10,928 (2024-01-01 through 2025-01-31)  
**Primary key:** `event_id`  
**Foreign keys:** `incident_id` → `outage_incidents_2024-01-01_2025-01-31.csv`; `circuit_id` → `circuits_master.csv`

### Data Dictionary

| Field | Type | Unit | Allowed Values / Range | Source / Derivation | Nullable |
|---|---|---|---|---|---|
| `event_id` | string | — | `EVT-2024-nnnnnnn` | T04 base | No |
| `incident_id` | string | — | `INC-2024-nnnnn` | T04 base | No |
| `start_ts` | datetime | local | `YYYY-MM-DDThh:mm:ss` | T04 base | No |
| `end_ts` | datetime | local | `YYYY-MM-DDThh:mm:ss` | T04 base | No |
| `utc_offset` | string | — | `-05:00`, `-04:00` | T04 base | No |
| `duration_min` | int | minutes | ≥ 0 | T04 base | No |
| `customers_affected` | int | customers | ≥ 1 | T04 base | No |
| `customer_minutes` | int | cust-min | ≥ 0 | T04 base | No |
| `restoration_steps` | int | steps | ≥ 1 | T04 base | No |
| `circuit_id` | string | — | `{SC}-{nnn}-{n}` | T04 base | No |
| `substation_id` | string | — | `{SC}-{nnn}` | T04 base | No |
| `service_center` | enum | — | LAF, CRW, THT, FRK, DNV | T04 base | No |
| `county` | string | — | 14 service-territory counties | T04 base | No |
| `municipality` | string | — | city name or `unincorporated` | T04 base | No |
| `device_type` | enum | — | substation_breaker, feeder_breaker, recloser, sectionalizer, fuse, transformer, service, 69kv_line | T04 base | No |
| `device_id` | string | — | device identifier | T04 base | No |
| `outage_level` | enum | — | supply, substation, feeder, lateral, transformer, service | T04 base | No |
| `cause_category` | enum | — | vegetation, equipment, animal, weather, public, power_supply, operational, planned, unknown | T04 base | No |
| `cause_code` | string | — | see App-D cause-code table | T04 base | No |
| `tree_location` | enum | — | inside_row, outside_row, unknown, n/a | T04 base | No |
| `weather_code` | string | — | weather description or empty | T04 base | Yes |
| `intentional` | enum | — | `Y`, `N` | T04 base | No |
| `critical_facilities_affected` | int | facilities | ≥ 0 | T04 base | No |
| `detection_source` | enum | — | ami_last_gasp, scada, customer_call, field | T04 base | No |
| `med_flag` | enum | — | `Y`, `N` | T19: `Y` if `start_ts[:10]` in confirmed MED dates list | No |
| `med_date` | date | — | `YYYY-MM-DD` or empty | T19: populated when `med_flag = "Y"` | Yes |
| `notes` | string | — | free text | T04 base | Yes |
| `reportable` | enum | — | `Y`, `N` | T19: copied from parent incident `reportable` | No |

### Generation Notes

- Customer-minutes accrue to the day the event **begins** (IEEE 1366 begin-date convention).
- `med_flag = "Y"` for all events whose `start_ts` date is in `{2024-03-15, 2024-05-22, 2024-07-04, 2024-08-09, 2024-12-23}`. T04 base events on MED days with `med_flag = "N"` (163 events for non-storm incidents) are corrected in the T19 file; `med_flag` is not in the hash-checked base columns.
- `reportable` is a denormalized join column from the incident file for convenience.

---

## 3. `iurc_report_log_2024-01-01_2025-01-31.csv`

**Purpose:** One row per IURC report submission. Non-reportable incidents have no rows. Contains initial, update(s), and final reports for each of the 10 reportable incidents.

**Row count:** 59  
**Primary key:** `report_id`  
**Foreign keys:** `incident_id` → `outage_incidents_2024-01-01_2025-01-31.csv`

### Data Dictionary

| Field | Type | Unit | Allowed Values / Range | Source / Derivation | Nullable |
|---|---|---|---|---|---|
| `report_id` | string | — | `RPT-YYYY-nnnnn{A-Z}` | generated | No |
| `incident_id` | string | — | `INC-2024-nnnnn` | joins to incidents | No |
| `report_type` | enum | — | initial, update, final | T19: determined by position | No |
| `submitted_ts` | datetime | local | `YYYY-MM-DDThh:mm` | T19: computed per 170 IAC 4-1-23(b)(2) | No |
| `channel` | enum | — | email, phone | T19: email (preferred) | No |
| `form_revision` | string | — | `State Form 54646` | T19: company practice | No |
| `customers_affected_reported` | int | customers | ≥ 1 | T19: `peak_customers_out` | No |
| `customers_still_out_reported` | int | customers | ≥ 0 | T19: decreasing profile | No |
| `etr_reported` | datetime | local | `YYYY-MM-DDThh:mm` | T19: estimated | No |
| `cause_reported` | string | — | text description | T19: `under investigation` initially | No |
| `reported_by_person_id` | string | — | P23 | T19: Kevin Adeyemi, DCC Manager | No |

### Timeliness Notes

- All initial reports are submitted at or before the next scheduled reporting interval after `threshold_crossed_ts`. Source: 170 IAC 4-1-23(b)(1) and (b)(2).
- Update reports are submitted at each subsequent scheduled interval while customers remain above the threshold.
- Final reports are submitted at the next interval after restoration below the threshold.
- 2 of 10 reportable incidents (20%) use more than 60% of the allowed initial-report window (margin rule: ≥ 15% required).

---

## 4. `planned_interruption_notices_2024.csv`

**Purpose:** One row per planned interruption (623 rows for 2024). Records advance notice compliance per 170 IAC 4-1-23(c).

**Row count:** 623  
**Primary key:** `incident_id`  
**Foreign keys:** `incident_id` → `outage_incidents_2024-01-01_2025-01-31.csv`

### Data Dictionary

| Field | Type | Unit | Allowed Values / Range | Source / Derivation | Nullable |
|---|---|---|---|---|---|
| `incident_id` | string | — | `INC-2024-nnnnn` | T04 planned incidents | No |
| `notice_method` | enum | — | email, telephone, in_person | T19: email if >50 customers | No |
| `notice_sent_ts` | datetime | local | `YYYY-MM-DDThh:mm` or empty | T19: ≥2 days before start (company practice) | Yes |
| `customers_noticed` | int | customers | ≥ 0 | T19: equals customers_affected when notice sent | No |
| `customers_affected` | int | customers | ≥ 1 | T04 incident | No |
| `exception_code` | string | — | empty, `duration_lte_1hr`, `emergency`, `safety` | T19: per 170 IAC 4-1-23(c) | Yes |
| `scheduled_start_ts` | datetime | local | `YYYY-MM-DDThh:mm` | T04 incident | No |
| `actual_start_ts` | datetime | local | `YYYY-MM-DDThh:mm` | T04 incident | No |

### Compliance Notes

- The notice obligation applies only when the planned interruption is expected to exceed 1 hour (170 IAC 4-1-23(c)).
- Planned interruptions ≤ 1 hour use `exception_code = "duration_lte_1hr"` and have blank `notice_sent_ts`.
- All planned interruptions > 1 hour have `notice_sent_ts` at least 2 days before `scheduled_start_ts` (company practice).

---

## 5. `reliability_indices_2024.csv`

**Purpose:** 12 monthly rows plus one annual row with SAIFI, SAIDI, CAIDI with and without MED for calendar year 2024. Source data: `reliability_facts.yaml` (T04 canonical).

**Row count:** 13 (12 months + 1 annual)  
**Primary key:** `period`  
**Foreign keys:** None

### Data Dictionary

| Field | Type | Unit | Allowed Values / Range | Source / Derivation | Nullable |
|---|---|---|---|---|---|
| `period` | string | — | `2024-MM` or `2024-Annual` | generated | No |
| `customers_served` | int | customers | 403,997–407,491 | T04 facts.yaml | No |
| `ci_all` | int | customer-interruptions | ≥ 0 | T04 facts.yaml (with MED) | No |
| `cmi_all` | int | customer-minutes | ≥ 0 | T04 facts.yaml (with MED) | No |
| `saifi_all` | float | interr/customer | ≥ 0 | T04 facts.yaml | No |
| `saidi_all` | float | min/customer | ≥ 0 | T04 facts.yaml | No |
| `caidi_all` | float | minutes | ≥ 0 | T04 facts.yaml | No |
| `ci_ex_med` | int | customer-interruptions | ≥ 0 | T04 facts.yaml (ex-MED) | No |
| `cmi_ex_med` | int | customer-minutes | ≥ 0 | T04 facts.yaml (ex-MED) | No |
| `saifi_ex_med` | float | interr/customer | ≥ 0 | T04 facts.yaml | No |
| `saidi_ex_med` | float | min/customer | ≥ 0 | T04 facts.yaml | No |
| `caidi_ex_med` | float | minutes | SAIDI_ex_med / SAIFI_ex_med | T04 facts.yaml | No |
| `med_days` | int | days | 0–5 per month | count from facts.yaml med_dates_2024 | No |
| `tmed_saidi_min` | float | min/customer | 137.1872 | IEEE 1366 2.5β, 2019–2023 study period | No |
| `saifi_ex_med_ex_planned` | float | interr/customer | ≥ 0 | T04 facts.yaml (planned CI negligible) | No |
| `saidi_ex_med_ex_planned` | float | min/customer | ≥ 0 | T04 facts.yaml | No |

### Key Values

| Metric | Annual 2024 |
|---|---|
| SAIFI (with MED) | 1.5723 |
| SAIDI (with MED) | 262.20 min/customer |
| SAIFI (ex-MED) | 1.0987 |
| SAIDI (ex-MED) | 138.31 min/customer |
| CAIDI (ex-MED) | 125.88 minutes |
| MED days | 5 |
| TMED | 137.19 min/customer |

### Denominator

Annual `customers_served` = 405,805 (mid-year value from T04 facts.yaml). Monthly denominators vary from 403,997 (January) to 407,331 (December). Per company practice, the mid-year count is used for annual index computation; the rule does not prescribe a specific denominator date. Source: 170 IAC 4-1-23(e)(3); `reliability_facts.yaml`.

---

## ID Patterns

| Entity | Pattern | Example |
|---|---|---|
| Outage incident | `INC-2024-nnnnn` | `INC-2024-00001` |
| Outage event | `EVT-2024-nnnnnnn` | `EVT-2024-0009567` |
| IURC report | `RPT-{incident-suffix}{letter}` | `RPT-2024-00001A` |
| Circuit | `{SC}-{nnn}-{n}` | `LAF-012-3` |
| Service centers | LAF (Lafayette), CRW (Crawfordsville), THT (Terre Haute), FRK (Frankfort), DNV (Danville) | — |
