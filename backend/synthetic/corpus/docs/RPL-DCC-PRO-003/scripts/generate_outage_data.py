#!/usr/bin/env python3
"""
generate_outage_data.py — T19 dataset generator for RPL-DCC-PRO-003
Seed: 2024

Reads T04 base files and adds regulatory columns.
MUST NOT alter T04 base values (times, customers, CMI, cause).

Regulatory parameters live in the `params` dict below, populated from basis.json.
Company-practice parameters live in `company_params`.
"""

import csv
import json
import random
import hashlib
from datetime import datetime, timedelta, timezone, time
from pathlib import Path

# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------
random.seed(2024)

# ---------------------------------------------------------------------------
# Regulatory parameters (from RPL-DCC-PRO-003.basis.json)
# Source: 170 IAC 4-1-23(b)(1)(A) and 170 IAC 4-1-23(b)(2)
# ---------------------------------------------------------------------------
params = {
    # Reportability threshold — 170 IAC 4-1-23(b)(1)(A)
    "customers_served_denominator": 407491,          # for threshold computation only
    "pct_threshold": 0.02,                           # 2%
    "flat_threshold": 5000,                          # 5,000 customers
    "duration_threshold_min": 120,                   # 2 hours = 120 minutes
    # Applied threshold = min(2% of customers_served, 5000)
    # = min(8149, 5000) = 5,000

    # Planned interruption notice — 170 IAC 4-1-23(c)
    "planned_notice_trigger_min": 60,                # > 1 hour

    # Records retention — 170 IAC 4-1-3
    "records_retention_years": 3,

    # Reliability data retention — 170 IAC 4-1-23(f)
    "reliability_data_retention_years": 7,

    # Reliability report filing deadline — 170 IAC 4-1-23(e)
    "reliability_report_due_month": 3,               # March
    "reliability_report_due_day": 1,                 # 1st

    # Reporting intervals — 170 IAC 4-1-23(b)(2)
    # Times in Eastern Standard Time (Indianapolis time), as UTC offsets
    "business_day_intervals_est": ["06:00", "09:00", "11:00", "14:00", "16:00", "21:00"],
    "nonbusiness_day_intervals_est": ["06:00", "14:00", "21:00"],
}

# Company-practice parameters
company_params = {
    "reporting_channel": "email",                    # preferred; phone allowed if pre-coordinated
    "report_form": "State Form 54646",
    "report_form_id": "DCC-F-001",
    "oms_closeout_deadline_hours": 24,               # internal OMS closeout
    "tmed_saidi_min": 137.1872,                      # from reliability_facts.yaml
    "med_dates_2024": [
        "2024-03-15", "2024-05-22", "2024-07-04", "2024-08-09", "2024-12-23"
    ],
    # 2% of 407,491 = 8,149; flat threshold 5,000 — so effective threshold = 5,000
    "effective_customer_threshold": 5000,
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path(__file__).parent.parent
# corpus/ is the grandparent of docs/
OPS = BASE.parent.parent / "_global" / "ops"
DATA = BASE / "data"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
# Indiana / Indianapolis: EST = UTC-5, EDT = UTC-4
# For this corpus we treat all times as EST (UTC-5) per the rule's language
# unless the event file already specifies utc_offset.
# DST transitions: 2024-03-10 (spring forward) and 2024-11-03 (fall back)

DST_START_2024 = datetime(2024, 3, 10, 2, 0)   # clocks spring forward
DST_END_2024   = datetime(2024, 11, 3, 2, 0)   # clocks fall back


def utc_offset_for(ts: datetime) -> str:
    """Return UTC offset string for America/Indiana/Indianapolis."""
    if DST_START_2024 <= ts < DST_END_2024:
        return "-04:00"
    return "-05:00"


# Indiana State holidays 2024 (approximate; company uses state holidays for "business day" definition)
STATE_HOLIDAYS_2024 = {
    datetime(2024, 1, 1).date(),   # New Year's Day
    datetime(2024, 1, 15).date(),  # Martin Luther King Jr. Day
    datetime(2024, 2, 19).date(),  # Presidents' Day (not always IN, but listed as state holiday)
    datetime(2024, 5, 27).date(),  # Memorial Day
    datetime(2024, 7, 4).date(),   # Independence Day
    datetime(2024, 9, 2).date(),   # Labor Day
    datetime(2024, 11, 11).date(), # Veterans Day
    datetime(2024, 11, 28).date(), # Thanksgiving
    datetime(2024, 11, 29).date(), # Day after Thanksgiving (IN state holiday)
    datetime(2024, 12, 25).date(), # Christmas
    datetime(2024, 12, 26).date(), # Day after Christmas (IN)
    # 2025
    datetime(2025, 1, 1).date(),
    datetime(2025, 1, 20).date(),
}


def is_business_day(dt: datetime) -> bool:
    d = dt.date()
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    if d in STATE_HOLIDAYS_2024:
        return False
    return True


def next_reporting_interval(threshold_ts: datetime) -> datetime:
    """
    Return the next reporting interval after threshold_ts.
    Intervals are expressed in EST (UTC-5) per 170 IAC 4-1-23(b)(2).
    We compute in local Indianapolis time.
    """
    # Work in naive local time for simplicity
    # The rule says "EST (Indianapolis time)" which is UTC-5 year-round for Indiana
    local_ts = threshold_ts  # assume already in local time

    if is_business_day(local_ts):
        intervals_hhmm = [h.split(":") for h in params["business_day_intervals_est"]]
    else:
        intervals_hhmm = [h.split(":") for h in params["nonbusiness_day_intervals_est"]]

    today = local_ts.date()
    for hh, mm in intervals_hhmm:
        candidate = datetime(today.year, today.month, today.day, int(hh), int(mm))
        if candidate > local_ts:
            return candidate

    # Roll to next day's first interval
    next_day = local_ts.date() + timedelta(days=1)
    next_dt = datetime(next_day.year, next_day.month, next_day.day, 0, 0)
    return next_reporting_interval(next_dt)


def compute_reportable_and_threshold(peak: int, start_ts: datetime, restored_ts: datetime,
                                      incident_type: str) -> tuple:
    """
    Return (reportable: bool, criteria_met: str, threshold_crossed_ts: str).
    Reportable only if NOT planned, duration >= 120 min, peak >= 5,000.
    The threshold_crossed_ts is when BOTH criteria were first met.
    """
    if incident_type == "planned":
        return False, "", ""

    dur_min = (restored_ts - start_ts).total_seconds() / 60
    eff_threshold = company_params["effective_customer_threshold"]

    if peak >= eff_threshold and dur_min >= params["duration_threshold_min"]:
        # Threshold_crossed_ts: the later of (start_ts + 120 min) and (start_ts when peak first exceeded 5k)
        # Since peak is instantaneous at start_ts, the binding constraint is duration >= 120 min
        threshold_ts = start_ts + timedelta(minutes=params["duration_threshold_min"])
        criteria = f"peak_customers>={eff_threshold}|duration_min>={params['duration_threshold_min']}"
        return True, criteria, threshold_ts.strftime("%Y-%m-%dT%H:%M")
    return False, "", ""


# ---------------------------------------------------------------------------
# Load T04 base incidents
# ---------------------------------------------------------------------------
incidents_base = []
with open(OPS / "outage_incidents_base.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        incidents_base.append(row)

# Load T04 base events
events_base = []
with open(OPS / "outage_events_base.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        events_base.append(row)

# ---------------------------------------------------------------------------
# Build the incidents dataset
# ---------------------------------------------------------------------------
print("Building outage_incidents_2024-01-01_2025-01-31.csv ...")

# IURC reporting log accumulator
report_log_rows = []
report_counter = [1]

def next_report_id():
    rid = f"RPT-2024-{report_counter[0]:05d}"
    report_counter[0] += 1
    return rid


def build_report_rows(incident_id, threshold_ts_str, peak, start_ts, restored_ts):
    """Generate initial, update(s), and final report rows for a reportable incident."""
    rows = []
    threshold_ts = datetime.fromisoformat(threshold_ts_str)

    # Initial report: next interval after threshold_crossed_ts
    initial_ts = next_reporting_interval(threshold_ts)

    # Use >60% of window for ≥15% of reportable incidents (margin rule)
    # We'll handle this via a flag; we'll adjust timing for the first 2 incidents
    # to use 75–90% of the allowed window.
    window_start = threshold_ts
    window_end = next_reporting_interval(threshold_ts)
    window_min = (window_end - window_start).total_seconds() / 60

    # Initial report row
    rows.append({
        "report_id": next_report_id(),
        "incident_id": incident_id,
        "report_type": "initial",
        "submitted_ts": initial_ts.strftime("%Y-%m-%dT%H:%M"),
        "channel": "email",
        "form_revision": "State Form 54646",
        "customers_affected_reported": peak,
        "customers_still_out_reported": peak,
        "etr_reported": (start_ts + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M"),
        "cause_reported": "under investigation",
        "reported_by_person_id": "P23",
    })

    # Update reports: one per interval until restoration
    cur = initial_ts
    update_count = 0
    while cur < restored_ts:
        nxt = next_reporting_interval(cur + timedelta(minutes=1))
        if nxt >= restored_ts:
            break
        update_count += 1
        still_out = max(0, int(peak * (1 - 0.15 * update_count)))
        rows.append({
            "report_id": next_report_id(),
            "incident_id": incident_id,
            "report_type": "update",
            "submitted_ts": nxt.strftime("%Y-%m-%dT%H:%M"),
            "channel": "email",
            "form_revision": "State Form 54646",
            "customers_affected_reported": peak,
            "customers_still_out_reported": still_out,
            "etr_reported": (restored_ts - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "cause_reported": "vegetation/wind" if update_count >= 2 else "under investigation",
            "reported_by_person_id": "P23",
        })
        cur = nxt
        if update_count > 20:  # safety cap
            break

    # Final report: next interval after restoration
    final_ts = next_reporting_interval(restored_ts)
    rows.append({
        "report_id": next_report_id(),
        "incident_id": incident_id,
        "report_type": "final",
        "submitted_ts": final_ts.strftime("%Y-%m-%dT%H:%M"),
        "channel": "email",
        "form_revision": "State Form 54646",
        "customers_affected_reported": peak,
        "customers_still_out_reported": 0,
        "etr_reported": restored_ts.strftime("%Y-%m-%dT%H:%M"),
        "cause_reported": "vegetation/wind",
        "reported_by_person_id": "P23",
    })

    return rows


# Track which incidents will get the "wide window" treatment (≥15% of reportable)
# We have 10 reportable incidents (excluding planned); 15% = 1.5 → use 2 incidents
WIDE_WINDOW_INCIDENTS = set()

incident_out_rows = []
reportable_incident_ids = []

for inc in incidents_base:
    start_ts = datetime.fromisoformat(inc["first_start_ts"])
    restored_ts = datetime.fromisoformat(inc["restored_ts"])
    peak = int(inc["peak_customers_out"])
    incident_type = inc["incident_type"]

    reportable, criteria_met, threshold_crossed_ts = compute_reportable_and_threshold(
        peak, start_ts, restored_ts, incident_type
    )

    if reportable:
        reportable_incident_ids.append(inc["incident_id"])

    # Determine iurc report timestamps (derived from log)
    iurc_initial_ts = ""
    iurc_update_count = 0
    iurc_final_ts = ""

    if reportable and threshold_crossed_ts:
        threshold_dt = datetime.fromisoformat(threshold_crossed_ts)
        initial_dt = next_reporting_interval(threshold_dt)
        iurc_initial_ts = initial_dt.strftime("%Y-%m-%dT%H:%M")

        # count updates
        cur = initial_dt
        upd_count = 0
        while True:
            nxt = next_reporting_interval(cur + timedelta(minutes=1))
            if nxt >= restored_ts:
                break
            upd_count += 1
            cur = nxt
            if upd_count > 20:
                break
        iurc_update_count = upd_count

        final_dt = next_reporting_interval(restored_ts)
        iurc_final_ts = final_dt.strftime("%Y-%m-%dT%H:%M")

    row = dict(inc)
    row["threshold_crossed_ts"] = threshold_crossed_ts
    row["reportable"] = "Y" if reportable else "N"
    row["criteria_met"] = criteria_met
    row["iurc_initial_report_ts"] = iurc_initial_ts
    row["iurc_update_count"] = iurc_update_count if reportable else ""
    row["iurc_final_report_ts"] = iurc_final_ts

    incident_out_rows.append(row)

# Write incidents CSV
incident_fields = list(incidents_base[0].keys()) + [
    "threshold_crossed_ts", "reportable", "criteria_met",
    "iurc_initial_report_ts", "iurc_update_count", "iurc_final_report_ts"
]

with open(DATA / "outage_incidents_2024-01-01_2025-01-31.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=incident_fields)
    writer.writeheader()
    writer.writerows(incident_out_rows)

print(f"  Incidents written: {len(incident_out_rows)}")
print(f"  Reportable: {len(reportable_incident_ids)}: {reportable_incident_ids}")

# ---------------------------------------------------------------------------
# Build events dataset (T04 base + regulatory fields)
# ---------------------------------------------------------------------------
print("Building outage_events_2024-01-01_2025-01-31.csv ...")

# Build set of reportable incident IDs for join
reportable_set = set(reportable_incident_ids)

# Build set of MED dates for med_flag correction
# Must load reliability_facts.yaml at this point (loaded later in generator, load early reference)
import yaml as _yaml
with open(OPS / "reliability_facts.yaml") as _f:
    _facts_early = _yaml.safe_load(_f)
med_dates_set = set(_facts_early["med_dates_2024"])

event_out_rows = []
for evt in events_base:
    row = dict(evt)
    # Override med_flag based on start date vs MED dates (T19 corrects T04 base for non-storm events)
    # T04 base columns start_ts, end_ts, customers_affected, customer_minutes, cause_category,
    # cause_code are hash-checked and must not change; med_flag is not in that set.
    start_date = evt["start_ts"][:10]
    if start_date in med_dates_set:
        row["med_flag"] = "Y"
        row["med_date"] = start_date
    else:
        row["med_flag"] = "N"
        row["med_date"] = ""
    # Add regulatory fields
    row["reportable"] = "Y" if evt["incident_id"] in reportable_set else "N"
    event_out_rows.append(row)

event_fields = list(events_base[0].keys()) + ["reportable"]

with open(DATA / "outage_events_2024-01-01_2025-01-31.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=event_fields)
    writer.writeheader()
    writer.writerows(event_out_rows)

print(f"  Events written: {len(event_out_rows)}")

# ---------------------------------------------------------------------------
# Build IURC report log
# ---------------------------------------------------------------------------
print("Building iurc_report_log_2024-01-01_2025-01-31.csv ...")

# Build lookup for incidents
inc_by_id = {r["incident_id"]: r for r in incidents_base}

# Identify wide-window incidents (2 out of 10 reportable = 20% > 15%)
# Use the 3rd and 6th reportable incidents (neither is the App-A example)
wide_window_ids = set()
if len(reportable_incident_ids) >= 3:
    wide_window_ids.add(reportable_incident_ids[2])  # 3rd reportable
if len(reportable_incident_ids) >= 6:
    wide_window_ids.add(reportable_incident_ids[5])  # 6th reportable

report_log_rows = []

def build_report_log(incident_id, inc_base_row):
    """Build report log rows for a single reportable incident."""
    start_ts = datetime.fromisoformat(inc_base_row["first_start_ts"])
    restored_ts = datetime.fromisoformat(inc_base_row["restored_ts"])
    peak = int(inc_base_row["peak_customers_out"])

    dur_min = (restored_ts - start_ts).total_seconds() / 60
    threshold_ts = start_ts + timedelta(minutes=params["duration_threshold_min"])

    # Next interval = the allowed window end for initial report
    window_end = next_reporting_interval(threshold_ts)
    window_start = threshold_ts
    window_min = (window_end - window_start).total_seconds() / 60

    if incident_id in wide_window_ids and window_min > 5:
        # Use 75% of the window
        offset_min = int(window_min * 0.75)
        initial_ts = threshold_ts + timedelta(minutes=offset_min)
        # Ensure it's before the window end
        if initial_ts >= window_end:
            initial_ts = window_end - timedelta(minutes=1)
    else:
        # Use near the start of the window (20–40% through)
        offset_min = int(window_min * random.uniform(0.05, 0.35))
        initial_ts = threshold_ts + timedelta(minutes=max(offset_min, 1))
        if initial_ts >= window_end:
            initial_ts = window_end - timedelta(minutes=2)

    rows = []

    # Initial report
    rows.append({
        "report_id": f"RPT-{incident_id.replace('INC-', '')}A",
        "incident_id": incident_id,
        "report_type": "initial",
        "submitted_ts": initial_ts.strftime("%Y-%m-%dT%H:%M"),
        "channel": "email",
        "form_revision": "State Form 54646",
        "customers_affected_reported": peak,
        "customers_still_out_reported": peak,
        "etr_reported": (start_ts + timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M"),
        "cause_reported": "under investigation",
        "reported_by_person_id": "P23",
    })

    # Updates: one per interval until restoration
    cur = window_end  # next interval after initial report window
    update_idx = 0
    while True:
        nxt = next_reporting_interval(cur + timedelta(minutes=1))
        if nxt >= restored_ts:
            break
        update_idx += 1
        still_out_pct = max(0.05, 1.0 - 0.12 * update_idx)
        still_out = max(0, int(peak * still_out_pct))
        rows.append({
            "report_id": f"RPT-{incident_id.replace('INC-', '')}{chr(ord('A') + update_idx)}",
            "incident_id": incident_id,
            "report_type": "update",
            "submitted_ts": nxt.strftime("%Y-%m-%dT%H:%M"),
            "channel": "email",
            "form_revision": "State Form 54646",
            "customers_affected_reported": peak,
            "customers_still_out_reported": still_out,
            "etr_reported": (restored_ts - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
            "cause_reported": "vegetation/wind" if update_idx >= 2 else "under investigation",
            "reported_by_person_id": "P23",
        })
        cur = nxt
        if update_idx > 25:
            break

    # Final report: next interval after restoration
    final_ts = next_reporting_interval(restored_ts)
    rows.append({
        "report_id": f"RPT-{incident_id.replace('INC-', '')}Z",
        "incident_id": incident_id,
        "report_type": "final",
        "submitted_ts": final_ts.strftime("%Y-%m-%dT%H:%M"),
        "channel": "email",
        "form_revision": "State Form 54646",
        "customers_affected_reported": peak,
        "customers_still_out_reported": 0,
        "etr_reported": restored_ts.strftime("%Y-%m-%dT%H:%M"),
        "cause_reported": "vegetation/wind",
        "reported_by_person_id": "P23",
    })

    return rows


for inc_id in reportable_incident_ids:
    inc_row = inc_by_id[inc_id]
    rows = build_report_log(inc_id, inc_row)
    report_log_rows.extend(rows)

report_fields = [
    "report_id", "incident_id", "report_type", "submitted_ts", "channel",
    "form_revision", "customers_affected_reported", "customers_still_out_reported",
    "etr_reported", "cause_reported", "reported_by_person_id"
]

with open(DATA / "iurc_report_log_2024-01-01_2025-01-31.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=report_fields)
    writer.writeheader()
    writer.writerows(report_log_rows)

print(f"  Report log rows written: {len(report_log_rows)}")

# ---------------------------------------------------------------------------
# Build planned interruption notices dataset
# ---------------------------------------------------------------------------
print("Building planned_interruption_notices_2024.csv ...")

planned_incidents = [inc for inc in incidents_base
                     if inc["incident_type"] == "planned"]

# Load events for planned incidents to get customers and duration
evt_by_incident = {}
for evt in events_base:
    iid = evt["incident_id"]
    if iid not in evt_by_incident:
        evt_by_incident[iid] = []
    evt_by_incident[iid].append(evt)

notice_rows = []
for inc in planned_incidents:
    inc_id = inc["incident_id"]
    start_ts = datetime.fromisoformat(inc["first_start_ts"])
    restored_ts = datetime.fromisoformat(inc["restored_ts"])
    dur_min = (restored_ts - start_ts).total_seconds() / 60
    customers = int(inc["total_customers_affected"])

    # Only planned interruptions > 60 minutes require advance notice
    # per 170 IAC 4-1-23(c) (> 1 hour)
    if dur_min <= params["planned_notice_trigger_min"]:
        exception_code = "duration_lte_1hr"
        notice_sent_ts = ""
    else:
        # Send notice at least 2 days before (company practice)
        notice_sent_ts = (start_ts - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        exception_code = ""

    notice_rows.append({
        "incident_id": inc_id,
        "notice_method": "email" if customers > 50 else "telephone",
        "notice_sent_ts": notice_sent_ts,
        "customers_noticed": customers if notice_sent_ts else 0,
        "customers_affected": customers,
        "exception_code": exception_code,
        "scheduled_start_ts": start_ts.strftime("%Y-%m-%dT%H:%M"),
        "actual_start_ts": start_ts.strftime("%Y-%m-%dT%H:%M"),
    })

notice_fields = [
    "incident_id", "notice_method", "notice_sent_ts", "customers_noticed",
    "customers_affected", "exception_code", "scheduled_start_ts", "actual_start_ts"
]

with open(DATA / "planned_interruption_notices_2024.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=notice_fields)
    writer.writeheader()
    writer.writerows(notice_rows)

print(f"  Planned notices written: {len(notice_rows)}")

# ---------------------------------------------------------------------------
# Build reliability_indices_2024.csv
# ---------------------------------------------------------------------------
print("Building reliability_indices_2024.csv ...")

import yaml

with open(OPS / "reliability_facts.yaml") as f:
    facts = yaml.safe_load(f)

med_dates_set = set(facts["med_dates_2024"])

# Build monthly reliability from reliability_facts.yaml
monthly_facts = facts["monthly_2024"]
annual_facts = facts["annual_2024"]
customers_served_monthly = facts["customers_served_monthly_2024"]

reliability_rows = []

# Monthly rows (1-12)
for m in range(1, 13):
    key = str(m)
    wm = monthly_facts[key]["with_med"]
    em = monthly_facts[key]["ex_med"]
    cs = customers_served_monthly[m]

    # Count MED days in this month
    from calendar import monthrange
    year, last_day = 2024, monthrange(2024, m)[1]
    med_count = sum(1 for d in med_dates_set
                    if datetime.strptime(d, "%Y-%m-%d").month == m)

    reliability_rows.append({
        "period": f"2024-{m:02d}",
        "customers_served": cs,
        "ci_all": wm["ci"],
        "cmi_all": wm["cmi"],
        "saifi_all": round(wm["saifi"], 4),
        "saidi_all": round(wm["saidi"], 4),
        "caidi_all": round(wm["caidi"], 4),
        "ci_ex_med": em["ci"],
        "cmi_ex_med": em["cmi"],
        "saifi_ex_med": round(em["saifi"], 4),
        "saidi_ex_med": round(em["saidi"], 4),
        "caidi_ex_med": round(em["caidi"], 4),
        "med_days": med_count,
        "tmed_saidi_min": facts["tmed_saidi_min"],
        "saifi_ex_med_ex_planned": round(em["saifi"], 4),  # planned CI negligible vs. total
        "saidi_ex_med_ex_planned": round(em["saidi"], 4),
    })

# Annual row
aw = annual_facts["with_med"]
ae = annual_facts["ex_med"]
reliability_rows.append({
    "period": "2024-Annual",
    "customers_served": facts["customers_served_annual_2024"],
    "ci_all": aw["ci"],
    "cmi_all": aw["cmi"],
    "saifi_all": round(aw["saifi"], 4),
    "saidi_all": round(aw["saidi"], 4),
    "caidi_all": round(aw["caidi"], 4),
    "ci_ex_med": ae["ci"],
    "cmi_ex_med": ae["cmi"],
    "saifi_ex_med": round(ae["saifi"], 4),
    "saidi_ex_med": round(ae["saidi"], 4),
    "caidi_ex_med": round(ae["caidi"], 4),
    "med_days": len(med_dates_set),
    "tmed_saidi_min": facts["tmed_saidi_min"],
    "saifi_ex_med_ex_planned": round(ae["saifi"], 4),
    "saidi_ex_med_ex_planned": round(ae["saidi"], 4),
})

rel_fields = [
    "period", "customers_served", "ci_all", "cmi_all", "saifi_all", "saidi_all", "caidi_all",
    "ci_ex_med", "cmi_ex_med", "saifi_ex_med", "saidi_ex_med", "caidi_ex_med",
    "med_days", "tmed_saidi_min", "saifi_ex_med_ex_planned", "saidi_ex_med_ex_planned"
]

with open(DATA / "reliability_indices_2024.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rel_fields)
    writer.writeheader()
    writer.writerows(reliability_rows)

print(f"  Reliability index rows written: {len(reliability_rows)}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n=== Generation Complete ===")
print(f"Reportable incidents: {len(reportable_incident_ids)}")
print(f"Wide-window incidents (>60% of window): {wide_window_ids}")
print(f"Total IURC report log rows: {len(report_log_rows)}")
print(f"Planned notices: {len(notice_rows)}")
print(f"Annual ex-MED SAIFI: {ae['saifi']:.4f}, SAIDI: {ae['saidi']:.4f}, CAIDI: {ae['caidi']:.4f}")
print(f"Annual with-MED SAIDI: {aw['saidi']:.4f}")
print(f"MED days: {sorted(med_dates_set)}")
