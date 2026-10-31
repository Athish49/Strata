# Strata Verticals Re-Taxonomy: Analysis & Migration Plan

## Context

Strata currently defines 14 "verticals" (business-compliance-domain tags applied to documents), but only 5 have ever held a real document. A new 14-vertical taxonomy (`Strata Verticals — Final Reference.md`, untracked, dated 2026-10-18) was drafted by a separate agent run to close coverage gaps (it adds Tax & Trade Compliance, Health & Safety, and Data Privacy & Cybersecurity, which didn't exist before) and to clean up naming. The user asked for a deep evaluation of whether to adopt it, and — since this touches live production data — a full accounting of every schema, code, and data location `vertical` touches, so the re-org doesn't orphan or corrupt anything.

All analysis below is backed by direct read-only queries against the production Neon database (connection from `backend/.env`), not assumptions. Three research agents mapped the codebase (taxonomy definitions and all references, DB schema and connections, ingestion pipeline), and all three were cross-checked against live data.

## Answering the user's first question: how many verticals, and how are documents spread?

- **14 verticals are defined** in code (hand-duplicated across `frontend/lib/verticals.ts`, `backend/app/api/company/routes.py` `VERTICAL_SLUGS`, `backend/synthetic/corpus_meta.py` `CANONICAL_VERTICALS`, and partially in `frontend/scripts/build-fixtures.ts`), pinned equal by `backend/tests/synthetic/test_corpus_meta.py`.
- **Only 5 have ever held documents.** Verified live: single tenant `company_id = 'rpl'`, exactly **15 documents**, all `lifecycle_state = 'active'`, zero NULL/unclassified verticals:
  - Compliance & Legal — 6 docs
  - Policy & Governance — 5 docs
  - Operations & Processes — 2 docs
  - Environmental — 1 doc
  - Workforce & Safety — 1 doc
- The other 9 verticals are upload-only destinations with zero historical documents.
- Two verticals have a **stored name that differs from their frontend display name**: DB stores `"Workforce & Safety"` (frontend shows "Workforce & HR") and `"Environmental"` (frontend shows "Environmental & ESG"). This drift disappears automatically once the rename below is applied.
- `vertical` is a **plain nullable `text` column**, no CHECK/FK/lookup table — on both `company.company_documents.vertical` and `company.approval_policies.applies_to_vertical`. It is never classifier/LLM-assigned; only the upload form and the admin PATCH endpoint write it (confirmed: the ingest pipeline's own writer in `neon.py` hardcodes `vertical=None` and never overwrites it on conflict).
- Both live `approval_policies` rows are **completely unscoped** (`applies_to_vertical IS NULL`), so the vertical-scoped-policy risk is a template/future concern, not a live-data risk, here.
- Nothing hides a vertical inside a JSONB blob, an LLM prompt, or a routing branch anywhere in the engine or ingestion code (confirmed by grepping every JSONB write site and every `engine/*.py` consumer) — `vertical` is purely a label on `company_documents` plus the policy-scoping field. Clauses, clause_links, clause_citations, document_scope, the Qdrant index payload, and every `engine.*` table are vertical-blind; they reach a vertical only by joining back to `company_documents` live, at read time. **Restructuring verticals cannot corrupt any clause/citation/link/engine data — those are structurally decoupled.** What can break is: (a) the 4 duplicated taxonomy-definition files going out of sync, (b) any `approval_policies` row scoped to an old vertical name becoming unmatchable, and (c) anything hardcoding the old slug/name (tests, fixtures, URLs).

## Taxonomy evaluation

**Recommend adopting the new 14-vertical structure.** It closes 3 real gaps (Tax & Trade Compliance, Health & Safety, Data Privacy & Cybersecurity were entirely unrepresented before) and fixes the two display/storage name mismatches as a side effect. It is not a clean 1:1 rename — several old verticals split across multiple new ones, and the new verticals have internal overlaps that need explicit precedence rules so a document always has exactly one unambiguous home.

### New vertical names → slugs (user sign-off needed — these become the URL path, and the cutover is a clean break with no redirects)

| # | Name | Slug |
|---|---|---|
| 1 | Corporate Governance & Board | `corporate-governance-board` |
| 2 | Compliance & Ethics | `compliance-ethics` |
| 3 | Legal & Contractual | `legal-contractual` |
| 4 | Financial Compliance & Reporting | `financial-compliance-reporting` |
| 5 | Tax & Trade Compliance | `tax-trade-compliance` |
| 6 | Workforce & Employment | `workforce-employment` |
| 7 | Health & Safety | `health-safety` |
| 8 | Data Privacy & Cybersecurity | `data-privacy-cybersecurity` |
| 9 | Environmental & Sustainability | `environmental-sustainability` |
| 10 | Operations & Quality | `operations-quality` |
| 11 | Information Technology & Records | `information-technology-records` |
| 12 | Supply Chain & Third-Party Risk | `supply-chain-third-party-risk` |
| 13 | Policy & Training Management | `policy-training-management` |
| 14 | Risk & Resilience | `risk-resilience` |

### Overlap precedence rules (apply to all future documents, not just the 15 live ones)

| Overlap | Rule |
|---|---|
| Data Privacy & Cybersecurity (#8) vs. Information Technology & Records (#11) | Subject is protecting personal/sensitive data or cyber incident response → #8. System access/change management, general records retention schedules, AI governance, accessibility → #11. |
| Compliance & Ethics (#2) vs. Policy & Training Management (#13) | Substantive ethics/anti-corruption/whistleblower policy content → #2. Policy-lifecycle mechanics (version control, document control, training delivery/acknowledgment tracking) → #13, regardless of subject. |
| Health & Safety (#7) vs. Operations & Quality (#10) | Employee/public/product safety incidents and emergency response → #7. Manufacturing/process/GMP quality control → #10. |
| Corporate Governance & Board (#1) vs. Legal & Contractual (#3) | Board-level entity governance (formation, charters, filings) → #1. Contract/transaction-level entity documents → #3. |

### Gaps the reference doc leaves unresolved (decided by user, this session)

- **Utility customer/regulatory-filing documents** (rate tariffs, billing adjustments, disconnection/reconnection, customer complaints) have no dedicated home in the 14. **User decision: force-fit into the existing 14**, using this rule: billing/rate/fee-related → Financial Compliance & Reporting (#4); consumer-protection/complaint-handling procedures → Compliance & Ethics (#2); customer-facing operational procedures (meter testing, service interruption handling) → Operations & Quality (#10).
- **Capital & Infrastructure → Risk & Resilience** (per the reference doc's own mapping) is a weak merge — capex/financing arguably fits Financial Compliance & Reporting better. Zero live documents affected either way; this plan follows the reference doc as written and flags it for revisit if that path ever gets real documents.
- **Strategic & Competitive's non-antitrust portion** has no destination in the new mapping. Zero live documents affected. Default rule below sends it to Corporate Governance & Board; antitrust-specific content goes to Legal & Contractual per the reference doc.

### Default old→new mapping (all 14 old **stored** names, for any document not covered by the explicit per-doc overrides below — needed because local/CI/future-seeded databases can contain any of the 14, and because several old verticals split non-1:1)

| Old vertical (as stored) | Default new vertical | Note |
|---|---|---|
| Policy & Governance | Corporate Governance & Board | Splits with Policy & Training Management (policy-lifecycle docs) — see overlap rule |
| Compliance & Legal | Compliance & Ethics | Splits with Legal & Contractual, Contractual & Third-Party, and Strategic & Competitive (antitrust) |
| Financial & Reporting | Financial Compliance & Reporting | Direct, no split |
| Revenue & Pricing | Financial Compliance & Reporting | Folds in, no split |
| Operations & Processes | Operations & Quality | Direct rename + expansion |
| Technology & Systems | Information Technology & Records | Direct rename |
| Workforce & Safety (displayed "Workforce & HR") | Workforce & Employment | **Trap:** despite the "Safety" in the stored name, this is the literal reference-doc rename target — safety-incident-specific docs must be individually routed to Health & Safety instead (see DOC-15 below) |
| Environmental (displayed "Environmental & ESG") | Environmental & Sustainability | Direct rename |
| Supply Chain & Procurement | Supply Chain & Third-Party Risk | Direct, no split |
| Risk & Insurance | Risk & Resilience | Direct + Capital & Infrastructure folds in |
| Strategic & Competitive | Corporate Governance & Board | Antitrust-specific content → Legal & Contractual instead |
| Reputational & Stakeholder | Corporate Governance & Board | Folds in |
| Contractual & Third-Party Obligations | Legal & Contractual | Splits with Supply Chain & Third-Party Risk (vendor-specific docs) |
| Capital & Infrastructure | Risk & Resilience | Per reference doc; see gap note above |

## Per-document mapping (sign-off table — the 15 live documents, each with an explicit target, not a default)

Evidence used: `company.clause_citations` joined to `company.clauses` per `doc_id` (regulator/title/article ranges) and `document_versions.regulatory_basis` (empty for all 15 — not populated in this pipeline). Also checked `company.clause_links WHERE link_type='REFERENCES_DOC'` across all 15 docs — **zero cross-document links exist among them**, so no split decision below scatters a pair of docs that reference each other.

`doc_number` (the stable `RPL-*` register ID used by the synthetic corpus/CSV/front-matter) is the correct join key for updating seed data — `doc_id` (`DOC-0000xx`) looks like a per-environment surrogate.

| doc_number | doc_id | Title | Old vertical | Citation evidence | **New vertical (explicit)** | Alternate | Confidence |
|---|---|---|---|---|---|---|---|
| RPL-CMP-REG-001 (+#register) | DOC-000001/2 | Regulatory Obligations Register (+twin) | Compliance & Legal | 170 IAC 1-2–4-9 (broad), IC 8-1-2 | **Compliance & Ethics** | Policy & Training Management (document-control angle) | Medium |
| RPL-REG-CAL-2025 (+#register) | DOC-000003/4 | Regulatory Reporting Calendar 2025 (+twin) | Compliance & Legal | 170 IAC 1-2–4-1 (broad) | **Compliance & Ethics** | Corporate Governance & Board (#1 names "regulatory filing checklists" as an example doc — arguably the more literal fit) | Medium |
| RPL-LEG-RRS-001 (+#register) | DOC-000005/6 | Records Retention Schedule (+twin) | Compliance & Legal | CFR 18, 29, 40, 41, 49 (FERC/DOL/EPA/STB/DOT — cross-domain federal recordkeeping) + 170 IAC, IC | **Information Technology & Records** | — | High |
| RPL-TAR-GRR-012 | DOC-000007 | Tariff for Electric Service, IURC No. 12 | Policy & Governance | 170 IAC 1-2–4-2, IC 8-1-2 (utility rate statute) | **Financial Compliance & Reporting** | — | High |
| RPL-CS-PRO-004 | DOC-000008 | Disconnection Reconnection & Winter Protection Procedure | Policy & Governance | 170 IAC 16-1 (Indiana's consumer disconnection rule)–4-1, IC 8-1-2 | **Compliance & Ethics** | — | High |
| RPL-CS-PRO-007 | DOC-000009 | Meter Test Request & Billing Adjustment Procedure | Policy & Governance | 170 IAC 4-1 only (narrow) | **Financial Compliance & Reporting** | Operations & Quality | Medium |
| RPL-DO-PLN-002 | DOC-000010 | Vegetation Management Plan 2025 | Policy & Governance | CFR 29 (OSHA) + 170 IAC 16-1–4-9 (broad) | **Operations & Quality** | Health & Safety (OSHA citation) | Medium |
| RPL-CS-PRO-011 | DOC-000011 | Customer Complaint & Dispute Resolution Procedure | Policy & Governance | 170 IAC 16-1–4-1, IC 8-1-2 | **Compliance & Ethics** | — | High |
| RPL-MTR-PGM-001 | DOC-000012 | Meter Testing Program Plan | Operations & Processes | 170 IAC 4-1, IC 8-1-2 | **Operations & Quality** | — | High |
| RPL-DCC-PRO-003 | DOC-000013 | Service Interruption Reporting Procedure | Operations & Processes | 170 IAC 4-1–4-9 | **Operations & Quality** | — | High |
| RPL-ENV-PRO-005 | DOC-000014 | Spill Response & Reporting Procedure | Environmental | 327 IAC 2-6.1 (Indiana environmental code) | **Environmental & Sustainability** | — | High |
| RPL-SAF-PRO-009 | DOC-000015 | Electrical Accident & Incident Reporting Procedure | Workforce & Safety | 170 IAC 4-1, IC 8-1-2 | **Health & Safety** | — | High |

**9 of 15 documents are high-confidence** (direct precedent or unambiguous citation evidence); **6 are medium-confidence judgment calls**, all stemming from the old "Policy & Governance" and "Compliance & Legal" buckets being generic utility catch-alls that split non-1:1 in the new taxonomy. Twin pairs (1/2, 3/4, 5/6) are each assigned identically to their primary document.

**This table is the deliverable for final human sign-off before the backfill script runs.** The user should confirm or edit these 12 rows (covering 15 docs), plus the slug list and default-mapping table above, before any code change or migration begins.

## Migration mechanics

### Schema change (minimal — constrain the existing column, don't add a parallel one)

- Create `company.verticals(name text PRIMARY KEY, slug text UNIQUE NOT NULL, description text)`, seeded with the 14 new names/slugs from the table above, in an Alembic migration with a real `downgrade()`.
- Add `ALTER TABLE company.company_documents ADD CONSTRAINT company_documents_vertical_fk FOREIGN KEY (vertical) REFERENCES company.verticals(name) ON UPDATE CASCADE;` (nullable, so unclassified docs stay valid).
- Same FK, nullable, on `company.approval_policies.applies_to_vertical`.
- **No new `vertical_id` column, no change to `neon.py`, `upload.py`, `routes.py`, `engine/routes.py`.** They keep writing/reading the existing `vertical` text column. `ON UPDATE CASCADE` means a *database-level* rename of a vertical name later is a single `UPDATE company.verticals SET name = ...` — but the app-layer constants (`VERTICAL_SLUGS`, `lib/verticals.ts`, etc.) still need a code deploy to match; the FK only protects the data, it doesn't eliminate the need to keep code in sync.
- `downgrade()`: drop both FK constraints, restore `vertical`/`applies_to_vertical` from the backup tables below, then drop `company.verticals`.
- Rollback source is a **backup table**, not a second live column: `CREATE TABLE company._vertical_backfill_20261031 AS SELECT company_id, doc_id, vertical AS old_vertical FROM company.company_documents;` and the equivalent for `approval_policies`, created inside the same migration transaction before the `UPDATE`. Keep this backup table for a stated window (e.g. 30 days post-cutover) — `downgrade()` depends on it existing. Drop it in a **separate, later** migration once the rename is confirmed stable, not as part of this one.

### Backfill (data migration, same Alembic revision)

- A mapping dict covering **all 14 old stored names** (the default-mapping table above) **plus explicit per-`doc_number` overrides for all 15 live documents** (the sign-off table above) — the overrides take precedence over the default for `company_id = 'rpl'`.
- Abort the migration (`raise`) if any live `vertical` value has no mapping entry — guarantees no document is silently dropped or nulled.
- Run the `UPDATE`, then add the FK constraints, in the same transaction, so a constraint violation rolls back the whole revision.

### Expected post-migration distribution (verification target, and the updated answer to "how are docs spread")

| New vertical | Doc count |
|---|---|
| Compliance & Ethics | 6 |
| Operations & Quality | 3 |
| Financial Compliance & Reporting | 2 |
| Information Technology & Records | 2 |
| Environmental & Sustainability | 1 |
| Health & Safety | 1 |

6 of the 14 new verticals get a real document (up from 5 today). Compliance & Ethics becomes the largest single bucket/catch-all — which is exactly why the alternates column in the sign-off table matters: 2 of its 6 documents (the obligations register and reporting calendar) have a plausible alternate home in Corporate Governance & Board or Policy & Training Management, and the user should confirm the catch-all placement is intentional, not a default-by-neglect.

### `updated_at` must not be touched by the backfill

No DB trigger exists on `company.company_documents` (confirmed: `pg_trigger` query returns zero rows). The application layer *does* bump `updated_at` when the admin PATCH endpoint edits a document (`doc_admin.py`), but the migration's backfill runs as a direct SQL `UPDATE ... SET vertical = ...` outside that code path. The backfill's `UPDATE` statement must explicitly list only `vertical` in its `SET` clause (not `updated_at`), so the 15 documents don't appear freshly modified after a pure re-classification.

### Rehearsal

- Run the full migration against a Neon branch (branched off prod) first. Run `backend/synthetic/rehearsal_inner.py` against that branch afterward — it already asserts every seeded doc has a non-"unclassified" vertical, which is a useful post-migration sanity check.
- Only after the branch run is clean, apply to production.

### Cutover (per user's choices: short maintenance window, no dual-accept aliasing, no URL redirects)

1. Rehearse on Neon branch (above).
2. Stop the backend (the mechanism for "uploads offline" — there's no existing feature flag for this, so a brief process stop is simplest at this scale).
3. Run the Alembic migration against production (schema + backfill in one transaction).
4. Deploy backend (updated `VERTICAL_SLUGS`/`_canonical_vertical` allowlist in `routes.py`/`upload.py`, and `applies_to_vertical` validation added to `org.py`'s policy routes — see below) and frontend (`frontend/lib/verticals.ts`, URL routes under `app/app/documents/verticals/[vertical]/`, `UploadDocumentDialog.tsx`, `DocumentsBoard.tsx`/`logic.ts`) together.
5. Restart the backend, verify (below), reopen uploads.

### Code updates required

- **Gap found in `org.py`:** `create_policy` (line 632) and `update_policy` (line 660) write `body.applies_to_vertical` directly into SQL — neither calls `_canonical_vertical()`. Once the FK is added, bad input here becomes a raw DB `IntegrityError` (500) instead of a clean 422. Add `_canonical_vertical()` validation to both routes as part of this change.
- Backend: `VERTICAL_SLUGS` in `backend/app/api/company/routes.py`; `CANONICAL_VERTICALS` in `backend/synthetic/corpus_meta.py`; extend `backend/tests/synthetic/test_corpus_meta.py`'s existing pinning pattern to also assert the migration's seed list, `routes.py`, `corpus_meta.py`, `frontend/lib/verticals.ts`, and `frontend/scripts/build-fixtures.ts` all match each other (closes the "4 hand-synced copies" fragility, without building new codegen tooling).
- Frontend: `frontend/lib/verticals.ts` — the 14 entries + descriptions, sourced verbatim from the reference doc's "What It Covers" column so the UI copy doesn't drift from the taxonomy definition. `frontend/scripts/build-fixtures.ts` — both the `VERTICAL_SLUG`/`VERTICAL_ORDER` constants **and** the dozens of individual sample-document rows (from ~line 524 onward) that carry a hardcoded old-slug literal per row; each row needs remapping through the default-mapping table above before `documents.json` is regenerated. Also update `frontend/tests/e2e/company-and-kb.spec.ts` and `frontend/tests/support/mock-api/company.ts` (the mock upload endpoint replicates the vertical allowlist). Confirmed `frontend/lib/future-features.ts:95`'s `vertical` key in `PAGE_CUES` is a *page-type* key (the vertical-detail page), not a vertical name/slug — no change needed there.
- `realVerticals()` goes from 5 to 6 entries once the backfill lands (Compliance & Ethics joins the populated set) — `frontend/tests/unit/verticals.test.ts` needs that assertion updated.
- Seed/synthetic data, keyed by `doc_number` (the `RPL-*` ID), not `doc_id`: `backend/synthetic/corpus/_global/document_register.csv` and the per-doc front-matter `vertical:` fields under `backend/synthetic/corpus/docs/*/` — update these per the sign-off table, or a future re-seed reintroduces the old names (and a blanket string-replace would mis-split the same way the DB backfill would without overrides).
- Tests: update every hardcoded old slug/name across `backend/tests/api_company/*`, `backend/tests/synthetic/test_seed.py`, `backend/tests/company_ingest/test_front_matter.py`, and the frontend unit tests (`verticals.test.ts`, `documents-board-logic.test.tsx`, `company-fixtures.test.ts`, `http-company.test.ts`, `http-company-writes.test.ts`, `upload-dialog.test.tsx`, `kb-logic.test.tsx`, `engine-structure.test.tsx`). Also grep backend tests for **direct INSERTs with literal vertical strings** — these will now hit the new FK constraint and must use the new names.
- Confirm the test DB is built through Alembic migrations (not a separate schema fixture) so `company.verticals` actually gets seeded in CI.
- Confirm `_canonical_vertical()`'s `.title()`-casing round-trips cleanly for all 14 new names (test this explicitly — "Tax & Trade Compliance" and "Information Technology & Records" are the longest/most punctuation-heavy).

### Verification (pre/post invariants — the "nothing orphaned" check)

Pre-migration baseline counts (captured live, 2026-10-31): `clauses`=2334, `clause_links`=3296, `clause_citations`=1373, `document_versions`=15, `document_scope`=419, `approval_requests`=15, `approval_steps`=30, `engine.doc_rollups`=30, `engine.findings`=41, `company_documents`=15.

Post-migration: re-run the same counts and confirm **all unchanged** (none of these tables should be touched by a `vertical` rename — if any count moves, something unrelated broke). Then confirm: still 15 `company_documents` rows matching the sign-off table exactly; 0 values not present in `company.verticals`; the three twin pairs still share a vertical with their primary doc; `backend/synthetic/rehearsal_inner.py` passes against the Neon branch; `pytest` passes; frontend unit tests pass; and a manual walkthrough of the documents board, each new vertical's page, the upload dialog's vertical dropdown, the admin PATCH endpoint, and policy create/update all behave correctly against the new names.

## Out of scope for this migration

- Re-deriving `approval_policies` scoping logic or splitting policy rows — not needed, both live policies are unscoped.
- Snapshotting `approval_requests`' policy-match justification — pre-existing architecture, unrelated to this rename, not touched.
- Any change to the Qdrant index, `engine.*` tables, or clause/citation/link data — confirmed structurally decoupled from `vertical`, nothing to migrate there.
- `supplement_docs/data_report/*.html` — static point-in-time snapshots, not live consumers; regenerate manually if wanted, not part of this plan.
