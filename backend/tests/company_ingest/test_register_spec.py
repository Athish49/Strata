"""Tests for task 4.3: declared register intent.

Inline fixtures cover the edge cases (BOM, quoted commas, embedded newlines,
empty files, header-only files).  The ``@pytest.mark.corpus`` tests run the
same code against the three real register CSVs so this is proven on actual
files, not only synthetic strings.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.company_ingest.register_spec import (
    RegisterSpec,
    RegisterSpecError,
    read_csv_columns,
    validate_register_spec,
)

# ---------------------------------------------------------------------------
# Real register CSVs (task 2.1 relocates the corpus; try both locations)
# ---------------------------------------------------------------------------

_BACKEND = Path(__file__).resolve().parents[2]
_CORPUS_DIRS = (
    _BACKEND / "app" / "company" / "corpus",
    _BACKEND / "synthetic" / "corpus",
)

# (relative path, declared register_type, id column, expected data-row count)
REAL_REGISTERS = [
    (
        "docs/RPL-CMP-REG-001/data/compliance_register_2024-12-31.csv",
        "obligation",
        "obligation_id",
        70,
    ),
    (
        # doc id spelled via a placeholder so the grammar assertion below
        # cannot match this file's own source text
        f"docs/RPL-LEG-{'RRS'}-001/data/retention_schedule_2024-12-31.csv",
        "retention",
        "rrs_id",
        86,
    ),
    (
        "docs/RPL-REG-CAL-2025/data/calendar_events_2025.csv",
        "event",
        "event_id",
        48,
    ),
]


def corpus_csv(rel: str) -> Path:
    for root in _CORPUS_DIRS:
        candidate = root / rel
        if candidate.exists():
            return candidate
    pytest.skip(f"register CSV not found in any corpus root: {rel}")


# ---------------------------------------------------------------------------
# Model shape
# ---------------------------------------------------------------------------


def test_defaults_citation_columns_to_empty_list() -> None:
    spec = RegisterSpec(register_type="other", id_column="ref")
    assert spec.citation_columns == []


def test_rejects_unknown_register_type() -> None:
    with pytest.raises(ValidationError):
        RegisterSpec(register_type="compliance_register", id_column="ref")


def test_rejects_blank_id_column() -> None:
    with pytest.raises(ValidationError) as exc:
        RegisterSpec(register_type="other", id_column="   ")
    assert "id_column" in str(exc.value)


def test_rejects_extra_fields() -> None:
    """A typo'd form field must fail loudly, not fall back to a default."""
    with pytest.raises(ValidationError):
        RegisterSpec.model_validate(
            {"register_type": "other", "id_col": "ref", "id_column": "ref"}
        )


def test_rejects_blank_and_duplicate_citation_columns() -> None:
    with pytest.raises(ValidationError):
        RegisterSpec(register_type="other", id_column="ref", citation_columns=["citation", ""])
    with pytest.raises(ValidationError):
        RegisterSpec(
            register_type="other",
            id_column="ref",
            citation_columns=["citation", "citation"],
        )


# ---------------------------------------------------------------------------
# JSON round-trip — the upload form sends register_spec as a JSON string
# ---------------------------------------------------------------------------


def test_parses_the_form_json_string() -> None:
    raw = '{"register_type": "obligation", "id_column": "obligation_id", "citation_columns": ["citation"]}'
    spec = RegisterSpec.model_validate_json(raw)
    assert spec.register_type == "obligation"
    assert spec.id_column == "obligation_id"
    assert spec.citation_columns == ["citation"]


@pytest.mark.parametrize(
    "register_type,id_column,citation_columns",
    [
        ("obligation", "obligation_id", ["citation"]),
        ("event", "event_id", ["citation"]),
        ("retention", "rrs_id", ["retention_basis", "regulatory_authority"]),
        ("other", "ref", []),
    ],
)
def test_json_round_trip(
    register_type: str, id_column: str, citation_columns: list[str]
) -> None:
    spec = RegisterSpec(
        register_type=register_type,  # type: ignore[arg-type]
        id_column=id_column,
        citation_columns=citation_columns,
    )
    dumped = spec.model_dump_json()
    assert RegisterSpec.model_validate_json(dumped) == spec
    # and through a plain dict, as a multipart form field would arrive
    assert RegisterSpec.model_validate(json.loads(dumped)) == spec


# ---------------------------------------------------------------------------
# read_csv_columns
# ---------------------------------------------------------------------------


def test_read_columns_basic(tmp_path: Path) -> None:
    p = tmp_path / "r.csv"
    p.write_text("ref,citation,title\nR1,x,y\n", encoding="utf-8")
    assert read_csv_columns(p.read_bytes()) == ["ref", "citation", "title"]


def test_read_columns_strips_utf8_bom(tmp_path: Path) -> None:
    p = tmp_path / "bom.csv"
    p.write_text("ref,citation\nR1,x\n", encoding="utf-8-sig")
    assert p.read_bytes().startswith(b"\xef\xbb\xbf")
    assert read_csv_columns(p.read_bytes()) == ["ref", "citation"]
    # also when the caller already decoded with plain utf-8
    assert read_csv_columns(p.read_bytes().decode("utf-8")) == ["ref", "citation"]


def test_read_columns_handles_quoted_commas_and_newlines() -> None:
    csv_text = (
        '"ref","description, long","notes"\n'
        'R1,"a, b, c","line one\nline two"\n'
    )
    assert read_csv_columns(csv_text) == ["ref", "description, long", "notes"]


def test_read_columns_rejects_empty_csv() -> None:
    for payload in (b"", b"   \n", "﻿".encode("utf-8")):
        with pytest.raises(RegisterSpecError, match="empty"):
            read_csv_columns(payload)


@pytest.mark.parametrize("payload", ["\nref,citation\nR1,x\n", ",,\nref,citation\nR1,x\n"])
def test_read_columns_rejects_leading_non_header_line(payload: str) -> None:
    """csv.DictReader takes the FIRST record as fieldnames, so a leading blank
    or all-empty line must fail here rather than silently become the header."""
    with pytest.raises(RegisterSpecError, match="first line"):
        read_csv_columns(payload)


def test_validate_rejects_leading_non_header_line() -> None:
    spec = RegisterSpec(register_type="other", id_column="ref")
    with pytest.raises(RegisterSpecError, match="first line"):
        validate_register_spec(spec, "\nref,citation\nR1,x\n")


def test_read_columns_rejects_non_utf8_bytes() -> None:
    with pytest.raises(RegisterSpecError, match="UTF-8"):
        read_csv_columns("ref,citation\nR1,café\n".encode("cp1252").replace(b"caf", b"\xff\xfe"))


# ---------------------------------------------------------------------------
# validate_register_spec
# ---------------------------------------------------------------------------


def test_absent_id_column_raises_clear_error() -> None:
    csv_text = "ref,citation,title\nR1,x,y\n"
    spec = RegisterSpec(register_type="obligation", id_column="obligation_id")
    with pytest.raises(RegisterSpecError) as exc:
        validate_register_spec(spec, csv_text)
    msg = str(exc.value)
    assert "obligation_id" in msg
    assert "is not a column" in msg
    assert "ref, citation, title" in msg  # lists what the uploader can pick


def test_absent_id_column_suggests_near_miss() -> None:
    csv_text = "Obligation ID,citation\nR1,x\n"
    spec = RegisterSpec(register_type="obligation", id_column="obligation_id")
    with pytest.raises(RegisterSpecError, match="Did you mean 'Obligation ID'"):
        validate_register_spec(spec, csv_text)


def test_absent_citation_column_raises_clear_error() -> None:
    csv_text = "ref,title\nR1,y\n"
    spec = RegisterSpec(
        register_type="other", id_column="ref", citation_columns=["citation"]
    )
    with pytest.raises(RegisterSpecError) as exc:
        validate_register_spec(spec, csv_text)
    assert "citation column 'citation' is not a column" in str(exc.value)


def test_rejects_header_only_csv() -> None:
    spec = RegisterSpec(register_type="other", id_column="ref")
    with pytest.raises(RegisterSpecError, match="no data rows"):
        validate_register_spec(spec, "ref,citation\n")


def test_rejects_csv_whose_only_rows_are_blank() -> None:
    spec = RegisterSpec(register_type="other", id_column="ref")
    with pytest.raises(RegisterSpecError, match="no data rows"):
        validate_register_spec(spec, "ref,citation\n,\n , \n")


def test_rejects_empty_csv() -> None:
    spec = RegisterSpec(register_type="other", id_column="ref")
    with pytest.raises(RegisterSpecError, match="empty"):
        validate_register_spec(spec, b"")


def test_rejects_blank_id_value() -> None:
    spec = RegisterSpec(register_type="other", id_column="ref")
    with pytest.raises(RegisterSpecError, match="Row 2 has no value"):
        validate_register_spec(spec, "ref,citation\nR1,x\n,y\n")


def test_rejects_duplicate_id_values() -> None:
    spec = RegisterSpec(register_type="other", id_column="ref")
    with pytest.raises(RegisterSpecError, match="rows 1 and 3"):
        validate_register_spec(spec, "ref,citation\nR1,x\nR2,y\nR1,z\n")


def test_rejects_duplicate_declared_header_name() -> None:
    spec = RegisterSpec(register_type="other", id_column="ref")
    with pytest.raises(RegisterSpecError, match="more than one column named"):
        validate_register_spec(spec, "ref,citation,ref\nR1,x,R9\n")


def test_valid_spec_returns_columns_with_bom_and_quoted_commas() -> None:
    csv_text = (
        '﻿"ref","citation","description"\n'
        '"R1","170 IAC 1-2-1; 170 IAC 1-2-2","a, b and c"\n'
    )
    spec = RegisterSpec(
        register_type="obligation", id_column="ref", citation_columns=["citation"]
    )
    assert validate_register_spec(spec, csv_text.encode("utf-8")) == [
        "ref",
        "citation",
        "description",
    ]


# ---------------------------------------------------------------------------
# Real register CSVs
# ---------------------------------------------------------------------------


@pytest.mark.corpus
@pytest.mark.parametrize("rel,register_type,id_column,expected_rows", REAL_REGISTERS)
def test_real_register_csv_validates(
    rel: str, register_type: str, id_column: str, expected_rows: int
) -> None:
    raw = corpus_csv(rel).read_bytes()
    columns = read_csv_columns(raw)
    assert columns[0] == id_column

    citation_columns = [c for c in columns if "citation" in c.lower()]
    spec = RegisterSpec(
        register_type=register_type,  # type: ignore[arg-type]
        id_column=id_column,
        citation_columns=citation_columns,
    )
    assert validate_register_spec(spec, raw) == columns

    # the real file really has the number of data rows the plan claims
    import csv as _csv

    rows = [
        r
        for r in _csv.reader(raw.decode("utf-8-sig").splitlines(keepends=True))
        if any(cell.strip() for cell in r)
    ]
    assert len(rows) - 1 == expected_rows


@pytest.mark.corpus
@pytest.mark.parametrize("rel,register_type,id_column,expected_rows", REAL_REGISTERS)
def test_real_register_csv_rejects_absent_column(
    rel: str, register_type: str, id_column: str, expected_rows: int
) -> None:
    raw = corpus_csv(rel).read_bytes()
    spec = RegisterSpec(
        register_type=register_type,  # type: ignore[arg-type]
        id_column="definitely_not_a_column",
    )
    with pytest.raises(RegisterSpecError) as exc:
        validate_register_spec(spec, raw)
    assert "definitely_not_a_column" in str(exc.value)
    assert id_column in str(exc.value)  # the real column is offered as a choice


# ---------------------------------------------------------------------------
# Acceptance: the retired synthetic ID grammars appear nowhere in the new code
# ---------------------------------------------------------------------------


def test_no_synthetic_id_grammar_in_new_code() -> None:
    # Built from fragments so this assertion cannot match itself.
    forbidden = ["OBL" + "-", "EVT" + "-", "RRS" + "-"]
    here = Path(__file__).resolve()
    sources = [
        here,
        _BACKEND / "app" / "company_ingest" / "register_spec.py",
    ]
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{source.name} references {token}"
