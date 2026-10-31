#!/usr/bin/env python3
"""
RPL-MTR-PGM-001 Dataset Generator
Seed: 2024 (deterministic)
Generates all datasets for the Meter Testing Program Plan.
"""
import numpy as np
import pandas as pd
import gzip
import json
import hashlib
import os
from datetime import date, timedelta

SEED = 2024
rng = np.random.default_rng(SEED)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CIRCUITS_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../../_global/ops/circuits_master.csv"
)

# ---------------------------------------------------------------------------
# REGULATORY PARAMETERS (from 170 IAC 4-1-*)
# ---------------------------------------------------------------------------
params = {
    "avg_error_limit_pct": 2.0,      # 170 IAC 4-1-9(b)(1)(A)
    "fl_error_limit_pct": 1.0,       # 170 IAC 4-1-9(b)(1)(B)
    "ll_error_limit_pct": 3.0,       # 170 IAC 4-1-9(b)(1)(C)
    "avg_pct_formula": "(FL + LL) / 2",  # 170 IAC 4-1-8(a)
    "ll_test_load_pct": 10,          # 170 IAC 4-1-8(a)
    "fl_test_load_pct": 100,         # 170 IAC 4-1-8(a)
    "ll_agreement_limit_pct": 0.5,   # 170 IAC 4-1-8(b)
    "new_meter_test_window_days": 60,  # 170 IAC 4-1-6(c)
    "records_retention_min_years": 3,  # 170 IAC 4-1-3
    "customer_test_report_days": 10,   # 170 IAC 4-1-11(d)
    "customer_appeal_days": 5,         # 170 IAC 4-1-11(e)
    "customer_test_free_first_two": True,  # 170 IAC 4-1-11(a)
    "customer_test_second_after_months": 12,  # 170 IAC 4-1-11(a)
    "customer_fee_charge_prior_months": 36,   # 170 IAC 4-1-11(b)(1)(A)
    "reference_standard_recal_years": 2,  # 170 IAC 4-1-7(C)
    "portable_error_threshold_pct": 1.0,  # 170 IAC 4-1-7(D)
    "periodic_interval_years": 16,    # 170 IAC 4-1-10(b),(d)
    "method_b_lot_min_size": 301,     # 170 IAC 4-1-10(c)(2)
    "method_b_u_pct": 102.0,          # 170 IAC 4-1-10(c)(5)
    "method_b_l_pct": 98.0,           # 170 IAC 4-1-10(c)(5)
    "method_b_aql": 2.50,             # 170 IAC 4-1-10(c)(4)
    "rejected_lot_accel_max_months": 96,  # 170 IAC 4-1-10(c)(7)
    "demand_register_interval_years": 8,  # 170 IAC 4-1-10(d)(1)(B),(H)
    "electronic_meter_interval_years": 16,  # 170 IAC 4-1-10(d)(2)
    "portable_pf_limit_pct": 2.0,     # 170 IAC 4-1-9(b)(5)
}

# ---------------------------------------------------------------------------
# COMPANY PRACTICE PARAMETERS
# ---------------------------------------------------------------------------
company_params = {
    # Sampling plan label (per orchestrator instruction — company practice)
    "sampling_plan_label": (
        "Internal procedure: RPL Meter Sampling Plan "
        "(based on variables-sampling principles consistent with "
        "ANSI/ASQC Z1.9-1993 Inspection Level II)"
    ),
    "sampling_plan_basis": "internal_procedure",
    # Sample sizes by lot size (indicative; labeled company practice)
    "sampling_table": [
        {"lot_min": 2,      "lot_max": 8,      "code": "B", "n": 3},
        {"lot_min": 9,      "lot_max": 15,     "code": "C", "n": 4},
        {"lot_min": 16,     "lot_max": 25,     "code": "D", "n": 5},
        {"lot_min": 26,     "lot_max": 50,     "code": "E", "n": 7},
        {"lot_min": 51,     "lot_max": 90,     "code": "F", "n": 10},
        {"lot_min": 91,     "lot_max": 150,    "code": "G", "n": 15},
        {"lot_min": 151,    "lot_max": 280,    "code": "H", "n": 25},
        {"lot_min": 281,    "lot_max": 500,    "code": "I", "n": 35},
        {"lot_min": 501,    "lot_max": 1200,   "code": "J", "n": 50},
        {"lot_min": 1201,   "lot_max": 3200,   "code": "K", "n": 75},
        {"lot_min": 3201,   "lot_max": 10000,  "code": "L", "n": 100},
        {"lot_min": 10001,  "lot_max": 35000,  "code": "M", "n": 150},
        {"lot_min": 35001,  "lot_max": 150000, "code": "N", "n": 200},
        {"lot_min": 150001, "lot_max": 500000, "code": "P", "n": 300},
    ],
    "ami_reconfig_threshold": 0.005,   # HES flag rate for anomaly pull
    "ami_zero_consumption_days": 10,   # days before flag
    "shop_test_capacity_per_day": 80,  # meters/day
    "field_test_crew_count": 4,
    "acceptance_lot_min_size": 500,
    "acceptance_lot_max_size": 6000,
    "transformer_rated_count_range": (6000, 9000),
    "annual_acceptance_lots_range": (8, 16),
}

def get_sample_size(lot_size: int) -> int:
    for row in company_params["sampling_table"]:
        if row["lot_min"] <= lot_size <= row["lot_max"]:
            return row["n"]
    return 300  # large lot fallback

# ---------------------------------------------------------------------------
# GROUP DEFINITIONS (54 groups, sums to 409,950)
# ---------------------------------------------------------------------------
# Fields: id, vendor_family, meter_technology, form, meter_class,
#         service_type, install_year_min, install_year_max, meter_count,
#         test_method (sample|periodic), periodic_interval_years (if periodic)
GROUPS = [
    # AMI 2S CL200 Vendor A — 16 groups, total 205,232
    {"id":"GRP-001","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2016,"install_year_max":2017,"meter_count":42000,"test_method":"sample"},
    {"id":"GRP-002","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2016,"install_year_max":2017,"meter_count":5000,"test_method":"sample"},
    {"id":"GRP-003","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2018,"install_year_max":2019,"meter_count":48000,"test_method":"sample"},
    {"id":"GRP-004","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2018,"install_year_max":2019,"meter_count":5000,"test_method":"sample"},
    {"id":"GRP-005","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2020,"install_year_max":2021,"meter_count":55000,"test_method":"sample"},
    {"id":"GRP-006","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2020,"install_year_max":2021,"meter_count":8000,"test_method":"sample"},
    {"id":"GRP-007","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2022,"install_year_max":2023,"meter_count":26000,"test_method":"sample"},
    {"id":"GRP-008","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2022,"install_year_max":2023,"meter_count":3000,"test_method":"sample"},
    {"id":"GRP-009","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2024,"install_year_max":2024,"meter_count":11232,"test_method":"sample"},
    {"id":"GRP-010","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2024,"install_year_max":2024,"meter_count":2000,"test_method":"sample"},
    # AMI 2S CL200 Vendor B — 6 groups, total 114,000
    {"id":"GRP-011","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2016,"install_year_max":2018,"meter_count":29000,"test_method":"sample"},
    {"id":"GRP-012","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2016,"install_year_max":2018,"meter_count":4000,"test_method":"sample"},
    {"id":"GRP-013","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2019,"install_year_max":2021,"meter_count":43000,"test_method":"sample"},
    {"id":"GRP-014","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2019,"install_year_max":2021,"meter_count":5000,"test_method":"sample"},
    {"id":"GRP-015","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2022,"install_year_max":2024,"meter_count":30000,"test_method":"sample"},
    {"id":"GRP-016","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2022,"install_year_max":2024,"meter_count":3000,"test_method":"sample"},
    # AMI 2S CL320 — 2 groups, total 7,424
    {"id":"GRP-017","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL320","service_type":"commercial_sc","install_year_min":2019,"install_year_max":2022,"meter_count":4000,"test_method":"sample"},
    {"id":"GRP-018","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"2S","meter_class":"CL320","service_type":"commercial_sc","install_year_min":2021,"install_year_max":2024,"meter_count":3424,"test_method":"sample"},
    # AMI 12S CL200 — 4 groups, total 14,848
    {"id":"GRP-019","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"12S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2017,"install_year_max":2020,"meter_count":6224,"test_method":"sample"},
    {"id":"GRP-020","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"12S","meter_class":"CL200","service_type":"commercial_ct","install_year_min":2017,"install_year_max":2020,"meter_count":1200,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-021","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"12S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2019,"install_year_max":2023,"meter_count":6224,"test_method":"sample"},
    {"id":"GRP-022","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"12S","meter_class":"CL200","service_type":"commercial_ct","install_year_min":2019,"install_year_max":2023,"meter_count":1200,"test_method":"periodic","periodic_interval_years":16},
    # AMI 16S CL200/CL320 — 4 groups, total 14,848
    {"id":"GRP-023","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"16S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2017,"install_year_max":2021,"meter_count":6924,"test_method":"sample"},
    {"id":"GRP-024","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"16S","meter_class":"CL200","service_type":"industrial_ct","install_year_min":2017,"install_year_max":2021,"meter_count":500,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-025","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"16S","meter_class":"CL320","service_type":"commercial_sc","install_year_min":2019,"install_year_max":2023,"meter_count":6924,"test_method":"sample"},
    {"id":"GRP-026","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"16S","meter_class":"CL320","service_type":"industrial_ct","install_year_min":2019,"install_year_max":2023,"meter_count":500,"test_method":"periodic","periodic_interval_years":16},
    # AMI 9S CL20 — 4 groups, total 9,280
    {"id":"GRP-027","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"9S","meter_class":"CL20","service_type":"commercial_sc","install_year_min":2018,"install_year_max":2021,"meter_count":4290,"test_method":"sample"},
    {"id":"GRP-028","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"9S","meter_class":"CL20","service_type":"commercial_ct","install_year_min":2018,"install_year_max":2021,"meter_count":350,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-029","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"9S","meter_class":"CL20","service_type":"commercial_sc","install_year_min":2019,"install_year_max":2023,"meter_count":4290,"test_method":"sample"},
    {"id":"GRP-030","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"9S","meter_class":"CL20","service_type":"commercial_ct","install_year_min":2019,"install_year_max":2023,"meter_count":350,"test_method":"periodic","periodic_interval_years":16},
    # AMI 3S/4S/1S — 3 groups, total 5,568
    {"id":"GRP-031","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"3S","meter_class":"CL200","service_type":"residential","install_year_min":2017,"install_year_max":2022,"meter_count":1856,"test_method":"sample"},
    {"id":"GRP-032","vendor_family":"Vendor_A","meter_technology":"solid_state_AMI","form":"4S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2018,"install_year_max":2023,"meter_count":1856,"test_method":"sample"},
    {"id":"GRP-033","vendor_family":"Vendor_B","meter_technology":"solid_state_AMI","form":"1S","meter_class":"CL200","service_type":"residential","install_year_min":2016,"install_year_max":2022,"meter_count":1856,"test_method":"sample"},
    # AMR 2S CL200 — 8 groups, total 28,260
    {"id":"GRP-034","vendor_family":"Vendor_B","meter_technology":"solid_state_AMR","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2005,"install_year_max":2008,"meter_count":5000,"test_method":"sample"},
    {"id":"GRP-035","vendor_family":"Vendor_B","meter_technology":"solid_state_AMR","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2009,"install_year_max":2012,"meter_count":7000,"test_method":"sample"},
    {"id":"GRP-036","vendor_family":"Vendor_B","meter_technology":"solid_state_AMR","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2013,"install_year_max":2015,"meter_count":6000,"test_method":"sample"},
    {"id":"GRP-037","vendor_family":"Vendor_B","meter_technology":"solid_state_AMR","form":"2S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2005,"install_year_max":2010,"meter_count":1000,"test_method":"sample"},
    {"id":"GRP-038","vendor_family":"Vendor_B","meter_technology":"solid_state_AMR","form":"2S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2011,"install_year_max":2015,"meter_count":780,"test_method":"sample"},
    {"id":"GRP-039","vendor_family":"Vendor_C","meter_technology":"solid_state_AMR","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2005,"install_year_max":2009,"meter_count":4240,"test_method":"sample"},
    {"id":"GRP-040","vendor_family":"Vendor_C","meter_technology":"solid_state_AMR","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":2010,"install_year_max":2015,"meter_count":4240,"test_method":"sample"},
    {"id":"GRP-041","vendor_family":"Vendor_B","meter_technology":"solid_state_AMR","form":"2S","meter_class":"CL200","service_type":"commercial_sc","install_year_min":2006,"install_year_max":2013,"meter_count":0,"test_method":"sample"},  # placeholder, adjusted below
    # AMR 12S/16S/9S CT — 4 groups, total 3,140
    {"id":"GRP-042","vendor_family":"Vendor_B","meter_technology":"solid_state_AMR","form":"12S","meter_class":"CL200","service_type":"commercial_ct","install_year_min":2005,"install_year_max":2012,"meter_count":1099,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-043","vendor_family":"Vendor_C","meter_technology":"solid_state_AMR","form":"16S","meter_class":"CL200","service_type":"commercial_ct","install_year_min":2005,"install_year_max":2013,"meter_count":1099,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-044","vendor_family":"Vendor_B","meter_technology":"solid_state_AMR","form":"9S","meter_class":"CL20","service_type":"commercial_ct","install_year_min":2005,"install_year_max":2012,"meter_count":471,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-045","vendor_family":"Vendor_C","meter_technology":"solid_state_AMR","form":"9S","meter_class":"CL20","service_type":"commercial_ct","install_year_min":2006,"install_year_max":2015,"meter_count":471,"test_method":"periodic","periodic_interval_years":16},
    # EM 2S CL200 — 6 groups, total 6,836
    {"id":"GRP-046","vendor_family":"Vendor_C","meter_technology":"electromechanical","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":1972,"install_year_max":1985,"meter_count":1200,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-047","vendor_family":"Vendor_C","meter_technology":"electromechanical","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":1986,"install_year_max":1995,"meter_count":1700,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-048","vendor_family":"Vendor_C","meter_technology":"electromechanical","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":1996,"install_year_max":2004,"meter_count":1400,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-049","vendor_family":"legacy_other","meter_technology":"electromechanical","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":1972,"install_year_max":1985,"meter_count":700,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-050","vendor_family":"legacy_other","meter_technology":"electromechanical","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":1986,"install_year_max":1995,"meter_count":900,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-051","vendor_family":"legacy_other","meter_technology":"electromechanical","form":"2S","meter_class":"CL200","service_type":"residential","install_year_min":1996,"install_year_max":2004,"meter_count":936,"test_method":"periodic","periodic_interval_years":16},
    # EM 1S/12S — 3 groups, total 514
    {"id":"GRP-052","vendor_family":"Vendor_C","meter_technology":"electromechanical","form":"1S","meter_class":"CL200","service_type":"residential","install_year_min":1980,"install_year_max":2000,"meter_count":200,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-053","vendor_family":"Vendor_C","meter_technology":"electromechanical","form":"12S","meter_class":"CL200","service_type":"commercial_ct","install_year_min":1975,"install_year_max":1998,"meter_count":157,"test_method":"periodic","periodic_interval_years":16},
    {"id":"GRP-054","vendor_family":"legacy_other","meter_technology":"electromechanical","form":"1S","meter_class":"CL200","service_type":"residential","install_year_min":1972,"install_year_max":1990,"meter_count":157,"test_method":"periodic","periodic_interval_years":16},
]

# Fix the placeholder group 41 — add its count to group 040 and remove it
GROUPS = [g for g in GROUPS if g["meter_count"] > 0]

# Validate totals
total_check = sum(g["meter_count"] for g in GROUPS)
ami_check   = sum(g["meter_count"] for g in GROUPS if g["meter_technology"]=="solid_state_AMI")
amr_check   = sum(g["meter_count"] for g in GROUPS if g["meter_technology"]=="solid_state_AMR")
em_check    = sum(g["meter_count"] for g in GROUPS if g["meter_technology"]=="electromechanical")
assert total_check == 409950, f"Total mismatch: {total_check}"
assert ami_check   == 371200, f"AMI mismatch: {ami_check}"
assert amr_check   == 31400,  f"AMR mismatch: {amr_check}"
assert em_check    == 7350,   f"EM mismatch: {em_check}"
print(f"Group totals verified: {len(GROUPS)} groups, {total_check} meters")

# ---------------------------------------------------------------------------
# VENDOR CODE MAPPING
# ---------------------------------------------------------------------------
VENDOR_CODE = {"Vendor_A": "A", "Vendor_B": "B", "Vendor_C": "C", "legacy_other": "L"}

# ---------------------------------------------------------------------------
# SERVICE CENTERS AND COUNTIES
# ---------------------------------------------------------------------------
circuits_df = pd.read_csv(CIRCUITS_PATH)
circuit_ids = circuits_df["circuit_id"].values
service_centers = circuits_df["service_center"].values
counties = circuits_df["county"].values

# ---------------------------------------------------------------------------
# HELPER: generate install dates
# ---------------------------------------------------------------------------
def gen_install_dates(n, yr_min, yr_max, rng_obj):
    """Generate random install dates within year range, uniform over days."""
    days_min = (date(yr_min, 1, 1) - date(1970, 1, 1)).days
    days_max = (date(yr_max, 12, 31) - date(1970, 1, 1)).days
    epoch_days = rng_obj.integers(days_min, days_max + 1, size=n)
    return pd.to_datetime(epoch_days, unit="D", origin="unix").strftime("%Y-%m-%d")

# ---------------------------------------------------------------------------
# HELPER: compute accuracy and within_limits
# ---------------------------------------------------------------------------
def compute_accuracy(fl, ll):
    avg = (fl + ll) / 2.0
    within = (
        (np.abs(avg - 100.0) <= params["avg_error_limit_pct"]) &
        (np.abs(fl  - 100.0) <= params["fl_error_limit_pct"]) &
        (np.abs(ll  - 100.0) <= params["ll_error_limit_pct"])
    )
    return avg, within

# ---------------------------------------------------------------------------
# GENERATE METER REGISTRY
# ---------------------------------------------------------------------------
def generate_registry():
    print("Generating meter registry...")
    rows = []
    vendor_counters = {"A": 1, "B": 1, "C": 1, "L": 1}

    for grp in GROUPS:
        n = grp["meter_count"]
        vc = VENDOR_CODE[grp["vendor_family"]]
        # Serials
        start = vendor_counters[vc]
        serials = [f"RPL-{vc}-{i:07d}" for i in range(start, start + n)]
        vendor_counters[vc] += n
        # Install dates
        install_dates = gen_install_dates(
            n, grp["install_year_min"], grp["install_year_max"], rng
        )
        # Circuit assignment (random)
        cidx = rng.integers(0, len(circuit_ids), size=n)
        cids   = circuit_ids[cidx]
        scodes = service_centers[cidx]
        cntys  = counties[cidx]
        # Premise IDs (sequential per group)
        prem_start = start  # reuse vendor counter logic for uniqueness
        premise_ids = [f"PRM-{i:07d}" for i in range(prem_start, prem_start + n)]
        # Account IDs (99% active)
        active_mask = rng.random(n) < 0.99
        account_ids = np.where(
            active_mask,
            [f"ACC-{i:07d}" for i in range(prem_start, prem_start + n)],
            ""
        )
        # last_test_date: blank for new meters (install yr >= 2022); others get periodic or none
        last_test_dates = []
        last_test_reasons = []
        for i, idate in enumerate(install_dates):
            yr = int(idate[:4])
            if yr >= 2022:
                # Too new to have been tested in-service (install test done at factory)
                last_test_dates.append("")
                last_test_reasons.append("")
            elif grp["test_method"] == "periodic":
                # Assign last test date ensuring no overdue (must be >= 2009-01-01)
                # 10% chance of being in final 20% window (last_test_date 2009-2012)
                if rng.random() < 0.12:
                    # Margin zone: test date 2009-2012
                    td = gen_install_dates(1, 2009, 2012, rng)[0]
                else:
                    # Comfortable: test date 2013-2023
                    td = gen_install_dates(1, 2013, 2023, rng)[0]
                last_test_dates.append(td)
                last_test_reasons.append("in_service_periodic")
            else:
                # Sample method: assign sparse last_test_date
                if rng.random() < 0.15:
                    td = gen_install_dates(1, 2018, 2024, rng)[0]
                    last_test_dates.append(td)
                    last_test_reasons.append("in_service_sample")
                else:
                    last_test_dates.append("")
                    last_test_reasons.append("")

        group_rows = {
            "meter_serial": serials,
            "meter_group_id": [grp["id"]] * n,
            "meter_technology": [grp["meter_technology"]] * n,
            "form": [grp["form"]] * n,
            "meter_class": [grp["meter_class"]] * n,
            "service_type": [grp["service_type"]] * n,
            "vendor_family": [grp["vendor_family"]] * n,
            "install_date": install_dates,
            "premise_id": premise_ids,
            "account_id": account_ids,
            "service_center": scodes,
            "county": cntys,
            "circuit_id": cids,
            "last_test_date": last_test_dates,
            "last_test_reason": last_test_reasons,
            "status": ["in_service"] * n,
        }
        rows.append(pd.DataFrame(group_rows))

    df = pd.concat(rows, ignore_index=True)
    print(f"  Registry rows: {len(df)}")
    return df

# ---------------------------------------------------------------------------
# GENERATE METER POPULATION
# ---------------------------------------------------------------------------
def generate_population(registry_df):
    print("Generating meter population...")
    rows = []
    for grp in GROUPS:
        n = grp["meter_count"]
        gdf = registry_df[registry_df["meter_group_id"] == grp["id"]]
        oldest_test = ""
        if grp["test_method"] == "periodic":
            valid_dates = gdf["last_test_date"][gdf["last_test_date"] != ""]
            if len(valid_dates) > 0:
                oldest_test = valid_dates.min()
        ssize = get_sample_size(n) if grp["test_method"] == "sample" else 0
        interval_basis = f"{grp.get('periodic_interval_years',16)} years (170 IAC 4-1-10)" if grp["test_method"]=="periodic" else "Annual sampling (company practice)"
        row = {
            "meter_group_id": grp["id"],
            "vendor_family": grp["vendor_family"],
            "meter_technology": grp["meter_technology"],
            "form": grp["form"],
            "meter_class": grp["meter_class"],
            "service_type": grp["service_type"],
            "install_year_band": f"{grp['install_year_min']}-{grp['install_year_max']}",
            "meter_count": n,
            "test_method": grp["test_method"],
            "group_rule": (
                f"Vendor: {grp['vendor_family']}; Form/Class: {grp['form']}/{grp['meter_class']}; "
                f"Service: {grp['service_type']}; Install: {grp['install_year_min']}-{grp['install_year_max']}"
            ),
            "sample_size_2025": ssize,
            "periodic_interval_basis": interval_basis,
            "oldest_last_test_date": oldest_test,
            "meters_due_2025_q1": int(n * 0.25) if grp["test_method"]=="periodic" else 0,
            "meters_due_2025_q2": int(n * 0.25) if grp["test_method"]=="periodic" else 0,
            "meters_due_2025_q3": int(n * 0.25) if grp["test_method"]=="periodic" else 0,
            "meters_due_2025_q4": (n - 3*int(n*0.25)) if grp["test_method"]=="periodic" else 0,
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    return df

# ---------------------------------------------------------------------------
# GENERATE STANDARDS CALIBRATION
# ---------------------------------------------------------------------------
def generate_standards():
    print("Generating standards calibration data...")
    rows = []
    ref_date = date(2024, 6, 15)  # last certified
    # 3 reference standards
    for i in range(1, 4):
        rows.append({
            "standard_id": f"RS-{i:03d}",
            "standard_level": "reference",
            "make_model_generic": f"Lab-Standard-Whr-{i}",
            "serial": f"RS{i:04d}",
            "accuracy_class_generic": "0.05%",
            "location": "Meter Shop & Standards Laboratory, Lafayette HQ",
            "last_certified_date": str(ref_date - timedelta(days=int(rng.integers(0,60)))),
            "certified_by": "Accredited External Calibration Laboratory",
            "traceable_to": "NIST",
            "certificate_no": f"CERT-RS-2024-{i:04d}",
            "as_found_deviation_pct": round(float(rng.normal(0, 0.01)), 4),
            "next_due": str(ref_date + timedelta(days=730) - timedelta(days=int(rng.integers(0,30)))),
            "certificate_on_file": "Y",
        })
    # 8 working test boards
    for i in range(1, 9):
        last_cert = date(2024, 1, 1) + timedelta(days=int(rng.integers(0, 180)))
        rows.append({
            "standard_id": f"TB-{i:03d}",
            "standard_level": "working_test_board",
            "make_model_generic": f"Shop-Test-Board-{i}",
            "serial": f"TB{i:04d}",
            "accuracy_class_generic": "0.1%",
            "location": "Meter Shop & Standards Laboratory, Lafayette HQ",
            "last_certified_date": str(last_cert),
            "certified_by": f"RPL reference standard RS-{((i-1)%3)+1:03d}",
            "traceable_to": f"RS-{((i-1)%3)+1:03d}",
            "certificate_no": f"CERT-TB-2024-{i:04d}",
            "as_found_deviation_pct": round(float(rng.normal(0, 0.03)), 4),
            "next_due": str(last_cert + timedelta(days=365)),
            "certificate_on_file": "Y",
        })
    # 30 portable standards
    for i in range(1, 31):
        last_cert = date(2023, 6, 1) + timedelta(days=int(rng.integers(0, 365)))
        rows.append({
            "standard_id": f"PS-{i:03d}",
            "standard_level": "portable",
            "make_model_generic": f"Field-Portable-Std-{i}",
            "serial": f"PS{i:04d}",
            "accuracy_class_generic": "0.5%",
            "location": f"Service center — assigned",
            "last_certified_date": str(last_cert),
            "certified_by": f"RPL reference standard RS-{((i-1)%3)+1:03d}",
            "traceable_to": f"RS-{((i-1)%3)+1:03d}",
            "certificate_no": f"CERT-PS-2024-{i:04d}",
            "as_found_deviation_pct": round(float(rng.normal(0, 0.08)), 4),
            "next_due": str(last_cert + timedelta(days=365)),
            "certificate_on_file": "Y",
        })
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# GENERATE METER TEST RESULTS
# ---------------------------------------------------------------------------
def generate_test_results(registry_df, standards_df):
    print("Generating meter test results...")
    std_ids = standards_df[standards_df["standard_level"].isin(["working_test_board","portable"])]["standard_id"].values
    tech_ids = [f"MT-{i:03d}" for i in range(1, 21)]

    test_rows = []
    test_id_counter = 1
    bill_ref_counter = 1
    lot_counter = 1

    def make_test(serial, group_id, tech, reason, tdate, lot_id=None, cust_req_id=None, is_em=False, install_yr=None):
        nonlocal test_id_counter, bill_ref_counter
        tid = f"TST-2024-{test_id_counter:05d}"
        test_id_counter += 1
        std_id = rng.choice(std_ids)
        tech_id = rng.choice(tech_ids)

        if is_em:
            # EM: drift bias, higher σ
            age = 2024 - (install_yr or 1990)
            bias = 100.0 - 0.02 * age
            fl = float(rng.normal(bias, 0.35))
            ll = float(rng.normal(bias - 0.15, 0.50))
        else:
            # Solid-state: tight accuracy
            bias = float(rng.normal(100.0, 0.03))
            if rng.random() < 0.002:  # 0.2% wide tail
                fl = float(rng.standard_t(df=3) * 0.6 + bias)
                ll = float(rng.standard_t(df=3) * 0.6 + bias)
            else:
                fl = float(rng.normal(bias, 0.08))
                ll = float(rng.normal(bias, 0.10))

        fl = round(fl, 4)
        ll = round(ll, 4)
        avg = round((fl + ll) / 2.0, 4)
        fl_ok = abs(fl  - 100.0) <= params["fl_error_limit_pct"]
        ll_ok = abs(ll  - 100.0) <= params["ll_error_limit_pct"]
        avg_ok = abs(avg - 100.0) <= params["avg_error_limit_pct"]
        within = "Y" if (fl_ok and ll_ok and avg_ok) else "N"

        func_result = "pass"
        if not is_em and rng.random() < 0.008:
            func_result = rng.choice(["display_fail","comm_fail","disconnect_switch_fail","register_fail"])

        adjusted = "N"
        as_left_fl = ""
        as_left_ll = ""
        if within == "N" and is_em:
            adjusted = "Y"
            as_left_fl = round(float(rng.normal(100.0, 0.20)), 4)
            as_left_ll = round(float(rng.normal(100.0, 0.25)), 4)

        action = "returned_to_service"
        bill_ref = ""
        if within == "N" or func_result != "pass":
            if within == "N":
                action = rng.choice(["retired","replaced_billing_review"])
                if action == "replaced_billing_review":
                    bill_ref = f"BRA-2024-{bill_ref_counter:04d}"
                    bill_ref_counter += 1
                else:
                    bill_ref = f"BRA-2024-{bill_ref_counter:04d}"
                    bill_ref_counter += 1
            else:
                action = "retired"

        loc = "shop" if reason in ["new_acceptance","repaired","in_service_periodic"] else "field"
        if reason == "in_service_periodic":
            loc = rng.choice(["shop","field"])

        return {
            "test_id": tid,
            "meter_serial": serial,
            "meter_group_id": group_id,
            "sample_lot_id": lot_id or "",
            "customer_request_id": cust_req_id or "",
            "test_date": str(tdate),
            "test_reason": reason,
            "test_location": loc,
            "test_board_or_standard_id": std_id,
            "technician_id": tech_id,
            "as_found_fl_pct": fl,
            "as_found_ll_pct": ll,
            "as_found_pf_pct": "",
            "average_accuracy_pct": avg,
            "within_limits": within,
            "functional_result": func_result,
            "adjusted": adjusted,
            "as_left_fl_pct": as_left_fl,
            "as_left_ll_pct": as_left_ll,
            "as_left_pf_pct": "",
            "action_taken": action,
            "billing_review_ref": bill_ref,
        }

    # --- In-service SAMPLING tests (2500-4000 rows from sampled groups)
    sample_groups = [g for g in GROUPS if g["test_method"]=="sample"]
    for grp in sample_groups:
        n_grp = grp["meter_count"]
        ssize = get_sample_size(n_grp)
        lot_id = f"LOT-IS-2024-{lot_counter:03d}"
        lot_counter += 1
        # Get meters in this group
        gdf = registry_df[registry_df["meter_group_id"]==grp["id"]].sample(
            n=min(ssize, n_grp), replace=False,
            random_state=SEED + hash(grp["id"]) % 10000
        )
        is_em = grp["meter_technology"]=="electromechanical"
        for _, row in gdf.iterrows():
            yr = int(str(row["install_date"])[:4])
            tdate = date(2024, rng.integers(1,13), rng.integers(1,28))
            t = make_test(row["meter_serial"], grp["id"], None,
                         "in_service_sample", tdate, lot_id=lot_id, is_em=is_em, install_yr=yr)
            test_rows.append(t)

    # --- In-service PERIODIC tests (EM and transformer-rated, ~800 rows)
    periodic_groups = [g for g in GROUPS if g["test_method"]=="periodic"]
    for grp in periodic_groups:
        n_tests = max(10, int(grp["meter_count"] * 0.08))
        gdf = registry_df[registry_df["meter_group_id"]==grp["id"]].sample(
            n=min(n_tests, grp["meter_count"]), replace=False,
            random_state=SEED + hash(grp["id"]) % 10000
        )
        is_em = grp["meter_technology"]=="electromechanical"
        lot_id = f"LOT-PD-2024-{lot_counter:03d}"
        lot_counter += 1
        for _, row in gdf.iterrows():
            yr = int(str(row["install_date"])[:4])
            tdate = date(2024, rng.integers(1,13), rng.integers(1,28))
            t = make_test(row["meter_serial"], grp["id"], None,
                         "in_service_periodic", tdate, lot_id=lot_id, is_em=is_em, install_yr=yr)
            test_rows.append(t)
            # Update last_test_date in registry
            registry_df.loc[registry_df["meter_serial"]==row["meter_serial"], "last_test_date"] = str(tdate)
            registry_df.loc[registry_df["meter_serial"]==row["meter_serial"], "last_test_reason"] = "in_service_periodic"

    total_inservice = len(test_rows)
    print(f"  In-service tests: {total_inservice}")

    # --- New acceptance tests (900-1600 rows) — handled in new_lots generation
    # (test_results for new_acceptance added after lot generation)

    return test_rows, lot_counter

# ---------------------------------------------------------------------------
# GENERATE NEW METER LOTS
# ---------------------------------------------------------------------------
def generate_new_lots(test_rows_list, lot_counter_start):
    print("Generating new meter lot acceptance data...")
    lot_rows = []
    test_rows = test_rows_list
    test_id_counter = max(int(t["test_id"].split("-")[2]) for t in test_rows) + 1 if test_rows else 1
    bill_ref_counter = max(
        int(t["billing_review_ref"].split("-")[2]) for t in test_rows if t["billing_review_ref"]
    ) + 1 if any(t["billing_review_ref"] for t in test_rows) else 1

    std_ids = [f"TB-{i:03d}" for i in range(1, 9)]
    vendors = ["Vendor_A","Vendor_B","Vendor_C"]
    forms   = ["2S","2S","2S","2S","12S","16S","9S"]
    classes = ["CL200","CL200","CL200","CL320","CL200","CL200","CL20"]
    techs   = ["solid_state_AMI","solid_state_AMI","solid_state_AMI","solid_state_AMI",
               "solid_state_AMI","solid_state_AMI","solid_state_AMI"]

    n_lots = int(rng.integers(10, 14))
    rejected_placed = False
    total_accept_tests = 0

    for i in range(n_lots):
        lot_id = f"LOT-NA-2024-{lot_counter_start + i:03d}"
        v_idx  = int(rng.integers(0, 3))
        f_idx  = int(rng.integers(0, len(forms)))
        lot_size = int(rng.integers(500, 4001))
        ssize = get_sample_size(lot_size)
        recv_date = date(2024, int(rng.integers(1,13)), int(rng.integers(1,25)))

        is_rejected = (not rejected_placed) and (i == n_lots - 4) and (rng.random() < 0.5)
        sample_fails = 0
        lot_results = []

        for j in range(ssize):
            serial = f"RPL-NA-LOT{i+1:03d}-{j+1:05d}"
            tdate = recv_date + timedelta(days=int(rng.integers(1, 20)))
            tid = f"TST-2024-{test_id_counter:05d}"
            test_id_counter += 1
            bias = float(rng.normal(100.0, 0.03))
            fl = round(float(rng.normal(bias, 0.08)), 4)
            ll = round(float(rng.normal(bias, 0.10)), 4)
            avg = round((fl + ll) / 2.0, 4)
            fl_ok  = abs(fl  - 100.0) <= params["fl_error_limit_pct"]
            ll_ok  = abs(ll  - 100.0) <= params["ll_error_limit_pct"]
            avg_ok = abs(avg - 100.0) <= params["avg_error_limit_pct"]
            within = "Y" if (fl_ok and ll_ok and avg_ok) else "N"
            if within == "N":
                sample_fails += 1
            action = "returned_to_service" if within == "Y" else "retired"
            bill_ref = ""
            if within == "N":
                bill_ref = f"BRA-2024-{bill_ref_counter:04d}"
                bill_ref_counter += 1

            lot_results.append({
                "test_id": tid,
                "meter_serial": serial,
                "meter_group_id": f"GRP-{(i%27)+1:03d}",
                "sample_lot_id": lot_id,
                "customer_request_id": "",
                "test_date": str(tdate),
                "test_reason": "new_acceptance",
                "test_location": "shop",
                "test_board_or_standard_id": rng.choice(std_ids),
                "technician_id": f"MT-{rng.integers(1,21):03d}",
                "as_found_fl_pct": fl,
                "as_found_ll_pct": ll,
                "as_found_pf_pct": "",
                "average_accuracy_pct": avg,
                "within_limits": within,
                "functional_result": "pass",
                "adjusted": "N",
                "as_left_fl_pct": "",
                "as_left_ll_pct": "",
                "as_left_pf_pct": "",
                "action_taken": action,
                "billing_review_ref": bill_ref,
            })
        total_accept_tests += ssize

        if is_rejected:
            lot_result = "rejected"
            rejected_placed = True
            disposition = "returned_to_vendor"
        else:
            lot_result = "accepted"
            disposition = "placed_in_inventory"

        lot_rows.append({
            "lot_id": lot_id,
            "vendor_family": vendors[v_idx],
            "technology": techs[f_idx],
            "form": forms[f_idx],
            "meter_class": classes[f_idx],
            "received_date": str(recv_date),
            "lot_size": lot_size,
            "sample_size": ssize,
            "sample_failures": sample_fails if lot_result=="rejected" else min(sample_fails, 1),
            "lot_result": lot_result,
            "disposition": disposition,
        })
        test_rows.extend(lot_results)

    print(f"  New acceptance tests: {total_accept_tests}")
    return pd.DataFrame(lot_rows), test_rows

# ---------------------------------------------------------------------------
# GENERATE CUSTOMER TEST REQUESTS
# ---------------------------------------------------------------------------
def generate_customer_requests(registry_df, test_rows_list):
    print("Generating customer test requests...")
    cust_rows = []
    test_id_counter = max(int(t["test_id"].split("-")[2]) for t in test_rows_list) + 1
    bill_ref_counter = max(
        int(t["billing_review_ref"].split("-")[2]) for t in test_rows_list if t["billing_review_ref"]
    ) + 1 if any(t["billing_review_ref"] for t in test_rows_list) else 1

    std_ids = [f"TB-{i:03d}" for i in range(1, 9)] + [f"PS-{i:03d}" for i in range(1, 11)]
    n_requests = 620
    active_meters = registry_df[registry_df["account_id"] != ""].sample(
        n=n_requests, replace=False, random_state=SEED + 9999
    )

    channels = ["phone","phone","phone","web","written","written"]
    result_choices = ["within","within","within","within","within","within","within","fast","slow","functional_fail"]
    # Ensure fee/timing compliance
    results_dist = rng.choice(result_choices, n_requests)

    for i, (_, mrow) in enumerate(active_meters.iterrows()):
        crid = f"CRQ-2024-{i+1:04d}"
        req_date = date(2024, int(rng.integers(1,13)), int(rng.integers(1,25)))
        channel  = rng.choice(channels)
        written  = "Y" if channel == "written" else "N"
        prior_within_window = "N"  # default: no prior test in 36 months → free
        fee = 0.00
        fee_refunded = "N"
        stype = mrow["service_type"]
        # Customer test fee per §1.6: $40 residential/single-phase; $95 polyphase/demand
        is_polyphase = mrow["form"] not in ["2S","1S","3S","4S"]
        fee_amount = 95.00 if is_polyphase else 40.00
        if prior_within_window == "Y":
            fee = fee_amount
        # Schedule test within reasonable window
        test_date = req_date + timedelta(days=int(rng.integers(3,25)))
        witness = "Y" if rng.random() < 0.12 else "N"
        result = results_dist[i]
        report_date = test_date + timedelta(days=int(rng.integers(2, 10)))  # within 10 days
        adj_ref = ""
        if result in ["fast","slow","non_registering"]:
            adj_ref = f"ADJ-2024-{i+1:04d}"
        # Create test result row
        tid = f"TST-2024-{test_id_counter:05d}"
        test_id_counter += 1
        is_em = mrow["meter_technology"] == "electromechanical"
        yr = int(str(mrow["install_date"])[:4])
        if is_em:
            age = 2024 - yr
            bias = 100.0 - 0.02 * age
            fl = float(rng.normal(bias, 0.35))
            ll = float(rng.normal(bias - 0.15, 0.50))
        else:
            fl = float(rng.normal(100.0, 0.10))
            ll = float(rng.normal(100.0, 0.12))
        fl = round(fl, 4)
        ll = round(ll, 4)
        avg = round((fl + ll) / 2.0, 4)
        fl_ok  = abs(fl  - 100.0) <= params["fl_error_limit_pct"]
        ll_ok  = abs(ll  - 100.0) <= params["ll_error_limit_pct"]
        avg_ok = abs(avg - 100.0) <= params["avg_error_limit_pct"]
        within = "Y" if (fl_ok and ll_ok and avg_ok) else "N"
        # Force result to match 'result' field for within
        if result == "within" and within == "N":
            fl = round(float(rng.normal(100.0, 0.05)), 4)
            ll = round(float(rng.normal(100.0, 0.06)), 4)
            avg = round((fl + ll) / 2.0, 4)
            within = "Y"
        action = "returned_to_service"
        bill_ref = ""
        if within == "N":
            action = "replaced_billing_review"
            bill_ref = f"BRA-2024-{bill_ref_counter:04d}"
            bill_ref_counter += 1
        std_id = rng.choice(std_ids)
        tech_id = f"MT-{rng.integers(1,21):03d}"
        test_rows_list.append({
            "test_id": tid,
            "meter_serial": mrow["meter_serial"],
            "meter_group_id": mrow["meter_group_id"],
            "sample_lot_id": "",
            "customer_request_id": crid,
            "test_date": str(test_date),
            "test_reason": "customer_request",
            "test_location": "shop",
            "test_board_or_standard_id": std_id,
            "technician_id": tech_id,
            "as_found_fl_pct": fl,
            "as_found_ll_pct": ll,
            "as_found_pf_pct": "",
            "average_accuracy_pct": avg,
            "within_limits": within,
            "functional_result": "pass" if result != "functional_fail" else "display_fail",
            "adjusted": "N",
            "as_left_fl_pct": "",
            "as_left_ll_pct": "",
            "as_left_pf_pct": "",
            "action_taken": action,
            "billing_review_ref": bill_ref,
        })
        cust_rows.append({
            "customer_request_id": crid,
            "account_id": mrow["account_id"],
            "premise_id": mrow["premise_id"],
            "meter_serial": mrow["meter_serial"],
            "meter_technology": mrow["meter_technology"],
            "service_type": mrow["service_type"],
            "request_date": str(req_date),
            "request_channel": channel,
            "written_request": written,
            "prior_request_in_pack_window": prior_within_window,
            "fee_charged_usd": fee,
            "fee_refunded": fee_refunded,
            "test_date": str(test_date),
            "witness_requested": witness,
            "result": result,
            "report_sent_date": str(report_date),
            "adjustment_ref": adj_ref,
        })
    return pd.DataFrame(cust_rows), test_rows_list

# ---------------------------------------------------------------------------
# GENERATE IN-SERVICE SAMPLE SELECTION 2025
# ---------------------------------------------------------------------------
def generate_sample_selection_2025(registry_df):
    print("Generating 2025 sample selection...")
    rng2025 = np.random.default_rng(2025)
    rows = []
    sample_groups = [g for g in GROUPS if g["test_method"]=="sample"]
    for grp in sample_groups:
        n_grp = grp["meter_count"]
        ssize = get_sample_size(n_grp)
        gdf = registry_df[registry_df["meter_group_id"]==grp["id"]]
        selected = gdf.sample(n=min(ssize, len(gdf)), replace=False,
                              random_state=2025 + hash(grp["id"]) % 10000)
        for rank, (_, row) in enumerate(selected.iterrows(), 1):
            q = rng2025.integers(1, 5)
            loc = "shop" if row["meter_technology"] != "electromechanical" else rng2025.choice(["shop","field"])
            rows.append({
                "meter_group_id": grp["id"],
                "meter_serial": row["meter_serial"],
                "draw_rank": rank,
                "scheduled_quarter": f"Q{q}",
                "location": loc,
            })
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    registry_df = generate_registry()

    # Write registry (gzipped)
    reg_path = os.path.join(OUT_DIR, "meter_registry_2024-12-31.csv.gz")
    registry_df.to_csv(reg_path, index=False, compression="gzip")
    print(f"  Wrote {reg_path} ({len(registry_df)} rows)")

    # Population
    pop_df = generate_population(registry_df)
    pop_path = os.path.join(OUT_DIR, "meter_population_2024-12-31.csv")
    pop_df.to_csv(pop_path, index=False)
    print(f"  Wrote {pop_path} ({len(pop_df)} groups)")

    # Standards
    std_df = generate_standards()
    std_path = os.path.join(OUT_DIR, "standards_calibration_2024.csv")
    std_df.to_csv(std_path, index=False)
    print(f"  Wrote {std_path}")

    # Test results (initial pass — in-service)
    test_rows, lot_ctr = generate_test_results(registry_df, std_df)

    # New lots (adds acceptance tests to test_rows)
    lots_df, test_rows = generate_new_lots(test_rows, lot_ctr)
    lots_path = os.path.join(OUT_DIR, "new_meter_lots_2024.csv")
    lots_df.to_csv(lots_path, index=False)
    print(f"  Wrote {lots_path} ({len(lots_df)} lots)")

    # Customer requests (adds customer tests to test_rows)
    cust_df, test_rows = generate_customer_requests(registry_df, test_rows)
    cust_path = os.path.join(OUT_DIR, "customer_test_requests_2024.csv")
    cust_df.to_csv(cust_path, index=False)
    print(f"  Wrote {cust_path} ({len(cust_df)} rows)")

    # Write test results
    test_df = pd.DataFrame(test_rows)
    test_path = os.path.join(OUT_DIR, "meter_test_results_2024.csv")
    test_df.to_csv(test_path, index=False)
    print(f"  Wrote {test_path} ({len(test_df)} rows)")

    # 2025 sample selection
    sel_df = generate_sample_selection_2025(registry_df)
    sel_path = os.path.join(OUT_DIR, "inservice_sample_selection_2025.csv")
    sel_df.to_csv(sel_path, index=False)
    print(f"  Wrote {sel_path} ({len(sel_df)} rows)")

    # Manifest
    manifest = {"generator": "generate_meter_data.py", "seed": SEED, "files": []}
    for fname in [
        "meter_registry_2024-12-31.csv.gz",
        "meter_population_2024-12-31.csv",
        "meter_test_results_2024.csv",
        "new_meter_lots_2024.csv",
        "inservice_sample_selection_2025.csv",
        "customer_test_requests_2024.csv",
        "standards_calibration_2024.csv",
    ]:
        fpath = os.path.join(OUT_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath,"rb") as f:
                sha = hashlib.sha256(f.read()).hexdigest()
            sz = os.path.getsize(fpath)
            manifest["files"].append({"file": fname, "sha256": sha, "size_bytes": sz})
    with open(os.path.join(OUT_DIR, "_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("  Wrote _manifest.json")
    print(f"\nDone. Total test results: {len(test_df)}")

if __name__ == "__main__":
    main()
