"""Tests for ``synthetic/corpus_meta.py`` and the repaired register CSVs (task 9.1 steps 1, 5, 5a).

Skips cleanly when ``backend/synthetic/`` is absent.
"""
from __future__ import annotations

import ast
import csv
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
SYNTHETIC = BACKEND / "synthetic"
if not (SYNTHETIC / "corpus_meta.py").is_file():
    pytest.skip("backend/synthetic/ is absent", allow_module_level=True)

from synthetic import corpus_meta as cm  # noqa: E402

pytestmark = pytest.mark.corpus


def _vertical_slug_keys() -> set[str]:
    """``VERTICAL_SLUGS`` keys read with ``ast`` (importing routes.py would pull in app.db)."""
    tree = ast.parse((BACKEND / "app" / "api" / "company" / "routes.py").read_text(encoding="utf-8"))
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
        if any(isinstance(t, ast.Name) and t.id == "VERTICAL_SLUGS" for t in targets):
            return set(ast.literal_eval(node.value).keys())
    raise AssertionError("VERTICAL_SLUGS not found")


def test_canonical_verticals_match_product():
    assert len(cm.CANONICAL_VERTICALS) == 14
    assert {v.lower() for v in cm.CANONICAL_VERTICALS} == _vertical_slug_keys()


def test_document_register():
    entries = cm.read_document_register()
    by_id = {e.doc_id: e for e in entries}
    assert len(entries) == 16  # 12 demo documents + 4 RPL-INF-* scaffolding rows
    assert set(cm.DEMO_DOC_IDS) <= set(by_id)
    assert cm.unmapped_register_verticals(entries) == {}
    for doc_id in cm.DEMO_DOC_IDS:
        e = by_id[doc_id]
        assert e.canonical_vertical in cm.CANONICAL_VERTICALS
        assert e.title and e.version and e.status and e.effective_date and e.review_cycle
        assert e.next_review_date and e.owner_id and e.reviewer_id and e.file_path
    assert by_id["RPL-LEG-RRS-001"].review_cycle == "Biennial"
    assert by_id["RPL-CS-PRO-007"].approver_id is None  # two-signature document
    assert by_id["RPL-SAF-PRO-009"].canonical_vertical == "Workforce & Safety"


def test_people_and_document_roles():
    people = {p.person_id: p for p in cm.read_people()}
    assert len(people) == 27
    p03 = people["P03"]
    assert p03.department == "Legal" and p03.reports_to_id == "P02" and p03.alternate_person_id == "P02"
    assert cm.DocumentRole("RPL-LEG-RRS-001", "reviewer") in p03.document_roles
    assert len(p03.document_roles) == 4
    assert people["P01"].reports_to_id is None
    assert cm.departments()[0] == "Executive"

    # Every demo document's register owner/reviewer/approver is mirrored in document_roles.
    roles = {(r.doc_id, r.role): pid for pid, p in people.items() for r in p.document_roles}
    for e in cm.read_document_register():
        if e.doc_id not in cm.DEMO_DOC_IDS:
            continue
        for role in ("owner", "reviewer", "approver"):
            assert roles.get((e.doc_id, role)) == getattr(e, f"{role}_id"), (e.doc_id, role)


def test_company_profile():
    prof = cm.read_company_profile()
    assert prof.legal_name == "Rockridge Power & Light Company"
    assert prof.regulator == "Indiana Utility Regulatory Commission (IURC)"
    assert prof.business_utility_type == "electric_distribution"
    a = prof.attributes
    assert len(a) == 22
    assert a["utility_type"].type == "string" and a["utility_type"].value == "electric"
    assert a["owns_generating_units"].type == "bool" and a["owns_generating_units"].value is False
    assert a["customer_count_total"].type == "number" and a["customer_count_total"].value == 407491
    assert {x.type for x in a.values()} == {"bool", "number", "string"}


def test_front_matter_all_styles():
    files = cm.doc_files()
    fm = {d: cm.read_front_matter(f.md_path) for d, f in files.items()}
    # YAML
    assert fm["RPL-CS-PRO-004"].version == "5.1" and fm["RPL-CS-PRO-004"].approver_id == "P03"
    assert fm["RPL-CS-PRO-004"].next_review == "2026-02-10"
    assert len(fm["RPL-CS-PRO-004"].regulatory_basis) == 12
    assert fm["RPL-CS-PRO-007"].approver_id is None
    # marker + bold key/value
    assert fm["RPL-CMP-REG-001"].version == "4.0" and fm["RPL-CMP-REG-001"].owner_id == "P09"
    assert fm["RPL-LEG-RRS-001"].version == "7.2" and fm["RPL-LEG-RRS-001"].owner_id == "P03"
    # marker + table
    assert fm["RPL-REG-CAL-2025"].approved_date == "2025-03-14"
    assert fm["RPL-REG-CAL-2025"].law_as_of == "2024-12-31"
    # HTML-comment tariff header: states no title/version, so none is invented
    tar = fm["RPL-TAR-GRR-012"]
    assert (tar.owner_id, tar.reviewer_id, tar.approver_id) == ("P11", "P10", "P03")
    assert tar.effective_date == "2024-06-01" and tar.title is None and tar.version is None


def test_doc_files():
    files = cm.doc_files()
    assert sorted(files) == sorted(cm.DEMO_DOC_IDS)
    regs = {d: [(r.path.name, r.id_column, r.register_type) for r in f.registers] for d, f in files.items()}
    assert regs["RPL-CMP-REG-001"] == [("compliance_register_2024-12-31.csv", "obligation_id", "obligation")]
    assert regs["RPL-LEG-RRS-001"] == [("retention_schedule_2024-12-31.csv", "rrs_id", "retention")]
    assert regs["RPL-REG-CAL-2025"] == [("calendar_events_2025.csv", "event_id", "event")]
    assert sum(len(v) for v in regs.values()) == 3
    for f in files.values():
        assert f.md_path.is_file()


@pytest.mark.parametrize(
    "doc_id,expected_rows,header_len",
    [("RPL-CMP-REG-001", 70, 15), ("RPL-LEG-RRS-001", 86, 13), ("RPL-REG-CAL-2025", 48, 12)],
)
def test_register_csvs_parse_cleanly(doc_id, expected_rows, header_len):
    reg = cm.doc_files()[doc_id].registers[0]
    with open(reg.path, newline="", encoding="utf-8-sig") as fh:
        raw_rows = list(csv.reader(fh))
    assert len(raw_rows[0]) == header_len
    assert all(len(r) == header_len for r in raw_rows), [i for i, r in enumerate(raw_rows, 1) if len(r) != header_len]
    with open(reg.path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == expected_rows
    assert not [r for r in rows if None in r or None in r.values()]
    ids = [r[reg.id_column] for r in rows]
    assert all(i.strip() for i in ids) and len(set(ids)) == len(ids)


def test_retention_rows_repaired_as_intended():
    reg = cm.doc_files()["RPL-LEG-RRS-001"].registers[0]
    with open(reg.path, newline="", encoding="utf-8-sig") as fh:
        rows = {r["rrs_id"]: r for r in csv.DictReader(fh)}
    cs1 = rows["RRS-CS-001"]
    assert cs1["description"] == (
        "All account data for current customers including account setup, rate class, billing history, deposits"
    )
    assert cs1["regulatory_authority"] == "IURC" and cs1["media"] == "electronic"
    assert cs1["implementation_docs"] == "RPL-TAR-GRR-012; RPL-CS-PRO-004"
    assert cs1["wave2_clause_ref"] == "RPL-CS-PRO-004:12.1; RPL-TAR-GRR-012:R01.D01"
    assert cs1["notes"] == "Retain in CIS; 7 years after final close"
    hr5 = rows["RRS-HR-005"]
    assert hr5["regulatory_authority"] == "IOSHA" and hr5["media"] == "electronic"
    assert hr5["vital_record"] == "N" and hr5["disposition_method"] == "delete"
    assert hr5["owner_dept"] == "Human Resources"
