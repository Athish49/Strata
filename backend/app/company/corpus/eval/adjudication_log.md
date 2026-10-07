# T91 Adjudication Log

| **Corpus SHA-256** | `a7adf93afef12d7a7c58008efbca265b3d4dea2f5a27bd18c29eeeeca66937f0` |
|---|---|
| **Date** | 2026-10-07 |
| **Wave** | 5 — Isolated agent |
| **Status** | Single-annotator provisional release (dual-annotator pending) |

---

## Inter-Annotator Agreement

Per T91 spec step 9, two independent isolated agents (A and B) produce annotation keys and a third adjudicates disagreements. Cohen's κ target ≥ 0.80 on `finding_type` at the clause level before release.

**This release is a single-annotator provisional key.** The dual-annotator run and formal κ calculation are pending. This log will be updated when the second annotator's key is available.

Provisional κ: **N/A** (single annotator)  
Release condition met: **No** — provisional only

---

## Annotation Decisions

### AD-001 — Disposition of 170 IAC 4-1-16 (Readoption)

**Question:** Should 4-1-16's readoption (S2 effective 2025-09-12) generate `stale_citation` or `informational` findings for documents that cite it (T13, T14, T17, T10, T11)?

**Decision:** `informational` (low severity)

**Reasoning:** The body text of 4-1-16 is substantively identical in S1 and S2. The readoption is an administrative filing that renews the rule without substantive change. No notice period, prohibited condition, or obligation value changed. The `stale_citation` type applies when a changed S2 version invalidates a parameter embedded in a document clause; it does not apply to administrative readoption filings that do not change obligations.

**Evidence:** `s1_s2_diffs.json` confirms: S2 body = S1 body + readoption filing citation appended to authority block. Normalized content (strip metadata suffix) is character-identical.

---

### AD-002 — Disposition of 170 IAC 1-7-3 (Whitespace Correction)

**Question:** Should the whitespace correction in 1-7-3's statutory citation generate any finding?

**Decision:** `informational` (low severity) for T13 only (which directly cites 1-7-3). No finding for documents that do not directly cite 1-7-3.

**Reasoning:** The S2 change is a typographical correction — one extraneous space removed from `8-1.5-3- 8.3` → `8-1.5-3-8.3`. There is no obligation, value, or process change. Including it as `informational` ensures the engine is not penalized for detecting the citation update, but it cannot generate precision/recall impact.

---

### AD-003 — Stale_citation vs. Stale_at_approval for RPL-CMP-REG-001

**Question:** T10 (RPL-CMP-REG-001) was approved 2025-01-23 (one day before S2 effective 2025-01-24 for 1-6-3/4/5). Should T10 findings be classified as `stale_citation` or `stale_at_approval`?

**Decision:** `stale_citation`

**Reasoning:** `stale_at_approval` applies when a document was approved *after* the S2 effective date while still incorporating S1 parameters — i.e., the approver had the opportunity to use S2 law but did not. T10 was approved 2025-01-23, one calendar day *before* S2 took effect on 2025-01-24. The approver could not have incorporated S2 because it was not yet in force. `stale_citation` (the document's cited version is now out of date relative to S2) is therefore the correct classification.

**Contrast with T11:** T11 was approved 2025-03-14 — fifty days after S2 effective date — making `stale_at_approval` appropriate. The O-3 project directive explicitly assigned `lagging_at_approval: true` to T11 only.

---

### AD-004 — Severity of All S2-Change Findings

**Question:** Should any 1-6-3/4/5 findings be elevated to `medium` or `high` severity?

**Decision:** All findings remain `low` severity.

**Reasoning:**  
- `high` severity is reserved for customer-facing or regulator-facing obligations where a wrong value could result in a regulatory violation or customer harm. None of the 1-6-3/4/5 changes create this risk for RPL: (a) 1-6-3 adds a new *permissive* filing type (not a new obligation); (b) 1-6-4's SDC removal and modal verb change weaken, not strengthen, a prohibition; (c) 1-6-5's fax elimination and electronic filing mandate affect internal procedures, not customer-facing commitments.  
- `medium` would apply if the changes introduced a new internal process obligation or deadline. No new deadline was added; the electronic filing system was already the primary method and fax was rarely used.  
- Both T10 and T11 self-identified the gap through their own acknowledged-deficiency notices and scheduled remediation events, reducing severity further.

---

### AD-005 — New Requirement Gap for 1-6-3 Item (6) (Rate/Charge Decrease Filings)

**Question:** Does the new item (6) in 1-6-3 S2 (rate/charge decrease as an allowable administrative filing type) create a `new_requirement_gap` for any corpus document?

**Decision:** No `new_requirement_gap` findings.

**Reasoning:** A `new_requirement_gap` applies when a new S2 section creates a positive obligation that the existing document does not address. Item (6) in 1-6-3 S2 is a *permissive expansion* — it allows a new type of filing to use the 30-day administrative procedure. It does not require RPL to do anything it was not already doing. No document needs to be updated to comply with a new mandate. The T10 and T11 stale_citation/stale_at_approval findings already capture that these documents need to incorporate the updated allowable-type list.

---

### AD-006 — T12 (RPL-LEG-RRS-001) Classification

**Question:** Should T12's single citation of 1-6-5 (retention table, RRS-FIN-011) generate a `stale_citation` finding or only `informational`?

**Decision:** `informational`

**Reasoning:** The citation in RRS-FIN-011 is a *source regulation pointer* — it identifies the regulation that generates the records to be retained. The 7-year retention period is an RPL internal policy decision, not a value prescribed by 1-6-5. The S2 changes (fax removed, electronic filing mandatory) affect how filings are made, not how long the resulting records are kept. There is no embedded parameter from 1-6-5 in the retention table that is now wrong. An `informational` finding is appropriate to flag that the cited regulation changed, but no update action is required.

---

### AD-007 — T11 Stale_at_approval Severity: Acknowledged vs. Unacknowledged

**Question:** Should T11's `stale_at_approval` severity be higher because the document was approved while citing outdated law?

**Decision:** Retain `low` severity due to full acknowledgement and scheduled remediation.

**Reasoning:** The T91 spec notes that severity reflects customer-facing/regulator-facing impact. T11 mitigates severity through three mechanisms: (1) the front-matter LAGGING-AT-APPROVAL NOTICE explicitly identifies the outdated citations; (2) Section 11.2 restates the notice; (3) EVT-2025-0011 schedules v1.3 remediation by 2025-04-30. An unacknowledged `stale_at_approval` finding on a customer-facing document would warrant `medium` or `high`. T11's transparency and existing remediation plan justify `low`.

---

### AD-008 — T14 and T17 vs. Orchestrator `is_cleared=false`

**Question:** The orchestrator report marks T14 (RPL-CS-PRO-004) and T17 (RPL-CS-PRO-011) as `is_cleared=false`. The T91 answer key marks them as `expected_status: cleared`. Which takes precedence?

**Decision:** T91 expected_status: cleared; conflict recorded.

**Reasoning:** The orchestrator marked T14 and T17 `is_cleared=false` because they cite 170 IAC 4-1-16, which has an S2 record (effective 2025-09-12). Database evidence (`s1_s2_diffs.json`): normalized body text of S2 4-1-16 is character-identical to S1. The S2 change is a readoption filing citation appended to the authority block only. No obligation, value, period, or condition changed. Under T91 spec step 2, this classifies as `readoption_only` — the spec does not create a non-informational finding for readoption-only changes. T14 and T17 are therefore correctly cleared.

**Conflict note:** If a future version of the corpus includes a substantive amendment to 4-1-16, T14 and T17 would be reclassified to flagged. The orchestrator's conservative `is_cleared=false` may reflect a design intent to require positive confirmation of no-change for every cited S2 record, which is more conservative than the T91 spec requires.

---

### AD-009 — T11 EVT-2025-0017: Subsection 1-6-5(c)(1) Does Not Exist in S2

**Question:** T11 EVT-2025-0017 cites `170 IAC 1-6-5(c)(1)` (IURC electronic portal access verification). In S2, subsection (c) was restructured: the enumerated subsections (c)(1) and (c)(2) were replaced by a single paragraph mandating the electronic filing system. Does this warrant a separate finding or elevate EF-0006?

**Decision:** Noted in EF-0006's expected_action; no separate finding created.

**Reasoning:** EF-0006 already anchors to `RPL-REG-CAL-2025:6.1` (the Q2 events section that contains EVT-2025-0017) with `stale_at_approval` classification. The specific stale subsection reference `1-6-5(c)(1)` is captured in EF-0006's s2_quote and expected_action. Creating a separate finding for the subsection granularity would duplicate EF-0006 on the same clause and citation. A system detection on `1-6-5(c)(1)` or `1-6-5(c)` (the parent) would match EF-0006's citation criteria after subsection normalization. The finding type remains `stale_at_approval` rather than the potentially more precise `stale_citation` because the document-level cause is `lagging_at_approval`.

---

### AD-010 — Severity Calibration for 1-6-3/4/5 Findings

**Decision:** All stale_citation and stale_at_approval findings for 1-6-3/4/5 are classified `medium` severity.

**Reasoning:** Spec definition: high = customer-facing or regulator-facing obligation; medium = internal process; low = informational. 170 IAC 1-6-3/4/5 govern how RPL submits filings to the IURC. T10 and T11 are internal compliance infrastructure documents — their staleness is an internal process issue that could propagate to regulator-facing filing failures. `medium` correctly captures this risk level. `high` would require the stale clause to directly govern a customer-facing or regulator-facing transaction; the stale clauses here govern compliance documentation, not the filings themselves. Initial release used `low` (with acknowledged-deficiency reduction), which was inconsistent with the spec's objective severity definition; corrected to `medium`.

---

## Pending Items

| Item | Status | Target |
|---|---|---|
| Annotator B independent key | Pending | Before production release |
| Cohen's κ calculation | Pending | κ ≥ 0.80 required |
| Check 14 (S2 contamination) — T90 deferred | Pending | Isolated contamination agent per Appendix O-11 |
| T90 checks 11–13 (LLM fidelity/realism) | Deferred | Per-document LLM agents required |
| T90 check 15 (engine baseline run on S1) | Deferred | Requires Strata engine deployment |

---

*This log is Wave 5 restricted — never expose to generator agents or the Strata engine under test.*
