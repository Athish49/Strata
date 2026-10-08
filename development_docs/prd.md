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

## 3. Data reality (re-measured 2026-10-08 on real-wave run `0dcc125e-6da6-419f-beb1-8c347e4fb2d4`, via `/engine/runs/{id}`) — the design is built around this
| Fact | Value |
|---|---|
| S2 rows evaluated (IAC 1,068 + CFR 46) | 1,114 raw changes |
| By class | cosmetic 1,004; punctuation_only 1; cross_ref_only 10; substantive 63; new_section 33; repealed 3 |
| Noise (cosmetic + punctuation + cross-ref) | 1,015 (filtered by `diff_hash`/normalizer, W0 fix) |
| Changes in RPL footprint | 96 (87 cosmetic noise, **9 real**; all 9 characterized as obligation-changed) |
| Candidates | 1,234 (direct_section 865, register_hop 292, direct_rule 77, value_echo 0); 411 LLM-judged, 0 rule-judged |
| Findings | **4 action_required**, 0 review, 0 info: RPL-CMP-REG-001 (OBL-2024-0018, 170 IAC 1-6-3) and RPL-REG-CAL-2025 (3.7 / 1-6-2, EVT-2025-0044 / 1-6, EVT-2025-0045 / 1-6-5). The earlier run `05b50712-79df-4c4e-bdb3-c84f31e189ec` had the same 4 plus 3 review items |
| Documents | 2 flagged / 10 cleared; 721 clauses cleared with reasons; 12 of 12 document statuses match the expected status |
| Radar | 20 yes / 53 no / 17 unclear |
| `170 IAC 4-1-16` | cited by many clauses; its change is cosmetic, so it is cleared (0 findings) |
| New S2 sections in cited rules / repeal flips RPL cites | not re-measured here; the 3 repealed and 33 new sections produced no finding |
| CFR citations resolved at section level | historically 0, so CFR changes go to radar. Not re-verified in this pass |
| `defined_terms` linked to code sections | 0, so no definition-ripple path |
| `company.datasets` | 0 rows, so no quantified impact |
| `restates` links | 3,048, driven by citation-number noise, not used |
| Effective dates for IAC changes | none in `regulatory_actions`; only DIN publication dates in S2 text |
| LLM calls in the latest run | 0 live (all judgments served from `engine.llm_calls`, see engine_spec.md "Offline-filled judgments") |

**Implications**
1. The real wave is a **precision test**: the engine must clear every clause that cites a changed-but-cosmetic section (87 of 96 in-footprint changes are cosmetic) and flag only true impacts.
2. The real wave alone yields few clause findings (4). **What-if mode** lets the expert apply a change live and see clause-level conflicts propagate through the same engine (presets only for the demo; custom what-if is paused).
3. Most substantive changes touch no RPL citation. The **radar** screens them against the company profile; it stays Should-have.

**Scoring status (honest).** Clause-level scorecard: precision 0, recall 0, matched 0 (4 system non-info findings vs 6 expected); FP rate on negatives PASS; routing PASS (0 matches); S1 baseline PASS; and 12/12 documents' flagged/cleared status correct. The success targets in section 7 are therefore NOT met at clause level. See `scoring_diagnosis.md` for the open export-format question.

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
