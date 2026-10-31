#!/usr/bin/env python3
"""
generate_vm_data.py — Deterministic generator for RPL-DO-PLN-002 datasets.
Seed: 2024.  Run from any directory; uses absolute paths from script location.

NOTE (gap RPL-DO-PLN-002-G001): The T04 circuits_master.csv sets last_trim_year
for all circuits to 2019-2021, making all circuits simultaneously eligible in 2025.
Per §2 contractor-capacity constraints, the 2025 schedule selects the highest-priority
~1/cycle fraction of each category (annual target = category_OH / cycle).
Remaining eligible circuits are deferred to the next cycle rotation.
"""

import csv
import json
import math
import os
import random
import hashlib
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DOC_DIR = SCRIPT_DIR.parent
DATA_DIR = DOC_DIR / "data"
GLOBAL_OPS = DOC_DIR.parent.parent / "_global" / "ops"

CIRCUITS_MASTER   = GLOBAL_OPS / "circuits_master.csv"
OUTAGE_EVENTS     = GLOBAL_OPS / "outage_events_base.csv"
RELIABILITY_YAML  = GLOBAL_OPS / "reliability_facts.yaml"

SEED = 2024
rng  = random.Random(SEED)

# ── regulatory params (from grounding pack — §2 of RPL-DO-PLN-002) ────────────
params = {
    "notice_min_calendar_days": 14,           # 170 IAC 4-9-4(a)
    "easement_request_business_days": 5,      # 170 IAC 4-9-3(b)
    "estimated_day_request_calendar_days": 3, # 170 IAC 4-9-4(e)
    "estimated_day_advance_business_days": 3, # 170 IAC 4-9-4(e)
    "implied_consent_weeks": 2,               # 170 IAC 4-9-2(6)
    "debris_removal_calendar_days": 3,        # 170 IAC 4-9-7(e)
    "dispute_pre_work_objection_business_days": 5,  # 170 IAC 4-9-8(a)
    "dispute_utility_response_business_days": 3,    # 170 IAC 4-9-8(b) / 4-9-10(b)
    "dispute_stay_lift_calendar_days": 7,           # 170 IAC 4-9-8(d)(3)
    "dispute_records_months": 6,                    # 170 IAC 16-1-4(b)
    "informal_complaint_days": 7,                   # 170 IAC 16-1-4(c)(5)
    "consumer_affairs_decision_days": 30,           # 170 IAC 16-1-5(c)(5)
    "director_review_days": 7,                      # 170 IAC 16-1-5(d)
    "commission_review_days": 20,                   # 170 IAC 16-1-6(a)
    "line_upgrade_notice_calendar_days": 60,        # 170 IAC 4-9-5(a)
    "annual_report_deadline": "March 31",           # 170 IAC 4-9-7(g)
    "over_25pct_canopy_requires_consent": True,     # 170 IAC 4-9-7(c)
    "emergency_over_25pct_allowed": True,           # 170 IAC 4-9-6
}

# ── company practice params (not regulatory) ──────────────────────────────────
company_params = {
    "cycle_backbone":          4,    # years — company practice
    "cycle_lateral_dominant":  5,
    "cycle_urban_ug_dominant": 6,
    "unit_cost_backbone":   9500,    # $/OH-mile — company practice
    "unit_cost_lateral":    8200,
    "unit_cost_urban":      7000,
    "door_hanger_days_before_work": 3,  # company practice
    "notice_letter_typical_lead": 21,   # company practice (exceeds 14-day minimum)
    "budget_2025_total": 41_600_000,    # exact — from §24
}

CYCLE_MAP = {
    "backbone":           company_params["cycle_backbone"],
    "lateral_dominant":   company_params["cycle_lateral_dominant"],
    "urban_ug_dominant":  company_params["cycle_urban_ug_dominant"],
}
UNIT_COST_MAP = {
    "backbone":          company_params["unit_cost_backbone"],
    "lateral_dominant":  company_params["unit_cost_lateral"],
    "urban_ug_dominant": company_params["unit_cost_urban"],
}
SC_CONTRACTOR = {
    "LAF": "Contractor A", "FRK": "Contractor A", "DAN": "Contractor A",
    "CRW": "Contractor B", "THT": "Contractor B",
}


# ── Indiana business-days helper ──────────────────────────────────────────────
IN_HOLIDAYS = {
    date(2024, 1, 1), date(2024, 1, 15), date(2024, 5, 27), date(2024, 7, 4),
    date(2024, 9, 2), date(2024, 11, 28), date(2024, 11, 29),
    date(2024, 12, 24), date(2024, 12, 25),
    date(2025, 1, 1), date(2025, 1, 20), date(2025, 5, 26), date(2025, 7, 4),
    date(2025, 9, 1), date(2025, 11, 27), date(2025, 11, 28),
    date(2025, 12, 24), date(2025, 12, 25),
}


def quarter_range(year: int, q: int):
    s = {1: date(year,1,1), 2: date(year,4,1), 3: date(year,7,1), 4: date(year,10,1)}
    e = {1: date(year,3,31), 2: date(year,6,30), 3: date(year,9,30), 4: date(year,12,31)}
    return s[q], e[q]


# ── read helpers ──────────────────────────────────────────────────────────────
def read_circuits():
    with open(CIRCUITS_MASTER, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_outage_events():
    with open(OUTAGE_EVENTS, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_customers_monthly():
    """Parse customers_served_monthly from reliability_facts.yaml."""
    monthly = {}
    in_section = False
    with open(RELIABILITY_YAML, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s.startswith("customers_served_monthly"):
                in_section = True
                continue
            if in_section:
                if ":" in s and (s[0].isdigit() or s.startswith("'")):
                    k, v = s.split(":", 1)
                    monthly[k.strip().strip("'")] = int(v.strip())
                elif s and not s.startswith(" "):
                    break
    return monthly


# ─────────────────────────────────────────────────────────────────────────────
# 1.  vm_circuit_schedule_2025.csv
# ─────────────────────────────────────────────────────────────────────────────
def generate_circuit_schedule(circuits, tree_ci_map, routine_budget=None):
    """
    Select highest-priority circuits per category up to the annual target miles
    (total_cat_OH / cycle).  All 528 circuits are eligible in 2025 per T04 data;
    the annual target is what fits in one contractor season.  See module docstring.
    """
    # Annual target miles per category
    cat_oh = defaultdict(float)
    for c in circuits:
        cat_oh[c["vm_category"]] += float(c["oh_miles"])
    annual_targets = {cat: cat_oh[cat] / CYCLE_MAP[cat] for cat in CYCLE_MAP}

    # Sort eligible circuits per category by descending tree CI then circuit_id
    eligible = defaultdict(list)
    for c in circuits:
        cat = c["vm_category"]
        last_trim = int(c.get("last_trim_year", 0))
        if last_trim + CYCLE_MAP.get(cat, 5) > 2025:
            continue  # not yet due
        ci = tree_ci_map.get(c["circuit_id"], 0)
        eligible[cat].append((ci, c["circuit_id"], c))
    for cat in eligible:
        eligible[cat].sort(key=lambda x: (-x[0], x[1]))

    # Select up to target miles per category
    selected = []
    for cat in ("backbone", "lateral_dominant", "urban_ug_dominant"):
        target = annual_targets[cat]
        cumulative = 0.0
        for _ci, _cid, c in eligible.get(cat, []):
            if cumulative >= target * 1.01:
                break
            selected.append(c)
            cumulative += float(c["oh_miles"])

    # Build schedule rows
    quarter_probs = [0.22, 0.28, 0.28, 0.22]
    notice_counter = 1
    rows = []

    for c in selected:
        cat = c["vm_category"]
        cycle = CYCLE_MAP[cat]
        last_trim = int(c.get("last_trim_year", 2025 - cycle))
        oh_miles = float(c["oh_miles"])
        sc = c["service_center"]

        # Use lognormal centered at -σ²/2 so E[e^X]=1 (mean density factor = 1)
        df = rng.lognormvariate(-0.35**2/2, 0.35)
        df = max(0.4, min(3.0, df))
        est_cost = int(oh_miles * UNIT_COST_MAP[cat] * df)

        q = rng.choices([1, 2, 3, 4], weights=quarter_probs, k=1)[0]
        q_start, q_end = quarter_range(2025, q)
        days_in_q = (q_end - q_start).days
        start_offset = rng.randint(0, max(0, days_in_q - 30))
        p_start = q_start + timedelta(days=start_offset)
        crew_speed = rng.uniform(0.6, 1.2)
        crews = rng.randint(1, 3)
        dur = max(3, min(int(math.ceil(oh_miles / (crew_speed * crews))), 90))
        p_end = min(p_start + timedelta(days=dur), q_end)

        # Notice dates: ≥14 calendar days before work; 10% in 14-17 day window
        if rng.random() < 0.10:
            lead = rng.randint(14, 17)
        else:
            lead = rng.randint(18, 35)
        letter_date = p_start - timedelta(days=lead)
        dh_date = p_start - timedelta(days=company_params["door_hanger_days_before_work"])
        if dh_date < letter_date:
            dh_date = letter_date + timedelta(days=1)

        rows.append({
            "circuit_id":             c["circuit_id"],
            "substation_id":          c["substation_id"],
            "service_center":         sc,
            "county":                 c["county"],
            "voltage_kv":             c["voltage_kv"],
            "phase_type":             c["phase_type"],
            "vm_category":            cat,
            "cycle_years":            cycle,
            "last_trim_year":         last_trim,
            "scheduled_quarter_2025": f"Q{q}",
            "overhead_miles":         round(oh_miles, 1),
            "contractor":             SC_CONTRACTOR.get(sc, "Contractor A"),
            "est_cost_usd":           est_cost,
            "planned_start_date":     p_start.isoformat(),
            "planned_end_date":       p_end.isoformat(),
            "notice_batch_id":        f"VMN-2025-{notice_counter:03d}",
            "notice_letter_date":     letter_date.isoformat(),
            "door_hanger_start_date": dh_date.isoformat(),
            "customers_on_circuit":   int(c["customers_on_circuit"]),
            "tree_ci_2024":           tree_ci_map.get(c["circuit_id"], 0),
            "priority_rank":          0,   # filled below
            "schedule_note":          "",
        })
        notice_counter += 1

    # Assign priority ranks (highest CI first)
    rows.sort(key=lambda r: (-r["tree_ci_2024"], r["circuit_id"]))
    for i, r in enumerate(rows):
        r["priority_rank"] = i + 1

    # Scale est_cost_usd to match routine_budget within 0.5% (acceptance test 2)
    if routine_budget is not None and rows:
        raw_total = sum(r["est_cost_usd"] for r in rows)
        if raw_total > 0:
            scale = routine_budget / raw_total
            for r in rows:
                r["est_cost_usd"] = int(r["est_cost_usd"] * scale)
            # Adjust last row for any rounding residual
            residual = routine_budget - sum(r["est_cost_usd"] for r in rows)
            rows[-1]["est_cost_usd"] += residual

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 2.  vm_work_completed_2024.csv
#     T04 master has no circuits with last_trim_year=2024, so we synthesize a
#     plausible prior-year dataset: same approximate circuit mix but different
#     subset (using deterministic shuffle), representing the 2024 annual program.
# ─────────────────────────────────────────────────────────────────────────────
def generate_work_completed_2024(circuits, tree_ci_map):
    """
    Simulate the 2024 completed program.  Uses a separate RNG stream (seed 2023)
    to pick circuits and parameters independently from the 2025 schedule.
    """
    rng2024 = random.Random(2023)

    cat_oh = defaultdict(float)
    for c in circuits:
        cat_oh[c["vm_category"]] += float(c["oh_miles"])
    annual_targets = {cat: cat_oh[cat] / CYCLE_MAP[cat] for cat in CYCLE_MAP}

    # Sort by descending CI then reverse circuit_id (different from 2025 priority)
    eligible = defaultdict(list)
    for c in circuits:
        cat = c["vm_category"]
        ci = tree_ci_map.get(c["circuit_id"], 0)
        eligible[cat].append((ci, c["circuit_id"], c))
    for cat in eligible:
        eligible[cat].sort(key=lambda x: (-x[0], x[1]))
        # Reverse so 2024 picks different circuits than 2025
        eligible[cat] = eligible[cat][::-1]

    selected = []
    for cat in ("backbone", "lateral_dominant", "urban_ug_dominant"):
        target = annual_targets[cat]
        cumulative = 0.0
        for _ci, _cid, c in eligible.get(cat, []):
            if cumulative >= target * 1.01:
                break
            selected.append(c)
            cumulative += float(c["oh_miles"])

    rows = []
    for c in selected:
        cat = c["vm_category"]
        oh_planned = round(float(c["oh_miles"]), 1)
        oh_actual  = round(oh_planned * rng2024.uniform(0.93, 1.02), 1)
        # Random completion date in 2024
        start_d = date(2024, 1, 1) + timedelta(days=rng2024.randint(5, 330))
        comp_d  = start_d + timedelta(days=rng2024.randint(5, 45))
        if comp_d > date(2024, 12, 31):
            comp_d = date(2024, 12, 15)
        unit_2024 = {"backbone": 9200, "lateral_dominant": 7900, "urban_ug_dominant": 6800}
        df = rng2024.lognormvariate(0.0, 0.35)
        df = max(0.4, min(3.0, df))
        actual_cost = int(oh_actual * unit_2024.get(cat, 8000) * df)
        rows.append({
            "circuit_id":       c["circuit_id"],
            "substation_id":    c["substation_id"],
            "service_center":   c["service_center"],
            "county":           c["county"],
            "voltage_kv":       c["voltage_kv"],
            "vm_category":      cat,
            "contractor":       SC_CONTRACTOR.get(c["service_center"], "Contractor A"),
            "planned_miles":    oh_planned,
            "actual_miles":     oh_actual,
            "completion_date":  comp_d.isoformat(),
            "actual_cost_usd":  actual_cost,
            "audit_pass_pct":   round(rng2024.uniform(88, 100), 1),
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 3.  vm_tree_outages_2024.csv  (DERIVED from outage_events_base.csv)
# ─────────────────────────────────────────────────────────────────────────────
def generate_tree_outages_2024(events, customers_monthly):
    """Aggregate vegetation outage events by month × tree_location × med_flag."""

    # Aggregation containers
    veg_agg = {}   # (month, loc, med) -> {outages, ci, cmi}
    all_agg = {}   # month -> {outages, ci}

    for e in events:
        ts = e.get("start_ts", "")
        if not ts.startswith("2024"):
            continue
        month = int(ts[5:7])

        if month not in all_agg:
            all_agg[month] = {"outages": 0, "ci": 0}
        all_agg[month]["outages"] += 1
        all_agg[month]["ci"] += int(e.get("customers_affected", 0) or 0)

        if e.get("cause_category") != "vegetation":
            continue

        loc = (e.get("tree_location") or "unknown").strip() or "unknown"
        med = e.get("med_flag", "N") or "N"
        key = (month, loc, med)
        if key not in veg_agg:
            veg_agg[key] = {"outages": 0, "ci": 0, "cmi": 0}
        veg_agg[key]["outages"] += 1
        veg_agg[key]["ci"]      += int(e.get("customers_affected", 0) or 0)
        veg_agg[key]["cmi"]     += int(e.get("customer_minutes", 0) or 0)

    rows = []
    for (month, loc, med), agg in sorted(veg_agg.items()):
        cs = customers_monthly.get(str(month), 405805)
        ci  = agg["ci"]
        cmi = agg["cmi"]
        all_c = all_agg.get(month, {"outages": 0, "ci": 0})
        all_ci = all_c["ci"]
        rows.append({
            "month":                   month,
            "tree_location":           loc,
            "med_flag":                med,
            "sustained_outages":       agg["outages"],
            "customer_interruptions":  ci,
            "customer_minutes":        cmi,
            "tree_saifi_contribution": round(ci / cs, 6) if cs else 0,
            "tree_saidi_contribution": round(cmi / cs, 6) if cs else 0,
            "all_cause_outages":       all_c["outages"],
            "all_cause_ci":            all_ci,
            "tree_share_of_saifi_pct": round(ci / all_ci * 100, 2) if all_ci else 0,
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 4.  vm_budget_2024_2025.csv
# ─────────────────────────────────────────────────────────────────────────────
def generate_budget():
    """2025 total must equal exactly 41,600,000 (company_params["budget_2025_total"])."""
    lines = [
        ("BDG-001", "Routine cycle trimming — distribution",          "O&M",     "distribution",           27_940_000, "OH-miles",   3350),
        ("BDG-002", "Hazard tree removal (incl. outside-ROW)",         "O&M",     "distribution",            6_180_000, "trees",       4100),
        ("BDG-003", "Herbicide / brush / mowing (IVM)",                "O&M",     "distribution",            2_580_000, "acres",       3200),
        ("BDG-004", "Mid-cycle, hot spot and customer-request work",    "O&M",     "distribution",            2_020_000, "work-orders",  680),
        ("BDG-005", "Storm / emergency vegetation (non-MED)",           "O&M",     "distribution",            1_490_000, "events",      None),
        ("BDG-006", "69 kV subtransmission ROW",                       "capital",  "subtransmission_69kv",      910_000, "ROW-miles",    42),
        ("BDG-007", "Contractor oversight, work planning and QA/QC",   "O&M",     "distribution",              390_000, "audits",       320),
        ("BDG-008", "Customer education and communications",            "O&M",     "distribution",               90_000, "campaigns",      6),
    ]
    # Force exact total
    raw_total = sum(l[4] for l in lines)
    diff = 41_600_000 - raw_total
    lines[0] = (*lines[0][:4], lines[0][4] + diff, *lines[0][5:])
    assert sum(l[4] for l in lines) == 41_600_000, f"Budget mismatch: {sum(l[4] for l in lines)}"

    rows = []
    rng_b = random.Random(SEED + 1)
    for lid, cat, cost_type, system, bgt_2025, unit, units_2025 in lines:
        bgt_2024 = int(bgt_2025 * rng_b.uniform(0.88, 1.08))
        act_2024 = int(bgt_2024 * rng_b.uniform(0.90, 1.12))
        var = act_2024 - bgt_2024
        var_pct = round(var / bgt_2024 * 100, 1) if bgt_2024 else 0
        if var_pct > 5:
            note = "Storm-driven scope increase Q3; accelerated trimming on high-CI circuits."
        elif var_pct < -5:
            note = "Favorable contractor pricing; mild late-winter enabled Q1 acceleration."
        else:
            note = ""
        uc = round(bgt_2025 / units_2025, 2) if units_2025 else ""
        rows.append({
            "line_id":          lid,
            "category":         cat,
            "cost_type":        cost_type,
            "system":           system,
            "budget_2024_usd":  bgt_2024,
            "actual_2024_usd":  act_2024,
            "variance_usd":     var,
            "variance_note":    note,
            "budget_2025_usd":  bgt_2025,
            "unit":             unit,
            "units_2025":       units_2025 if units_2025 is not None else "",
            "unit_cost_2025":   uc,
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 5.  vm_customer_contacts_2024.csv
# ─────────────────────────────────────────────────────────────────────────────
def generate_customer_contacts(circuits):
    """300–700 logged contacts; 10–40 formal disputes; 2–15 IURC CAD referrals."""
    cat_weights = {
        "notice_question": 0.30, "debris": 0.18, "property_damage": 0.08,
        "refusal_of_work": 0.06, "tree_health": 0.10, "storm_debris": 0.07,
        "customer_request_trim": 0.09, "easement_documentation_request": 0.05,
        "removal_dispute": 0.04, "other": 0.03,
    }
    channels = ["phone", "web", "email", "letter", "in-person"]
    circuit_ids = [c["circuit_id"] for c in circuits]
    resolutions = {
        "notice_question":                "Information provided by contact center.",
        "debris":                         "Debris removed within 3 calendar days.",
        "property_damage":                "Claim filed under RPL-CLM-PRO-001.",
        "refusal_of_work":                "Work rescheduled; consent obtained.",
        "tree_health":                    "ISA arborist assessment completed; customer notified.",
        "storm_debris":                   "Advised: storm debris not an RPL obligation (170 IAC 4-9-7(f)).",
        "customer_request_trim":          "Customer trim order added to mid-cycle schedule.",
        "easement_documentation_request": "Easement copy provided within 5 business days.",
        "removal_dispute":                "Second-representative review completed; dispute resolved.",
        "other":                          "Referred to appropriate department.",
    }
    total = rng.randint(420, 560)
    cats = list(cat_weights.keys())
    weights = list(cat_weights.values())
    rows = []
    for i in range(1, total + 1):
        recv = date(2024, 1, 1) + timedelta(days=rng.randint(0, 364))
        cat  = rng.choices(cats, weights=weights, k=1)[0]
        ckt  = rng.choice(circuit_ids)
        chan = rng.choice(channels)
        esc  = "Y" if cat in ("removal_dispute", "property_damage", "refusal_of_work") and rng.random() < 0.5 else "N"
        iurc = "Y" if esc == "Y" and rng.random() < 0.09 else "N"
        iurc_info = iurc  # if IURC referral made, info was provided
        dtc  = rng.randint(1, 5) if cat in ("notice_question", "other") else rng.randint(1, 30)
        closed = min(recv + timedelta(days=dtc), date(2024, 12, 31))
        rows.append({
            "contact_id":              f"VMC-2024-{i:04d}",
            "received_date":           recv.isoformat(),
            "channel":                 chan,
            "circuit_id":              ckt,
            "category":                cat,
            "escalated_to_second_rep": esc,
            "iurc_cad_referral":       iurc,
            "resolution":              resolutions[cat],
            "closed_date":             closed.isoformat(),
            "days_to_close":           dtc,
            "iurc_info_provided":      iurc_info,
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# CSV / manifest helpers
# ─────────────────────────────────────────────────────────────────────────────
def write_csv(path: Path, rows: list, fields: list):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    circuits = read_circuits()
    events   = read_outage_events()
    customers_monthly = read_customers_monthly()

    # Pre-compute tree CI per circuit for 2024
    tree_ci_map = {}
    for e in events:
        if e.get("cause_category") == "vegetation" and e.get("start_ts", "").startswith("2024"):
            cid = e.get("circuit_id", "")
            tree_ci_map[cid] = tree_ci_map.get(cid, 0) + 1

    # Compute budget first so schedule can reconcile to BDG-001
    budget = generate_budget()
    routine_budget = next(r["budget_2025_usd"] for r in budget if r["line_id"] == "BDG-001")

    # 1. Schedule
    schedule = generate_circuit_schedule(circuits, tree_ci_map, routine_budget=routine_budget)
    sched_fields = [
        "circuit_id","substation_id","service_center","county","voltage_kv","phase_type",
        "vm_category","cycle_years","last_trim_year","scheduled_quarter_2025","overhead_miles",
        "contractor","est_cost_usd","planned_start_date","planned_end_date",
        "notice_batch_id","notice_letter_date","door_hanger_start_date",
        "customers_on_circuit","tree_ci_2024","priority_rank","schedule_note",
    ]
    sched_path = DATA_DIR / "vm_circuit_schedule_2025.csv"
    write_csv(sched_path, schedule, sched_fields)
    total_oh = sum(r["overhead_miles"] for r in schedule)
    routine_cost = sum(r["est_cost_usd"] for r in schedule)
    print(f"vm_circuit_schedule_2025.csv: {len(schedule)} rows")
    print(f"  Σoh_miles = {total_oh:.1f}")
    print(f"  Σest_cost_usd = {routine_cost:,}")

    # 2. Work completed 2024
    wc2024 = generate_work_completed_2024(circuits, tree_ci_map)
    wc_fields = [
        "circuit_id","substation_id","service_center","county","voltage_kv",
        "vm_category","contractor","planned_miles","actual_miles",
        "completion_date","actual_cost_usd","audit_pass_pct",
    ]
    wc_path = DATA_DIR / "vm_work_completed_2024.csv"
    write_csv(wc_path, wc2024, wc_fields)
    print(f"vm_work_completed_2024.csv: {len(wc2024)} rows")

    # 3. Tree outages (derived)
    tree_outs = generate_tree_outages_2024(events, customers_monthly)
    to_fields = [
        "month","tree_location","med_flag","sustained_outages",
        "customer_interruptions","customer_minutes",
        "tree_saifi_contribution","tree_saidi_contribution",
        "all_cause_outages","all_cause_ci","tree_share_of_saifi_pct",
    ]
    to_path = DATA_DIR / "vm_tree_outages_2024.csv"
    write_csv(to_path, tree_outs, to_fields)
    print(f"vm_tree_outages_2024.csv: {len(tree_outs)} rows")

    # 4. Budget (already generated above)
    b_fields = [
        "line_id","category","cost_type","system",
        "budget_2024_usd","actual_2024_usd","variance_usd","variance_note",
        "budget_2025_usd","unit","units_2025","unit_cost_2025",
    ]
    b_path = DATA_DIR / "vm_budget_2024_2025.csv"
    write_csv(b_path, budget, b_fields)
    total_2025 = sum(r["budget_2025_usd"] for r in budget)
    print(f"vm_budget_2024_2025.csv: {len(budget)} rows; 2025 total = {total_2025:,}")

    # 5. Customer contacts
    contacts = generate_customer_contacts(circuits)
    c_fields = [
        "contact_id","received_date","channel","circuit_id","category",
        "escalated_to_second_rep","iurc_cad_referral",
        "resolution","closed_date","days_to_close","iurc_info_provided",
    ]
    c_path = DATA_DIR / "vm_customer_contacts_2024.csv"
    write_csv(c_path, contacts, c_fields)
    print(f"vm_customer_contacts_2024.csv: {len(contacts)} rows")

    # Manifest
    file_meta = [
        ("vm_circuit_schedule_2025.csv", sched_path, len(schedule), sched_fields),
        ("vm_work_completed_2024.csv",   wc_path,    len(wc2024),   wc_fields),
        ("vm_tree_outages_2024.csv",     to_path,    len(tree_outs),to_fields),
        ("vm_budget_2024_2025.csv",      b_path,     len(budget),   b_fields),
        ("vm_customer_contacts_2024.csv",c_path,     len(contacts), c_fields),
    ]
    manifest = {
        "doc_id": "RPL-DO-PLN-002",
        "generated_by": "scripts/generate_vm_data.py",
        "seed": SEED,
        "files": [
            {"file": fn, "rows": nr, "columns": len(cols),
             "sha256": sha256_file(fp), "generator_script": "scripts/generate_vm_data.py", "seed": SEED}
            for fn, fp, nr, cols in file_meta
        ],
    }
    with open(DATA_DIR / "_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print("_manifest.json written")

    return schedule, wc2024, tree_outs, budget, contacts, total_oh, routine_cost


if __name__ == "__main__":
    main()
