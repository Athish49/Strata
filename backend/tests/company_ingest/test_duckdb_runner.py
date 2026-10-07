"""Tests for task 7.2.1 — DuckDB check runner."""
from __future__ import annotations

import pathlib

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.company_ingest.datasets.duckdb_runner import CheckResult, run_check


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_parquet(tmp_path: pathlib.Path, name: str, table: pa.Table) -> str:
    """Write a PyArrow Table to a Parquet file and return its path string."""
    path = tmp_path / name
    pq.write_table(table, path)
    return str(path)


def _make_test_table() -> pa.Table:
    """Create a small test table with an id and a value column."""
    return pa.table(
        {
            "id": pa.array([1, 2, 3, 4, 5, 6, 7], type=pa.int64()),
            "value": pa.array([10, 30, 55, 70, 90, 45, 80], type=pa.int64()),
            "label": pa.array(["a", "b", "c", "d", "e", "f", "g"]),
        }
    )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def parquet_path(tmp_path: pathlib.Path) -> str:
    return _write_parquet(tmp_path, "test_data.parquet", _make_test_table())


@pytest.fixture()
def datasets(parquet_path: str) -> dict[str, str]:
    return {"test_data": parquet_path}


# ---------------------------------------------------------------------------
# 1. Basic count — rows where value > 50
# ---------------------------------------------------------------------------

def test_basic_count(datasets):
    result = run_check(
        "SELECT * FROM test_data WHERE value > {threshold}",
        {"threshold": (50, "number")},
        datasets,
    )
    assert isinstance(result, CheckResult)
    # values > 50: 55, 70, 90, 80  → 4 rows
    assert result.violation_count == 4


# ---------------------------------------------------------------------------
# 2. violation_count is the correct count
# ---------------------------------------------------------------------------

def test_violation_count_correct(datasets):
    result = run_check(
        "SELECT * FROM test_data WHERE value > {threshold}",
        {"threshold": (50, "number")},
        datasets,
    )
    assert result.violation_count == 4


# ---------------------------------------------------------------------------
# 3. affected_count equals violation_count
# ---------------------------------------------------------------------------

def test_affected_count_equals_violation(datasets):
    result = run_check(
        "SELECT * FROM test_data WHERE value > {threshold}",
        {"threshold": (50, "number")},
        datasets,
    )
    assert result.affected_count == result.violation_count


# ---------------------------------------------------------------------------
# 4. sample_rows is a list of dicts with correct column names
# ---------------------------------------------------------------------------

def test_sample_rows_are_dicts_with_correct_columns(datasets):
    result = run_check(
        "SELECT * FROM test_data WHERE value > {threshold}",
        {"threshold": (50, "number")},
        datasets,
    )
    assert isinstance(result.sample_rows, list)
    assert len(result.sample_rows) > 0
    for row in result.sample_rows:
        assert isinstance(row, dict)
        assert set(row.keys()) == {"id", "value", "label"}


# ---------------------------------------------------------------------------
# 5. elapsed_seconds > 0
# ---------------------------------------------------------------------------

def test_elapsed_seconds_positive(datasets):
    result = run_check(
        "SELECT * FROM test_data WHERE value > {threshold}",
        {"threshold": (50, "number")},
        datasets,
    )
    assert result.elapsed_seconds > 0


# ---------------------------------------------------------------------------
# 6. Parameter type: number → numeric literal substituted
# ---------------------------------------------------------------------------

def test_param_number(datasets):
    result = run_check(
        "SELECT * FROM test_data WHERE value > {threshold}",
        {"threshold": (30, "number")},
        datasets,
    )
    # values > 30: 55, 70, 90, 80 → 4 rows (45 is not > 30 so also 45? no: 45>30 yes)
    # values: 10,30,55,70,90,45,80 → > 30: 55,70,90,45,80 → 5
    assert result.violation_count == 5
    assert result.error is None


# ---------------------------------------------------------------------------
# 7. Parameter type: string → properly quoted, no injection
# ---------------------------------------------------------------------------

def test_param_string_safe(datasets):
    # A value with a single-quote and attempted injection must not cause an error
    result = run_check(
        "SELECT * FROM test_data WHERE label = {lbl}",
        {"lbl": ("'; DROP TABLE", "string")},
        datasets,
    )
    # No rows match the injected string; what matters is no error/exception
    assert result.error is None
    assert result.violation_count == 0


# ---------------------------------------------------------------------------
# 8. Parameter type: bool → TRUE/FALSE
# ---------------------------------------------------------------------------

def test_param_bool(tmp_path):
    bool_table = pa.table({"flag": pa.array([True, False, True], type=pa.bool_())})
    path = _write_parquet(tmp_path, "bool_data.parquet", bool_table)
    result = run_check(
        "SELECT * FROM bool_data WHERE flag = {active}",
        {"active": (True, "bool")},
        {"bool_data": path},
    )
    assert result.violation_count == 2
    assert result.error is None


# ---------------------------------------------------------------------------
# 9. Parameter type: duration → INTERVAL '10 days'
# ---------------------------------------------------------------------------

def test_param_duration(tmp_path):
    import datetime as dt
    # Create a table with dates; filter rows older than INTERVAL '10 days' from now
    base = dt.date(2024, 1, 1)
    dates = [base + dt.timedelta(days=i) for i in range(5)]
    date_table = pa.table({"d": pa.array(dates, type=pa.date32())})
    path = _write_parquet(tmp_path, "date_data.parquet", date_table)
    # All dates are in 2024; comparing against today minus interval — all will be old
    result = run_check(
        "SELECT * FROM date_data WHERE d < (CURRENT_DATE - {age})",
        {"age": (10, "duration", "days")},
        {"date_data": path},
    )
    # All 5 dates are well before today minus 10 days
    assert result.violation_count == 5
    assert result.error is None


# ---------------------------------------------------------------------------
# 10. Security: SELECT ok
# ---------------------------------------------------------------------------

def test_security_select_ok(datasets):
    result = run_check(
        "SELECT COUNT(*) AS n FROM test_data",
        {},
        datasets,
    )
    assert result.error is None


# ---------------------------------------------------------------------------
# 11. Security: WITH...SELECT ok
# ---------------------------------------------------------------------------

def test_security_with_select_ok(datasets):
    result = run_check(
        "WITH cte AS (SELECT * FROM test_data) SELECT * FROM cte WHERE value > 50",
        {},
        datasets,
    )
    assert result.error is None
    assert result.violation_count == 4


# ---------------------------------------------------------------------------
# 12. Security: INSERT rejected
# ---------------------------------------------------------------------------

def test_security_insert_rejected(datasets):
    with pytest.raises(ValueError, match="Unsafe SQL"):
        run_check(
            "INSERT INTO test_data VALUES (99, 99, 'x')",
            {},
            datasets,
        )


# ---------------------------------------------------------------------------
# 13. Security: DROP rejected
# ---------------------------------------------------------------------------

def test_security_drop_rejected(datasets):
    with pytest.raises(ValueError, match="Unsafe SQL"):
        run_check(
            "DROP TABLE test_data",
            {},
            datasets,
        )


# ---------------------------------------------------------------------------
# 14. Security: COPY rejected
# ---------------------------------------------------------------------------

def test_security_copy_rejected(datasets):
    with pytest.raises(ValueError, match="Unsafe SQL"):
        run_check(
            "COPY test_data TO '/tmp/out.csv'",
            {},
            datasets,
        )


# ---------------------------------------------------------------------------
# 15. Security: two statements rejected
# ---------------------------------------------------------------------------

def test_security_two_statements_rejected(datasets):
    with pytest.raises(ValueError, match="Unsafe SQL"):
        run_check(
            "SELECT 1; SELECT 2",
            {},
            datasets,
        )


# ---------------------------------------------------------------------------
# 16. Security: PRAGMA rejected
# ---------------------------------------------------------------------------

def test_security_pragma_rejected(datasets):
    with pytest.raises(ValueError, match="Unsafe SQL"):
        run_check(
            "PRAGMA database_list",
            {},
            datasets,
        )


# ---------------------------------------------------------------------------
# 17. Multiple datasets: two views registered, JOIN works
# ---------------------------------------------------------------------------

def test_multiple_datasets(tmp_path):
    table_a = pa.table({"id": pa.array([1, 2, 3], type=pa.int64()), "score": pa.array([10, 20, 30], type=pa.int64())})
    table_b = pa.table({"id": pa.array([2, 3, 4], type=pa.int64()), "name": pa.array(["x", "y", "z"])})
    path_a = _write_parquet(tmp_path, "a.parquet", table_a)
    path_b = _write_parquet(tmp_path, "b.parquet", table_b)

    result = run_check(
        "SELECT a.id, a.score, b.name FROM ds_a a JOIN ds_b b ON a.id = b.id",
        {},
        {"ds_a": path_a, "ds_b": path_b},
    )
    # ids 2 and 3 exist in both → 2 rows
    assert result.violation_count == 2
    assert result.error is None
    for row in result.sample_rows:
        assert "id" in row and "score" in row and "name" in row


# ---------------------------------------------------------------------------
# 18. Timeout: long-running query returns error="timeout"
# ---------------------------------------------------------------------------

def test_timeout(tmp_path):
    # Write a minimal parquet to satisfy dataset registration
    tiny = pa.table({"x": pa.array([1], type=pa.int64())})
    path = _write_parquet(tmp_path, "tiny.parquet", tiny)

    # generate_series with a large range forces a long scan/count
    result = run_check(
        "SELECT * FROM generate_series(1, 100000000) t(n) WHERE n = -1",
        {},
        {"tiny_data": path},
        timeout_seconds=0.1,
    )
    assert result.error == "timeout"


# ---------------------------------------------------------------------------
# 19. Empty result: violation_count=0, sample_rows=[]
# ---------------------------------------------------------------------------

def test_empty_result(datasets):
    result = run_check(
        "SELECT * FROM test_data WHERE value > {threshold}",
        {"threshold": (9999, "number")},
        datasets,
    )
    assert result.violation_count == 0
    assert result.sample_rows == []
    assert result.error is None


# ---------------------------------------------------------------------------
# 20. Parquet from tmp_path: a real .parquet file is queryable
# ---------------------------------------------------------------------------

def test_parquet_from_tmp_path(tmp_path):
    table = pa.table({"col": pa.array([7, 14, 21], type=pa.int64())})
    path = _write_parquet(tmp_path, "real.parquet", table)

    result = run_check(
        "SELECT * FROM real_data WHERE col > {v}",
        {"v": (10, "number")},
        {"real_data": path},
    )
    assert result.violation_count == 2  # 14 and 21
    assert result.error is None
    assert len(result.sample_rows) == 2
