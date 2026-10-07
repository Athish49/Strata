"""Unit tests for compare_basis.py pure functions.

These tests use inline fixtures only — no *.basis.json files are read from disk.
Run with:
    cd /Users/athish/Documents/Strata && python -m pytest tools/offline_eval/test_compare_basis.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).parent))

from compare_basis import (
    build_confusion_matrix,
    compute_citation_agreement,
    compute_parameter_recall,
    compute_role_agreement,
    generate_report,
)


# ---------------------------------------------------------------------------
# Role agreement tests
# ---------------------------------------------------------------------------


def test_role_agreement_partial_match():
    """3 clauses, 2 match, 1 mismatch → 66.7% agreement."""
    basis = [
        {"clause_id": "DOC:1.1", "clause_type": "regulatory_restatement"},
        {"clause_id": "DOC:1.2", "clause_type": "obligation"},
        {"clause_id": "DOC:1.3", "clause_type": "obligation"},
    ]
    engine = {
        "DOC:1.1": {"role": "regulatory_restatement"},
        "DOC:1.2": {"role": "obligation"},
        "DOC:1.3": {"role": "boilerplate"},  # mismatch
    }
    result = compute_role_agreement(basis, engine)
    assert result["total"] == 3
    assert result["matched"] == 2
    assert result["agreement_pct"] == 66.7
    assert len(result["misses"]) == 1
    assert result["misses"][0][0] == "DOC:1.3"


def test_role_agreement_full_match():
    """All clauses match → 100%."""
    basis = [
        {"clause_id": "DOC:2.1", "clause_type": "obligation"},
    ]
    engine = {
        "DOC:2.1": {"role": "obligation"},
    }
    result = compute_role_agreement(basis, engine)
    assert result["total"] == 1
    assert result["matched"] == 1
    assert result["agreement_pct"] == 100.0


def test_role_agreement_no_clause_type_skipped():
    """Basis clauses without clause_type are skipped."""
    basis = [
        {"clause_id": "DOC:3.1"},  # no clause_type
        {"clause_id": "DOC:3.2", "clause_type": "obligation"},
    ]
    engine = {
        "DOC:3.2": {"role": "obligation"},
    }
    result = compute_role_agreement(basis, engine)
    assert result["total"] == 1
    assert result["matched"] == 1


# ---------------------------------------------------------------------------
# Confusion matrix tests
# ---------------------------------------------------------------------------


def test_confusion_matrix_correct_pair_counted():
    """When basis=regulatory_restatement and engine=obligation, that pair is counted."""
    basis = [
        {"clause_id": "DOC:4.1", "clause_type": "regulatory_restatement"},
        {"clause_id": "DOC:4.2", "clause_type": "obligation"},
    ]
    engine = {
        "DOC:4.1": {"role": "obligation"},   # mismatch
        "DOC:4.2": {"role": "obligation"},   # match
    }
    matrix = build_confusion_matrix(basis, engine)
    assert matrix.get(("regulatory_restatement", "obligation"), 0) == 1
    assert matrix.get(("obligation", "obligation"), 0) == 1


def test_confusion_matrix_missing_engine_marked():
    """When engine clause is missing, role is recorded as MISSING."""
    basis = [
        {"clause_id": "DOC:5.1", "clause_type": "obligation"},
    ]
    engine = {}  # no engine output
    matrix = build_confusion_matrix(basis, engine)
    assert matrix.get(("obligation", "MISSING"), 0) == 1


# ---------------------------------------------------------------------------
# Parameter recall tests
# ---------------------------------------------------------------------------


def test_parameter_recall_overlapping_span_counted():
    """Overlapping span between basis and engine parameter → counted as found."""
    basis = [
        {
            "clause_id": "DOC:6.1",
            "clause_type": "regulatory_restatement",
            "parameters": [
                {"span": [10, 45], "value_text": "30 days", "kind": "period"},
            ],
        }
    ]
    engine = {
        "DOC:6.1": {
            "parameters": [
                # overlapping span [20, 50]
                {"span_start": 20, "span_end": 50, "value_text": "thirty days", "kind": "period"},
            ]
        }
    }
    result = compute_parameter_recall(basis, engine)
    assert result["total"] == 1
    assert result["found"] == 1
    assert result["recall_pct"] == 100.0


def test_parameter_recall_equal_value_text_counted():
    """Equal normalized value_text (no span overlap) → counted as found."""
    basis = [
        {
            "clause_id": "DOC:7.1",
            "clause_type": "regulatory_restatement",
            "parameters": [
                {"span": [0, 5], "value_text": "30 days", "kind": "period"},
            ],
        }
    ]
    engine = {
        "DOC:7.1": {
            "parameters": [
                # no overlap with [0,5] but same normalized text
                {"span_start": 100, "span_end": 110, "value_text": "30 days", "kind": "period"},
            ]
        }
    }
    result = compute_parameter_recall(basis, engine)
    assert result["total"] == 1
    assert result["found"] == 1
    assert result["recall_pct"] == 100.0


def test_parameter_recall_no_match_not_counted():
    """No span overlap and different value_text → not counted (miss)."""
    basis = [
        {
            "clause_id": "DOC:8.1",
            "clause_type": "regulatory_restatement",
            "parameters": [
                {"span": [0, 5], "value_text": "30 days", "kind": "period"},
            ],
        }
    ]
    engine = {
        "DOC:8.1": {
            "parameters": [
                {"span_start": 100, "span_end": 110, "value_text": "60 days", "kind": "period"},
            ]
        }
    }
    result = compute_parameter_recall(basis, engine)
    assert result["total"] == 1
    assert result["found"] == 0
    assert result["recall_pct"] == 0.0
    assert len(result["misses"]) == 1


def test_parameter_recall_non_regulatory_skipped():
    """Clauses that are not regulatory_restatement are skipped."""
    basis = [
        {
            "clause_id": "DOC:9.1",
            "clause_type": "obligation",  # not regulatory_restatement
            "parameters": [
                {"span": [0, 10], "value_text": "30 days", "kind": "period"},
            ],
        }
    ]
    engine = {"DOC:9.1": {"parameters": []}}
    result = compute_parameter_recall(basis, engine)
    assert result["total"] == 0
    assert result["found"] == 0


# ---------------------------------------------------------------------------
# Citation agreement tests
# ---------------------------------------------------------------------------


def test_citation_agreement_present():
    """Basis citation present in engine cited_sections → counted."""
    basis = [
        {
            "clause_id": "DOC:10.1",
            "citations": ["170 IAC 4-1-16"],
        }
    ]
    engine = {
        "DOC:10.1": {
            "citations": [
                {"normalized_key": "170 IAC 4-1-16", "code_section_id": "sec-1"},
            ]
        }
    }
    result = compute_citation_agreement(basis, engine)
    assert result["total"] == 1
    assert result["found"] == 1
    assert result["agreement_pct"] == 100.0


def test_citation_agreement_missing():
    """Basis citation NOT in engine cited_sections → recorded as gap."""
    basis = [
        {
            "clause_id": "DOC:11.1",
            "citations": ["170 IAC 4-1-16"],
        }
    ]
    engine = {
        "DOC:11.1": {
            "citations": [
                {"normalized_key": "170 IAC 4-1-99", "code_section_id": "sec-99"},
            ]
        }
    }
    result = compute_citation_agreement(basis, engine)
    assert result["total"] == 1
    assert result["found"] == 0
    assert result["agreement_pct"] == 0.0
    assert ("DOC:11.1", "170 IAC 4-1-16") in result["misses"]


def test_citation_agreement_partial():
    """Some citations found, some missing → partial agreement %."""
    basis = [
        {
            "clause_id": "DOC:12.1",
            "citations": ["170 IAC 4-1-16", "170 IAC 4-1-17"],
        }
    ]
    engine = {
        "DOC:12.1": {
            "citations": [
                {"normalized_key": "170 IAC 4-1-16"},
                # 170 IAC 4-1-17 missing
            ]
        }
    }
    result = compute_citation_agreement(basis, engine)
    assert result["total"] == 2
    assert result["found"] == 1
    assert result["agreement_pct"] == 50.0


# ---------------------------------------------------------------------------
# Report generation test
# ---------------------------------------------------------------------------


def test_generate_report_contains_summary_and_matrix():
    """generate_report returns a Markdown string with summary table and confusion matrix."""
    role_stats = {
        "total": 3,
        "matched": 2,
        "agreement_pct": 66.7,
        "misses": [("DOC:1.3", "obligation", "boilerplate")],
    }
    param_stats = {
        "total": 4,
        "found": 4,
        "recall_pct": 100.0,
        "misses": [],
    }
    cite_stats = {
        "total": 2,
        "found": 1,
        "agreement_pct": 50.0,
        "misses": [("DOC:11.1", "170 IAC 4-1-16")],
    }
    confusion_matrix = {
        ("obligation", "obligation"): 2,
        ("obligation", "boilerplate"): 1,
    }

    report = generate_report(
        run_id="test-run-001",
        role_stats=role_stats,
        param_stats=param_stats,
        cite_stats=cite_stats,
        confusion_matrix=confusion_matrix,
    )

    assert "test-run-001" in report
    assert "66.7%" in report
    assert "100.0%" in report
    assert "50.0%" in report
    assert "Confusion Matrix" in report
    assert "obligation" in report
    assert "boilerplate" in report
    assert "≥ 90%" in report
    assert "≥ 95%" in report
    assert "tracked, not enforced" in report
