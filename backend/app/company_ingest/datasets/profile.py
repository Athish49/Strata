"""Task 7.1.1 — Dataset profiling and Parquet conversion.

Reads a P3 CSV (or .csv.gz), profiles each column, converts to Parquet,
and (optionally) uploads the result to R2.
"""
from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pa_csv
import pyarrow.parquet as pq

from app.company_ingest.collect.collector import SourceFile
from app.company_ingest.run_context import RunContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ColumnProfile:
    column_name: str
    dtype: str                       # text | integer | float | date | timestamp | boolean
    null_rate: float                 # 0.0 to 1.0
    distinct_count: int
    min_value: str | None            # as string
    max_value: str | None            # as string
    top_values: list[dict] | None    # [{value, count}] top 10, only if ≤ 50 distinct
    semantic_role: str | None = field(default=None)   # SemanticRole value or None
    fk_target: str | None = field(default=None)       # "dataset.column" or "clause:DOC_ID:prefix"


@dataclass
class DatasetProfile:
    name: str                        # file stem
    doc_id: str | None               # None for _global/ops
    row_count: int
    file_sha256: str                 # of the original CSV
    r2_parquet_key: str
    r2_source_key: str
    primary_key: str | None          # first unique, non-null, _id/*_serial column
    columns: list[ColumnProfile] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _map_dtype(arrow_type: pa.DataType) -> str:
    """Map a pyarrow DataType to one of: text, integer, float, date, timestamp, boolean."""
    if pa.types.is_boolean(arrow_type):
        return "boolean"
    if pa.types.is_integer(arrow_type):
        return "integer"
    if pa.types.is_floating(arrow_type):
        return "float"
    if pa.types.is_date(arrow_type):
        return "date"
    if pa.types.is_timestamp(arrow_type):
        return "timestamp"
    return "text"


def _profile_column(col: pa.ChunkedArray, name: str, row_count: int) -> ColumnProfile:
    """Profile a single column array."""
    dtype = _map_dtype(col.type)

    # Null rate
    null_count = col.null_count
    null_rate = null_count / row_count if row_count > 0 else 0.0

    # Non-null values for distinct counting and min/max
    non_null = col.drop_null()
    non_null_flat = non_null.combine_chunks() if isinstance(non_null, pa.ChunkedArray) else non_null

    # Distinct count
    try:
        value_counts_arr = pc.value_counts(non_null_flat)
        distinct_count = len(value_counts_arr)
    except Exception:
        # Fallback: use a Python set
        distinct_count = len(set(non_null_flat.to_pylist()))
        value_counts_arr = None

    # min / max
    min_value: str | None = None
    max_value: str | None = None
    if len(non_null_flat) > 0:
        try:
            min_val = pc.min(non_null_flat).as_py()
            max_val = pc.max(non_null_flat).as_py()
            min_value = str(min_val) if min_val is not None else None
            max_value = str(max_val) if max_val is not None else None
        except Exception:
            pass

    # top_values — only when distinct_count ≤ 50
    top_values: list[dict] | None = None
    if distinct_count <= 50 and value_counts_arr is not None:
        try:
            # value_counts returns a StructArray with fields "values" and "counts"
            pairs: list[dict] = []
            for item in value_counts_arr.to_pylist():
                pairs.append({"value": str(item["values"]), "count": item["counts"]})
            # Sort by count descending, take top 10
            pairs.sort(key=lambda x: x["count"], reverse=True)
            top_values = pairs[:10]
        except Exception:
            top_values = None

    return ColumnProfile(
        column_name=name,
        dtype=dtype,
        null_rate=null_rate,
        distinct_count=distinct_count,
        min_value=min_value,
        max_value=max_value,
        top_values=top_values,
    )


def _detect_primary_key(
    table: pa.Table, columns: list[ColumnProfile]
) -> str | None:
    """Return the first column ending in _id or _serial that is unique and non-null."""
    row_count = table.num_rows
    for cp in columns:
        name_lower = cp.column_name.lower()
        if not (name_lower.endswith("_id") or name_lower.endswith("_serial")):
            continue
        if cp.null_rate == 0.0 and cp.distinct_count == row_count:
            return cp.column_name
    return None


def _resolve_version(source: SourceFile) -> str:
    """Try to determine the version for a doc-level dataset.

    Mirrors the collector's logic: look for a *.md file directly under the
    doc's root directory (corpus/docs/<DOC_ID>/) and call _get_p1_version().
    Falls back to "unknown" if no .md is found or the file is a global ops file.
    """
    if source.doc_id is None:
        return "latest"

    # The CSV lives at corpus/docs/<DOC_ID>/data/<name>.csv
    # The doc's root .md lives at corpus/docs/<DOC_ID>/*.md
    doc_root = source.abs_path.parent.parent  # corpus/docs/<DOC_ID>/
    md_files = list(doc_root.glob("*.md"))
    if md_files:
        from app.company_ingest.collect.collector import _get_p1_version
        return _get_p1_version(md_files[0])

    return "unknown"


def _r2_keys(
    source: SourceFile,
    company_id: str,
    run_id: str,
) -> tuple[str, str]:
    """Return (r2_parquet_key, r2_source_key) for the given SourceFile."""
    from app.company_ingest.store.r2_keys import (
        global_parquet_key,
        parquet_key,
        raw_dataset_key,
        global_file_key,
    )
    from pathlib import PurePosixPath

    doc_id = source.doc_id
    stem = source.abs_path.stem
    # Strip .csv from .csv.gz stem (e.g. "foo.csv" from "foo.csv.gz")
    if stem.endswith(".csv"):
        stem = stem[:-4]

    if doc_id is not None:
        version = _resolve_version(source)
        pq_key = parquet_key(company_id, doc_id, version, stem)
        src_key = raw_dataset_key(company_id, doc_id, version, stem)
    else:
        # _global/ops — parquet key has no version component
        pq_key = global_parquet_key(company_id, stem)
        # Source key: global file key
        parts = PurePosixPath(source.rel_path).parts
        rel_within_global = "/".join(parts[2:])
        src_key = global_file_key(company_id, run_id, rel_within_global)

    return pq_key, src_key


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def profile_dataset(
    source: SourceFile,
    company_id: str,
    run_id: str,
    ctx: RunContext,
    upload_r2: bool = True,
) -> DatasetProfile:
    """Read a P3 CSV (or .csv.gz), profile it, convert to Parquet, upload to R2.

    Parameters
    ----------
    source:
        A SourceFile with profile == Profile.P3_DATASET.
    company_id:
        Company identifier (e.g. "rpl").
    run_id:
        Active run UUID as a string.
    ctx:
        RunContext for logging issues.
    upload_r2:
        When False, skip R2 upload (useful in tests).
    """
    abs_path = source.abs_path
    doc_id = source.doc_id

    # File stem (handle .csv.gz)
    name = abs_path.stem
    if name.endswith(".csv"):
        name = name[:-4]

    # Determine R2 keys
    r2_parquet_key, r2_source_key = _r2_keys(source, company_id, run_id)

    # ------------------------------------------------------------------
    # Read CSV with pyarrow
    # ------------------------------------------------------------------
    convert_opts = pa_csv.ConvertOptions(
        null_values=["", "NULL", "null", "None"],
        strings_can_be_null=True,
        # pa_csv.ISO8601 is the sentinel constant; the string "iso8601" does not work
        timestamp_parsers=[pa_csv.ISO8601],
    )
    read_opts = pa_csv.ReadOptions()
    parse_opts = pa_csv.ParseOptions()

    table = pa_csv.read_csv(
        str(abs_path),
        read_options=read_opts,
        parse_options=parse_opts,
        convert_options=convert_opts,
    )

    row_count = table.num_rows

    # ------------------------------------------------------------------
    # Profile each column
    # ------------------------------------------------------------------
    columns: list[ColumnProfile] = []
    for col_name in table.schema.names:
        col = table.column(col_name)
        cp = _profile_column(col, col_name, row_count)
        columns.append(cp)

    # ------------------------------------------------------------------
    # Detect primary key
    # ------------------------------------------------------------------
    primary_key = _detect_primary_key(table, columns)

    # ------------------------------------------------------------------
    # Write Parquet to a temp file
    # ------------------------------------------------------------------
    parquet_bytes: bytes | None = None
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        pq.write_table(table, str(tmp_path), compression="zstd")
        parquet_bytes = tmp_path.read_bytes()
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Upload to R2 (best-effort)
    # ------------------------------------------------------------------
    version = _resolve_version(source)
    if upload_r2 and parquet_bytes is not None:
        try:
            from app.company_ingest.store import r2

            r2.put_bytes(
                key=r2_parquet_key,
                data=parquet_bytes,
                metadata={
                    # sha256 is the CSV's hash for idempotency (not the Parquet's)
                    "sha256": source.sha256,
                    "content_type": "application/octet-stream",
                    "doc_id": doc_id or "",
                    "version": version,
                    "profile": "p3_dataset",
                },
                content_type="application/octet-stream",
            )
        except Exception as exc:
            ctx.issue(
                "warning",
                "datasets",
                "r2_upload_failed",
                f"R2 upload failed for {abs_path.name}: {exc}",
                path=source.rel_path,
                doc_id=doc_id,
            )

    return DatasetProfile(
        name=name,
        doc_id=doc_id,
        row_count=row_count,
        file_sha256=source.sha256,
        r2_parquet_key=r2_parquet_key,
        r2_source_key=r2_source_key,
        primary_key=primary_key,
        columns=columns,
    )
