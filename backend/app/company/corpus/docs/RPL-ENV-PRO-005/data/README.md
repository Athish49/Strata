# RPL-ENV-PRO-005 Dataset README

**Document:** RPL-ENV-PRO-005 Spill Response & Reporting Procedure v3.1
**Extract date:** 2025-03-05
**Generator seed:** 2024
**Law as-of:** 2024-12-31

---

## Dataset: spill_events_2024.csv

**Purpose:** Synthetic 2024 spill event log for Rockridge Power & Light Company (RPL). Covers all substance releases from RPL equipment, vehicles and facilities recorded in the EHS Incident Management System (EHS-IMS) during calendar year 2024. Supports reportability decision table validation, record series RRS-ENV-001, and App-E worked examples.

**Row count:** 95

**Primary key:** `event_id` (SPL-2024-nnnn, unique)

**Foreign keys:** `service_center` → corpus/_global/company_profile.yaml service_centers; `county` → §1.1 county list

---

## Data Dictionary

| Field | Type | Unit | Allowed Values / Range | Source / Derivation | Nullable |
|---|---|---|---|---|---|
| event_id | string | — | SPL-2024-0001 … SPL-2024-nnnn | EHS-IMS sequence | No |
| discovered_ts | datetime | local (America/Indiana/Indianapolis) | YYYY-MM-DDTHH:MM; within 2024 | Synthetic | No |
| stopped_ts | datetime | local | YYYY-MM-DDTHH:MM | discovered_ts + 0.25–4 hours | No |
| utc_offset | string | — | -05:00 (Nov–Mar) / -04:00 (Apr–Oct) | Indiana DST rule | No |
| service_center | string | — | LAF, CRW, THT, FRK, DAN | §1.1 | No |
| county | string | — | 14 RPL counties per §1.1 | §1.1 | No |
| source_type | string | — | pole_transformer, padmount_transformer, substation_equipment, standby_generator, fleet_vehicle, bucket_truck_hydraulic, fueling | §1.6 asset classes | No |
| rpl_classification | string | — | facility_equipment, facility_equipment_inside_boundary, facility_belly_tank, transportation_in_transit, transportation_at_worksite, facility_fuel_storage | RPL-ENV-PRO-005 §7.1 | No |
| substance | string | — | mineral_oil, diesel, gasoline, hydraulic_fluid, other | §1.6 Table S asset-substance pairing | No |
| pcb_status_code | string | — | NP-T, NP-M, UNK, PCB-C, PCB | §1.6 Table S WAM codes | No |
| volume_released_gal | decimal | US gallons | > 0 | Triangular distribution over §1.6 nameplate ranges by source_type | No |
| volume_recovered_gal | decimal | US gallons | 0 … volume_released_gal | Triangular distribution over recovery fractions | No |
| receiving_medium | string | — | impervious, soil_inside_boundary, soil_beyond_boundary, surface_water, storm_drain, sewer | Company-practice classification per §7.1 | No |
| special_area_flag | string | — | Y, N | GIS screening result per §7.5; Y if any ENV_* layer triggered | No |
| cause | string | — | vehicle_strike, storm_wind, lightning, equipment_failure, vandalism_theft, hose_failure, overfill, other | Operational taxonomy | No |
| reportable | string | — | Y, N | Company-practice decision table §7.2 (no regulatory thresholds — 327 IAC 2-6.1 is out_of_scope_reference) | No |
| decision_row | string | — | T7-1 through T7-6 | First matching row in §7.2 table | No |
| exclusion_applied | string | — | RPL-ENV-PRO-005:7.3.1, RPL-ENV-PRO-005:7.3.2, or blank | Populated only when reportable = N | Yes |
| idem_report_ts | datetime | local | YYYY-MM-DDTHH:MM; blank if not reportable | Company practice: within 2-hour internal target of determination | Yes |
| idem_incident_no | string | — | IDEM-ER-2024-nnnnn | Assigned by IDEM; synthetic | Yes |
| update_count | integer | — | 0, 1, 2 | Number of IDEM update calls per §8.4 | No |
| third_party_notice_required | string | — | Y, N | Y when medium = surface_water or special_area_flag = Y | No |
| third_party_notice_ts | datetime | local | YYYY-MM-DDTHH:MM | Within 4 hours of determination when required | Yes |
| closed_date | date | — | YYYY-MM-DD within 2024 | EHS-IMS close date | No |
| compliance_confirmation_requested | string | — | Y, N | Y when reportable = Y and medium in (surface_water, storm_drain) | No |

---

## Generation Notes

- Generator: `scripts/generate_spill_data.py`, seed 2024 (deterministic).
- `params = {}` — the grounding pack for 327 IAC 2-6.1 is empty (rule is an out_of_scope_reference); no regulatory thresholds are hard-coded.
- Substance distribution: ~78% mineral oil (pole_transformer + padmount_transformer + substation_equipment), ~16% diesel (standby_generator + fleet_vehicle + fueling), ~6% hydraulic_fluid (bucket_truck_hydraulic) — target ≥ 75% mineral oil, achieved.
- Volume ranges: bounded by §1.6 Table S nameplate volumes per source_type.
- App-E events (SPL-2024-0033, SPL-2024-0071, SPL-2024-0088) are force-inserted to ensure worked examples are present in the dataset.
- Baseline compliance: all reportable events (reportable = Y) have IDEM notification within the 2-hour company performance target; no record is at or past the limit.
- DST: utc_offset = -05:00 for months 11, 12, 1, 2, 3; -04:00 for months 4–10.

---

## Margin Rule (§3.6a)

For reportable events with an IDEM notification timestamp, the elapsed time from reportability determination to IDEM contact is distributed over 0.2–1.8 hours (within the 2-hour company target). No record meets or exceeds the 2-hour target.

-
---

## Acceptance Test Results (2026-10-07 01:01)

**STATUS: PASS** — all acceptance tests passed

