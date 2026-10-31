# Verticals Migration — Table Schemas, Connections & Data Reference

Companion to `plan.md`. This document is the single reference for every table, column, constraint, and data value the verticals migration touches or must leave untouched. Built from direct inspection of `backend/migrations/versions/*.py` and live read-only queries against the production Neon DB (connection: `backend/.env`, schemas `company`, `engine`, `public`).

---

## 1. New table: `company.verticals`

Does not exist today. To be created by the migration.

```sql
CREATE TABLE company.verticals (
    name        text PRIMARY KEY,
    slug        text UNIQUE NOT NULL,
    description text
);
```

- `name` is the canonical backend display string (what `company_documents.vertical` and `approval_policies.applies_to_vertical` store) — the natural key, not a surrogate id, so existing readers/writers of those columns need no code change.
- `slug` is the frontend-facing URL slug (must match `frontend/lib/verticals.ts` exactly).
- `description` should be sourced verbatim from the reference doc's "What It Covers" column (see §5 below) so the UI copy doesn't drift from the taxonomy definition.

Seed data (14 rows) — see §5 for the full name/slug/description table.

---

## 2. Modified tables: new FK constraints only, no new columns

### `company.company_documents`

Existing definition (`backend/migrations/versions/c3d4e5f6a7b8_company_schema.py:54-68`):

```sql
CREATE TABLE company.company_documents (
    company_id           text NOT NULL,
    doc_id                text NOT NULL,
    title                 text,
    doc_class             text,
    vertical              text,          -- target of this migration
    owner_id              text,
    reviewer_id           text,
    approver_id           text,
    review_cycle          text,
    current_version_id    uuid,
    current_content_hash  character(64),
    doc_number            text,          -- the stable RPL-* register id, used for data-migration joins
    lifecycle_state       text NOT NULL DEFAULT 'active',
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, doc_id)
);
```

Change:

```sql
ALTER TABLE company.company_documents
  ADD CONSTRAINT company_documents_vertical_fk
  FOREIGN KEY (vertical) REFERENCES company.verticals(name)
  ON UPDATE CASCADE;
```

- Nullable — unclassified documents (`vertical IS NULL`) remain valid.
- `ON UPDATE CASCADE` means any *future* rename of a vertical's `name` is a single `UPDATE company.verticals` — no document rows need touching. (The app-layer constants still need a code deploy to match — the FK protects data integrity, not code sync.)
- **No DB trigger exists on this table** (confirmed via `pg_trigger` query — zero rows). `updated_at` is only bumped by the application layer (the admin PATCH endpoint, `doc_admin.py`). The migration's backfill `UPDATE` must list only `vertical` in its `SET` clause so `updated_at` is untouched by the pure re-classification.

### `company.approval_policies`

Existing definition (`backend/migrations/versions/f7b2c91d4a08_v2_document_versioning.py:250-258`):

```sql
CREATE TABLE company.approval_policies (
    company_id            text NOT NULL,
    policy_id             uuid NOT NULL,
    name                   text NOT NULL,
    applies_to_vertical    text,   -- target of this migration
    applies_to_doc_class   text,
    PRIMARY KEY (policy_id)
);
```

Change:

```sql
ALTER TABLE company.approval_policies
  ADD CONSTRAINT approval_policies_vertical_fk
  FOREIGN KEY (applies_to_vertical) REFERENCES company.verticals(name)
  ON UPDATE CASCADE;
```

- Nullable, same rationale.
- **Live data check (2026-10-31): both existing rows have `applies_to_vertical IS NULL`.** Zero live rows are vertical-scoped, so the FK addition carries zero backfill risk for this table today — it's purely forward protection.
- **Code gap found:** `backend/app/api/company/org.py` `create_policy` (line 632) and `update_policy` (line 660) write `body.applies_to_vertical` straight into SQL without calling `_canonical_vertical()`. Once this FK exists, an invalid vertical name submitted through either endpoint becomes a raw `IntegrityError` (HTTP 500) instead of a clean 422. **Add `_canonical_vertical()` validation to both routes as part of this migration's code changes** — this is a correctness fix the FK surfaces, not an unrelated change.

---

## 3. New backup tables (rollback source — not live columns)

Created inside the same migration transaction, before the `UPDATE`:

```sql
CREATE TABLE company._vertical_backfill_20261031 AS
  SELECT company_id, doc_id, vertical AS old_vertical
  FROM company.company_documents;

CREATE TABLE company._approval_policy_vertical_backfill_20261031 AS
  SELECT company_id, policy_id, applies_to_vertical AS old_applies_to_vertical
  FROM company.approval_policies;
```

- These are the `downgrade()` data source: drop both FKs → restore `vertical`/`applies_to_vertical` from these tables by joining on PK → drop `company.verticals`.
- **Retention:** keep for a stated window (recommend 30 days post-cutover). Drop in a **separate, later** migration once the rename is confirmed stable — not as part of this one, since `downgrade()` depends on them existing.

---

## 4. Tables confirmed NOT to need any change (structurally decoupled from `vertical`)

Verified by reading every DDL and every JSONB write call site in `backend/app`:

| Table | Why it's safe |
|---|---|
| `company.clauses` | No `vertical` column. Reaches a vertical only via `doc_id` join to `company_documents`. |
| `company.clause_citations` | Links clauses to regulatory citations (`source_system`, `title`, `article`, `code_section_id` as plain indexed text, not FK) — no vertical involvement. |
| `company.clause_links` | Clause↔clause / clause↔document graph edges (`link_type`: `REFERENCES_DOC`, `REFERENCES_CLAUSE`, `RESTATES`, etc.) — no vertical column, no vertical-keyed logic. |
| `company.clause_parameters`, `company.defined_terms`, `company.term_usages` | Clause-level extraction tables, no vertical involvement. |
| `company.document_scope` | Regulatory-citation rollup per document version, no vertical column. |
| `company.document_versions` | Versioning table, no vertical column (vertical lives only on the parent `company_documents` row). |
| `company.approval_requests` / `company.approval_steps` | `approval_requests.policy_id` has **no FK** (confirmed; intentionally — see `org.py:714`'s comment on `delete_policy` nulling it for exactly this reason) and is never re-derived after open. Live data: 0 approval requests reference a vertical-scoped policy (both live policies are unscoped), so this migration carries zero risk here. Not modified. |
| `engine.doc_rollups`, `engine.findings`, `engine.candidates`, `engine.change_records`, `engine.radar_items`, `engine.score_reports`, `engine.llm_calls` | None store `vertical`; `doc_rollups`/`findings` surface it only via a live `LEFT JOIN` to `company_documents` at API-read time (`backend/app/api/engine/routes.py:163,187`) — automatically reflects the new value post-migration, nothing to backfill. |
| Qdrant `company_clauses` collection | Payload fields are explicitly enumerated (`backend/app/company_ingest/index/qdrant_setup.py:37-53`) and `vertical` is not among them — no re-embedding needed. |
| Every JSONB column (`doc_rollups.counts`, `runs.stats`, `change_records.*`, `findings.quotes`, `llm_calls.request/response`, `ingest_jobs.stats/register_spec`) | Checked every write call site, not just DDL — none embed a vertical key. |

**Invariant check:** none of these tables' row counts should change as a result of this migration. Baseline counts captured live (2026-10-31), to re-check post-migration:

| Table | Row count |
|---|---|
| `company.clauses` | 2334 |
| `company.clause_links` | 3296 |
| `company.clause_citations` | 1373 |
| `company.document_versions` | 15 |
| `company.document_scope` | 419 |
| `company.approval_requests` | 15 |
| `company.approval_steps` | 30 |
| `engine.doc_rollups` | 30 |
| `engine.findings` | 41 |
| `company.company_documents` | 15 |

---

## 5. New taxonomy: 14 verticals (name, slug, description for `company.verticals` seed + `frontend/lib/verticals.ts`)

| # | Name | Slug | What It Covers (source: `Strata Verticals — Final Reference.md`) |
|---|---|---|---|
| 1 | Corporate Governance & Board | `corporate-governance-board` | Board structure, bylaws, charters, fiduciary duties, shareholder rights, entity management, annual filings, regulatory disclosure obligations |
| 2 | Compliance & Ethics | `compliance-ethics` | Code of conduct, anti-corruption (FCPA), anti-bribery, whistleblower protections, compliance training, conflicts of interest, FTC consumer/advertising compliance |
| 3 | Legal & Contractual | `legal-contractual` | Contract governance, litigation holds, IP protection, licensing, entity structure, NDAs, antitrust compliance |
| 4 | Financial Compliance & Reporting | `financial-compliance-reporting` | SOX/ICFR, GAAP/IFRS, financial disclosures, audit requirements, internal controls, revenue recognition, pricing regulations, fee disclosures |
| 5 | Tax & Trade Compliance | `tax-trade-compliance` | Corporate tax, payroll tax, sales tax, international tax (FATCA), transfer pricing, export controls, customs, OFAC sanctions, tariffs |
| 6 | Workforce & Employment | `workforce-employment` | Labor laws, wage & hour, FMLA, ADA, anti-discrimination, benefits (ERISA), immigration/work authorization, DEI policies |
| 7 | Health & Safety | `health-safety` | Workplace safety, emergency preparedness, hazard communication, PPE, incident reporting, product/consumer safety |
| 8 | Data Privacy & Cybersecurity | `data-privacy-cybersecurity` | GDPR, CCPA/CPRA, state privacy laws, data breach notification, cybersecurity frameworks, data retention, information security |
| 9 | Environmental & Sustainability | `environmental-sustainability` | EPA regulations, emissions, waste management, environmental permits, GHG reporting, ESG disclosures, climate risk, energy management |
| 10 | Operations & Quality | `operations-quality` | Quality management, process compliance, GMP, FDA product regulations, CAPA, operational standards, business process documentation |
| 11 | Information Technology & Records | `information-technology-records` | IT policies, system access controls, change management, records retention, digital accessibility (ADA/WCAG), AI governance and responsible use |
| 12 | Supply Chain & Third-Party Risk | `supply-chain-third-party-risk` | Vendor compliance, third-party risk, supplier due diligence, modern slavery/forced labor, supply chain transparency, conflict minerals |
| 13 | Policy & Training Management | `policy-training-management` | Policy lifecycle, document control, version management, compliance training programs, employee acknowledgments |
| 14 | Risk & Resilience | `risk-resilience` | Enterprise risk management, insurance requirements, business continuity, disaster recovery, operational resilience |

### Overlap precedence rules (for classifying any document, not just the 15 live ones)

| Overlap | Rule |
|---|---|
| #8 Data Privacy & Cybersecurity vs. #11 Information Technology & Records | Protecting personal/sensitive data or cyber incident response → #8. System access/change management, general records retention, AI governance, accessibility → #11. |
| #2 Compliance & Ethics vs. #13 Policy & Training Management | Substantive ethics/anti-corruption/whistleblower content → #2. Policy-lifecycle mechanics (version control, document control, training delivery/acknowledgment tracking) → #13, regardless of subject. |
| #7 Health & Safety vs. #10 Operations & Quality | Employee/public/product safety incidents and emergency response → #7. Manufacturing/process/GMP quality control → #10. |
| #1 Corporate Governance & Board vs. #3 Legal & Contractual | Board-level entity governance (formation, charters, filings) → #1. Contract/transaction-level entity documents → #3. |
| (gap) Utility customer/regulatory-filing docs (tariffs, billing, disconnection, complaints) | No dedicated vertical exists. Billing/rate/fee-related → #4. Consumer-protection/complaint-handling → #2. Customer-facing operational procedures → #10. |

---

## 6. Old → new mapping (default table, keyed on the 14 old **stored** names)

Use for any document not covered by the explicit per-`doc_number` override in §7 — needed because local/CI/future-seeded databases can contain any of the 14 old names, and because several split non-1:1.

| Old vertical (as stored in DB) | Default new vertical | Note |
|---|---|---|
| Policy & Governance | Corporate Governance & Board | Splits with Policy & Training Management (policy-lifecycle docs) |
| Compliance & Legal | Compliance & Ethics | Splits with Legal & Contractual, Contractual & Third-Party, Strategic & Competitive (antitrust) |
| Financial & Reporting | Financial Compliance & Reporting | Direct, no split |
| Revenue & Pricing | Financial Compliance & Reporting | Folds in, no split |
| Operations & Processes | Operations & Quality | Direct rename + expansion |
| Technology & Systems | Information Technology & Records | Direct rename |
| Workforce & Safety (displayed "Workforce & HR") | Workforce & Employment | **Trap:** despite "Safety" in the stored name, this is the literal rename target. Safety-incident-specific docs must be individually routed to Health & Safety instead (see DOC-15 in §7). |
| Environmental (displayed "Environmental & ESG") | Environmental & Sustainability | Direct rename |
| Supply Chain & Procurement | Supply Chain & Third-Party Risk | Direct, no split |
| Risk & Insurance | Risk & Resilience | Direct + Capital & Infrastructure folds in |
| Strategic & Competitive | Corporate Governance & Board | Antitrust-specific content → Legal & Contractual instead |
| Reputational & Stakeholder | Corporate Governance & Board | Folds in |
| Contractual & Third-Party Obligations | Legal & Contractual | Splits with Supply Chain & Third-Party Risk (vendor-specific docs) |
| Capital & Infrastructure | Risk & Resilience | Per reference doc |

---

## 7. Per-document override (the 15 live rows — explicit target, takes precedence over §6 default)

Evidence: `company.clause_citations` joined to `company.clauses` per `doc_id` (regulator/title/article), cross-checked with `company.clause_links WHERE link_type='REFERENCES_DOC'` (zero cross-links exist among these 15 docs — no split decision below separates linked documents). `document_versions.regulatory_basis` is empty for all 15 (not populated by this pipeline).

`doc_number` (`RPL-*`) is the join key for seed-data files (CSV, front matter); `doc_id` (`DOC-0000xx`) is a per-environment surrogate.

| doc_number | doc_id | Old vertical | New vertical | Confidence |
|---|---|---|---|---|
| RPL-CMP-REG-001 (+ #register twin) | DOC-000001/2 | Compliance & Legal | Compliance & Ethics | Medium |
| RPL-REG-CAL-2025 (+ #register twin) | DOC-000003/4 | Compliance & Legal | Compliance & Ethics | Medium |
| RPL-LEG-RRS-001 (+ #register twin) | DOC-000005/6 | Compliance & Legal | Information Technology & Records | High |
| RPL-TAR-GRR-012 | DOC-000007 | Policy & Governance | Financial Compliance & Reporting | High |
| RPL-CS-PRO-004 | DOC-000008 | Policy & Governance | Compliance & Ethics | High |
| RPL-CS-PRO-007 | DOC-000009 | Policy & Governance | Financial Compliance & Reporting | Medium |
| RPL-DO-PLN-002 | DOC-000010 | Policy & Governance | Operations & Quality | Medium |
| RPL-CS-PRO-011 | DOC-000011 | Policy & Governance | Compliance & Ethics | High |
| RPL-MTR-PGM-001 | DOC-000012 | Operations & Processes | Operations & Quality | High |
| RPL-DCC-PRO-003 | DOC-000013 | Operations & Processes | Operations & Quality | High |
| RPL-ENV-PRO-005 | DOC-000014 | Environmental | Environmental & Sustainability | High |
| RPL-SAF-PRO-009 | DOC-000015 | Workforce & Safety | Health & Safety | High |

Full rationale, citation evidence, and alternates for the 6 medium-confidence rows are in `plan.md` §"Per-document mapping" — that table is the human sign-off artifact; this one is the migration script's literal override map.

### Expected post-migration distribution (verification target)

| New vertical | Doc count |
|---|---|
| Compliance & Ethics | 6 |
| Operations & Quality | 3 |
| Financial Compliance & Reporting | 2 |
| Information Technology & Records | 2 |
| Environmental & Sustainability | 1 |
| Health & Safety | 1 |

6 of 14 verticals populated (up from 5 today). `frontend/tests/unit/verticals.test.ts`'s `realVerticals()` assertion must move from 5 to 6.

---

## 8. Code locations that read/write these columns (no schema change, but must stay in sync)

| Location | Role |
|---|---|
| `backend/app/api/company/routes.py:20-37` (`VERTICAL_SLUGS`) | Backend name ↔ frontend slug map. Must list the 14 new names/slugs. |
| `backend/app/api/company/upload.py:240-252` (`_canonical_vertical`) | Sole validator/normalizer on write. Must accept the 14 new names/slugs, reject everything else with 422. |
| `backend/app/api/company/doc_admin.py:113-116` | PATCH endpoint, reuses `_canonical_vertical`. No change needed beyond the allowlist update above. |
| `backend/app/api/company/org.py:632,660` | **Policy create/update — currently missing `_canonical_vertical()` validation (see §2).** |
| `backend/app/api/company/org.py:214-234` (`select_policy`) | `(vertical, doc_class)` policy-matching logic — unaffected by the rename itself since both live policies are unscoped; logic doesn't need to change. |
| `backend/synthetic/corpus_meta.py:45-60` (`CANONICAL_VERTICALS`) | Must match `VERTICAL_SLUGS` — pinned by `backend/tests/synthetic/test_corpus_meta.py:33-35`. |
| `backend/synthetic/corpus/_global/document_register.csv` | Seed CSV, `vertical` column — update per §7, keyed by `doc_number`. |
| `backend/synthetic/corpus/docs/*/` front matter | Per-doc `vertical:` field, parsed by `backend/app/company_ingest/parse/front_matter.py` but currently discarded on ingest (`neon.py:283` hardcodes `vertical=None`) — update anyway so a future re-seed doesn't resurrect old names. |
| `frontend/lib/verticals.ts:13-28` | Canonical FE definition — slug, name, description per §5. |
| `frontend/scripts/build-fixtures.ts` (~lines 69-93 constants, ~524+ sample rows) | Both the slug/order constants AND every individual hardcoded sample-doc row need remapping through §6 before `documents.json` regenerates. |
| `frontend/fixtures/company/documents.json` | Regenerated output of the script above. |
| `frontend/app/app/documents/verticals/[vertical]/page.tsx`, `VerticalView.tsx`, `VerticalSection.tsx`, `DocumentsBoard.tsx`, `logic.ts` | URL routing and board UI — slug-driven, no logic change, just data. |
| `frontend/components/documents/upload/UploadDocumentDialog.tsx`, `upload/logic.ts` | Upload dropdown — sourced from `lib/verticals.ts`, no logic change. |
| `frontend/lib/future-features.ts:95` | `PAGE_CUES["vertical"]` — confirmed this is a *page-type* key (the vertical detail page), not a vertical name. **No change.** |
