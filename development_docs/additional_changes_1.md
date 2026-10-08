# Strata v1 — Additional Changes 1 (frontend capability pack)

**What this is:** a standalone add-on to the existing engine specs (`prd.md`, `architecture.md`, `data_model.md`, `engine_spec.md`, `api_ui.md`, `implementation_plan.md`). It adds the backend endpoints/fields and frontend screens needed for the full UI.

**When to start:**
- Backend tasks (AC1) start after W4 is done.
- Frontend tasks (AC2) start after W5 tasks 5.1.1 and 5.2.1 are done.
- Do not interrupt or rework in-flight waves.

**Precedence:** where this doc conflicts with `api_ui.md` §2 (UI pages), this doc wins. Everything else in the original specs still holds.

## Rules
- **Additive only.**
  - Existing `/engine/*` responses may gain fields; do not rename or remove any.
  - Only one schema change: `engine.runs.progress` (AC1.1.1).
- All guardrails in `architecture.md` §5 still apply (information barrier, no hardcoded doc/citation literals, read-only company data).
- No LLM calls in any task here. All new text is templated from stored data.
- If a separate visual design spec from the UI agent exists in the repo (e.g. `frontend_design*.md`), follow it for look and layout. This doc defines the required **behavior and data**.
- Reporting after each group: ≤12 lines, in the form `task | DONE/BLOCKED | key numbers | files`.
- `∥` = may run in parallel; `→` = depends on.

---

## AC1 — Backend additions

### AC1.1.1 Run progress (→W4)
- Migration: `ALTER TABLE engine.runs ADD COLUMN progress jsonb NULL`.
- `run.py` writes `{"stage": <s>, "done": int, "total": int, "message": str}` at each stage start/end:
  - `s ∈ delta, characterize, candidates, judge, ledger, radar, done, failed`;
  - within `characterize`, `judge` and `radar`, update `done` at most every 2 s.
- `GET /engine/runs/{id}` returns `progress`.

*Done-when:* a what-if run shows monotonically increasing progress when polled.

### AC1.1.2 Plain-English sentence (∥ AC1.1.1)
Add `sentence: str` (templated, no LLM) to every finding DTO: document-page items, the evidence card, and the reader annotations.

The label is `heading_path[-1]` if it is present, else `local_id`. Rules, in order:
1. `required_change` present and `finding_type != 'stale_citation'` → `"{label} states “{from_text}”; {citation} now requires “{to_text}”."`
2. `stale_citation` with a repeal → `"{label} cites {citation}, which was repealed."`
3. `stale_citation` with a renumber → `"{label} cites {citation}, now renumbered to {to_text}."`
4. Otherwise → the first sentence of `rationale`, truncated to 200 characters.

Truncate the quoted from/to text to 80 characters each, with an ellipsis.

### AC1.1.3 Ledger and change detail fields (∥)
- **`GET /engine/runs/{run_id}/ledger`** rows gain `source_system, agency_id, title_number, rule_key`. Get them from `change_records`; join `public.code_sections` on `coalesce(s2_section_id, s1_section_id)` for `agency_id` and `title_number`. It returns all rows when no filter is given (~1,114).
- **`GET /engine/changes/{change_id}`** gains:
  - `agency_id, title_number`;
  - `s1_snapshot, s2_snapshot` (from `runs.snapshots[source_system]`; whatif: `s1` = S1 date, `s2` = `"what-if"`);
  - `noise_explanation` (templated by class):
    - cosmetic: "Only formatting or readoption stamps changed."
    - metadata_only: "Only statutory authority/history lines changed."
    - punctuation_only: "Only punctuation changed."
    - cross_ref_only: "Only cross-references to other laws changed."
    - other classes: null;
  - `raw_diff_path` = the existing `/diff/{source_system}/{citation}/compare` path. Verify its query params for selecting snapshots and include them;
  - `candidates_grouped`: `{"findings": {verdict: [...]}, "cleared": [{clause_id, doc_id, doc_title, match_path, reason}]}`, where `reason` = `skip_reason` mapped to readable text, or the candidate `rationale`.

### AC1.1.4 Finding card additions (∥)
**`GET /engine/findings/{id}`** gains:
- `doc`: `{doc_id, title, version, effective_date, approved_date}`;
- `change.s1_snapshot`, `change.s2_snapshot`;
- `two_signature: bool` (`approver_id` IS NULL);
- `sentence` (from AC1.1.2);
- **`trace`**, an ordered node list for the "why this clause was found" chain:
```json
[{"node":"regulation","citation":"...","heading":"...","change_id":"..."},
 {"node":"clause","clause_id":"...","doc_id":"...","doc_title":"...","unit_kind":"...","label":"...","finding_id":"...|null","verdict":"...|null","link_type":"...|null"},
 ... ending with this finding's clause]
```

Trace construction:
- `direct_*` → `[regulation, this clause]`.
- `register_hop` → `[regulation, via clause, this clause]`. The via clause comes from `path_detail`; attach its finding if one exists for the same change. `link_type` goes on the last edge.
- `value_echo` → `[regulation, this clause]`, with node `label` suffixed "(restates {old value})".
- Then add `downstream`: findings whose `propagated_from` = this finding, in the same node shape.

### AC1.1.5 Document reader endpoint (∥)
**`GET /engine/documents/{doc_id}/reader?run_id=`** (default: latest done kb run).

Response:
```json
{
  "doc": {"doc_id","title","vertical","version","effective_date","approved_date","law_as_of",
          "route":{"owner":{person},"reviewer":{person},"approver":{person}|null},"two_signature":bool},
  "rollup": {...doc_rollups row...},
  "tables": {"<table_id>": ["col1","col2", "..."]},
  "clauses": [{"clause_id","local_id","ordinal","parent_clause_id","heading_path","unit_kind",
               "section_kind","table_id","row_cells","text_raw","clause_role"}],
  "annotations": [
    {"clause_id","kind":"finding","finding_id","verdict","severity","citation","change_id",
     "quote_span":[s,e]|null,"sentence"},
    {"clause_id","kind":"cleared","change_id","citation","change_class","reason"}
  ]
}
```

Rules:
- `clauses`: every clause of the document's current version (including boilerplate, for full rendering), ordered by `ordinal`.
- `annotations`: one per finding, plus one per cleared candidate in this doc for this run. A clause may have several. `quote_span` = `locate_quote(quotes.clause, text_raw)`.
- `tables`: column order per table from `company.table_columns` (match `doc_id` and `table_name`; verify `table_name` ↔ `clauses.table_id` mapping), in physical row order. Fallback: the keys of the first row's `row_cells`.

*Done-when:* `len(clauses)` = the clause count for the doc; annotation counts equal that doc's findings plus cleared candidates for the run.

### AC1.1.6 Impact matrix endpoint (∥)
**`GET /engine/runs/{run_id}/matrix?include_noise=false`**
```json
{"docs":[{"doc_id","title","vertical","status"}],
 "changes":[{"change_id","citation","heading","change_class","cited_clause_count"}],
 "cells":[{"doc_id","change_id","worst":"action_required|optional_relaxed|update_citation|review|info|cleared","n_findings","n_cleared"}]}
```

Rules:
- Columns: in-footprint changes, excluding noise classes unless `include_noise=true`, ordered by `cited_clause_count` desc.
- Rows: all company docs, grouped by vertical.
- Cells exist only where the (doc, change) pair has ≥1 candidate.
- `worst` priority: `action_required > optional_relaxed > update_citation > review > info > cleared`.

*Done-when:* summing `n_findings` over cells equals the run's finding count for in-footprint changes.

### AC1.1.7 Global search (∥, should-have)
**`GET /engine/search?q=&run_id=`** returns up to 8 of each:
- `docs` (doc_id/title ILIKE);
- `clauses` (clause_id ILIKE, or `text_raw` ILIKE when q ≥ 4 chars → `{clause_id, doc_id, snippet}`);
- `changes` (citation/heading ILIKE, scoped to the run).

### AC1.1.8 Tests (→AC1.1.1–1.1.7)
- httpx tests for each new endpoint or field, against the kb run and one what-if run.
- 404 for unknown ids; 409 while a run is `running`. Exception: `GET /engine/runs/{id}` never returns 409.

---

## AC2 — Frontend (supersedes `api_ui.md` §2)

### AC2.0 Global
- **Stack:** Next.js App Router, TypeScript, Tailwind, shadcn/ui (Radix), lucide-react, SWR or React Query, `diff` (jsdiff, what-if preview only), TanStack Table (optional). No chart or graph libraries; the funnel, minimap, trace and timeline are divs/CSS.
- **Fonts:** Inter (UI), a serif such as Source Serif 4 (all regulation and document text), JetBrains Mono (citations, clause ids).
- **Layout:**
  - Top bar: Strata, run selector (`Real wave · S1→S2` / `Baseline` / `What-if: <title>`), global search (AC1.1.7).
  - Left nav: **Overview · Changes · Documents · Impact Matrix · Radar · What-if · Trust**.
  - `/ledger` redirects to `/changes`.
- **SIMULATED mode:** for a what-if run, show an amber top banner "SIMULATED — not real regulation" and a striped run pill.
- **Every page reads `?run=`.**
- **Color tokens** (one language everywhere: pills, borders, ticks, matrix cells):
  - action_required: red-600; optional_relaxed: blue-600; update_citation: violet-600; review: amber-500; info: slate-400;
  - cleared: green-600 (subtle); noise classes: gray dotted;
  - diff: delete = red text with strikethrough, insert = green text with underline (never color alone).
- **Trust badges** (reusable):
  - `Verified quote ✓` / `Evidence unverified — review`;
  - `Decided by rule` / `AI judgment · {confidence%}`;
  - match-path icon plus text: `link` "Cites this section", `book` "Cites the parent rule", `git-branch` "Linked via {link_type}", `repeat` "Restates the old value".
- **Never show** uuids or raw JSON. Show clause ids, citations, names. Show a two-signature document as "Two-signature document", never as "missing approver".
- **Components:** `VerdictPill, ClassPill, TrustBadges, MatchPathTag, DiffView (inline | side-by-side, collapsible equal runs >300 chars, change navigator ↑↓), QuoteHighlight, FunnelBar, Minimap, TraceChain, Timeline, EvidenceDrawer, MatrixGrid, RunSelector, SimulatedBanner, RouteChips, ProgressStepper`.

### AC2.1 Overview `/` (→AC1.1.1)
1. **Funnel** from `stats`: total S2 changes → substantive (noise breakdown in gray by class) → touch your documents → change an obligation → findings. Beside it, a green "N clauses checked and cleared". Each bar links to a filtered `/changes`.
2. **Tiles:** docs flagged vs cleared; findings by verdict; radar possibly-applicable count; mini scorecard (kb runs only).
3. **"Needs your attention":** top 8 findings by severity, as `sentence` + doc chip → evidence drawer.
4. **Zero-findings state** (no empty screen): "No clause needs action. {clauses_cleared} clauses checked across {n} documents — see why" → `/changes`, plus a CTA "Try a what-if change" → `/whatif`.

### AC2.2 Changes `/changes` (→AC1.1.3)
- **Left tree:** agency → title → rule → section, with count badges, built client-side from the ledger.
  - Filter chips: *Touches your documents* (on), *Substantive only* (on), *Show noise*, plus class chips.
  - Row: citation (mono), heading, ClassPill, published date, "cited by N clauses".
- **Right detail:**
  - Header: summary + direction chip + value-change chips `old → new`.
  - Timeline: S1 snapshot ● → publication date ● (if present) → S2 snapshot ●.
  - `DiffView` with an Inline/Side-by-side toggle.
  - Noise classes: a gray banner with `noise_explanation`, plus a "Show raw diff" toggle that fetches `raw_diff_path`.
  - **Impacted clauses panel** from `candidates_grouped`: findings by verdict, then a collapsible "Cleared (N)" with reasons. Rows link to the reader at that clause.
- **Deep link:** `/changes?change=<id>`.

### AC2.3 Documents `/documents` and Reader `/documents/[docId]` (→AC1.1.2, AC1.1.5)
**Board:**
- Cards grouped by vertical: title, doc id, version, owner name, status pill (Action needed / Review / Cleared), verdict mini-bar.
- Cleared cards show `rollup.reason`.

**Reader (the most important screen):**
- **Center: render the document from `clauses`.**
  - Section headings come from changes in `heading_path`.
  - `section`/`appendix`: paragraphs (serif).
  - `register_row`/`table_row`: rows of one table per `table_id`, columns from `tables`.
  - `form_field`: a labelled field inside a bordered "Form" block grouped by appendix.
  - `tariff_subrule`: a rule label + text.
- **Overlays:**
  - Finding: a left border in the worst verdict color, the `quote_span` highlighted, and a small verdict pill.
  - Cleared: a gray ✓ in the gutter; hover tooltip "Checked: no impact — {reason} ({citation})".
- **Right rail:** findings in document order (VerdictPill, clause id, `sentence`, citation).
  - Click → scroll to the clause and pulse its highlight.
  - Keys `j/k` or `↑/↓` move between findings; `Enter` opens the EvidenceDrawer.
  - A collapsed "Cleared (N)" group at the bottom.
- **Minimap:** a thin strip beside the scrollbar with colored ticks at `ordinal / max_ordinal` per annotated clause; click → scroll.
- **Header:** doc metadata, RouteChips (owner → reviewer → approver), status pill.
- **Deep link:** `/documents/[docId]?clause=<clause_id>` scrolls to the clause and highlights it.

### AC2.4 Evidence drawer + `/findings/[id]` (→AC1.1.4)
Right-side drawer (≈640px) from the reader, changes panel or matrix; also a standalone page. Sections:
1. **`sentence`** (large), then VerdictPill · severity · TrustBadges.
2. **Three panes:** S1 rule (s1 quote highlighted) · S2 rule (s2 quote highlighted + diff marks) · clause (clause quote highlighted). Toggle "Combine rule panes" → a single inline redline.
3. **Suggested update:** a `from → to` chip, labeled "Suggested update — not applied".
4. **Why this clause was found:** `TraceChain` from `trace` (horizontal cards; clickable to the reader/changes), followed by `downstream`.
5. **Also affected:** a list of `also_affected`.
6. **Timeline:** only if `finding_type='stale_at_approval'`. Rule published ● before document approved ●, captioned "This document was already out of date when it was approved."
7. **Routing:** RouteChips (two-signature label when needed). If review routes exist (W8): Accept / Reject (a note is required on reject) + review history.

### AC2.5 Impact Matrix `/matrix` (→AC1.1.6)
- Grid: rows = docs (grouped by vertical, sticky first column); columns = changes (citation headers, tooltip with heading + class).
- Cell: a colored dot for `worst` + `n_findings`; green ✓ when `worst='cleared'` (tooltip "n cleared"); empty = not cited.
- Toggle "Include noise changes" (`include_noise=true`).
- Cell click → a popover listing the findings and cleared clauses, linking to the drawer or reader.

### AC2.6 What-if studio `/whatif` (→W6, AC1.1.1)
- **Left:** preset cards (title, last-run summary; click → open results instantly) + a section picker (`/engine/whatif/sections`, sorted by cited clauses).
- **Center:** the S1 text in a textarea, a live jsdiff preview below it (same styling as DiffView), a "Repeal this section" toggle, a title input, and a **Run impact** button.
- **On run:** a `ProgressStepper` (Delta → Characterize → Candidates → Judge → Ledger) driven by `progress`, polled every 2 s, with counts per stage. On done: buttons "Open overview" / "Open matrix" with `?run=`.

### AC2.7 Trust `/trust`
- Scorecard (`/engine/runs/{id}/scorecard`): precision, recall, false-positive rate on must-not-flag, routing — big numbers vs targets (≥0.80, ≥0.83, 0, ≥0.80) with pass/fail. Show "Baseline S1 vs S1: {n} findings ✓/✗".
- From `stats`: decided by rule vs AI, LLM calls, run duration.
- Static method notes (4 bullets):
  - only S1→S2 changes are evaluated;
  - noise classes never reach AI;
  - every finding carries verified quotes or is marked for review;
  - every change has a recorded outcome.
- What-if runs: show "Not scored (simulated)".

### AC2.8 Radar `/radar` (→W7; skip if W7 is cut)
- Tabs: Possibly applicable · Screened out · Unclear.
- Item: citation + heading + agency, `affected_activity`, attribute chips (`key = value` from company attributes), `reason`, S2 quote, "Rule also covered by: {docs}".
- Header note: "Advisory — not tied to any clause."

### AC2.9 Polish and QA (→AC2.1–AC2.7)
- Loading skeletons; error toasts.
- Every cross-link works: finding ↔ change ↔ reader clause ↔ matrix cell.
- Keyboard navigation in the reader.
- Desktop ≥1280px first; tablet usable.
- *Done-when:* the demo path below runs on the deployed app with no console errors.

---

## Build order and parallelism
| Step | Tasks | Parallel? |
|---|---|---|
| 1 | AC1.1.1–AC1.1.7 | All ∥ each other (after W4) |
| 2 | AC1.1.8 | → step 1 |
| 3 | AC2.0 | After 5.2.1; ∥ step 1 |
| 4 | AC2.1, AC2.2, AC2.3 | ∥ each other (→AC2.0 + their AC1 deps) |
| 5 | AC2.4, AC2.5, AC2.7 | ∥ (AC2.4 → AC2.3) |
| 6 | AC2.6 | → W6 |
| 7 | AC2.8 | → W7 (optional) |
| 8 | AC2.9 | Last |

## Demo path (acceptance)
1. Overview funnel + cleared count.
2. Changes: open the most-cited in-footprint change → noise banner + cleared list.
3. Matrix (real wave).
4. What-if: open a value preset → Matrix lights up.
5. Documents → the most affected doc → reader, `j/k` through findings, minimap ticks.
6. Open the evidence drawer → sentence, three verified quotes, trace chain, routing.
7. Radar (if built).
8. Trust.
