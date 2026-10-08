# Strata v1 — Frontend Build Spec

Status: ready for build · Owner: Athish · Last updated: 2026-10-07
Inputs merged: `frontend_brief.md` (from the backend agent), the product owner's page plan, the KB and company data audits (2026-10-07), and the backend code and docs on `main`.

---

## 0. How to use this document

This is the single source of truth for the agent building the Strata frontend. It is self-contained. Supporting files in `frontend_development_docs/`:
- `README.md`: reading order and the kickoff prompt.
- `frontend_brief.md`: the backend agent's brief, kept for provenance.
- `reference/`: the KB and company-data audits (2026-10-07). Use them for data shapes and realistic values.

### 0.1 Hard boundaries for this phase
1. **All code lives in `frontend/`.** It is a standalone Next.js project, and `frontend/` is the **deploy root** (Vercel "Root Directory" = `frontend`).
   - No `package.json`, lockfile, workspace file, CI config or tooling at the repo root.
   - The app must install, build and run when `frontend/` is the only folder present.
2. **Never create, modify or delete anything outside `frontend/`.** The backend folders are under active development by another agent. The only exception is `frontend_development_docs/`, and only when the owner asks.
3. **No integrations in this phase.**
   - No calls to the backend, no API base URL, no proxy rewrites, no environment variables pointing at services.
   - No database, Qdrant or R2 access.
   - Every data domain (KB, engine, company) is served by the in-app mock layer (§6).
   - The `StrataApi` interface is designed so a live implementation can be added later without touching pages.
4. **Nothing at runtime or build time may import from outside `frontend/`.** The one-off fixture script (§6.4) may read the corpus files in `../backend` **read-only**, on a developer's machine. It writes JSON into `frontend/fixtures/`, which is committed. The app only ever reads the committed fixtures.

**Precedence when sources disagree**
1. This spec.
2. `development_docs/frontend_brief.md`. It is canonical for anything about the analysis engine (runs, changes, findings, evidence) that this spec does not override.
3. The backend code on `main`, as a **read-only reference** for shapes and field names. Endpoint shapes there win over guesses in either document when designing fixtures.

Every deliberate departure from the brief is listed in §3 with a reason.

**Rules for the build agent**
- Build everything against the typed data layer in §6, served entirely by mocks. The backend's analysis engine (`/engine/*`) does not exist yet, and even the existing KB endpoints are not called in this phase.
- **Information barrier.** Never read, copy or derive fixtures from these paths:
  - `backend/app/company/corpus/eval/**`
  - `backend/app/company/corpus/grounding/**`
  - `backend/app/company/corpus/qa/**`
  - `backend/app/company/corpus/validation/**`
  - `*.basis.json`
  - `tools/offline_eval/**`
  
  They hold the engine's answer key. Mock findings must be invented scenarios, not the expected answers.
- **Visual design is specified in §17** (Harvey-inspired: monochrome, serif titles, hairlines, status-only color). Style shadcn/ui components to it; never leave shadcn defaults visible.
- **Future-capability cues are specified in §18.** Build every cue in the catalog and nothing beyond it. Do not build anything in §15 (out of scope), even as a stub, except where §18 lists a disabled cue for it.

---

## 1. Product

**Strata** is a regulatory-change impact product for an electric utility. Government rules are held in a knowledge base (KB) with two snapshots: **S1** (old) and **S2** (new). The company's documents are broken down to the **clause** level: procedure sections, tariff sub-rules, register rows, form fields. They are assumed compliant with S1.

When S2 arrives, the engine:
1. takes only what changed between S1 and S2;
2. separates real changes from noise (cosmetic, metadata, punctuation, cross-reference-only);
3. finds every company clause that depends on a changed section;
4. decides clause by clause whether the clause is now out of line;
5. attaches verified quotes from the old rule, the new rule and the clause;
6. routes each finding to the document's owner, reviewer and approver.

It **flags; it never edits** documents. It also **proves what it cleared**.

**The moment the UI must deliver:** *this exact sentence in this exact clause no longer matches this exact change in the law, and here is the proof.*

**Product goal (from the owner):** help a company understand how a change to a government rule, regulation or guideline affects it, across every department. The company is organized into 14 verticals (§5.3), each holding its department's documents. In v1 a change is surfaced by flagging the clauses (and therefore the documents) that need review.

---

## 2. Users and demo context

**User.** A domain expert at the client company: regulatory affairs, compliance, legal, or a department owner. The client is a large company with many departments. **The demo has one user, with no login and access to everything.** Design every page so a first-time user understands it without training, and so a department user could later land on "their" vertical.

**Demo company.** Rockridge Power & Light (RPL). It is a synthetic Indiana investor-owned electric **distribution** utility: about 407k customers, no generating units, in the MISO footprint, regulated by the IURC.

**Regulators and coverage**

| Agency | Level | Codebook (rules in force) | Activity feed (actions) |
|---|---|---|---|
| FERC | Federal | 18 CFR parts 35, 37, 38 | Federal Register rules |
| EPA | Federal | 40 CFR parts 60, 63, 72, 73 | Federal Register rules |
| IURC | State (IN) | 170 IAC (the core of RPL's documents) | Orders (GAOs), Investigations, Rulemakings |
| IDEM | State (IN) | 326 IAC (air), 327 IAC (water) | Rulemakings |
| (no agency record yet) | State (IN) | 610 IAC (labor), 675 IAC (fire and building safety) | none |

**Snapshots.** IAC S1 2024-12-31 → S2 2025-12-31. CFR S1 2025-01-02 → S2 2026-10-02.

**The 12 analyzed company documents**

| doc_id | Title | Backend vertical | Shape |
|---|---|---|---|
| RPL-CMP-REG-001 | Regulatory Obligations Register | Compliance & Legal | Register, 70 obligation rows |
| RPL-REG-CAL-2025 | Regulatory Reporting Calendar 2025 | Compliance & Legal | Register, 48 dated events |
| RPL-LEG-RRS-001 | Records Retention Schedule | Compliance & Legal | Register, 86 record series |
| RPL-TAR-GRR-012 | Tariff for Electric Service, General Rules | Policy & Governance | Tariff sub-rules |
| RPL-CS-PRO-004 | Disconnection, Reconnection & Winter Protection Procedure | Policy & Governance | Prose plus form templates (notice letters) |
| RPL-CS-PRO-007 | Meter Test Request & Billing Adjustment Procedure | Policy & Governance | Prose; **two-signature, no approver by design** |
| RPL-DO-PLN-002 | Vegetation Management Plan 2025 | Policy & Governance | Prose plus tables |
| RPL-CS-PRO-011 | Customer Complaint & Dispute Resolution Procedure | Policy & Governance | Prose plus forms; **two-signature, no approver by design** |
| RPL-MTR-PGM-001 | Meter Testing Program Plan | Operations & Processes | Prose plus tables |
| RPL-DCC-PRO-003 | Service Interruption Reporting Procedure | Operations & Processes | Prose |
| RPL-ENV-PRO-005 | Spill Response & Reporting Procedure | Environmental | Prose plus forms |
| RPL-SAF-PRO-009 | Electrical Accident & Incident Reporting Procedure | Workforce & Safety | Prose |

The four `RPL-INF-*` register entries (company profile, people directory, document register, operational master data) are reference assets, not analyzed documents. They do not appear on the Documents board. The company profile and the people directory power the Company profile page (§9.14).

**People.** 27 people (P01–P27) with name, title, department and reporting line. The departments are Executive, Legal, Regulatory Affairs, Compliance, Customer Operations, Metering, Distribution Operations, Operations and EHS. Every document has an owner and a reviewer, and usually an approver. For RPL-CS-PRO-007 and RPL-CS-PRO-011 show **"Two-signature document"**, never "missing approver".

**What the real data looks like (design for it)**
- About 1,100 raw changes, mostly noise. About 57% of the 1,036 changed IAC sections are cosmetic (readoption stamps, register-number lines).
- Only about **8 changed sections touch sections RPL cites**, across 3 documents: the Reporting Calendar, the Complaint Procedure and the Disconnection Procedure. Most of those are cosmetic, a comma, or a style rewording ("shall not" → "may not").
- **One cosmetic change is cited by 94 clauses.** The engine clears all 94, each with a reason.
- So the real wave yields few or no clause-level conflicts and many cleared clauses. **Clearing must look like valuable work** ("we checked 162 clauses; here's why each is fine"), never like an empty screen.
- Rich clause-level conflicts are demonstrated through **What-if mode**. The user edits or repeals an S1 section, and the same engine runs (about 1–2 minutes, or instantly for presets). Those results are labeled **SIMULATED**.
- About 480 substantive changes touch nothing RPL cites. The **Radar** screens them against the company profile, e.g. "owns generating units = false" means the EPA turbine rule doesn't apply.

---

## 3. Decisions log (reconciling the brief with the owner's page plan)

| # | Topic | Owner's plan | Brief | **Decision** |
|---|---|---|---|---|
| D1 | Navigation model | Data-centric: Home, Government data, Company data | Engine-centric: Overview, Changes, Documents, Matrix, Radar, What-if, Trust | **Both, in two nav groups.** "Analysis" (the brief's 7 pages) is the primary working surface. "Knowledge base" (Regulations, Company profile) is the browsable reference. The Documents board is the company-data landing page. |
| D2 | Marketing page | Required | Not mentioned | **Build it** at `/`. The app lives at `/app`. Tone follows the brief: calm and factual, no hype. |
| D3 | Verticals | 14 verticals | Documents grouped by the 5 backend verticals | **The board shows all 14 verticals** in a fixed order (§5.3). The 5 backend vertical names are mapped onto them. |
| D4 | Data for the 9 empty verticals | Mock it | The matrix and engine counts are based on 12 documents | **2–3 sample entries per empty vertical, labeled "Not monitored".** They show on the board and the vertical pages only. They never appear in runs, the matrix, funnel counts, search results of type clause, or the Trust metrics, and they have no reader. This keeps the engine numbers honest in front of a domain expert. |
| D5 | Government data landing + "Add agency" | Agencies split into Federal and State, with add buttons | Changes tree grouped by agency | **Both.** Regulations (KB) lists agencies with disabled "Add agency" cards. Changes keeps the brief's Agency → Title → Rule → Section tree. |
| D6 | IAC 610 / 675 | Unknown owners | 610 = labor, 675 = fire/building | Show them under State as **codebook-only cards**: "610 IAC — Labor" and "675 IAC — Fire & Building Safety", each with "No activity feed". There is no agency record yet, so don't invent agency names. |
| D7 | Original PDF view | "View original PDF" button | Do not build PDF rendering | **Disabled future button** "View original file". The reader renders from clauses only. |
| D8 | Upcoming deadlines on Home | From the Reporting Calendar | No compliance countdown; show publication dates only | **Dropped.** |
| D9 | Ask AI / chat, notifications, integrations, multi-company | Considered | Do not build | **Not built. They appear only as disabled cues** (§18), at the owner's direction, to signal where the platform is going. None of them has any behavior. |
| D10 | Document page right panel | Tabs for flags, citations, key values, details | A findings rail, ordered by position | **The brief's findings rail is primary.** Document metadata sits in the header. A clause-details popover (citations, values, defined terms) is a P2 addition (§9.4). |
| D11 | Tariff vertical | Suggested moving it to Revenue & Pricing | Policy | **Keep the backend's vertical (Policy & Governance Documents).** |
| D12 | Run awareness | Not considered | `?run=` on every page; SIMULATED mode | **Adopted globally**, KB pages included (they keep the param in every link and show change badges for the selected run). |
| D13 | Brief's version-history endpoint | — | `GET /diff/version-history/{ss}/{citation}` | The real route is **`GET /diff/{source_system}/{citation}`**. Record the real route in the contract notes for future wiring and flag it to the backend owner. |
| D14 | Integration | — | Live polling, live KB endpoints | **Not in this phase.** Everything is mocked inside `frontend/` (§0.1). Polling and running states are exercised against the mock layer. |
| D15 | Look and feel | — | Calm, dense; reference Harvey, Linear, GitHub diffs; red/blue/violet/amber/slate/green verdict colors | **Harvey-inspired monochrome system (§17).** Color is used only for status: red, green and one muted amber. |
| D16 | Verdict colors | — | Five distinct verdict hues | Reduced to red (action required), amber (review), ink/ink-2/ink-3 neutrals with icons (update citation / relaxed / info) and green (cleared). The pill text and icon always carry the meaning. |
| D17 | SIMULATED mode | — | Amber banner and striped pill | **Neutral diagonal hatch plus a "Simulated" tag.** Amber is reserved for "needs review". |
| D18 | Top bar | — | Top bar with RunSelector and search | **No top bar** (Harvey layout). Search lives in the sidebar header (⌘K). The RunSelector sits at the right of every analysis page header. |
| D19 | Future cues | 1–2 disabled buttons per page | — | **Expanded into a curated catalog (§18)**: at most 3 per page plus a few shell cues, all disabled, from one registry. |

---

## 4. Tech stack

The stack is the de-facto standard for agent-built React apps in 2026. Agents produce it most reliably, it matches the brief's constraints, and it suits a calm, dense, professional UI (references: Linear, GitHub PR diffs, Harvey review tables, Draftable compare).

| Concern | Choice | Notes |
|---|---|---|
| Framework | **Next.js 16 (App Router)** + **React 19** | Use the latest 16.x stable at scaffold time. Deploy target: Vercel, with Root Directory `frontend`. |
| Runtime | **Node.js LTS** | Pin it in `frontend/.nvmrc` and in `engines` in `frontend/package.json`. |
| Language | **TypeScript**, `strict: true` | No `any` in app code. |
| Package manager | **pnpm** | |
| Styling | **Tailwind CSS v4** | Utility classes only, no CSS-in-JS. Design tokens are CSS variables exposed via `@theme` (§17.2). |
| Components | **shadcn/ui** (CLI v4), **Radix primitives** | Base UI is now shadcn's default, but the brief specifies Radix. Pick Radix once, at init. The components are copied into the repo and owned by us. |
| Icons | **lucide-react** | Match-path icons are in §11.2. |
| Server state | **TanStack Query v5** | Caching; `refetchInterval: 2000` while a run is `running`; mutations for reviews and what-if. |
| URL state | **nuqs** | Type-safe search params: `run`, filters, `finding`, tabs. Every view must be shareable by URL. |
| Tables and grids | **TanStack Table v8** | Lists, ledgers, the KB tables. The matrix may be a plain CSS grid driven by the same data. |
| Long lists | **@tanstack/react-virtual** | Use only where needed: the reader for long documents, cleared ledgers, KB section lists. |
| Contract and validation | **zod** | One schema per API entity. Types are inferred from the schemas, and fixtures are validated in tests. |
| Text diff (client) | **diff** (jsdiff) | In the UI, **only** for the what-if live preview. Everything else renders the `diff_segments` provided by the data layer. The fixture script also uses it to generate consistent `diff_segments`. |
| Command palette | **cmdk** (shadcn `Command`) | Global search, ⌘K. |
| Split panes | **react-resizable-panels** (shadcn `Resizable`) | Changes master–detail, reader + findings rail. |
| Drawer, dialogs, popovers, tooltips | shadcn `Sheet`, `Dialog`, `Popover`, `Tooltip`, `HoverCard` | The evidence drawer is a `Sheet`. |
| Toasts | **sonner** (shadcn) | Review saved, run started or finished. |
| Fonts | `next/font/google` | **Source Serif 4** (display and document), **Inter** (UI), **JetBrains Mono** (ids) (§17.3). |
| Unit tests | **Vitest** + **React Testing Library** | Label dictionaries, sentence builders, status derivation, fixture invariants. |
| E2E tests | **Playwright** | The demo script in §12 is the e2e suite. Chromium is preinstalled in the cloud environment, so use `executablePath: '/opt/pw-browsers/chromium'` if versions mismatch, and never run `playwright install`. |
| Lint and format | ESLint (`next` config) + Prettier + `prettier-plugin-tailwindcss` | |

**Do not add:** chart or visualization libraries (the funnel, minimap, trace chain, timeline and matrix are plain divs and CSS), graph or network libraries, Redux, Zustand or other global stores (URL state, TanStack Query and one small React context are enough), animation libraries, PDF libraries, CSS-in-JS, other component kits (MUI, Chakra, Mantine, Ant), or auth libraries.

---

## 5. Project structure and conventions

### 5.1 Layout

`frontend/` is a self-contained project root. Scaffold it with `pnpm create next-app frontend` from the repo root, then work only inside it.

```
frontend/                                # deploy root; nothing outside this folder is touched
  package.json  pnpm-lock.yaml  .nvmrc  next.config.ts  tsconfig.json
  eslint.config.mjs  .prettierrc  components.json  playwright.config.ts  vitest.config.ts
  .gitignore  README.md                  # README: how to run, test, and deploy with Root Directory = frontend
  app/
    (marketing)/page.tsx                 # "/" landing
    app/                                 # "/app/*" product
      layout.tsx                         # AppShell: dark sidebar, main canvas, SimulatedBanner, providers
      page.tsx                           # Overview
      changes/page.tsx                   # tree + empty detail
      changes/[changeId]/page.tsx        # tree + change detail
      documents/page.tsx                 # board, 14 verticals
      documents/verticals/[vertical]/page.tsx
      documents/[docId]/page.tsx         # reader
      findings/[findingId]/page.tsx      # evidence card, full page
      matrix/page.tsx
      radar/page.tsx
      what-if/page.tsx                   # studio
      what-if/[scenarioId]/page.tsx      # editor + run progress
      trust/page.tsx
      regulations/page.tsx               # KB: agencies overview
      regulations/[agencyId]/page.tsx    # KB: agency (rules in force / activity)
      regulations/sections/[sourceSystem]/[...citation]/page.tsx
      regulations/actions/[sourceSystem]/[...sourceId]/page.tsx
      company/page.tsx                   # KB: company profile & people
  components/
    ui/                                  # shadcn (generated; edit freely)
    shell/                               # AppShell, Sidebar, TopBar, RunSelector, SimulatedBanner, GlobalSearch, Breadcrumbs
    engine/                              # VerdictPill, ClassPill, DiffView, QuoteHighlight, TraceChain, Minimap, EvidenceDrawer, FunnelBar, MatrixGrid, RouteChips, TrustBadges, ...
    documents/                           # DocCard, VerticalSection, ClauseRenderer, FindingsRail, ...
    kb/                                  # AgencyCard, SectionTree, ActionList, ...
    common/                              # EmptyState, ErrorState, StatTile, FutureCue, PersonChip, ...
  lib/
    api/
      schemas/                           # zod schemas = the contract (§6.3)
      client.ts                          # StrataApi interface + the single place that picks the implementation
      mock/                              # mock implementation + fixtures loader (the only implementation in this phase)
      queries.ts                         # TanStack Query keys + hooks
    labels.ts                            # every enum → display label (§11)
    sentences.ts                         # plain-English sentence builders (§11.4)
    status.ts                            # document status derivation (§11.5)
    verticals.ts                         # 14 verticals + backend mapping (§5.3)
    future-features.ts                   # future-cue registry (§18)
    run-context.tsx                      # current run from ?run=, SIMULATED flag
  fixtures/                              # committed JSON, validated by zod in tests; the app's only data source
  scripts/
    build-fixtures.ts                    # one-off, dev-only: reads ../backend corpus read-only → writes fixtures/ (§6.4)
  tests/{unit,e2e}/
```

### 5.2 Conventions
- Server components only for static shells and the marketing page. Product pages render client components that read through TanStack Query hooks, so swapping in a live implementation later changes nothing in the pages.
- **Never render raw JSON. Never display internal ids (uuids).** Show clause ids (`RPL-CS-PRO-004:7.2`), citations (`170 IAC 4-1-16`), doc ids and people's names. Uuids may appear in URLs only.
- All display strings for enums come from `lib/labels.ts`. Components never format enums inline.
- Dates are ISO in data and formatted as `Feb 5, 2025` in the UI. For changes show the **publication date** (with its `date_basis`). There are no effective-date countdowns.
- Citations and clause ids always render in the mono role, and legal and document text in the serif role (§17.3).

### 5.3 The 14 verticals (fixed order)

| # | Display name | slug | Mapped backend vertical(s) | Real docs |
|---|---|---|---|---|
| 1 | Compliance & Legal | `compliance-legal` | Compliance & Legal | 3 |
| 2 | Policy & Governance Documents | `policy-governance` | Policy & Governance | 5 |
| 3 | Financial & Reporting | `financial-reporting` | — | 0 (samples) |
| 4 | Revenue & Pricing | `revenue-pricing` | — | 0 (samples) |
| 5 | Operations & Processes | `operations-processes` | Operations & Processes | 2 |
| 6 | Technology & Systems | `technology-systems` | — | 0 (samples) |
| 7 | Workforce & HR | `workforce-hr` | Workforce & Safety | 1 |
| 8 | Environmental & ESG | `environmental-esg` | Environmental | 1 |
| 9 | Supply Chain & Procurement | `supply-chain-procurement` | — | 0 (samples) |
| 10 | Risk & Insurance | `risk-insurance` | — | 0 (samples) |
| 11 | Strategic & Competitive | `strategic-competitive` | — | 0 (samples) |
| 12 | Reputational & Stakeholder | `reputational-stakeholder` | — | 0 (samples) |
| 13 | Contractual & Third-Party Obligations | `contractual-third-party` | — | 0 (samples) |
| 14 | Capital & Infrastructure | `capital-infrastructure` | — | 0 (samples) |

Each vertical also carries a one-sentence description for its page header, written by the build agent and kept factual. Sample entries for the empty verticals are realistic titles for a distribution utility, for example:
- Financial & Reporting: "FERC Form 1 Preparation Procedure"
- Technology & Systems: "Customer Data Privacy & Security Policy"
- Supply Chain & Procurement: "Supplier Qualification Procedure"
- Capital & Infrastructure: "Substation Capital Project Approval Standard"

Each sample has an owner drawn from the 27 people, and the status "Not monitored".

---

## 6. Data layer

### 6.1 Three data domains, all mocked in this phase

| Domain | Backend today (reference only) | Source in this phase |
|---|---|---|
| **KB**: agencies, regulations, actions, diffs, version history | Exists on `main` (FastAPI): `/regulations`, `/actions`, `/diff`, `/timeline`, `/search`, `/impact`. **Not called.** | `mock` |
| **Engine**: runs, changes ledger, candidates, findings, rollups, matrix, radar, what-if, scores, reader | Not built yet (`/engine/*`; contract will be `api_ui.md`) | `mock` |
| **Company**: documents, clauses, people, attributes | Neon `company.*`, no HTTP endpoints yet | `mock` (fixtures built from the corpus, §6.4) |

There is no environment configuration, no rewrites and no network access to the backend. The mock layer is the only data source, and the app works fully offline.

### 6.2 The `StrataApi` interface
One TypeScript interface, grouped by domain (`kb`, `engine`, `company`), with one implementation in this phase (`mock/`).
- Components and hooks only see the interface, through `lib/api/queries.ts`.
- `lib/api/client.ts` is the single place that chooses the implementation.
- Wiring the backend later means adding a `live/` implementation that returns the same zod-validated shapes, and changing that one place. Pages, hooks and components do not change.
- Do not create `live/` or any fetch code now.

Mock behavior:
- 150–400 ms artificial latency, so loading states are real.
- Mutations (reviews, scenarios, runs) are kept in memory and mirrored to `sessionStorage`. Wrap storage access in try/catch.
- A what-if run on a **preset** completes instantly (it already has a `last_run_id`). A **custom** run advances through the five stages over about 8–10 seconds, so the stepper and polling are exercised.

### 6.3 Contract (zod schemas)
Field names follow the brief exactly. Items marked **(A#)** are the backend additions from brief §9. Items marked **(B#)** are further asks from this spec (§14). Treat both as provisional until `api_ui.md` lands.

**Run**
- `run_id`, `kind` (`kb` | `baseline` | `whatif`), `title`, `status` (`queued` | `running` | `succeeded` | `failed`), `started_at`, `finished_at`, `scenario_id?`
- `progress?` **(A4)**: `{stage, done, total, message}`, where `stage` is one of `delta | characterize | candidates | judge | ledger`
- `stats` (the funnel):
  - `changes_raw`
  - `by_class{<change_class>: n}`
  - `substantive`, `noise`
  - `in_footprint`, `obligation_changed`
  - `candidates_by_path{<match_path>: n}`
  - `findings_by_verdict{<verdict>: n}`
  - `clauses_cleared`
  - `docs_flagged`, `docs_cleared`
  - `radar{applicable, screened_out, unclear}`
  - `decided_by{rule, ai}`, `llm_calls`

**ChangeRecord** (one per changed regulation section)
- `change_id`, `citation`, `heading`, `source_system`, `rule_key`, `agency_id` (A3), `title_number` (A3)
- `change_class` (§11.1)
- `diff_segments[]`: `{op: equal | delete | insert, text}`
- `published_date`, `date_basis`, `din?`, `s1_snapshot`, `s2_snapshot` (A5)
- `in_footprint`, `cited_clause_count`
- `characterization?`: `{obligation_changed, direction, summary, value_changes[{label, old, new, unit?}]}`
- `disposition`, `disposition_reason`

**Candidate** (one change × clause pair checked)
- `candidate_id`, `change_id`, `clause_id`, `doc_id`
- `match_path`, `path_detail`: an ordered list of nodes `{kind: section | rule | register_row | form_field | tariff_rule | clause, ref, label}`
- `outcome`: `affected` | `cleared`
- `skip_reason?`, `rationale?`, `finding_id?`

**Finding**
- `finding_id`, `run_id`, `change_id`, `clause_id`, `doc_id`, `citation`
- `finding_type`, `verdict`, `severity` (`high` | `medium` | `low`), `confidence` (0–1), `decided_by` (`rule` | `ai`)
- `required_change {from_text, to_text}`
- `quotes {s1, s2, clause}`: each `{text, span?: [start, end]}`
- `quotes_verified`, `rationale`
- `match_path`, `path_detail`, `propagated_from?` (another finding_id)
- `stale_at_approval`, `doc_approved_date` (A5), `rule_published_date`
- `route {owner, reviewer, approver?}`: each a Person
- `reviews[]`: `{decision: accept | reject, note?, at}`

**DocRollup**
- `doc_id`, `status` (`flagged` | `cleared`), `counts_by_verdict`, `changes_considered`, `cleared_reason?`

**RadarItem**
- `radar_id`, `change_id`, `citation`, `heading`, `agency_id`
- `applicable` (`yes` | `no` | `unclear`)
- `attribute_basis[]`: `{key, value}`
- `affected_activity`, `reason`, `quote`
- `docs_covering_same_rule[]` (doc_ids)

**Scenario**
- `scenario_id`, `title`, `citation`, `source_system`
- `edit_kind` (`text_edit` | `repeal`), `edited_text?`
- `is_preset`, `last_run_id?`

**ScoreReport**
- `precision`, `recall`, `fp_rate_must_not_flag`, `routing_accuracy`
- `targets {precision: 0.80, recall: 0.83, fp_rate: 0, routing: 0.80}`
- `baseline_findings` (expect 0)
- `decided_by {rule, ai}`, `llm_calls`

**Reader** (A1): `doc` (DocumentMeta) + `clauses[]` + `annotations[]`
- Clause: `{clause_id, ordinal, heading_path[], unit_kind, text_raw, row_cells?, parent_clause_id?}`
- Annotation: `{clause_id, kind: finding | cleared, verdict?, finding_id?, change_id, citation, quote_span?, reason}`

**Matrix** (A2): `docs[]`, `changes[]` (in-footprint; noise columns only when `include_noise`), `cells[{doc_id, change_id, worst_verdict | 'cleared', n_findings, n_cleared}]`

**Company**
- DocumentMeta: `doc_id, title, version, status, effective_date, approved_date, law_as_of, next_review, review_cycle, vertical, owner, reviewer, approver?, two_signature: boolean, monitored: boolean`
- Person: `person_id, name, title, department, reports_to_id`
- CompanyAttribute: `key, value, source`

**KB**
- **Agency:** `agency_id, name, level, geo, domains[], codebook_titles[], section_count, action_count, s1_snapshot, s2_snapshot, last_sync_at, has_activity_feed`. The 610/675 codebook-only entries have `agency_id` null and `has_activity_feed` false.
- **CodeSection:** `citation, source_system, title_number, part_or_article, rule_key, section_number, heading, body_text, status (approved | repealed), snapshot_date, owning_agency, amendment_source?, federal_refs[], iac_cross_refs[]`
- **RegulatoryAction:** `source_system, source_id, agency, action_type, status, date_published, title, abstract, cfr_references[], legal_refs[], docket_ids[], rin?, din?, source_url, related[{source_id, relationship_type: related_to | supersedes | corrects}]`

Model the mock KB methods on the existing endpoints on `main`, read from `backend/app/api/regulatory/*.py` for reference only, so a later live implementation maps one-to-one:
- `GET /regulations?source_system&agency&jurisdiction_level&status&search&page&limit≤200`
- `GET /regulations/{source_system}/{citation}`
- `GET /actions?source_system&agency&status&action_type&date_from&date_to&search&page&limit≤200`
- `GET /actions/{source_system}/{source_id}`
- `GET /diff/{source_system}/{citation}`: version history
- `GET /diff/{source_system}/{citation}/compare?date_a&date_b`: raw line diff
- `GET /timeline/{source_system}/{citation}`

Keep pagination parameters in the mock method signatures even though fixtures are small.

### 6.4 Fixtures

All fixtures are committed JSON under `frontend/fixtures/`. The app reads nothing else.

**Company fixtures** are generated once by `frontend/scripts/build-fixtures.ts`. It reads these corpus files in `../backend/app/company/` **read-only** and writes JSON to `frontend/fixtures/company/`. Re-run it manually if the corpus changes; never wire it into `build`, `dev` or CI.
- `corpus/_global/document_register.csv`: document metadata (skip `RPL-INF-*`).
- `corpus/_global/people_directory.csv`: people.
- `corpus/_global/company_profile.yaml`: company attributes, e.g. `owns_generating_units=false`, `has_gas_operations=false`, standby generator count.
- `corpus/docs/<doc_id>/<doc_id>_v*.md`: front matter plus body, segmented into clauses:
  - Headings become `heading_path`.
  - Numbered sections become `section` clauses with ids like `RPL-CS-PRO-004:8.2`.
  - Markdown tables become `table_row` clauses with `row_cells`.
  - The `App-*` form blocks become `form_field` clauses.
  - Tariff rules become `tariff_subrule` clauses.
  - Appendices become `appendix` clauses.
- `corpus/docs/<doc_id>/data/*.csv` for the three registers: `register_row` clauses with `row_cells` and ids like `RPL-CMP-REG-001:OBL-2024-0047`.

Later, a JSON export of `company.clauses` from the backend owner (ask B1) can replace the generated clauses, since it carries the real clause ids. Do not request or wait for it in this phase. Either way, clause ids in engine fixtures must exist in the company fixtures.

**KB fixtures** are hand-authored, with real citations where the repo provides them:
- **Agencies:** FERC, EPA, IURC and IDEM, plus the 610 and 675 codebook-only entries. Counts and snapshot dates come from `frontend_development_docs/reference/kb_audit_government.html` (e.g. 170 IAC: 647 sections; Federal Register: 990 actions; IURC: 42 orders, 138 investigations, 19 rulemakings; IDEM: 17 rulemakings).
- **Sections:** the full set of citations RPL actually cites (parsed from the documents' `regulatory_basis` front matter and in-text citations), plus about 20 representative sections per other codebook title, so every agency tree has depth.
  - Body text is short placeholder text with `"placeholder": true`.
  - Mark some sections as repealed so the toggle has something to hide.
- **Actions:** about 8–15 per stream. They are plausible but invented, carry `"placeholder": true`, and include at least one supersedes and one corrects chain.
- **Version history:** two entries (S1, S2) for every changed section in the engine fixtures.

Placeholder flags never render in the UI. They exist so that whoever wires the backend later can find every invented value.

**Engine fixtures** are hand-authored, internally consistent and invented (see the information barrier in §0).

Run `kb-real` ("Real wave · S1→S2"):
- `changes_raw` 1,114 = `substantive` 491 + `noise` 623.
- Noise splits into cosmetic 590 + metadata_only + punctuation_only + cross_ref_only, which must sum to 623.
- `in_footprint` 8, across RPL-REG-CAL-2025, RPL-CS-PRO-011 and RPL-CS-PRO-004. Pick citations from those documents' `regulatory_basis` front matter.
- **0 findings** that require action. `clauses_cleared` 162.
- One cosmetic change has `cited_clause_count` 94, all cleared with reasons.
- One style rewording ("shall not" → "may not") is cleared as "same legal effect".
- Radar: applicable a small number (include a 326 IAC item justified by `standby_generator_count = 3`), screened out the majority (include the EPA turbine rule screened out by `owns_generating_units = false`), plus a few unclear. The substantive changes outside the footprint should total about 483.

Run `baseline` ("Baseline · S1 vs S1"): 0 changes, 0 findings.

Presets (instant, SIMULATED):
- **Preset A**, "170 IAC 4-1-x: notice period 10 → 15 days". It produces findings in RPL-CS-PRO-004 (procedure sections **and** a notice-letter form field in App-A), RPL-CMP-REG-001 (an obligation row) and RPL-REG-CAL-2025 (a calendar event).
  - The findings mix verdicts (`action_required`, `update_citation`, `review`, `info`) and paths (`direct_section`, `direct_rule`, `register_hop`, `value_echo`).
  - At least one finding carries `propagated_from`, giving the chain register row → procedure → form field.
  - At least one is `decided_by: ai` with confidence 0.82. At least one has `quotes_verified: false`. At least one has `stale_at_approval: true`.
- **Preset B**, "Repeal 170 IAC x-y-z". Its findings are mostly `update_citation` / `review`.

Score report: values on or above target, with baseline 0 findings.

Section text (S1/S2) for in-footprint and preset sections is hand-authored. It must be long enough for the diff, collapse and quote-highlight features to be exercised (several paragraphs for at least one section), and it carries `"placeholder": true`. `diff_segments` must be consistent with the S1 and S2 text: generate them in the fixture script with jsdiff, not by hand.

**Invariants** are checked by a Vitest suite over the fixtures:
- Funnel sums add up.
- Every `clause_id` and `doc_id` referenced exists.
- `findings_by_verdict` matches the findings list.
- Every candidate has an outcome and, if cleared, a reason.
- The matrix cells agree with the candidates.
- Sample (unmonitored) docs never appear in engine fixtures.

**The UI never hardcodes a number.** Every count comes from `run.stats` or derived lists.

### 6.5 Run context
- `?run=<run_id>` lives on every `/app` URL. Missing means the latest `kb` run. Every internal link preserves it (`<AppLink>` helper).
- `RunContext` exposes `run` and `isSimulated` (`kind === 'whatif'`). It feeds the RunSelector, the SimulatedBanner and query keys (every engine query key includes `run_id`).
- While `run.status === 'running'`, poll the run (`api.engine.getRun`, the future `GET /engine/runs/{id}`) every 2 s. When the run succeeds, invalidate that run's queries. In this phase the mock advances the run's stages over time, so polling is real.

---

## 7. Global UX rules

### 7.1 Principles (from the brief; non-negotiable)
1. **Clause, not document.** No document-level "non-compliant" without one click to the exact clause and the exact words.
2. **Evidence beside the verdict.** Every verdict sits next to its proof: old rule, new rule and clause text, with the matching words highlighted.
3. **Show the noise you removed.** Cleared items and noise classes are a feature. They are collapsed by default, always one click away, and always come with a reason.
4. **Trust signals are first-class:**
   - `Verified quote ✓`
   - `Decided by rule`, or `AI judgment · 82%`
   - `Evidence unverified — review`
   - "Why this clause was found", the match path in plain words.
5. **One semantic language everywhere.** A verdict maps to one token that is reused in pills, document highlights, minimap ticks, matrix cells and funnel bars (§17.2).
6. **Plain English first, legal text second.** Lead with a sentence ("Clause states 10 business days; the rule now requires 14."), then show the text.
7. **Calm, dense, professional.** No decorative motion. Transitions only where they aid orientation (drawer open, highlight pulse).
8. **Not overwhelming for a first-time user.** One primary action per screen. Progressive disclosure: collapsed groups and drawers rather than more pages. Consistent list → detail patterns. Breadcrumbs below the top level. Every count is clickable to the filtered list it summarizes.

### 7.2 Page states (every data view implements all that apply)
- **Loading:** skeletons shaped like the content. No spinners on full pages.
- **Empty:** explain why, and offer the next useful action. Never a blank panel. The Overview's empty real wave is a *success* state (§9.1).
- **Error:** a plain sentence, a retry, and which data source failed.
- **Running:** the stage stepper or progress in context. Pages that read the run show "Results will appear when the run finishes".
- **Simulated:** a persistent banner ("SIMULATED — What-if: <title>. These results are not real regulatory changes.") with a "Back to real wave" action. The RunSelector in the page header shows the "Simulated" tag.
- **Not monitored** (sample docs): a status pill and a disabled "Start monitoring" button. No reader link.

### 7.3 Keyboard
- `⌘K` / `Ctrl K`: global search.
- In the reader: `j`/`k` or `↓`/`↑` for the next and previous finding, `Enter` to open the evidence drawer.
- `Esc` closes the drawer.
- In the change diff: `n`/`p` for the next and previous change.
- `?` shows a shortcuts sheet.

### 7.4 Accessibility
- Diff deletes and inserts are never shown by color alone: strikethrough for deletions, underline for insertions.
- Every pill has text, not just a color.
- Focus is visible. The drawer traps focus and returns it on close.
- Highlights carry `aria-describedby` pointing to their reason.
- Tables use proper headers. The matrix headers have full-text tooltips and `aria-label`s.

### 7.5 Responsiveness
Desktop-first (≥1280 px). Usable on tablet (≥768 px): the rails collapse into toggled panels. Mobile is not required for `/app`. The marketing page must be fully responsive.

### 7.6 Future-capability cues
Rendered by `<FutureCue id="…" />` from the registry in `lib/future-features.ts`. Rules, variants and the full catalog are in §18. Nothing outside that catalog may be stubbed.

---

## 8. Information architecture

### 8.1 Route map

| Route | Page | Nav group |
|---|---|---|
| `/` | Marketing landing | — |
| `/app` | Overview | Analysis |
| `/app/changes`, `/app/changes/[changeId]` | Changes | Analysis |
| `/app/documents` | Documents board (14 verticals) | Analysis |
| `/app/documents/verticals/[vertical]` | Vertical page | (under Documents) |
| `/app/documents/[docId]` | Document reader | (under Documents) |
| `/app/findings/[findingId]` | Evidence card (full page) | — |
| `/app/matrix` | Impact matrix | Analysis |
| `/app/radar` | Radar | Analysis |
| `/app/what-if`, `/app/what-if/[scenarioId]` | What-if studio | Analysis |
| `/app/trust` | Trust scorecard | Analysis |
| `/app/regulations` | Agencies overview | Knowledge base |
| `/app/regulations/[agencyId]` | Agency page | (under Regulations) |
| `/app/regulations/sections/[sourceSystem]/[...citation]` | Regulation section | (under Regulations) |
| `/app/regulations/actions/[sourceSystem]/[...sourceId]` | Regulatory action | (under Regulations) |
| `/app/company` | Company profile & people | Knowledge base |

The evidence card also opens as a drawer on any page via `?finding=<findingId>`. The full page and the drawer share one component.

### 8.2 Shell
There is no top bar; the layout follows Harvey (§17.5).
- **Sidebar:**
  - **Header:** the "Strata" wordmark (links to `/app`), a search icon button (opens ⌘K; placeholder "Search doc id, clause id, citation…") and the notifications future cue.
  - **Analysis:** Overview · Changes · Documents · Impact Matrix · Radar · What-if · Trust
  - **Knowledge base:** Regulations · Company
  - **Recents:** the last 4 visited items.
  - **Coming soon:** future cues (§18.2).
  - **Footer:** the company chip with the workspace-switcher cue.
  - Badges: Documents shows the number of documents needing action in the current run. Changes shows the in-footprint count. Badges are small neutral counts; the documents-needing-action badge is red-soft when above zero.
- **RunSelector:** a select control (`Real wave · S1→S2 ▾`) at the right of every analysis page header (`Baseline`, `What-if: <title>` and each run's status in the menu). Knowledge-base pages show it too, since change badges depend on the run.
- **SimulatedBanner:** pinned to the top of the main area whenever `isSimulated`.
- **Breadcrumbs** on every page below the top level, e.g. `Documents › Policy & Governance Documents › RPL-CS-PRO-004`.

### 8.3 Global search (cmdk)
- Results are grouped as **Documents** (doc id, title), **Clauses** (clause id plus a heading snippet), **Changed sections** (citation, heading, class), **Regulations** (KB sections and agencies) and **People**.
- Matching is exact or prefix for ids and citations, fuzzy for titles. All matching runs client-side over an index built from the fixtures. Full-text semantic search over regulation text (the backend's `/search`) is a later integration and gets no placeholder.
- Selecting a result navigates there, keeping `?run=`.

### 8.4 Future-capability cues
See §18.2 for the complete per-page catalog. That catalog replaces the earlier list of future buttons.

---

## 9. Page specs

Each page lists **Purpose · Data · Layout and contents · Interactions · States · Acceptance**.

### 9.0 Marketing landing (`/`)
**Purpose.** Explain the product in under a minute and get the visitor into the demo.

**Contents**, in order:
1. **Hero.** One-line value statement (e.g. "Know exactly which clauses a regulatory change affects — and why."), a one-sentence subhead, and a primary CTA "Open the demo" → `/app`.
2. **The problem.** Regulations change constantly, most changes are noise, and the real ones hide inside long rules and long company documents.
3. **How it works:** six short steps mirroring §1. Detect changes → Remove noise → Find dependent clauses → Judge each clause → Prove it with verified quotes → Route to owners. Add the line "Flags, never edits. Proves what it cleared."
4. **Coverage.** Agencies (FERC, EPA, IURC, IDEM) with "more coming", and the 14 verticals.
5. **Trust.** Precision, recall and baseline 0, as described claims. In this phase describe the method without figures. The scores in the fixtures are mock values and must not appear on the marketing page.
6. **Product preview.** A static screenshot of the reader and the evidence card, captured from the running app.
7. **Closing CTA.**

**Acceptance.** Responsive down to 360 px. No invented customer logos or testimonials. A single CTA target.

### 9.1 Overview (`/app`): "The wave at a glance"
**Data:** `run.stats`, top findings (by severity, then verdict), doc rollups, score report.

**Layout and contents**
1. **Funnel (hero).** Horizontal bars, one per stage:
   `changes_raw → substantive (noise beside it, split by class with a legend) → in_footprint → obligation_changed → findings`
   - Beside it, a prominent "**N clauses checked and cleared**" figure.
   - Each bar is a link to a filtered view (substantive → Changes "Substantive only"; noise → Changes with noise classes; in-footprint → Changes "Touches RPL"; findings → Documents filtered; cleared → Changes ledger "Cleared").
   - Noise bars use the noise token family.
2. **Tiles:** documents flagged vs cleared · findings by verdict · Radar "possibly applicable" count · Trust mini (precision / recall / FP / baseline ✓). Each tile links to its page.
3. **"Needs your attention."** Up to 7 findings, each a one-line plain-English sentence (§11.4) plus a doc chip and a VerdictPill. Clicking opens the evidence drawer.
4. **Empty real wave** (0 findings): do not show an empty state. Instead:
   - Headline: "No clause needs action."
   - Subline: "162 clauses checked across 3 documents — see why." It links to the cleared ledger.
   - Secondary CTA: "Try a what-if change" → `/app/what-if`.

**States:** a running run shows the stepper in place of the funnel. Simulated shows the banner, and the funnel uses the what-if run.

Future cues: §18.2.

**Acceptance**
- Funnel numbers equal `run.stats`.
- Every bar and tile navigates to the filtered destination with `?run=` kept.
- The empty real wave shows the success copy.

### 9.2 Changes (`/app/changes[/changeId]`): "What changed in the law"
**Data:** change records for the run, plus candidates for the selected change, plus the raw line diff from `api.kb.compare`.

**Layout:** resizable master–detail.

**Left: tree.** Agency → Title → Rule → Section, built client-side from `agency_id`, `title_number` and `rule_key` (A3).
- Count badges at every level.
- Filter chips:
  - **Touches RPL** (default on)
  - **Substantive only** (default on)
  - **Show noise**
  - one chip per change class
- A section row shows citation (mono), heading, ClassPill, published date and "cited by N clauses".
- Filters live in the URL.

**Right: change detail.**
1. **Header:** citation, heading, agency. Then the plain-English `characterization.summary`, a **direction chip** (tightened / relaxed / new requirement / removed / clarified / style only) and **value-change chips** (`10 → 14 business days`).
2. **Version timeline strip:** S1 snapshot date ● → publication date ● (DIN shown) → S2 snapshot date ●.
3. **DiffView**, toggling between:
   - **Inline redline** (default).
   - **Side-by-side**: S1 left, S2 right, synchronized scrolling.

   It collapses unchanged runs longer than 300 characters ("… 1,240 unchanged characters …", expandable) and has a "Change 1 of 3 ↑↓" navigator.
   For noise classes: a neutral explanation banner ("Only the readoption stamp changed") and a **Show raw diff** toggle that loads the line diff (`api.kb.compare`, modeled on `/diff/{ss}/{citation}/compare`).
4. **Impacted clauses (the ledger for this change).** Every candidate, grouped by outcome: findings by verdict first, then **Cleared (n)**, collapsed, each with its reason.
   - Each row: clause id, doc chip, match-path icon and a one-line reason.
   - A finding row opens the evidence drawer. A cleared row links to the clause in the reader.
5. A link to the KB section page: "Open full regulation".

**States:**
- With no selection, the detail pane shows a short guide and the 3 most-cited changes.
- If filters hide everything: "No changes match these filters" with a reset.

Future cues: §18.2.

**Acceptance (demo):**
- Opening the 94-clause cosmetic change shows the neutral banner, a stamp-only diff and "Cleared (94)" with reasons.
- The "shall not → may not" change shows the direction "style only" and is cleared.

### 9.3 Documents board (`/app/documents`) and vertical page
**Purpose.** The company-data landing page: every vertical, every document, and its status in this run.

**Board**
- 14 **VerticalSection**s in the fixed order of §5.3. Each header shows the vertical name, document count, and a needs-action count; clicking the header opens the vertical page.
- Inside each section, **DocCard**s show:
  - title, doc id, version
  - owner (PersonChip)
  - **status pill**: Action needed / Review / Cleared (§11.5)
  - a **verdict mini-bar** (counts per verdict)
  - for cleared docs, the one-line reason ("3 changes considered: 2 cosmetic, 1 style-only")
  - "Two-signature document" where applicable
- Sample docs in empty verticals render as compact rows with a "Not monitored" pill, owner, and a disabled "Start monitoring" button.
- Filters (URL): status, vertical, owner. Sort: needs action first.
- Future cues: §18.2.

**Vertical page** (`/app/documents/verticals/[vertical]`)
- Header: name, one-sentence description, counts.
- Table (TanStack): doc id, title, type, version, owner, next review, status, findings. Flagged rows sort first.
- Empty vertical (samples only): explain that these documents are not yet monitored.
- Future cues: §18.2.

**Acceptance**
- All 14 verticals render.
- Sample docs never link to a reader.
- Status pills match the rollups.
- In Preset A, the Disconnection Procedure, Obligations Register and Calendar show Action needed or Review.

### 9.4 Document reader (`/app/documents/[docId]`): the most important screen
**Data:** Reader (A1) for the current run, plus findings for the document.

**Header**
- Title, doc id, version, effective / approved / law-as-of dates.
- Status pill and the rollup sentence.
- **RouteChips**: owner → reviewer → approver with names and titles, or "Two-signature document".
- Future cues: §18.2.

**Center: the document**, rendered from clauses in `ordinal` order by **ClauseRenderer**:
- Headings come from `heading_path`, de-duplicated so consecutive clauses don't repeat headings.
- `section`: paragraphs in the document serif.
- `register_row` / `table_row`: real table rows from `row_cells`, grouped into one table per parent with a header row.
- `form_field`: a labeled field inside an "Appendix / Form" block, so a notice letter reads like a letter.
- `tariff_subrule`: text with a sheet/rule label.
- `appendix`: a titled block.

**Overlays**
- **Affected clause:** a left border in the verdict token, with the exact `quote_span` highlighted inline.
- **Cleared clause:** a subtle ✓ gutter marker. Hover: "Checked: no impact — cosmetic change to <citation>".
- **Unchecked clause:** no marker.

**Right rail: FindingsRail**
- Findings in document order. Each item: VerdictPill, clause id, plain-English sentence, citation.
- Clicking (or `Enter`) scrolls to the clause, pulses its highlight and opens the evidence drawer.
- `j`/`k` and `↑`/`↓` move between findings.
- A collapsed **"Cleared (n)"** group sits at the bottom.

**Minimap:** a slim track along the right edge with ticks at each finding's relative position (ordinal ÷ count) in the verdict token. Clicking a tick scrolls there.

**P2:** clicking any clause opens a popover with its citations, extracted values (deadlines, periods, amounts) and defined terms. Defined terms in the text show their definition on hover.

**States**
- If the document wasn't in the run's footprint: "No change in this run touched this document" plus the list of rules it cites.
- Long documents are virtualized; scroll-to-clause must work with virtualization.

**Acceptance (demo, Preset A on RPL-CS-PRO-004):**
- Minimap ticks are visible.
- `j`/`k` steps through findings.
- One finding lands on a notice-letter form field rendered as a letter.

### 9.5 Evidence card (drawer via `?finding=`; page `/app/findings/[findingId]`): "Why this clause is out of line"
1. **Verdict sentence** (most prominent): built from `required_change` and the citation (§11.4).
   - Example: "§8.2 states **10 business days**; 170 IAC 4-1-x now requires **15 business days**."
   - Badge row: VerdictPill · severity · `Decided by rule` or `AI judgment · 82%` · `Verified quote ✓` (or `Evidence unverified — review`).
2. **Three-pane evidence:**
   - **Old rule (S1)** with its quote highlighted.
   - **New rule (S2)** with its quote highlighted and diff marks.
   - **Clause** with its quote highlighted.
   
   A toggle merges the two rule panes into one inline redline.
3. **Required change:** a `from → to` chip, labeled "**Suggested update — not applied**".
4. **Why this clause was found: TraceChain.** A horizontal chain built from `match_path`, `path_detail` and `propagated_from`, e.g. `170 IAC 4-1-x → Obligation register row OBL-2024-0047 → Disconnection Procedure §8.2 → Notice letter field App-A.F4`. Every node is clickable (KB section, register row in the reader, clause in the reader). Caption: "Fix once, fix everywhere."
5. **Also affected by this change:** sibling findings across documents (doc chip, clause id, verdict). Each opens its own card.
6. **Timeline**, only when `stale_at_approval`: rule published ● before document approved ●, with the caption "This document was already out of date when it was approved."
7. **Routing and review:**
   - RouteChips.
   - **Accept** / **Reject** buttons. Reject requires a note.
   - The review history is listed.
   - Mock mode persists reviews in the session.
   - Future cues: §18.2.

**Acceptance**
- No section renders without its data.
- The trace chain matches `path_detail`.
- Reject without a note is blocked.
- The drawer URL is shareable and reopens the same card.

### 9.6 Impact matrix (`/app/matrix`)
- **Grid:**
  - Rows: the 12 monitored documents, grouped by vertical.
  - Columns: the in-footprint changed sections. Headers are citations (truncated or rotated) with a tooltip giving heading and class.
- **Cells:**
  - a verdict-token dot with a count (worst verdict wins);
  - a neutral ✓ when all candidates are cleared;
  - empty when the document doesn't cite the section.
- Clicking a cell opens a popover listing the findings and cleared candidates for that doc × change. Items link to the evidence card or the reader.
- Toggle (URL): **Show noise columns**.
- A legend for the cell states.
- Read-only.
- Future cues: §18.2.

**Acceptance**
- In the real wave, no cell shows action-required, and the ✓ cells show where checking happened.
- In Preset A, the three demo docs light up.

### 9.7 Radar (`/app/radar`): "Changes your documents don't cite"
- Header copy: "**Advisory.** These are not tied to any clause."
- **Tabs:** Possibly applicable · Screened out · Unclear, each with a count.
- **Possibly applicable item:**
  - citation and heading
  - attribute-basis chips (e.g. `standby_generator_count = 3`), each linking to the Company profile
  - an affected-activity sentence, the reason, and the S2 quote
  - "Docs covering the same rule" chips
- **Screened out item:** a reason line (e.g. "owns_generating_units = false").
- Future cues: §18.2.

**Acceptance:** the demo's 326 IAC standby-generator item appears under Possibly applicable, and the EPA turbine rule appears under Screened out.

### 9.8 What-if studio (`/app/what-if[/scenarioId]`)
- **Left column:**
  - **Preset cards** (pre-run, marked "instant"), e.g. "170 IAC 4-1-x: notice period 10 → 15 days" and "Repeal 170 IAC x-y-z".
  - Below them, a **section picker** listing the sections RPL cites, sorted by "cited by N clauses", with search.
- **Center: editor.**
  - The S1 text in a textarea.
  - A **live client-side diff preview** below it (jsdiff, same rendering as DiffView inline).
  - A **"Repeal this section"** toggle that disables the editor.
  - Scenario title field.
- **Run impact →** shows the **StageStepper**: Delta → Characterize → Candidates → Judge → Ledger. Counts appear as each stage finishes (from `run.progress`), and it polls every 2 s.
- On success: **Open results**. This switches `?run=` to the what-if run and goes to Overview in SIMULATED mode.
- Presets run instantly: clicking one goes straight to results.
- Future cues: §18.2.

**Acceptance**
- A custom edit shows the diff preview live, and Run shows stage progress, then results.
- Every analysis page renders the what-if run with the SIMULATED banner.
- "Back to real wave" restores the `kb` run.

### 9.9 Trust (`/app/trust`)
- Four big figures: precision, recall, false-positive rate on the must-not-flag set, and routing accuracy. Each shows its target (≥0.80, ≥0.83, 0, ≥0.80) and a pass/fail mark.
- "**Baseline: S1 vs S1 → 0 findings ✓**" (links to the baseline run).
- **Method**, as four bullets:
  - Only changes are evaluated.
  - Noise classes never reach AI.
  - Every finding carries verified quotes.
  - Every change has a recorded outcome.
- Counts: decided by rule vs AI, and LLM calls.
- Future cues: §18.2.

### 9.10 Regulations: agencies overview (`/app/regulations`)
**Purpose.** Show which government sources Strata monitors (the owner's "government data landing page").

- **Federal** section: FERC and EPA cards. **State · Indiana** section: IURC and IDEM cards, plus codebook-only cards for **610 IAC — Labor** and **675 IAC — Fire & Building Safety**.
- **Card contents:**
  - agency name and level
  - codebook titles/parts (e.g. "170 IAC")
  - section count and action count
  - snapshot dates (S1 → S2)
  - last sync
  - "N changed in this run" (links to Changes filtered to that agency)
- Future cues (§18.2): an "Add agency" card ends each section, "Add jurisdiction" sits in the page header, and a compact "More source types" row sits below the agencies.
- Data: `api.kb.listAgencies()` from fixtures. Future endpoint: B2.

### 9.11 Agency page (`/app/regulations/[agencyId]`)
- **Header:** name, level, domains, codebook titles, snapshot dates, last sync. Future cues: §18.2.
- **Tab "Rules in force":**
  - A tree: Title → Part/Article → Rule → Section.
  - Each section row shows citation, heading, and a "Changed in this run" badge with its ClassPill.
  - Repealed sections are hidden behind a toggle.
  - Search within the agency.
  - Data: `api.kb.listSections({agency})` from fixtures. Future endpoints: `/regulations?agency=` or B3.
- **Tab "Activity":**
  - Actions with **stream chips** (FERC/EPA: Federal Register; IURC: Orders · Investigations · Rulemakings; IDEM: Rulemakings).
  - Filters: action type, status, date.
  - Data: `api.kb.listActions({agency, source_system})` from fixtures. Future endpoint: `/actions`.
- Codebook-only cards (610/675) open the same page with the Activity tab disabled and the caption "No activity feed tracked".

### 9.12 Regulation section (`/app/regulations/sections/[ss]/[...citation]`)
- Citation, heading, agency, status (approved / repealed), snapshot.
- The full text in the document serif, with an outline for long text. Bodies can reach ~150k characters, so sections are collapsible.
- A **snapshot switcher** and a "Compare S1 ↔ S2" DiffView. Version history and the comparison come from the mock KB methods modeled on `/diff/{ss}/{citation}` and `/diff/{ss}/{citation}/compare`.
- **Amended by:** a link to the amending action (`amendment_source`).
- **Cross-references:** federal and IAC cross-refs as links.
- **Cited by RPL:** clauses and documents citing this section, grouped by vertical (from the company fixtures' citations; future endpoint B4).
- If the section changed in the current run: a callout "Changed in this run — view analysis" → Changes detail.

### 9.13 Regulatory action (`/app/regulations/actions/[ss]/[...sourceId]`)
- Title, type, status, agency, publication date, docket ids / RIN / DIN, abstract, and a source link (opens in a new tab).
- **Related actions:** the supersedes / corrects / related-to chain.
- **Sections affected:** `cfr_references` and the IAC links, as section links.

### 9.14 Company profile (`/app/company`)
- Company header: name, type (electric distribution, investor-owned), state, customers, regulator.
- **Attributes table** (key, value, source) from `company_profile.yaml`. These are the keys Radar cites, and each attribute has an anchor so Radar chips can link straight to it.
- **People:** a directory table (name, title, department), plus a simple reporting tree. Each person shows the documents they own, review or approve.
- Future cues: §18.2.

### 9.15 Global search
See §8.3.

**Acceptance:** typing `RPL-CS-PRO-004:8`, `170 IAC 4-1` or `Pierce` returns grouped results within 100 ms against the fixtures.

---

## 10. Component inventory

Brief components (required):

| Component | Responsibility |
|---|---|
| `VerdictPill` | A verdict (or `cleared`) → label + token. One component everywhere. |
| `ClassPill` | A change class → label + token. Noise classes use the noise family. |
| `DiffView` | Renders `diff_segments`. Modes: inline / side-by-side; collapse-unchanged; change navigator; raw-diff toggle. |
| `QuoteHighlight` | Highlights `span` or `text` within a body; supports a verdict token and `aria-describedby`. |
| `TraceChain` | Renders `path_detail` / `propagated_from` as clickable nodes. |
| `Minimap` | Tick track by relative position; click to scroll. |
| `EvidenceDrawer` | The §9.5 card in a Sheet; the full page reuses its body. |
| `FunnelBar` | One funnel stage: label, count, proportional bar, link. |
| `MatrixGrid` | Docs × changes grid with cell popovers. |
| `RunSelector` | Lists runs with kind, status and SIMULATED marker; writes `?run=`. |
| `SimulatedBanner` | The persistent what-if banner with "Back to real wave". |
| `RouteChips` | Owner → reviewer → approver, or the "Two-signature document" label. |
| `TrustBadges` | Verified quote, decided by rule / AI with confidence, unverified evidence. |

Additional components:
- **Shell:** `AppShell`, `Sidebar`, `TopBar`, `GlobalSearch`, `Breadcrumbs`, `AppLink` (preserves `?run=`).
- **Common:** `StatTile`, `EmptyState`, `ErrorState`, `FutureCue` (variants in §18.1), `PersonChip`, `AttributeChip`, `DocChip`, `CitationText`, `InfoStrip`, `PageHeader` (breadcrumbs, caption, serif title, actions, RunSelector), `Toolbar`.
- **Shell additions:** `Recents`, `CompanyChip`, `IconRail` (collapsed sidebar).
- **Engine:** `MatchPathIcon`, `DirectionChip`, `ValueChangeChip`, `StageStepper`, `TimelineStrip`, `LedgerList` (grouped findings / cleared), `ScoreFigure`.
- **Documents:** `VerticalSection`, `DocCard`, `SampleDocRow`, `DocStatusPill`, `VerdictMiniBar`, `ClauseRenderer` (one sub-renderer per `unit_kind`), `FindingsRail`.
- **KB:** `AgencyCard`, `AddAgencyCard`, `SectionTree`, `ActionList`, `StreamChips`.

---

## 11. Labels, tokens and sentences

### 11.1 Enumerations → labels

| Enum | Values → label |
|---|---|
| `verdict` | `action_required` → Action required · `optional_relaxed` → Relaxed (optional update) · `update_citation` → Update citation · `review` → Needs review · `info` → Info |
| candidate outcome | `cleared` → Cleared ("Cleared" is not a verdict) |
| `change_class` (real) | `substantive` → Substantive · `repealed` → Repealed · `renumbered` → Renumbered · `new_section` → New section |
| `change_class` (noise) | `cosmetic` → Cosmetic · `metadata_only` → Metadata only · `punctuation_only` → Punctuation only · `cross_ref_only` → Cross-reference only |
| `direction` | tightened → Tightened · relaxed → Relaxed · new_requirement → New requirement · removed → Removed · clarified → Clarified · style_only → Style only |
| `run.kind` | `kb` → Real wave · S1→S2 · `baseline` → Baseline · S1 vs S1 · `whatif` → What-if: <title> |
| `decided_by` | `rule` → Decided by rule · `ai` → AI judgment · <confidence as %> |
| `applicable` | yes → Possibly applicable · no → Screened out · unclear → Unclear |
| action streams | `federal_register` → Federal Register · `iurc_gaos` → Orders · `iurc_investigations` → Investigations · `iurc_rulemakings` / `idem_rulemakings` → Rulemakings |

### 11.2 Match paths (icon + plain words)

| `match_path` | Icon (lucide) | Plain words |
|---|---|---|
| `direct_section` | `link` | "Cites this section directly" |
| `direct_rule` | `book` | "Cites the parent rule (<rule_key>)" |
| `register_hop` | `git-branch` | "Linked through <register row / form / tariff rule ref>" |
| `value_echo` | `repeat` | "Restates the old value (<old value>) without citing it" |

### 11.3 Semantic tokens (values and rendering in §17.2)
- Verdicts: `--verdict-action-required`, `--verdict-optional-relaxed`, `--verdict-update-citation`, `--verdict-review`, `--verdict-info`, `--state-cleared`.
- Noise: `--noise`.
- Diff: `--diff-delete`, `--diff-insert`. Always paired with strikethrough and underline.
- Simulated mode: `--simulated`.
- Type roles: `--font-ui` (sans), `--font-document` (serif, for legal and company text), `--font-mono` (citations, clause ids).

**Rule:** one map from verdict → token, used by every component (pill, border, highlight, tick, cell, bar). No component chooses its own color.

### 11.4 Sentence builders (`lib/sentences.ts`)
- **Finding sentence:** `"<clause label> states <from_text>; <citation> now requires <to_text>."`
  - Repeal: `"<clause label> relies on <citation>, which was repealed."`
  - `update_citation`: `"<clause label> cites <old citation>; the rule is now <new citation>."`
  - Fallback: `characterization.summary`.
- **Cleared reason:** `"Checked: no impact — <class label lowercased> change to <citation>."`, or the backend's `skip_reason`/`rationale` when present.
- **Doc cleared line:** `"<n> changes considered: <k1> cosmetic, <k2> style-only…"`, built from the rollup.
- `<clause label>`: `§<local id>` for sections, `row <id>` for register rows, `field <label>` for form fields, `rule <id>` for tariff sub-rules.

### 11.5 Document status derivation (`lib/status.ts`)
- `rollup.status === 'flagged'` and any `action_required` → **Action needed**.
- `rollup.status === 'flagged'` otherwise → **Review**.
- `rollup.status === 'cleared'`, or the document has no candidates → **Cleared**, with the reason line ("No cited section changed" when there are no candidates).
- `monitored === false` → **Not monitored**.

Confirm this mapping with the backend owner (B5).

---

## 12. Demo script (about 6 minutes; also the Playwright e2e suite)
1. **Overview (real wave):** "1,114 changes landed. Strata removed 623 as noise, found 8 that touch our documents, and checked 162 clauses." The success state appears with no findings.
2. **Changes:** open the cosmetic change cited by 94 clauses. Side-by-side shows that only a stamp changed: "94 clauses cleared, here's the proof." Open the "shall not → may not" change: style only, cleared.
3. **Matrix:** nothing requires action; the ✓ cells show where checking happened.
4. **What-if:** run Preset A, "notice period 10 → 15 days" (instant). The SIMULATED banner appears.
5. **Matrix / Documents:** the Disconnection Procedure, Obligations Register and Calendar light up.
6. **Reader:** open the Disconnection Procedure. Minimap ticks are visible; `j`/`k` through findings; one lands on a notice-letter form field.
7. **Evidence card:** the verdict sentence, three verified quotes, the trace chain register row → procedure → form field, and the route to the owner. Reject with a note.
8. **Radar:** the 326 IAC change applies "because you operate 3 standby generators".
9. **Trust:** the metrics and baseline 0.
10. *(Owner addition)* **Regulations:** the agencies with "Add agency"; open IURC → Activity → Orders.

---

## 13. Build order and milestones
Each milestone ends with lint, typecheck and unit tests green, plus its acceptance checks.

| M | Scope | Done when |
|---|---|---|
| M0 | Scaffold `frontend/` as a standalone project (§0.1, §5.1) with Next.js + TS + Tailwind + shadcn (Radix) + the libraries in §4, and a `frontend/README.md` covering run, test and deploy (Vercel Root Directory = `frontend`). The §17 design tokens and fonts. Shell (dark sidebar with Recents and the shell future cues, icon rail, PageHeader with breadcrumbs and RunSelector, SimulatedBanner). The `FutureCue` registry. zod schemas, the `StrataApi` interface, the mock adapter, fixture builder, fixture invariant tests, run context, labels, sentences, status | The shell renders. Switching `?run=` changes the banner. Fixtures pass the invariants. `git status` shows changes only under `frontend/`. `pnpm build` passes from inside `frontend/`. |
| M1 | Overview | §9.1 acceptance |
| M2 | Changes (tree + DiffView + ledger) | §9.2 acceptance |
| M3 | Documents board + vertical page + reader (ClauseRenderer, overlays, rail, minimap, keyboard) | §9.3–9.4 acceptance |
| M4 | Evidence card (drawer + page, reviews) | §9.5 acceptance |
| M5 | What-if studio (presets, editor with jsdiff preview, stepper, SIMULATED across the app) | §9.8 acceptance |
| M6 | Impact matrix | §9.6 acceptance |
| M7 | Trust | §9.9 |
| M8 | Radar | §9.7 acceptance |
| M9 | Knowledge base: Regulations overview, agency, section and action pages, Company profile (all from fixtures) | §9.10–9.14 |
| M10 | Global search, marketing landing, Playwright demo script (§12) green | §8.3, §9.0, §12 |

M1–M8 follow the brief's order. M9–M10 are the owner's additions.

---

## 14. Backend coordination (for later; not part of this phase)

Nothing in this section blocks the build. It records what the backend will need to provide when the frontend is wired up, so the mock shapes stay aligned.

**Brief §9 additions, confirmed as needed by this spec:**
- **A1** `GET /engine/documents/{doc_id}/reader?run_id=`
- **A2** `GET /engine/runs/{id}/matrix`
- **A3** `agency_id`, `title_number`, `rule_key` on ledger rows
- **A4** `runs.progress`
- **A5** `s1_snapshot`, `s2_snapshot` on changes, and `approved_date` on findings

**Further asks from this spec (B#):**

| # | Ask | Used by |
|---|---|---|
| B1 | A one-off JSON export of `company.clauses` (plus `row_cells`) for the 12 docs, or `GET /engine/documents/{doc_id}/clauses` | Reader fixtures with real clause ids |
| B2 | `GET /agencies` with codebook titles, section and action counts, snapshot dates and last sync (from `sync_state`). Include the 610/675 codebook-only entries. | Regulations overview |
| B3 | `GET /regulations/tree?agency=` (hierarchy with counts), or allow `limit` > 200 | Agency "Rules in force" tree |
| B4 | `GET /engine/citations/{source_system}/{citation}/clauses`: clauses citing a section | "Cited by RPL" on section pages |
| B5 | Confirm the document status mapping (§11.5) and the `severity` and `direction` enums | Pills and chips |
| B6 | Review endpoint: `POST /engine/findings/{id}/reviews {decision, note}` | Evidence card |
| B7 | What-if endpoints: list, create or update scenarios, `POST .../run` → `run_id` | What-if studio |
| B8 | Fix the brief's version-history route name (the real route is `GET /diff/{ss}/{citation}`) | Docs accuracy |
| B9 | `GET /engine/documents` (metadata, people, `two_signature`) and `GET /company/profile` | Board, profile |

---

## 15. Out of scope for v1 (do not build)
- Any backend integration in this phase: API calls, proxies, environment configuration for services, database, vector store or object storage access (§0.1).
- Any change outside `frontend/`.
- Chart or visualization libraries, graph or network visualizations.
- A document editor, or tracked changes on company documents. The product flags, it never edits.
- Chat or "Ask AI", notifications, user accounts, auth, roles.
- PDF or DOCX rendering of original documents.
- Quantified dataset impacts (operational CSVs).
- Compliance countdowns or effective-date timers (show publication dates only).
- Gradients, illustrations, stock imagery, emoji, colored icons, or any color outside §17.2.
- Harvey's name, logo, proprietary fonts or verbatim copy. The look is inspired by Harvey, never copied.

---

## 16. Open questions (non-blocking; defaults in parentheses)
1. Final names for the IAC 610 and 675 agencies. (Default: codebook-only cards labeled by title.)
2. Should the matrix include sample (unmonitored) documents as greyed rows? (Default: no.)
3. Is the Radar "Docs covering the same rule" computed by the backend or the client? (Default: backend field.)

---

## 17. Visual design system

### 17.1 Direction
The product must **feel like Harvey**: sharp, quiet, institutional. Think legal-grade software, not a startup dashboard. The reference screenshots the owner chose show four things:
- a near-black sidebar beside a warm off-white canvas;
- large serif page titles and big serif figures;
- hairline-bordered white cards and tables;
- a monochrome palette in which **color appears only to mean something**: red for problems, green for resolved or positive, and one muted warm tone for "needs attention".

Rules that follow from this:
1. **Monochrome first.** Everything is warm neutrals and ink. Status color is the only color.
2. **Typography carries the hierarchy**, not boxes or color: a serif for titles, figures and documents; a neutral sans for UI; a mono for ids.
3. **Hairlines, not shadows.** Separation comes from 1px borders and background steps. Shadows appear only on floating layers (popover, drawer, tooltip).
4. **No decoration:** no gradients, illustrations, emoji, glassmorphism, colored icons or marketing flourishes inside the app.
5. **Dense where data lives, generous around headings.** Tables and lists are compact. Page titles and the verdict sentence get air.
6. **Sentence case everywhere.** No all-caps, except the tiny "Soon" and "Simulated" tags.

**Reference screenshots:** `frontend_development_docs/reference/design/` holds four Harvey screenshots, plus a README mapping each one to Strata pages. Study them before building any UI. They are the target for overall feel; this section is the target for exact values.

**Inspired by, never copied.** Do not use Harvey's name, logo, "H" mark, proprietary fonts (HarveySerif, HarveySans and the like) or verbatim UI copy. Strata has its own wordmark, set in the display serif.

### 17.2 Color tokens (light theme only)
Define these as CSS variables in `app/globals.css` and expose them through Tailwind v4 `@theme`. shadcn's `--background`, `--foreground`, `--border` and so on map onto these. All text pairs below meet WCAG AA (checked); the disabled grey is exempt.

| Token | Value | Use |
|---|---|---|
| `--canvas` | `#F7F6F3` | App background (warm off-white) |
| `--surface` | `#FFFFFF` | Cards, tables, drawer, popovers |
| `--surface-muted` | `#F1F0EC` | Table group rows, hover, tab track, code/quote wells |
| `--border` | `#E7E5E0` | Hairlines |
| `--border-strong` | `#D6D3CC` | Inputs, control outlines, dashed cue cards |
| `--ink` | `#141413` | Primary text, primary button, focus ring |
| `--ink-2` | `#52504B` | Secondary text, icons |
| `--ink-3` | `#6F6C66` | Labels, captions, axis text, table headers (4.6:1 or better on every surface) |
| `--ink-4` | `#A8A59E` | Disabled and future-cue text only |
| `--sidebar` | `#0F0F0E` | Sidebar background |
| `--sidebar-fg` | `#EDECE8` | Sidebar text |
| `--sidebar-muted` | `#9A978F` | Sidebar section labels, secondary items |
| `--sidebar-active` | `#252523` | Active nav item background |
| `--sidebar-border` | `#232321` | Sidebar dividers |
| `--red` / `--red-soft` / `--red-line` | `#B42318` / `#FDECEA` / `#F5C2BD` | Action required, diff deletions, negative deltas |
| `--green` / `--green-soft` | `#1E6B45` / `#E8F3EC` | Cleared, diff insertions, positive deltas, pass marks |
| `--amber` / `--amber-soft` | `#8A5317` / `#FBF0E2` | "Needs review" only: low confidence or unverified evidence |

**Semantic mapping** (the brief's single color language, reduced to Harvey's palette). Every component reads these; none picks its own color.

| Semantic token | Maps to | Rendering |
|---|---|---|
| `--verdict-action-required` | red | Soft red pill; red left border on the clause; red tick and dot |
| `--verdict-review` | amber | Soft amber pill; amber border, tick and dot |
| `--verdict-update-citation` | ink | Neutral pill with ink text and a `quote` icon; ink border, tick and dot |
| `--verdict-optional-relaxed` | ink-2 | Outlined neutral pill with an `arrow-down-right` icon; ink-2 border, tick and dot |
| `--verdict-info` | ink-3 | Muted neutral pill; ink-3 tick and dot |
| `--state-cleared` | green | Soft green pill; green ✓ gutter marker; green figure for "clauses cleared" |
| `--noise` | ink-4 texture | Hatched or dotted fill (see 17.6), never a solid color |
| `--diff-delete` / `--diff-insert` | red / green | Red text with strikethrough and a red-soft background; green text with underline and a green-soft background |
| `--simulated` | ink hatch | Diagonal hatch pattern plus the "Simulated" tag. **Not amber**, which is reserved for review. |

### 17.3 Typography
Fonts are loaded with `next/font/google`. They are open-source stand-ins for Harvey's proprietary faces.

| Role | Family | Used for |
|---|---|---|
| Display and document serif | **Source Serif 4** (variable, optical sizing on) | Page titles, big figures, the verdict sentence, company-document and legal text, the wordmark |
| UI sans | **Inter** (tabular numerals in tables and counts) | Everything else |
| Mono | **JetBrains Mono** | Citations, clause ids, doc ids, DINs |

| Style | Spec |
|---|---|
| Wordmark | Serif 24/28, weight 500, sidebar-fg |
| Page title | Serif 36/44, weight 400, tracking −0.015em, ink |
| Page caption (above title) | Sans 13/18, ink-3, e.g. "Real wave · S1 Dec 31, 2024 → S2 Dec 31, 2025" |
| Big figure | Serif 48/52, weight 400, ink. Delta beside it in sans 13 medium, green or red with an arrow. |
| Verdict sentence | Serif 22/30, weight 400; the key values in weight 600 |
| Card or section title | Sans 18/24, weight 500, ink. Subtitle sans 14/20, ink-3. |
| Body UI | Sans 14/20, ink |
| Dense table | Sans 13/18 |
| Label or header | Sans 12/16, weight 500, ink-3 |
| Sidebar item | Sans 15/20, sidebar-fg. Section label sans 13/16, sidebar-muted. |
| Reader document text | Serif 16/26, ink, measure ≤ 72ch |
| Evidence pane text | Serif 15/24 |
| Mono | 12.5/18 (13/18 in headers) |

### 17.4 Shape, spacing, elevation, motion
- **Radii:** cards and drawer 12px · buttons, inputs and selects 8px · pills and badges 6px · tags 4px · minimap ticks 1px.
- **Spacing:** 4px base. Page padding 40px horizontal and 32px top. Card padding 24px. Grid gaps 16px or 24px. Section spacing 40px.
- **Borders:** 1px `--border` on cards, tables and dividers; column dividers inside tables, as in Harvey review tables.
- **Elevation:** none on cards. Popover, dropdown and tooltip get `0 4px 16px rgba(20,20,19,.08)`. The drawer gets `0 8px 32px rgba(20,20,19,.12)` and a 1px left border.
- **Motion:** 150 ms ease-out for hover and state changes, 200 ms for the drawer slide, and a single 600 ms highlight pulse when jumping to a clause. Respect `prefers-reduced-motion` (no slide, no pulse). Nothing else animates.
- **Icons:** lucide at 16px (14px in dense tables), stroke 1.5, ink-2. Never colored, except the status ✓ and arrow in deltas.

### 17.5 Layout and component styling
**App shell**
- **Sidebar:** fixed, 264px, `--sidebar`, full height.
  - **Header row:** the "Strata" wordmark, then search and notification (future cue) icon buttons on the right.
  - **Primary nav:** Overview · Changes · Documents · Impact Matrix · Radar · What-if · Trust. Each is an icon plus a label; the active item is a `--sidebar-active` rounded (8px) row.
  - **Knowledge base** section: Regulations · Company.
  - **Recents** section: the last 4 visited documents, changes or findings, kept in `sessionStorage` (wrapped in try/catch). Each row has a small bullet and an ellipsis-truncated label.
  - **Coming soon** section: future cues (§18.1).
  - **Footer:** the company chip ("Rockridge Power & Light", with a square monogram "R"), plus the workspace-switcher future cue.
- **Icon rail (64px):** the sidebar collapses to it via a toggle. The reader collapses it automatically to give the document room, as in the reference's agent-builder screen.
- **Main area:** `--canvas`. Content max-width is 1440px for dashboards; the reader, changes and matrix pages are full width.
- **Page header:** caption (optional) above a serif title on the left; actions on the right. Secondary buttons first, then **at most one** primary (ink) button. Breadcrumbs sit above the caption in ink-3 with `›` separators, the current page in ink.
- **Info strip:** a full-width white card under the header with a small monogram icon and one sentence. Example: "1 change needs review across 3 documents." It links to the filtered view. Use it at most once per page, and only when there's something actionable.

**Components**
- **Cards:** `--surface`, hairline border, radius 12, padding 24. The title row has a title and subtitle on the left and select controls on the right. Footer rows (legend or actions) sit under a hairline divider.
- **Buttons:**
  - Primary: ink background, white text, h-36, radius 8, sans 14 medium.
  - Secondary: surface, `--border-strong`, ink text.
  - Ghost: text only, ink-2, with surface-muted on hover.
  - Icon buttons: 32×32.
- **Select controls** (period, filter): surface, `--border-strong`, h-32, radius 8, label plus a 14px `chevron-down`.
- **Tabs:** segmented. The track is transparent and the active tab is a surface pill with a hairline border; inactive tabs are ink-3 and turn ink on hover. Use them on the agency, radar and company pages.
- **Toolbar** (above tables, in Harvey review-table style): a row of ghost icon-plus-label actions separated by 1px vertical dividers, h-44, with a hairline bottom border.
- **Tables:**
  - Header row h-40: icon plus label in label style, with filter and sort icons that appear on hover.
  - Rows h-40 (h-32 compact for ledgers and the matrix). A leading row-number column in ink-3, and checkbox selection only where an action exists.
  - **Group rows:** `--surface-muted` band with an icon, the name in weight 500, "· n items" in ink-3, and a chevron.
  - Cells truncate with an ellipsis and show a tooltip with the full text.
  - Hover: surface-muted.
- **Pills:** soft background with matching text, sans 12 medium, h-22, radius 6, horizontal padding 8. Status pills use the semantic tokens. Neutral pills: surface-muted with ink-2 text.
- **Tags** (ClassPill noise, "Simulated", "Soon"): 11px medium, radius 4, 1px border.
- **Tooltips:** ink background, white sans 12, radius 6, max-width 280px.
- **Drawer** (evidence card): 640px wide (resizable to 880px), `--surface`, a sticky header with the verdict sentence and a close button, and sections separated by hairlines.
- **Empty states:** text only. A serif 20 line, a sans 14 ink-3 explanation and one action. No illustrations.
- **Skeletons:** `--surface-muted` blocks with a subtle shimmer, disabled under reduced motion.

### 17.6 Data marks without a chart library
All of these are plain divs and CSS, styled to match the reference's hairline bars.
- **"Your data" bars** (funnel substantive and in-footprint stages, verdict mini-bars): a solid ink fill, or the hairline texture `repeating-linear-gradient(90deg, var(--ink) 0 1px, transparent 1px 3px)` for large bars.
- **Noise bars:** a dotted or hatched texture in ink-4 (`repeating-linear-gradient(45deg, var(--ink-4) 0 1px, transparent 1px 4px)`), with a legend entry "Noise".
- **Funnel:** horizontal bars as in the reference's "Top power users" card. The stage label is on the left in sans 13 ink-2, the bar fills proportionally, and the value sits to its right in sans 12 ink-3 ("491 substantive"). "Clauses cleared" is a separate serif big figure in green.
- **Minimap:** a 6px track with 3px × 2px ticks in the verdict tokens.
- **Matrix cells:** a 10px dot in the verdict token with a count, a green ✓ for cleared, or empty.
- **Timeline strip and trace chain:** hairline connectors between 8px nodes (ink) and small bordered cards.
- **Stage stepper:** a vertical list as in the reference's agent-builder progress. A done stage shows a ✓ in ink plus a count, the running stage a spinner ring, and pending stages a hollow ring in ink-4.

### 17.7 Marketing landing styling
- Dark-first, like Harvey's site: a warm near-black (`#0F0E0D`) hero with an ivory (`#FAFAF9`) serif headline at 72/76 (40/44 on mobile).
- Sections alternate between dark and `--canvas`.
- Product screenshots are framed as in the owner's references: the app screenshot on a dark field with a very subtle grain (an inline SVG noise filter at about 6% opacity). This is the only texture allowed.
- Buttons: ivory-on-dark primary with radius 4px. The marketing site uses sharp corners; the app uses 8px.
- No stock imagery, logos of customers we don't have, or testimonials.

---

## 18. Future-capability cues

### 18.1 Purpose and rules
These are disabled UI affordances that show what Strata could do next, so a first-time viewer senses a broad, cutting-edge platform without reading a roadmap. They replace the earlier short list of future buttons.

1. **They never work.** No click handler, dialog, toast or navigation. Hover and focus show a tooltip; that's all.
2. **At most 3 per page**, not counting the shell. One cluster per page is ideal. They are **never** the primary button, and never placed inside the evidence panes or between a verdict and its proof.
3. **Each one sits beside the data it would act on**, so its meaning is obvious without reading.
4. **They are visually quieter than real controls:**
   - ink-4 label and icon;
   - a "Soon" tag (11px medium, ink-3, 1px `--border-strong`, radius 4);
   - normal cursor, since `not-allowed` reads as an error.
5. **Accessibility:**
   - render with `aria-disabled="true"`, not the `disabled` attribute, so they stay focusable and the tooltip works;
   - include screen-reader text "(coming soon)";
   - Enter and Space do nothing.
6. **Tooltip copy:** the label in weight 500, one outcome-focused line of at most 90 characters, then "Coming soon" in ink-3. Plain words, no "AI-powered" fluff.
7. **Single registry.** Every cue is defined once in `lib/future-features.ts` (`id, label, tooltip, icon, variant`) and rendered by `<FutureCue id="…" />`. A constant `SHOW_FUTURE_CUES` (default `true`) hides them all at once for a no-cues demo.

**Variants of `FutureCue`:**
- `button`: secondary-button shape.
- `toolbar`: a toolbar item.
- `inline-add`: "+ Label" ghost text, as in the reference's "+ Add source".
- `card`: a dashed `--border-strong` card with a plus icon.
- `nav`: a sidebar item.
- `icon`: an icon button.
- `chip`: a filter chip.
- `menu-item`: a row in a dropdown or the command palette.

### 18.2 Catalog
Copy is final unless the owner edits it. Ids are stable.

**Shell (on every page)**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `notifications` | icon · sidebar header (bell) | Alerts | Get alerted the moment a rule your documents depend on changes. |
| `assistant` | nav · sidebar "Coming soon" | Assistant | Ask questions across regulations and your documents, with cited answers. |
| `agents` | nav · sidebar "Coming soon" | Agents | Automate recurring work, like monthly obligation reviews or filing prep. |
| `integrations` | nav · sidebar "Coming soon" | Integrations | Connect SharePoint, Google Drive, Box, Jira and ServiceNow. |
| `workspace-switcher` | icon · company chip chevron | Switch company | Monitor several operating companies and affiliates from one workspace. |
| `search-ask` | menu-item · last row of ⌘K results | Ask Strata "‹query›" | Get a cited answer instead of a list of results. |

**Overview**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `schedule-briefing` | button · page header | Schedule briefing | Email a one-page summary of every regulatory wave to leadership. |
| `export-report` | button · page header | Export report | Download a board-ready PDF of this wave's impact. |
| `continuous-monitoring` | menu-item · RunSelector, under a "Coming soon" divider | Continuous monitoring | Analyze changes the day they're published, not snapshot to snapshot. |

**Changes**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `proposed-rules` | chip · tree filter row | Proposed rules | See which clauses a proposed rule would affect before it becomes final. |
| `watch` | button · change detail header | Watch | Follow this section and get alerted on any future change. |
| `impact-memo` | button · change detail header | Draft impact memo | Generate a counsel-ready memo of this change and every clause it touches. |

**Documents board**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `connect-source` | button · page header | Connect source | Keep documents in sync from SharePoint, Google Drive, Box or iManage. |
| `upload-document` | button · page header | Upload | Add a document; Strata splits it into clauses and files it in the right vertical. |
| `coverage-gaps` | toolbar · board toolbar | Find coverage gaps | Find rules RPL is subject to that no document covers yet. |

**Vertical page**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `invite-team` | button · page header | Invite team | Give this department's owners and reviewers their own view. |
| `upload-document` | button · page header | Upload | (as above) |
| `start-monitoring` | inline-add · each sample-doc row | Start monitoring | Check this document against every future regulatory change. |

**Document reader**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `ask-document` | toolbar · reader toolbar | Ask | Ask about this document and get answers cited to its clauses. |
| `export-redline` | toolbar · reader toolbar | Export redline | Send suggested updates to Word as tracked changes for the owner. |
| `view-original` | toolbar · reader toolbar | Original file | View the source PDF or Word file beside its clauses. |
| `version-history` | icon · chevron on the version chip in the header (counts toward the 3 only if the toolbar is crowded; prefer keeping it) | Version history | Compare this document with its earlier versions. |

**Evidence card**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `draft-rewrite` | inline-add · after the "Suggested update — not applied" chip | Draft full rewrite | Draft a complete replacement clause that satisfies the new rule. |
| `create-task` | button · routing section | Create task | Open a tracked task in Jira or ServiceNow for the owner. |
| `request-signoff` | button · routing section | Request sign-off | Collect owner, reviewer and approver sign-off with an audit trail. |

**Impact matrix**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `ai-column` | toolbar · matrix toolbar | Add column | Ask one question of every document and see each answer in its row. |
| `export-matrix` | toolbar · matrix toolbar | Export | Download this matrix as a spreadsheet. |

**Radar**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `map-document` | inline-add · each "Possibly applicable" item | Map to document | Link this rule to the document that should cover it. |
| `assign-review` | inline-add · each "Possibly applicable" or "Unclear" item | Assign | Ask a colleague to confirm whether this applies to RPL. |

**What-if**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `from-proposed-rule` | card · last card in the preset list | Start from a proposed rule | Load an open IURC or Federal Register proposal as a scenario. |
| `compare-scenarios` | button · page header | Compare | Put two scenarios side by side. |

**Trust**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `evidence-pack` | button · page header | Export evidence pack | Package every decision, quote and review for auditors or regulators. |
| `review-sampling` | inline-add · Method card | Set up review sampling | Route a random sample of AI decisions to a human reviewer each wave. |

**Regulations overview**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `add-agency-federal` | card · end of Federal (subtitle "NERC, OSHA, DOE…") | Add agency | Track another federal agency's rules and actions for RPL. |
| `add-agency-state` | card · end of State (subtitle "OUCC, Indiana DNR…") | Add agency | Track another Indiana agency's rules and actions for RPL. |
| `add-jurisdiction` | button · page header | Add jurisdiction | Monitor another state, such as Ohio, Illinois or Michigan. |
| `more-sources` | one compact row of 3 small cards below the agencies, under the heading "More source types": Indiana General Assembly · MISO tariff & manuals · Court & commission decisions | (card titles) | Track bills before they amend the Indiana Code. · Track MISO tariff and business-practice changes. · Track decisions that reinterpret your rules. |

(`more-sources` counts as one cue for the per-page limit.)

**Agency page**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `track-docket` | toolbar · Activity tab | Track docket | Follow an IURC cause or FERC docket and see every new filing. |
| `add-data-source` | button · page header | Add data source | Add another feed for this agency, such as guidance or FAQs. |

**Regulation section**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `watch` | button · page header | Watch | (as above) |
| `add-note` | button · page header | Add note | Leave an internal interpretation note for your team. |

**Regulatory action**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `comment-letter` | button · page header, **only when `action_type` is a proposed rule or advance notice** | Draft comment letter | Draft comments on an open rulemaking, grounded in RPL's documents. |
| `track-docket` | button · page header | Track docket | (as above) |

**Company profile**

| id | Variant · placement | Label | Tooltip |
|---|---|---|---|
| `edit-profile` | button · page header | Edit profile | Correct an attribute and Radar re-screens every change automatically. |
| `sync-directory` | inline-add · People section header | Sync directory | Keep people and roles in sync with Workday or Okta. |

**Marketing landing.** No disabled controls. Add a calm **"What's next"** section of four items, as plain content: Assistant with cited answers · Early warning on proposed rules · Integrations with your document and ticketing systems · Multi-company monitoring.
