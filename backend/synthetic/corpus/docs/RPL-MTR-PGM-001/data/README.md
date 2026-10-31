# RPL-MTR-PGM-001 Data Directory

Generated datasets for the **Rockridge Power & Light Company — Meter Testing Program Plan** (RPL-MTR-PGM-001 v6.0).

**Generator:** `scripts/generate_meter_data.py` | **Seed:** 2024 | **Snapshot:** S1 (2024-12-31)

---

## Files

| File | Description | Rows / Notes |
|---|---|---|
| `meter_registry_2024-12-31.csv.gz` | Full meter fleet registry, gzip-compressed | 409,950 rows |
| `meter_population_2024-12-31.csv` | Homogeneous group summary with meter counts and 2025 sample sizes | 53 groups; Σmeter_count = 409,950 |
| `meter_test_results_2024.csv` | All test records for CY 2024 (in-service, acceptance, customer) | ~6,382 rows |
| `new_meter_lots_2024.csv` | New-meter acceptance lot records | ~11 lots |
| `inservice_sample_selection_2025.csv` | 2025 annual sample draw (meter serial, group, quarter, location) | ~3,750 rows |
| `customer_test_requests_2024.csv` | Customer-requested meter tests, CY 2024 | 620 rows |
| `standards_calibration_2024.csv` | Test equipment calibration register (reference, shop test board, portable) | 41 rows |
| `_manifest.json` | SHA-256 checksums and file sizes for all data files | — |
| `README.md` | This file | — |

---

## Fleet Totals (2024-12-31)

| Technology | Count |
|---|---|
| Solid-state AMI | 371,200 |
| Solid-state AMR | 31,400 |
| Electromechanical | 7,350 |
| **Total** | **409,950** |

---

## Key Regulatory Parameters

| Parameter | Value | Citation |
|---|---|---|
| Average error limit | ±2.00% | 170 IAC 4-1-9(b)(1)(A) |
| Full-load error limit | ±1.00% | 170 IAC 4-1-9(b)(1)(B) |
| Light-load error limit | ±3.00% | 170 IAC 4-1-9(b)(1)(C) |
| LL test load | 10% of rated test amperes | 170 IAC 4-1-8(a) |
| FL test load | 100% of rated test amperes | 170 IAC 4-1-8(a) |
| Method A periodic interval | 16 years | 170 IAC 4-1-10(b),(d) |
| Demand register periodic interval | 8 years | 170 IAC 4-1-10(d)(1)(B),(H) |
| Electronic meter periodic interval | 16 years | 170 IAC 4-1-10(d)(2) |
| Method B lot minimum size | 301 meters | 170 IAC 4-1-10(c)(2) |
| Method B AQL | 2.50 | 170 IAC 4-1-10(c)(4) |
| Method B U / L | 102% / 98% | 170 IAC 4-1-10(c)(5) |
| Rejected lot accelerated max | 96 months | 170 IAC 4-1-10(c)(7) |
| Reference standard recal interval | 2 years | 170 IAC 4-1-7(C) |
| Portable standard error threshold | ±1.00% | 170 IAC 4-1-7(D) |
| New meter test window | 60 days | 170 IAC 4-1-6(c) |
| Records retention minimum | 3 years | 170 IAC 4-1-3 |
| Customer test report deadline | 10 days | 170 IAC 4-1-11(d) |
| Customer appeal period | 5 days | 170 IAC 4-1-11(e) |

---

## Schema Notes

### meter_registry_2024-12-31.csv.gz
Columns: `meter_serial, meter_group_id, meter_technology, form, meter_class, service_type, vendor_family, install_date, premise_id, account_id, service_center, county, circuit_id, last_test_date, last_test_reason, status`

### meter_test_results_2024.csv
Columns: `test_id, meter_serial, meter_group_id, sample_lot_id, customer_request_id, test_date, test_reason, test_location, test_board_or_standard_id, technician_id, as_found_fl_pct, as_found_ll_pct, as_found_pf_pct, average_accuracy_pct, within_limits, functional_result, adjusted, as_left_fl_pct, as_left_ll_pct, as_left_pf_pct, action_taken, billing_review_ref`

`within_limits` = "Y" if |avg−100| ≤ 2.0 AND |fl−100| ≤ 1.0 AND |ll−100| ≤ 3.0, else "N".

---

*Uncontrolled when extracted — verify with `_manifest.json` checksums before use.*
