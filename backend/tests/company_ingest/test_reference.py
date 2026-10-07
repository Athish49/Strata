"""Tests for task 2.1.2: reference data loaders.

Run (unit tests only — no DB):
    cd backend && .venv/bin/python -m pytest tests/company_ingest/test_reference.py -v -k "not qdrant and not corpus and not neon"

Run corpus integration tests:
    cd backend && .venv/bin/python -m pytest tests/company_ingest/test_reference.py -v -m corpus
"""
from __future__ import annotations

import csv
import io
import textwrap
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.company_ingest.collect.collector import SourceFile
from app.company_ingest.collect.reference import (
    RegisterEntry,
    load_company_profile,
    load_document_register,
    load_people,
    load_reference_data,
    upsert_company,
    upsert_company_attributes,
)
from app.company_ingest.constants import Profile
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx() -> RunContext:
    return RunContext(run_id=uuid.uuid4(), company_id="test_co")


def _write_tmp(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# company_profile.yaml parsing
# ---------------------------------------------------------------------------

MINIMAL_PROFILE_YAML = textwrap.dedent("""\
    company:
      legal_name: "Acme Electric Co."
    applicability_attributes:
      jurisdiction: OH
      utility_type: electric
      owns_generating_units: false
      customer_count_total: 50000
      has_fleet_vehicles: true
      fleet_vehicle_count: 100
""")


class TestLoadCompanyProfile:
    def test_returns_dict(self, tmp_path):
        p = _write_tmp(tmp_path, "company_profile.yaml", MINIMAL_PROFILE_YAML)
        ctx = _make_ctx()
        result = load_company_profile(p, ctx)
        assert isinstance(result, dict)

    def test_company_name_present(self, tmp_path):
        p = _write_tmp(tmp_path, "company_profile.yaml", MINIMAL_PROFILE_YAML)
        ctx = _make_ctx()
        result = load_company_profile(p, ctx)
        assert result["company"]["legal_name"] == "Acme Electric Co."

    def test_applicability_attributes_present(self, tmp_path):
        p = _write_tmp(tmp_path, "company_profile.yaml", MINIMAL_PROFILE_YAML)
        ctx = _make_ctx()
        result = load_company_profile(p, ctx)
        attrs = result.get("applicability_attributes", {})
        assert "jurisdiction" in attrs
        assert attrs["customer_count_total"] == 50000

    def test_bool_values_parsed(self, tmp_path):
        p = _write_tmp(tmp_path, "company_profile.yaml", MINIMAL_PROFILE_YAML)
        ctx = _make_ctx()
        result = load_company_profile(p, ctx)
        attrs = result["applicability_attributes"]
        assert attrs["owns_generating_units"] is False
        assert attrs["has_fleet_vehicles"] is True


# ---------------------------------------------------------------------------
# upsert_company_attributes — parsing logic (no real DB)
# ---------------------------------------------------------------------------

class TestUpsertCompanyAttributesParsing:
    """Test that the function issues the right execute calls (mock session)."""

    @pytest.mark.asyncio
    async def test_attributes_passed_to_session(self, tmp_path):
        p = _write_tmp(tmp_path, "company_profile.yaml", MINIMAL_PROFILE_YAML)
        ctx = _make_ctx()
        session = AsyncMock()
        await upsert_company_attributes(session, "test_co", p, ctx)
        # 6 attributes in the YAML → 6 execute calls
        assert session.execute.call_count == 6

    @pytest.mark.asyncio
    async def test_count_incremented(self, tmp_path):
        p = _write_tmp(tmp_path, "company_profile.yaml", MINIMAL_PROFILE_YAML)
        ctx = _make_ctx()
        session = AsyncMock()
        await upsert_company_attributes(session, "test_co", p, ctx)
        assert ctx.stats.get("company_attributes_upserted", 0) == 6

    @pytest.mark.asyncio
    async def test_bool_attribute_passed(self, tmp_path):
        p = _write_tmp(tmp_path, "company_profile.yaml", MINIMAL_PROFILE_YAML)
        ctx = _make_ctx()
        session = AsyncMock()
        await upsert_company_attributes(session, "test_co", p, ctx)
        # Extract all keyword-args dicts passed to session.execute
        all_kwargs = [call.args[1] for call in session.execute.call_args_list]
        # Find the 'has_fleet_vehicles' call
        fleet_row = next((kw for kw in all_kwargs if kw.get("key") == "has_fleet_vehicles"), None)
        assert fleet_row is not None
        assert fleet_row["value_bool"] is True
        assert fleet_row["value_text"] == "True"

    @pytest.mark.asyncio
    async def test_numeric_attribute_passed(self, tmp_path):
        p = _write_tmp(tmp_path, "company_profile.yaml", MINIMAL_PROFILE_YAML)
        ctx = _make_ctx()
        session = AsyncMock()
        await upsert_company_attributes(session, "test_co", p, ctx)
        all_kwargs = [call.args[1] for call in session.execute.call_args_list]
        count_row = next((kw for kw in all_kwargs if kw.get("key") == "customer_count_total"), None)
        assert count_row is not None
        assert count_row["value_num"] == 50000.0

    @pytest.mark.asyncio
    async def test_no_attributes_issues_warning(self, tmp_path):
        empty_yaml = "company:\n  legal_name: Empty\n"
        p = _write_tmp(tmp_path, "company_profile.yaml", empty_yaml)
        ctx = _make_ctx()
        session = AsyncMock()
        await upsert_company_attributes(session, "test_co", p, ctx)
        warnings = [i for i in ctx.issues if i.code == "no_applicability_attributes"]
        assert len(warnings) == 1


# ---------------------------------------------------------------------------
# people_directory.csv parsing
# ---------------------------------------------------------------------------

PEOPLE_CSV_CONTENT = (
    "person_id,name,title,department,reports_to_id,email,phone_ext,location,"
    "document_roles,oncall_roles,alternate_person_id\n"
    "P01,Alice Smith,Director,Engineering,,alice@example.com,101,HQ,,,"
    "\n"
    "P02,Bob Jones,Manager,Engineering,P01,bob@example.com,102,HQ,"
    "DOC-001:owner,OPS-ONCALL;SAF-ONCALL,P01\n"
    "P03,Carol Lee,Engineer,Engineering,P02,carol@example.com,103,HQ,,,P02\n"
)


class TestLoadPeople:
    @pytest.mark.asyncio
    async def test_all_rows_inserted(self, tmp_path):
        p = _write_tmp(tmp_path, "people_directory.csv", PEOPLE_CSV_CONTENT)
        ctx = _make_ctx()
        session = AsyncMock()
        await load_people(session, "test_co", p, ctx)
        assert session.execute.call_count == 3
        assert ctx.stats["people_upserted"] == 3

    @pytest.mark.asyncio
    async def test_oncall_roles_split_on_semicolon(self, tmp_path):
        p = _write_tmp(tmp_path, "people_directory.csv", PEOPLE_CSV_CONTENT)
        ctx = _make_ctx()
        session = AsyncMock()
        await load_people(session, "test_co", p, ctx)
        # P02 has two oncall_roles
        all_kwargs = [call.args[1] for call in session.execute.call_args_list]
        p02_row = next(kw for kw in all_kwargs if kw["person_id"] == "P02")
        assert p02_row["oncall_roles"] == ["OPS-ONCALL", "SAF-ONCALL"]

    @pytest.mark.asyncio
    async def test_empty_oncall_roles_is_empty_list(self, tmp_path):
        p = _write_tmp(tmp_path, "people_directory.csv", PEOPLE_CSV_CONTENT)
        ctx = _make_ctx()
        session = AsyncMock()
        await load_people(session, "test_co", p, ctx)
        all_kwargs = [call.args[1] for call in session.execute.call_args_list]
        p01_row = next(kw for kw in all_kwargs if kw["person_id"] == "P01")
        assert p01_row["oncall_roles"] == []

    @pytest.mark.asyncio
    async def test_alternate_person_id_nullable(self, tmp_path):
        p = _write_tmp(tmp_path, "people_directory.csv", PEOPLE_CSV_CONTENT)
        ctx = _make_ctx()
        session = AsyncMock()
        await load_people(session, "test_co", p, ctx)
        all_kwargs = [call.args[1] for call in session.execute.call_args_list]
        p01_row = next(kw for kw in all_kwargs if kw["person_id"] == "P01")
        assert p01_row["alternate_person_id"] is None
        p02_row = next(kw for kw in all_kwargs if kw["person_id"] == "P02")
        assert p02_row["alternate_person_id"] == "P01"

    @pytest.mark.asyncio
    async def test_unknown_headers_logged_as_info(self, tmp_path):
        # Add an unknown column 'badge_number'
        content = PEOPLE_CSV_CONTENT.replace(
            "person_id,name,title,department,reports_to_id,email,phone_ext,location,document_roles,oncall_roles,alternate_person_id",
            "person_id,name,title,department,reports_to_id,email,phone_ext,location,document_roles,oncall_roles,alternate_person_id,badge_number",
        ).replace("\nP01,", "\nP01,").replace("\nP02,", "\nP02,").replace("\nP03,", "\nP03,")
        # Just append a value for the new column
        lines = content.strip().split("\n")
        new_lines = [lines[0]]
        for line in lines[1:]:
            new_lines.append(line + ",9999")
        p = _write_tmp(tmp_path, "people_directory.csv", "\n".join(new_lines) + "\n")
        ctx = _make_ctx()
        session = AsyncMock()
        await load_people(session, "test_co", p, ctx)
        unknown_issues = [i for i in ctx.issues if i.code == "unknown_header"]
        assert len(unknown_issues) == 1
        assert "badge_number" in unknown_issues[0].message


# ---------------------------------------------------------------------------
# document_register.csv parsing
# ---------------------------------------------------------------------------

REGISTER_CSV_CONTENT = (
    "doc_id,title,vertical,version,status,effective_date,approved_date,law_as_of,"
    "owner_id,reviewer_id,approver_id,review_cycle,next_review_date,supersedes_version,"
    "supersedes_date,file_path,render_path,record_series_ids,regulatory_basis_sections,"
    "coverage_dispositions_summary,notes\n"
    "DOC-001,Title One,,1.0,Approved,2025-01-01,2024-12-31,,P01,P02,P03,"
    "Annual,2026-01-01,,,corpus/_global/doc1.md,,,§1 Rule A; §2 Rule B,,\n"
    "DOC-002,Title Two,,2.0,Draft,,,2024-12-31,P04,P05,,"
    "Biennial,2027-01-01,,,corpus/_global/doc2.md,,,,\n"
)


class TestLoadDocumentRegister:
    def test_returns_list_of_register_entries(self, tmp_path):
        p = _write_tmp(tmp_path, "document_register.csv", REGISTER_CSV_CONTENT)
        ctx = _make_ctx()
        entries = load_document_register(p, ctx)
        assert len(entries) == 2
        assert all(isinstance(e, RegisterEntry) for e in entries)

    def test_doc_id_parsed(self, tmp_path):
        p = _write_tmp(tmp_path, "document_register.csv", REGISTER_CSV_CONTENT)
        ctx = _make_ctx()
        entries = load_document_register(p, ctx)
        assert entries[0].doc_id == "DOC-001"
        assert entries[1].doc_id == "DOC-002"

    def test_nullable_fields(self, tmp_path):
        p = _write_tmp(tmp_path, "document_register.csv", REGISTER_CSV_CONTENT)
        ctx = _make_ctx()
        entries = load_document_register(p, ctx)
        # DOC-001: law_as_of is empty
        assert entries[0].law_as_of is None
        # DOC-002: effective_date is empty, approver_id is empty
        assert entries[1].effective_date is None
        assert entries[1].approver_id is None

    def test_regulatory_basis_sections_raw(self, tmp_path):
        p = _write_tmp(tmp_path, "document_register.csv", REGISTER_CSV_CONTENT)
        ctx = _make_ctx()
        entries = load_document_register(p, ctx)
        assert entries[0].regulatory_basis_sections == "§1 Rule A; §2 Rule B"
        assert entries[1].regulatory_basis_sections == ""

    def test_count_stat_set(self, tmp_path):
        p = _write_tmp(tmp_path, "document_register.csv", REGISTER_CSV_CONTENT)
        ctx = _make_ctx()
        load_document_register(p, ctx)
        assert ctx.stats["register_entries_loaded"] == 2

    def test_file_path_parsed(self, tmp_path):
        p = _write_tmp(tmp_path, "document_register.csv", REGISTER_CSV_CONTENT)
        ctx = _make_ctx()
        entries = load_document_register(p, ctx)
        assert entries[0].file_path == "corpus/_global/doc1.md"


# ---------------------------------------------------------------------------
# load_reference_data orchestrator
# ---------------------------------------------------------------------------

def _make_source_file(abs_path: Path, name: str | None = None) -> SourceFile:
    return SourceFile(
        rel_path=f"corpus/_global/{name or abs_path.name}",
        abs_path=abs_path,
        sha256="abc123",
        size=abs_path.stat().st_size,
        doc_id=None,
        profile=Profile.P4_REFERENCE,
    )


class TestLoadReferenceData:
    @pytest.mark.asyncio
    async def test_returns_register_entries(self, tmp_path):
        profile_path = _write_tmp(tmp_path, "company_profile.yaml", MINIMAL_PROFILE_YAML)
        people_path = _write_tmp(tmp_path, "people_directory.csv", PEOPLE_CSV_CONTENT)
        register_path = _write_tmp(tmp_path, "document_register.csv", REGISTER_CSV_CONTENT)

        sources = [
            _make_source_file(profile_path),
            _make_source_file(people_path),
            _make_source_file(register_path),
        ]
        ctx = _make_ctx()
        session = AsyncMock()
        result = await load_reference_data(sources, session, "test_co", ctx)
        assert len(result) == 2
        assert all(isinstance(e, RegisterEntry) for e in result)

    @pytest.mark.asyncio
    async def test_non_p4_sources_ignored(self, tmp_path):
        register_path = _write_tmp(tmp_path, "document_register.csv", REGISTER_CSV_CONTENT)
        # Mark as P3, not P4
        non_p4 = SourceFile(
            rel_path="corpus/_global/document_register.csv",
            abs_path=register_path,
            sha256="abc",
            size=register_path.stat().st_size,
            doc_id=None,
            profile=Profile.P3_DATASET,
        )
        ctx = _make_ctx()
        session = AsyncMock()
        result = await load_reference_data([non_p4], session, "test_co", ctx)
        # All three P4 files are missing → warnings issued, no register entries
        assert result == []
        missing = [i for i in ctx.issues if i.severity == "warning"]
        assert len(missing) == 3

    @pytest.mark.asyncio
    async def test_missing_files_issue_warnings(self, tmp_path):
        ctx = _make_ctx()
        session = AsyncMock()
        result = await load_reference_data([], session, "test_co", ctx)
        assert result == []
        codes = {i.code for i in ctx.issues}
        assert "missing_company_profile" in codes
        assert "missing_people_csv" in codes
        assert "missing_document_register" in codes


# ---------------------------------------------------------------------------
# Corpus integration tests (real files, no DB)
# ---------------------------------------------------------------------------

CORPUS_GLOBAL = (
    Path(__file__).parent.parent.parent
    / "app" / "company" / "corpus" / "_global"
)


@pytest.mark.corpus
class TestCorpusFiles:
    """Parsing-only tests against the real corpus files — no DB connection needed."""

    def test_company_profile_has_applicability_attributes(self):
        yaml_path = CORPUS_GLOBAL / "company_profile.yaml"
        ctx = _make_ctx()
        data = load_company_profile(yaml_path, ctx)
        attrs = data.get("applicability_attributes", {})
        assert len(attrs) >= 20, f"Expected ≥ 20 applicability_attributes, got {len(attrs)}"

    def test_document_register_entries(self):
        csv_path = CORPUS_GLOBAL / "document_register.csv"
        ctx = _make_ctx()
        entries = load_document_register(csv_path, ctx)
        assert len(entries) >= 1

    def test_document_register_doc_ids_non_empty(self):
        csv_path = CORPUS_GLOBAL / "document_register.csv"
        ctx = _make_ctx()
        entries = load_document_register(csv_path, ctx)
        for e in entries:
            assert e.doc_id, "doc_id must not be empty"

    @pytest.mark.asyncio
    async def test_upsert_company_attributes_count(self):
        """Parse the real YAML and confirm ≥ 20 attributes are extracted."""
        yaml_path = CORPUS_GLOBAL / "company_profile.yaml"
        ctx = _make_ctx()
        session = AsyncMock()
        await upsert_company_attributes(session, "rpl", yaml_path, ctx)
        assert ctx.stats.get("company_attributes_upserted", 0) >= 20

    @pytest.mark.asyncio
    async def test_load_people_count(self):
        """Parse the real people CSV and confirm 27 people are processed."""
        csv_path = CORPUS_GLOBAL / "people_directory.csv"
        ctx = _make_ctx()
        session = AsyncMock()
        await load_people(session, "rpl", csv_path, ctx)
        assert ctx.stats.get("people_upserted", 0) == 27
