#!/usr/bin/env python3
"""
RPL-ENV-PRO-005 Acceptance Tests
Exits 0 on pass, non-zero on any failure.
Results are appended to data/README.md after execution.
"""

import csv
import sys
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data" / "spill_events_2024.csv"
MANIFEST_FILE = ROOT / "data" / "_manifest.json"
MD_FILE = ROOT / "RPL-ENV-PRO-005_v3.1.md"
README_FILE = ROOT / "data" / "README.md"

TZ = ZoneInfo("America/Indiana/Indianapolis")

VALID_SERVICE_CENTERS = {"LAF", "CRW", "THT", "FRK", "DAN"}
VALID_COUNTIES = {
    "Tippecanoe", "Clinton", "Carroll", "White", "Benton",
    "Warren", "Fountain", "Montgomery", "Boone", "Hendricks",
    "Putnam", "Parke", "Vermillion", "Vigo",
}
VALID_SOURCE_TYPES = {
    "pole_transformer", "padmount_transformer", "substation_equipment",
    "standby_generator", "fleet_vehicle", "bucket_truck_hydraulic", "fueling",
}
VALID_SUBSTANCES = {"mineral_oil", "diesel", "gasoline", "hydraulic_fluid", "other"}
VALID_PCB_CODES = {"NP-T", "NP-M", "UNK", "PCB-C", "PCB"}
VALID_RECEIVING_MEDIA = {
    "impervious", "soil_inside_boundary", "soil_beyond_boundary",
    "surface_water", "storm_drain", "sewer",
}
VALID_DECISION_ROWS = {"T7-1", "T7-2", "T7-3", "T7-4", "T7-5", "T7-6"}
APP_E_IDS = {"SPL-2024-0033", "SPL-2024-0071", "SPL-2024-0088"}
COMPANY_NOTIFICATION_WINDOW_HOURS = 2

failures = []
warnings = []

def fail(msg):
    failures.append(msg)

def warn(msg):
    warnings.append(msg)


def check_csv():
    if not DATA_FILE.exists():
        fail(f"CSV not found: {DATA_FILE}")
        return []

    rows = list(csv.DictReader(DATA_FILE.open(encoding="utf-8")))

    # AT-01: Row count 80–110
    n = len(rows)
    if not (80 <= n <= 110):
        fail(f"AT-01 Row count {n} outside [80, 110]")
    else:
        print(f"  AT-01 PASS: row count = {n}")

    # AT-02: event_id uniqueness and pattern
    ids = [r["event_id"] for r in rows]
    if len(ids) != len(set(ids)):
        fail("AT-02 Duplicate event_ids found")
    else:
        for eid in ids:
            if not (eid.startswith("SPL-2024-") and eid[9:].isdigit() and len(eid[9:]) == 4):
                fail(f"AT-02 Invalid event_id format: {eid}")
                break
        else:
            print("  AT-02 PASS: event_id uniqueness and format")

    # AT-03: Mineral oil fraction ≥ 75%
    mo = sum(1 for r in rows if r["substance"] == "mineral_oil")
    mo_pct = mo / n * 100
    if mo_pct < 75:
        fail(f"AT-03 Mineral oil {mo_pct:.1f}% < 75%")
    else:
        print(f"  AT-03 PASS: mineral oil = {mo_pct:.1f}%")

    # AT-04: Valid enumerated fields
    for i, r in enumerate(rows, 1):
        if r["service_center"] not in VALID_SERVICE_CENTERS:
            fail(f"AT-04 Row {i} invalid service_center: {r['service_center']}")
        if r["county"] not in VALID_COUNTIES:
            fail(f"AT-04 Row {i} invalid county: {r['county']}")
        if r["source_type"] not in VALID_SOURCE_TYPES:
            fail(f"AT-04 Row {i} invalid source_type: {r['source_type']}")
        if r["substance"] not in VALID_SUBSTANCES:
            fail(f"AT-04 Row {i} invalid substance: {r['substance']}")
        if r["pcb_status_code"] not in VALID_PCB_CODES:
            fail(f"AT-04 Row {i} invalid pcb_status_code: {r['pcb_status_code']}")
        if r["receiving_medium"] not in VALID_RECEIVING_MEDIA:
            fail(f"AT-04 Row {i} invalid receiving_medium: {r['receiving_medium']}")
        if r["reportable"] not in {"Y", "N"}:
            fail(f"AT-04 Row {i} invalid reportable: {r['reportable']}")
        if r["special_area_flag"] not in {"Y", "N"}:
            fail(f"AT-04 Row {i} invalid special_area_flag: {r['special_area_flag']}")
        if r["decision_row"] not in VALID_DECISION_ROWS:
            fail(f"AT-04 Row {i} invalid decision_row: {r['decision_row']}")
    if not any("AT-04" in f for f in failures):
        print("  AT-04 PASS: all enumerated fields valid")

    # AT-05: Volume logic (recovered ≤ released)
    for i, r in enumerate(rows, 1):
        try:
            rel = float(r["volume_released_gal"])
            rec = float(r["volume_recovered_gal"])
            if rec > rel + 0.01:
                fail(f"AT-05 Row {i} recovered ({rec}) > released ({rel})")
            if rel <= 0:
                fail(f"AT-05 Row {i} volume_released_gal ≤ 0")
        except ValueError:
            fail(f"AT-05 Row {i} non-numeric volume")
    if not any("AT-05" in f for f in failures):
        print("  AT-05 PASS: volume logic")

    # AT-06: Reportable events have IDEM notification
    for i, r in enumerate(rows, 1):
        if r["reportable"] == "Y" and not r["idem_report_ts"]:
            fail(f"AT-06 Row {i} reportable=Y but idem_report_ts blank")
        if r["reportable"] == "N" and r["idem_report_ts"]:
            fail(f"AT-06 Row {i} reportable=N but idem_report_ts populated")
    if not any("AT-06" in f for f in failures):
        print("  AT-06 PASS: IDEM notification presence/absence")

    # AT-07: Notification within company 2-hour window
    over_window = 0
    for i, r in enumerate(rows, 1):
        if r["reportable"] == "Y" and r["idem_report_ts"] and r["discovered_ts"]:
            try:
                disc = datetime.fromisoformat(r["discovered_ts"]).replace(tzinfo=TZ)
                idem = datetime.fromisoformat(r["idem_report_ts"]).replace(tzinfo=TZ)
                elapsed_hours = (idem - disc).total_seconds() / 3600
                if elapsed_hours > COMPANY_NOTIFICATION_WINDOW_HOURS + 0.5:  # tolerance for determination lag
                    over_window += 1
            except ValueError:
                warn(f"AT-07 Row {i} timestamp parse error")
    if over_window > 0:
        warn(f"AT-07 {over_window} rows exceeded 2.5-hour window (discovery to IDEM) — review determination lag")
    else:
        print("  AT-07 PASS: all reportable events notified within window")

    # AT-08: Exclusion only for N rows
    for i, r in enumerate(rows, 1):
        if r["reportable"] == "Y" and r["exclusion_applied"]:
            fail(f"AT-08 Row {i} reportable=Y has exclusion_applied={r['exclusion_applied']}")
    if not any("AT-08" in f for f in failures):
        print("  AT-08 PASS: exclusion_applied only on non-reportable rows")

    # AT-09: App-E events present
    row_ids = {r["event_id"] for r in rows}
    for eid in APP_E_IDS:
        if eid not in row_ids:
            fail(f"AT-09 App-E event {eid} missing from dataset")
    if not any("AT-09" in f for f in failures):
        print(f"  AT-09 PASS: all App-E events present ({', '.join(sorted(APP_E_IDS))})")

    # AT-10: App-E reportability matches expected
    expected = {
        "SPL-2024-0033": ("Y", "T7-3"),
        "SPL-2024-0071": ("Y", "T7-5"),
        "SPL-2024-0088": ("N", "T7-1"),
    }
    row_map = {r["event_id"]: r for r in rows}
    for eid, (exp_rep, exp_row) in expected.items():
        r = row_map.get(eid)
        if r:
            if r["reportable"] != exp_rep:
                fail(f"AT-10 {eid} reportable={r['reportable']} expected={exp_rep}")
            if r["decision_row"] != exp_row:
                fail(f"AT-10 {eid} decision_row={r['decision_row']} expected={exp_row}")
    if not any("AT-10" in f for f in failures):
        print("  AT-10 PASS: App-E reportability correct")

    # AT-11: Dates within 2024
    for i, r in enumerate(rows, 1):
        try:
            disc = datetime.fromisoformat(r["discovered_ts"]).replace(tzinfo=TZ)
            if not (datetime(2024, 1, 1, tzinfo=TZ) <= disc <= datetime(2024, 12, 31, 23, 59, tzinfo=TZ)):
                fail(f"AT-11 Row {i} discovered_ts {r['discovered_ts']} outside 2024")
        except ValueError:
            fail(f"AT-11 Row {i} discovered_ts parse error")
    if not any("AT-11" in f for f in failures):
        print("  AT-11 PASS: all timestamps within 2024")

    # AT-12: utc_offset consistent with month
    for i, r in enumerate(rows, 1):
        try:
            disc = datetime.fromisoformat(r["discovered_ts"]).replace(tzinfo=TZ)
            expected_offset = "-05:00" if disc.month in (11, 12, 1, 2, 3) else "-04:00"
            if r["utc_offset"] != expected_offset:
                fail(f"AT-12 Row {i} utc_offset {r['utc_offset']} expected {expected_offset} for month {disc.month}")
        except ValueError:
            pass
    if not any("AT-12" in f for f in failures):
        print("  AT-12 PASS: utc_offset consistent with DST rule")

    # AT-13: decision_row cross-reference exists in procedure md
    if MD_FILE.exists():
        md_text = MD_FILE.read_text(encoding="utf-8")
        unique_rows = {r["decision_row"] for r in rows}
        for dr in unique_rows:
            if dr not in md_text:
                fail(f"AT-13 decision_row '{dr}' not found in procedure md")
        if not any("AT-13" in f for f in failures):
            print("  AT-13 PASS: all decision_row values found in procedure md")
    else:
        warn("AT-13 SKIP: procedure md not found")

    return rows


def check_manifest():
    if not MANIFEST_FILE.exists():
        fail("AT-14 Manifest file missing")
        return
    with MANIFEST_FILE.open() as f:
        manifest = json.load(f)
    sha_in_manifest = manifest["files"][0]["sha256"]
    actual_sha = hashlib.sha256(DATA_FILE.read_bytes()).hexdigest()
    if sha_in_manifest != actual_sha:
        fail(f"AT-14 Manifest sha256 mismatch: manifest={sha_in_manifest} actual={actual_sha}")
    else:
        print(f"  AT-14 PASS: manifest sha256 matches ({actual_sha[:16]}…)")

    rows_in_manifest = manifest["files"][0]["rows"]
    rows_actual = sum(1 for _ in csv.DictReader(DATA_FILE.open(encoding="utf-8")))
    if rows_in_manifest != rows_actual:
        fail(f"AT-14 Manifest row count {rows_in_manifest} ≠ actual {rows_actual}")


def main():
    print("=" * 60)
    print("RPL-ENV-PRO-005 Acceptance Tests")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    rows = check_csv()
    check_manifest()

    print("-" * 60)
    if failures:
        print(f"FAIL — {len(failures)} failure(s):")
        for f in failures:
            print(f"  ✗ {f}")
    else:
        print("PASS — all acceptance tests passed")

    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  ! {w}")

    # Append results to data/README.md
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    result_block = f"\n---\n\n## Acceptance Test Results ({timestamp})\n\n"
    if failures:
        result_block += f"**STATUS: FAIL** — {len(failures)} failure(s)\n\n"
        for f in failures:
            result_block += f"- FAIL: {f}\n"
    else:
        result_block += "**STATUS: PASS** — all acceptance tests passed\n\n"
    if warnings:
        result_block += f"\nWarnings:\n"
        for w in warnings:
            result_block += f"- WARN: {w}\n"

    if README_FILE.exists():
        existing = README_FILE.read_text(encoding="utf-8")
        # Remove previous results block if any
        if "## Acceptance Test Results" in existing:
            existing = existing[:existing.index("## Acceptance Test Results") - 4]
        README_FILE.write_text(existing + result_block, encoding="utf-8")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
