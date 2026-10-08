# Strata v1 — Impact Engine PRD

Read order for Claude Code: `prd.md` → `architecture.md` → `data_model.md` → `engine_spec.md` → `api_ui.md` → `implementation_plan.md`.
If anything is ambiguous, follow these docs literally; do not invent features, tables, or routes. If blocked, stop and report.
The earlier company-ingestion spec, gap report and plan were retired (see git history, commit `12e6e7c` and earlier). Comments in `backend/app/company_ingest` and its tests that cite "SPEC §n" or "task 1.x.y" refer to those retired docs; they are not part of this plan, and the task numbers in `implementation_plan.md` are unrelated to them. Reference material for the data layers is in `supplement_docs/`.

## 1. Goal
When government rules change between snapshot S1 and S2, show the company **which clauses in which documents** are affected, **why** (verified quotes from both rule versions and the clause), **what must change**, and **who must act**. Flag only — never edit company documents.

## 2. Demo scenario (fixed assumptions)
- Company: Rockridge Power & Light (RPL, `company_id='rpl'`), synthetic Indiana electric distribution utility. 12 ingested documents across 5 verticals.
- All RPL documents are compliant with S1 (`law_as_of = 2024-12-31`). A run with S1 as current law must produce **0 non-informational findings**.
- Only the S1→S2 changes are evaluated. Never re-scan all of S2 against company data.
- Snapshots: IAC 2024-12-31 → 2025-12-31; CFR 2025-01-02 → 2026-10-02.
- S2 is **write-on-change**: S2 holds only changed or new rows. **A section absent from S2 is unchanged, never repealed.**
- The engine is generic. No logic keyed to specific doc IDs, citations, titles, or to RPL.

## 3. Data reality (measured 2026-10-07) — the design is built around this
| Fact | Value |
|---|---|
| IAC S2 rows with changed content_hash / new sections | 1,036 / 32 |
| CFR S2 changed / new | 45 / 1 |
| IAC changes that are cosmetic (readoption stamps, DIN lines, spacing artifacts) | 996 of 1,036 after the W0 normalizer fix (was 590) — `diff_hash` filters them |
| Substantive changes (diff_hash), after W0 fix | IAC 40, CFR 37 (total 77; before the fix: IAC 446, CFR 45). Re-verify on the first kb run |
| Substantive changes in sections RPL cites (after W0 fix) | **4 sections (170 IAC 1-6-2..1-6-5), 45 clauses, 4 documents** (was 8 sections / 3 docs). Re-verify on the first kb run |
| Of the top 5: real meaning change | ≤1 (others: cosmetic footer, comma, statute-ref metadata, "shall not"→"may not") |
| `170 IAC 4-1-16` | cited by 94 clauses; its change is cosmetic → must flag 0 |
| New S2 sections in rules RPL cites / repeal flips RPL cites | 0 / 0 |
| CFR citations resolved at section level | 0 → all CFR changes go to radar |
| `defined_terms` linked to code sections | 0 → no definition-ripple path |
| `company.datasets` | 0 rows → no quantified impact |
| `restates` links | 3,048, driven by citation-number noise ("170") → not used |
| Effective dates for IAC changes | none in `regulatory_actions`; only DIN publication dates in S2 text |

**Implications**
1. The real wave is a **precision test**: the engine must clear every clause that cites a changed-but-cosmetic section (63 of 67 cited sections that have an S2 row are cosmetic) and flag only true impacts.
2. The real wave alone may yield few clause findings. **What-if mode** lets the expert apply a change live and see clause-level conflicts propagate through the same engine.
3. ~70 substantive changes touch no RPL citation (77 total minus the 4 cited). The **radar** screens them against the company profile; it is small, so it stays Should-have.

## 4. Users
- Compliance analyst: triages the wave.
- Document owner, reviewer, approver: act on findings. Routing comes from `company.company_documents`.
- Demo audience: an energy-regulation domain expert.

## 5. Features
### Must (v1)
| ID | Feature | One-line definition |
|---|---|---|
| M1 | Impact engine | 5-stage pipeline: delta → characterize → candidates → judge → ledger (`engine_spec.md`) |
| M2 | Signal funnel | Raw changes → after normalization → in RPL footprint → obligation changed → findings; also clauses cleared |
| M3 | Document board | One card per document: flagged/cleared, verdict counts, owner, reason when cleared |
| M4 | Clause evidence card | S1 vs S2 word diff, clause text with quote highlighted, verdict, required change, match path, rationale, also-affected, route |
| M5 | Ledger | Every change has a disposition. Every cleared clause has a reason (e.g. "cosmetic readoption stamp") |
| M6 | Scorecard | `backend/app/company/corpus/eval/scoring.py` metrics for the real wave plus the S1 baseline result |
| M7 | What-if mode | The user edits or repeals a cited S1 section (or picks a preset); the same engine runs; results are labeled SIMULATED |

### Should (build after Must; cuttable)
| ID | Feature | One-line definition |
|---|---|---|
| S1 | Regulatory radar | Substantive changes with no RPL citation, screened against `company_attributes`: possibly applicable / screened out (reason) / unclear |
| S2 | Review actions | Accept or reject a finding with a note; document shows reviewed count |

## 6. Verdict vocabulary (UI label ← `finding_type`)
| UI verdict | finding_type(s) | Meaning |
|---|---|---|
| Action required | `parameter_change`, `required_content_change`, `conflict`, `new_requirement_gap`, `stale_at_approval` | The clause now conflicts with the rule |
| Optional — rule relaxed | any of the above with `direction='relaxed'` | The clause is stricter than the law now requires |
| Update citation | `stale_citation` | The text is fine; the reference is stale (renumbered or repealed) |
| Review | `informational` with `needs_review=true` | Low confidence or unverified evidence |
| Info | `informational` | No action |
| Cleared (not a finding) | — | Candidate checked: no impact, with reason |

Severity: high = customer- or regulator-facing obligation; medium = internal process; low = informational.

## 7. Success criteria
- S1 baseline run: 0 non-informational findings.
- Real wave (`scoring.py`): false-positive rate on `must_not_flag` = 0; precision ≥ 0.80; recall ≥ 0.83; routing ≥ 0.80.
- 100% of non-informational findings have verified quotes.
- Every change record has a disposition. Every candidate is judged or has a skip reason (enforced by a ledger check).
- What-if preset results load instantly (pre-run). A custom what-if run finishes in < 120 s.
- Reruns are reproducible via the LLM cache.

## 8. Out of scope — do not build
| Item | Why |
|---|---|
| Definition-ripple matching | No `defined_terms` link to code sections; no definitions changed |
| Semantic or hybrid search candidate path | Not needed at this scale; no hybrid search exists |
| Subsection parser | Few changes; the judge sees the word diff and the clause's subsection |
| Quantified dataset impact | `datasets` is empty; no real change hits a dataset parameter |
| Compliance countdown | No effective dates; show the DIN publication date only |
| Auto-editing documents or creating new document versions | Flag-only product decision |
| Auth, multi-company, notifications | Not needed for the demo |
| Changes to existing `/regulations`, `/diff`, `/impact`, `/timeline` routes | Leave them untouched |
| Agents with tools | All work fits bounded calls with guaranteed completeness |

## 9. Glossary
- **Change record**: one S1→S2 change to one code section (or one what-if edit).
- **Footprint**: code sections or rules that RPL clauses cite (resolved citations).
- **Candidate**: a (change, clause) pair to evaluate. It carries a `match_path`.
- **Finding**: a candidate judged affected. Cleared candidates are recorded but are not findings.
- **Run**: one engine execution. `kind` ∈ `kb` (real wave), `baseline` (S1 vs S1), `whatif`.
