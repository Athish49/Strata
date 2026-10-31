#!/usr/bin/env python3
"""
generate_incident_data.py
Deterministic generator for incident_log_2024.csv
RPL-SAF-PRO-009 v2.0   seed=2024

Regulatory values come from T21 grounding pack (170 IAC 4-1-24).
Company-practice values are in company_params below.
"""

import csv
import random
import math
import os
from datetime import datetime, timedelta, date

# ── Regulatory parameters (from T21.json / 170 IAC 4-1-24) ──────────────────
params = {
    # IURC reporting trigger: "accident attended with loss of human life"
    # Source: 170 IAC 4-1-24 body_text_s1
    "iurc_reportable_condition": "fatal",
    # Records retention minimum: "at least three years"
    # Source: 170 IAC 4-1-3 body_text_s1
    "records_retention_years": 3,
}

# ── Company-practice parameters ───────────────────────────────────────────────
company_params = {
    # Row count target (within spec 260–340)
    "row_count": 285,
    # IURC-reportable events in 2024: exactly 1 (CUST, fatal)
    "iurc_reportable_count": 1,
    # Tier distribution (company data)
    "tier_weights": {4: 0.58, 3: 0.26, 2: 0.12, 1: 0.04},
    # Category distribution
    "category_weights": {
        "NMSSSIF": 0.22, "VEH": 0.20, "FALL": 0.14,
        "EQP": 0.12, "STRIK": 0.10, "PROP": 0.08,
        "ENRG": 0.06, "DIGN": 0.04, "CUST": 0.02,
        "FIRE": 0.01, "OTHER": 0.01,
    },
    # IURC business hours (Table X): 8:15–16:45 ET, Mon–Fri
    # 2024 Indiana state holidays (mapped from 2025 pattern to 2024)
    "iurc_open_time": (8, 15),
    "iurc_close_time": (16, 45),
    # 2024 Indiana state holidays
    "indiana_holidays_2024": {
        date(2024, 1, 1),   # New Year's Day
        date(2024, 1, 15),  # MLK Day (3rd Mon Jan)
        date(2024, 5, 27),  # Memorial Day (last Mon May)
        date(2024, 7, 4),   # Independence Day
        date(2024, 9, 2),   # Labor Day (1st Mon Sep)
        date(2024, 11, 28), # Thanksgiving
        date(2024, 11, 29), # Day after Thanksgiving
        date(2024, 12, 24), # Christmas Eve
        date(2024, 12, 25), # Christmas Day
    },
}

SERVICE_CENTERS = ["LAF", "CRW", "THT", "FRK", "DAN"]
COUNTIES_BY_SC = {
    "LAF": ["Tippecanoe", "Clinton", "Carroll"],
    "CRW": ["Montgomery", "Fountain", "Parke"],
    "THT": ["Vigo", "Vermillion"],
    "FRK": ["Clinton", "Carroll", "White"],
    "DAN": ["Hendricks", "Boone"],
}
VOLTAGE_CLASSES = ["120/240V", "12.47kV", "34.5kV", "69kV", "unknown"]
INJURY_BY_TIER = {
    1: ["fatal", "hospitalized"],
    2: ["lost_time", "restricted"],
    3: ["medical_treatment"],
    4: ["first_aid", "none"],
}
PERSON_BY_CAT = {
    "VEH": ["employee", "contractor"],
    "ENRG": ["employee", "contractor"],
    "FALL": ["employee", "contractor"],
    "STRIK": ["employee", "contractor"],
    "FIRE": ["employee", "contractor", "none"],
    "CUST": ["public"],
    "DIGN": ["contractor", "public"],
    "EQP": ["employee", "contractor"],
    "PROP": ["none", "employee"],
    "NMSSSIF": ["employee", "contractor"],
    "OTHER": ["employee", "contractor", "public"],
}

# Select a sample of outage_event_ids from the ops file to cross-reference
OUTAGE_EVENT_IDS = [
    "EVT-2024-0000336", "EVT-2024-0000065", "EVT-2024-0000174",
    "EVT-2024-0000228", "EVT-2024-0001047", "EVT-2024-0002311",
    "EVT-2024-0003008", "EVT-2024-0004122", "",  # empty = no outage
]


def is_business_day(dt: datetime, holidays: set) -> bool:
    """Return True if dt falls within IURC business hours on a business day."""
    d = dt.date()
    if d.weekday() >= 5:  # Sat/Sun
        return False
    if d in holidays:
        return False
    oh, om = company_params["iurc_open_time"]
    ch, cm = company_params["iurc_close_time"]
    open_time = oh * 60 + om
    close_time = ch * 60 + cm
    event_time = dt.hour * 60 + dt.minute
    return open_time <= event_time < close_time


def next_business_open(dt: datetime, holidays: set) -> datetime:
    """Return the next IURC opening time after dt."""
    d = dt.date() + timedelta(days=1)
    while True:
        if d.weekday() < 5 and d not in holidays:
            oh, om = company_params["iurc_open_time"]
            return datetime(d.year, d.month, d.day, oh, om)
        d += timedelta(days=1)


def rand_ts_in_2024(rng: random.Random) -> datetime:
    """Random datetime in 2024."""
    start = datetime(2024, 1, 1, 0, 0)
    end = datetime(2024, 12, 31, 23, 59)
    delta = end - start
    seconds = int(delta.total_seconds())
    return start + timedelta(seconds=rng.randint(0, seconds))


def utc_offset_for(dt: datetime) -> str:
    """EST/EDT offset for America/Indiana/Indianapolis."""
    # EDT: 2nd Sun Mar → 1st Sun Nov
    # 2024: DST starts Mar 10, ends Nov 3
    dst_start = datetime(2024, 3, 10, 2, 0)
    dst_end = datetime(2024, 11, 3, 2, 0)
    if dst_start <= dt < dst_end:
        return "-04:00"
    return "-05:00"


def generate():
    rng = random.Random(2024)
    holidays = company_params["indiana_holidays_2024"]
    n = company_params["row_count"]
    rows = []

    # ── Row 1: the single IURC-reportable event ──────────────────────────────
    # A tree-service worker (public) contacts an RPL overhead line; fatal.
    # Event on a Tuesday during business hours so telephone notice during biz day.
    event_ts = datetime(2024, 8, 13, 10, 30)   # Tuesday, within IURC hours
    informed_ts = datetime(2024, 8, 13, 10, 45) # RPL informed 15 min after
    # Business day → call as soon as possible after being informed
    iurc_phone_ts = datetime(2024, 8, 13, 11, 5)   # ~20 min after informed
    # Written report after all pertinent info accumulated
    iurc_written_ts = datetime(2024, 8, 21, 9, 0).strftime("%Y-%m-%dT%H:%M")

    reportable_row = {
        "incident_id": "INC-2024-00142",
        "event_ts": event_ts.strftime("%Y-%m-%dT%H:%M"),
        "utc_offset": utc_offset_for(event_ts),
        "service_center": "LAF",
        "county": "Tippecanoe",
        "person_type": "public",
        "category": "CUST",
        "tier": "1",
        "energized_contact": "Y",
        "voltage_class": "12.47kV",
        "injury_severity": "fatal",
        "property_damage_est_usd": "0",
        "outage_event_id": "EVT-2024-0003782",
        "iurc_reportable": "Y",
        "informed_ts": informed_ts.strftime("%Y-%m-%dT%H:%M"),
        "business_hours": "Y",
        "iurc_phone_ts": iurc_phone_ts.strftime("%Y-%m-%dT%H:%M"),
        "iurc_written_ts": iurc_written_ts,
        "capa_count": "3",
        "investigation_closed_date": "2024-10-15",
    }
    rows.append(reportable_row)

    # ── Remaining n-1 rows ──────────────────────────────────────────────────
    cat_keys = list(company_params["category_weights"].keys())
    cat_weights = [company_params["category_weights"][k] for k in cat_keys]

    # Remove CUST (already used) from pool for the rest to limit CUST count
    # We'll allow 1 more non-fatal CUST to keep the distribution non-zero
    incident_seq = 1
    while len(rows) < n:
        incident_seq += 1
        # Skip INC-2024-00142 (already used)
        if incident_seq == 142:
            continue

        cat = rng.choices(cat_keys, weights=cat_weights, k=1)[0]

        # Tier assignment
        tier_keys = [1, 2, 3, 4]
        tier_weights_list = [company_params["tier_weights"][t] for t in tier_keys]
        # NMSSSIF and PROP are always Tier 4
        if cat in ("NMSSSIF", "PROP"):
            tier = 4
        elif cat == "ENRG":
            # energized contacts skew Tier 2-3
            tier = rng.choices([2, 3, 4], weights=[0.35, 0.45, 0.20], k=1)[0]
        else:
            tier = rng.choices(tier_keys, weights=tier_weights_list, k=1)[0]

        # Never assign Tier 1 with fatal here (that's the reportable row)
        # A Tier 1 here = hospitalized only
        inj_options = INJURY_BY_TIER[tier].copy()

        # For PROP/NMSSSIF, person_type is often none
        person_type = rng.choice(PERSON_BY_CAT.get(cat, ["employee"]))

        # injury_severity
        if cat == "PROP":
            injury_severity = "none"
        elif cat == "NMSSSIF":
            injury_severity = "none"
        elif person_type == "none":
            injury_severity = "none"
        else:
            # Filter out fatal for Tier 1 non-reportable (hospitalized only)
            if tier == 1:
                inj_options = ["hospitalized"]
            injury_severity = rng.choice(inj_options)

        energized = "Y" if cat in ("ENRG",) else (
            "Y" if cat in ("CUST", "FALL", "STRIK") and rng.random() < 0.15 else "N"
        )
        voltage = rng.choice(VOLTAGE_CLASSES) if energized == "Y" else ""

        prop_damage = 0
        if cat == "PROP":
            prop_damage = rng.randint(500, 180000)
        elif cat in ("VEH", "FIRE") and rng.random() < 0.4:
            prop_damage = rng.randint(2000, 45000)
        elif tier <= 2 and rng.random() < 0.3:
            prop_damage = rng.randint(500, 15000)

        # outage cross-reference
        outage_id = rng.choice(OUTAGE_EVENT_IDS) if cat in ("ENRG", "FIRE", "DIGN", "CUST") and rng.random() < 0.4 else ""

        # event timestamp
        ts = rand_ts_in_2024(rng)

        # capa_count
        if tier == 1:
            capa = rng.randint(3, 6)
        elif tier == 2:
            capa = rng.randint(1, 4)
        elif tier == 3:
            capa = rng.randint(0, 2)
        else:
            capa = rng.randint(0, 1)

        # investigation_closed_date (within 2024 or early 2025 for some Tier 1-2)
        close_days = {1: (60, 120), 2: (30, 75), 3: (14, 35), 4: (7, 20)}
        lo, hi = close_days[tier]
        close_delta = timedelta(days=rng.randint(lo, hi))
        close_dt = ts + close_delta
        if close_dt.year > 2024:
            close_date = ""  # still open at year-end
        else:
            close_date = close_dt.strftime("%Y-%m-%d")

        sc = rng.choice(SERVICE_CENTERS)
        county = rng.choice(COUNTIES_BY_SC[sc])

        row = {
            "incident_id": f"INC-2024-{incident_seq:05d}",
            "event_ts": ts.strftime("%Y-%m-%dT%H:%M"),
            "utc_offset": utc_offset_for(ts),
            "service_center": sc,
            "county": county,
            "person_type": person_type,
            "category": cat,
            "tier": str(tier),
            "energized_contact": energized,
            "voltage_class": voltage,
            "injury_severity": injury_severity,
            "property_damage_est_usd": str(prop_damage),
            "outage_event_id": outage_id,
            "iurc_reportable": "N",
            "informed_ts": "",
            "business_hours": "",
            "iurc_phone_ts": "",
            "iurc_written_ts": "",
            "capa_count": str(capa),
            "investigation_closed_date": close_date,
        }
        rows.append(row)

    # Sort by event_ts
    rows.sort(key=lambda r: r["event_ts"])

    return rows


def write_csv(rows, output_path):
    fieldnames = [
        "incident_id", "event_ts", "utc_offset", "service_center", "county",
        "person_type", "category", "tier", "energized_contact", "voltage_class",
        "injury_severity", "property_damage_est_usd", "outage_event_id",
        "iurc_reportable", "informed_ts", "business_hours",
        "iurc_phone_ts", "iurc_written_ts", "capa_count", "investigation_closed_date",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Written {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    rows = generate()
    write_csv(rows, os.path.join(out_dir, "incident_log_2024.csv"))

    # Summary stats
    total = len(rows)
    iurc_y = sum(1 for r in rows if r["iurc_reportable"] == "Y")
    tier_counts = {}
    for r in rows:
        t = int(r["tier"])
        tier_counts[t] = tier_counts.get(t, 0) + 1
    cat_counts = {}
    for r in rows:
        c = r["category"]
        cat_counts[c] = cat_counts.get(c, 0) + 1

    print(f"Total rows: {total}")
    print(f"IURC reportable: {iurc_y}")
    print(f"Tier distribution: {tier_counts}")
    print(f"Category distribution: {cat_counts}")
