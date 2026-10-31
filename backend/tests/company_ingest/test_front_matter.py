"""Tests for task 2.2.1: front-matter parser and document registration.

Run with:
    cd backend && .venv/bin/python -m pytest tests/company_ingest/test_front_matter.py -v -k "not qdrant and not corpus and not neon"
"""
from __future__ import annotations

import textwrap

import pytest

from app.company_ingest.parse.front_matter import FrontMatter, split_front_matter


# ===========================================================================
# Style 1: YAML front matter
# ===========================================================================

YAML_FM_FIXTURE = textwrap.dedent("""\
    ---
    doc_id: RPL-CS-PRO-004
    title: Disconnection, Reconnection & Winter Protection Procedure
    version: "5.1"
    status: Approved
    effective_date: 2025-02-10
    approved_date: 2025-02-05
    law_as_of: 2024-12-31
    owner: {id: P15, name: Jasmine Carter, title: "Supervisor, Credit & Collections"}
    reviewer: {id: P13, name: Karen Mitchell, title: "Director, Customer Service"}
    approver: {id: P03, name: Jonathan Pierce, title: "Senior Counsel, Regulatory"}
    next_review: 2026-02-10
    classification: Internal
    regulatory_basis: ["170 IAC 4-1-1", "170 IAC 4-1-13"]
    supersedes: "5.0 (2024-01-15)"
    ---

    Body starts here.
""")

YAML_FM_TWO_SIG_FIXTURE = textwrap.dedent("""\
    ---
    doc_id: RPL-CS-PRO-007
    title: Meter Test Request & Billing Adjustment Procedure
    version: "3.0"
    status: Approved
    effective_date: 2025-02-17
    approved_date: 2025-02-12
    law_as_of: 2024-12-31
    owner: {id: P18, name: Luis Hernandez, title: "Supervisor, Metering Services"}
    reviewer: {id: P14, name: Steven Park, title: "Director, Customer Operations"}
    approver: null
    next_review: 2026-02-17
    classification: Internal
    regulatory_basis:
      - "170 IAC 4-1-2"
      - "170 IAC 4-1-4"
    ---

    Two-signature body here.
""")


class TestYamlFrontMatter:
    def test_doc_id_extracted(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert fm.doc_id == "RPL-CS-PRO-004"

    def test_title_extracted(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert fm.title == "Disconnection, Reconnection & Winter Protection Procedure"

    def test_version_extracted(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert fm.version == "5.1"

    def test_status_extracted(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert fm.status == "Approved"

    def test_effective_date_extracted(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert str(fm.effective_date) == "2025-02-10"

    def test_approved_date_extracted(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert str(fm.approved_date) == "2025-02-05"

    def test_law_as_of_extracted(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert str(fm.law_as_of) == "2024-12-31"

    def test_next_review_extracted(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert str(fm.next_review) == "2026-02-10"

    def test_classification_extracted(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert fm.classification == "Internal"

    def test_supersedes_extracted(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert fm.supersedes == "5.0 (2024-01-15)"

    def test_regulatory_basis_is_list(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert isinstance(fm.regulatory_basis, list)
        assert "170 IAC 4-1-1" in fm.regulatory_basis
        assert "170 IAC 4-1-13" in fm.regulatory_basis

    def test_owner_id_from_dict(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert fm.owner_id == "P15"

    def test_reviewer_id_from_dict(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert fm.reviewer_id == "P13"

    def test_approver_id_from_dict(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert fm.approver_id == "P03"

    def test_body_text_starts_after_closing_fence(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert body.strip().startswith("Body starts here.")

    def test_body_char_offset_correct(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE, "RPL-CS-PRO-004")
        assert YAML_FM_FIXTURE[offset:].strip().startswith("Body starts here.")

    def test_two_signature_approver_is_none(self):
        fm, body, offset = split_front_matter(YAML_FM_FIXTURE_TWO_SIG := YAML_FM_TWO_SIG_FIXTURE, "RPL-CS-PRO-007")
        assert fm.approver_id is None

    def test_two_signature_owner_id_extracted(self):
        fm, body, offset = split_front_matter(YAML_FM_TWO_SIG_FIXTURE, "RPL-CS-PRO-007")
        assert fm.owner_id == "P18"

    def test_two_signature_reviewer_id_extracted(self):
        fm, body, offset = split_front_matter(YAML_FM_TWO_SIG_FIXTURE, "RPL-CS-PRO-007")
        assert fm.reviewer_id == "P14"

    def test_regulatory_basis_list_from_block(self):
        fm, body, offset = split_front_matter(YAML_FM_TWO_SIG_FIXTURE, "RPL-CS-PRO-007")
        assert "170 IAC 4-1-2" in fm.regulatory_basis
        assert "170 IAC 4-1-4" in fm.regulatory_basis


# ===========================================================================
# Style 2: HTML comment header (RPL-TAR-GRR-012)
# ===========================================================================

HTML_COMMENT_FM_FIXTURE = textwrap.dedent("""\
    <!-- RPL-TAR-GRR-012 | Rockridge Power & Light Company | IURC Tariff No. 12 -->
    <!-- Cause No. 99012 | Filed: 2024-04-30 | Effective: 2024-06-01 -->
    <!-- Owner: P11 (Aisha Thompson) | Reviewer: P10 (Robert Haskins) | Approver: P03 (Jonathan Pierce) -->
    <!-- Issuing Officer: Thomas Whitfield, Vice President, Regulatory & Government Affairs (P07) -->
    <!-- Law-as-of: 2024-12-31 | Grounding Pack: T13 | Snapshot: S1 -->

    ---

    # ROCKRIDGE POWER & LIGHT COMPANY
    ## Indiana Utility Regulatory Commission Tariff No. 12
""")


class TestHtmlCommentFrontMatter:
    def test_doc_id_extracted(self):
        fm, body, offset = split_front_matter(HTML_COMMENT_FM_FIXTURE, "RPL-TAR-GRR-012")
        assert fm.doc_id == "RPL-TAR-GRR-012"

    def test_owner_id_extracted(self):
        fm, body, offset = split_front_matter(HTML_COMMENT_FM_FIXTURE, "RPL-TAR-GRR-012")
        assert fm.owner_id == "P11"

    def test_reviewer_id_extracted(self):
        fm, body, offset = split_front_matter(HTML_COMMENT_FM_FIXTURE, "RPL-TAR-GRR-012")
        assert fm.reviewer_id == "P10"

    def test_approver_id_extracted(self):
        fm, body, offset = split_front_matter(HTML_COMMENT_FM_FIXTURE, "RPL-TAR-GRR-012")
        assert fm.approver_id == "P03"

    def test_law_as_of_extracted(self):
        fm, body, offset = split_front_matter(HTML_COMMENT_FM_FIXTURE, "RPL-TAR-GRR-012")
        assert fm.law_as_of == "2024-12-31"

    def test_effective_date_extracted(self):
        fm, body, offset = split_front_matter(HTML_COMMENT_FM_FIXTURE, "RPL-TAR-GRR-012")
        assert fm.effective_date == "2024-06-01"

    def test_body_starts_after_comments(self):
        fm, body, offset = split_front_matter(HTML_COMMENT_FM_FIXTURE, "RPL-TAR-GRR-012")
        assert "ROCKRIDGE POWER" in body

    def test_body_char_offset_correct(self):
        fm, body, offset = split_front_matter(HTML_COMMENT_FM_FIXTURE, "RPL-TAR-GRR-012")
        assert "ROCKRIDGE POWER" in HTML_COMMENT_FM_FIXTURE[offset:]

    def test_body_offset_after_comment_lines(self):
        """The comment lines themselves must not appear in body."""
        fm, body, offset = split_front_matter(HTML_COMMENT_FM_FIXTURE, "RPL-TAR-GRR-012")
        assert "<!-- RPL-TAR-GRR-012" not in body


# ===========================================================================
# Style 3: Marker-based (RPL-CMP-REG-001 — bold key-values)
# ===========================================================================

MARKER_KV_FIXTURE = textwrap.dedent("""\
    # IURC Regulatory Compliance Register

    <!-- RPL-CMP-REG-001:meta -->
    **Document ID:** RPL-CMP-REG-001
    **Version:** 4.0
    **Title:** IURC Regulatory Compliance Register
    **Company:** Rockridge Power & Light Company (RPL)
    **Law as of Date:** 2024-12-31
    **Approved:** 2025-01-23
    **Effective:** 2025-01-23
    **Supersedes:** RPL-CMP-REG-001 v3.2 (2024-07-01)
    **Owner:** Marcus Lee, Manager Regulatory Compliance (P09)
    **Reviewer:** Elena Vasquez, Director Regulatory Affairs (P08)
    **Approver:** Jonathan Pierce, VP Legal & Regulatory (P03)
    **Classification:** Internal — Regulatory Compliance

    ---

    ## Table of Contents

    1. Purpose
""")

# Style 3b: pipe-separated bold kv (RPL-LEG-RRS-001)
MARKER_PIPE_FIXTURE = textwrap.dedent("""\
    # Records Retention Schedule

    <!-- RPL-LEG-RRS-001:1.0 -->
    **Document ID:** RPL-LEG-RRS-001 | **Version:** 7.2
    **Approved:** 2025-01-23 | **Effective:** 2025-01-23
    **Prepared by:** Jonathan Pierce, Senior Counsel Regulatory (P03)
    **Reviewer:** Elena Vasquez, Manager Regulatory Affairs (P08)
    **Approver:** Sandra Kim, Director Environmental Health & Safety (P24)
    **Supersedes:** RPL-LEG-RRS-001 v7.1 (2024-04-01)
    **Law As-Of Date:** 2024-12-31

    ---

    ## Section 1 — Purpose
""")

# Style 3c: table style (RPL-REG-CAL-2025)
MARKER_TABLE_FIXTURE = textwrap.dedent("""\
    # RPL-REG-CAL-2025: 2025 Regulatory Compliance Calendar
    ## Rockridge Power & Light Company

    <!-- RPL-REG-CAL-2025:front-matter -->

    | Field | Value |
    |---|---|
    | **Document ID** | RPL-REG-CAL-2025 |
    | **Version** | 1.2 |
    | **Title** | 2025 Regulatory Compliance Calendar |
    | **Approved** | 2025-03-14 |
    | **Effective** | 2025-03-17 |
    | **Law as-of** | 2024-12-31 |
    | **Owner** | Marcus Lee (P09), Regulatory Affairs Analyst |
    | **Reviewer** | Elena Vasquez (P08), Manager Regulatory Affairs |
    | **Approver** | Jonathan Pierce (P03), Senior Counsel Regulatory |
    | **Supersedes** | RPL-REG-CAL-2025 v1.1 (2024-02-28) |

    ---

    ## Section 1 — Purpose
""")


class TestMarkerFrontMatterKV:
    """Tests for CMP-REG-001 style (bold key-value pairs)."""

    def test_doc_id_extracted(self):
        fm, body, offset = split_front_matter(MARKER_KV_FIXTURE, "RPL-CMP-REG-001")
        assert fm.doc_id == "RPL-CMP-REG-001"

    def test_version_extracted(self):
        fm, body, offset = split_front_matter(MARKER_KV_FIXTURE, "RPL-CMP-REG-001")
        assert fm.version == "4.0"

    def test_title_extracted(self):
        fm, body, offset = split_front_matter(MARKER_KV_FIXTURE, "RPL-CMP-REG-001")
        assert fm.title == "IURC Regulatory Compliance Register"

    def test_law_as_of_extracted(self):
        fm, body, offset = split_front_matter(MARKER_KV_FIXTURE, "RPL-CMP-REG-001")
        assert fm.law_as_of == "2024-12-31"

    def test_owner_id_extracted(self):
        fm, body, offset = split_front_matter(MARKER_KV_FIXTURE, "RPL-CMP-REG-001")
        assert fm.owner_id == "P09"

    def test_reviewer_id_extracted(self):
        fm, body, offset = split_front_matter(MARKER_KV_FIXTURE, "RPL-CMP-REG-001")
        assert fm.reviewer_id == "P08"

    def test_approver_id_extracted(self):
        fm, body, offset = split_front_matter(MARKER_KV_FIXTURE, "RPL-CMP-REG-001")
        assert fm.approver_id == "P03"

    def test_body_starts_after_separator(self):
        fm, body, offset = split_front_matter(MARKER_KV_FIXTURE, "RPL-CMP-REG-001")
        assert "Table of Contents" in body

    def test_body_char_offset_correct(self):
        fm, body, offset = split_front_matter(MARKER_KV_FIXTURE, "RPL-CMP-REG-001")
        assert "Table of Contents" in MARKER_KV_FIXTURE[offset:]


class TestMarkerFrontMatterPipe:
    """Tests for LEG-RRS-001 style (pipe-separated bold kv)."""

    def test_version_extracted(self):
        fm, body, offset = split_front_matter(MARKER_PIPE_FIXTURE, "RPL-LEG-RRS-001")
        assert fm.version == "7.2"

    def test_owner_id_extracted(self):
        fm, body, offset = split_front_matter(MARKER_PIPE_FIXTURE, "RPL-LEG-RRS-001")
        assert fm.owner_id == "P03"

    def test_reviewer_id_extracted(self):
        fm, body, offset = split_front_matter(MARKER_PIPE_FIXTURE, "RPL-LEG-RRS-001")
        assert fm.reviewer_id == "P08"

    def test_approver_id_extracted(self):
        fm, body, offset = split_front_matter(MARKER_PIPE_FIXTURE, "RPL-LEG-RRS-001")
        assert fm.approver_id == "P24"

    def test_body_after_separator(self):
        fm, body, offset = split_front_matter(MARKER_PIPE_FIXTURE, "RPL-LEG-RRS-001")
        assert "Section 1" in body


class TestMarkerFrontMatterTable:
    """Tests for REG-CAL-2025 style (markdown table)."""

    def test_version_extracted(self):
        fm, body, offset = split_front_matter(MARKER_TABLE_FIXTURE, "RPL-REG-CAL-2025")
        assert fm.version == "1.2"

    def test_title_extracted(self):
        fm, body, offset = split_front_matter(MARKER_TABLE_FIXTURE, "RPL-REG-CAL-2025")
        assert fm.title == "2025 Regulatory Compliance Calendar"

    def test_owner_id_extracted(self):
        fm, body, offset = split_front_matter(MARKER_TABLE_FIXTURE, "RPL-REG-CAL-2025")
        assert fm.owner_id == "P09"

    def test_reviewer_id_extracted(self):
        fm, body, offset = split_front_matter(MARKER_TABLE_FIXTURE, "RPL-REG-CAL-2025")
        assert fm.reviewer_id == "P08"

    def test_approver_id_extracted(self):
        fm, body, offset = split_front_matter(MARKER_TABLE_FIXTURE, "RPL-REG-CAL-2025")
        assert fm.approver_id == "P03"

    def test_body_after_separator(self):
        fm, body, offset = split_front_matter(MARKER_TABLE_FIXTURE, "RPL-REG-CAL-2025")
        assert "Section 1" in body

    def test_body_char_offset_correct(self):
        fm, body, offset = split_front_matter(MARKER_TABLE_FIXTURE, "RPL-REG-CAL-2025")
        assert "Section 1" in MARKER_TABLE_FIXTURE[offset:]


# ===========================================================================
# body_char_offset precision tests
# ===========================================================================

class TestBodyCharOffset:
    def test_yaml_offset_points_to_body(self):
        text = "---\ndoc_id: RPL-X\n---\n\nHello world"
        fm, body, offset = split_front_matter(text, "RPL-X")
        assert text[offset:].strip() == "Hello world"

    def test_html_comment_offset_points_to_body(self):
        text = "<!-- RPL-TAR-GRR-012 | Company | Tariff -->\n<!-- Law-as-of: 2024-12-31 -->\n\nBody here"
        fm, body, offset = split_front_matter(text, "RPL-TAR-GRR-012")
        assert "Body here" in text[offset:]

    def test_marker_offset_points_to_body(self):
        text = "# Title\n\n<!-- RPL-CMP-REG-001:meta -->\n**Version:** 1.0\n\n---\n\nContent here"
        fm, body, offset = split_front_matter(text, "RPL-CMP-REG-001")
        assert "Content here" in text[offset:]


# ===========================================================================
# FrontMatter dataclass
# ===========================================================================

class TestFrontMatterDataclass:
    def test_regulatory_basis_defaults_to_empty_list(self):
        fm = FrontMatter()
        assert fm.regulatory_basis == []

    def test_all_fields_default_to_none(self):
        fm = FrontMatter()
        for attr in ("doc_id", "title", "version", "status", "effective_date",
                     "approved_date", "law_as_of", "next_review", "classification",
                     "supersedes", "owner_id", "reviewer_id", "approver_id",
                     "vertical", "review_cycle"):
            assert getattr(fm, attr) is None, f"{attr} should default to None"

    def test_approver_id_can_be_none(self):
        fm = FrontMatter(owner_id="P18", reviewer_id="P14", approver_id=None)
        assert fm.approver_id is None
