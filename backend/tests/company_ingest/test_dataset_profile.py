"""Tests for Task 7.1.1 — dataset profiling and Parquet conversion."""
from __future__ import annotations

import gzip
import hashlib
import io
import textwrap
import uuid
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from app.company_ingest.collect.collector import SourceFile
from app.company_ingest.constants import Profile
from app.company_ingest.datasets.profile import (
    ColumnProfile,
    DatasetProfile,
    profile_dataset,
)
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source(
    tmp_path: Path,
    content: str,
    filename: str = "test_data.csv",
    doc_id: str | None = "RPL-TEST-001",
    gz: bool = False,
) -> SourceFile:
    """Write *content* to a temp CSV file and return a SourceFile."""
    if gz:
        fname = filename if filename.endswith(".gz") else filename + ".gz"
        fpath = tmp_path / fname
        fpath.write_bytes(gzip.compress(content.encode()))
    else:
        fpath = tmp_path / filename
        fpath.write_text(content, encoding="utf-8")

    data = fpath.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    rel = f"corpus/docs/{doc_id}/data/{fpath.name}" if doc_id else f"corpus/_global/ops/{fpath.name}"
    return SourceFile(
        rel_path=rel,
        abs_path=fpath,
        sha256=sha,
        size=len(data),
        doc_id=doc_id,
        profile=Profile.P3_DATASET,
    )


def _ctx() -> RunContext:
    return RunContext(run_id=uuid.uuid4(), company_id="rpl")


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestDtypeDetection:
    """Test 1: dtype detection for integer, float, text, date, and timestamp columns."""

    def test_integer_float_text(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            row_id,count_val,price,label
            1,10,1.5,alpha
            2,20,2.5,beta
            3,30,3.5,gamma
        """)
        src = _make_source(tmp_path, csv, "dtype_test.csv")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        col_map = {c.column_name: c for c in result.columns}
        assert col_map["row_id"].dtype == "integer"
        assert col_map["count_val"].dtype == "integer"
        assert col_map["price"].dtype == "float"
        assert col_map["label"].dtype == "text"

    def test_date_and_timestamp_dtypes(self, tmp_path: Path) -> None:
        """YYYY-MM-DD → date, YYYY-MM-DDThh:mm → timestamp."""
        csv = textwrap.dedent("""\
            event_date,event_ts,name
            2024-01-01,2024-01-01T12:00,alpha
            2024-01-02,2024-01-02T13:30,beta
            2024-01-03,2024-01-03T09:15,gamma
        """)
        src = _make_source(tmp_path, csv, "date_test.csv")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        col_map = {c.column_name: c for c in result.columns}
        assert col_map["event_date"].dtype == "date", (
            f"Expected 'date', got '{col_map['event_date'].dtype}'"
        )
        assert col_map["event_ts"].dtype == "timestamp", (
            f"Expected 'timestamp', got '{col_map['event_ts'].dtype}'"
        )


class TestNullRate:
    """Test 2: null_rate computation with empty cells."""

    def test_null_rate(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            item_id,value
            1,10
            2,
            3,30
            4,
            5,50
        """)
        src = _make_source(tmp_path, csv, "null_test.csv")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        col_map = {c.column_name: c for c in result.columns}
        # 2 out of 5 rows have empty value → null_rate = 0.4
        assert abs(col_map["value"].null_rate - 0.4) < 1e-9
        assert col_map["item_id"].null_rate == 0.0


class TestDistinctCount:
    """Test 3: distinct_count with known values."""

    def test_distinct_count(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            sensor_id,status
            1,active
            2,active
            3,inactive
            4,active
            5,inactive
        """)
        src = _make_source(tmp_path, csv, "distinct_test.csv")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        col_map = {c.column_name: c for c in result.columns}
        assert col_map["sensor_id"].distinct_count == 5
        assert col_map["status"].distinct_count == 2


class TestTopValues:
    """Test 4: top_values only when distinct_count ≤ 50."""

    def test_top_values_present_when_few_distinct(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            category
            A
            B
            A
            C
            A
            B
        """)
        src = _make_source(tmp_path, csv, "top_test.csv")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        col_map = {c.column_name: c for c in result.columns}
        cat = col_map["category"]
        assert cat.distinct_count == 3
        assert cat.top_values is not None
        # A should be first (count=3)
        assert cat.top_values[0]["value"] == "A"
        assert cat.top_values[0]["count"] == 3

    def test_top_values_none_when_many_distinct(self, tmp_path: Path) -> None:
        # 51 unique values → no top_values
        rows = ["id\n"] + [f"{i}\n" for i in range(51)]
        csv = "".join(rows)
        src = _make_source(tmp_path, csv, "many_distinct.csv")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        col_map = {c.column_name: c for c in result.columns}
        assert col_map["id"].top_values is None


class TestPrimaryKeyDetection:
    """Tests 5 & 6: primary_key detection."""

    def test_primary_key_detected(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            meter_id,reading,flag
            M001,100,ok
            M002,200,ok
            M003,300,warn
        """)
        src = _make_source(tmp_path, csv, "pk_test.csv")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        assert result.primary_key == "meter_id"

    def test_primary_key_none_when_not_unique(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            meter_id,reading
            M001,100
            M001,200
            M002,300
        """)
        src = _make_source(tmp_path, csv, "pk_dup.csv")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        assert result.primary_key is None

    def test_primary_key_none_when_no_id_column(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            name,value
            alice,1
            bob,2
            carol,3
        """)
        src = _make_source(tmp_path, csv, "no_pk.csv")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        assert result.primary_key is None

    def test_serial_column_detected(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            row_serial,name
            1,alice
            2,bob
            3,carol
        """)
        src = _make_source(tmp_path, csv, "serial_test.csv")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        assert result.primary_key == "row_serial"

    def test_primary_key_none_when_has_nulls(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            device_id,name
            D001,alpha
            ,beta
            D003,gamma
        """)
        src = _make_source(tmp_path, csv, "pk_null.csv")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        assert result.primary_key is None


class TestParquetConversion:
    """Test 7: Parquet row count = CSV row count (write and re-read Parquet)."""

    def test_parquet_row_count_matches_csv(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            event_id,ts,value
            1,2024-01-01T00:00:00,10.5
            2,2024-01-02T00:00:00,20.0
            3,2024-01-03T00:00:00,30.5
            4,2024-01-04T00:00:00,40.0
            5,2024-01-05T00:00:00,50.5
        """)
        src = _make_source(tmp_path, csv, "pq_test.csv")

        # Capture written Parquet bytes by patching pq.write_table
        captured: list[bytes] = []
        _orig_write = pq.write_table

        def _capturing_write(table, path, **kwargs):
            _orig_write(table, path, **kwargs)
            captured.append(Path(path).read_bytes())

        import app.company_ingest.datasets.profile as _mod
        orig = _mod.pq.write_table
        _mod.pq.write_table = _capturing_write
        try:
            result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)
        finally:
            _mod.pq.write_table = orig

        assert result.row_count == 5
        assert len(captured) == 1

        # Re-read from Parquet bytes and verify row count
        pq_table = pq.read_table(io.BytesIO(captured[0]))
        assert pq_table.num_rows == 5


class TestEmptyStringNull:
    """Test 8: empty string → null in Parquet (for text columns)."""

    def test_empty_string_in_text_col_is_null(self, tmp_path: Path) -> None:
        """Empty string in a text column must be treated as null."""
        csv = textwrap.dedent("""\
            name,label
            alice,good
            bob,
            carol,great
        """)
        src = _make_source(tmp_path, csv, "empty_text_null.csv")

        # Capture Parquet bytes
        captured: list[bytes] = []
        _orig_write = pq.write_table

        def _cap(table, path, **kwargs):
            _orig_write(table, path, **kwargs)
            captured.append(Path(path).read_bytes())

        import app.company_ingest.datasets.profile as _mod
        orig = _mod.pq.write_table
        _mod.pq.write_table = _cap
        try:
            result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)
        finally:
            _mod.pq.write_table = orig

        # Verify the profile says null_rate > 0 for the text 'label' column
        col_map = {c.column_name: c for c in result.columns}
        assert col_map["label"].null_rate > 0, "Empty string in text column must register as null"

        # Re-read Parquet and verify the cell is actually null
        pq_table = pq.read_table(io.BytesIO(captured[0]))
        label_col = pq_table.column("label").to_pylist()
        assert label_col[1] is None, f"Expected None for empty string, got {label_col[1]!r}"

    def test_empty_string_treated_as_null_numeric(self, tmp_path: Path) -> None:
        """Empty string in a numeric column also yields null."""
        csv = textwrap.dedent("""\
            item_id,score
            1,10
            2,
            3,30
        """)
        src = _make_source(tmp_path, csv, "empty_null.csv")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        col_map = {c.column_name: c for c in result.columns}
        assert col_map["score"].null_rate > 0
        assert col_map["score"].null_rate < 1
        assert result.row_count == 3


class TestGzipCSV:
    """Test gzip-compressed CSV files."""

    def test_gz_csv_profiled(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            sensor_id,reading
            S001,100
            S002,200
            S003,300
        """)
        src = _make_source(tmp_path, csv, "sensor_data.csv", gz=True)
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        assert result.row_count == 3
        assert result.name == "sensor_data"


class TestGlobalOpsFile:
    """Test _global/ops files (doc_id=None)."""

    def test_global_ops_no_doc_id(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            circuit_id,capacity
            C001,100
            C002,200
        """)
        src = _make_source(tmp_path, csv, "circuits_master.csv", doc_id=None)
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        assert result.doc_id is None
        assert result.row_count == 2
        assert "global/ops" in result.r2_parquet_key


class TestDatasetProfileFields:
    """Verify DatasetProfile fields are populated correctly."""

    def test_profile_fields(self, tmp_path: Path) -> None:
        csv = textwrap.dedent("""\
            obs_id,value
            1,10
            2,20
            3,30
        """)
        src = _make_source(tmp_path, csv, "obs_data.csv", doc_id="RPL-OBS-001")
        result = profile_dataset(src, "rpl", str(uuid.uuid4()), _ctx(), upload_r2=False)

        assert result.name == "obs_data"
        assert result.doc_id == "RPL-OBS-001"
        assert result.row_count == 3
        assert result.file_sha256 == src.sha256
        assert "derived" in result.r2_parquet_key
        assert ".parquet" in result.r2_parquet_key
        assert len(result.columns) == 2


# ---------------------------------------------------------------------------
# Corpus tests (slow, marked separately)
# ---------------------------------------------------------------------------


@pytest.mark.corpus
class TestCorpusDatasets:
    """Profile all P3 CSV files in corpus. No R2 upload."""

    def test_all_p3_files(self) -> None:
        """Profile all P3 CSV files and verify Parquet row count matches CSV row count."""
        import csv as csv_mod
        import time

        from app.config import settings
        from app.company_ingest.collect.collector import collect
        from app.company_ingest.constants import Profile

        ctx = _ctx()
        sources = collect(ctx, upload_r2=False)
        # Only CSV/CSV.GZ files labelled P3 (other extensions can end up P3 via fallback)
        p3_files = [
            s for s in sources
            if s.profile == Profile.P3_DATASET
            and s.abs_path.suffix.lower() in (".csv", ".gz")
        ]

        assert len(p3_files) > 0, "No P3 dataset files found in corpus"

        meter_pop_name = "meter_population_2024-12-31"

        for src in p3_files:
            is_meter = meter_pop_name in src.abs_path.name

            # Count CSV rows independently (don't rely on pyarrow for ground truth)
            if src.abs_path.suffix.lower() == ".gz":
                import gzip as gz_mod
                with gz_mod.open(src.abs_path, "rt", encoding="utf-8", errors="replace") as fh:
                    csv_rows = sum(1 for _ in csv_mod.reader(fh)) - 1  # exclude header
            else:
                with src.abs_path.open(encoding="utf-8", errors="replace", newline="") as fh:
                    csv_rows = sum(1 for _ in csv_mod.reader(fh)) - 1

            t0 = time.time()
            dp = profile_dataset(src, "rpl", str(ctx.run_id), ctx, upload_r2=False)
            elapsed = time.time() - t0

            if is_meter:
                assert elapsed < 120, (
                    f"Meter population profiling took {elapsed:.1f}s (limit 120s)"
                )

            assert dp.row_count == csv_rows, (
                f"Row count mismatch for {src.rel_path}: "
                f"profile says {dp.row_count}, CSV reader says {csv_rows}"
            )
