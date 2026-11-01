# Task 1.2 Findings — Provenance of the 12 non-register documents' data

**Status:** read-only investigation, complete except step 3 (human log review), which **has NOT happened**.
**Zero writes** were made to Neon, Qdrant, or R2 by this investigation. **No document was re-ingested or re-uploaded.** Step 5 (scratch-Postgres reproduction via `rehearsal.py`) was **skipped** — see "Step 5" section below for why.

---

## 1. Re-confirmation of the live pattern (step 1) — still holds, unchanged

All queries run read-only against the live production Neon DB (`backend/.env`'s `DATABASE_URL`) via `psycopg2` in a read-only session, and against R2 via `boto3`, on 2026-10-31.

| Check | Result |
|---|---|
| Clause counts, all 15 docs | Identical to `company_data_storage.md`'s pre-cutover table, digit-for-digit (85, 70, 36, 48, 87, 86, 136, 237, 144, 331, 174, 147, 277, 228, 248) |
| `normalized_statement` populated | Registers (`DOC-000002/4/6`): 70/70, 48/48, 86/86 — 100%. Non-register (12 docs): **0 of 2,250** |
| `clause_parameters.is_citation_fragment` | Registers: 100% NULL (534/426/806 rows, all NULL). Non-register: 100% non-NULL (every doc's row count = its `n_set`, zero NULLs) — confirmed per-document this session, not just in aggregate |
| `llm_extractions` distinct `run_id`s | Exactly 3 (`591331f6…`, `77168fcd…`, `3775849f…`) — the 3 register run_ids. Zero for any of the 12 |
| `report.json` for a sample of the 12 (`DOC-000001`, `DOC-000008`, `DOC-000010`) | Fetched directly from R2 (`company/rpl/ingest_runs/{run_id}/report.json`, no `strata/` prefix needed — the boto3 client's configured `R2_ENDPOINT` already absorbs it): `stats={}`, `issues=[]`, `checks=[]` for all 3. Run durations: 2.46s, 1.69s, 1.72s |
| `clause_links` cross-document rows, non-register docs | `restates` 628/1996 cross-doc, `references_record_series` 232/320, `references_clause` 29/288, `references_tariff` 111/217, `references_form` 22/207, `references_obligation` 73/143 — all nonzero, matching the earlier audit exactly |

**No drift.** The pattern is exactly as described in `report.md`'s addendum and `tables_and_connections.md` §7/§8.

---

## 2. `reuse.py` — read in full, and definitively ruled out as the mechanism

Read `app/company_ingest/reuse.py` end to end (213 lines). What it actually does, precisely:

- It requires a **real prior `document_versions` row for the same `doc_id`** already present in `company.clauses` (`_PRIOR_CLAUSES_SQL` filters on `company_id`/`doc_id`/`version_id = :prior_version_id`). If `spec.supersedes_version_id` is `None` (i.e., this is nominally a first version), it returns `0` immediately (`reuse.py:136-137`) — no inheritance is possible at all for a document with no recorded predecessor in the new schema.
- When it does match (`text_sha256` + `unit_kind` + `section_kind` identical to a prior clause), it inherits **exactly four things, no more**: `clause_role`/`role_method`/`assessable` (only when the prior was LLM-assigned), `normalized_statement`, `topic_terms`, and `method='llm'` rows from `clause_parameters` (`reuse.py:184-205`).
- It **never reads or writes `clause_links`, `clause_citations`, or regex/non-LLM `clause_parameters` at all** — there is no SQL touching those tables anywhere in the file. Its own docstring (`reuse.py:26-42`) is explicit about this split: citations, regex parameters, and deterministic roles are *recomputed* by stage 4, never inherited; only LLM-derived fields are inherited, and `clause_links` isn't in either list.

**This rules reuse.py out, not just as "the most promising lead didn't pan out" but affirmatively, on two independent grounds:**

1. **Structural:** it has no code path that could ever populate `clause_links` (cross-document or otherwise) or set `is_citation_fragment`. Even in the maximally generous reading ("the 12 docs' *current* version is a new row created on top of an existing document that already had full v1-era data"), `reuse_from_prior_version` would still leave `clause_links`/`clause_citations`/`is_citation_fragment` entirely unset by this code — something else would still have to explain those.
2. **Empirical, and this is the clean kill:** if `reuse.py` had fired, it would have copied `normalized_statement` from the prior row (`reuse.py:188`, unconditional once a match with LLM output is found). The live data shows **zero** of 2,250 non-register clauses have `normalized_statement` set. A `reuse.py`-mediated carryover and "zero `normalized_statement`" are mutually exclusive outcomes of the same code path — you cannot inherit the parameters/role fields without the function also having inherited `normalized_statement` in the same loop iteration (`reuse.py:176-208` sets both in the same `for unit, row in matches` block, unconditionally once the `continue` guard at line 181-182 is passed). Since `normalized_statement` is uniformly null and LLM parameters/role somehow are not (is_citation_fragment, and clause_role presumably present), this is not a case of reuse.py having *partially* run — the two outcomes cannot both come from the same single pass through this function at all.

**Conclusion:** `reuse.py` did not produce this data, for any of the 12 documents. Whatever carried the data forward bypassed this mechanism entirely, or wrote the data by some other path that doesn't share reuse.py's inherit/recompute split.

---

## 3. `service.py` / `jobs.py` — every return path, checked (step 4)

`ingest_document` (`app/company_ingest/service.py:482-751`) is a single linear `async def` with **no early return** before the final `return IngestResult(...)` at line 735. The only other `return`s in the function body are inside nested helpers (`_delta`, `stats_before` closures) or raise `IngestError`/`CitationResolutionError` on failure paths (lines 614, 616, 695, 723) — none of which mark a job succeeded; a raised exception from inside `ingest_document` propagates up through `jobs.py` and would mark the job `failed`, not `succeeded`.

Critically: **stage 9 (the R2 snapshot write, `service.py:728-733`) is unconditional** — it runs for every successful call, immediately before the one and only `return`. Grepped `jobs.py`'s full `return`/job-state-transition logic as well: no path sets `state='succeeded'` without having first awaited the real `ingest_document()` call to completion (the job wrapper's success transition is downstream of that await, not short-circuited).

**This means: as the code exists today (and, as far as can be told from this one version of the file, structurally — there's nothing suggesting an older version would have differed in this specific property), a real, complete call to `ingest_document()` *cannot* produce `ingest_jobs.state='succeeded'` while also leaving the R2 derived snapshot missing.** Yet that is exactly the live state for all 12 documents (confirmed, §7 of `tables_and_connections.md`, re-confirmed above). This rules out "a real, complete call to today's `ingest_document()` ran and we're just missing the snapshot by some unrelated bug" — if it ran to completion (which the `'succeeded'` state implies), the snapshot write is not skippable on the success path.

So the 12 documents' `'succeeded'` ingest_jobs rows are not consistent with a real, complete run of the current `ingest_document()` as the code reads today — nor with a `reuse.py`-mediated partial run (§2). Both of the "went through a real, if assisted, call into service.py" sub-hypotheses that the task card asks to check are now ruled out. What's left is not visible in the current tracked code at all (see §5).

---

## 4. The git-history gap search (step 1's addendum) — closes the gap, surfaces one new lead, then rules it out too

Ran all four searches the task card calls out:

1. `git log --all -i -S "update company.clauses"` → **one hit**: `8697c45` ("company documents ingestion pipeline v2" — today's v1→v2 cutover commit). This is the same commit already known from the INSERT search; no separate UPDATE-only commit exists.
2. `git log --all --diff-filter=D --name-only -- backend/scripts` → three files deleted in `8697c45`: `demo_prep.py`, `fix_current_version_ids.py`, `score_run.py`. (`demo_prep.py`/`score_run.py` were actually *moved* to `backend/synthetic/`, confirmed by the full `--stat` diff showing `backend/{scripts => synthetic}/demo_prep.py` — only `fix_current_version_ids.py` is a pure, unreplaced deletion: 113 lines removed, 0 added.)
3. Migration `f7b2c91d4a08` (`v2_document_versioning`) — read in full: **pure DDL**, no DML beyond schema changes, consistent with `tables_and_connections.md` §7's existing classification.
4. `fix_current_version_ids.py`'s recovered content (`git show 8697c45^:backend/scripts/fix_current_version_ids.py`) looked, at first read, like a serious lead: its own docstring describes re-pointing `company_documents.current_version_id` / `document_versions.version_id` to an **already-existing, already-populated clause set** left over from the old `cli/ingest.py` pipeline (which used `version_id = stable_uuid(company_id, doc_id, fm.version or "v1")`, a **deterministic UUIDv5**) whenever the new pipeline's version row ended up pointing at an empty clause set. This would explain full carryover **without ever touching `company.clauses`** — exactly consistent with item 5's INSERT/UPDATE grep finding nothing, since this script only writes `document_versions`/`company_documents`.

   **This lead was then checked against live data and ruled out.** All 12 documents' actual `current_version_id` values are random **UUIDv4**s (version nibble `4`, e.g. `0082f3de-f216-**4**153-be76-f46920cb0cf4` for `DOC-000008`), not the deterministic UUIDv5 (`stable_uuid(...)`, version nibble `5`) the old `cli/ingest.py`/`fix_current_version_ids.py` scheme would produce — confirmed by recomputing `stable_uuid("rpl", doc_number, version_string)` for 3 sample documents and finding no match against the live `current_version_id`. All 15 documents' `document_versions.created_at` is today (2026-10-31, times clustered 09:04–09:22 UTC), and the clauses physically carry this same fresh version_id (joining `clauses.version_id = document_versions.version_id` returns the full, correct clause count for every document). So `fix_current_version_ids.py` is **not** the mechanism — whatever ran did create genuinely new `document_versions` rows with fresh random ids, and clause/parameter/link rows were attached under those fresh ids, not under some repointed old id.

**No git-tracked script or migration — INSERT, UPDATE, or ID-repointing — explains the live state.** The gap the task card flagged is now closed as thoroughly as git history allows; nothing further surfaces.

---

## 5. What this leaves: mechanism not found in any tracked code, current or historical

Putting §2–§4 together, the live state has a specific, oddly-split shape that no code in the repository (at any point in its tracked history) produces:

- Fresh-looking `document_versions` rows (random UUIDv4, today's timestamp, correctly linked `ingest_run_id`/`ingest_jobs.state='succeeded'`) — this part *is* new.
- `clauses`/`clause_citations`/`clause_parameters` rows attached under those fresh ids, with exact pre-cutover counts, non-null `is_citation_fragment`, and real content for all but 274 clauses — this part looks like **old, already-enriched data**, not freshly parsed.
- `clause_links` rows that are structurally impossible for the current single-document `resolve_refs.py`/`restates.py` call pattern to produce (confirmed by `service.py:663-664` and task 1.0's finding) — also old-looking data.
- `normalized_statement`/`topic_terms`/`llm_extractions`/R2 derived snapshot — all **absent**, which is what you'd get if the real stage-5 LLM-enrichment and stage-9 snapshot steps were *skipped*, not merely failed silently (a genuinely failed stage 5 would still try stage 9 per the unconditional code path in §3, and a crash anywhere would mark the job failed, not succeeded).

**No combination of `service.py`'s real `ingest_document()`, `reuse.py`, or any git-tracked script/migration (INSERT or UPDATE, case-insensitive, checked both ways) accounts for this shape.** The only candidate found in git history that was *structurally* capable of explaining it without touching `company.clauses` directly (`fix_current_version_ids.py`) is ruled out by the UUID-version-nibble evidence in §4.

**Ruled-out list, for the record:**
- A real, complete, unmodified call to today's `ingest_document()` — ruled out (§3: stage 9 is unconditional on the success path; the derived snapshot is missing for all 12).
- `reuse.py`-mediated inheritance from a prior version (with or without a same-day re-ingest on top) — ruled out (§2: structurally cannot touch `clause_links`/`is_citation_fragment`; empirically contradicted by `normalized_statement` being uniformly null).
- Any git-tracked script or migration directly writing (INSERT or UPDATE) to `company.clauses`/`clause_links`/`clause_parameters` — ruled out (§4 point 1, and the original case-sensitive INSERT-only grep).
- `fix_current_version_ids.py`'s ID-repointing trick (update `document_versions.version_id` to adopt an old, already-populated clause set's id, without touching `clauses` at all) — ruled out (§4 point 4: live `version_id`s are random UUIDv4s with today's timestamp, not the old deterministic UUIDv5 scheme this script operates on).

**What remains unexplained:** some process did insert/attach this data under the 12 documents' current (today-dated, UUIDv4) `document_versions` rows, did mark the corresponding `ingest_jobs` rows `'succeeded'`, and did write a `report.json` with the empty-stats/short-runtime shape characteristic of a near-no-op run — but it did not do this through any code path, tracked script, or migration present anywhere in this repository's git history. Either it ran via code that was never committed (an interactive REPL session, a one-off uncommitted local script, or a now-force-pushed/rebased-away commit not reachable by `git log --all`), or it happened through some infrastructure this investigation has no visibility into (a manual DB operation, a restore/import tool outside this codebase). This is exactly the kind of gap step 3 (application/Render logs around each `ingest_run_id`'s `started_at`/`finished_at`) is positioned to close, since logs would show what process actually made these specific calls — **and that step has not been done.**

---

## 6. Item 8 — the 274 empty-`text_raw` clauses: likely a copy-time artifact, not a current-code stripping rule, and it does degrade two live read sites

Live query (re-run, exact match to the task card's numbers): 274 clauses across the same 6 documents (`DOC-000008`: 29, `DOC-000010`: 83, `DOC-000012`: 29, `DOC-000013`: 60, `DOC-000014`: 37, `DOC-000015`: 36), zero elsewhere.

**Pattern found, not previously noted:** overwhelmingly, the affected `clause_id`s are the **first sub-clause of each top-level numbered section** — `local_id`s like `1.1`, `2.1`, `3.1`, … `10.1` for `DOC-000008`, and the equivalent "`N.1`" shape for the other 5 documents (confirmed by listing `unit_kind`/`section_kind` for every affected row: almost all are `unit_kind='section'` spanning every `section_kind` the documents use — `purpose`, `scope`, `definitions`, `roles`, `regulatory_basis`, `training`, `records`, `revision_history`, `related_docs`, `approval`, plus `appendix`-kind units). This looks like the "section header / container" clause for each numbered section, as opposed to its content sub-clauses (`N.2`, `N.3`, …), which are confirmed to carry real text.

**Checked against current code, not assumed:** `app/company_ingest/parse/markdown_segmenter.py` (the segmenter that would have produced any freshly-parsed version of these documents) has **no special case that zeroes `text_raw`** for header/container clauses — `text_raw` is always computed as a literal slice of the source body text (`markdown_segmenter.py:282`, `:497-502`), with no conditional stripping logic anywhere in the file. If these 274 rows had been produced by a fresh run of the current segmenter against the unchanged source `.md`, they would **not** be empty — the surviving v1 R2 snapshot (`derived/RPL-CS-PRO-004/v1/clauses.jsonl`) confirms this directly: the same `local_id`s have real (if sometimes short — a bare heading) content there. **This rules out "intentional stripping rule, current code" as the explanation.** It is a discrepancy between the two states, not a documented current-code behavior.

**Most likely explanation, not provable from the artifacts available to this investigation:** whatever process copied the old data forward (§5) lost or dropped text specifically for container/header-type clauses — plausibly a copy step that treated "N.1" nodes as pure structural parents and only copied text for leaf/content nodes, or a bug in whatever extraction re-derived `text_raw` for just these rows while leaving everything else (parameters, links, citations) intact. This is consistent with, but doesn't by itself prove, the broader carryover hypothesis — it's a separate defect riding on the same unexplained copy operation.

**Does it degrade a live read site? Yes, confirmed by code read, not just structurally:**
- `app/engine/judge.py:241` interpolates `item.text_raw` directly into the LLM judge's prompt (`f"{item.text_raw}"` inside the judge's prompt template) — for these 274 clauses the judge would see a blank clause body.
- `app/engine/judge.py:264` and `app/engine/rules.py:181-190` both call `verify_quote(cl, item.text_raw or "")` / `verify_quote(cq, clause.text_raw or "")` — against an empty string, `verify_quote` cannot find any quote, so any check depending on these specific 274 clauses' text would read as "quote not verified" rather than reflecting the clause's real (if short) content.

In practice this is a narrow, bounded degradation (274 of 2,334 total clauses, 11.7%, confined to 6 documents' container-level rows) rather than a correctness crisis, but it is real, confirmed-live, and not an intentional design choice in the current pipeline.

---

## 7. Step 3 (human-only) — explicitly flagged as NOT done

Per the task card, checking Render's log viewer (or wherever `uvicorn`/`BackgroundTasks` output for these specific `ingest_run_id`s landed) around each of the 12 documents' `started_at`/`finished_at` is **human-only** — this sub-agent has no access to Render's dashboard or any log aggregation system. **This has not been attempted and remains the single most likely way to actually resolve §5's open question** — real application logs from the actual timestamps (today, 09:04–09:22 UTC per the live `document_versions.created_at` values pulled in this session) would show whatever process made these specific `ingest_run_id`s/`ingest_jobs` rows exist, something no amount of further DB/git archaeology can supply. Flagging back to the user: **please pull Render's logs for run_ids `7f30d5ae-c5f6-4a9a-8961-09ec0375337d` (DOC-000001), `6569055e-89ad-4057-826e-91ff40fb6e46` (DOC-000008), and `62b01826-cd9b-4373-b2dc-a9a5acc8f166` (DOC-000010)** around 2026-10-31 09:04–09:22 UTC, as a representative sample, and check for any admin/maintenance endpoint call, bulk-import script invocation, or swallowed exception in that window.

## 8. Step 5 — skipped, as instructed

Reproduction against a scratch Postgres via `rehearsal.py`/`rehearsal_inner.py` was not attempted. Per the task card this requires provisioning throwaway infrastructure (a scratch Postgres instance) and potentially paid LLM calls, neither of which this investigation could do "fully offline with no new infrastructure." Skipping per the task card's own instruction, not attempted.

---

## Summary for acceptance

- **Mechanism:** not found. Every candidate mechanism visible in the current or historical tracked codebase — a real `ingest_document()` call, `reuse.py`-mediated inheritance, a tracked INSERT/UPDATE script or migration, and the one promising ID-repointing script (`fix_current_version_ids.py`) found via the expanded git search — has been checked against live data and **affirmatively ruled out**, each on a specific, falsifiable ground (§2–§4).
- **Ruled-out list:** see §5.
- **Step 3 (human log review):** **not done.** Specific run_ids and time window to check are listed in §7.
- **Step 5 (scratch-DB reproduction):** **skipped**, per the task card's own instruction (would require new infrastructure and possibly paid LLM calls).
- **Item 8 (274 empty-`text_raw` clauses):** new pattern identified (concentrated in section-header/container clauses, "`N.1`" local_ids); ruled out as a current-code stripping rule (segmenter has no such logic); confirmed to degrade two live read sites (`judge.py`'s prompt construction and `verify_quote` calls in both `judge.py` and `rules.py`) for the affected 274 clauses specifically. Root cause of the data loss itself remains open, tied to the same unexplained carryover mechanism as the rest of this report.
- **No live data was written to.** All Neon queries used a read-only session (`conn.set_session(readonly=True)`); R2 access was read-only `get_object`/`head_object`. **No document was re-ingested or re-uploaded.**
