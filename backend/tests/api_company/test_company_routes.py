import os

import pytest

from app.api.company import routes as r


def test_vertical_slug():
    assert r.vertical_slug("Compliance & Legal") == "compliance-legal"
    assert r.vertical_slug("Workforce & Safety") == "workforce-hr"
    assert r.vertical_slug("Environmental") == "environmental-esg"
    assert r.vertical_slug("Nope") == "unclassified"
    assert r.vertical_slug(None) == "unclassified"


def test_doc_type():
    assert r.derive_doc_type("RPL-CS-PRO-004") == "Procedure"
    assert r.derive_doc_type("RPL-TAR-GRR-012") == "Tariff"
    assert r.derive_doc_type("RPL-REG-CAL-2025") == "Register"
    assert r.derive_doc_type("RPL-MTR-PGM-001") == "Program Plan"
    assert r.derive_doc_type("RPL-INF-DR-001") == "Document"


def test_unit_kind_and_row_cells():
    assert r.clean_unit_kind("other") == "section"
    assert r.clean_unit_kind("table_row") == "table_row"
    assert r.clean_row_cells({"a": "x", "null": ["y"], "n": 1}) == {"a": "x"}
    assert r.clean_row_cells(None) is None


def test_attribute_value():
    from decimal import Decimal
    assert r.attribute_value(True, None, None) is True
    assert r.attribute_value(None, Decimal("407491"), None) == 407491
    assert isinstance(r.attribute_value(None, Decimal("407491"), None), int)
    assert r.attribute_value(None, Decimal("1.5"), None) == 1.5
    assert r.attribute_value(None, None, "IN") == "IN"
    assert r.attribute_source("company_profile.yaml: x") == "company_profile.yaml"


def test_build_document_csv_fallback():
    row = {"doc_id": "RPL-CS-PRO-007", "title": "t", "vertical": None, "review_cycle": None,
           "approver_id": None, "ingest_status": "ingested", "next_review": None,
           "o_pid": "P18", "o_name": "n", "o_title": "t", "o_dept": "d", "o_rt": None,
           "r_pid": "P14", "r_name": "n", "r_title": "t", "r_dept": "d", "r_rt": None, "a_pid": None}
    reg = {"RPL-CS-PRO-007": {"vertical": "Policy & Governance", "review_cycle": "Annual", "next_review_date": "2026-02-17"}}
    d = r.build_document(row, [], reg)
    assert d["vertical"] == "policy-governance" and d["two_signature"] and d["monitored"]
    assert d["approver"] is None and d["next_review"] == "2026-02-17" and d["review_cycle"] == "Annual"
    d2 = r.build_document(row, [], {})
    assert d2["vertical"] == "unclassified" and d2["next_review"] is None


def test_register_loads():
    assert len(r.load_register()) >= 12


needs_db = pytest.mark.skipif(not os.getenv("DATABASE_URL") and not os.path.exists(
    os.path.join(os.path.dirname(__file__), "..", "..", ".env")), reason="no DATABASE_URL")


@needs_db
@pytest.mark.neon
def test_live_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        docs = c.get("/company/documents").json()
        assert len(docs) == 12
        assert len({d["vertical"] for d in docs}) == 5
        assert sorted(d["doc_id"] for d in docs if d["two_signature"]) == ["RPL-CS-PRO-007", "RPL-CS-PRO-011"]
        cl = c.get("/company/documents/RPL-CMP-REG-001/clauses").json()
        assert len(cl) == 155
        assert sorted(x["ordinal"] for x in cl) == list(range(1, 156))
        assert c.get("/company/documents/NOPE").status_code == 404
        assert c.get("/company/documents/NOPE/clauses").json() == []
        p = c.get("/company/profile").json()
        assert p["customers"] == 407491 and len(p["attributes"]) == 22
