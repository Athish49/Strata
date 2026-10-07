"""Task 8.2.1 — `ingest` CLI and orchestration.

Entry point for the Strata company data ingestion pipeline.
Runs all pipeline stages in order, with flags to skip LLM, datasets,
and dry-run mode (skips Neon and R2 writes).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from app.company_ingest.run_context import RunContext
from app.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    """CLI entry point for the company ingest pipeline."""
    parser = argparse.ArgumentParser(description="Strata company data ingestion")
    parser.add_argument("--company-id", default=settings.COMPANY_ID)
    parser.add_argument("--corpus-root", default=settings.CORPUS_ROOT)
    parser.add_argument("--no-llm", action="store_true", help="Skip all LLM calls")
    parser.add_argument("--no-datasets", action="store_true", help="Skip dataset profiling and checks")
    parser.add_argument("--rebuild", action="store_true", help="Force re-ingest of already-ingested docs")
    parser.add_argument("--dry-run", action="store_true", help="Run all stages but do not write to Neon or R2")
    args = parser.parse_args()
    exit_code = asyncio.run(_run(args))
    sys.exit(exit_code)


async def _run(args: argparse.Namespace) -> int:
    """Run the full ingest pipeline. Returns exit code (0=success, 1=failure)."""
    # Import stage functions here so they can be patched in tests
    from app.company_ingest.collect.collector import collect
    from app.company_ingest.datasets.keys import detect_keys
    from app.company_ingest.datasets.profile import profile_dataset
    from app.company_ingest.datasets.propose_checks import propose_checks
    from app.company_ingest.datasets.validate_checks import validate_checks
    from app.company_ingest.enrich.citations import enrich_citations
    from app.company_ingest.enrich.parameters_regex import enrich_parameters
    from app.company_ingest.enrich.references import enrich_references
    from app.company_ingest.enrich.roles import enrich_roles
    from app.company_ingest.enrich.terms import extract_terms, find_term_usages
    from app.company_ingest.ids import stable_uuid
    from app.company_ingest.index.upsert import upsert_clauses
    from app.company_ingest.link.document_scope import build_document_scope
    from app.company_ingest.link.resolve_refs import resolve_references
    from app.company_ingest.link.restates import find_restates_links
    from app.company_ingest.llm.run_clause_enrichment import run_clause_enrichment
    from app.company_ingest.llm.run_column_roles import run_column_roles
    from app.company_ingest.parse.front_matter import split_front_matter
    from app.company_ingest.parse.markdown_segmenter import segment_with_ctx
    from app.company_ingest.parse.register_segmenter import segment_register
    from app.company_ingest.store.commit import build_run_report, finalize_parameters
    from app.company_ingest.store.snapshot import write_clause_snapshot
    from app.company_ingest.validate.checks import RunState, run_all_checks
    from app.company_ingest.constants import Profile

    ctx = RunContext(
        company_id=args.company_id,
        no_llm=args.no_llm,
        no_datasets=args.no_datasets,
        rebuild=args.rebuild,
    )

    # Override corpus root if provided via CLI
    if args.corpus_root:
        os.environ["CORPUS_ROOT"] = args.corpus_root

    try:
        # -----------------------------------------------------------------
        # Stage 1: Collect
        # -----------------------------------------------------------------
        logger.info("Stage 1: Collect")
        sources = collect(ctx, upload_r2=not args.dry_run)
        ctx.count("sources_collected", len(sources))

        # -----------------------------------------------------------------
        # Stage 2: Segment (P1 prose, P2 register, P3 datasets)
        # -----------------------------------------------------------------
        logger.info("Stage 2: Segment")
        all_units: list = []

        p1_sources = [s for s in sources if s.profile == Profile.P1_PROSE]
        p2_sources = [s for s in sources if s.profile == Profile.P2_REGISTER]
        p3_sources = [s for s in sources if s.profile == Profile.P3_DATASET]

        # Load reference data (P4 files → Neon)
        from app.company_ingest.collect.reference import load_reference_data
        from app.db import AsyncSessionLocal
        register_entries = []
        if not args.dry_run:
            async with AsyncSessionLocal() as _ref_session:
                register_entries = await load_reference_data(
                    sources, _ref_session, args.company_id, ctx
                )
                await _ref_session.commit()

        # P1 segmentation: read each .md, split front matter, segment
        for source in p1_sources:
            text = source.abs_path.read_text(encoding="utf-8")
            fm, body, offset = split_front_matter(text, source.doc_id)
            version_id = str(stable_uuid(args.company_id, source.doc_id or "", fm.version or "v1"))
            units = segment_with_ctx(version_id, source.doc_id, body, offset, ctx)
            all_units.extend(units)

        # P2 segmentation
        col_roles_map: dict[str, dict[str, str | None]] = {}
        for source in p2_sources:
            doc_key = source.doc_id or source.rel_path
            version_id = str(stable_uuid(args.company_id, doc_key, source.rel_path))
            units, col_roles = segment_register(
                version_id,
                source.doc_id or "global",
                source.abs_path,
                source.doc_id or "",
                ctx,
            )
            all_units.extend(units)
            col_roles_map[doc_key] = col_roles

        # P3 profiling (if not --no-datasets)
        dataset_profiles: list = []
        if not args.no_datasets:
            for source in p3_sources:
                profile = profile_dataset(
                    source,
                    args.company_id,
                    str(ctx.run_id),
                    ctx,
                    upload_r2=not args.dry_run,
                )
                dataset_profiles.append(profile)
            detect_keys(dataset_profiles, {}, ctx)

        # -----------------------------------------------------------------
        # Stage 3: Deterministic enrichment (all 5 passes)
        # -----------------------------------------------------------------
        logger.info("Stage 3: Deterministic enrichment")
        registered_doc_ids = list({s.doc_id for s in sources if s.doc_id})
        enrich_citations(all_units, ctx)
        enrich_parameters(all_units, ctx)
        enrich_references(all_units, registered_doc_ids, ctx)
        enrich_roles(all_units, ctx)
        terms = extract_terms(all_units, ctx)
        term_usages_list = find_term_usages(terms, all_units, ctx=ctx)

        # -----------------------------------------------------------------
        # Stage 4a: LLM clause enrichment
        # -----------------------------------------------------------------
        logger.info("Stage 4a: LLM clause enrichment")
        await run_clause_enrichment(all_units, ctx)

        # -----------------------------------------------------------------
        # Stage 4b: LLM column roles (skipped if --no-llm)
        # -----------------------------------------------------------------
        if not args.no_llm:
            logger.info("Stage 4b: LLM column roles")
            for doc_key, col_roles in col_roles_map.items():
                headers = list(col_roles.keys())
                sample_units = [u for u in all_units if u.doc_id == doc_key][:5]
                sample_rows = [u.row_cells for u in sample_units if u.row_cells]
                updated = await run_column_roles(doc_key, headers, col_roles, sample_rows, ctx)
                col_roles_map[doc_key] = updated

        # -----------------------------------------------------------------
        # Stage 4c: Dataset checks (skipped if --no-datasets or --no-llm)
        # -----------------------------------------------------------------
        proposals: list = []
        if not args.no_datasets and not args.no_llm:
            logger.info("Stage 4c: Dataset checks")
            all_proposals: list = []
            for dp in dataset_profiles:
                desc, dp_proposals = await propose_checks(dp, all_units, [], ctx)
                all_proposals.extend(dp_proposals)
            # Build parameter map for validation
            param_map: dict = {}
            for unit in all_units:
                for i, p in enumerate(unit.parameters):
                    pk = f"{unit.clause_id}:{i}"
                    param_map[pk] = p
            proposals = validate_checks(all_proposals, param_map, {}, ctx)

        # -----------------------------------------------------------------
        # Stage 5: Link resolution
        # -----------------------------------------------------------------
        logger.info("Stage 5: Link resolution")
        links = resolve_references(all_units, registered_doc_ids, ctx)

        # -----------------------------------------------------------------
        # Stage 6: Document scope rollup
        # -----------------------------------------------------------------
        logger.info("Stage 6: Document scope")
        # Build a map of doc_id → version_id using the same logic as insert_document_versions
        # (derive from the first unit for that doc, or fall back to stable_uuid with "v1")
        _doc_version_id_map: dict[str, str] = {}
        for _u in all_units:
            if _u.doc_id and _u.doc_id not in _doc_version_id_map:
                _doc_version_id_map[_u.doc_id] = _u.version_id
        scope_rows: list = []
        for doc_id in registered_doc_ids:
            doc_units = [u for u in all_units if u.doc_id == doc_id]
            _scope_version_id = _doc_version_id_map.get(
                doc_id, str(stable_uuid(args.company_id, doc_id, "v1"))
            )
            rows = build_document_scope(doc_id, _scope_version_id, doc_units, [], ctx)
            scope_rows.extend(rows)

        # -----------------------------------------------------------------
        # Stage 7: Restates links
        # -----------------------------------------------------------------
        logger.info("Stage 7: Restates links")
        restates = find_restates_links(all_units, links, ctx)
        links.extend(restates)

        # -----------------------------------------------------------------
        # Stage 8: Qdrant indexing (skipped if --dry-run)
        # -----------------------------------------------------------------
        if not args.dry_run:
            logger.info("Stage 8: Qdrant indexing")
            await upsert_clauses(all_units, args.company_id, "v1", ctx)

        # Finalize parameters before acceptance checks
        finalize_parameters(all_units)

        # -----------------------------------------------------------------
        # Stage 9: Acceptance checks
        # -----------------------------------------------------------------
        logger.info("Stage 9: Acceptance checks")
        state = RunState(
            units=all_units,
            links=links,
            scope_rows=scope_rows,
            dataset_profiles=dataset_profiles,
            check_proposals=proposals,
            doc_ids=registered_doc_ids,
            stats=ctx.stats,
            issues=ctx.issues,
        )
        outcomes = run_all_checks(state, ctx)

        # -----------------------------------------------------------------
        # Stage 10: Snapshot + report (write steps skipped if --dry-run)
        # -----------------------------------------------------------------
        logger.info("Stage 10: Snapshot + report")
        # finalize_parameters is idempotent
        finalize_parameters(all_units)

        if not args.dry_run:
            from app.company_ingest.store import r2 as _r2_mod
            for doc_id in registered_doc_ids:
                doc_units = [u for u in all_units if u.doc_id == doc_id]
                if doc_units:
                    write_clause_snapshot(doc_units, doc_id, "v1", args.company_id, _r2_mod, ctx, force=args.rebuild)

            # Neon writes — commit all pipeline outputs in one session
            from app.db import AsyncSessionLocal
            from app.company_ingest.store.neon import commit_run
            async with AsyncSessionLocal() as _neon_session:
                await commit_run(
                    session=_neon_session,
                    ctx=ctx,
                    sources=sources,
                    register_entries=register_entries,
                    units=all_units,
                    links=links,
                    scope_rows=scope_rows,
                    terms=terms,
                    term_usages=term_usages_list,
                    col_roles_map=col_roles_map,
                    dataset_profiles=dataset_profiles,
                    proposals=proposals,
                    report_r2_key=None,
                )
                await _neon_session.commit()

        unit_counts = {
            doc_id: len([u for u in all_units if u.doc_id == doc_id])
            for doc_id in registered_doc_ids
        }
        report = build_run_report(ctx, outcomes, registered_doc_ids, unit_counts)

        # Print summary
        all_passed = all(o.passed for o in outcomes)
        passed_count = sum(1 for o in outcomes if o.passed)
        logger.info(
            "Run complete. Checks: %d/%d passed.",
            passed_count,
            len(outcomes),
        )
        for o in outcomes:
            status = "PASS" if o.passed else "FAIL"
            logger.info("  Check %d: %s — %s", o.check_number, status, o.metric)

        return 0 if all_passed else 1

    except Exception as e:  # noqa: BLE001
        logger.error("Ingest failed: %s", e, exc_info=True)
        ctx.issue(
            severity="error",
            stage="cli",
            code="unexpected_error",
            message=str(e),
        )
        return 1


if __name__ == "__main__":
    main()
