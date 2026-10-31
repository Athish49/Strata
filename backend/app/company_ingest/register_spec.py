"""Task 4.3 — Declared register intent.

A CSV upload is treated as a *register* (one data row = one clause, parsed by
``parse/register_segmenter.py``) only when the caller explicitly declares it so
by sending a ``register_spec``.  v1 instead sniffed the first data cell against
hard-coded synthetic ID grammars, which no real customer CSV would ever match.
Intent is now declared, never sniffed.

This module owns:

* :class:`RegisterSpec` — the declared intent (TDD §3.3).
* :func:`read_csv_columns` — read a CSV's header row, for a UI column picker.
* :func:`validate_register_spec` — check a spec against actual CSV bytes.

Every failure raised here is caller error (a bad form field or a bad file), so
:class:`RegisterSpecError` carries a message meant to be shown verbatim to the
uploader and must be mapped to a 4xx by the API layer.
"""
from __future__ import annotations

import csv
import io
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "RegisterSpec",
    "RegisterSpecError",
    "read_csv_columns",
    "validate_register_spec",
]


class RegisterSpecError(ValueError):
    """A declared register spec does not match the uploaded CSV.

    The message is user-facing and actionable; the API layer should surface it
    as a 422 ``detail`` rather than letting it become a 500.
    """


class RegisterSpec(BaseModel):
    """User-declared intent for a CSV upload.

    ``register_type`` describes what the rows are; ``id_column`` names the
    header column holding each row's stable identifier; ``citation_columns``
    names the columns carrying regulatory citations.
    """

    model_config = ConfigDict(extra="forbid")

    register_type: Literal["obligation", "event", "retention", "other"]
    id_column: str
    citation_columns: list[str] = Field(default_factory=list)

    @field_validator("id_column")
    @classmethod
    def _id_column_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("id_column must name a column in the CSV header; it cannot be blank.")
        return v

    @field_validator("citation_columns")
    @classmethod
    def _citation_columns_clean(cls, v: list[str]) -> list[str]:
        if any(not c.strip() for c in v):
            raise ValueError("citation_columns cannot contain blank entries.")
        dupes = sorted({c for c in v if v.count(c) > 1})
        if dupes:
            raise ValueError(
                "citation_columns contains duplicate entries: " + ", ".join(dupes)
            )
        return v


def _decode(data: str | bytes) -> str:
    """Decode CSV bytes as UTF-8, tolerating a byte-order mark."""
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise RegisterSpecError(
                "This CSV is not valid UTF-8 text. Re-export it as 'CSV UTF-8' "
                "and upload it again."
            ) from exc
    else:
        text = data
    # A str may still carry a decoded BOM (e.g. read with plain utf-8).
    return text.lstrip("﻿")


def _rows(text: str) -> list[list[str]]:
    """Parse CSV text into raw rows (RFC 4180: quoted fields may hold commas
    and newlines).  Ragged rows are preserved as-is.

    The default ``csv.field_size_limit`` is left alone deliberately: the
    segmenter parses with the same default, so a field this rejects would have
    crashed there instead."""
    try:
        return list(csv.reader(io.StringIO(text, newline="")))
    except csv.Error as exc:
        raise RegisterSpecError(f"This file could not be parsed as CSV: {exc}") from exc


def _is_blank_row(row: list[str]) -> bool:
    return not any(cell.strip() for cell in row)


def read_csv_columns(data: str | bytes) -> list[str]:
    """Return the CSV's column names, in header order.

    Intended for a UI column picker: the uploader sees these names and chooses
    ``id_column`` / ``citation_columns`` from them.

    The *first* record is the header, exactly as ``csv.DictReader`` treats it —
    a leading blank or all-empty line is an error rather than something to skip,
    because the segmenter would otherwise take that line as its column names.

    Raises
    ------
    RegisterSpecError
        If the file is empty, not UTF-8, unparseable, or its first line is not
        a usable header row.
    """
    text = _decode(data)
    if not text.strip():
        raise RegisterSpecError("This CSV file is empty.")

    rows = _rows(text)
    if not rows or _is_blank_row(rows[0]):
        raise RegisterSpecError(
            "The first line of this CSV must be the header row naming the columns."
        )

    # Column names are returned exactly as written in the file (apart from the
    # BOM), so a picked name is the same key ``csv.DictReader`` will produce.
    return list(rows[0])


def _suggest(name: str, columns: list[str]) -> str | None:
    """Return a near-miss column name (case/whitespace-insensitive), if any."""
    key = name.strip().lower().replace(" ", "").replace("_", "")
    for col in columns:
        if col and col.strip().lower().replace(" ", "").replace("_", "") == key:
            return col
    return None


def _check_declared_column(label: str, name: str, columns: list[str]) -> None:
    if name in columns:
        return
    available = ", ".join(c for c in columns if c) or "(none)"
    hint = _suggest(name, columns)
    suffix = f" Did you mean '{hint}'?" if hint else ""
    raise RegisterSpecError(
        f"{label} '{name}' is not a column in this CSV. "
        f"Available columns: {available}.{suffix}"
    )


def validate_register_spec(spec: RegisterSpec, data: str | bytes) -> list[str]:
    """Validate a declared :class:`RegisterSpec` against the CSV it describes.

    Checks, in order:

    1. The CSV is non-empty, UTF-8 (BOM tolerated) and parseable.
    2. ``id_column`` names an existing header column.
    3. Every entry in ``citation_columns`` names an existing header column.
    4. No declared column name is duplicated in the header (``csv.DictReader``
       would silently keep only the last such column).
    5. The CSV has at least one data row that is not entirely blank.
    6. Every data row has a non-empty, unique value in ``id_column`` — the
       segmenter derives ``clause_id`` from it, so blanks and duplicates
       collide downstream.

    Returns
    -------
    list[str]
        The CSV's column names, in header order.

    Raises
    ------
    RegisterSpecError
        On the first failed check, with a message safe to show the uploader.
    """
    columns = read_csv_columns(data)

    _check_declared_column("id_column", spec.id_column, columns)
    for col in spec.citation_columns:
        _check_declared_column("citation column", col, columns)

    declared = [spec.id_column, *spec.citation_columns]
    dupes = sorted({c for c in declared if columns.count(c) > 1})
    if dupes:
        raise RegisterSpecError(
            "This CSV has more than one column named: "
            + ", ".join(f"'{c}'" for c in dupes)
            + ". Give each column a unique name and upload it again."
        )

    text = _decode(data)
    raw = _rows(text)
    # raw[0] is the header (read_csv_columns already proved it usable).  Row
    # numbers below are positions among the data rows, matching the segmenter's
    # own 1-based row numbering; entirely blank rows (common as a trailing
    # artefact of spreadsheet exports) are not counted as data.
    data_rows = [(n, r) for n, r in enumerate(raw[1:], start=1) if not _is_blank_row(r)]
    if not data_rows:
        raise RegisterSpecError(
            "This CSV has a header row but no data rows, so there is nothing to ingest."
        )

    id_index = columns.index(spec.id_column)
    seen: dict[str, int] = {}
    for offset, row in data_rows:
        value = row[id_index].strip() if id_index < len(row) else ""
        if not value:
            raise RegisterSpecError(
                f"Row {offset} has no value in the id column '{spec.id_column}'. "
                "Every row needs a unique identifier."
            )
        if value in seen:
            raise RegisterSpecError(
                f"The id column '{spec.id_column}' must be unique, but '{value}' "
                f"appears in rows {seen[value]} and {offset}."
            )
        seen[value] = offset

    return columns
