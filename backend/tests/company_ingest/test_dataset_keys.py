"""Tests for Task 7.1.2 — Foreign-key and clause-reference detection."""
from __future__ import annotations

import pytest

from app.company_ingest.datasets.keys import detect_keys
from app.company_ingest.datasets.profile import ColumnProfile, DatasetProfile
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _col(
    name: str,
    dtype: str = "text",
    null_rate: float = 0.0,
    distinct_count: int = 5,
    top_values: list[dict] | None = None,
) -> ColumnProfile:
    return ColumnProfile(
        column_name=name,
        dtype=dtype,
        null_rate=null_rate,
        distinct_count=distinct_count,
        min_value=None,
        max_value=None,
        top_values=top_values,
    )


def _make_top(values: list[str]) -> list[dict]:
    return [{"value": v, "count": 1} for v in values]


def _dataset(
    name: str,
    columns: list[ColumnProfile],
    primary_key: str | None = None,
    doc_id: str | None = "DOC-001",
) -> DatasetProfile:
    return DatasetProfile(
        name=name,
        doc_id=doc_id,
        row_count=len(columns),
        file_sha256="abc123",
        r2_parquet_key=f"rpl/{name}.parquet",
        r2_source_key=f"rpl/{name}.csv",
        primary_key=primary_key,
        columns=columns,
    )


def _ctx() -> RunContext:
    return RunContext(company_id="rpl")


# ---------------------------------------------------------------------------
# Test 1: FK detection — column matches target PK and top_values confirm
# ---------------------------------------------------------------------------


def test_fk_detected_when_column_matches_target_pk():
    """circuit_id in dataset A with matching top_values → foreign_key to B.circuit_id"""
    circuit_values = _make_top(["C001", "C002", "C003", "C004", "C005"])

    col_circuit_id = _col("circuit_id", dtype="integer", top_values=circuit_values, distinct_count=5)
    col_event_id = _col("event_id", dtype="integer", top_values=_make_top(["E1", "E2"]), distinct_count=2)

    dataset_a = _dataset("outage_events", [col_circuit_id, col_event_id], primary_key="event_id")

    # Dataset B has circuit_id as its primary key
    pk_col_b = _col("circuit_id", dtype="integer", top_values=circuit_values, distinct_count=5)
    other_col = _col("region", dtype="text", top_values=_make_top(["North"]), distinct_count=1)
    dataset_b = _dataset("circuits_master", [pk_col_b, other_col], primary_key="circuit_id")

    ctx = _ctx()
    detect_keys([dataset_a, dataset_b], {}, ctx)

    assert col_circuit_id.semantic_role == "foreign_key"
    assert col_circuit_id.fk_target == "circuits_master.circuit_id"
    assert ctx.stats.get("fk_detected", 0) == 1


# ---------------------------------------------------------------------------
# Test 2: FK NOT detected when top_values don't match (< 90%)
# ---------------------------------------------------------------------------


def test_fk_not_detected_when_top_values_mismatch():
    """column ends in _id but only 50% of values match target PK → not detected."""
    col_circuit_id = _col(
        "circuit_id",
        dtype="integer",
        top_values=_make_top(["C001", "C002", "X999", "X888", "X777"]),
        distinct_count=5,
    )
    col_event_id = _col("event_id", dtype="integer", top_values=_make_top(["E1"]), distinct_count=1)
    dataset_a = _dataset("outage_events", [col_circuit_id, col_event_id], primary_key="event_id")

    # Dataset B has only C001 and C002 in its PK top_values
    pk_col_b = _col("circuit_id", dtype="integer", top_values=_make_top(["C001", "C002"]), distinct_count=2)
    dataset_b = _dataset("circuits_master", [pk_col_b], primary_key="circuit_id")

    ctx = _ctx()
    detect_keys([dataset_a, dataset_b], {}, ctx)

    assert col_circuit_id.semantic_role is None
    assert ctx.stats.get("fk_detected", 0) == 0


# ---------------------------------------------------------------------------
# Test 3: FK skipped when column IS the dataset's own primary key
# ---------------------------------------------------------------------------


def test_fk_skipped_for_own_primary_key():
    """The column that IS the PK should not be marked as a FK to itself."""
    # dataset_a.circuit_id is the PK
    pk_col = _col("circuit_id", dtype="integer", top_values=_make_top(["C1", "C2"]), distinct_count=2)
    dataset_a = _dataset("circuits_master", [pk_col], primary_key="circuit_id")

    # dataset_b also has circuit_id as PK
    pk_col_b = _col("circuit_id", dtype="integer", top_values=_make_top(["C1", "C2"]), distinct_count=2)
    dataset_b = _dataset("circuits_backup", [pk_col_b], primary_key="circuit_id")

    ctx = _ctx()
    detect_keys([dataset_a, dataset_b], {}, ctx)

    # The PK column of dataset_a should not be marked as FK
    assert pk_col.semantic_role is None
    assert ctx.stats.get("fk_detected", 0) == 0


# ---------------------------------------------------------------------------
# Test 4: FK skipped if column name doesn't end in _id or _serial
# ---------------------------------------------------------------------------


def test_fk_skipped_for_non_id_columns():
    """Columns like 'region' or 'status' should never be FK candidates."""
    col_region = _col("region", dtype="text", top_values=_make_top(["North", "South"]), distinct_count=2)
    col_pk = _col("event_id", dtype="integer", top_values=_make_top(["E1"]), distinct_count=1)
    dataset_a = _dataset("outage_events", [col_region, col_pk], primary_key="event_id")

    pk_col_b = _col("circuit_id", dtype="integer", top_values=_make_top(["C1"]), distinct_count=1)
    dataset_b = _dataset("circuits_master", [pk_col_b], primary_key="circuit_id")

    ctx = _ctx()
    detect_keys([dataset_a, dataset_b], {}, ctx)

    assert col_region.semantic_role is None
    assert ctx.stats.get("fk_detected", 0) == 0


# ---------------------------------------------------------------------------
# Test 5: FK skipped if top_values is None (too many distinct values)
# ---------------------------------------------------------------------------


def test_fk_skipped_when_top_values_is_none():
    """Column with top_values=None (> 50 distinct) should be skipped for FK detection."""
    col_circuit_id = _col("circuit_id", dtype="integer", top_values=None, distinct_count=1000)
    col_pk = _col("event_id", dtype="integer", top_values=_make_top(["E1"]), distinct_count=1)
    dataset_a = _dataset("outage_events", [col_circuit_id, col_pk], primary_key="event_id")

    pk_col_b = _col("circuit_id", dtype="integer", top_values=_make_top(["C1"]), distinct_count=1)
    dataset_b = _dataset("circuits_master", [pk_col_b], primary_key="circuit_id")

    ctx = _ctx()
    detect_keys([dataset_a, dataset_b], {}, ctx)

    assert col_circuit_id.semantic_role is None
    assert ctx.stats.get("fk_detected", 0) == 0


# ---------------------------------------------------------------------------
# Test 6: Clause-ref detection — text column with matching clause IDs
# ---------------------------------------------------------------------------


def test_clause_ref_detected():
    """Column with values like ['7.2.1', '7.2.2', '7.3'] detected as clause_ref."""
    clause_values = _make_top(["7.2.1", "7.2.2", "7.3", "8.1", "8.2"])
    col_clause = _col(
        "clause_ref_id",
        dtype="text",
        top_values=clause_values,
        distinct_count=5,
    )
    col_pk = _col("record_id", dtype="integer", top_values=_make_top(["1"]), distinct_count=1)
    dataset = _dataset(
        "spill_events",
        [col_clause, col_pk],
        primary_key="record_id",
        doc_id="DOC-001",
    )

    clause_ids_by_doc = {
        "DOC-001": {"7.2.1", "7.2.2", "7.3", "8.1", "8.2", "9.1"},
    }

    ctx = _ctx()
    detect_keys([dataset], clause_ids_by_doc, ctx)

    assert col_clause.semantic_role == "clause_ref"
    assert col_clause.fk_target == "clause:DOC-001:clause_ref_id"
    assert ctx.stats.get("clause_ref_detected", 0) == 1


# ---------------------------------------------------------------------------
# Test 7: Clause-ref NOT detected if < 90% match clause pattern
# ---------------------------------------------------------------------------


def test_clause_ref_not_detected_below_threshold():
    """Column with only 50% clause-like values should not be marked as clause_ref."""
    mixed_values = _make_top(["7.2.1", "7.2.2", "foo", "bar", "baz"])
    col_mixed = _col(
        "clause_or_text",
        dtype="text",
        top_values=mixed_values,
        distinct_count=5,
    )
    col_pk = _col("record_id", dtype="integer", top_values=_make_top(["1"]), distinct_count=1)
    dataset = _dataset(
        "some_dataset",
        [col_mixed, col_pk],
        primary_key="record_id",
        doc_id="DOC-001",
    )

    clause_ids_by_doc = {"DOC-001": {"7.2.1", "7.2.2"}}

    ctx = _ctx()
    detect_keys([dataset], clause_ids_by_doc, ctx)

    assert col_mixed.semantic_role is None
    assert ctx.stats.get("clause_ref_detected", 0) == 0


# ---------------------------------------------------------------------------
# Test 8: Clause-ref NOT detected for non-text dtype
# ---------------------------------------------------------------------------


def test_clause_ref_not_detected_for_non_text():
    """Integer column with values resembling clause IDs should not be detected."""
    col_numeric = _col(
        "clause_num",
        dtype="integer",
        top_values=_make_top(["7", "8", "9"]),
        distinct_count=3,
    )
    col_pk = _col("record_id", dtype="integer", top_values=_make_top(["1"]), distinct_count=1)
    dataset = _dataset(
        "some_dataset",
        [col_numeric, col_pk],
        primary_key="record_id",
        doc_id="DOC-001",
    )

    clause_ids_by_doc = {"DOC-001": {"7", "8", "9"}}

    ctx = _ctx()
    detect_keys([dataset], clause_ids_by_doc, ctx)

    assert col_numeric.semantic_role is None
    assert ctx.stats.get("clause_ref_detected", 0) == 0


# ---------------------------------------------------------------------------
# Test 9: FK integrity warning logged when top_values have non-matching entries
# ---------------------------------------------------------------------------


def test_fk_integrity_warning_logged():
    """FK detected but some values missing from target → warning issued."""
    # col has 5 values; only 4 appear in target PK
    col_circuit_id = _col(
        "circuit_id",
        dtype="integer",
        top_values=_make_top(["C001", "C002", "C003", "C004", "CXXX"]),
        distinct_count=5,
    )
    col_pk = _col("event_id", dtype="integer", top_values=_make_top(["E1"]), distinct_count=1)
    dataset_a = _dataset("outage_events", [col_circuit_id, col_pk], primary_key="event_id")

    # Target PK has C001..C004 but NOT CXXX — 4/5 = 80% which is < 90%
    # We need 90%+ to detect the FK at all. Adjust: only 1 value missing out of 10
    col_circuit_id2 = _col(
        "circuit_id",
        dtype="integer",
        top_values=_make_top(["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "CXXX"]),
        distinct_count=10,
    )
    col_pk2 = _col("event_id", dtype="integer", top_values=_make_top(["E1"]), distinct_count=1)
    dataset_a2 = _dataset("outage_events2", [col_circuit_id2, col_pk2], primary_key="event_id")

    # Target has all except CXXX → 9/10 = 90% match (exactly at threshold)
    pk_col_b = _col(
        "circuit_id",
        dtype="integer",
        top_values=_make_top(["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09"]),
        distinct_count=9,
    )
    dataset_b = _dataset("circuits_master", [pk_col_b], primary_key="circuit_id")

    ctx = _ctx()
    detect_keys([dataset_a2, dataset_b], {}, ctx)

    # FK should be detected (9/10 = 90% match)
    assert col_circuit_id2.semantic_role == "foreign_key"

    # Integrity warning should be issued for the 1 missing value
    integrity_warnings = [
        i for i in ctx.issues
        if i.code == "fk_integrity_violation"
    ]
    assert len(integrity_warnings) == 1
    assert integrity_warnings[0].details["count"] == 1


# ---------------------------------------------------------------------------
# Test 10: ctx.count() incremented for both fk_detected and clause_ref_detected
# ---------------------------------------------------------------------------


def test_ctx_counts_incremented():
    """Both fk_detected and clause_ref_detected counters incremented correctly."""
    # FK setup
    circuit_values = _make_top(["C1", "C2", "C3"])
    col_circuit_id = _col("circuit_id", dtype="integer", top_values=circuit_values, distinct_count=3)
    col_event_id = _col("event_id", dtype="integer", top_values=_make_top(["E1"]), distinct_count=1)
    dataset_a = _dataset("outage_events", [col_circuit_id, col_event_id], primary_key="event_id")

    pk_col_b = _col("circuit_id", dtype="integer", top_values=circuit_values, distinct_count=3)
    dataset_b = _dataset("circuits_master", [pk_col_b], primary_key="circuit_id")

    # Clause-ref setup
    clause_values = _make_top(["7.1", "7.2", "8.1"])
    col_clause = _col("clause_ref_id", dtype="text", top_values=clause_values, distinct_count=3)
    col_pk_c = _col("rec_id", dtype="integer", top_values=_make_top(["1"]), distinct_count=1)
    dataset_c = _dataset("spill_events", [col_clause, col_pk_c], primary_key="rec_id", doc_id="DOC-002")

    clause_ids_by_doc = {"DOC-002": {"7.1", "7.2", "8.1", "8.2"}}

    ctx = _ctx()
    detect_keys([dataset_a, dataset_b, dataset_c], clause_ids_by_doc, ctx)

    assert ctx.stats.get("fk_detected", 0) >= 1
    assert ctx.stats.get("clause_ref_detected", 0) >= 1


# ---------------------------------------------------------------------------
# Corpus tests (skip in non-corpus runs)
# ---------------------------------------------------------------------------


@pytest.mark.corpus
def test_corpus_fk_circuit_id():
    """circuit_id in outage_events and meter_population → FK to circuits_master.circuit_id."""
    pytest.importorskip("pyarrow")
    import hashlib
    from pathlib import Path
    from app.company_ingest.collect.collector import SourceFile
    from app.company_ingest.constants import Profile
    from app.company_ingest.datasets.profile import profile_dataset

    corpus_root = Path(__file__).parent.parent.parent / "corpus"
    if not corpus_root.exists():
        pytest.skip("Corpus not available")

    # Look for relevant CSV files
    outage_path = next(corpus_root.rglob("outage_events.csv"), None)
    meter_path = next(corpus_root.rglob("meter_population.csv"), None)
    circuits_path = next(corpus_root.rglob("circuits_master.csv"), None)

    if not (outage_path and circuits_path):
        pytest.skip("Required corpus datasets not found")

    def _make_source(path: Path) -> SourceFile:
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        # Infer doc_id from path structure
        parts = path.parts
        doc_id = None
        if "docs" in parts:
            idx = parts.index("docs")
            if idx + 1 < len(parts):
                doc_id = parts[idx + 1]
        rel = str(path.relative_to(corpus_root.parent))
        return SourceFile(
            rel_path=rel,
            abs_path=path,
            sha256=sha,
            profile=Profile.P3_DATASET,
            doc_id=doc_id,
        )

    ctx = RunContext(company_id="rpl")
    profiles = []
    for path in filter(None, [outage_path, meter_path, circuits_path]):
        src = _make_source(path)
        p = profile_dataset(src, "rpl", str(ctx.run_id), ctx, upload_r2=False)
        profiles.append(p)

    detect_keys(profiles, {}, ctx)

    fk_cols = [
        col
        for p in profiles
        for col in p.columns
        if col.semantic_role == "foreign_key" and col.fk_target and "circuit_id" in col.fk_target
    ]
    assert len(fk_cols) > 0, "Expected at least one circuit_id FK detected"


@pytest.mark.corpus
def test_corpus_clause_ref_spill_events():
    """A clause_ref column found in the spill_events dataset (T20)."""
    pytest.importorskip("pyarrow")
    import hashlib
    from pathlib import Path
    from app.company_ingest.collect.collector import SourceFile
    from app.company_ingest.constants import Profile
    from app.company_ingest.datasets.profile import profile_dataset

    corpus_root = Path(__file__).parent.parent.parent / "corpus"
    if not corpus_root.exists():
        pytest.skip("Corpus not available")

    spill_path = next(corpus_root.rglob("spill_events.csv"), None)
    if not spill_path:
        pytest.skip("spill_events.csv not found in corpus")

    data = spill_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    parts = spill_path.parts
    doc_id = None
    if "docs" in parts:
        idx = parts.index("docs")
        if idx + 1 < len(parts):
            doc_id = parts[idx + 1]

    rel = str(spill_path.relative_to(corpus_root.parent))
    src = SourceFile(
        rel_path=rel,
        abs_path=spill_path,
        sha256=sha,
        profile=Profile.P3_DATASET,
        doc_id=doc_id,
    )

    ctx = RunContext(company_id="rpl")
    dataset = profile_dataset(src, "rpl", str(ctx.run_id), ctx, upload_r2=False)

    # Build clause_ids_by_doc from actual doc if possible, else use empty
    clause_ids_by_doc: dict[str, set[str]] = {}
    if doc_id:
        # Look for a registry/known clause IDs
        clause_ids_by_doc[doc_id] = set()

    detect_keys([dataset], clause_ids_by_doc, ctx)

    clause_cols = [
        col for col in dataset.columns if col.semantic_role == "clause_ref"
    ]
    assert len(clause_cols) > 0, "Expected at least one clause_ref column in spill_events"
