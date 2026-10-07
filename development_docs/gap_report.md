# Company Data Ingestion — Gap Report
Date: 2026-10-07
Test count (non-corpus): **803 passing** (94 deselected for qdrant/corpus/neon marks)

> **Update (same date):** GAP-1 resolved. `store/neon.py` built with bulk insert functions
> for all 18 `company.*` tables. CLI wired to call `commit_run` inside an `AsyncSession`
> transaction. All 803 non-corpus tests still pass.

---

## ✅ Completed tasks (by wave)

### W1
| Task | Files |
|------|-------|
| 1.1.1 Package skeleton, config, constants, ids | `company_ingest/__init__.py` + sub-package `__init__.py` files, `constants.py`, `ids.py` (config lives in `app/config.py`) |

### W2
| Task | Files |
|------|-------|
| 1.1.2 RunContext + issue log | `run_context.py` |
| 1.2.1 Neon migrations — company schema | `backend/migrations/versions/c3d4e5f6a7b8_company_schema.py`, `store/schema.sql` |
| 1.2.2 R2 client + key builder | `store/r2.py`, `store/r2_keys.py` |
| 1.2.3 Qdrant collection setup | `index/qdrant_setup.py` |
| 1.3.1 Text utilities | `parse/text.py`, `parse/numbers.py` |
| 1.3.2 Citation parser adapter | `enrich/citations_grammar.py` |
| 1.3.3 LLM client | `llm/client.py` |

### W3
| Task | Files |
|------|-------|
| 2.1.1 Collector + allowlist | `collect/allowlist.py`, `collect/collector.py` |
| 2.1.2 Reference data loaders | `collect/reference.py` |
| 2.2.1 Front-matter parser + register_docs | `parse/front_matter.py`, `collect/register_docs.py` |

### W4
| Task | Files |
|------|-------|
| 3.1.1 Markdown segmenter | `parse/markdown_segmenter.py` |
| 3.2.1 Register-row segmenter | `parse/register_segmenter.py` |
| 7.1.1 Dataset profiling + Parquet | `datasets/profile.py` |

### W5
| Task | Files |
|------|-------|
| 4.1.1 Citation extraction | `enrich/citations.py` |
| 4.1.2 Parameter extraction (regex) | `enrich/parameters_regex.py` |
| 4.1.3 Reference extraction | `enrich/references.py` |
| 4.1.4 Clause-role markers | `enrich/roles.py` |
| 4.1.5 Defined terms + usages | `enrich/terms.py` |
| 7.1.2 Dataset key detection | `datasets/keys.py` |

### W6
| Task | Files |
|------|-------|
| 5.1.1 LLM schemas + prompts | `llm/schemas.py`, `llm/clause_enrichment.py`, `llm/prompts/clause_enrichment.md`, `llm/prompts/doc_class.md` |
| 5.2.1 Column roles | `llm/run_column_roles.py`, `llm/prompts/column_roles.md` |
| 7.2.1 DuckDB runner | `datasets/duckdb_runner.py` |

### W7
| Task | Files |
|------|-------|
| 5.1.2 LLM enrichment runner | `llm/run_clause_enrichment.py` |
| 6.1.1 Resolve refs | `link/resolve_refs.py` |
| 6.1.3 Document scope | `link/document_scope.py` |
| 7.2.2 Propose checks | `datasets/propose_checks.py`, `llm/prompts/parameter_checks.md` |

### W8
| Task | Files |
|------|-------|
| 6.1.2 Restates links | `link/restates.py` |
| 6.2.1 Embeddings + Qdrant indexing | `index/embed.py`, `index/bm25.py`, `index/upsert.py` |
| 7.2.3 Validate checks | `datasets/validate_checks.py` |

### W9
| Task | Files |
|------|-------|
| 8.1.1 Acceptance checks | `validate/checks.py` |
| 8.1.2 Snapshot + report | `store/commit.py`, `store/snapshot.py` |

### W10
| Task | Files |
|------|-------|
| 8.2.1 CLI | `cli/ingest.py` |

### W11
| Task | Files |
|------|-------|
| 9.1.1 Offline eval tool | `tools/offline_eval/compare_basis.py`, `tools/offline_eval/README.md` |
| 9.1.2 End-to-end test | `tests/company_ingest/test_e2e_corpus.py` |

All 33 tasks across W1–W11 have corresponding source files present.

---

## ⚠️ Deviations and known gaps

### ~~GAP-1: Neon DB writes not implemented~~ ✅ RESOLVED
- **Specified:** `store/commit.py` should write all rows (clauses, citations, parameters, terms, usages, links, scope, table columns, datasets, columns, checks) to Neon in one transaction; `collect/reference.py` data should be inserted into Neon.
- **Built:** `store/commit.py` only computes `value_source` in-memory and builds a `report.json` dict. The actual Neon inserts are absent. The CLI (`cli/ingest.py` lines 95–101 and 250–256) has two explicit `# TODO: Neon writes` comments showing exactly where DB calls should go. Reference data load is also skipped.
- **Severity:** CRITICAL — the pipeline does not persist any data to the Neon database. R2 writes and Qdrant indexing still work. Phase A testing (--no-llm --no-datasets) is possible for validation logic but produces no Neon rows.

### GAP-2: `--refresh-llm` and `--only DOC_ID` CLI flags missing (MINOR)
- **Specified:** Task 8.2.1 spec lists `[--refresh-llm]` (force new LLM calls even on a rebuild) and `[--only DOC_ID ...]` (restrict to specific docs while still loading others' clause IDs from Neon).
- **Built:** Neither flag is present in `cli/ingest.py`. The four flags implemented are `--no-llm`, `--no-datasets`, `--rebuild`, `--dry-run`.
- **Severity:** MINOR for Phase A (these are optional extensions). `--dry-run` (not in the spec) was added as a bonus.

### GAP-3: `store/commit.py` scope (INFO)
- **Specified:** Task 8.1.2 — `store/commit.py` and `store/snapshot.py` handle commit + snapshot + report as a unit.
- **Built:** The spec says `store/commit.py` owns the Neon transaction. It only owns in-memory finalization (`finalize_parameters`, `build_run_report`). The Neon transaction body is in the CLI as a TODO block. The split is functional but deviates from the file-ownership described in the spec.
- **Severity:** INFO — the logic is in the right directory; the Neon transaction stub is co-located with where it belongs once a live DB is available.

### GAP-4: `config.py` owned by company_ingest (INFO)
- **Specified:** Task 1.1.1 item 2 — create `config.py` under `backend/app/company_ingest/`. If the backend already has a settings module, extend it instead.
- **Built:** Settings are extended into `backend/app/config.py` (the existing backend settings module), not a standalone `company_ingest/config.py`. All company-ingest env vars (`CORPUS_ROOT`, `COMPANY_ID`, `R2_*`, `QDRANT_*`, `LLM_*`, `EMBED_*`) are present.
- **Severity:** INFO — spec explicitly allows this ("If the backend already has a settings module, extend it instead"). Compliant.

---

## 🔴 Missing or incomplete items

1. **Neon persistence** (GAP-1 above): No rows are written to `company.*` tables. The migration exists and is correct, but the runtime insert path is not implemented. This is the single largest gap between spec and built code.

2. **`--only` flag** (GAP-2): Cross-document link resolution works for the full run. The `--only` scoping (load other docs' clause IDs from Neon, restrict processing) is not present — partly because there are no Neon reads to pull existing clause IDs from.

---

## 🟡 Partial implementations

### store/commit.py
- In-memory finalization (`finalize_parameters`, `build_run_report`, `write_report`) is complete and tested.
- The Neon transaction is a documented stub in `cli/ingest.py`. Tests for `test_commit_snapshot.py` cover the in-memory path and R2 report writing.

### collect/reference.py
- Parsing of `company_profile.yaml`, `people_directory.csv`, and `document_register.csv` is implemented.
- Loading parsed data into Neon (upsert to `companies`, `company_attributes`, `people`) is skipped in the CLI due to the missing DB session wiring.

### test_e2e_corpus.py (9.1.2)
- File exists with the three-configuration structure (--no-llm --no-datasets; full LLM; full).
- Tests are marked `corpus`, `qdrant`, `neon` and excluded from the non-corpus run. They exercise the CLI end-to-end but cannot assert Neon row counts until GAP-1 is resolved.

---

## Additional spot-checks (all passed)

| Item | Finding |
|------|---------|
| LLM model ID in `.env.example` | `LLM_MODEL=claude-sonnet-5-5` ✅ |
| Migration table count | 18 tables: companies, company_attributes, people, company_documents, document_versions, clauses, clause_citations, clause_parameters, defined_terms, term_usages, clause_links, document_scope, table_columns, datasets, dataset_columns, parameter_checks, llm_extractions, ingest_runs ✅ (exceeds 17-table minimum) |
| Information barrier in `compare_basis.py` | Imports only stdlib (argparse, json, re, sys, collections, pathlib, typing) — zero `backend/app/` imports ✅ |
| `ClauseUnit` fields | All required fields present: version_id, doc_id, clause_id, local_id, parent_clause_id, unit_kind, heading_path, section_kind, ordinal, char_start, char_end, line_start, text_raw, text_norm, text_sha256, sheet_no, table_id, row_cells, citations, parameters, refs, role, role_method, assessable, terms, normalized_statement, topic_terms ✅ |
| All 5 enrich functions (4.1.1–4.1.5) | citations.py, parameters_regex.py, references.py, roles.py, terms.py — all present ✅ |
| All link modules | resolve_refs.py, document_scope.py, restates.py — all present ✅ |
| All index modules | embed.py, bm25.py, upsert.py — all present ✅ |
| All dataset modules | profile.py, keys.py, duckdb_runner.py, propose_checks.py, validate_checks.py — all present ✅ |
| CLI flags | --no-llm, --no-datasets, --rebuild, --dry-run present ✅; --refresh-llm and --only missing ⚠️ |
| pytest.ini marks | qdrant, corpus, neon registered ✅ |
| R2 upload in collect() | Implemented via real boto3 client; write-once semantics enforced ✅ |
| `tools/offline_eval/` exists | Yes, with compare_basis.py, README.md, test_compare_basis.py ✅ |

---

## 🟢 Summary

**All 33 tasks have source files on disk.** The pipeline architecture is complete: collection, segmentation, deterministic enrichment, LLM enrichment, link resolution, Qdrant indexing, dataset profiling, acceptance checks, CLI orchestration, and the offline evaluation tool are all built. The test suite passes 803 non-corpus, non-qdrant, non-neon tests.

**Phase A readiness (`--no-llm --no-datasets`):** The pipeline can run end-to-end in memory, pass acceptance checks, write R2 objects (raw files + clauses.jsonl + report.json), and upsert Qdrant points. It is ready for Phase A **validation logic** testing.

**Blocking gap for Phase A production use:** Neon DB writes are not implemented (GAP-1). The pipeline cannot persist clauses, citations, parameters, links, or scope rows. Until the Neon insert path is wired (the TODO stubs in `cli/ingest.py` lines ~99 and ~253 need a live `AsyncSession` and bulk-insert functions), the pipeline cannot be promoted to any environment that depends on queryable Neon data. This is the single required fix before Phase A milestone is fully met.
