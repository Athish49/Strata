# Data Directory — RPL-SAF-PRO-009 v2.0
# Electrical Accident & Incident Reporting Procedure

## Dataset: incident_log_2024.csv

**Purpose:** Synthetic 2024 incident log for Rockridge Power & Light Company (IURC utility ID 99012). Supports App-D worked example and App-E data dictionary in RPL-SAF-PRO-009 v2.0. Used for acceptance testing of the IURC notification decision logic.

**Row count:** 285 (within the 260–340 specification)
**Primary key:** `incident_id` (format: `INC-2024-#####`)
**Seed:** 2024
**Generator:** `../scripts/generate_incident_data.py`
**Law as-of:** 2024-12-31

### Foreign Keys

- `outage_event_id` → `corpus/_global/ops/outage_events_base.csv` (`event_id`); nullable (empty string if no associated outage)

### Data Dictionary

See Appendix E of RPL-SAF-PRO-009_v2.0.md for the full data dictionary table.

| Field | Type | Unit / Allowed Values | Nullable | Source / Derivation |
|---|---|---|---|---|
| incident_id | string | INC-2024-##### | No | EHS-IMS ID format (company practice) |
| event_ts | string | YYYY-MM-DDThh:mm (local ET) | No | Generated; 2024-01-01 to 2024-12-31 |
| utc_offset | string | -05:00 or -04:00 | No | DST-aware (2024-03-10 to 2024-11-03 = -04:00) |
| service_center | string | LAF, CRW, THT, FRK, DAN | No | Company practice |
| county | string | Indiana county name | No | Derived from service_center |
| person_type | string | employee, contractor, public, none | No | Category-driven |
| category | string | VEH, ENRG, FALL, STRIK, FIRE, CUST, DIGN, EQP, PROP, NMSSSIF, OTHER | No | §7.1 Table S-INC |
| tier | string | 1, 2, 3, 4 | No | §7.2 severity tiers |
| energized_contact | string | Y, N | No | Y for ENRG or energized-hazard events |
| voltage_class | string | 120/240V, 12.47kV, 34.5kV, 69kV, unknown, "" | Yes | RPL standard voltages; empty if not energized |
| injury_severity | string | none, first_aid, medical_treatment, restricted, lost_time, hospitalized, fatal | No | Tier-consistent |
| property_damage_est_usd | integer | ≥ 0 | No | 0 if no damage |
| outage_event_id | string | EVT-2024-###### or "" | Yes | Cross-ref to outage_events_base.csv |
| iurc_reportable | string | Y, N | No | Y iff injury_severity = "fatal" and nexus present (170 IAC 4-1-24) |
| informed_ts | string | YYYY-MM-DDThh:mm or "" | Yes | Only for iurc_reportable = Y |
| business_hours | string | Y, N, "" | Yes | Only for iurc_reportable = Y; event_ts vs. IURC hours |
| iurc_phone_ts | string | YYYY-MM-DDThh:mm or "" | Yes | Only for iurc_reportable = Y |
| iurc_written_ts | string | YYYY-MM-DDThh:mm or "" | Yes | Only for iurc_reportable = Y |
| capa_count | integer | 0–6 | No | Tier-consistent |
| investigation_closed_date | string | YYYY-MM-DD or "" | Yes | Empty if not closed by 2024-12-31 |

### Generation Notes

- Seed 2024 produces a deterministic output. Re-running `generate_incident_data.py` with the same seed produces an identical CSV.
- The single IURC-reportable row (`INC-2024-00142`, category CUST, fatal) is hard-coded in the generator to ensure timestamps comply with 170 IAC 4-1-24 timing requirements and to serve as the App-D worked example.
- The remaining 284 rows are generated stochastically from weighted distributions (seed-controlled).
- `outage_event_id` values in the dataset are drawn from a small set of real outage event IDs sampled from `corpus/_global/ops/outage_events_base.csv`.
- `business_hours` is computed from `event_ts` using IURC office hours (8:15 a.m.–4:45 p.m. ET, Monday–Friday) and the 2024 Indiana state holiday schedule.

### Margin Rules (§3.6a compliance)

| Metric | Rule |
|---|---|
| IURC-reportable row compliance | 100% of reportable rows comply with 170 IAC 4-1-24 timing (iurc_phone_ts > informed_ts; iurc_written_ts > iurc_phone_ts) |
| Tier 3-4 share | ≥ 75% of rows are Tier 3 or 4 (realistic for a distribution utility incident log) |
| Investigation open at year-end | 14 Tier 3 rows and all open Tier 1-2 rows have blank investigation_closed_date — ordinary operational imperfection, no regulatory effect |

### Realistic Imperfection

- 14 rows have `investigation_closed_date = ""` (investigations not closed by 2024-12-31)
- Several NMSSSIF rows have `capa_count = 0` (not all near misses generate CAPAs — company practice allows discretion for Tier 4)
- A small number of VEH rows have minor property damage with no injury (Tier 4), consistent with parking lot and low-speed incidents

---

## Acceptance Test Results
Run timestamp (UTC): 2026-10-07T08:00:13Z
Total rows: 285
IURC reportable: 1
Tier distribution: {'1': 12, '2': 22, '3': 55, '4': 196}
Category distribution: {'CUST': 7, 'DIGN': 4, 'ENRG': 14, 'EQP': 36, 'FALL': 55, 'FIRE': 2, 'NMSSSIF': 60, 'OTHER': 2, 'PROP': 32, 'STRIK': 25, 'VEH': 48}
Failures: 0
Warnings: 0
