"""Task 9.1.2 — End-to-end corpus test.

Runs the full CLI in offline mode (--no-llm --no-datasets --dry-run) against the
real on-disk corpus and checks in-memory outputs.  No live Neon, Qdrant, or R2
connections are required.

All tests are marked @pytest.mark.corpus and are excluded from the normal suite
by the default ``-k "not corpus"`` filter.  To run them:
    pytest tests/company_ingest/test_e2e_corpus.py --run-it corpus
    # or simply:
    pytest tests/company_ingest/test_e2e_corpus.py -k corpus
"""
from __future__ import annotations

import argparse
from collections import Counter
from unittest.mock import AsyncMock, patch

import pytest

from app.company_ingest.cli.ingest import _run
from app.company_ingest.validate.checks import CheckOutcome, RunState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(**kwargs):
    """Return a Namespace with default offline flags."""
    defaults = dict(
        company_id="rpl",
        corpus_root=None,  # uses settings.CORPUS_ROOT
        no_llm=True,
        no_datasets=True,
        rebuild=False,
        dry_run=True,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# Fixture: run the pipeline once and capture RunState
# ---------------------------------------------------------------------------


@pytest.fixture
async def pipeline_state():
    """Run the pipeline in --no-llm --no-datasets --dry-run mode.

    Patches ``run_all_checks`` at its definition site so that we can capture the
    RunState that is built by the CLI before checks execute.  All writes (R2,
    Qdrant, Neon) are skipped because ``dry_run=True``.
    """
    captured: dict = {}

    from app.company_ingest.validate import checks as checks_mod

    original_run_all_checks = checks_mod.run_all_checks

    def capturing_run_all_checks(state: RunState, ctx):
        captured["state"] = state
        captured["ctx"] = ctx
        return original_run_all_checks(state, ctx)

    with (
        patch(
            "app.company_ingest.validate.checks.run_all_checks",
            side_effect=capturing_run_all_checks,
        ),
        patch(
            "app.company_ingest.store.snapshot.write_clause_snapshot",
            return_value="r2/key",
        ),
    ):
        exit_code = await _run(_make_args())

    return exit_code, captured.get("state"), captured.get("ctx")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.corpus
@pytest.mark.asyncio
async def test_e2e_exits_zero(pipeline_state):
    """Pipeline should exit 0 when all acceptance checks pass."""
    exit_code, state, ctx = pipeline_state
    assert exit_code == 0, f"Pipeline exited with code {exit_code} (expected 0)"


@pytest.mark.corpus
@pytest.mark.asyncio
async def test_e2e_clause_count(pipeline_state):
    """All 12 P1 documents should produce at least 10 clauses each."""
    _, state, _ = pipeline_state
    assert len(state.units) > 0, "No units produced by the pipeline"

    counts = Counter(u.doc_id for u in state.units)
    assert len(counts) == 12, (
        f"Expected 12 docs, got {len(counts)}: {sorted(counts.keys())}"
    )
    for doc_id, count in counts.items():
        assert count >= 10, f"{doc_id} has only {count} clauses (expected ≥ 10)"


@pytest.mark.corpus
@pytest.mark.asyncio
async def test_e2e_no_duplicate_clause_ids(pipeline_state):
    """Every clause ID must be unique across all units."""
    _, state, _ = pipeline_state
    ids = [u.clause_id for u in state.units]
    dup_counts = {cid: n for cid, n in Counter(ids).items() if n > 1}
    assert len(dup_counts) == 0, (
        f"Duplicate clause IDs found: {list(dup_counts.keys())[:10]}"
    )


@pytest.mark.corpus
@pytest.mark.asyncio
async def test_e2e_all_roles_assigned(pipeline_state):
    """With --no-llm, heuristic enrichment should assign a role to every unit."""
    _, state, _ = pipeline_state
    undecided = [u for u in state.units if u.role is None]
    assert len(undecided) == 0, (
        f"{len(undecided)} units have no role assigned; "
        f"first 5: {[u.clause_id for u in undecided[:5]]}"
    )


@pytest.mark.corpus
@pytest.mark.asyncio
async def test_e2e_links_resolved(pipeline_state):
    """Reference resolution rate should be at least 60%."""
    _, state, _ = pipeline_state
    resolved = state.stats.get("links_resolved", 0)
    unresolved = state.stats.get("links_unresolved", 0)
    total = resolved + unresolved
    if total > 0:
        rate = resolved / total
        assert rate >= 0.6, (
            f"Link resolution rate {rate:.1%} is below 60% "
            f"({resolved}/{total} resolved)"
        )


@pytest.mark.corpus
@pytest.mark.asyncio
async def test_e2e_scope_rows_present(pipeline_state):
    """Document scope rollup must produce at least one scope row."""
    _, state, _ = pipeline_state
    assert len(state.scope_rows) > 0, "No document scope rows were generated"


@pytest.mark.corpus
@pytest.mark.asyncio
async def test_e2e_p2_register_rows(pipeline_state):
    """P2 register documents should produce ≥ 150 register_row units in total.

    Expected contributions:
      - compliance_register  ~70 rows
      - calendar_events      ~48 rows
      - retention_schedule   ~86 rows
    """
    _, state, _ = pipeline_state
    register_rows = [u for u in state.units if u.unit_kind == "register_row"]
    assert len(register_rows) >= 150, (
        f"Expected ≥ 150 register rows, got {len(register_rows)}"
    )
