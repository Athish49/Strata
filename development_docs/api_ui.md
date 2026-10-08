# Strata v1 — API & UI

> **Superseded.** The UI contract is now `ui_wiring_contract.md`; the `/engine/ui/*` and `/company/*` endpoints are the live UI API. The `/engine/*` routes below remain for runs and what-if. In the UI endpoints, quote spans are plain-text offsets into the displayed text, not diff coordinates.

## 1. API (FastAPI, prefix `/engine`, JSON, no auth)
All list endpoints take `run_id`. If it is omitted, use the latest `done` run of `kind='kb'`.

| Method & path | Returns / does |
|---|---|
| `POST /engine/runs` body `{kind:'kb'\|'baseline'}` | Starts a background run → `{run_id}` |
| `GET /engine/runs?kind=` | List of `{run_id, kind, status, started_at, finished_at, scenario_title?}` |
| `GET /engine/runs/{run_id}` | `{run, stats}` (the funnel) |
| `GET /engine/runs/{run_id}/documents` | Doc rollups joined with title, vertical, owner name, approved_date |
| `GET /engine/runs/{run_id}/documents/{doc_id}` | `{doc, rollup, groups:{action_required[], optional_relaxed[], update_citation[], review[], info[]}, cleared[]}`. Finding items: `{finding_id, clause_id, heading_path, citation, finding_type, verdict, severity, short_rationale}`. Cleared items: `{clause_id, citation, skip_reason\|rationale, change_class}` |
| `GET /engine/findings/{finding_id}` | Evidence card (§1.1) |
| `GET /engine/runs/{run_id}/ledger?in_footprint=&change_class=&disposition=` | Change records: `{change_id, citation, heading, change_class, in_footprint, cited_clause_count, disposition, disposition_reason, published_date, n_findings, n_cleared}` |
| `GET /engine/changes/{change_id}` | Change detail: diff_segments, summary, value_changes, candidates (with paths and outcomes) |
| `GET /engine/runs/{run_id}/scorecard` | `engine.score_reports.metrics`, plus the latest baseline run's metrics |
| `GET /engine/runs/{run_id}/radar?applicable=` | Radar items joined with change citation, heading, agency |
| `GET /engine/whatif/sections` | `{citation, s1_section_id, heading, cited_clause_count}` |
| `GET /engine/whatif/sections/{s1_section_id}` | `{citation, heading, s1_text}` |
| `GET /engine/whatif/scenarios` | Scenarios with `last_run_id` and status |
| `POST /engine/whatif/scenarios` body `{s1_section_id, edit_kind, edited_text?, title}` | Creates a scenario and starts its run → `{scenario_id, run_id}` |
| `POST /engine/whatif/scenarios/{id}/run` | Re-runs → `{run_id}` |
| `POST /engine/findings/{finding_id}/reviews` body `{action, note?, person_id}` | Stores a review. `reject` requires `note` (422 otherwise) |
| `GET /engine/people` | `{person_id, name, title}` |

Rules: return 404 for unknown ids and 409 when a run is still `running` for result endpoints. Never expose `engine.llm_calls`.

### 1.1 Evidence card payload (`GET /engine/findings/{id}`)
```json
{
  "finding": {"finding_id","clause_id","doc_id","citation","finding_type","verdict","severity",
              "needs_review","required_change","rationale","confidence","decided_by","match_path",
              "quotes_verified","route":{"owner":{..},"reviewer":{..},"approver":{..}|null},
              "reviews":[...]},
  "change": {"change_id","citation","heading","change_class","summary","direction","value_changes",
             "published_date","date_basis","din","amendment_source","origin","diff_segments",
             "s1_quote_span":[start,end]|null, "s2_quote_span":[start,end]|null},
  "clause": {"clause_id","doc_title","heading_path","text_raw","quote_span":[start,end]|null},
  "path": [{"path","via_clause_id","link_type","value"}],
  "also_affected": [{"finding_id","doc_id","clause_id","verdict"}],
  "propagated_from": {"finding_id","clause_id"} | null
}
```
Quote spans are computed server-side with `quotes.locate_quote`: on `s*_text_norm` for the change, and on `text_raw` for the clause.

## 2. UI (Next.js App Router + TypeScript + Tailwind, `frontend/`)
- Global layout: a header showing Strata, the run selector (kb wave / baseline / what-if runs), and nav: Overview · Documents · Ledger · Radar · What-if.
- Every page reads `?run=`.
- What-if runs show a persistent amber **SIMULATED — not real regulation** banner.
- Plain, dense, professional styling. No charts library is needed; draw the funnel with styled divs.

| Page | Route | Content |
|---|---|---|
| Overview | `/` | (1) **Funnel**: raw changes → after normalization (noise removed, by class) → in RPL footprint → obligation changed → findings; plus "N clauses checked and cleared". (2) Tiles: docs flagged/cleared, findings by verdict. (3) Scorecard tile: precision, recall, FP rate, routing, S1 baseline = 0 ✓ (kb runs only) |
| Documents | `/documents` | One card per doc: title, vertical, owner, status pill (flagged red / cleared green), verdict counts, cleared reason (one line) |
| Document | `/documents/[docId]` | Sections in order: Action required · Optional (relaxed) · Update citation · Review · Info · **Cleared (collapsed)**. A row is clause_id, heading path, citation, one-line rationale; click → finding |
| Finding | `/findings/[id]` | **Evidence card**. Left: change header (citation, heading, published date + basis, summary, direction) and the word diff (red delete / green insert; collapse equal runs > 300 chars), with the S1/S2 quotes highlighted. Right: doc title, clause heading path, clause text with the quote highlighted. Bottom: verdict pill, required change (`from → to`), rationale, match path ("Why this clause": e.g. "Cites 170 IAC x-y-z" / "Linked from register row … via references_obligation"), also-affected list, route (owner → reviewer → approver; "two-signature document" when the approver is null), review buttons (S2) |
| Ledger | `/ledger` | Change table with filters (class, in footprint, disposition). Row expands to the change detail: diff and candidates with outcome and reason. This is the proof screen: e.g. "cosmetic: readoption stamp — 94 clauses cleared" |
| Radar | `/radar` | Three groups: Possibly applicable (attribute basis chips, reason, rule covered by docs) · Screened out (reason) · Unclear (collapsed) |
| What-if | `/whatif` | Left: presets list (run instantly) and a section picker. Right: an editor with the S1 text in a textarea (or a "Repeal section" toggle) and a **Run impact** button → polls the run → links to Overview/Documents with `?run=` |

UI rules:
- Never show raw JSON.
- Show `quotes_verified=false` as "evidence unverified — review".
- Every finding links back to its change in the Ledger.
