# IEEE Std 1366™-2012 — Major Event Day (MED) Identification Method (§2.5β)

**Extract prepared by:** Corpus Orchestrator  
**Date:** 2025-10-06  
**Source:** LBNL public report — Eto, J.H., "Reliability Metrics and the Role of the Reliability Value-Based Planning Framework in Assessing the Value of Electricity Reliability," Lawrence Berkeley National Laboratory, LBNL-6236E, 2013. Available at: https://eta-publications.lbl.gov/sites/default/files/7._eto_-_reliability_metrics_and_rvbp.pdf  
**Purpose:** Reference extract for T04 (ops data) and T19 (outage reporting) document tasks in the Strata synthetic corpus project. Generators cite this extract; they do not reconstruct the paywalled IEEE standard from memory.

---

## 1. What the method does

The IEEE 1366 Major Event Day (MED) exclusion method identifies days with unusually high SAIDI that should be excluded from a utility's "normal" SAIDI/SAIFI metric. Including major events would inflate the index and obscure year-to-year trends in routine reliability.

---

## 2. The 2.5β Threshold (TMED) Algorithm

### Step 1 — Collect daily SAIDI data for the study period

Collect daily SAIDI values for a consecutive five-year period ending on the last day of the year preceding the reporting year (i.e., for 2024 reporting: use daily SAIDI for 2019–2023).

Let the dataset be: **S** = {s₁, s₂, …, s_N} where N ≈ 1,826 days (5 × 365 or 5 × 365 + 1 for leap years). Each sᵢ is the system-level customer-minutes of interruption on day i divided by the number of customers served (the daily contribution to SAIDI).

### Step 2 — Compute the natural log of daily SAIDI values (for days with non-zero SAIDI)

For each day with sᵢ > 0, compute:

    xᵢ = ln(sᵢ)

Exclude days with zero SAIDI (no interruptions) from the log transform. The zero-day exclusion is important; excluding them improves the lognormal fit.

### Step 3 — Compute the mean (μ) and standard deviation (σ) of the log-transformed values

    μ = (1/M) × Σ xᵢ         (sum over the M non-zero days)
    σ = sqrt( (1/(M-1)) × Σ (xᵢ − μ)² )

### Step 4 — Compute TMED

    TMED = exp(μ + 2.5 × σ)

TMED is expressed in customer-minutes per customer (same units as daily SAIDI). It is computed once from the five-year study period and applied to the current reporting year.

**Interpretation:** TMED is the 2.5-standard-deviation point of the fitted lognormal distribution of non-zero daily SAIDI. Days whose SAIDI exceeds TMED are classified as Major Event Days and excluded from the ex-MED indices.

---

## 3. Applying MED to the Reporting Year

For each day d in the reporting year:

1. Compute daily SAIDI(d) from the outage event data: sum of customer-minutes on events that **begin on day d** divided by customers served.
   - Events beginning before midnight and ending after: the customer-minutes accrue to the day the event starts (the "begin-date accrue" convention).
   - Sustained interruptions only (≥ 1 minute or the threshold the utility uses for SAIDI).

2. If SAIDI(d) > TMED: classify d as a Major Event Day.

3. When computing ex-MED annual indices:
   - Exclude all customer-interruptions and customer-minutes from events that began on any MED.
   - Include customer-interruptions and customer-minutes from events on non-MED days, regardless of duration.

---

## 4. Indices Definitions (IEEE 1366)

| Index | Full name | Formula |
|---|---|---|
| SAIFI | System Average Interruption Frequency Index | Total Sustained Customer-Interruptions / Customers Served |
| SAIDI | System Average Interruption Duration Index | Total Customer-Minutes of Interruption / Customers Served |
| CAIDI | Customer Average Interruption Duration Index | SAIDI / SAIFI (average duration per customer interrupted) |
| MAIFI | Momentary Average Interruption Frequency Index | Total Momentary Customer-Interruptions / Customers Served |

"Customers served" is the count of customers connected to the distribution system at a representative point in the year (typically the beginning of the year or an average of beginning and end; the utility's chosen denominator must be stated consistently).

---

## 5. Worked example (illustrative, not normative)

Suppose the five-year study period (2019–2023) yields:
- M = 623 non-zero SAIDI days
- μ (log-transformed) = 1.62
- σ (log-transformed) = 1.18

Then:  
    TMED = exp(1.62 + 2.5 × 1.18) = exp(1.62 + 2.95) = exp(4.57) ≈ 96.5 customer-minutes

For the 2024 reporting year, any day with system-level SAIDI > 96.5 min is a Major Event Day and excluded from ex-MED indices.

---

## 6. Utility-specific notes for T04 / T19 use

- **Accrue-to-begin-date rule.** Unless the pack states otherwise, all customer-minutes for an outage accrue to the calendar day on which the outage began. This is the IEEE 1366 convention (not accrue-to-end-date or split-by-midnight).
- **Denominator.** Use the `customers_served` field from `reliability_facts.yaml`, which T04 establishes. The denominator is the same for both with-MED and ex-MED indices.
- **Study period.** The five-year study period for 2024 reporting is 2019–2023. The corpus provides `daily_saidi_history_2019_2023.csv` for this computation.
- **Zero-SAIDI days.** Days with zero daily SAIDI are excluded from the log calculation but not from the index computation (they simply contribute nothing to SAIDI).
- **Planned interruptions.** Unless the pack says otherwise, planned interruptions are included in the denominator indices and shown separately as an exclusion when the pack or the utility chooses to display them separately.
- **Momentary interruptions** (< 1 minute or < 5 minutes, per utility definition) do not count toward SAIDI/SAIFI but do count toward MAIFI. Use the definition from the pack (if any) or state it as company practice.
- **TMED unit check.** TMED is in the same units as daily SAIDI: customer-minutes per customer per day. It is not an annual figure.

---

## 7. Citation instructions for document tasks

When citing this method in a corpus document, use the following language:

> Major Event Days are identified using the method specified in IEEE Std 1366™-2012, §2.5β (the "2.5β TMED method"), as summarized in `corpus/_global/reference/ieee1366_med_method.md`. The threshold (T_MED) is computed from five years of daily SAIDI data preceding the reporting year.

Do **not** cite specific page numbers, clauses or tables from the paywalled IEEE standard itself. Cite only this extract, which is based on the LBNL public documentation of the method.

---

*End of extract*
