# Strata v1 — Frontend Brief (for the UI/UX agent)

You are designing the frontend for **Strata**, a regulatory-change impact product. The backend engine is specified and being built. Your job: a UI that makes its results **instantly understandable and trustworthy** to a domain expert in electric-utility regulation.

The backend is only as impressive as what the UI reveals. Design for the "aha": *this exact sentence in this exact clause no longer matches this exact change in the law — and here is the proof.*

---

## 1. Product in one paragraph
Government regulations live in a knowledge base with two snapshots: S1 (old) and S2 (new). A company's documents are ingested down to the **clause** level: procedures, tariff rules, registers, forms. They are assumed compliant with S1.

When S2 arrives, the engine:
- takes only what changed between S1 and S2;
- separates real changes from noise;
- finds every company clause that depends on a changed section;
- decides, clause by clause, whether the clause is now out of line;
- shows verified quotes from the old rule, the new rule and the clause;
- routes each finding to the document's owner, reviewer and approver.

It **flags; it never edits** documents. It also proves what it **cleared**.

## 2. Demo context (design for this story)
- **Company:** Rockridge Power & Light (RPL), a synthetic Indiana electric distribution utility.
- **Regulators:**
  - IURC (state utility commission): Indiana Administrative Code title 170 — the core of the company's documents.
  - IDEM (environment): IAC 326 (air) and 327 (water).
  - FERC: 18 CFR 35/37/38.
  - EPA: 40 CFR 60/63/72/73.
  - Also in the KB: IAC 610 (labor) and 675 (fire/building).
- **Snapshots:** IAC S1 2024-12-31 → S2 2025-12-31. CFR S1 2025-01-02 → S2 2026-10-02.
- **The 12 company documents** (`doc_id`, title, vertical):
  - RPL-CMP-REG-001 Regulatory Obligations Register (Compliance) — a register table, 70 obligation rows
  - RPL-REG-CAL-2025 Regulatory Reporting Calendar 2025 (Compliance) — 48 dated events
  - RPL-LEG-RRS-001 Records Retention Schedule (Compliance) — 86 record series
  - RPL-TAR-GRR-012 Tariff for Electric Service, General Rules (Policy) — tariff sub-rules
  - RPL-CS-PRO-004 Disconnection, Reconnection & Winter Protection Procedure (Policy) — prose plus form templates (notice letter fields)
  - RPL-CS-PRO-007 Meter Test Request & Billing Adjustment Procedure (Policy)
  - RPL-DO-PLN-002 Vegetation Management Plan 2025 (Policy)
  - RPL-CS-PRO-011 Customer Complaint & Dispute Resolution Procedure (Policy)
  - RPL-MTR-PGM-001 Meter Testing Program Plan (Operations)
  - RPL-DCC-PRO-003 Service Interruption Reporting Procedure (Operations)
  - RPL-ENV-PRO-005 Spill Response & Reporting Procedure (Environmental)
  - RPL-SAF-PRO-009 Electrical Accident & Incident Reporting Procedure (Workforce & Safety)
- **People:** 27 people (P01–P27) with name, title and department. Each document has an owner, a reviewer and (usually) an approver.
  - RPL-CS-PRO-007 and RPL-CS-PRO-011 are **two-signature documents with no approver by design**. Show "Two-signature document", never "missing".

### What the real data will look like (important — design for it)
- **~1,100 raw changes, but mostly noise.** Of 1,036 changed IAC sections, ~57% are cosmetic (readoption stamps, register-number lines).
- **Only ~8 changed sections touch sections RPL cites**, across 3 documents (Reporting Calendar, Complaint Procedure, Disconnection Procedure). Most of those are cosmetic, a comma, or a style rewording ("shall not" → "may not").
- **One cosmetic change is cited by 94 clauses.** The engine must clear all 94, with a reason.
- **So the real wave produces few or no clause-level conflicts and many cleared clauses.** The UI must make *clearing* look like valuable work ("we checked 160 clauses; here's why each is fine"), not like an empty screen.
- **Rich clause-level conflicts are shown through What-if mode.** The user edits a value or repeals a section in an S1 regulation; the same engine runs (~1–2 min, or instantly for pre-run presets). Results are labeled **SIMULATED**.
- **~480 substantive changes touch nothing RPL cites.** The Radar screens these against the company profile (e.g. "owns generating units = false" → the EPA turbine rule doesn't apply).

---

## 3. What the backend produces (your data vocabulary)
All under `/engine/*` (FastAPI). Contract: `api_ui.md`. Proposed additions: §9 of this brief.

| Entity | Key fields you can render |
|---|---|
| **Run** | `kind` (kb = real wave, baseline = S1 vs S1, whatif), status, timestamps, **stats** (the funnel: raw → by class → in footprint → obligation changed → candidates by path → findings by verdict → clauses cleared → docs flagged/cleared → radar counts) |
| **Change record** (one per changed regulation section) | citation, heading, rule_key, agency/title, **change_class**, **diff_segments** (word diff: equal/delete/insert), published_date + date_basis + DIN, in_footprint, cited_clause_count, characterization (obligation_changed, direction, plain-English summary, value_changes old→new), disposition + reason |
| **Candidate** (change × clause pair checked) | clause_id, doc_id, match_path, path_detail (via which clause and link), outcome: affected, or cleared with `skip_reason` / rationale |
| **Finding** (a candidate judged affected) | clause_id, doc_id, citation, **finding_type**, **verdict**, severity, **required_change {from_text → to_text}**, **quotes {s1, s2, clause}** + quotes_verified, rationale, confidence, **decided_by (rule vs AI)**, match_path, propagated_from, route (owner/reviewer/approver as people), reviews |
| **Doc rollup** | status flagged/cleared, counts per verdict, changes_considered, cleared reason |
| **Radar item** | change, applicable yes/no/unclear, attribute_basis (company profile keys), affected_activity, reason, quote, docs covering the same rule |
| **What-if scenario** | title, citation, edit_kind (text_edit/repeal), is_preset, last_run_id |
| **Score report** | precision, recall, false-positive rate on must-not-flag clauses, routing accuracy; baseline = 0 findings |

**Enumerations:**
- `change_class`: `substantive, repealed, renumbered, new_section` (real), and `cosmetic, metadata_only, punctuation_only, cross_ref_only` (noise).
- `verdict`: `action_required, optional_relaxed, update_citation, review, info`. "Cleared" is not a finding; it is a candidate outcome.
- `match_path`: `direct_section` (clause cites the section), `direct_rule` (clause cites the parent rule), `register_hop` (linked from or to a register row / form / tariff rule), `value_echo` (the clause restates the old value without citing it).

**Company data available for display:**
- Documents: title, version, effective/approved dates, vertical, owner/reviewer/approver.
- Clauses: clause_id like `RPL-CS-PRO-004:7.2`, ordinal, heading_path (array), unit_kind (`section, table_row, register_row, form_field, tariff_subrule, appendix`), text_raw, row_cells (JSON cells for table/register rows), parent_clause_id.
- Company attributes, e.g. `owns_generating_units=false`, `standby_generator_count=3`, `has_gas_operations=false`.

**Regulation data available:**
- S1 and S2 text per section.
- Existing endpoints: `GET /diff/{source_system}/{citation}/compare` (raw line diff) and `GET /diff/version-history/{source_system}/{citation}` (version chain).

---

## 4. Design principles (non-negotiable)
1. **Clause, not document.** Never show a document-level "non-compliant" without one click to the exact clause and exact words.
2. **Evidence beside verdict.** Every verdict sits next to its proof: old rule text, new rule text, clause text, with the matching words highlighted. Pattern used by Harvey (sentence-level citations beside each answer), Norm Ai (every recommendation paired with rationale and citation) and Ascent (side-by-side redline of obligations).
3. **Show the noise you removed.** Cleared items and noise classes are a feature. Collapsed by default, always one click away, always with a reason.
4. **Trust signals are first-class:**
   - `Verified quote ✓`;
   - `Decided by rule` (deterministic) vs `AI judgment · 82%`;
   - `Evidence unverified — review`;
   - "Why this clause was found" (the match path in plain words).
5. **One color language everywhere** (see §7). The same verdict color appears in pills, document highlights, minimap ticks, matrix cells and funnel bars.
6. **Plain-English first, legal text second.** Lead with a sentence ("Clause states 10 business days; the rule now requires 14."), then the text.
7. **Calm, dense, professional.** No marketing gradients, no animation for its own sake. Reference look: Harvey review tables, Linear, GitHub PR diffs, Draftable compare.

---

## 5. Information architecture
Top bar: **Strata** · run selector (`Real wave · S1→S2` / `Baseline` / `What-if: <title>`) · global search (doc id, clause id, citation).
Left nav: **Overview · Changes · Documents · Impact Matrix · Radar · What-if · Trust**.

A what-if run turns the whole app into SIMULATED mode: an amber top banner and a striped run pill. Every page takes `?run=`.

### 5.1 Overview — "The wave at a glance"
- **The funnel (hero).** Horizontal bars, each step clickable to a filtered view:
  `1,114 changes in S2 → 491 substantive (623 noise: 590 cosmetic, …) → 8 touch your documents → N change an obligation → F findings` and, beside it, **"162 clauses checked and cleared"** (green). Noise bars are gray with a class legend.
- **Tiles:** documents flagged vs cleared; findings by verdict; radar "possibly applicable" count; scorecard mini (precision / recall / FP / baseline ✓).
- **"Needs your attention" list:** top findings sorted by severity, each a one-line plain-English sentence plus a doc chip, linking to the evidence card.
- **Empty real wave** (0 findings): don't show an empty state. Show "No clause needs action. 162 clauses checked across 3 documents — see why," plus a CTA "Try a what-if change."

### 5.2 Changes — "What changed in the law" (regulation diff explorer)
- **Left: tree** Agency → Title → Rule → Section, with count badges. Filter chips: *Touches RPL* (default on) · *Substantive only* (default on) · *Show noise* · class chips. A section row shows citation, heading, class pill, published date, and "cited by N clauses".
- **Right: change detail.**
  - **Header:** citation, heading, agency; plain-English summary + direction chip (tightened/relaxed/new requirement/removed/clarified/style only); value-change chips like `10 → 14 business days`.
  - **Version timeline strip:** S1 snapshot date ● → DIN publication date ● → S2 snapshot date ●.
  - **Diff viewer** with a toggle: **Inline redline** (default; red strikethrough delete, green underline insert) | **Side-by-side** (S1 left, S2 right, synchronized scroll). Collapse unchanged runs over 300 characters ("… 1,240 unchanged characters …"). Show a "Changes 1 of 3 ↑↓" navigator. Noise classes render a gray explanation banner ("Only the readoption stamp changed") and a **"Show raw diff"** toggle using the existing `/diff/.../compare` endpoint.
  - **Impacted clauses panel** (the ledger for this change): every candidate clause grouped by outcome (findings by verdict → cleared with reason). Each row: clause id, doc chip, match-path icon, one-line reason.

### 5.3 Documents — board → reader
- **Board:** 12 cards grouped by vertical. Each card shows title, doc id, version, owner avatar/name, a status pill (**Action needed** red / **Review** amber / **Cleared** green), a verdict mini-bar, and for cleared docs the one-line reason ("3 changes considered: 2 cosmetic, 1 style-only").
- **Document reader (the most important screen to get right).** Split view:
  - **Center: the document itself**, rendered from clauses in `ordinal` order.
    - Headings come from `heading_path`.
    - `register_row` / `table_row` render as real table rows from `row_cells`.
    - `form_field` renders as a labelled form field inside an "Appendix / Form" block, so a notice letter looks like a letter.
    - `tariff_subrule` renders with a sheet/rule label.
    - **Overlays:** affected clauses get a colored left border in the verdict color, and the exact clause quote is highlighted inline. Cleared clauses get a subtle gray ✓ gutter marker; hover shows "Checked: no impact — cosmetic change to <citation>". Unchecked clauses get no marker.
  - **Right rail: findings list** for this document, ordered by position. Each item: verdict pill, clause id, plain-English sentence, citation. Click → scroll to the clause and pulse its highlight. `↑/↓` or `j/k` move between findings (the issue-navigation pattern from DocJuris). A collapsed "Cleared (64)" group sits at the bottom.
  - **Scrollbar minimap:** colored ticks along the right edge at each finding's relative position (by ordinal), so the expert sees *where* in a long document the issues sit.
  - **Header:** document metadata, routing (owner → reviewer → approver), and the status pill.

### 5.4 Evidence card — "Why this clause is out of line"
Opens as a right-side drawer from the reader, the Changes panel or the matrix, and also has its own URL.
1. **Verdict sentence** (large): built from `required_change` and the citation. Example: "§7.2 states **10 business days**; 170 IAC 4-1-x now requires **14 business days**." Pills: verdict · severity · `Decided by rule` or `AI judgment · 0.82` · `Verified quote ✓`.
2. **Three-pane evidence:**
   - Old rule (S1) with its quote highlighted;
   - New rule (S2) with its quote highlighted and the diff marks;
   - Clause text with its quote highlighted.
   Panes 1–2 can collapse into a single inline redline.
3. **Required change:** a `from → to` diff chip (red → green). Label it "Suggested update — not applied".
4. **Why this clause was found (trace).** A horizontal chain of small cards built from `match_path` / `path_detail` / `propagated_from`. Example:
   `170 IAC 4-1-x` → `Obligation register row OBL-2024-0047` → `Disconnection Procedure §7.2` → `Notice letter field App-A.F4`.
   Each node is clickable. This is the "fix once, fix everywhere" moment.
5. **Also affected by this change:** sibling findings across documents (doc chip + clause id + verdict).
6. **Timeline (only when `stale_at_approval`):** rule published ● before document approved ●, with the caption "This document was already out of date when it was approved."
7. **Routing and review:** owner → reviewer → approver with names and titles ("Two-signature document" when there is no approver). Accept / Reject buttons; reject requires a note.

### 5.5 Impact Matrix — Harvey-review-table style
A grid. Rows = 12 documents (grouped by vertical). Columns = the in-footprint changed sections (citation headers, rotated or truncated, tooltip with heading + class).

Cell content:
- a verdict-color dot with a count;
- gray ✓ = all candidates cleared;
- empty = the document doesn't cite this section.

Clicking a cell opens the filtered findings or cleared list. A toggle shows the "noise columns too". This is the single best "at a glance" picture of who is hit by what. Keep it read-only and simple.

### 5.6 Radar — "Changes your documents don't cite"
Three tabs:
- **Possibly applicable:** attribute-basis chips, e.g. `standby_generator_count = 3`; affected-activity sentence; reason; S2 quote; docs covering the same rule.
- **Screened out:** a reason line, e.g. "owns_generating_units = false".
- **Unclear.**

Header copy: "Advisory. These are not tied to any clause."

### 5.7 What-if studio
- **Left: preset cards** (pre-run, instant), e.g. "170 IAC x-y-z: notice period 10 → 15 days" and "Repeal 170 IAC x-y-z". Below: a **section picker** of the sections RPL cites, sorted by "cited by N clauses".
- **Center: editor** showing the S1 text in a textarea, with a **live client-side diff preview** under it (use `jsdiff`) and a "Repeal this section" toggle.
- **Run impact →** shows a **stage progress stepper**: Delta → Characterize → Candidates → Judge → Ledger, with counts appearing as each stage completes. Then: "Open results" → Overview/Documents in SIMULATED mode.

The what-if run reuses every screen above, so building the core screens well makes this nearly free.

### 5.8 Trust (scorecard)
- Precision, recall, false-positive rate on the must-not-flag set, routing accuracy, against the targets (≥0.80, ≥0.83, 0, ≥0.80). Big numbers with pass/fail.
- "Baseline: S1 vs S1 → 0 findings ✓".
- Method notes in 4 bullets:
  - only changes are evaluated;
  - noise classes never reach AI;
  - every finding carries verified quotes;
  - every change has a recorded outcome.
- Counts: decided by rule vs AI; LLM calls.

---

## 6. Core user flows (demo script, ~6 minutes)
1. **Overview:** "1,114 changes landed. Strata removed 623 as noise, found 8 that touch our documents, and checked 162 clauses."
2. **Changes:** open the cosmetic change cited by 94 clauses. Side-by-side shows only a stamp changed → "94 clauses cleared, here's the proof." Open the style rewording ("shall not" → "may not") → "same legal effect, cleared."
3. **Matrix:** see that nothing in the real wave requires action, and where it checked.
4. **What-if:** run the preset "notice period 10 → 15 days" (instant).
5. **Matrix / Documents:** the Disconnection Procedure, Obligations Register and Calendar light up.
6. **Reader:** open the Disconnection Procedure; minimap ticks; jump through findings with `j/k`; one hits a notice-letter form field.
7. **Evidence card:** the verdict sentence, three verified quotes, the trace chain register row → procedure → form field, the route to the owner. Click Reject with a note to show review.
8. **Radar:** "and here's what changed outside your documents that may still apply: 326 IAC change, because you operate 3 standby generators."
9. **Trust:** metrics and baseline.

---

## 7. Visual language
| Token | Use | Color guidance |
|---|---|---|
| action_required | Pill, border, tick | Red 600 |
| optional_relaxed | Rule loosened | Blue 600 |
| update_citation | Stale reference | Violet 600 |
| review | Low confidence / unverified | Amber 500 |
| info | No action | Slate 400 |
| cleared | Checked, no impact | Green 600 (subtle) |
| noise classes | Cosmetic, metadata, punctuation, cross-ref | Gray 300–500, dotted |
| diff delete / insert | Redline | Red text with strikethrough / green text with underline (never color alone; keep the strikethrough and underline for accessibility) |
| SIMULATED | What-if mode | Amber banner with a diagonal-stripe pill |

- **Typography:** sans (Inter) for UI; **serif (e.g. Source Serif) for legal and document text**, which reads as documents; mono (JetBrains Mono) for citations and clause ids.
- **Icons** (lucide) for match paths: `link` direct citation, `git-branch` register hop, `repeat` value echo, `book` rule-level.
- **Density:** 13–14px base, tables with 32px rows, generous whitespace only around the verdict sentence.

## 8. Technical constraints
- Next.js App Router + TypeScript + Tailwind; shadcn/ui (Radix) components; lucide icons; `jsdiff` (client what-if preview only); TanStack Table for the matrix and lists if needed. **No graph or visualization library**: the funnel, minimap, trace chain and timeline are plain divs/CSS.
- Data fetching: SWR or React Query. Poll running runs every 2s.
- No auth, single company. Desktop-first (≥1280px) with a usable tablet layout; mobile isn't required.
- Never render raw JSON. Never show internal ids (uuid); show clause ids, citations and names.

## 9. Backend additions needed for this UI (small; confirm with the backend owner)
| # | Endpoint / field | Purpose |
|---|---|---|
| A1 | `GET /engine/documents/{doc_id}/reader?run_id=` → doc meta + ordered clauses (`clause_id, ordinal, heading_path, unit_kind, text_raw, row_cells, parent_clause_id`) + annotations (`clause_id, kind: finding\|cleared, verdict, finding_id, change_id, citation, quote_span, reason`) | Document reader with overlays |
| A2 | `GET /engine/runs/{id}/matrix` → docs, in-footprint changes, cells `{doc_id, change_id, worst_verdict\|cleared, n_findings, n_cleared}` | Impact matrix |
| A3 | Ledger rows gain `agency_id, title_number, rule_key` | Changes tree, built client-side |
| A4 | `runs.progress` `{stage, done, total, message}` written by the orchestrator and returned by `GET /engine/runs/{id}` | What-if progress stepper |
| A5 | Change detail gains `s1_snapshot, s2_snapshot`, plus the doc `approved_date` on the finding card | Timelines |
Everything else is already in `api_ui.md`.

## 10. Don't build (v1)
Charts libraries, a graph-database or network visualization, a document editor or tracked changes on company docs, chat or "ask AI", notifications, user accounts, PDF rendering of the original documents, quantified dataset impacts, a compliance countdown (there are no effective dates — show the publication date only).

## 11. Deliverables expected from you
1. A page-by-page wireframe description (or low-fi mockups) for §5.1–5.8, including empty, running and simulated states.
2. A component inventory: `VerdictPill`, `ClassPill`, `DiffView` (inline/side-by-side), `QuoteHighlight`, `TraceChain`, `Minimap`, `EvidenceDrawer`, `FunnelBar`, `MatrixGrid`, `RunSelector`, `SimulatedBanner`, `RouteChips`, `TrustBadges`.
3. Confirmation or changes to the §9 API additions.
4. A build order: Overview → Changes → Documents (board + reader) → Evidence card → What-if → Matrix → Trust → Radar.
