"""Tests for task 2.1.1: allowlist and corpus collector.

Run with:
    cd backend && .venv/bin/python -m pytest tests/company_ingest/test_collector.py -v -k "not qdrant and not corpus and not neon"

To also run the real-corpus integration test:
    cd backend && .venv/bin/python -m pytest tests/company_ingest/test_collector.py -v -m corpus
"""
from __future__ import annotations

import csv
import io
import re
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.company_ingest.collect.allowlist import ALLOW_GLOBS, DENY_GLOBS, is_allowed
from app.company_ingest.collect.collector import (
    SourceFile,
    _detect_p2,
    _detect_profile,
    collect,
)
from app.company_ingest.constants import Profile
from app.company_ingest.run_context import RunContext


# ===========================================================================
# Allowlist — DENY patterns (each DENY pattern must block a sample path)
# ===========================================================================

class TestDenyPatterns:
    """Every DENY pattern must block at least one representative path."""

    def test_deny_basis_json_in_doc_folder(self):
        assert is_allowed("corpus/docs/RPL-CMP-REG-001/RPL-CMP-REG-001.basis.json") is False

    def test_deny_basis_json_nested(self):
        assert is_allowed("corpus/docs/X/subdir/X.basis.json") is False

    def test_deny_scripts_file(self):
        assert is_allowed("corpus/docs/RPL-CS-PRO-004/scripts/render_RPL-CS-PRO-004.py") is False

    def test_deny_scripts_nested_file(self):
        assert is_allowed("corpus/docs/X/scripts/sub/helper.py") is False

    def test_deny_data_readme(self):
        assert is_allowed("corpus/docs/RPL-CMP-REG-001/data/README.md") is False

    def test_deny_data_readme_any_doc(self):
        assert is_allowed("corpus/docs/RPL-DCC-PRO-003/data/README.md") is False

    def test_deny_manifest_json_in_doc_data(self):
        assert is_allowed("corpus/docs/X/data/_manifest.json") is False

    def test_deny_manifest_json_in_global_ops(self):
        assert is_allowed("corpus/_global/ops/_manifest.json") is False

    def test_deny_grounding_file(self):
        assert is_allowed("corpus/grounding/T10.json") is False

    def test_deny_grounding_subdir(self):
        assert is_allowed("corpus/grounding/sub/T11.json") is False

    def test_deny_qa_file(self):
        assert is_allowed("corpus/qa/clause_id_freeze.json") is False

    def test_deny_validation_file(self):
        assert is_allowed("corpus/validation/T90_results.json") is False

    def test_deny_eval_file(self):
        assert is_allowed("corpus/eval/expected_findings.json") is False

    def test_deny_wins_over_allow_basis_json(self):
        # corpus/docs/*/*.md would normally allow .md, but .basis.json should always deny
        # This path also tests DENY winning when it matches before ALLOW
        assert is_allowed("corpus/docs/X/X.basis.json") is False


# ===========================================================================
# Allowlist — ALLOW paths must pass
# ===========================================================================

class TestAllowPatterns:
    def test_allow_doc_md(self):
        assert is_allowed("corpus/docs/RPL-CMP-REG-001/RPL-CMP-REG-001_v4.0.md") is True

    def test_allow_doc_md_generic(self):
        assert is_allowed("corpus/docs/X/X.md") is True

    def test_allow_doc_data_csv(self):
        assert is_allowed("corpus/docs/RPL-CMP-REG-001/data/compliance_register_2024-12-31.csv") is True

    def test_allow_doc_data_csv_generic(self):
        assert is_allowed("corpus/docs/X/data/X.csv") is True

    def test_allow_render_file(self):
        assert is_allowed("corpus/docs/RPL-CMP-REG-001/render/RPL-CMP-REG-001_v4.0.pdf") is True

    def test_allow_render_nested(self):
        assert is_allowed("corpus/docs/X/render/sub/file.pdf") is True

    def test_allow_global_yaml(self):
        assert is_allowed("corpus/_global/company_profile.yaml") is True

    def test_allow_global_ops_csv(self):
        assert is_allowed("corpus/_global/ops/circuits_master.csv") is True

    def test_allow_global_reference_md(self):
        assert is_allowed("corpus/_global/reference/ieee1366_med_method.md") is True

    def test_allow_global_render_pdf(self):
        assert is_allowed("corpus/_global/render/company_fact_sheet.pdf") is True

    def test_deny_wins_global_manifest(self):
        # _manifest.json anywhere is denied even though _global/** would allow it
        assert is_allowed("corpus/_global/ops/_manifest.json") is False


# ===========================================================================
# Allowlist — paths that are neither ALLOW nor DENY → return False
# ===========================================================================

class TestNotAllowedNotDenied:
    def test_python_file_in_doc_root_is_blocked(self):
        # render_RPL-CS-PRO-011.py is directly under doc folder — not in ALLOW
        assert is_allowed("corpus/docs/RPL-CS-PRO-011/render_RPL-CS-PRO-011.py") is False

    def test_md_in_doc_data_subdir_not_allowed(self):
        # .md in data/ subfolder — not matched by corpus/docs/*/*.md (depth mismatch)
        assert is_allowed("corpus/docs/X/data/notes.md") is False

    def test_random_file_outside_corpus_structure(self):
        assert is_allowed("other/folder/file.txt") is False


# ===========================================================================
# Profile detection (mock paths — no real file reads needed for most cases)
# ===========================================================================

class TestProfileDetection:
    """Use temporary files so _detect_p2 can read bytes, but avoid the real corpus."""

    def _make_csv(self, tmp_path: Path, header: list[str], first_row: list[str]) -> Path:
        p = tmp_path / "test.csv"
        with p.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerow(first_row)
        return p

    def test_p1_md_directly_in_doc_folder(self, tmp_path: Path):
        md = tmp_path / "RPL-CMP-REG-001_v4.0.md"
        md.write_text("# Doc")
        rel = "corpus/docs/RPL-CMP-REG-001/RPL-CMP-REG-001_v4.0.md"
        assert _detect_profile(rel, md) == Profile.P1_PROSE

    def test_p1_requires_exactly_4_parts(self, tmp_path: Path):
        # .md inside data/ subfolder is NOT P1
        md = tmp_path / "notes.md"
        md.write_text("notes")
        rel = "corpus/docs/RPL-CMP-REG-001/data/notes.md"
        # 5 parts → cannot be P1; not .csv either → falls through to P3
        assert _detect_profile(rel, md) == Profile.P3_DATASET

    def test_p2_obligation_csv(self, tmp_path: Path):
        csv_path = self._make_csv(
            tmp_path,
            ["obligation_id", "citation", "title"],
            ["OBL-2024-0001", "170 IAC 1-2-1", "Some obligation"],
        )
        rel = "corpus/docs/RPL-CMP-REG-001/data/compliance_register_2024-12-31.csv"
        assert _detect_profile(rel, csv_path) == Profile.P2_REGISTER

    def test_p2_event_csv(self, tmp_path: Path):
        csv_path = self._make_csv(
            tmp_path,
            ["event_id", "citation", "title"],
            ["EVT-2025-0001", "170 IAC 1-2-1", "Some event"],
        )
        rel = "corpus/docs/RPL-REG-CAL-2025/data/calendar_events_2025.csv"
        assert _detect_profile(rel, csv_path) == Profile.P2_REGISTER

    def test_p2_retention_csv(self, tmp_path: Path):
        csv_path = self._make_csv(
            tmp_path,
            ["rrs_id", "record_series_name"],
            ["RRS-CS-001", "Customer Account Records"],
        )
        rel = "corpus/docs/RPL-LEG-RRS-001/data/retention_schedule_2024-12-31.csv"
        assert _detect_profile(rel, csv_path) == Profile.P2_REGISTER

    def test_p3_csv_no_id_col(self, tmp_path: Path):
        csv_path = self._make_csv(
            tmp_path,
            ["circuit_id", "region"],   # ends in _id but first data row won't match OBL/EVT/RRS
            ["CIR-001", "North"],
        )
        rel = "corpus/docs/RPL-DCC-PRO-003/data/outage_events.csv"
        assert _detect_profile(rel, csv_path) == Profile.P3_DATASET

    def test_p3_csv_id_col_but_plain_value(self, tmp_path: Path):
        csv_path = self._make_csv(
            tmp_path,
            ["event_id", "description"],
            ["12345", "plain event"],  # doesn't match EVT-YYYY-NNNN
        )
        rel = "corpus/docs/X/data/events.csv"
        assert _detect_profile(rel, csv_path) == Profile.P3_DATASET

    def test_p4_global_yaml(self, tmp_path: Path):
        f = tmp_path / "company_profile.yaml"
        f.write_text("name: RPL")
        rel = "corpus/_global/company_profile.yaml"
        assert _detect_profile(rel, f) == Profile.P4_REFERENCE

    def test_p4_global_reference_md(self, tmp_path: Path):
        f = tmp_path / "ieee1366_med_method.md"
        f.write_text("# Standard")
        rel = "corpus/_global/reference/ieee1366_med_method.md"
        assert _detect_profile(rel, f) == Profile.P4_REFERENCE

    def test_p3_global_ops_csv(self, tmp_path: Path):
        f = tmp_path / "circuits_master.csv"
        f.write_text("circuit_id,region\nC001,North")
        rel = "corpus/_global/ops/circuits_master.csv"
        assert _detect_profile(rel, f) == Profile.P3_DATASET

    def test_p4_global_ops_non_csv(self, tmp_path: Path):
        f = tmp_path / "reliability_facts.yaml"
        f.write_text("saidi: 42")
        rel = "corpus/_global/ops/reliability_facts.yaml"
        assert _detect_profile(rel, f) == Profile.P4_REFERENCE

    def test_render_in_doc_folder(self, tmp_path: Path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4")
        rel = "corpus/docs/RPL-CMP-REG-001/render/RPL-CMP-REG-001_v4.0.pdf"
        assert _detect_profile(rel, f) == Profile.RENDER

    def test_render_in_global(self, tmp_path: Path):
        f = tmp_path / "fact_sheet.pdf"
        f.write_bytes(b"%PDF-1.4")
        rel = "corpus/_global/render/company_fact_sheet.pdf"
        assert _detect_profile(rel, f) == Profile.RENDER


# ===========================================================================
# _detect_p2 unit tests
# ===========================================================================

class TestDetectP2:
    def _csv_file(self, tmp_path: Path, header: list[str], row: list[str]) -> Path:
        p = tmp_path / "test.csv"
        with p.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerow(row)
        return p

    def test_obligation_pattern(self, tmp_path):
        f = self._csv_file(tmp_path, ["obligation_id"], ["OBL-2024-0001"])
        assert _detect_p2(f) is True

    def test_event_pattern(self, tmp_path):
        f = self._csv_file(tmp_path, ["event_id"], ["EVT-2025-9999"])
        assert _detect_p2(f) is True

    def test_retention_pattern(self, tmp_path):
        f = self._csv_file(tmp_path, ["rrs_id"], ["RRS-CS-001"])
        assert _detect_p2(f) is True

    def test_retention_multi_alpha(self, tmp_path):
        f = self._csv_file(tmp_path, ["rrs_id"], ["RRS-CUST-123"])
        assert _detect_p2(f) is True

    def test_col_not_ending_id(self, tmp_path):
        f = self._csv_file(tmp_path, ["circuit_name"], ["OBL-2024-0001"])
        assert _detect_p2(f) is False

    def test_value_not_matching(self, tmp_path):
        f = self._csv_file(tmp_path, ["event_id"], ["plain-value"])
        assert _detect_p2(f) is False

    def test_empty_csv(self, tmp_path):
        p = tmp_path / "empty.csv"
        p.write_text("")
        assert _detect_p2(p) is False

    def test_header_only_csv(self, tmp_path):
        p = tmp_path / "header_only.csv"
        p.write_text("obligation_id,title\n")
        assert _detect_p2(p) is False


# ===========================================================================
# collect() — unit tests with mocked R2 and settings
# ===========================================================================

class TestCollectUnit:
    """Small synthetic corpus in a temp directory."""

    def _make_corpus(self, tmp_path: Path) -> Path:
        """Create a minimal corpus under tmp_path/corpus/."""
        corpus = tmp_path / "corpus"
        doc_dir = corpus / "docs" / "DOC-001"
        doc_dir.mkdir(parents=True)
        (doc_dir / "DOC-001_v1.0.md").write_text(
            "---\nversion: 1.0\n---\n# Doc\n"
        )
        data_dir = doc_dir / "data"
        data_dir.mkdir()
        with (data_dir / "register.csv").open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["obligation_id", "title"])
            writer.writerow(["OBL-2024-0001", "Some obligation"])
        # A denied file
        (doc_dir / "DOC-001.basis.json").write_text('{"type":"basis"}')
        # Global file
        global_dir = corpus / "_global"
        global_dir.mkdir()
        (global_dir / "company_profile.yaml").write_text("name: Test")
        return corpus

    def test_collect_returns_source_files(self, tmp_path):
        corpus = self._make_corpus(tmp_path)
        ctx = RunContext(company_id="test")
        with patch("app.company_ingest.collect.collector.settings") as mock_settings:
            mock_settings.CORPUS_ROOT = str(corpus)
            mock_settings.COMPANY_ID = "test"
            files = collect(ctx, upload_r2=False)
        assert isinstance(files, list)
        assert all(isinstance(f, SourceFile) for f in files)

    def test_denied_paths_counted(self, tmp_path):
        corpus = self._make_corpus(tmp_path)
        ctx = RunContext(company_id="test")
        with patch("app.company_ingest.collect.collector.settings") as mock_settings:
            mock_settings.CORPUS_ROOT = str(corpus)
            mock_settings.COMPANY_ID = "test"
            collect(ctx, upload_r2=False)
        assert ctx.stats.get("denied_paths", 0) > 0

    def test_denied_path_issues_recorded(self, tmp_path):
        corpus = self._make_corpus(tmp_path)
        ctx = RunContext(company_id="test")
        with patch("app.company_ingest.collect.collector.settings") as mock_settings:
            mock_settings.CORPUS_ROOT = str(corpus)
            mock_settings.COMPANY_ID = "test"
            collect(ctx, upload_r2=False)
        denied_issues = [i for i in ctx.issues if i.code == "denied_path"]
        assert len(denied_issues) > 0
        assert all(i.severity == "info" for i in denied_issues)
        assert all(i.stage == "collect" for i in denied_issues)

    def test_no_denied_files_in_result(self, tmp_path):
        corpus = self._make_corpus(tmp_path)
        ctx = RunContext(company_id="test")
        with patch("app.company_ingest.collect.collector.settings") as mock_settings:
            mock_settings.CORPUS_ROOT = str(corpus)
            mock_settings.COMPANY_ID = "test"
            files = collect(ctx, upload_r2=False)
        rel_paths = {f.rel_path for f in files}
        # basis.json must not appear
        assert not any(".basis.json" in p for p in rel_paths)

    def test_sha256_is_hex(self, tmp_path):
        corpus = self._make_corpus(tmp_path)
        ctx = RunContext(company_id="test")
        with patch("app.company_ingest.collect.collector.settings") as mock_settings:
            mock_settings.CORPUS_ROOT = str(corpus)
            mock_settings.COMPANY_ID = "test"
            files = collect(ctx, upload_r2=False)
        for f in files:
            assert re.fullmatch(r"[0-9a-f]{64}", f.sha256), f"Bad sha256 for {f.rel_path}"

    def test_p1_profile_detected(self, tmp_path):
        corpus = self._make_corpus(tmp_path)
        ctx = RunContext(company_id="test")
        with patch("app.company_ingest.collect.collector.settings") as mock_settings:
            mock_settings.CORPUS_ROOT = str(corpus)
            mock_settings.COMPANY_ID = "test"
            files = collect(ctx, upload_r2=False)
        p1_files = [f for f in files if f.profile == Profile.P1_PROSE]
        assert len(p1_files) == 1
        assert p1_files[0].doc_id == "DOC-001"

    def test_p2_profile_detected(self, tmp_path):
        corpus = self._make_corpus(tmp_path)
        ctx = RunContext(company_id="test")
        with patch("app.company_ingest.collect.collector.settings") as mock_settings:
            mock_settings.CORPUS_ROOT = str(corpus)
            mock_settings.COMPANY_ID = "test"
            files = collect(ctx, upload_r2=False)
        p2_files = [f for f in files if f.profile == Profile.P2_REGISTER]
        assert len(p2_files) == 1

    def test_p4_global_profile_detected(self, tmp_path):
        corpus = self._make_corpus(tmp_path)
        ctx = RunContext(company_id="test")
        with patch("app.company_ingest.collect.collector.settings") as mock_settings:
            mock_settings.CORPUS_ROOT = str(corpus)
            mock_settings.COMPANY_ID = "test"
            files = collect(ctx, upload_r2=False)
        p4_files = [f for f in files if f.profile == Profile.P4_REFERENCE]
        assert len(p4_files) >= 1
        assert any("company_profile.yaml" in f.rel_path for f in p4_files)

    def test_max_50_denied_issues(self, tmp_path):
        """Even when > 50 files are denied, only 50 issues are recorded."""
        corpus = tmp_path / "corpus"
        docs = corpus / "docs" / "BIG-DOC-001"
        docs.mkdir(parents=True)
        (docs / "BIG-DOC-001_v1.0.md").write_text("# doc")
        # Create 60 basis.json files (all denied)
        for i in range(60):
            (docs / f"chunk_{i}.basis.json").write_text("{}")
        ctx = RunContext(company_id="test")
        with patch("app.company_ingest.collect.collector.settings") as mock_settings:
            mock_settings.CORPUS_ROOT = str(corpus)
            mock_settings.COMPANY_ID = "test"
            collect(ctx, upload_r2=False)
        denied_issues = [i for i in ctx.issues if i.code == "denied_path"]
        assert len(denied_issues) == 50
        assert ctx.stats["denied_paths"] == 60


# ===========================================================================
# collect() — real corpus integration tests
# ===========================================================================

EXPECTED_DOC_IDS = {
    "RPL-CMP-REG-001",
    "RPL-CS-PRO-004",
    "RPL-CS-PRO-007",
    "RPL-CS-PRO-011",
    "RPL-DCC-PRO-003",
    "RPL-DO-PLN-002",
    "RPL-ENV-PRO-005",
    "RPL-LEG-RRS-001",
    "RPL-MTR-PGM-001",
    "RPL-REG-CAL-2025",
    "RPL-SAF-PRO-009",
    "RPL-TAR-GRR-012",
}

# P2 CSVs: (doc_id, filename_fragment)
EXPECTED_P2 = [
    ("RPL-CMP-REG-001", "compliance_register"),   # obligation
    ("RPL-REG-CAL-2025", "calendar_events"),       # event
    ("RPL-LEG-RRS-001", "retention_schedule"),     # retention
]


@pytest.mark.corpus
class TestCollectRealCorpus:
    """Integration tests against the actual corpus on disk."""

    @pytest.fixture(scope="class")
    def source_files(self):
        from app.config import settings as real_settings

        ctx = RunContext(company_id=real_settings.COMPANY_ID)
        files = collect(ctx, upload_r2=False)
        return files, ctx

    def test_denied_paths_positive(self, source_files):
        _, ctx = source_files
        assert ctx.stats.get("denied_paths", 0) > 0, "Expected at least one denied path"

    def test_all_12_doc_ids_present(self, source_files):
        files, _ = source_files
        found_doc_ids = {f.doc_id for f in files if f.doc_id is not None}
        missing = EXPECTED_DOC_IDS - found_doc_ids
        assert not missing, f"Missing doc IDs: {missing}"

    def test_p2_obligation_csv_detected(self, source_files):
        files, _ = source_files
        p2_files = [f for f in files if f.profile == Profile.P2_REGISTER]
        obligation = [f for f in p2_files if "compliance_register" in f.rel_path]
        assert obligation, "No obligation P2 CSV found (RPL-CMP-REG-001)"

    def test_p2_event_csv_detected(self, source_files):
        files, _ = source_files
        p2_files = [f for f in files if f.profile == Profile.P2_REGISTER]
        event = [f for f in p2_files if "calendar_events" in f.rel_path]
        assert event, "No event P2 CSV found (RPL-REG-CAL-2025)"

    def test_p2_retention_csv_detected(self, source_files):
        files, _ = source_files
        p2_files = [f for f in files if f.profile == Profile.P2_REGISTER]
        retention = [f for f in p2_files if "retention_schedule" in f.rel_path]
        assert retention, "No retention P2 CSV found (RPL-LEG-RRS-001)"

    def test_no_basis_json_in_result(self, source_files):
        files, _ = source_files
        basis = [f for f in files if f.rel_path.endswith(".basis.json")]
        assert not basis, f"basis.json files leaked into result: {[f.rel_path for f in basis]}"

    def test_no_grounding_files_in_result(self, source_files):
        files, _ = source_files
        grounding = [f for f in files if "corpus/grounding/" in f.rel_path]
        assert not grounding, f"Grounding files leaked: {[f.rel_path for f in grounding]}"

    def test_no_scripts_files_in_result(self, source_files):
        files, _ = source_files
        scripts = [f for f in files if "/scripts/" in f.rel_path]
        assert not scripts, f"Scripts files leaked: {[f.rel_path for f in scripts]}"

    def test_no_qa_eval_validation_files(self, source_files):
        files, _ = source_files
        blocked = [
            f for f in files
            if any(
                seg in f.rel_path
                for seg in ("corpus/qa/", "corpus/eval/", "corpus/validation/")
            )
        ]
        assert not blocked, f"Blocked files leaked: {[f.rel_path for f in blocked]}"

    def test_all_sha256_are_hex(self, source_files):
        files, _ = source_files
        bad = [f for f in files if not re.fullmatch(r"[0-9a-f]{64}", f.sha256)]
        assert not bad, f"Bad SHA-256: {[(f.rel_path, f.sha256) for f in bad]}"

    def test_p1_present_for_every_doc(self, source_files):
        files, _ = source_files
        p1_doc_ids = {f.doc_id for f in files if f.profile == Profile.P1_PROSE}
        missing = EXPECTED_DOC_IDS - p1_doc_ids
        assert not missing, f"Docs without P1: {missing}"

    def test_rel_paths_all_start_with_corpus(self, source_files):
        files, _ = source_files
        bad = [f for f in files if not f.rel_path.startswith("corpus/")]
        assert not bad, f"Bad rel_paths: {[f.rel_path for f in bad]}"
