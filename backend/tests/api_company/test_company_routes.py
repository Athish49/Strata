import builtins
import inspect
import os
import pathlib
from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.api.company import routes as r


def test_vertical_slug():
    assert r.vertical_slug("Compliance & Legal") == "compliance-legal"
    assert r.vertical_slug("Workforce & Safety") == "workforce-hr"
    assert r.vertical_slug("Environmental") == "environmental-esg"
    assert r.vertical_slug("Nope") == "unclassified"
    assert r.vertical_slug(None) == "unclassified"


def test_doc_type_label_from_doc_class_column():
    assert r.doc_type_label("procedure") == "Procedure"
    assert r.doc_type_label("retention_schedule") == "Retention Schedule"
    assert r.doc_type_label("tariff") == "Tariff"
    assert r.doc_type_label(None) == "Document"
    assert r.doc_type_label("  ") == "Document"


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


# ------------------------------------------------- DB-only payloads (no corpus)
DOC_ROW = {
    "doc_id": "DOC-000123", "title": "Customer Notice Procedure", "doc_class": "procedure",
    "doc_number": "RPL-CS-PRO-007", "vertical": "Policy & Governance", "review_cycle": "Annual",
    "owner_id": "P18", "reviewer_id": "P14", "approver_id": None,
    "version": "v5.1", "status": "approved", "effective_date": date(2025, 1, 2),
    "approved_date": date(2024, 12, 20), "law_as_of": date(2024, 12, 1),
    "next_review": date(2026, 2, 17), "ingest_status": "ingested",
    "o_pid": "P18", "o_name": "Ann Owner", "o_title": "Director", "o_dept": "CS", "o_rt": "P01",
    "r_pid": "P14", "r_name": "Rex Reviewer", "r_title": "Manager", "r_dept": "Legal", "r_rt": "P01",
    "a_pid": None, "a_name": None, "a_title": None, "a_dept": None, "a_rt": None,
}

DOC_KEYS = {"doc_id", "title", "version", "status", "effective_date", "approved_date", "law_as_of",
            "next_review", "review_cycle", "vertical", "vertical_name", "owner", "reviewer",
            "approver", "two_signature", "monitored", "doc_type", "doc_number", "cited_citations",
            # state for documents with no current version yet (still processing / in review)
            "lifecycle_state", "has_current_version", "latest_version_no",
            "latest_version_status", "latest_ingest_status"}


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    """Matches the first (substring, rows) rule found in the SQL text."""

    def __init__(self, rules):
        self.rules = rules
        self.sql = []

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.sql.append((sql, params))
        for key, rows in self.rules:
            if key in sql:
                return _Res(rows(params) if callable(rows) else rows)
        return _Res([])


def client_for(rules):
    from app.db import get_db
    from app.main import app

    sess = FakeSession(rules)

    async def _dep():
        yield sess

    app.dependency_overrides[get_db] = _dep
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    return c, sess


@pytest.fixture
def _clear_overrides():
    yield
    from app.main import app
    app.dependency_overrides.clear()


@pytest.fixture
def no_files(monkeypatch):
    """Any file read during the request fails the test: payloads must be DB-only."""
    def _boom(*a, **k):
        raise AssertionError(f"file I/O during request: {a!r}")

    monkeypatch.setattr(builtins, "open", _boom)
    monkeypatch.setattr(pathlib.Path, "open", _boom)
    monkeypatch.setattr(pathlib.Path, "read_text", _boom)


def test_module_has_no_file_io():
    src = inspect.getsource(r)
    for needle in ("open(", "Path(", "pathlib", "csv", "yaml"):
        assert needle not in src.lower(), needle
    for gone in ("_GLOBAL", "load_register", "load_profile_yaml", "derive_doc_type"):
        assert not hasattr(r, gone), gone


def test_build_document_db_only():
    d = r.build_document(dict(DOC_ROW), ["170 IAC 4-1-16"])
    assert set(d) == DOC_KEYS
    assert d["vertical"] == "policy-governance" and d["vertical_name"] == "Policy & Governance"
    assert d["doc_type"] == "Procedure" and d["doc_number"] == "RPL-CS-PRO-007"
    assert d["next_review"] == "2026-02-17" and d["review_cycle"] == "Annual"
    assert d["two_signature"] and d["monitored"] and d["approver"] is None
    # unpopulated columns -> nulls / fallbacks, never a file lookup
    bare = dict(DOC_ROW, vertical=None, doc_class=None, doc_number=None, review_cycle=None, next_review=None)
    d2 = r.build_document(bare, [])
    assert d2["vertical"] == "unclassified" and d2["doc_type"] == "Document"
    assert d2["doc_number"] is None and d2["review_cycle"] is None and d2["next_review"] is None


async def test_documents_endpoints_fully_populated_from_db(no_files, _clear_overrides):
    # the cited SQL also joins company_documents, so its rule must come first
    c, sess = client_for([
        ("DISTINCT c.doc_id, cs.citation", [{"doc_id": "DOC-000123", "citation": "170 IAC 4-1-16"}]),
        ("FROM company.company_documents cd", [DOC_ROW]),
    ])
    async with c:
        lst = (await c.get("/company/documents")).json()
        one = (await c.get("/company/documents/DOC-000123")).json()
    assert lst == [one]
    assert set(one) == DOC_KEYS
    assert one["doc_number"] == "RPL-CS-PRO-007" and one["doc_type"] == "Procedure"
    assert one["vertical"] == "policy-governance" and one["review_cycle"] == "Annual"
    assert one["next_review"] == "2026-02-17" and one["effective_date"] == "2025-01-02"
    assert one["owner"]["name"] == "Ann Owner" and one["reviewer"]["name"] == "Rex Reviewer"
    assert one["cited_citations"] == ["170 IAC 4-1-16"]
    assert any("cd.doc_class, cd.doc_number" in s for s, _ in sess.sql)


async def test_document_404_from_db(no_files, _clear_overrides):
    c, _ = client_for([])
    async with c:
        assert (await c.get("/company/documents/NOPE")).status_code == 404


async def test_profile_fully_populated_from_db(no_files, _clear_overrides):
    attr = lambda k, t=None, n=None, b=None: {"key": k, "value_text": t, "value_num": n,
                                             "value_bool": b, "source": "api:P18"}
    c, _ = client_for([
        ("FROM company.companies", [{"name": "Riverplain Energy"}]),
        ("FROM company.company_attributes", [
            attr("customer_count_total", n=Decimal("407491")),
            attr("jurisdiction", t="IN"),
            attr("ownership", t="investor_owned"),
            attr("regulator", t="IURC"),
            attr("utility_type", t="electric"),
            attr("has_gas_operations", b=False),
        ]),
    ])
    async with c:
        p = (await c.get("/company/profile")).json()
    assert set(p) == {"name", "type", "state", "customers", "regulator", "attributes"}
    assert p["name"] == "Riverplain Energy" and p["state"] == "Indiana"
    assert p["customers"] == 407491 and p["regulator"] == "IURC"
    assert p["type"] == "Investor-owned electric utility"
    assert {"key": "has_gas_operations", "value": False, "source": "api"} in p["attributes"]


async def test_people_shape_unchanged(no_files, _clear_overrides):
    c, _ = client_for([("FROM company.people", [
        {"person_id": "P18", "name": "Ann", "title": None, "department": "CS", "reports_to_id": None}])])
    async with c:
        ppl = (await c.get("/company/people")).json()
    assert ppl == [{"person_id": "P18", "name": "Ann", "title": "", "department": "CS", "reports_to_id": None}]


needs_db = pytest.mark.skipif(not os.getenv("DATABASE_URL") and not os.path.exists(
    os.path.join(os.path.dirname(__file__), "..", "..", ".env")), reason="no DATABASE_URL")


@needs_db
@pytest.mark.neon
def test_live_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app
    # Post-cutover (task 9.2) shape of the live demo company. v2 ids are system-assigned
    # (`DOC-xxxxxx`), so documents are correlated by `doc_number` (the corpus RPL id), and
    # each register CSV is its own `<RPL id>#register` document (task 9.1 decision (a)):
    # 12 narrative + 3 registers = 15. RPL-CMP-REG-001's 155 v1 clauses are now split
    # 85 narrative + 70 register rows across its two documents.
    with TestClient(app) as c:
        docs = c.get("/company/documents").json()
        assert len(docs) == 15
        by_num = {d["doc_number"]: d for d in docs}
        assert len(by_num) == 15
        assert sum(1 for n in by_num if n.endswith("#register")) == 3
        assert all(d["status"] == "effective" and d["has_current_version"] for d in docs)
        assert "unclassified" not in {d["vertical"] for d in docs}
        assert len({d["vertical"] for d in docs}) == 5
        assert sorted(n for n, d in by_num.items() if d["two_signature"]) == ["RPL-CS-PRO-007", "RPL-CS-PRO-011"]
        for num, n_clauses in (("RPL-CMP-REG-001", 85), ("RPL-CMP-REG-001#register", 70)):
            cl = c.get(f"/company/documents/{by_num[num]['doc_id']}/clauses").json()
            assert len(cl) == n_clauses
            assert sorted(x["ordinal"] for x in cl) == list(range(1, n_clauses + 1))
        assert c.get("/company/documents/NOPE").status_code == 404
        assert c.get("/company/documents/NOPE/clauses").json() == []
        p = c.get("/company/profile").json()
        assert p["customers"] == 407491 and len(p["attributes"]) == 24
        assert p["regulator"] == "Indiana Utility Regulatory Commission (IURC)"
        assert p["type"] == "Investor-owned electric distribution utility"


# ---------------------------------------------------------------- documents with no current version
def test_build_document_exposes_state_for_a_document_still_in_review():
    """A new upload has no current version, so `version`/`status` are blank. The UI must
    still be able to say "processing" / "in review" from the lifecycle + newest version."""
    from app.api.company.routes import build_document

    d = build_document({
        "doc_id": "DOC-000001", "title": "New policy", "vertical": "Compliance & Legal",
        "lifecycle_state": "pending", "version_status": None, "ingest_status": None,
        "latest_version_no": 1, "latest_version_status": "in_review",
        "latest_ingest_status": "pending",
    }, [])
    assert d["lifecycle_state"] == "pending"
    assert d["has_current_version"] is False and d["monitored"] is False
    assert (d["latest_version_no"], d["latest_version_status"], d["latest_ingest_status"]) == (1, "in_review", "pending")
    assert d["version"] == "" and d["status"] == ""


def test_build_document_current_version_is_monitored():
    from app.api.company.routes import build_document

    d = build_document({"doc_id": "DOC-000002", "title": "T", "vertical": "Environmental",
                        "lifecycle_state": "active", "version": "v1.0", "status": "effective",
                        "version_status": "effective", "ingest_status": "ingested"}, [])
    assert d["has_current_version"] is True and d["monitored"] is True
    assert d["vertical"] == "environmental-esg"


def test_all_fourteen_frontend_verticals_map_both_ways():
    """Uploads are accepted into every vertical the product offers, not just the five the
    synthetic corpus happened to use, and each maps back to the slug the UI routes on."""
    from app.api.company.routes import VERTICAL_SLUGS, vertical_slug

    frontend_slugs = {
        "compliance-legal", "policy-governance", "financial-reporting", "revenue-pricing",
        "operations-processes", "technology-systems", "workforce-hr", "environmental-esg",
        "supply-chain-procurement", "risk-insurance", "strategic-competitive",
        "reputational-stakeholder", "contractual-third-party", "capital-infrastructure",
    }
    assert set(VERTICAL_SLUGS.values()) == frontend_slugs
    for name, slug in VERTICAL_SLUGS.items():
        assert vertical_slug(name.title()) == slug
