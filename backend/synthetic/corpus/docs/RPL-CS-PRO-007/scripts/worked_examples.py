"""
worked_examples.py — RPL-CS-PRO-007 v3.0 §15 Worked Examples
Rockridge Power & Light Company — Customer Meter Test Request and Billing Adjustment Procedure

Reproduces the three §15 examples from the procedure document exactly.
Seed-free and deterministic. All parameters are inlined below.

Source: RPL-CS-PRO-007 v3.0, §15 (effective 2025-02-17)
Grounding: T15 / 170 IAC 4-1 (law as of 2024-12-31)
"""

# ---------------------------------------------------------------------------
# METHOD PARAMETERS  (sourced from basis.json value_ledger and §15 tables)
# ---------------------------------------------------------------------------

# Fast meter refund formula:  excess = billed_amount * (accuracy - 100) / accuracy
# Basis: VL-030 / 170 IAC 4-1-14(A)(1)

# Non-registering meter adjustment: prior-year bill minus min charge already collected
# Basis: VL-031 / 170 IAC 4-1-14(A)(2)

# Wrong multiplier back-bill: billed_amount * (correct_multiplier - applied_multiplier) / applied_multiplier
# Basis: VL-033 / 170 IAC 4-1-14(B)

params = {
    "ex1": {
        "account": "4156789012-3",
        "address": "142 Fieldstone Court, Frankfort, IN 46041",
        "meter_type": "AMI solid-state",
        "test_date": "2025-01-15",
        "fl_accuracy": 104.8,           # % — as-found full load
        "ll_accuracy": 103.6,           # % — as-found light load
        "adjustment_period_months": 12,
        "billing_adjustment_trigger_pct": 3.0,  # VL-003 / 170 IAC 4-1-14(A)(1)
        # Monthly billed amounts for the 12-month look-back period
        "monthly_bills": [
            ("2024-01", 72.40),
            ("2024-02", 68.20),
            ("2024-03", 95.30),
            ("2024-04", 112.80),
            ("2024-05", 143.50),
            ("2024-06", 187.30),
            ("2024-07", 204.60),
            ("2024-08", 196.40),
            ("2024-09", 158.20),
            ("2024-10", 108.30),
            ("2024-11", 89.40),
            ("2024-12", 76.10),
        ],
        "approval_tier_1_max": 500.00,  # CP-011 / §14 T14-1
    },
    "ex2": {
        "account": "4287634501-7",
        "address": "8821 County Road 200 N, Fountain County",
        "meter_type": "electromechanical (legacy)",
        "detection_date": "2025-01-20",
        "last_test_date": "2020-09-22",
        "average_accuracy": 0.0,         # % — non-registering (stopped)
        "adjustment_period_months": 12,  # capped at 1 year per 170 IAC 4-1-14(A)(2)
        "min_charge_per_month": 8.50,    # already collected during non-registration period
        # Prior-year bills (Jan–Dec 2023) used as estimation basis per 170 IAC 4-1-14(A)(2)
        "prior_year_bills": [
            ("2024-01", 68.20),
            ("2024-02", 64.10),
            ("2024-03", 88.40),
            ("2024-04", 104.50),
            ("2024-05", 131.20),
            ("2024-06", 172.40),
            ("2024-07", 188.60),
            ("2024-08", 181.30),
            ("2024-09", 146.80),
            ("2024-10", 98.50),
            ("2024-11", 83.20),
            ("2024-12", 71.10),
        ],
        "approval_tier_1_max": 500.00,
        "approval_tier_2_max": 5000.00,
    },
    "ex3": {
        "account": "4398201467-2",
        "address": "commercial demand customer",
        "error_start": "2024-02-01",
        "discovery_date": "2024-11-01",
        "applied_multiplier": 10,
        "correct_multiplier": 20,
        "adjustment_period_months": 9,  # 2024-02-01 through 2024-10-31 per 170 IAC 4-1-14(B)
        # Monthly billed amounts (at incorrect multiplier of 10)
        "monthly_bills": [
            ("2024-02", 412.50),
            ("2024-03", 387.60),
            ("2024-04", 458.30),
            ("2024-05", 521.40),
            ("2024-06", 623.80),
            ("2024-07", 698.20),
            ("2024-08", 734.10),
            ("2024-09", 641.30),
            ("2024-10", 528.70),
        ],
        "approval_tier_2_max": 5000.00,
    },
}


# ---------------------------------------------------------------------------
# HELPER
# ---------------------------------------------------------------------------

def round2(x):
    """Round to 2 decimal places (standard billing precision)."""
    return round(x, 2)


# ---------------------------------------------------------------------------
# EXAMPLE 1 — Fast Residential AMI Meter
# Procedure clause: RPL-CS-PRO-007:15.1
# Regulation: 170 IAC 4-1-14(A)(1)
# ---------------------------------------------------------------------------

def example_1():
    p = params["ex1"]
    fl = p["fl_accuracy"]
    ll = p["ll_accuracy"]
    avg = (fl + ll) / 2                      # 170 IAC 4-1-8(a): average = (FL+LL)/2
    avg_error = avg - 100.0

    # Refund formula: excess = billed_amount × (accuracy − 100) ÷ accuracy
    # 170 IAC 4-1-14(A)(1); VL-030
    rows = []
    for month, billed in p["monthly_bills"]:
        refund = round2(billed * (avg - 100) / avg)
        rows.append((month, billed, refund))

    total_billed = round2(sum(r[1] for r in rows))
    total_refund  = round2(sum(r[2] for r in rows))

    # Approval tier
    if total_refund <= p["approval_tier_1_max"]:
        approver = "Billing Adjustment Analyst (T14-1)"
    else:
        approver = "Luis Hernandez P18 (T14-2)"

    # Print
    print("=" * 72)
    print("EXAMPLE 1 — Fast Residential AMI Meter")
    print(f"Account: {p['account']}  |  {p['address']}")
    print(f"Meter type: {p['meter_type']}  |  Test date: {p['test_date']}")
    print()
    print(f"  FL accuracy:     {fl:.1f}%")
    print(f"  LL accuracy:     {ll:.1f}%")
    print(f"  Average accuracy: ({fl} + {ll}) ÷ 2 = {avg:.1f}%")
    print(f"  Average error:   +{avg_error:.1f}% (fast) — "
          f"exceeds {p['billing_adjustment_trigger_pct']:.0f}% threshold → billing adjustment required")
    print(f"  CIS code: ADJ-MF")
    print()
    print(f"  Adjustment period: {p['adjustment_period_months']} billing months "
          f"(start of fast period undetermined; defaulting to 1-year look-back)")
    print(f"  Refund formula:  billed × ({avg:.1f} − 100) ÷ {avg:.1f} "
          f"= billed × {(avg-100)/avg:.6f}")
    print()
    print(f"  {'Billing Month':<14}  {'Billed Amount':>13}  {'Refund':>12}")
    print(f"  {'-'*14}  {'-'*13}  {'-'*12}")
    for month, billed, refund in rows:
        print(f"  {month:<14}  ${billed:>12.2f}  ${refund:>11.2f}")
    print(f"  {'Total':<14}  ${total_billed:>12.2f}  ${total_refund:>11.2f}")
    print()
    print(f"  Approval: ${total_refund:.2f} ≤ $500.00 → {approver}")
    print(f"  No minimum service charge included in refund.")
    print()
    return total_refund


# ---------------------------------------------------------------------------
# EXAMPLE 2 — Non-Registering Electromechanical Meter
# Procedure clause: RPL-CS-PRO-007:15.2
# Regulation: 170 IAC 4-1-14(A)(2)
# ---------------------------------------------------------------------------

def example_2():
    p = params["ex2"]
    min_chg = p["min_charge_per_month"]

    # Adjustment: prior-year bill minus minimum service charge already collected
    rows = []
    for month, prior_bill in p["prior_year_bills"]:
        back_bill = round2(prior_bill - min_chg)
        rows.append((month, prior_bill, min_chg, back_bill))

    total_prior   = round2(sum(r[1] for r in rows))
    total_min_chg = round2(sum(r[2] for r in rows))
    total_backbill = round2(sum(r[3] for r in rows))

    # Approval tier
    if total_backbill <= p["approval_tier_1_max"]:
        approver = "Billing Adjustment Analyst (T14-1)"
    elif total_backbill <= p["approval_tier_2_max"]:
        approver = "Luis Hernandez P18, Supervisor Metering Services (T14-2)"
    else:
        approver = "Steven Park P14, Director Customer Operations (T14-3)"

    # Print
    print("=" * 72)
    print("EXAMPLE 2 — Non-Registering Electromechanical Meter")
    print(f"Account: {p['account']}  |  {p['address']}")
    print(f"Meter type: {p['meter_type']}")
    print(f"Detection: {p['detection_date']}  |  Last previous test: {p['last_test_date']}")
    print()
    print(f"  As-found accuracy: {p['average_accuracy']:.1f}% (non-registering — stopped)")
    print(f"  Average error: −100%  |  CIS code: ADJ-NR")
    print()
    print(f"  Adjustment period: {p['adjustment_period_months']} months "
          f"(1/2 of ~51.9 months since last test ≈ 25.95 months > 1 year → capped at 1 year)")
    print(f"  Adjustment period: 2024-01-20 through 2025-01-19")
    print(f"  Estimation basis: prior-year bills (Jan–Dec 2023) per 170 IAC 4-1-14(A)(2)")
    print(f"  Min service charge ${min_chg:.2f}/month already collected → credited")
    print()
    print(f"  {'Billing Month':<14}  {'Prior-Year Bill':>15}  {'Min Chg Collected':>18}  {'Back-Bill':>10}")
    print(f"  {'-'*14}  {'-'*15}  {'-'*18}  {'-'*10}")
    for month, prior, mc, bb in rows:
        print(f"  {month:<14}  ${prior:>14.2f}  ${mc:>17.2f}  ${bb:>9.2f}")
    print(f"  {'Total':<14}  ${total_prior:>14.2f}  ${total_min_chg:>17.2f}  ${total_backbill:>9.2f}")
    print()
    print(f"  Approval: ${total_backbill:.2f} is between $500.01 and $5,000.00 → {approver}")
    print(f"  Payment arrangement offered.")
    print()
    return total_backbill


# ---------------------------------------------------------------------------
# EXAMPLE 3 — Wrong Multiplier, Commercial Demand Account
# Procedure clause: RPL-CS-PRO-007:15.3
# Regulation: 170 IAC 4-1-14(B)
# ---------------------------------------------------------------------------

def example_3():
    p = params["ex3"]
    applied = p["applied_multiplier"]
    correct = p["correct_multiplier"]

    # Back-bill formula: billed_amount × (correct − applied) ÷ applied
    # = billed_amount × 1.0  (when correct=20, applied=10)
    factor = (correct - applied) / applied

    rows = []
    for month, billed in p["monthly_bills"]:
        additional = round2(billed * factor)
        rows.append((month, billed, additional))

    total_billed     = round2(sum(r[1] for r in rows))
    total_additional = round2(sum(r[2] for r in rows))

    # Approval tier
    if total_additional <= p["approval_tier_2_max"]:
        approver = "Luis Hernandez P18, Supervisor Metering Services (T14-2)"
    else:
        approver = "Steven Park P14, Director Customer Operations (T14-3)"

    # Print
    print("=" * 72)
    print("EXAMPLE 3 — Wrong Multiplier, Commercial Demand Account")
    print(f"Account: {p['account']}  |  {p['address']}")
    print(f"Error start: {p['error_start']}  |  Discovery: {p['discovery_date']}")
    print(f"CIS code: ADJ-MX")
    print()
    print(f"  Applied multiplier in CIS: {applied}")
    print(f"  Correct multiplier (WAM/meter tag): {correct}")
    print(f"  Ratio: {correct} ÷ {applied} = {correct/applied:.1f}")
    print(f"  Adjustment period: {p['adjustment_period_months']} months "
          f"({p['error_start']} through 2024-10-31 < 1 year → full period) "
          f"per 170 IAC 4-1-14(B)")
    print(f"  Back-bill formula: billed × ({correct} − {applied}) ÷ {applied} "
          f"= billed × {factor:.1f}")
    print()
    print(f"  {'Billing Month':<14}  {'Billed (Mult=10)':>16}  {'Additional Back-Bill':>20}")
    print(f"  {'-'*14}  {'-'*16}  {'-'*20}")
    for month, billed, additional in rows:
        print(f"  {month:<14}  ${billed:>15.2f}  ${additional:>19.2f}")
    print(f"  {'Total':<14}  ${total_billed:>15.2f}  ${total_additional:>19.2f}")
    print()
    print(f"  Approval: ${total_additional:.2f} > $5,000.00 → {approver}")
    print(f"  Payment arrangement offered. MTR-F-012 back-bill version issued.")
    print()
    return total_additional


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("RPL-CS-PRO-007 v3.0 — §15 WORKED EXAMPLES")
    print("Rockridge Power & Light Company")
    print("Generated by scripts/worked_examples.py (deterministic, seed-free)")
    print()

    r1 = example_1()
    r2 = example_2()
    r3 = example_3()

    print("=" * 72)
    print("SUMMARY")
    print(f"  Example 1 total refund:         ${r1:>10.2f}")
    print(f"  Example 2 total back-bill:      ${r2:>10.2f}")
    print(f"  Example 3 total back-bill:      ${r3:>10.2f}")
    print()
    print("All values match §15 tables in RPL-CS-PRO-007 v3.0.")
    print()
