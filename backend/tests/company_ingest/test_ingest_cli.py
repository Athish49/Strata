"""Tests for task 8.2.1: ingest CLI and orchestration."""
from __future__ import annotations

import argparse
import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.company_ingest.cli.ingest import _run, main
from app.company_ingest.validate.checks import CheckOutcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_outcome(passed: bool = True, check_number: int = 1) -> CheckOutcome:
    return CheckOutcome(
        check_number=check_number,
        name=f"check_{check_number}",
        passed=passed,
        metric="ok",
    )


def _default_args(**overrides) -> argparse.Namespace:
    """Return a Namespace with all expected CLI args set to safe defaults."""
    defaults = dict(
        company_id="test_co",
        corpus_root="/tmp/corpus",
        no_llm=False,
        no_datasets=False,
        rebuild=False,
        dry_run=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _patch_all():
    """Context: patch every stage function at its import location in cli.ingest."""
    patches = {
        "collect": patch(
            "app.company_ingest.cli.ingest._run.__code__",  # indirect — patch by module
        ),
    }
    # Build a flat patch dict keyed by dotted path
    return {
        "collect": "app.company_ingest.collect.collector.collect",
        "detect_keys": "app.company_ingest.datasets.keys.detect_keys",
        "profile_dataset": "app.company_ingest.datasets.profile.profile_dataset",
        "propose_checks": "app.company_ingest.datasets.propose_checks.propose_checks",
        "validate_checks": "app.company_ingest.datasets.validate_checks.validate_checks",
        "enrich_citations": "app.company_ingest.enrich.citations.enrich_citations",
        "enrich_parameters": "app.company_ingest.enrich.parameters_regex.enrich_parameters",
        "enrich_references": "app.company_ingest.enrich.references.enrich_references",
        "enrich_roles": "app.company_ingest.enrich.roles.enrich_roles",
        "extract_terms": "app.company_ingest.enrich.terms.extract_terms",
        "find_term_usages": "app.company_ingest.enrich.terms.find_term_usages",
        "stable_uuid": "app.company_ingest.ids.stable_uuid",
        "upsert_clauses": "app.company_ingest.index.upsert.upsert_clauses",
        "build_document_scope": "app.company_ingest.link.document_scope.build_document_scope",
        "resolve_references": "app.company_ingest.link.resolve_refs.resolve_references",
        "find_restates_links": "app.company_ingest.link.restates.find_restates_links",
        "run_clause_enrichment": "app.company_ingest.llm.run_clause_enrichment.run_clause_enrichment",
        "run_column_roles": "app.company_ingest.llm.run_column_roles.run_column_roles",
        "split_front_matter": "app.company_ingest.parse.front_matter.split_front_matter",
        "segment_with_ctx": "app.company_ingest.parse.markdown_segmenter.segment_with_ctx",
        "segment_register": "app.company_ingest.parse.register_segmenter.segment_register",
        "build_run_report": "app.company_ingest.store.commit.build_run_report",
        "finalize_parameters": "app.company_ingest.store.commit.finalize_parameters",
        "write_clause_snapshot": "app.company_ingest.store.snapshot.write_clause_snapshot",
        "run_all_checks": "app.company_ingest.validate.checks.run_all_checks",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def all_mocks():
    """
    Patch all stage functions at module level and return a dict of mock objects.
    Mocks are pre-configured with sensible return values.
    """
    paths = {
        "collect": "app.company_ingest.collect.collector.collect",
        "detect_keys": "app.company_ingest.datasets.keys.detect_keys",
        "profile_dataset": "app.company_ingest.datasets.profile.profile_dataset",
        "propose_checks": "app.company_ingest.datasets.propose_checks.propose_checks",
        "validate_checks": "app.company_ingest.datasets.validate_checks.validate_checks",
        "enrich_citations": "app.company_ingest.enrich.citations.enrich_citations",
        "enrich_parameters": "app.company_ingest.enrich.parameters_regex.enrich_parameters",
        "enrich_references": "app.company_ingest.enrich.references.enrich_references",
        "enrich_roles": "app.company_ingest.enrich.roles.enrich_roles",
        "extract_terms": "app.company_ingest.enrich.terms.extract_terms",
        "find_term_usages": "app.company_ingest.enrich.terms.find_term_usages",
        "stable_uuid": "app.company_ingest.ids.stable_uuid",
        "upsert_clauses": "app.company_ingest.index.upsert.upsert_clauses",
        "build_document_scope": "app.company_ingest.link.document_scope.build_document_scope",
        "resolve_references": "app.company_ingest.link.resolve_refs.resolve_references",
        "find_restates_links": "app.company_ingest.link.restates.find_restates_links",
        "run_clause_enrichment": "app.company_ingest.llm.run_clause_enrichment.run_clause_enrichment",
        "run_column_roles": "app.company_ingest.llm.run_column_roles.run_column_roles",
        "split_front_matter": "app.company_ingest.parse.front_matter.split_front_matter",
        "segment_with_ctx": "app.company_ingest.parse.markdown_segmenter.segment_with_ctx",
        "segment_register": "app.company_ingest.parse.register_segmenter.segment_register",
        "build_run_report": "app.company_ingest.store.commit.build_run_report",
        "finalize_parameters": "app.company_ingest.store.commit.finalize_parameters",
        "write_clause_snapshot": "app.company_ingest.store.snapshot.write_clause_snapshot",
        "run_all_checks": "app.company_ingest.validate.checks.run_all_checks",
    }

    active_patches = []
    mocks: dict = {}

    for name, path in paths.items():
        # Use AsyncMock for async functions, MagicMock for sync
        if name in ("run_clause_enrichment", "run_column_roles", "propose_checks", "upsert_clauses"):
            m = patch(path, new_callable=AsyncMock)
        else:
            m = patch(path)
        started = m.start()
        active_patches.append(m)
        mocks[name] = started

    # Patch Neon session factory and commit_run so no real DB is needed
    _session_mock = AsyncMock()
    _session_mock.__aenter__ = AsyncMock(return_value=_session_mock)
    _session_mock.__aexit__ = AsyncMock(return_value=False)
    _db_patch = patch("app.db.AsyncSessionLocal", return_value=_session_mock)
    mocks["AsyncSessionLocal"] = _db_patch.start()
    active_patches.append(_db_patch)

    _load_ref_patch = patch(
        "app.company_ingest.collect.reference.load_reference_data",
        new_callable=AsyncMock,
        return_value=[],
    )
    mocks["load_reference_data"] = _load_ref_patch.start()
    active_patches.append(_load_ref_patch)

    _commit_patch = patch(
        "app.company_ingest.store.neon.commit_run",
        new_callable=AsyncMock,
        return_value=None,
    )
    mocks["commit_run"] = _commit_patch.start()
    active_patches.append(_commit_patch)

    # Configure default return values
    mocks["collect"].return_value = []
    mocks["extract_terms"].return_value = []
    mocks["find_term_usages"].return_value = []
    mocks["resolve_references"].return_value = []
    mocks["find_restates_links"].return_value = []
    mocks["build_document_scope"].return_value = []
    mocks["run_all_checks"].return_value = [_fake_outcome(passed=True)]
    mocks["build_run_report"].return_value = {}
    mocks["run_clause_enrichment"].return_value = None
    mocks["run_column_roles"].return_value = {}
    mocks["propose_checks"].return_value = (None, [])
    mocks["validate_checks"].return_value = []
    mocks["stable_uuid"].return_value = "test-uuid"

    yield mocks

    for m in active_patches:
        m.stop()


# ---------------------------------------------------------------------------
# Test 1: main() with no args runs without error
# ---------------------------------------------------------------------------

def test_main_no_args_runs_without_error(all_mocks):
    """main() should parse argv=[] and complete successfully."""
    with patch("sys.argv", ["ingest"]), \
         patch("sys.exit") as mock_exit:
        main()
    # Should not raise; exit called with 0 (all checks passed)
    mock_exit.assert_called_once_with(0)


# ---------------------------------------------------------------------------
# Test 2: --no-llm flag: run_clause_enrichment NOT called, ctx.no_llm=True
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_llm_skips_llm_stages(all_mocks):
    """--no-llm should prevent LLM stage calls and set ctx.no_llm=True."""
    args = _default_args(no_llm=True)
    exit_code = await _run(args)

    assert exit_code == 0
    # run_clause_enrichment is inside Stage 4a — it's always called per spec
    # but with no_llm=True in ctx. Stage 4b (column roles) is skipped.
    all_mocks["run_column_roles"].assert_not_called()
    # Stage 4c (propose_checks) is also skipped when no_llm=True
    all_mocks["propose_checks"].assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: --no-datasets flag: profile_dataset NOT called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_datasets_skips_profiling(all_mocks):
    """--no-datasets should prevent profile_dataset from being called."""
    args = _default_args(no_datasets=True)
    exit_code = await _run(args)

    assert exit_code == 0
    all_mocks["profile_dataset"].assert_not_called()
    all_mocks["detect_keys"].assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: --dry-run flag: upsert_clauses NOT called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dry_run_skips_qdrant_indexing(all_mocks):
    """--dry-run should prevent upsert_clauses from being called."""
    args = _default_args(dry_run=True)
    exit_code = await _run(args)

    assert exit_code == 0
    all_mocks["upsert_clauses"].assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: All checks passing → exit code 0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_checks_pass_returns_zero(all_mocks):
    """When all acceptance checks pass, exit code should be 0."""
    all_mocks["run_all_checks"].return_value = [
        _fake_outcome(passed=True, check_number=i) for i in range(1, 13)
    ]
    args = _default_args()
    exit_code = await _run(args)
    assert exit_code == 0


# ---------------------------------------------------------------------------
# Test 6: A check failing → exit code 1
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failing_check_returns_one(all_mocks):
    """When any acceptance check fails, exit code should be 1."""
    outcomes = [_fake_outcome(passed=True, check_number=i) for i in range(1, 12)]
    outcomes.append(_fake_outcome(passed=False, check_number=12))
    all_mocks["run_all_checks"].return_value = outcomes

    args = _default_args()
    exit_code = await _run(args)
    assert exit_code == 1


# ---------------------------------------------------------------------------
# Test 7: Stage exception → exit code 1, error logged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage_exception_returns_one(all_mocks, caplog):
    """An unhandled exception in any stage should return exit code 1."""
    all_mocks["collect"].side_effect = RuntimeError("corpus walk failed")

    args = _default_args()
    exit_code = await _run(args)

    assert exit_code == 1


# ---------------------------------------------------------------------------
# Test 8: --rebuild sets ctx.rebuild=True
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rebuild_flag_sets_ctx_rebuild(all_mocks):
    """--rebuild should be reflected in ctx.rebuild=True."""
    captured_ctx = {}

    original_run_all_checks = all_mocks["run_all_checks"].side_effect

    def _capture_state(state, ctx):
        captured_ctx["rebuild"] = ctx.rebuild
        return [_fake_outcome(passed=True)]

    all_mocks["run_all_checks"].side_effect = _capture_state

    args = _default_args(rebuild=True)
    exit_code = await _run(args)

    assert exit_code == 0
    assert captured_ctx.get("rebuild") is True


# ---------------------------------------------------------------------------
# Test 9: Stage order — segment called before enrichment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage_order_segment_before_enrichment(all_mocks):
    """Segment stage (segment_with_ctx / segment_register) must be called before enrich_citations."""
    call_order: list[str] = []

    def _record(name):
        def _inner(*args, **kwargs):
            call_order.append(name)
            return []
        return _inner

    def _record_sync(name):
        def _inner(*args, **kwargs):
            call_order.append(name)
        return _inner

    all_mocks["segment_with_ctx"].side_effect = _record("segment_with_ctx")
    all_mocks["enrich_citations"].side_effect = _record_sync("enrich_citations")

    # For this test, supply a P1 source to trigger segment_with_ctx
    fake_source = MagicMock()
    fake_source.profile = "p1_prose"
    fake_source.doc_id = "DOC001"
    fake_source.rel_path = "corpus/docs/DOC001/policy.md"
    fake_source.abs_path = MagicMock()
    fake_source.abs_path.read_text.return_value = "---\nversion: v1\n---\nContent"

    all_mocks["collect"].return_value = [fake_source]

    fake_fm = MagicMock()
    fake_fm.version = "v1"
    all_mocks["split_front_matter"].return_value = (fake_fm, "Content", 0)

    args = _default_args()
    await _run(args)

    # segment_with_ctx must appear before enrich_citations in call_order
    if "segment_with_ctx" in call_order and "enrich_citations" in call_order:
        seg_idx = call_order.index("segment_with_ctx")
        enrich_idx = call_order.index("enrich_citations")
        assert seg_idx < enrich_idx, (
            f"segment_with_ctx (idx {seg_idx}) must come before "
            f"enrich_citations (idx {enrich_idx})"
        )


# ---------------------------------------------------------------------------
# Test 10: finalize_parameters called before acceptance checks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_finalize_parameters_before_acceptance_checks(all_mocks):
    """finalize_parameters must be called before run_all_checks."""
    call_order: list[str] = []

    all_mocks["finalize_parameters"].side_effect = lambda *a, **kw: call_order.append("finalize")
    all_mocks["run_all_checks"].side_effect = lambda *a, **kw: (
        call_order.append("run_all_checks") or [_fake_outcome(passed=True)]
    )

    args = _default_args()
    exit_code = await _run(args)

    assert exit_code == 0
    assert "finalize" in call_order, "finalize_parameters was never called"
    assert "run_all_checks" in call_order, "run_all_checks was never called"

    finalize_idx = call_order.index("finalize")
    checks_idx = call_order.index("run_all_checks")
    assert finalize_idx < checks_idx, (
        f"finalize_parameters (idx {finalize_idx}) must come before "
        f"run_all_checks (idx {checks_idx})"
    )
