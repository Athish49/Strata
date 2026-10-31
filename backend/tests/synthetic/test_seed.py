"""Tests for ``synthetic/seed.py``'s pure logic (task 9.1): the document plan, the
doc_class / role derivations, write accounting, and the HTTP-only contract.

No HTTP server and no database: the end-to-end path (real app, real Postgres, two
seed runs) is ``synthetic/rehearsal.py``. Skips cleanly when ``backend/synthetic/``
is absent.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

BACKEND = Path(__file__).resolve().parents[2]
SYNTHETIC = BACKEND / "synthetic"
if not (SYNTHETIC / "seed.py").is_file():
    pytest.skip("backend/synthetic/ is absent", allow_module_level=True)

from app.company_ingest.constants import DocClass  # noqa: E402
from synthetic import corpus_meta as cm  # noqa: E402
from synthetic import seed as sd  # noqa: E402
from synthetic.rehearsal_inner import FORBIDDEN_SEED_IMPORTS, seed_imports  # noqa: E402

pytestmark = pytest.mark.corpus

REGISTER_ROWS = {"obligation_id": 70, "event_id": 48, "rrs_id": 86}


@pytest.fixture(scope="module")
def plan() -> list[sd.DocPlan]:
    return sd.build_plan()


# ---------------------------------------------------------------- doc_class_for
@pytest.mark.parametrize("rpl,expected", [
    ("RPL-CS-PRO-004", "procedure"), ("RPL-DO-PLN-002", "plan"), ("RPL-MTR-PGM-001", "plan"),
    ("RPL-TAR-GRR-012", "tariff"), ("RPL-CMP-REG-001", "register"),
    ("RPL-REG-CAL-2025", "calendar"), ("RPL-LEG-RRS-001", "retention_schedule"),
])
def test_doc_class_for(rpl, expected):
    assert sd.doc_class_for(rpl) == expected


@pytest.mark.parametrize("rpl", ["RPL-XX-ZZZ-001", "RPL-CS", "PRO"])
def test_doc_class_for_rejects_unknown_type_codes(rpl):
    with pytest.raises(sd.SeedError, match="cannot derive doc_class"):
        sd.doc_class_for(rpl)


def test_every_type_code_maps_to_a_real_doc_class():
    values = {c.value for c in DocClass}
    assert set(sd.TYPE_DOC_CLASS.values()) <= values
    assert set(sd.REGISTER_DOC_CLASS.values()) <= values


# ----------------------------------------------------------------- roles_by_doc
def _person(pid: str, *roles: tuple[str, str]) -> cm.Person:
    return cm.Person(person_id=pid, name=pid, title=None, department=None, reports_to_id=None,
                     email=None, phone_ext=None, location=None,
                     document_roles=tuple(cm.DocumentRole(d, r) for d, r in roles),
                     oncall_roles=(), alternate_person_id=None)


def test_roles_by_doc_merges_people_per_document():
    got = sd.roles_by_doc([_person("P1", ("D1", "owner"), ("D2", "approver")),
                           _person("P2", ("D1", "reviewer"))])
    assert got == {"D1": {"owner": "P1", "reviewer": "P2"}, "D2": {"approver": "P1"}}


def test_roles_by_doc_rejects_two_holders_of_one_role():
    with pytest.raises(sd.SeedError, match="two owners|two owner"):
        sd.roles_by_doc([_person("P1", ("D1", "owner")), _person("P2", ("D1", "owner"))])


def test_roles_by_doc_tolerates_a_repeated_identical_assignment():
    got = sd.roles_by_doc([_person("P1", ("D1", "owner"), ("D1", "owner"))])
    assert got == {"D1": {"owner": "P1"}}


def test_roles_by_doc_on_the_real_directory_matches_the_register():
    roles = sd.roles_by_doc(cm.read_people())
    reg = {e.doc_id: e for e in cm.read_document_register()}
    for doc_id in cm.DEMO_DOC_IDS:
        e = reg[doc_id]
        want = {k: v for k, v in (("owner", e.owner_id), ("reviewer", e.reviewer_id),
                                  ("approver", e.approver_id)) if v}
        assert roles[doc_id] == want, doc_id


# ------------------------------------------------------------------- build_plan
def test_plan_has_15_documents_12_docx_and_3_registers(plan):
    assert len(plan) == 15
    assert sum(d.kind == "docx" for d in plan) == 12
    assert sum(d.kind == "csv" for d in plan) == 3
    assert len({d.doc_number for d in plan}) == 15
    assert {d.doc_number for d in plan if d.kind == "docx"} == set(cm.DEMO_DOC_IDS)


def test_each_register_follows_its_parent_and_inherits_its_metadata(plan):
    for i, d in enumerate(plan):
        if d.kind != "csv":
            continue
        parent = plan[i - 1]
        assert d.doc_number == f"{parent.doc_number}#register"
        assert d.parent_id == parent.doc_number and parent.kind == "docx"
        assert d.title == f"{parent.title} — Register"
        for attr in ("vertical", "law_as_of", "review_cycle", "next_review", "effective_date",
                     "approved_date", "roles", "policy_key"):
            assert getattr(d, attr) == getattr(parent, attr), (d.doc_number, attr)


def test_register_specs_declare_id_and_citation_columns(plan):
    regs = {d.register_spec["id_column"]: d for d in plan if d.kind == "csv"}
    assert set(regs) == set(REGISTER_ROWS)
    assert regs["rrs_id"].register_spec["citation_columns"] == ["retention_basis"]
    assert regs["obligation_id"].register_spec["citation_columns"] == ["citation"]
    assert regs["event_id"].register_spec["citation_columns"] == ["citation"]
    assert {d.doc_class for d in regs.values()} == {"register", "calendar", "retention_schedule"}
    for id_col, d in regs.items():
        assert d.path.is_file() and d.filename == d.path.name
        rows = d.path.read_text(encoding="utf-8-sig").strip().splitlines()
        assert len(rows) - 1 == REGISTER_ROWS[id_col], id_col


def test_docx_entries_come_from_the_md_sources_not_the_renders(plan):
    for d in plan:
        if d.kind == "docx":
            assert d.path.suffix == ".md" and d.path.is_file(), d.doc_number
            assert "render" not in d.path.parts
            assert d.filename == f"{d.doc_number}.docx"


def test_plan_metadata_is_fully_populated(plan):
    for d in plan:
        assert d.vertical in cm.CANONICAL_VERTICALS, d.doc_number
        assert d.doc_class in {c.value for c in DocClass}
        assert d.law_as_of and d.review_cycle and d.next_review and d.effective_date
        assert {"owner", "reviewer"} <= set(d.roles)


def test_policy_choice_and_signers(plan):
    by = {d.doc_number: d for d in plan}
    # Two-signature documents (no approver, org_chart.md).
    for doc in ("RPL-CS-PRO-007", "RPL-CS-PRO-011"):
        assert by[doc].policy_key == "two_signature"
        assert "approver" not in by[doc].roles
        assert by[doc].signers() == [by[doc].roles["owner"], by[doc].roles["reviewer"]]
    for d in plan:
        if "approver" in d.roles:
            assert d.policy_key == "default"
            assert d.signers() == [d.roles["reviewer"], d.roles["approver"]]


def test_plan_is_deterministic():
    a, b = sd.build_plan(), sd.build_plan()
    assert [(d.doc_number, d.path, d.roles, d.register_spec) for d in a] == \
           [(d.doc_number, d.path, d.roles, d.register_spec) for d in b]


# ------------------------------------------------------------- Api accounting
def _api(handler) -> tuple[sd.Api, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://t")
    return sd.Api(client, log=lambda _m: None), client


def test_api_counts_every_non_get_call_and_only_those():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200 if req.method == "GET" else 201, json={"ok": True})

    async def go():
        api, client = _api(handler)
        async with client:
            assert await api.get("/a") == {"ok": True}
            await api.call("POST", "/b")
            await api.call("PATCH", "/c", ok=(201,))
            await api.get("/d")
        return api

    api = asyncio.run(go())
    assert api.writes == 2
    assert api.write_log == ["POST /b -> 201", "PATCH /c -> 201"]


def test_api_raises_on_an_unexpected_status_but_still_counts_the_write():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"status": "duplicate"})

    async def go():
        api, client = _api(handler)
        async with client:
            with pytest.raises(sd.SeedError, match="409"):
                await api.call("POST", "/x")
            res = await api.call("POST", "/x", ok=(202, 409))
            assert res.status_code == 409
        return api

    assert asyncio.run(go()).writes == 2


# ------------------------------------------------------------ HTTP-only contract
def test_seed_imports_nothing_that_can_write_the_database_directly():
    names = seed_imports()
    assert "httpx" in names and "synthetic" in names
    assert not names & set(FORBIDDEN_SEED_IMPORTS), names & set(FORBIDDEN_SEED_IMPORTS)


def test_seed_imports_detects_a_direct_app_import(tmp_path):
    fake = tmp_path / "seed.py"
    fake.write_text("import httpx\nfrom app.db import AsyncSessionLocal\nimport sqlalchemy.orm\n")
    assert seed_imports(fake) & set(FORBIDDEN_SEED_IMPORTS) == {"app", "sqlalchemy"}
