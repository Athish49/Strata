# Strata UI wiring contract (frontend `StrataApi` <-> FastAPI backend)

Status: authoritative for the wiring agents. Verified against the live backend (`:8000`, read-only GETs) and read-only SQL on 2026-10-07/08.
Ignore `development_docs/api_ui.md`. Mock fixtures are NEVER mixed with live data: in `http` mode no fixture is imported.

Contents: 0 Ground truth | 1 Lead pre-work | 2 Global conventions | 3 Engine methods | 4 KB methods | 5 Company methods | 6 Decisions on known mismatches | 7 Backend module A (engine + kb) | 8 Backend module B (company) | 9 Frontend file split | 10 Risks / open questions | 11 Verification checklist

---

## 0. Ground truth

**Database (from `backend/.env` `DATABASE_URL`, host only):** `ep-fancy-river-ar47ie12-pooler.c-4.us-west-2.aws.neon.tech`, database `neondb`, Neon serverless Postgres 18 (pooled endpoint, AWS us-west-2). It is **remote, not local**. Nothing in the repo marks it as a dev branch, and `render.yaml`'s deployed `strata-backend` service reads the same `DATABASE_URL` variable from a dashboard secret. Treat it as **shared / possibly production**. It holds test data (24 engine runs, many repeated what-if runs, 4 orphan what-if runs whose scenario row was deleted). `.env` also holds a live LLM key, so every engine run costs money.

**Live data snapshot (what the UI will show):**

| Domain | Fact |
|---|---|
| Company | `company_id='rpl'` (= `engine_settings.ENGINE_COMPANY_ID`), name "Rockridge Power & Light Company". **12 documents** (not 39), 27 people (P01..P27), 22 `company_attributes` rows, 2334 clauses. |
| Document metadata | `company_documents.vertical`, `doc_class`, `review_cycle` and `document_versions.next_review` are **NULL for all 12 docs**. The real values are in the static file `backend/app/company/corpus/_global/document_register.csv` (columns `vertical`, `review_cycle`, `next_review_date`). Only 5 of the 14 verticals have docs live: compliance-legal (3), policy-governance (5), operations-processes (2), environmental-esg (1), workforce-hr (1). **9 verticals are empty live and stay empty. Never pad with samples.** |
| Runs | 24 rows in `engine.runs`: kb 5 (all `done`), baseline 2 (`done`), whatif 17 (16 `done`, 1 `failed`). Statuses in the DB CHECK: `running`, `done`, `failed` (nothing else; there is no `queued`). |
| Latest done kb run | `05b50712-79df-4c4e-bdb3-c84f31e189ec`: 1114 changes (1015 noise), 96 in footprint, 9 characterized, 1234 candidates, 7 findings (4 `action_required`, 3 `review`), 2 docs flagged / 10 cleared, radar 20 yes / 53 no / 17 unclear. Its scorecard reads precision 0 / recall 0 / overall FAIL: **that is real data, not a wiring bug.** |
| What-if | 4 presets (`is_preset=true`, all with a `done` `last_run_id`): "170 IAC 4-1-13: day 17->26", "170 IAC 4-1-16: repeal section", "170 IAC 1-6-1: day 30->45", "170 IAC 16-1-5: day 7->10". |
| KB | `agencies`: epa, ferc, idem, idol (610), ifpbsc (675), iurc. `code_sections` 3522 latest rows (2 snapshots per source_system: iac 2024-12-31 / 2025-12-31, cfr 2025-01-02 / 2026-10-02). `regulatory_actions` 1206 rows. |

**ID formats (verified end to end):**

| Id | Format | Lines up with |
|---|---|---|
| run_id, change_id, candidate_id, finding_id, scenario_id, review_id | UUID string (lowercase, hyphenated) | `change_records.change_id` = `doc_rollups.changes_considered[].change_id` = `radar_items.change_id` = matrix cell `change_id`. `candidates.finding_id` joins `findings.candidate_id`. |
| doc_id | text, e.g. `RPL-CS-PRO-004` | identical in `company_documents`, `clauses.doc_id`, `candidates.doc_id`, `findings.doc_id`, `doc_rollups.doc_id` (12 = 12). |
| clause_id | text `"<doc_id>:<local>"`, e.g. `RPL-CS-PRO-004:8.2`, `RPL-CMP-REG-001:OBL-2024-0018`. Unique per document. | 1234/1234 candidate clause_ids found in `company.clauses` (same `clause_pk`). |
| person_id | `"P01".."P27"` | `findings.route_owner/reviewer/approver`, `company_documents.owner_id/...`, `finding_reviews.person_id`. |
| agency_id / slug | lowercase text `iurc ferc epa idem idol ifpbsc` | `agencies.agency_id` = `code_sections.agency_id` = `regulatory_actions.agency`. **Use agency_id as the slug.** |
| citation | text with spaces, e.g. `170 IAC 4-1-16`, `18 CFR 35.19`. `source_system` for sections: `iac` or `cfr`. | URL-encode each path segment (`encodeURIComponent`); never split on `/`. |
| Action `source_system` | `federal_register`, `iurc_gaos`, `iurc_investigations`, `iurc_rulemakings`, `idem_rulemakings` | equals the frontend `stream`. |

Frontend mock ids (`run_kb_real`, `chg-...`, `f_a_001`, `scn_preset_a`) are mock-only. UI code must treat all ids as opaque strings.

---

## 1. Lead pre-work (BEFORE downstream agents start)

These are edits to `client.ts`, `mock/*`, `queries.ts`, `schemas/*`, `lib/*`. Downstream agents may rely on them being done.

### 1.1 Exact signature changes

```ts
// client.ts (EngineApi)
getScore(run_id: string): Promise<ScoreReport | null>;                       // was getScore()
submitReview(finding_id: string, decision: "accept" | "reject", note?: string, person_id?: string): Promise<Finding>; // 4th arg optional, non-breaking
listEditableSections(): Promise<EditableSection[]>;                           // NEW: what-if section picker
getSectionS1Text(source_system: string, citation: string): Promise<SectionS1Text | null>; // NEW: editor text must be the S1 text
```
```ts
// schemas/engine.ts additions
export const editableSectionSchema = z.object({
  citation: z.string(), source_system: sourceSystemSchema, heading: z.string(), cited_clause_count: z.number(),
});
export const sectionS1TextSchema = z.object({ citation: z.string(), heading: z.string(), s1_text: z.string() });
```
```ts
// queries.ts
qk.score(runId)              // was qk.score()
useScore(runId: Nullable<string>)   // enabled: !!runId
useEditableSections()        // qk.editableSections()
useSectionS1Text(ss, citation)  // qk.sectionS1Text(ss, citation)
// useSubmitReview: add optional personId to the mutation variables; pass through.
```
Mock must implement the new/changed methods (mock `getScore(run_id)` returns the fixture for any non-whatif run id and `null` for whatif; mock `listEditableSections` = the cited sections from fixtures with `cited_clause_count`; mock `getSectionS1Text` = `fixtures().versions["iac|<cit>"][0].text`).

`saveScenario` / `startWhatIf` / `listScenarios` signatures are unchanged (semantics in 3.12-3.14).

### 1.2 Schema widenings (only widen; all existing fixtures stay valid)

One bad row fails the whole `z.array(...).parse`, so these are mandatory. Reasons are verified against live data.

| # | File / field | Change | Why (live data) |
|---|---|---|---|
| S1 | `common.ts` `directionSchema` | add `"mixed"`; add `mixed: "Mixed"` to `DIRECTION_LABELS` in `lib/labels.ts` | 34 of 44 directional changes are `mixed`. Cannot be mapped honestly to another value. |
| S2 | `engine.ts` `changeRecordSchema.published_date`, `.date_basis` -> `.nullable()` | | 587 of 1114 kb changes and ALL what-if changes have no publication date. |
| S3 | `findingSchema.rule_published_date` -> `isoDate.nullable()` | | same (what-if). |
| S4 | `findingSchema.confidence` -> `z.number().min(0).max(1).nullable()`; callers of `decidedByLabel(decided_by, confidence ?? undefined)` | | rule decisions and "unavailable" AI outcomes carry NULL confidence. |
| S5 | `changeRecordSchema.disposition`, `.disposition_reason` -> `z.string().nullable()` | | older runs have NULL disposition. |
| S6 | `runSchema` add `error: z.string().nullable().optional()` | | failed runs carry an error string; UI may show it. |
| S7 | `scoreReportSchema.baseline_findings` -> `z.number().nullable()` | | no baseline score may exist; `null` = "baseline not run". |
| S8 | `kb.ts` `regulatoryActionSchema.date_published` -> `isoDate.nullable()` | | GAO/investigation rows have no date (list is also ordered date DESC with NULLs first). |
| S9 | `quotes` stay `{text:string, span?}`; **empty string `""` = absent quote** | (no schema change) | 887 `review` findings have no s1/s2 quote; new sections have no S1. UI must render "no quote" for `text === ""`. |
| S10 | `required_change` stays `{from_text,to_text}`; **both `""` = absent** | (no schema change) | 887 findings have NULL `required_change`. `lib/sentences.ts` already falls back to `rationale` when from/to are empty. |

Backend maps (no enum change needed): `direction removed_requirement` -> `removed`; `unit_kind other` -> `section` (1 row: `RPL-TAR-GRR-012:S50.IDX`); relationship types outside {related_to, supersedes, corrects} -> `related_to` (live data has only those 3; guard anyway).

### 1.3 Run context (important)

`lib/run-context.tsx` has `DEFAULT_RUN_ID = "run_kb_real"`: live this would 404. **Do not fix this with an alias in the adapter**: `useSubmitReview` invalidates `["engine", f.run_id, ...]` using the finding's real UUID, so any query keyed by an alias never refreshes. Required change: `RunProvider` resolves the default from the runs list:

```ts
const { data: runs } = useRuns();
const latestKb = runs?.filter(r => r.kind === "kb" && r.status === "succeeded")
                      .sort((a,b) => b.started_at.localeCompare(a.started_at))[0]?.run_id;
const runId = param || latestKb || null;   // null while loading: queries are `enabled: !!runId`
```
(`DEFAULT_RUN_ID` constant can stay for mock mode only.) `RunSelector` marks the current run with `runId ?? run?.run_id`; with a real id this works unchanged. The `/engine/ui/runs` list always contains the latest done kb run (see 3.1), and is sorted `started_at` desc.

### 1.4 Mock parity for payload shape (recommended)

- `mock.listChanges(run)` and `mock.getMatrix().changes` must return **light rows** (`diff_segments: []`, `s1_text: ""`, `s2_text: ""`), and full rows only from `getChange`. Otherwise page agents will build on list-level diffs that the live API does not provide.
- `mock.listSections` must return `body_text: ""` in list rows, full text only from `getSection`.

### 1.5 Environment and wiring

- `client.ts`: `export const api: StrataApi = process.env.NEXT_PUBLIC_STRATA_DATA === "http" ? httpApi : mockApi;` (default `mock`). `NEXT_PUBLIC_STRATA_API_URL` (default `http://localhost:8000`). CORS: backend default `ENGINE_CORS_ORIGINS=*` allows `:3000`.
- Backend registration (lead): add `"routes_ui_runs", "routes_ui_results", "routes_ui_kb"` to the `for _name in (...)` list at the bottom of `backend/app/api/engine/routes.py`; add `from app.api.company.routes import router as company_router; app.include_router(company_router)` to `backend/app/main.py`; optionally `app.add_middleware(GZipMiddleware, minimum_size=1000)` (payloads are text-heavy).

---

## 2. Global conventions (all adapters and new endpoints)

| Topic | Rule |
|---|---|
| Base URL | `${NEXT_PUBLIC_STRATA_API_URL}`. All requests GET except the two writes in 3.13/3.15. No auth. |
| zod | Every response is `schema.parse()`d in the shared helper. New backend endpoints return **exactly** the zod JSON shape (extra keys are tolerated and stripped by zod). |
| 404 | single get -> `null`; list under a missing run -> `[]`; matrix -> `{docs:[],changes:[],cells:[]}`. |
| 409 | "run is still running" (all result endpoints, existing and new). Adapter returns the **empty result** (`[]` / `null` / empty matrix), same as the mock does for a running custom run. The UI polls `getRun` and invalidates results when it flips. New `/engine/ui/*` result endpoints also return 409 while `running`, EXCEPT `GET /engine/ui/runs`, `GET /engine/ui/runs/{id}`, scenarios and whatif-section endpoints. |
| 422/5xx | throw `ApiError(status, detail)`; React Query surfaces it to `ErrorState`. |
| Dates | `YYYY-MM-DD` for dates, ISO-8601 with `Z` for timestamps (already what FastAPI emits). |
| Numbers | Postgres `numeric` (confidence, value_num) must be cast to `float` backend-side (existing code returns strings otherwise). |
| Light vs full | List endpoints for changes and sections are **light** (no texts). Details are full. |
| Ordering | Runs: `started_at` desc. Documents: `doc_id`. Rollups: flagged first, then `doc_id`. Findings: severity high->low, then `doc_id`, `clause_id`. Changes: `in_footprint` desc, real classes first, `citation`. Candidates: `doc_id`, `clause_id`, change `citation`. |
| Heading cleaning | `code_sections.heading` carries the citation as a prefix (4250/4273 IAC rows; CFR rows start `§ 35.19 `). One rule everywhere (`clean_heading(citation, heading)`): strip leading `citation` (case-insensitive) or a leading `§ <token>`, then trim spaces/`-:.`; if the result is empty keep the original. Backend uses it in all `/engine/ui/*` payloads; `http/kb.ts` uses the identical rule (port in `http/shared.ts`) for the existing `/actions`-independent paths only if it ever shows raw headings (KB sections come from new endpoints, so backend cleans them). |

---

## 3. EngineApi (file `frontend/lib/api/http/engine.ts`; backend module A)

All new paths are mounted under `/engine` by `routes.py`, so a router file declares `@router.get("/ui/...")`. `{rid}` accepts a run UUID only (the frontend resolves "latest", see 1.3). Shared backend helpers: import `_all, _one, _j, _uuid, _get_run, _span` from `app.api.engine.routes` (as `routes_radar.py` does); `locate_quote` from `app.engine.quotes`.

| Method | Backend | New? |
|---|---|---|
| listRuns | `GET /engine/ui/runs?collapse=true` | NEW |
| getRun | `GET /engine/ui/runs/{rid}` | NEW |
| listChanges | `GET /engine/ui/runs/{rid}/changes` (light) | NEW |
| getChange | `GET /engine/ui/runs/{rid}/changes/{change_id}` (full) | NEW |
| listCandidates | `GET /engine/ui/runs/{rid}/candidates?change_id=&doc_id=` | NEW |
| listFindings | `GET /engine/ui/runs/{rid}/findings?doc_id=&change_id=` | NEW |
| getFinding | `GET /engine/ui/findings/{finding_id}` | NEW |
| listRollups | `GET /engine/ui/runs/{rid}/rollups` | NEW (trivial map of `/engine/runs/{rid}/documents`) |
| getReader | composite: company `getDocument` + `listClauses` + `GET /engine/ui/runs/{rid}/documents/{doc_id}/annotations` | annotations NEW |
| getMatrix | composite: company `listDocuments` (monitored, sorted by doc_id) + `GET /engine/ui/runs/{rid}/matrix?include_noise=` returning `{changes, cells}` | NEW |
| listRadar | `GET /engine/ui/runs/{rid}/radar` | NEW (existing `/runs/{rid}/radar` has wrong shape) |
| listScenarios | `GET /engine/ui/scenarios` (+ in-memory drafts appended by adapter) | NEW |
| saveScenario | adapter-local draft, no request | none |
| startWhatIf | existing `POST /engine/whatif/scenarios` or `POST /engine/whatif/scenarios/{id}/run`, then `GET /engine/ui/runs/{id}` | existing POST |
| getScore | `GET /engine/ui/runs/{rid}/score` (200 with JSON `null` when unscored) | NEW |
| submitReview | existing `POST /engine/findings/{id}/reviews`, then `GET /engine/ui/findings/{id}` | existing POST |
| listEditableSections | `GET /engine/ui/whatif/sections` | NEW |
| getSectionS1Text | `GET /engine/ui/whatif/sections/{s1_section_id}` (id looked up from the list by citation) | NEW |

### 3.1 listRuns / getRun -> `Run`

`GET /engine/ui/runs` returns `Run[]` (stats included: it is the `engine.runs.stats` column, so no N+1). `collapse=true` (default) returns: the latest `done` kb run plus any kb run that is `running` or `failed` and newer; the latest `done` baseline run; every what-if run that is some scenario's `last_run_id` or is `running`; sorted `started_at` desc. `collapse=false` returns all 24. (This hides 4 identical-label kb duplicates and 4 orphan what-ifs with NULL titles.) `GET /engine/ui/runs/{rid}` returns one `Run` (404 unknown/invalid uuid; does NOT 409).

| Run field | Source | Tag |
|---|---|---|
| run_id | `runs.run_id` (uuid str) | DIRECT |
| kind | `runs.kind` (`kb`/`baseline`/`whatif`) | DIRECT |
| title | kb: `"Real wave · S1→S2"`; baseline: `"Baseline · S1 vs S1"`; whatif: `whatif_scenarios.title` via `runs.scenario_id`, fallback `"What-if scenario"` when the scenario row is gone | DERIVED backend |
| status | `done`->`succeeded`; `running`->`running`; `failed`->`failed`. `queued` is never produced. Stale guard: `running` with `started_at` older than `STALE_RUN_MINUTES=30` and no `finished_at` -> `failed` (display only, no write) | DERIVED backend |
| started_at / finished_at | `runs.started_at` / `finished_at` | DIRECT |
| scenario_id | `runs.scenario_id` or null | DIRECT |
| error | `runs.error` | DIRECT (S6) |
| progress | `null` unless running; see 3.1.1 | DERIVED backend, best effort |
| stats | see table below; `runs.stats` is NULL while running and partial/missing keys in old runs -> every key defaults to 0/`{}` | DERIVED backend |

`stats` mapping (`s` = `runs.stats`, `bc` = `s.by_class`):

| RunStats key | Rule |
|---|---|
| changes_raw | `s.raw_changed` |
| by_class | `s.by_class` |
| substantive | **sum of REAL classes** in `bc` (substantive + repealed + renumbered + new_section) = `changes_raw - noise` (latest kb: 99, NOT the backend's `s.substantive` = 63 which is only the class count). Invariant: `changes_raw == substantive + noise`. |
| noise | sum of `cosmetic, metadata_only, punctuation_only, cross_ref_only` in `bc` |
| in_footprint | **sum of the values** of `s.in_footprint` (a dict class->n; includes noise in footprint; latest kb = 96) |
| obligation_changed | `s.obligation_changed` |
| candidates_by_path | `s.candidates` (fill the 4 paths with 0) |
| findings_by_verdict | `s.findings` (fill the 5 verdicts with 0) |
| clauses_cleared | `s.clauses_cleared` |
| docs_flagged / docs_cleared | `s.docs_flagged` / `s.docs_cleared` |
| radar | `{applicable: s.radar.yes, screened_out: s.radar.no, unclear: s.radar.unclear}` (zeros if the run had no radar stage) |
| decided_by | `{rule: s.judged_rule, ai: s.judged_llm}` |
| llm_calls | `s.llm_calls` (can be 0 on a fully cached re-run even though `judged_llm`=411; show as is) |

#### 3.1.1 progress (running runs)

The backend stores NO progress. Honest fallback, derived from rows the pipeline has written so far (counts over `engine.*` for the run; first matching rule wins), stage names = zod `stage`:
1. `doc_rollups` exist -> `ledger`, done = rollup rows, total = number of company documents, message `"{done} of {total} documents rolled up"`.
2. any `candidates` with `skip_reason IS NULL AND (judged_by IS NOT NULL OR affected IS NOT NULL)` or any findings -> `judge`, total = candidates with `skip_reason IS NULL`, done = those with `judged_by IS NOT NULL`, message `"{done} of {total} candidate clauses judged"`.
3. candidates with `skip_reason IS NULL` exist -> `judge`, done 0.
4. `change_records` exist and some have `obligation_changed IS NOT NULL` -> `candidates`, done = total = in-footprint substantive changes, message `"... changes matched against clauses"`.
5. `change_records` exist -> `characterize`, total = changes with `change_class='substantive' AND in_footprint`, done = those with `obligation_changed IS NOT NULL`, message `"... changes characterized"`.
6. otherwise -> `delta`, done 0, total 0, message `"Comparing snapshots"`.
It is coarse; if anything throws return `progress: null`. The UI must render an indeterminate state when `progress` is null or `total === 0`. Never synthesize progress from elapsed time in the frontend.

### 3.2 listChanges / getChange -> `ChangeRecord`

List is light (`diff_segments: []`, `s1_text: ""`, `s2_text: ""`); detail is full. Both are one row of `engine.change_records` `ch` joined `LEFT JOIN public.code_sections cs ON cs.id = COALESCE(ch.s2_section_id, ch.s1_section_id)` and `runs.snapshots`.

| Field | Source | Tag |
|---|---|---|
| change_id | `ch.change_id` | DIRECT |
| citation, source_system, rule_key, change_class, in_footprint, cited_clause_count, din, published_date, date_basis | same-named columns (nullable ones stay null: S2) | DIRECT |
| heading | `clean_heading(citation, ch.heading)` (`""` if null) | DERIVED backend |
| agency_id | `cs.agency_id` (all 3522 rows non-null) | DERIVED backend (join) |
| title_number | `cs.title_number`; fallback leading integer of `citation` | DERIVED backend |
| diff_segments | list: `[]`; detail: `ch.diff_segments`; if NULL and `s2_text_norm` present (new_section) -> `[{"op":"insert","text":s2}]`; if NULL and only s1 (repealed w/o diff) -> `[{"op":"delete","text":s1}]`; else `[]` | DIRECT / DERIVED |
| s1_text, s2_text | list `""`; detail `ch.s1_text_norm` / `ch.s2_text_norm` (`""` if null). Quote spans in findings are expressed in THESE strings. | DIRECT |
| s1_snapshot, s2_snapshot | `snapshot_date` of the S1/S2 `code_sections` row if present, else `runs.snapshots[source_system].s1/.s2` (what-if: s2_section_id is NULL) | DERIVED backend |
| characterization | `null` if `ch.direction IS NULL`; else `{obligation_changed: coalesce(ch.obligation_changed,false), direction: map(ch.direction), summary: coalesce(ch.summary,""), value_changes: [{label: vc.subject, old: vc.old_value_text, new: vc.new_value_text, unit: vc.unit}]}`. Direction map: identity, except `removed_requirement`->`removed` (and `mixed` kept, S1). | DERIVED backend |
| disposition, disposition_reason | columns, nullable (S5) | DIRECT |
| placeholder | omit | - |

Missing today: nothing; everything is derivable. Latest kb: only 9 of 96 in-footprint changes have a characterization; others are `null` ("honest null").

### 3.3 listCandidates -> `Candidate`

Source `engine.candidates k` + `findings f ON f.candidate_id=k.candidate_id` + `change_records` + `clauses`.

| Field | Source | Tag |
|---|---|---|
| candidate_id, run_id, change_id, clause_id, doc_id, match_path | columns | DIRECT |
| outcome | `"affected"` iff a finding row exists for the candidate, else `"cleared"` (live: affected=true <=> finding; verified 4+3 vs 1227 cleared) | DERIVED backend |
| skip_reason | `k.skip_reason`, but **`noise:*` -> null** (otherwise `clearedReason()` would print "noise:cosmetic"; the rationale carries the text) | DERIVED backend |
| rationale | `k.rationale` | DIRECT |
| finding_id | `f.finding_id` or null | DIRECT |
| path_detail | see 3.3.1 | DERIVED backend |

#### 3.3.1 path_detail builder (shared by candidates and findings)

Backend `path_detail` is a list of alternative `{path, value, link_type, via_clause_id}` steps, frontend wants an ordered chain `PathNode{kind,ref,label}`. Use the first step whose `path == match_path` (fallback first step). Chain:
- `direct_section`, `value_echo`: `[section(ref=change.citation, label="{citation} · {clean heading}"), clause]`
- `direct_rule`: `[section, rule(ref=step.value, label=step.value), clause]`
- `register_hop`: `[section, via, clause]` where `via.ref = step.via_clause_id`, `via.kind` by the via clause's `unit_kind` (`register_row`->`register_row`, `form_field`->`form_field`, `tariff_subrule`->`tariff_rule`, else `clause`), `via.label = "{via doc_id} · {via local id}"`.
- `clause` node: `ref = clause_id`, `label = "{doc_id} · {last heading_path element}"`.
Extra steps beyond the first (33 register_hop rows have 2) are dropped. Verified distribution: via clause unit_kind = section 292, register_row 49, tariff_subrule 8.

### 3.4 listFindings / getFinding -> `Finding`

`getFinding` has no run_id: `GET /engine/ui/findings/{finding_id}` (404 unknown; 409 if its run is running -> adapter returns null).

| Field | Source | Tag |
|---|---|---|
| finding_id, run_id, change_id, clause_id, doc_id, citation, finding_type, verdict, severity, quotes_verified, rationale, match_path, propagated_from | `engine.findings` columns (uuids as str; `propagated_from` uuid or null) | DIRECT |
| confidence | `float(f.confidence)` or null (S4) | DIRECT |
| decided_by | `llm`->`ai`, `rule`->`rule` | DERIVED backend |
| required_change | `{from_text, to_text}` from `f.required_change`; NULL/`{}` -> both `""` | DERIVED backend |
| quotes | `{s1,s2,clause}` each `{text: str or "", span}`. Spans are **plain-text offsets**: s1 into `change.s1_text_norm`, s2 into `change.s2_text_norm`, clause into `clauses.text_raw`, via `locate_quote(quote, text)`; `null` when quote absent or not found. (Not the diff-token coordinates `_diff_span` that `/engine/findings/{id}` returns.) | DERIVED backend |
| path_detail | 3.3.1 | DERIVED backend |
| stale_at_approval | `finding_type == 'stale_at_approval'` (assigned by the engine when published_date <= approved_date) | DERIVED backend |
| doc_approved_date | `document_versions.approved_date` of `company_documents.current_version_id` | DERIVED backend |
| rule_published_date | `change_records.published_date` (nullable, S3) | DERIVED backend |
| route | `{owner, reviewer, approver}` full `Person` objects (`person_id,name,title,department,reports_to_id`) from `company.people` for `route_owner/_reviewer/_approver`; approver `null` for two-signature docs (PRO-007, PRO-011) by design | DERIVED backend |
| reviews | `finding_reviews` -> `[{decision: action, note, at: created_at}]` ordered by `created_at` (person_id not in the zod; kept server-side) | DERIVED backend |

Notes: `needs_review` is not in the zod (ignored). 887 of 901 historic `review` findings are `informational` with null quotes/required_change/confidence; the UI shows them from `rationale`.

### 3.5 listRollups -> `DocRollup`

Source `engine.doc_rollups` (ordering in section 2). `run_id` str; `status` direct; `counts_by_verdict` = `counts` minus `cleared_clauses`, filled with the 5 verdict keys; `changes_considered` = `len(changes_considered)`; `considered_by_class` = count of `changes_considered[].change_class`; `cleared_reason` = `reason`. Runs without rollups (old kb/baseline, failed) return `[]` -> status.ts shows "No cited section changed".

### 3.6 getReader -> `Reader` (adapter composes)

`doc` = company `GET /company/documents/{doc_id}` (null -> return null); `clauses` = company `GET /company/documents/{doc_id}/clauses`; `annotations` = `GET /engine/ui/runs/{rid}/documents/{doc_id}/annotations` -> `Annotation[]`:
- one `kind:"finding"` per finding of the doc: `clause_id, verdict, finding_id, change_id, citation = f.citation, quote_span = clause span (text_raw offsets), reason = f.rationale`.
- one `kind:"cleared"` per cleared candidate of the doc (no finding): `verdict:null, finding_id:null, change_id, citation = change.citation, quote_span:null`, `reason = k.rationale` if non-empty, else `"Checked: no impact — {class words} change to {citation}."` (class words: cosmetic / metadata-only / punctuation-only / cross-reference-only / else lowercase class), else `"Checked: no impact."`.
A clause cleared against N changes yields N annotations (expected; <= 1234 rows/run). Findings can sit on clauses of non-current clause sets (register rows), which is why listClauses must return all sets (5.2).

### 3.7 getMatrix -> `Matrix` (adapter composes)

Backend `GET /engine/ui/runs/{rid}/matrix?include_noise=false` -> `{changes: ChangeRecord[] (LIGHT), cells: MatrixCell[]}`. `changes` = `in_footprint` changes, excluding noise classes unless `include_noise`. `cells`: group the run's candidates by `(doc_id, change_id)` restricted to those changes: `n_findings` = candidates with a finding, `n_cleared` = candidates without, `worst_verdict` = best-ranked verdict in order `action_required, optional_relaxed, update_citation, review, info`, else `"cleared"`. Adapter: `docs` = company `listDocuments()` filtered `monitored`, sorted by `doc_id` (mock parity: all monitored docs, not just docs with cells).

### 3.8 listRadar -> `RadarItem`

Source `radar_items r JOIN change_records ch` + `code_sections cs` (agency). Order: yes, unclear, no, then citation.

| Field | Source | Tag |
|---|---|---|
| radar_id | `change_id` (PK is `(run_id, change_id)`) | DERIVED |
| run_id, change_id | columns | DIRECT |
| citation | `ch.citation`; heading `clean_heading(...)` | DERIVED |
| agency_id | `cs.agency_id` | DERIVED (join) |
| applicable | `r.applicable` | DIRECT |
| attribute_basis | backend stores only KEYS (`text[]`); backend joins `company.company_attributes` (run's `company_id`) -> `[{key, value}]`, value = `value_bool` if not null, else `value_num` (int if integral, else float), else `value_text`; key missing in the profile -> value `"not in profile"` | DERIVED backend |
| affected_activity, reason | columns, null -> `""` | DIRECT |
| quote | `r.quote_s2` null -> `""` (42 of 90 null) | DIRECT |
| docs_covering_same_rule | `r.rule_covered_by_docs` (empty in the latest run) | DIRECT |

### 3.9 listScenarios -> `Scenario`

`GET /engine/ui/scenarios`: `SELECT scenario_id, title, citation, source_system, edit_kind, edited_text, is_preset, last_run_id FROM engine.whatif_scenarios` (order: presets first, then newest). All DIRECT (the existing `/engine/whatif/scenarios` drops `citation/source_system/edited_text` through its response_model, hence the new route). `edited_text` null for repeal. Adapter appends in-memory drafts (3.12).

### 3.10 getScore(run_id) -> `ScoreReport | null`

`GET /engine/ui/runs/{rid}/score`. Source `engine.score_reports.metrics` (own run) + latest done baseline score + run stats. `null` when the run has no score report (what-if runs are never scored; `Scorecard.metrics` null).

| Field | Source | Tag |
|---|---|---|
| precision, recall, fp_rate_must_not_flag, routing_accuracy | `metrics.*` (same keys) | DIRECT |
| targets `{precision,recall,fp_rate,routing}` | parse the first number in `metrics.targets[].target` strings ("Recall ≥ 0.83", "Precision ≥ 0.80", "FP rate on negative set = 0", "Routing accuracy ≥ 0.80"); fallback spec constants 0.80 / 0.83 / 0 / 0.80 | DERIVED backend |
| baseline_findings | `0` if latest baseline `baseline_check == "PASS"`; else non-info finding count from the latest done baseline run's `stats.findings`; `null` if no baseline exists (S7) | DERIVED backend |
| decided_by, llm_calls | the run's mapped stats (3.1) | DERIVED backend |

`metrics.per_doc`, `overall`, `recall_low/medium`, `matched` are not in the zod and are dropped. Do not massage FAIL results.

### 3.11 listEditableSections / getSectionS1Text

`GET /engine/ui/whatif/sections` -> `[{citation, source_system, heading (clean), cited_clause_count, s1_section_id}]` from `whatif.list_editable_sections` + `code_sections.source_system` (most-cited first). zod strips `s1_section_id`; the adapter keeps a `citation -> s1_section_id` map from the last list call (refetch the list if the map is empty). `GET /engine/ui/whatif/sections/{s1_section_id}` -> `{citation, heading (clean), s1_text}` from `whatif.get_section` (S1 body, NOT `/regulations/...`, which returns S2).

### 3.12 saveScenario (no request)

There is no create-without-run endpoint, and `POST /engine/whatif/scenarios` creates AND starts a billable run. So `saveScenario` is a **local draft**: validate (text_edit needs non-empty `edited_text`; citation must be in the editable sections map else throw `Error("Section is not cited by any RPL clause")`), store `{...s, scenario_id: s.scenario_id ?? "draft-"+uuid, is_preset:false, last_run_id:null}` in a module-level Map, return it. Editing a persisted (non-draft) scenario creates a new draft copy (backend has no update). Drafts vanish on reload; `listScenarios` returns backend rows then drafts.

### 3.13 startWhatIf(scenario_id) -> `Run`

| Case | Action |
|---|---|
| id is a draft | `POST /engine/whatif/scenarios {s1_section_id, edit_kind, edited_text (null for repeal), title}` -> `{scenario_id, run_id}`; delete the draft; poll (below) |
| preset (or any scenario) with `last_run_id` whose run is `succeeded` AND `is_preset` | no POST: return `GET /engine/ui/runs/{last_run_id}` (instant, free) |
| preset whose last run is missing/failed, or a persisted custom scenario | `POST /engine/whatif/scenarios/{id}/run` -> `{run_id}`; poll |
Race: the `runs` row is inserted by the background task AFTER the POST returns, so an immediate `GET /engine/ui/runs/{run_id}` is 404. Retry every 400 ms up to ~12 s until 200, then return that `Run` (status `running`; `useRunById` then polls every 2 s). Never return `queued` (the hook only polls `running`). Throw `Error("Run did not start")` on timeout. The 409 contract (section 2) applies to result endpoints while it runs.

### 3.14 submitReview -> `Finding`

1. Client check: `decision === "reject"` and blank `note` -> throw `Error("A note is required to reject")` (backend would 422).
2. Reviewer: `person_id` argument if given, else the finding's routed reviewer: `GET /engine/ui/findings/{id}` -> `route.reviewer?.person_id ?? route.owner.person_id`. (Backend requires `person_id`, validated against `company.people`.)
3. `POST /engine/findings/{finding_id}/reviews {action: decision, note, person_id}` (`accept|reject`). 404 finding/person -> throw.
4. Return `GET /engine/ui/findings/{id}` (parsed `Finding`, now including the new review). Backend allows multiple reviews per finding.

---

## 4. KbApi (file `http/kb.ts`; backend `routes_ui_kb.py` for new endpoints, existing `/actions` otherwise)

| Method | Backend | New? |
|---|---|---|
| listAgencies | `GET /engine/ui/kb/agencies` | NEW |
| getAgency(slug) | `GET /engine/ui/kb/agencies/{slug}` (404 -> null) | NEW |
| listSections | `GET /engine/ui/kb/sections?agency=&source_system=&status=&search=&page=&limit=` (limit up to 5000; light rows) | NEW |
| getSection | `GET /engine/ui/kb/sections/{source_system}/{citation:path}` | NEW |
| listActions | existing `GET /actions` + adapter map | existing |
| getAction | existing `GET /actions/{source_system}/{source_id:path}` + adapter map | existing |
| getVersionHistory | `GET /engine/ui/kb/sections/{source_system}/{citation:path}/versions` | NEW (route declared BEFORE the plain section route) |
| compare | client-side: same versions endpoint + `diffLines` (mock parity), NOT `/diff/.../compare` | none |

Why new: `/regulations?agency=` filters free-text `owning_agency` ("Air Pollution Control Division", "Indiana Utility Regulatory Commission"), so `agency=iurc` returns nothing for IAC; `/regulations` lacks body, title/part, cross refs; `/diff/{ss}/{cit}` returns diffs without S1/S2 texts.

### 4.1 Agency (`GET /engine/ui/kb/agencies`)

| Field | Source | Tag |
|---|---|---|
| agency_id, slug | `agencies.agency_id` for both. **Live 610/675 are `idol` / `ifpbsc` (non-null ids, slugs `idol`/`ifpbsc`), not `null`/`iac-610`**; `has_activity_feed=false` marks them codebook-only. | DIRECT |
| name | `agencies.name` ("Indiana Department of Labor" etc.) | DIRECT |
| level | `jurisdiction_level` | DIRECT |
| geo | `jurisdiction_geo`, federal (null) -> `"US"` | DERIVED |
| domains | `agencies.domain` | DIRECT |
| codebook_titles | iac: distinct `title_number` -> `"{t} IAC"` (idem: 326, 327); cfr: distinct `(title_number, part)` -> `"{t} CFR {part}"` (ferc: 35, 37, 38; epa: 60, 63, 72, 73) | DERIVED |
| section_count | `count(DISTINCT citation)` over the agency's `code_sections` (latest snapshot per citation; iurc 352, ferc 60, epa 225, idem 1615, idol 169, ifpbsc 1101). Not the row count. | DERIVED |
| action_count | `count(*)` of `regulatory_actions WHERE agency = agency_id` (iurc 199, idem 17, epa 920, ferc 42, idol/ifpbsc 0) | DERIVED |
| s1_snapshot / s2_snapshot | `min` / `max(snapshot_date)` over the agency's sections | DERIVED |
| last_sync_at | `max(sync_state.last_sync_at)` over the agency's section `source_system` and its action `source_system`s | DERIVED |
| has_activity_feed | `action_count > 0` | DERIVED |
| streams | distinct `regulatory_actions.source_system` for the agency | DERIVED |
Order: federal first (ferc, epa), then state (iurc, idem, idol, ifpbsc).

### 4.2 CodeSection (list light, detail full)

Latest snapshot per `(source_system, citation)` (same join as `/regulations`). `agency` filter = `code_sections.agency_id`. `search` = ILIKE on citation or heading (not body). `status` filter on `status`. `limit<=5000`.

| Field | Source | Tag |
|---|---|---|
| citation, source_system, title_number, section_number, snapshot_date, amendment_source | columns | DIRECT |
| part_or_article | `part` (iac: article, e.g. "4" for 170 IAC 4-1-16; cfr: part) | DIRECT |
| rule_key | iac: `"{title} IAC {part}-{subpart}"`; cfr: `"{title} CFR {part}"` (equals citation minus last segment; matches `change_records.rule_key`) | DERIVED backend |
| heading | `clean_heading` | DERIVED backend |
| body_text | list `""`, detail `body_text` (up to ~150k chars) | DIRECT |
| status | `approved`/`repealed` (only values in data) | DIRECT |
| owning_agency | `agency_id` (NOT the free-text `owning_agency` column) | DERIVED |
| federal_refs, iac_cross_refs | arrays, null -> `[]` | DIRECT |
Returns `Page{items,total,page,limit}`. `getSection` 404 -> null.

### 4.3 VersionEntry (`.../versions`)

All `code_sections` rows of the citation ordered by `snapshot_date`: `snapshot` = `"S1"` for the earliest snapshot date of that source_system, `"S2"` for the latest (a citation present only in S2 -> single `S2` entry); `snapshot_date`; `text` = `body_text`. `compare(ss, cit, date_a?, date_b?)`: adapter picks entries by `snapshot_date` (default first/last) and builds `LineDiff` with `diffLines` exactly like `mock/kb.ts`.

### 4.4 RegulatoryAction (existing `/actions`, adapter maps)

List query map: `agency` -> `agency` (canonical id, works); `source_system` and `stream` both -> backend `source_system` (if both given and different -> empty page); `status, action_type, date_from, date_to, search, page, limit<=200` identical. Response `{items,total,page,limit}` unchanged. Known quirk: ordered `date_published DESC` with NULLs first (IURC investigations/GAOs have no date) - unfixable without touching the existing router; accept.

| Field | Source | Tag |
|---|---|---|
| source_system, source_id, agency, action_type, status, title, source_url, rin | same | DIRECT |
| stream | = `source_system` | DERIVED frontend |
| date_published | `date_published` (nullable, S8) | DIRECT |
| abstract | detail: `abstract`; list: `""` (list omits it) | DIRECT / honest empty |
| cfr_references, legal_refs, docket_ids | null -> `[]` | DIRECT |
| din | not stored on actions -> `null` | MISSING -> honest null |
| related | detail: `related_actions_resolved[] -> {source_id: item.action.source_id, relationship_type}` with type outside {supersedes, corrects} -> `related_to`; list: `[]` | DERIVED frontend |
| placeholder | omit | - |
`getAction` 404 -> null; `source_id` may contain `/` (route is `:path`): encode segments individually.

---

## 5. CompanyApi (file `http/company.ts`; backend module B `/company`)

### 5.1 Endpoints (all GET, all return exact zod shapes)

| Method | Endpoint |
|---|---|
| listDocuments | `GET /company/documents` -> `DocumentMeta[]` (order by `doc_id`) |
| getDocument | `GET /company/documents/{doc_id}` -> `DocumentMeta` (404 -> null) |
| listClauses | `GET /company/documents/{doc_id}/clauses` -> `Clause[]` (404 unknown doc -> `[]`) |
| listPeople | `GET /company/people` -> `Person[]` (order by `person_id`) |
| getProfile | `GET /company/profile` -> `CompanyProfile` |
`company_id` = `engine_settings.ENGINE_COMPANY_ID`. Existing `/engine/people` and `/engine/runs/{id}/documents` are untouched.

### 5.2 DocumentMeta

`company.company_documents cd` + `document_versions v ON v.version_id = cd.current_version_id` + `company.people` x3 + CSV register.

| Field | Source | Tag |
|---|---|---|
| doc_id, title | `cd.doc_id`, `cd.title` | DIRECT |
| version, status, effective_date, approved_date, law_as_of | `v.*` ("Approved" for all) | DIRECT |
| next_review | `v.next_review` (NULL for all) -> CSV `next_review_date` -> null | DERIVED backend (static register fallback) |
| review_cycle | `cd.review_cycle` (NULL) -> CSV `review_cycle` -> null | DERIVED backend |
| vertical | `cd.vertical` (NULL) -> CSV `vertical` -> mapped to slug: `Compliance & Legal`->`compliance-legal`, `Policy & Governance`->`policy-governance`, `Operations & Processes`->`operations-processes`, `Environmental`->`environmental-esg`, `Workforce & Safety`->`workforce-hr` (the `backendVertical` column of `lib/verticals.ts`; keep the two in sync). Unmapped -> `"unclassified"`; `http/company.ts` drops docs whose slug is not in `VERTICAL_SLUGS` (with `console.warn`). Also returns extra `vertical_name` (ignored by zod). | DERIVED backend |
| owner, reviewer, approver | `people` rows for `owner_id/reviewer_id/approver_id` as full `Person`; approver `null` when `approver_id IS NULL` | DIRECT (join) |
| two_signature | `approver_id IS NULL` (PRO-007 and PRO-011; data_model.md says NULL is by design) | DERIVED backend |
| monitored | `v.ingest_status == 'ingested'` (true for all 12). Unmonitored sample docs do not exist live. | DERIVED backend |
| doc_type | derived from the doc_id type token (`RPL-<dept>-<TYPE>-<n>`): PRO->Procedure, PLN->Plan, PGM->Program Plan, GRR->Tariff, REG->Register, RRS->Register, CAL->Register, POL->Policy, STD->Standard, other->Document. `doc_class` is NULL in the DB. Label as derived; this is a naming heuristic, not stored metadata. | DERIVED backend |
| cited_citations | distinct `code_sections.citation` for the doc's `clause_citations` with `resolution_status IN ('resolved','resolved_rule')` via `clause_citations.code_section_id::int -> code_sections.id`, sorted (counts: CMP-REG 70, TAR 40, REG-CAL 28, DO-PLN 22, RRS 20, CS-PRO-007 13, 004 12, 011 12, MTR 9, DCC 7, SAF 4, ENV 0). NOT `regulatory_basis` (that array contains noise like "Table F F-1", "(company practice only)"). | DERIVED backend |

### 5.3 Clause

`company.clauses` selected **by `doc_id` across ALL clause sets** (not only `current_version_id`): 285 findings sit on register rows of non-current version sets (`fcfe93f5` etc.).

| Field | Source | Tag |
|---|---|---|
| clause_id, doc_id | columns | DIRECT |
| ordinal | **recomputed dense, 1-based** over the sort key `(version_id = current_version_id) DESC, ordinal, clause_id` (raw ordinals collide across sets: CMP-REG-001 has 155 rows but 85 distinct ordinals). Current/prose set first, register-row sets after. The minimap uses ordinal/count. | DERIVED backend |
| heading_path | `text[]` -> list (null -> `[]`; 1 row has none) | DIRECT |
| unit_kind | column; `other` -> `section` (1 row) | DIRECT / DERIVED |
| text_raw | column, null -> `""` (274 rows are empty TOC/heading rows; keep them) | DIRECT |
| row_cells | jsonb object with all-string values (2 rows contain a junk key `"null"` with an array value: keep only entries whose value is a string, drop the rest); null stays null | DERIVED backend |
| parent_clause_id | column (a `clause_id`) or null | DIRECT |

### 5.4 Person: `company.people` -> `{person_id, name, title, department, reports_to_id}` all DIRECT.

### 5.5 CompanyProfile

| Field | Source | Tag |
|---|---|---|
| name | `company.companies.name` | DIRECT |
| attributes | `company.company_attributes` rows -> `{key, value, source}`; value = `value_bool` if not null, else `value_num` (int when integral, else float), else `value_text`; `source` = text before `:` of `source` (e.g. `company_profile.yaml`); ordered by key. 22 rows (fixture's `grid_membership` is NOT in the DB; do not add). | DIRECT |
| customers | attribute `customer_count_total` (407491) | DERIVED |
| regulator | `company_profile.yaml` -> `company.regulator` ("Indiana Utility Regulatory Commission (IURC)"); not in DB | DERIVED (static file `app/company/corpus/_global/company_profile.yaml`, pyyaml already a dependency) |
| state | attribute `jurisdiction` = `IN` -> full name via a code->name dict in the module ("Indiana") | DERIVED |
| type | `"{ownership} {utility}"` from attributes `ownership=investor_owned` + yaml `business_model.utility_type=electric_distribution` -> `"Investor-owned electric distribution utility"` | DERIVED |
If the YAML is unreadable: `regulator` falls back to `""` and `type` to attribute values; never a hardcoded string for data that is not there.

---

## 6. Decisions on the known mismatches (summary)

| Topic | Decision |
|---|---|
| Run status | Backend set is exactly `running, done, failed`. Map `done`->`succeeded`; stale `running` (>30 min) -> `failed`; `queued` never occurs. |
| Run `title`/`stats` / N+1 | `GET /engine/ui/runs` returns full `Run` incl. `stats` in ONE query (stats is a column of `engine.runs`). `/engine/runs` stays untouched. |
| ChangeRecord extras | Provided by `/engine/ui/runs/{rid}/changes[/{id}]` (3.2): agency_id/title_number/snapshots via `code_sections` join, texts from `*_text_norm`, characterization from change_records columns. |
| getMatrix / listFindings / listCandidates / annotations / agencies / kb sections | New endpoints (3.4, 3.6, 3.7, 4.1, 4.2). |
| getScore | `getScore(run_id) -> ScoreReport | null` (1.1). |
| submitReview person | Optional 4th arg; default = finding's routed reviewer (3.14). |
| saveScenario vs startWhatIf vs POST | Draft locally; backend create+run only inside `startWhatIf`; presets served from `last_run_id` with no POST (3.12-3.13). |
| 409 while running | Adapters return empty results; `getRun` is never 409 and keeps polling; invalidation happens in `useRunById` when status leaves `running`. |
| Progress | Backend stores none; best-effort derivation from written rows (3.1.1) else `null` -> indeterminate UI. |
| IDs | Section 0. UUIDs for engine entities, text for doc/clause/person/agency. No id rewriting anywhere. |
| 14 verticals | 5 backend names map to 5 slugs; 9 stay empty (5.2). |
| monitored / two_signature / doc_type / cited_citations / next_review | 5.2 (monitored=ingested, two_signature=approver NULL, doc_type heuristic, citations from clause_citations, next_review from register CSV). |
| CompanyProfile | 5.5. |
| Enums | S1 + backend maps (1.2). |

---

## 7. Backend module A: `backend/app/api/engine/routes_ui_runs.py`, `routes_ui_results.py`, `routes_ui_kb.py` (one owner)

Each file: `router = APIRouter(tags=[...])`, paths start with `/ui/...` (mounted under `/engine`), read-only (SELECT only), `text()` SQL via `_all/_one`. No existing file is edited except the registration tuple in `routes.py` (lead). A fourth tiny file `routes_ui_common.py` (not a router; do NOT add it to the registration list) holds shared helpers: `resolve_run(db, rid, require_done)`, `clean_heading`, `build_path_nodes`, `map_stats`, `map_direction`, `CLASS_WORDS`. All three router files import it. Responses use plain dicts (or pydantic models mirroring section 3).

| File | Endpoints |
|---|---|
| `routes_ui_runs.py` | `GET /ui/runs`, `GET /ui/runs/{rid}`, `GET /ui/runs/{rid}/score`, `GET /ui/scenarios`, `GET /ui/whatif/sections`, `GET /ui/whatif/sections/{s1_section_id}` |
| `routes_ui_results.py` | `GET /ui/runs/{rid}/changes`, `.../changes/{change_id}`, `.../candidates`, `.../findings`, `GET /ui/findings/{finding_id}`, `.../rollups`, `.../documents/{doc_id}/annotations`, `.../matrix`, `.../radar` |
| `routes_ui_kb.py` | `GET /ui/kb/agencies`, `/ui/kb/agencies/{slug}`, `/ui/kb/sections`, `/ui/kb/sections/{source_system}/{citation:path}/versions` (declare first), `/ui/kb/sections/{source_system}/{citation:path}` |

Rules: invalid uuid -> 404 (reuse `_uuid`); result endpoints use `_get_run(db, rid)` (404 unknown, 409 running); `/ui/runs*` and scenario/whatif-section endpoints never 409; `float()` all numerics; stable ordering per section 2; no endpoint calls an LLM or writes.

## 8. Backend module B: `backend/app/api/company/` (package: `__init__.py`, `routes.py`)

`router = APIRouter(prefix="/company", tags=["company"])`; lead registers in `main.py`. Endpoints and shapes: section 5. Static inputs read at import with `pathlib.Path(__file__).resolve().parents[2] / "company/corpus/_global/..."` (`document_register.csv`, `company_profile.yaml`); cache in module globals; a missing file degrades to nulls, never raises. No dependency on module A. Optional one-time DB backfill of `company_documents.vertical/review_cycle` and `document_versions.next_review` would remove the CSV fallback but is a write to the shared DB: NOT part of this work.

## 9. Frontend: `frontend/lib/api/http/` (4 disjoint files + index)

| File | Contents |
|---|---|
| `shared.ts` | `API_BASE`, `getJson<T>(path, schema, opts)` (fetch + zod parse, `ApiError`, maps 404/409 per section 2, `encodeURIComponent` helper `seg()`), `qs()` builder dropping undefined, `sleep`, shared `clean_heading` port if needed. Exports `ApiError`. No domain logic. |
| `engine.ts` | `engineHttp: EngineApi`. Thin: each method = `getJson` with the zod schema from `schemas/*`. Composites: `getReader` (company calls + annotations via `Promise.all`), `getMatrix` (company documents filter/sort + `{changes,cells}`), `submitReview` (3.14), `startWhatIf` (3.13 incl. retry), drafts Map + `saveScenario` + `listScenarios` merge (3.12), section-id map for `listEditableSections/getSectionS1Text` (3.11). 409 -> empty results. Imports `companyHttp` only for `getDocument/listClauses/listDocuments`. |
| `kb.ts` | `kbHttp: KbApi`. New-endpoint methods are thin. `listActions/getAction` map per 4.4 (stream param, `abstract:""`, arrays default `[]`, `din:null`, `related` map). `compare` = versions + `diffLines` (copy of mock logic). |
| `company.ts` | `companyHttp: CompanyApi`. Thin; `listDocuments/getDocument` drop docs with a slug outside `VERTICAL_SLUGS`. |
| `index.ts` | `export const httpApi: StrataApi = { kb: kbHttp, engine: engineHttp, company: companyHttp }`. |
No fixture import anywhere under `http/`. No hardcoded counts or sample records.

## 10. Risks and open questions (need the user)

1. **Shared DB.** The DB looks shared (possibly prod). `submitReview` inserts into `engine.finding_reviews` permanently; what-if creation inserts a scenario + a run and spends LLM budget (up to 300 calls per run, `.env` has a live key). Decide whether `http` mode may enable these two writes at all, or should keep them disabled until a staging DB exists. Recommendation: enable review, gate what-if creation behind an explicit confirm; presets are free.
2. **Review actor.** No auth. Default attributes the review to the finding's routed reviewer; alternative is a "acting as" person picker (optional `person_id` arg already supports it).
3. **Which runs to list.** 24 runs, 5 identical-label kb runs, 4 orphan what-ifs with null titles. Default `collapse=true` hides them; confirm.
4. **Real scorecard FAILs** (precision 0, recall 0 on the latest kb run) and Overview will show 4 `action_required` findings. This is real engine output; confirm the demo is meant to show it.
5. **Metadata gaps filled from a static CSV** (vertical, review cycle, next review) because the DB columns are NULL. Alternative is a one-time DB backfill (write).
6. **`doc_type` is a doc_id-token heuristic**, not stored data.
7. **9 of 14 verticals and all "Not monitored" sample documents disappear live** (sample docs were fixtures only).
8. **Progress** is a coarse DB-derived guess; `STALE_RUN_MINUTES=30` marks hung runs failed (display only).
9. **Payload size.** Full kb change list with texts is ~5.6 MB; hence light list rows + gzip. Section list at `limit=5000` is ~0.5 MB.
10. **`llm_calls` can be 0** for cached re-runs even though `judged_llm`=411.
11. **Global search (M10)** would need all 12 docs' clauses client-side (12 `listClauses` calls) or a future `/company/search`; out of scope here.
12. **Disabled/"coming soon" features** (`lib/future-features.ts`) stay disabled; none needs an endpoint.
13. Existing `GET /actions` orders NULL `date_published` first; cosmetic only.

## 11. Verification checklist for implementers

- Backend: every `/engine/ui/*` list parses with the zod arrays using `curl` against the latest kb run (`05b50712-...`) and a what-if run (`18ee057d-...`, `09189501-...` repeal); candidates for a run == `stats.candidates` sum (1234 for the kb run); `stats.changes_raw == substantive + noise`; `/company/documents` returns 12 docs, 5 distinct verticals, `two_signature` true for exactly PRO-007 and PRO-011; clause list for `RPL-CMP-REG-001` has 155 rows with dense unique ordinals; every finding `clause_id` appears in its doc's clause list; radar `attribute_basis` values are non-empty typed values.
- Frontend: `NEXT_PUBLIC_STRATA_DATA=http` with the backend up shows run selector with 6 runs, Overview funnel numbers equal `run.stats`, a preset what-if opens without any POST, a running run returns empty results without errors, and `grep -r fixtures lib/api/http` is empty.
