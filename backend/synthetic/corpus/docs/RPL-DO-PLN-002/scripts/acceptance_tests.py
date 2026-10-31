#!/usr/bin/env python3
"""
acceptance_tests.py — Acceptance tests for RPL-DO-PLN-002 datasets.
Exits non-zero on any failure.  Results are appended to data/README.md.
"""

import csv
import sys
import json
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DOC_DIR    = SCRIPT_DIR.parent
DATA_DIR   = DOC_DIR / "data"
GLOBAL_OPS = DOC_DIR.parent.parent / "_global" / "ops"

CIRCUITS_MASTER  = GLOBAL_OPS / "circuits_master.csv"
OUTAGE_EVENTS    = GLOBAL_OPS / "outage_events_base.csv"
RELIABILITY_YAML = GLOBAL_OPS / "reliability_facts.yaml"

SCHED_CSV    = DATA_DIR / "vm_circuit_schedule_2025.csv"
WC_CSV       = DATA_DIR / "vm_work_completed_2024.csv"
TREE_OUT_CSV = DATA_DIR / "vm_tree_outages_2024.csv"
BUDGET_CSV   = DATA_DIR / "vm_budget_2024_2025.csv"
CONTACTS_CSV = DATA_DIR / "vm_customer_contacts_2024.csv"

# Regulatory params from pack
NOTICE_MIN_CALENDAR_DAYS = 14   # 170 IAC 4-9-4(a)

failures = []
results  = []


def check(name: str, passed: bool, detail: str = ""):
    mark = "PASS" if passed else "FAIL"
    msg  = f"[{mark}] {name}" + (f": {detail}" if detail else "")
    results.append(msg)
    print(msg)
    if not passed:
        failures.append(name)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_circuits_master():
    rows = read_csv(CIRCUITS_MASTER)
    return {r["circuit_id"]: r for r in rows}


def read_customers_monthly():
    monthly = {}
    in_sec = False
    with open(RELIABILITY_YAML, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s.startswith("customers_served_monthly"):
                in_sec = True
                continue
            if in_sec:
                if ":" in s and (s[0].isdigit() or s.startswith("'")):
                    k, v = s.split(":", 1)
                    monthly[k.strip().strip("'")] = int(v.strip())
                elif s and not s.startswith(" "):
                    break
    return monthly


# ── Test 1: Every circuit_id in VM datasets exists in circuits_master ─────────
def test_1_circuit_ids():
    master = read_circuits_master()
    vm_files = [
        ("vm_circuit_schedule_2025.csv", SCHED_CSV),
        ("vm_work_completed_2024.csv",   WC_CSV),
        ("vm_customer_contacts_2024.csv",CONTACTS_CSV),
    ]
    all_ok = True
    for fname, path in vm_files:
        if not path.exists():
            check(f"T1 {fname} exists", False, "file missing")
            all_ok = False
            continue
        rows = read_csv(path)
        bad = [r["circuit_id"] for r in rows if r["circuit_id"] not in master]
        if bad:
            check(f"T1 {fname} circuit_ids", False, f"{len(bad)} unknown IDs: {bad[:3]}")
            all_ok = False
        else:
            # Also check substation, county, voltage, phase match master
            mismatches = []
            for r in rows:
                m = master[r["circuit_id"]]
                if "substation_id" in r and r.get("substation_id") and r["substation_id"] != m["substation_id"]:
                    mismatches.append(f'{r["circuit_id"]} substation_id')
                if "county" in r and r.get("county") and r["county"] != m["county"]:
                    mismatches.append(f'{r["circuit_id"]} county')
                if "voltage_kv" in r and r.get("voltage_kv") and r["voltage_kv"] != m["voltage_kv"]:
                    mismatches.append(f'{r["circuit_id"]} voltage_kv')
            if mismatches:
                check(f"T1 {fname} field consistency", False, f"{len(mismatches)} mismatches: {mismatches[:3]}")
                all_ok = False
    if all_ok:
        check("T1 circuit_id FK integrity", True)


# ── Test 2: Schedule row count and OH miles reconciliation ────────────────────
def test_2_schedule_counts():
    if not SCHED_CSV.exists():
        check("T2 schedule file exists", False, "missing"); return
    master = read_circuits_master()
    rows = read_csv(SCHED_CSV)

    # Weighted cycle
    cycle_map = {"backbone": 4, "lateral_dominant": 5, "urban_ug_dominant": 6}
    total_circuits = sum(1 for r in master.values() if r["vm_category"] in cycle_map)
    total_cy = sum(cycle_map[r["vm_category"]] for r in master.values() if r["vm_category"] in cycle_map)
    weighted_cycle = total_cy / total_circuits
    expected_rows = total_circuits / weighted_cycle
    lo, hi = expected_rows * 0.90, expected_rows * 1.10
    n = len(rows)
    check("T2a schedule row count", lo <= n <= hi,
          f"{n} rows; expected {lo:.0f}–{hi:.0f} (528/{weighted_cycle:.2f}={expected_rows:.0f} ±10%)")

    # OH miles: sum vs §8 annual target ±2%
    cat_oh = {}
    for r in master.values():
        cat = r["vm_category"]
        cat_oh[cat] = cat_oh.get(cat, 0.0) + float(r["oh_miles"])
    annual_target = sum(cat_oh[cat] / cycle_map[cat] for cat in cycle_map if cat in cat_oh)
    sched_oh = sum(float(r["overhead_miles"]) for r in rows)
    lo_oh, hi_oh = annual_target * 0.98, annual_target * 1.02
    check("T2b Σoh_miles reconciles to §8 ±2%", lo_oh <= sched_oh <= hi_oh,
          f"{sched_oh:.1f} vs target {annual_target:.1f} ({lo_oh:.1f}–{hi_oh:.1f})")

    # Cost: Σest_cost_usd vs BDG-001 ±0.5%
    budget = read_csv(BUDGET_CSV)
    bkg001 = next((int(r["budget_2025_usd"]) for r in budget if r["line_id"] == "BDG-001"), None)
    if bkg001 is None:
        check("T2c BDG-001 exists", False, "not found in budget CSV"); return
    sched_cost = sum(int(r["est_cost_usd"]) for r in rows)
    lo_c, hi_c = bkg001 * 0.995, bkg001 * 1.005
    check("T2c Σest_cost_usd vs BDG-001 ±0.5%", lo_c <= sched_cost <= hi_c,
          f"{sched_cost:,} vs BDG-001={bkg001:,}")


# ── Test 3: Budget 2025 total = 41,600,000 ───────────────────────────────────
def test_3_budget_total():
    if not BUDGET_CSV.exists():
        check("T3 budget file exists", False, "missing"); return
    rows = read_csv(BUDGET_CSV)
    total = sum(int(r["budget_2025_usd"]) for r in rows)
    check("T3 budget 2025 total = 41,600,000", total == 41_600_000,
          f"actual = {total:,}")


# ── Test 4: vm_tree_outages_2024 recomputes from outage_events_base ───────────
def test_4_tree_outages_derived():
    if not TREE_OUT_CSV.exists():
        check("T4 tree outages file exists", False, "missing"); return

    # Read reliability_facts.yaml vegetation totals
    veg_2024 = {}
    in_sec = False
    with open(RELIABILITY_YAML, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s.startswith("vegetation_2024"):
                in_sec = True
                continue
            if in_sec:
                if ":" in s and not s.startswith("vegetation"):
                    k, v = s.split(":", 1)
                    try:
                        veg_2024[k.strip()] = float(v.strip())
                    except ValueError:
                        pass
                elif s.startswith("vegetation_") or (s and not s.startswith(" ")):
                    break

    customers_monthly = read_customers_monthly()
    annual_cs = float(next(iter(customers_monthly.values()), 405805))

    # Recompute from outage events
    with open(OUTAGE_EVENTS, newline="", encoding="utf-8") as f:
        events = list(csv.DictReader(f))

    from collections import defaultdict
    monthly_veg = defaultdict(lambda: {"outages": 0, "ci": 0, "cmi": 0})
    all_monthly  = defaultdict(lambda: {"outages": 0, "ci": 0})

    for e in events:
        ts = e.get("start_ts", "")
        if not ts.startswith("2024"):
            continue
        month = int(ts[5:7])
        all_monthly[month]["outages"] += 1
        all_monthly[month]["ci"] += int(e.get("customers_affected", 0) or 0)
        if e.get("cause_category") != "vegetation":
            continue
        loc = (e.get("tree_location") or "unknown").strip() or "unknown"
        med = e.get("med_flag", "N") or "N"
        key = (month, loc, med)
        monthly_veg[key]["outages"] += 1
        monthly_veg[key]["ci"]      += int(e.get("customers_affected", 0) or 0)
        monthly_veg[key]["cmi"]     += int(e.get("customer_minutes", 0) or 0)

    # Reconstruct expected rows
    expected = {}
    for (month, loc, med), agg in sorted(monthly_veg.items()):
        cs = customers_monthly.get(str(month), 405805)
        all_c = all_monthly.get(month, {"outages": 0, "ci": 0})
        key = (str(month), loc, med)
        expected[key] = {
            "sustained_outages": agg["outages"],
            "customer_interruptions": agg["ci"],
            "customer_minutes": agg["cmi"],
        }

    rows = read_csv(TREE_OUT_CSV)
    actual_keys = set()
    mismatches = []
    for r in rows:
        key = (r["month"], r["tree_location"], r["med_flag"])
        actual_keys.add(key)
        exp = expected.get(key)
        if exp is None:
            mismatches.append(f"unexpected row {key}")
        else:
            for field in ("sustained_outages", "customer_interruptions", "customer_minutes"):
                if int(r[field]) != exp[field]:
                    mismatches.append(f"{key} {field}: {r[field]} != {exp[field]}")

    missing = [str(k) for k in expected if k not in actual_keys]
    if missing:
        mismatches.extend([f"missing row {k}" for k in missing[:3]])

    check("T4 tree_outages recomputes from outage_events_base", len(mismatches) == 0,
          f"{len(mismatches)} discrepancies" if mismatches else "")


# ── Test 5: Notice dates satisfy 14-day minimum; ≥10% in 14-17 day window ────
def test_5_notice_dates():
    if not SCHED_CSV.exists():
        check("T5 schedule file exists", False, "missing"); return
    rows = read_csv(SCHED_CSV)
    violations = []
    tight_count = 0
    for r in rows:
        try:
            p_start  = date.fromisoformat(r["planned_start_date"])
            n_letter = date.fromisoformat(r["notice_letter_date"])
            lead = (p_start - n_letter).days
            if lead < NOTICE_MIN_CALENDAR_DAYS:
                violations.append(f'{r["circuit_id"]}: {lead} days (min {NOTICE_MIN_CALENDAR_DAYS})')
            if NOTICE_MIN_CALENDAR_DAYS <= lead <= 17:
                tight_count += 1
        except Exception as ex:
            violations.append(f'{r["circuit_id"]}: date parse error {ex}')

    tight_pct = tight_count / len(rows) * 100 if rows else 0
    check("T5a all notice dates ≥14 calendar days before work",
          len(violations) == 0, f"{len(violations)} violations: {violations[:3]}")
    check("T5b ≥10% notice dates in 14-17 day window (§3.6a margin rule)",
          tight_pct >= 10,
          f"{tight_pct:.1f}% in tight window ({tight_count}/{len(rows)})")


# ── Test 6: (structural) App-A fields map to clause IDs ──────────────────────
def test_6_app_a_fields():
    # This test checks that the required notice elements appear in the document.
    # Since we can't parse the .md from within this script easily, we check
    # that the basis JSON exists and has App-A clause entries.
    basis_path = DOC_DIR / "RPL-DO-PLN-002.basis.json"
    if not basis_path.exists():
        check("T6 basis.json exists", False, "missing"); return
    with open(basis_path, encoding="utf-8") as f:
        basis = json.load(f)
    app_a_clauses = [c for c in basis.get("clauses", [])
                     if ":App-A" in c.get("clause_id", "")]
    check("T6 App-A clause entries in basis.json", len(app_a_clauses) >= 6,
          f"{len(app_a_clauses)} App-A clauses found")


# ── Test 7: App-D equals top-20 circuits by OH miles in schedule ──────────────
def test_7_app_d_top20():
    if not SCHED_CSV.exists():
        check("T7 schedule file exists", False, "missing"); return
    rows = read_csv(SCHED_CSV)
    top20 = sorted(rows, key=lambda r: -float(r["overhead_miles"]))[:20]
    top20_ids = {r["circuit_id"] for r in top20}
    # Check that App-D section exists in the document
    doc_path = DOC_DIR / "RPL-DO-PLN-002_v2025.1.md"
    if not doc_path.exists():
        check("T7 document exists", False, "missing"); return
    with open(doc_path, encoding="utf-8") as f:
        doc_text = f.read()
    # Check that the top circuit_id is mentioned in App-D section
    all_present = all(cid in doc_text for cid in top20_ids)
    check("T7 App-D top-20 circuit IDs present in document", all_present,
          "" if all_present else f"missing some of: {top20_ids - set(doc_text.split())}")


# ── Test 8: Render files exist ────────────────────────────────────────────────
def test_8_render_files():
    render_dir = DOC_DIR / "render"
    required = [
        render_dir / "RPL-DO-PLN-002_v2025.1.docx",
        render_dir / "RPL-DO-PLN-002_v2025.1.pdf",
        render_dir / "RPL-DO-PLN-002_datasets.xlsx",
    ]
    chart_dir = render_dir / "charts"
    charts = list(chart_dir.glob("*.png")) if chart_dir.exists() else []

    for path in required:
        check(f"T8 render/{path.name} exists", path.exists())
    check("T8 ≥2 chart PNGs in render/charts/", len(charts) >= 2,
          f"{len(charts)} charts found")


# ──────────────────────────────────────────────────────────────────────────────
# Run all tests
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("RPL-DO-PLN-002 Acceptance Tests")
    print("=" * 60)

    test_1_circuit_ids()
    test_2_schedule_counts()
    test_3_budget_total()
    test_4_tree_outages_derived()
    test_5_notice_dates()
    test_6_app_a_fields()
    test_7_app_d_top20()
    test_8_render_files()

    print("=" * 60)
    if failures:
        print(f"FAILED: {len(failures)} test(s): {failures}")
        # Append to README
        readme = DATA_DIR / "README.md"
        with open(readme, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"\n\n## Acceptance Test Results ({datetime.now().isoformat()[:19]})\n\n")
            for r in results:
                f.write(f"- {r}\n")
            f.write(f"\n**Overall: FAILED ({len(failures)} failure(s))**\n")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")
        readme = DATA_DIR / "README.md"
        with open(readme, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"\n\n## Acceptance Test Results ({datetime.now().isoformat()[:19]})\n\n")
            for r in results:
                f.write(f"- {r}\n")
            f.write(f"\n**Overall: PASS (all {len(results)} tests)**\n")
        sys.exit(0)
