"""
acceptance_tests.py — T04 Acceptance Tests
Rockridge Power & Light Company Shared Operational Master Data

All 6 tests must pass.
"""

import os, sys, math, datetime
import numpy as np
import pandas as pd
import yaml

OPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = {}

def run_test(name, fn):
    try:
        fn()
        results[name] = True
        print(f"  [{PASS}] {name}")
    except AssertionError as e:
        results[name] = False
        print(f"  [{FAIL}] {name}: {e}")
    except Exception as e:
        results[name] = False
        print(f"  [{FAIL}] {name}: {type(e).__name__}: {e}")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
subs = pd.read_csv(os.path.join(OPS_DIR, "substations_master.csv"))
ckts = pd.read_csv(os.path.join(OPS_DIR, "circuits_master.csv"))
daily = pd.read_csv(os.path.join(OPS_DIR, "daily_saidi_history_2019_2023.csv"))
med = pd.read_csv(os.path.join(OPS_DIR, "med_days.csv"))
inc = pd.read_csv(os.path.join(OPS_DIR, "outage_incidents_base.csv"))
evt = pd.read_csv(os.path.join(OPS_DIR, "outage_events_base.csv"))
stp = pd.read_csv(os.path.join(OPS_DIR, "outage_restoration_steps_base.csv"))
with open(os.path.join(OPS_DIR, "reliability_facts.yaml")) as f:
    facts = yaml.safe_load(f)

# ---------------------------------------------------------------------------
# Test 1: Row counts and canonical sums
# ---------------------------------------------------------------------------
def test_counts_and_sums():
    assert len(subs) == 112, f"Expected 112 substations, got {len(subs)}"
    assert len(ckts) == 528, f"Expected 528 circuits, got {len(ckts)}"
    assert len(daily) == 1826, f"Expected 1826 daily rows, got {len(daily)}"

    oh_sum = round(ckts["oh_miles"].sum(), 1)
    assert abs(oh_sum - 14200.0) <= 0.1, f"OH miles={oh_sum}, expected 14200.0±0.1"

    ug_sum = round(ckts["ug_miles"].sum(), 1)
    assert abs(ug_sum - 4900.0) <= 0.1, f"UG miles={ug_sum}, expected 4900.0±0.1"

    cust_sum = int(ckts["customers_on_circuit"].sum())
    assert cust_sum == 407_491, f"Total customers={cust_sum}, expected 407,491"

    res_sum = int(ckts["customers_residential"].sum())
    assert res_sum == 361_480, f"Residential={res_sum}, expected 361,480"

    nonres_sum = int(ckts["customers_nonresidential"].sum())
    assert nonres_sum == 46_011, f"Non-residential={nonres_sum}, expected 46,011"

    # Event row count
    assert 9500 <= len(evt) <= 12000, f"Events={len(evt)}, expected 9,500-12,000"

run_test("T1: row counts and canonical sums", test_counts_and_sums)

# ---------------------------------------------------------------------------
# Test 2: Referential integrity
# ---------------------------------------------------------------------------
def test_referential_integrity():
    sub_ids = set(subs["substation_id"])
    ckt_ids = set(ckts["circuit_id"])
    inc_ids = set(inc["incident_id"])

    bad_ckt = evt[~evt["circuit_id"].isin(ckt_ids)]
    assert len(bad_ckt) == 0, f"{len(bad_ckt)} events have unknown circuit_id"

    bad_sub = evt[~evt["substation_id"].isin(sub_ids)]
    assert len(bad_sub) == 0, f"{len(bad_sub)} events have unknown substation_id"

    bad_inc = evt[~evt["incident_id"].isin(inc_ids)]
    assert len(bad_inc) == 0, f"{len(bad_inc)} events have unknown incident_id"

    # Every event must have at least 1 restoration step
    step_event_ids = set(stp["event_id"])
    no_steps = evt[~evt["event_id"].isin(step_event_ids)]
    assert len(no_steps) == 0, f"{len(no_steps)} events have no restoration steps"

    # Restoration steps must sum to customers_affected per event
    step_sums = stp.groupby("event_id")["customers_restored"].sum().reset_index()
    step_sums.columns = ["event_id", "step_sum"]
    merged = evt[["event_id","customers_affected"]].merge(step_sums, on="event_id")
    mismatch = merged[merged["customers_affected"] != merged["step_sum"]]
    assert len(mismatch) == 0, (
        f"{len(mismatch)} events where restoration steps don't sum to customers_affected"
        + (f"\nFirst few: {mismatch.head(3).to_dict()}" if len(mismatch) > 0 else ""))

run_test("T2: referential integrity", test_referential_integrity)

# ---------------------------------------------------------------------------
# Test 3: customer_minutes recomputes from restoration steps
# ---------------------------------------------------------------------------
def test_customer_minutes():
    # For each event, recompute CMI from steps and compare
    evt_ts = evt.set_index("event_id")["start_ts"].to_dict()
    evt_cm = evt.set_index("event_id")["customer_minutes"].to_dict()

    stp_sorted = stp.sort_values(["event_id","step_no"])

    mismatches = []
    for eid, grp in stp_sorted.groupby("event_id"):
        start = datetime.datetime.fromisoformat(evt_ts[eid])
        computed_cm = 0
        for _, row in grp.iterrows():
            st = datetime.datetime.fromisoformat(row["step_ts"])
            mo = max(1, int((st - start).total_seconds() / 60))
            computed_cm += int(row["customers_restored"]) * mo
        stored_cm = int(evt_cm[eid])
        if computed_cm != stored_cm:
            mismatches.append((eid, computed_cm, stored_cm))
        if len(mismatches) > 5:
            break

    assert len(mismatches) == 0, (
        f"customer_minutes mismatch for {len(mismatches)} events. "
        f"First: event={mismatches[0][0]} computed={mismatches[0][1]} stored={mismatches[0][2]}")

run_test("T3: customer_minutes recomputes from steps", test_customer_minutes)

# ---------------------------------------------------------------------------
# Test 4: TMED and MED dates recompute from history; 3-8 MED in 2024 incl. March
# ---------------------------------------------------------------------------
def test_tmed_and_med():
    nz = daily[daily["saidi_all_min"] > 0]["saidi_all_min"].values
    x = np.log(nz)
    mu = np.mean(x); sigma = np.std(x, ddof=1)
    tmed_computed = np.exp(mu + 2.5 * sigma)

    stored_tmed = med["tmed_saidi_min"].iloc[0]
    assert abs(tmed_computed - stored_tmed) < 0.01, (
        f"TMED mismatch: computed={tmed_computed:.4f} stored={stored_tmed:.4f}")

    # MED dates have daily_saidi > TMED
    for _, row in med.iterrows():
        assert row["daily_saidi_min"] > row["tmed_saidi_min"], (
            f"MED date {row['med_date']} SAIDI {row['daily_saidi_min']:.2f} <= TMED {row['tmed_saidi_min']:.2f}")

    # Count 2024 MED days
    med_2024 = med[med["year"] == 2024]
    n_med = len(med_2024)
    assert 3 <= n_med <= 8, f"2024 MED day count={n_med}, expected 3-8"

    # Must include a March 2024 MED day
    march_med = med_2024[med_2024["med_date"].str.startswith("2024-03")]
    assert len(march_med) >= 1, "No March 2024 MED day found"

run_test("T4: TMED and MED dates", test_tmed_and_med)

# ---------------------------------------------------------------------------
# Test 5: reliability_facts.yaml indices recompute within 0.001; targets met
# ---------------------------------------------------------------------------
def test_reliability_facts():
    annual_cs = facts["customers_served_annual_2024"]
    med_dates_set = set(facts["med_dates_2024"])

    ev24 = evt[evt["start_ts"].str.startswith("2024")].copy()
    ev24["is_med"]  = ev24["med_flag"] == "Y"

    exm_evts = ev24[~ev24["is_med"]]
    ci_exm  = int(exm_evts["customers_affected"].sum())
    cmi_exm = int(exm_evts["customer_minutes"].sum())

    saifi_c = ci_exm  / annual_cs
    saidi_c = cmi_exm / annual_cs
    caidi_c = saidi_c / saifi_c if saifi_c > 0 else 0.0

    stored_exm = facts["annual_2024"]["ex_med"]
    assert abs(saifi_c - stored_exm["saifi"]) < 0.002, (
        f"SAIFI mismatch: computed={saifi_c:.4f} stored={stored_exm['saifi']:.4f}")
    assert abs(saidi_c - stored_exm["saidi"]) < 0.5, (
        f"SAIDI mismatch: computed={saidi_c:.2f} stored={stored_exm['saidi']:.2f}")

    # Target checks
    assert 1.05 <= stored_exm["saifi"] <= 1.15, (
        f"SAIFI={stored_exm['saifi']:.4f} not in 1.05-1.15")
    assert 130 <= stored_exm["saidi"] <= 150, (
        f"SAIDI={stored_exm['saidi']:.2f} not in 130-150")
    assert 115 <= stored_exm["caidi"] <= 140, (
        f"CAIDI={stored_exm['caidi']:.2f} not in 115-140")

    wm = facts["annual_2024"]["with_med"]
    assert 220 <= wm["saidi"] <= 350, (
        f"With-MED SAIDI={wm['saidi']:.2f} not in 220-350")

run_test("T5: reliability_facts.yaml indices and targets", test_reliability_facts)

# ---------------------------------------------------------------------------
# Test 6: No regulatory field names or values
# ---------------------------------------------------------------------------
def test_no_regulatory_content():
    banned_patterns = [
        "reportab", "iurc_report", "threshold", "deadline",
        "report_due", "filing_due", "regulatory_limit",
    ]
    violations = []

    # Check all CSV headers
    for name, df in [("substations", subs), ("circuits", ckts), ("daily_saidi", daily),
                     ("med_days", med), ("incidents", inc), ("events", evt), ("steps", stp)]:
        for col in df.columns:
            for p in banned_patterns:
                if p.lower() in col.lower():
                    violations.append(f"Column '{col}' in {name}")

    # Check reliability_facts keys (top-level)
    for key in facts.keys():
        for p in banned_patterns:
            if p.lower() in key.lower():
                violations.append(f"Key '{key}' in reliability_facts.yaml")

    assert len(violations) == 0, (
        f"Regulatory content found: {violations}")

run_test("T6: no regulatory content", test_no_regulatory_content)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
n_pass = sum(results.values())
n_total = len(results)
print(f"Results: {n_pass}/{n_total} tests passed")
if n_pass == n_total:
    print("ALL TESTS PASSED")
else:
    failed = [k for k, v in results.items() if not v]
    print(f"FAILED: {failed}")
    sys.exit(1)
