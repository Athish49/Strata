# T91 Expected-Findings Answer Key

| **Corpus SHA-256** | `a7adf93afef12d7a7c58008efbca265b3d4dea2f5a27bd18c29eeeeca66937f0` |
|---|---|
| **Generated** | 2026-10-07 |
| **Snapshot S1** | 2024-12-31 |
| **Snapshot S2** | 2025-12-31 |
| **Wave** | 5 — Isolated agent |

---

## 1. Changed Citations Summary

| Citation | S2 Effective | Classification | Substantive? |
|---|---|---|---|
| 170 IAC 1-6-3 | 2025-01-24 | Content element added + renumbered | Yes — new item (6) rate/charge decrease |
| 170 IAC 1-6-4 | 2025-01-24 | Qualifier changed + condition removed | Yes — "may not" + SDC removed |
| 170 IAC 1-6-5 | 2025-01-24 | Required content change | Yes — fax removed; electronic filing mandatory; CSP provisions added |
| 170 IAC 1-7-3 | 2023-05-25 | Typographical correction | No — whitespace in citation only |
| 170 IAC 4-1-16 | 2025-09-12 | Readoption only | No — body text identical |

---

## 2. Document × Expected Status × Finding Counts

| Document | Expected Status | stale_citation | stale_at_approval | informational | Total |
|---|---|---|---|---|---|
| RPL-TAR-GRR-012 | **cleared** | 0 | 0 | 2 | 2 |
| RPL-CS-PRO-004 | **cleared** | 0 | 0 | 1 | 1 |
| RPL-CS-PRO-007 | **cleared** | 0 | 0 | 0 | 0 |
| RPL-DO-PLN-002 | **cleared** | 0 | 0 | 0 | 0 |
| RPL-CS-PRO-011 | **cleared** | 0 | 0 | 1 | 1 |
| RPL-MTR-PGM-001 | **cleared** | 0 | 0 | 0 | 0 |
| RPL-DCC-PRO-003 | **cleared** | 0 | 0 | 0 | 0 |
| RPL-ENV-PRO-005 | **cleared** | 0 | 0 | 0 | 0 |
| RPL-SAF-PRO-009 | **cleared** | 0 | 0 | 0 | 0 |
| RPL-CMP-REG-001 | **flagged** | 3 | 0 | 1 | 4 |
| RPL-REG-CAL-2025 | **flagged** | 0 | 3 | 1 | 4 |
| RPL-LEG-RRS-001 | **cleared** | 0 | 0 | 1 | 1 |
| **TOTAL** | | **3** | **3** | **7** | **13** |

**Non-informational (scored):** 6 (all severity `medium`)  
**Informational (not scored in precision/recall):** 7  

---

## 3. Findings Narrative

### Flagged: RPL-CMP-REG-001 (Compliance Register)

The compliance register was authored with law as-of 2024-12-31 (Snapshot S1). The document's own Section 2.7 and amendment log (2024-12-01) explicitly note that 170 IAC 1-6-3, 1-6-4, and 1-6-5 amendments (effective 2025-01-24) are outside scope and that an update is scheduled for Q1 2025.

- **EF-0001** (`stale_citation` / low): OBL-2024-0018 (1-6-3) cites S1 version. S2 adds new allowable filing type — rate/charge decrease (new item 6); prior items renumbered.
- **EF-0002** (`stale_citation` / low): OBL-2024-0019 (1-6-4) cites S1 version. S2 changes modal verb ("shall not" → "may not") and removes SDC prohibition.
- **EF-0003** (`stale_citation` / low): OBL-2024-0020 (1-6-5) cites S1 version. S2 eliminates fax, mandates electronic filing system, adds CSP telecom provisions.
- **EF-0011** (`informational` / low): Multiple OBL rows reference 4-1-16 through implementing procedures. S2 is readoption — no change.

### Flagged: RPL-REG-CAL-2025 (Regulatory Calendar)

The regulatory calendar was approved 2025-03-14 — fifty days after 170 IAC 1-6-3, 1-6-4, and 1-6-5 became effective in S2 (2025-01-24). The document carries an explicit LAGGING-AT-APPROVAL NOTICE in its front matter and in Section 11.2, and already includes remediation event EVT-2025-0011 (v1.3 calendar update, due 2025-04-30).

- **EF-0004** (`stale_at_approval` / low): 1-6-3 change. Calendar events EVT-0013/0022 cite 1-6-3 generally; EVT-0025 cites 1-6-3(1) [unchanged]; EVT-0036 cites 1-6-3(4) [unchanged]. v1.3 update should add event for new item (6) rate/charge decrease filings.
- **EF-0005** (`stale_at_approval` / low): 1-6-4 change. No specific 1-6-4 parameters embedded in calendar events beyond the LAGGING notice and remediation event.
- **EF-0006** (`stale_at_approval` / low): 1-6-5 change. EVT-0005 (filing procedures training), EVT-0017 (portal access, 1-6-5(c)(1)), EVT-0029 and EVT-0045 (OUCC same-day service, 1-6-5(b)) cite 1-6-5 subsections. v1.3 update should reflect fax elimination and mandatory electronic filing.
- **EF-0012** (`informational` / low): EVT-0006 and EVT-0041 cite 4-1-16 for disconnection compliance monitoring. S2 is readoption — no change.

### Cleared: RPL-TAR-GRR-012

Specific subsections cited in the tariff (1-6-3(2) at R04.7 and 1-6-3(4) at R16.1) are unchanged in S2. The new item (6) in 1-6-3 was inserted before the previously renumbered (7) and (8), but T13 does not cite those items. 1-6-4 and 1-6-5 appear in basis coverage only via general compliance; no specific parameters are embedded. T13 was approved 2025-01-23, one day before the S2 effective date — no stale_at_approval applies.

- **EF-0007** (`informational` / low): R13.1–R13.11 cite 4-1-16 (readoption, unchanged).
- **EF-0008** (`informational` / low): R04.7 cites 1-7-3 (whitespace correction, unchanged).

### Cleared: RPL-CS-PRO-004, RPL-CS-PRO-011

Both implement 170 IAC 4-1-16 (disconnection/reconnection). S2 is a readoption — substantively identical. Informational finding only (EF-0009, EF-0010).

### Cleared: RPL-CS-PRO-007, RPL-DO-PLN-002, RPL-MTR-PGM-001, RPL-DCC-PRO-003, RPL-ENV-PRO-005, RPL-SAF-PRO-009

No changed citations in these documents' grounding packs. RPL-ENV-PRO-005 has an empty pack (327 IAC 2-6.1 absent from DB; document written as company practice).

### Cleared: RPL-LEG-RRS-001

170 IAC 1-6-5 appears in one retention table row (RRS-FIN-011) as the generating regulation. S2 procedural changes do not affect the record category or 7-year retention period. Informational finding only (EF-0013).

---

## 4. Scoring Instructions

See `scoring.py` for implementation. Summary:

### Match Criteria

A system detection on an expected finding **matches** when all of:
1. `doc_id` matches
2. Detected clause is in `acceptable_clause_ids` OR is the immediate parent clause with `parent_tolerance: true`
3. `citation` matches at the same section level (subsection specificity is acceptable if the section-level citation matches)

Each expected finding matches **at most one** system detection. Extra detections on the same expected finding are ignored (not false positives).

### Scored Metrics

| Metric | Formula | Target |
|---|---|---|
| **Recall** | matched non-informational / 6 expected | ≥ 0.83 |
| **Precision** | matched non-informational / system non-informational detections | ≥ 0.80 |
| **False-positive rate (negative set)** | flagged must_not_flag clauses / total must_not_flag | 0.00 |
| **Routing accuracy** | matched findings with correct `route_to` / matched | ≥ 0.80 |
| **Baseline (S1)** | non-informational findings on S1 corpus | 0 |

### Severity Breakdown (non-informational)

| Severity | Count | Citations |
|---|---|---|
| high | 0 | — |
| medium | 6 | 1-6-3 (×2), 1-6-4 (×2), 1-6-5 (×2) |
| low | 0 | — |

### `finding_type` Agreement

For inter-annotator agreement (Cohen's κ), the following mapping is used:
- `stale_citation` and `stale_at_approval` are treated as distinct classes
- `informational` findings are excluded from κ calculation
- Target κ ≥ 0.80 before release (see `adjudication_log.md`)

---

## 5. Negative Set Summary

Clauses listed in `must_not_flag` across all documents:

| Document | Must-not-flag clauses | Reason |
|---|---|---|
| RPL-TAR-GRR-012 | R04.7, R16.1, R13.1–R13.11, R02.3 | Cites unchanged 1-6-3 subsections (2) and (4); 4-1-16 readoption |
| RPL-CS-PRO-004 | §1, §8–§12, App-A representative | 4-1-16 readoption — no substantive change |
| RPL-CS-PRO-011 | §1–§11 representative | 4-1-16 readoption — no substantive change |
| RPL-CMP-REG-001 | §1–§12 representative | General scope/definitions; obligations to non-changed citations |
| RPL-REG-CAL-2025 | §1–§4, AppA, AppB | Scope/definitions; events with unchanged citations |
| RPL-LEG-RRS-001 | §1–§7 representative | Retention rows for non-changed regulations |

**False-positive target:** 0 flagged must_not_flag clauses on both S1 and S2 runs.

---

## 6. Decoy Analysis

| Citation | Documents citing it | Classification | Why correctly unchanged |
|---|---|---|---|
| 170 IAC 1-7-3 | RPL-TAR-GRR-012 (via R02.3 basis), RPL-CMP-REG-001 (via T13 implementing doc) | Typographical only | Whitespace correction in statutory citation; substantive text identical |
| 170 IAC 4-1-16 | RPL-TAR-GRR-012, RPL-CS-PRO-004, RPL-CS-PRO-011, RPL-CMP-REG-001, RPL-REG-CAL-2025 | Readoption only | Body text identical S1→S2; effective date change is administrative |

**Note on T12 (RPL-LEG-RRS-001):** 170 IAC 1-6-5 cites are in the retention table (source-regulation pointer, RRS-FIN-011) — not a decoy since 1-6-5 substantively changed, but the retention row is not affected by the procedural changes. Covered as `informational` EF-0013 rather than a decoy.

---

*This document is Wave 5 restricted output — never expose to generator agents or the Strata engine under test.*
