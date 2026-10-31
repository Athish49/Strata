#!/usr/bin/env python3
"""
acceptance_tests.py
RPL-SAF-PRO-009 v2.0 — incident_log_2024.csv
Exit non-zero on any failure. Append results to data/README.md.
"""

import csv
import sys
import os
from datetime import datetime, date

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "incident_log_2024.csv")

VALID_CATEGORIES = {"VEH", "ENRG", "FALL", "STRIK", "FIRE", "CUST", "DIGN", "EQP", "PROP", "NMSSSIF", "OTHER"}
VALID_TIERS = {"1", "2", "3", "4"}
VALID_PERSON_TYPES = {"employee", "contractor", "public", "none"}
VALID_INJURY = {"none", "first_aid", "medical_treatment", "restricted", "lost_time", "hospitalized", "fatal"}
VALID_ENERGIZED = {"Y", "N"}
VALID_BOOL = {"Y", "N", ""}
VALID_SC = {"LAF", "CRW", "THT", "FRK", "DAN"}

INDIANA_HOLIDAYS_2024 = {
    date(2024, 1, 1), date(2024, 1, 15), date(2024, 5, 27),
    date(2024, 7, 4), date(2024, 9, 2), date(2024, 11, 28),
    date(2024, 11, 29), date(2024, 12, 24), date(2024, 12, 25),
}

failures = []
warnings = []


def fail(msg):
    failures.append(msg)
    print(f"FAIL: {msg}")


def warn(msg):
    warnings.append(msg)
    print(f"WARN: {msg}")


def is_iurc_biz_day(ts_str):
    """True if timestamp is within IURC business hours on a non-holiday weekday."""
    dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M")
    d = dt.date()
    if d.weekday() >= 5:
        return False
    if d in INDIANA_HOLIDAYS_2024:
        return False
    mins = dt.hour * 60 + dt.minute
    return (8 * 60 + 15) <= mins < (16 * 60 + 45)


with open(DATA_FILE, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

total = len(rows)
print(f"Loaded {total} rows from {DATA_FILE}")

# AT-1: Row count 260–340
if not (260 <= total <= 340):
    fail(f"AT-1: Row count {total} outside 260–340")
else:
    print(f"PASS AT-1: Row count {total} is within 260–340")

# AT-2: Primary key uniqueness
ids = [r["incident_id"] for r in rows]
if len(ids) != len(set(ids)):
    fail("AT-2: Duplicate incident_id values")
else:
    print("PASS AT-2: incident_id is unique")

# AT-3: PK format INC-2024-#####
import re
pk_pat = re.compile(r"^INC-2024-\d{5}$")
bad_pk = [r["incident_id"] for r in rows if not pk_pat.match(r["incident_id"])]
if bad_pk:
    fail(f"AT-3: Invalid incident_id format: {bad_pk[:5]}")
else:
    print("PASS AT-3: All incident_id match INC-2024-#####")

# AT-4: Category values
bad_cat = [r["incident_id"] for r in rows if r["category"] not in VALID_CATEGORIES]
if bad_cat:
    fail(f"AT-4: Invalid category values in rows: {bad_cat[:5]}")
else:
    print("PASS AT-4: All category values valid")

# AT-5: Tier values
bad_tier = [r["incident_id"] for r in rows if r["tier"] not in VALID_TIERS]
if bad_tier:
    fail(f"AT-5: Invalid tier values in rows: {bad_tier[:5]}")
else:
    print("PASS AT-5: All tier values valid")

# AT-6: person_type values
bad_pt = [r["incident_id"] for r in rows if r["person_type"] not in VALID_PERSON_TYPES]
if bad_pt:
    fail(f"AT-6: Invalid person_type values: {bad_pt[:5]}")
else:
    print("PASS AT-6: All person_type values valid")

# AT-7: injury_severity values
bad_inj = [r["incident_id"] for r in rows if r["injury_severity"] not in VALID_INJURY]
if bad_inj:
    fail(f"AT-7: Invalid injury_severity values: {bad_inj[:5]}")
else:
    print("PASS AT-7: All injury_severity values valid")

# AT-8: IURC-reportable row count = 1 (pack requires only fatalities)
reportable = [r for r in rows if r["iurc_reportable"] == "Y"]
if len(reportable) != 1:
    fail(f"AT-8: Expected 1 IURC-reportable row, found {len(reportable)}")
else:
    print("PASS AT-8: Exactly 1 IURC-reportable row")

# AT-9: Reportable row must be fatal (170 IAC 4-1-24 — loss of human life)
for r in reportable:
    if r["injury_severity"] != "fatal":
        fail(f"AT-9: IURC-reportable row {r['incident_id']} is not fatal (severity={r['injury_severity']})")
    else:
        print(f"PASS AT-9: Reportable row {r['incident_id']} has fatal severity")

# AT-10: Reportable row timestamps present and ordered
for r in reportable:
    rid = r["incident_id"]
    if not r["event_ts"]:
        fail(f"AT-10: {rid} missing event_ts")
    if not r["informed_ts"]:
        fail(f"AT-10: {rid} missing informed_ts")
    if not r["iurc_phone_ts"]:
        fail(f"AT-10: {rid} missing iurc_phone_ts")
    if not r["iurc_written_ts"]:
        fail(f"AT-10: {rid} missing iurc_written_ts")
    if r["event_ts"] and r["informed_ts"]:
        if r["informed_ts"] < r["event_ts"]:
            fail(f"AT-10: {rid} informed_ts < event_ts")
    if r["informed_ts"] and r["iurc_phone_ts"]:
        if r["iurc_phone_ts"] < r["informed_ts"]:
            fail(f"AT-10: {rid} iurc_phone_ts < informed_ts")
    if r["iurc_phone_ts"] and r["iurc_written_ts"]:
        if r["iurc_written_ts"] < r["iurc_phone_ts"]:
            fail(f"AT-10: {rid} iurc_written_ts < iurc_phone_ts")
    print(f"PASS AT-10: {rid} timestamps ordered correctly")

# AT-11: business_hours flag correct for reportable row
for r in reportable:
    rid = r["incident_id"]
    if r["event_ts"] and r["business_hours"]:
        expected = "Y" if is_iurc_biz_day(r["event_ts"]) else "N"
        if r["business_hours"] != expected:
            fail(f"AT-11: {rid} business_hours={r['business_hours']} but expected {expected} for event_ts={r['event_ts']}")
        else:
            print(f"PASS AT-11: {rid} business_hours={r['business_hours']} correct")

# AT-12: Non-reportable rows have empty timestamp fields
non_rep = [r for r in rows if r["iurc_reportable"] == "N"]
bad_ts = [r["incident_id"] for r in non_rep
          if r["informed_ts"] or r["iurc_phone_ts"] or r["iurc_written_ts"] or r["business_hours"]]
if bad_ts:
    fail(f"AT-12: Non-reportable rows have IURC timestamp fields: {bad_ts[:5]}")
else:
    print("PASS AT-12: Non-reportable rows have no IURC timestamp fields")

# AT-13: PROP and NMSSSIF are not IURC reportable
prop_nm_rep = [r["incident_id"] for r in rows
               if r["category"] in ("PROP", "NMSSSIF") and r["iurc_reportable"] == "Y"]
if prop_nm_rep:
    fail(f"AT-13: PROP/NMSSSIF rows marked IURC reportable: {prop_nm_rep}")
else:
    print("PASS AT-13: No PROP/NMSSSIF rows are IURC reportable")

# AT-14: Service center values
bad_sc = [r["incident_id"] for r in rows if r["service_center"] not in VALID_SC]
if bad_sc:
    fail(f"AT-14: Invalid service_center values: {bad_sc[:5]}")
else:
    print("PASS AT-14: All service_center values valid")

# AT-15: Tier 4 not hospitalized or fatal
tier4_severe = [r["incident_id"] for r in rows
                if r["tier"] == "4" and r["injury_severity"] in ("hospitalized", "fatal")]
if tier4_severe:
    fail(f"AT-15: Tier 4 rows with severe injury: {tier4_severe[:5]}")
else:
    print("PASS AT-15: No Tier 4 rows with hospitalized/fatal severity")

# AT-16: Tier distribution mostly Tier 3–4 (≥ 80%)
tier34 = sum(1 for r in rows if r["tier"] in ("3", "4"))
pct = tier34 / total
if pct < 0.75:
    fail(f"AT-16: Tier 3-4 share {pct:.1%} below 75% — not realistic for routine incident log")
else:
    print(f"PASS AT-16: Tier 3-4 share {pct:.1%} >= 75%")

# AT-17: event_ts within 2024
bad_year = [r["incident_id"] for r in rows
            if r["event_ts"] and not r["event_ts"].startswith("2024-")]
if bad_year:
    fail(f"AT-17: Rows with event_ts outside 2024: {bad_year[:5]}")
else:
    print("PASS AT-17: All event_ts within 2024")

# AT-18: property_damage_est_usd is numeric and non-negative
bad_prop = []
for r in rows:
    try:
        v = float(r["property_damage_est_usd"])
        if v < 0:
            bad_prop.append(r["incident_id"])
    except (ValueError, TypeError):
        bad_prop.append(r["incident_id"])
if bad_prop:
    fail(f"AT-18: Invalid property_damage_est_usd: {bad_prop[:5]}")
else:
    print("PASS AT-18: All property_damage_est_usd values are non-negative numbers")

# Print summary
print("\n=== ACCEPTANCE TEST SUMMARY ===")
print(f"Total rows: {total}")
print(f"IURC reportable: {len(reportable)}")
from collections import Counter
tier_dist = Counter(r["tier"] for r in rows)
cat_dist = Counter(r["category"] for r in rows)
print(f"Tier distribution: {dict(sorted(tier_dist.items()))}")
print(f"Category distribution: {dict(sorted(cat_dist.items()))}")
print(f"Failures: {len(failures)}")
print(f"Warnings: {len(warnings)}")

# Append results to README
readme_path = os.path.join(os.path.dirname(__file__), "..", "data", "README.md")
ts_now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
result_lines = [
    "\n## Acceptance Test Results\n",
    f"Run timestamp (UTC): {ts_now}\n",
    f"Total rows: {total}\n",
    f"IURC reportable: {len(reportable)}\n",
    f"Tier distribution: {dict(sorted(tier_dist.items()))}\n",
    f"Category distribution: {dict(sorted(cat_dist.items()))}\n",
    f"Failures: {len(failures)}\n",
    f"Warnings: {len(warnings)}\n",
]
if failures:
    result_lines.append("\n### Failures\n")
    for f in failures:
        result_lines.append(f"- {f}\n")

with open(readme_path, "a", encoding="utf-8") as readme:
    readme.writelines(result_lines)

if failures:
    sys.exit(1)
else:
    print("\nAll acceptance tests PASSED.")
    sys.exit(0)
