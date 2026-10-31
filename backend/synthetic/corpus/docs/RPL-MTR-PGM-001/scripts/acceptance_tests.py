#!/usr/bin/env python3
"""
RPL-MTR-PGM-001 Acceptance Tests
Validates the generated datasets for the Meter Testing Program Plan.
Run: python3 acceptance_tests.py
"""
import os
import sys
import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CIRCUITS_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../../_global/ops/circuits_master.csv"
)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    mark = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    results.append((mark, name, detail))
    return condition


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print("Loading data files...")
reg = pd.read_csv(
    os.path.join(DATA_DIR, "meter_registry_2024-12-31.csv.gz"),
    low_memory=False
)
pop = pd.read_csv(os.path.join(DATA_DIR, "meter_population_2024-12-31.csv"))
tests = pd.read_csv(os.path.join(DATA_DIR, "meter_test_results_2024.csv"), low_memory=False)
lots = pd.read_csv(os.path.join(DATA_DIR, "new_meter_lots_2024.csv"))
sel = pd.read_csv(os.path.join(DATA_DIR, "inservice_sample_selection_2025.csv"))
cust = pd.read_csv(os.path.join(DATA_DIR, "customer_test_requests_2024.csv"))
stds = pd.read_csv(os.path.join(DATA_DIR, "standards_calibration_2024.csv"))
circuits_df = pd.read_csv(CIRCUITS_PATH)
print("Data loaded.\n")

# ---------------------------------------------------------------------------
# Test 1: Registry row count == 409,950
# ---------------------------------------------------------------------------
n_reg = len(reg)
check(
    "Test 1: Registry row count == 409,950",
    n_reg == 409_950,
    f"actual = {n_reg:,}"
)

# ---------------------------------------------------------------------------
# Test 2: Tech-type distribution exact
# ---------------------------------------------------------------------------
counts = reg["meter_technology"].value_counts()
ami  = counts.get("solid_state_AMI", 0)
amr  = counts.get("solid_state_AMR", 0)
em   = counts.get("electromechanical", 0)
ok = (ami == 371_200) and (amr == 31_400) and (em == 7_350)
check(
    "Test 2: Tech distribution AMI=371200, AMR=31400, EM=7350",
    ok,
    f"AMI={ami}, AMR={amr}, EM={em}"
)

# ---------------------------------------------------------------------------
# Test 3: All circuit_id values in registry exist in circuits_master.csv
# ---------------------------------------------------------------------------
known_circuits = set(circuits_df["circuit_id"].astype(str))
reg_circuits   = set(reg["circuit_id"].astype(str))
unknown = reg_circuits - known_circuits
check(
    "Test 3: All circuit_id values in registry exist in circuits_master",
    len(unknown) == 0,
    f"unknown circuit_ids: {len(unknown)}" + (f" e.g. {list(unknown)[:3]}" if unknown else "")
)

# ---------------------------------------------------------------------------
# Test 4: All group_ids in registry exist in population; Σmeter_count = 409,950
# ---------------------------------------------------------------------------
known_groups  = set(pop["meter_group_id"].astype(str))
reg_groups    = set(reg["meter_group_id"].astype(str))
missing_groups = reg_groups - known_groups
sum_pop = pop["meter_count"].sum()
ok4 = (len(missing_groups) == 0) and (sum_pop == 409_950)
check(
    "Test 4: All group_ids in registry exist in population; Σmeter_count = 409,950",
    ok4,
    f"missing groups: {len(missing_groups)}, Σmeter_count = {sum_pop:,}"
)

# ---------------------------------------------------------------------------
# Test 5: test_results — all in-service/customer/periodic meter_ids in registry; accuracy numeric
# ---------------------------------------------------------------------------
registry_serials = set(reg["meter_serial"].astype(str))
# new_acceptance rows use synthetic lot serials (not in registry by design); exclude them
non_accept_tests = tests[tests["test_reason"] != "new_acceptance"]
missing_serials = set(non_accept_tests["meter_serial"].astype(str)) - registry_serials
accuracy_numeric = pd.to_numeric(tests["average_accuracy_pct"], errors="coerce").notna().all()
ok5 = (len(missing_serials) == 0) and accuracy_numeric
check(
    "Test 5: test_results (non-acceptance) serials all in registry; accuracy column numeric",
    ok5,
    f"missing serials: {len(missing_serials)}, accuracy_numeric: {accuracy_numeric}"
)

# ---------------------------------------------------------------------------
# Test 6: within_limits is boolean-recomputable from accuracy vs. limits
# ---------------------------------------------------------------------------
fl   = pd.to_numeric(tests["as_found_fl_pct"],       errors="coerce")
ll   = pd.to_numeric(tests["as_found_ll_pct"],       errors="coerce")
avg  = pd.to_numeric(tests["average_accuracy_pct"],  errors="coerce")
recomputed = (
    (np.abs(avg - 100.0) <= 2.0) &
    (np.abs(fl  - 100.0) <= 1.0) &
    (np.abs(ll  - 100.0) <= 3.0)
)
expected_within = recomputed.map({True: "Y", False: "N"})
actual_within   = tests["within_limits"].astype(str)
matches = (expected_within == actual_within).all()
check(
    "Test 6: within_limits is boolean-recomputable from fl/ll/avg vs. accuracy limits",
    matches,
    f"mismatches: {(expected_within != actual_within).sum()}"
)

# ---------------------------------------------------------------------------
# Test 7: customer_test_requests — ~620 rows (within ±50); all meter_ids valid
# ---------------------------------------------------------------------------
n_cust = len(cust)
cust_in_range = abs(n_cust - 620) <= 50
cust_serials_valid = set(cust["meter_serial"].astype(str)).issubset(registry_serials)
ok7 = cust_in_range and cust_serials_valid
check(
    "Test 7: customer_test_requests ~620 rows (±50); all meter_ids valid",
    ok7,
    f"rows: {n_cust}, meter_ids valid: {cust_serials_valid}"
)

# ---------------------------------------------------------------------------
# Test 8: standards_calibration — ≥4 rows; date column present; lab name present
# ---------------------------------------------------------------------------
n_stds = len(stds)
has_date = "last_certified_date" in stds.columns and stds["last_certified_date"].notna().any()
has_lab  = "certified_by" in stds.columns and stds["certified_by"].notna().any()
ok8 = (n_stds >= 4) and has_date and has_lab
check(
    "Test 8: standards_calibration ≥4 rows; date and lab name present",
    ok8,
    f"rows: {n_stds}, has_date: {has_date}, has_lab: {has_lab}"
)

# ---------------------------------------------------------------------------
# Test 9: new_meter_lots — lot_id unique; sample_size is integer; acceptance_result is pass/fail
# ---------------------------------------------------------------------------
lot_ids_unique = lots["lot_id"].nunique() == len(lots)
sample_size_int = pd.to_numeric(lots["sample_size"], errors="coerce").apply(
    lambda x: x == int(x) if pd.notna(x) else False
).all()
valid_results = lots["lot_result"].isin(["accepted", "rejected"]).all()
ok9 = lot_ids_unique and sample_size_int and valid_results
check(
    "Test 9: new_meter_lots lot_id unique; sample_size integer; lot_result is accepted/rejected",
    ok9,
    f"lot_id_unique: {lot_ids_unique}, sample_size_int: {sample_size_int}, valid_results: {valid_results}"
)

# ---------------------------------------------------------------------------
# Test 10: inservice_sample_selection_2025 — group_id FK valid; sample_size ≤ group size
# ---------------------------------------------------------------------------
sel_groups = set(sel["meter_group_id"].astype(str))
unknown_sel_groups = sel_groups - known_groups
# Check that selection count per group ≤ group meter_count
group_counts = pop.set_index("meter_group_id")["meter_count"].to_dict()
sel_counts = sel.groupby("meter_group_id").size()
exceeded = []
for gid, cnt in sel_counts.items():
    max_cnt = group_counts.get(str(gid), 0)
    if cnt > max_cnt:
        exceeded.append((gid, cnt, max_cnt))
ok10 = (len(unknown_sel_groups) == 0) and (len(exceeded) == 0)
check(
    "Test 10: inservice_sample_selection_2025 group_id FK valid; sample_size ≤ group size",
    ok10,
    f"unknown groups: {len(unknown_sel_groups)}, groups exceeded: {len(exceeded)}"
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print("=" * 60)
n_pass = sum(1 for r in results if r[0] == "PASS")
n_fail = sum(1 for r in results if r[0] == "FAIL")
print(f"Results: {n_pass}/{len(results)} PASS  |  {n_fail} FAIL")
print("=" * 60)

if n_fail > 0:
    sys.exit(1)
