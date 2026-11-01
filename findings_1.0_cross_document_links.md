# Task 1.0 — Cross-document link gap: decision document

**Status:** read-only investigation complete. No code changed. No writes made to Neon, R2, or Qdrant.
**Scope:** the 3 register documents (`DOC-000002`, `DOC-000004`, `DOC-000006`) only, per the task card — the 12 non-register documents' link data is excluded as evidence (its provenance is `implementation_plan.md` task 1.2's open question, not re-derived here).

---

## 1. The confirmed mechanism (not re-derived — restated for this document's context)

`app/company_ingest/service.py:663-664`:

```python
links = resolve_references(units, known_doc_ids, ctx)
links.extend(find_restates_links(units, links, ctx))
```

`units` is built fresh inside `ingest_document`, scoped to exactly one document version. Every index builder in `app/company_ingest/link/resolve_refs.py` (`_build_clause_index`, `_build_sheet_index`, `_build_rule_index`, `_build_form_index`, `_build_series_index`, `_build_obligation_index`, `_build_doc_index`) is built only from that list — so `references_clause`, `references_tariff`, `references_form`, `references_record_series`, `references_obligation`, and `restates` can only ever resolve to a target inside the same document being ingested. `references_doc` is checked against a real cross-document set (`registered_doc_ids`, sourced from `company.company_documents`), so it is structurally capable of cross-document resolution — but see §3.

`app/engine/candidates.py`'s `LINK_TYPES = ("references_clause", "references_obligation", "references_record_series", "references_tariff", "references_form")` — `restates` is excluded; this audit found no consumer of `restates` links anywhere in `app/engine/`.

## 2. Precise product impact — a concrete, specific missing engine candidate (not a hypothetical)

Using only the register documents' own `report.json` (fetched live from R2 at `company/rpl/ingest_runs/{run_id}/report.json` for each of the three register ingest runs), their `unresolved_ref` warning counts are:

| Doc | `unresolved_ref` warnings | All `ref_type` |
|---|---|---|
| `DOC-000002` (`RPL-CMP-REG-001#register`) | 68 | `references_clause` |
| `DOC-000004` (`RPL-REG-CAL-2025#register`) | 32 | `references_clause` |
| `DOC-000006` (`RPL-LEG-RRS-001#register`) | 67 | `references_clause` |

All 167 are `references_clause`, all carry a `target_hint` in `"<doc_number>:<local_id>"` form (e.g. `RPL-TAR-GRR-012:R01.D01`), and all are hints the current architecture cannot resolve (see §3 for why — it's not just "wrong document," the format itself can't match).

**I traced one of these 167 hints end-to-end against the engine's actual, live `engine.runs`/`engine.candidates`/`engine.findings` data** (run `858d3160-8c5a-4468-9021-6d0690095f54`, the one real `kind='kb'` run; 41 `findings`, 262 `register_hop` candidates):

- `DOC-000006`'s own `report.json` records: `DOC-000006:RRS-FIN-003` has an unresolved `references_clause` ref to `RPL-TAR-GRR-012:R01.D20`.
- `RRS-FIN-003` is a record-retention-series register row ("Rate Case Supporting Documentation"). Its raw content literally includes a field whose only purpose is to declare this exact cross-document link: `wave2_clause_ref: RPL-TAR-GRR-012:R01.D20`, plus `retention_basis: 170 IAC 1-5-9; company practice` and a notes field citing `170 IAC 1-6`.
- The target, `DOC-000007:R01.D20` (`RPL-TAR-GRR-012`, the live tariff), defines "Nonrecurring Charge... as defined in 170 IAC 1-6-2(11)."
- **170 IAC 1-6-2 is a real, open (`change_class='substantive'`) regulatory change in this exact run.** It directly hits `DOC-000007:R01.D20` (`match_path='direct_section'`), and the engine already ran its real LLM judge on that hit: `affected=False`, rationale *"The only change to the nonrecurring charge definition is wording... Its substance and its paragraph number (11) are unchanged... The substantive changes concern 'noncontroversial filing' and the deleted SDC definition, which this clause does not cover."*
- **`register_hop` — the exact code path this task is about (`app/engine/candidates.py`, one hop from a directly-hit clause across a `clause_links` row whose `link_type` is in `LINK_TYPES`) — is proven live in this same run**, not hypothetical: it produced 262 of this run's candidates, and at least one ambiguous case (`candidate_id 5c70a180` -> `finding_id f2941f2e`, an existing, separate cross-document `references_clause` link from `DOC-000001:11.2` to this same `DOC-000007:R01.D01`) was already promoted to a real finding (`finding_type='informational'`, `verdict='review'`, `needs_review=True`). *(That particular source link is itself one of the 12 non-register documents' links, whose provenance is task 1.2's open question — it is cited here only to prove the downstream `register_hop -> candidate -> finding` pipeline is live and wired, not as evidence about the register documents.)*

**The missing output, stated precisely:** had `DOC-000006:RRS-FIN-003 -> DOC-000007:R01.D20` resolved into a real `references_clause` row in `company.clause_links` (as its own `wave2_clause_ref` field says it should), `register_hop` would have added one additional `engine.candidates` row today — `clause_id='DOC-000006:RRS-FIN-003'`, `cited_citation='170 IAC 1-6-2'`, `match_path='register_hop'` — and that candidate would go through its own, independent LLM judgment using `RRS-FIN-003`'s own text (a retention-obligation row, not a tariff definition), not automatically inherit `R01.D20`'s "not affected" verdict. **I cannot determine, read-only, what that judgment would have been** — but the live pattern in this exact run (29 of 41 findings are `register_hop`/`direct_rule` candidates the LLM judge returned `None`/ambiguous for, auto-promoted to `needs_review=True` findings) means there is a real, non-trivial chance this specific missing link would have produced a 42nd finding: a human-review flag on the one register row that exists specifically to track which retention obligations are tied to which tariff clause — exactly the kind of cross-document relationship this register was built to carry, and exactly the kind of finding a compliance reviewer would want surfaced.

**Scope check (zero cross-document outbound links, confirmed, consistent with the task card's framing):** every `clause_links` row where a register document is the *source* is intra-document only — `DOC-000002->DOC-000002` (70 `references_obligation`), `DOC-000004->DOC-000004` (92 `restates`), `DOC-000006->DOC-000006` (88 `references_record_series`, 356 `restates`). The 216/81/65 `engine.candidates` rows that do exist for `DOC-000002`/`DOC-000004`/`DOC-000006` all arrive via links pointing *in* from the 12 other documents (carryover data, task 1.2's territory) — never via a link any register document's own ingest produced. None of the 167 recorded `unresolved_ref` targets I checked across all three register documents happen to be a clause directly hit by a *substantive* change in this specific run except the one above — the rest land on clauses only hit by `cosmetic`-class changes, which this run's candidate pipeline auto-resolves to `affected=False` without an LLM call and never promotes to a finding. That makes the `RRS-FIN-003`/`R01.D20` pair the one clean, fully-traceable example in the current live data — not proof that it's the *only* one that will ever occur, since every future regulatory KB update changes which clauses are "direct."

## 3. The hint-format / translation gap — confirmed more precisely than before

Previously confirmed: no code anywhere in `enrich/references.py` or `resolve_refs.py` translates a `doc_number` (`RPL-TAR-GRR-012`) into a `doc_id` (`DOC-000007`).

**New, more precise confirmation from reading `resolve_references`'s actual matching logic (`resolve_refs.py:218-225`):**

```python
full_id = hint if ":" in hint else f"{unit.doc_id}:{hint}"
if full_id not in clause_index:
    _warn(...)
```

`clause_index` (`_build_clause_index`) is keyed by `ClauseUnit.clause_id`, which is always `"<doc_id>:<local_id>"` (e.g. `"DOC-000007:R01.D20"`). But every one of the 167 recorded hints is already colon-joined in `"<doc_number>:<local_id>"` form (`"RPL-TAR-GRR-012:R01.D20"`) — so `full_id` is set to the hint *as-is* and compared directly against `doc_id`-keyed strings. **This lookup cannot succeed even in principle, regardless of whether `units` is single-document or whole-corpus-scoped** — the single-document scoping is necessary but not sufficient to explain the 167 failures; the `doc_number`-vs-`doc_id` prefix mismatch is a second, independent reason every one of these specific hints was always going to fail, confirmed directly from the comparison logic, not inferred.

**This means any fix to the scoping problem (§4) still needs a `doc_number -> doc_id` translation step added — confirmed, not assumed** — either as a lookup against `company.company_documents.doc_number` before the `clause_index`/`doc_index` check, or by changing what gets written into `target_hint` further upstream in the parser. Neither currently exists.

## 4. Fix design — options, not a pick

### (a) Re-run resolution against the whole corpus, every ingest
Query Neon for all of the company's current clauses/units (not just the one document being ingested) and re-run `resolve_references`/`find_restates_links` against that full set on every ingest.
- **Pro:** simplest to reason about; single code path; always fully consistent immediately after any ingest.
- **Con:** turns a per-document operation into one whose cost scales with total corpus size (today: 15 documents / ~2,300 clauses; this will only grow). Every future ingest re-pays the cost of re-resolving documents that haven't changed.

### (b) Background reconciliation job
A job (triggered post-promotion, or scheduled) that re-scans the whole corpus for cross-document links, independent of any single ingest call.
- **Pro:** matches the pre-cutover v1 batch model, which could do this naturally; keeps per-document ingest cheap and fast.
- **Con:** reintroduces exactly the kind of corpus-wide batch job the v1->v2 cutover was designed to eliminate (per the recovered `TDD.md`/`architecture.md` design docs cited in `report.md`). Needs its own scheduling/triggering/failure-handling design, which doesn't exist today in any form — `app/` has zero hits for "relink"/"reconcile"/"cross_document" (confirmed by grep).

### (c) Narrower: re-resolve only the backlog of recorded failures
Use each run's own recorded `unresolved_ref` warnings (already sitting in `report.json`, as demonstrated in §2) as a ready-made backlog, and re-attempt resolution for just those specific `(from_clause, target_hint)` pairs whenever a new document is promoted (checking whether the new document's `doc_number`/clauses satisfy any outstanding hint).
- **Pro:** bounded, incremental cost — doesn't scale with total corpus size, only with the (presumably much smaller) backlog of previously-unresolved hints; naturally self-documenting (the backlog itself is an audit trail of what got fixed and when).
- **Con:** needs a place to persist the backlog durably (today it only lives inside each run's `report.json` in R2 — not queryable, not indexed by target); doesn't retroactively help if a referenced document is deleted/never arrives; still needs the translation step in §3 regardless, same as (a)/(b).

**All three options need the `doc_number -> doc_id` translation from §3 as part of the fix, not as an assumed-solved prerequisite** — none of (a)/(b)/(c) becomes meaningfully simpler by picking one over another on this specific point.

## 5. What this document is not

This is a decision document, not a fix. No code was changed as part of this task. The next step is the user's choice of (a)/(b)/(c) (or a hybrid), at which point it becomes its own follow-up task with its own task card, per the task's own instruction not to implement a fix here.

---

## Confirmation of guardrails followed

- Zero writes to Neon (all queries were `SELECT`; no `INSERT`/`UPDATE`/`DELETE` issued).
- Zero writes to R2 (only `get_object` calls against existing `report.json` keys).
- Zero writes to Qdrant (not touched — not needed for this task).
- No document was uploaded, re-ingested, or re-versioned.
- No file in the repo was modified or deleted; this is the only new file created.
- Evidence base was limited to the 3 register documents (`DOC-000002`/`000004`/`000006`) as required; the one citation of a 12-non-register-document link (`DOC-000001:11.2 -> DOC-000007:R01.D01`) in §2 is used only to demonstrate that the engine's `register_hop` pipeline is live and wired end-to-end — not as evidence about the register documents' own data or about task 1.2's open provenance question.
