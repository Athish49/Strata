"""Org + approval write endpoints against a scripted fake session (no DB).

The v2 migration (f7b2c91d4a08) is NOT applied anywhere, so these tables exist in
no database. Every test here drives app.api.company.org through a fake session that
records the SQL it is handed and replays canned rows, which is also the only way to
assert the dual-write and the policy-selection ORDER BY without a live Postgres.

Idiom copied from tests/engine/test_api_routes.py:56-63.
"""
import re
import uuid

import httpx
import pytest

from app.api.company import org
from app.db import get_db
from app.main import app

PID = "P18"
DOC = "RPL-CS-PRO-007"
VER = str(uuid.uuid4())
POL = uuid.uuid4()
REQ = uuid.uuid4()

PERSON_ROW = [{"person_id": PID}]
DOC_ROW = [{"doc_id": DOC, "doc_class": "procedure", "vertical": "Compliance & Legal",
            "owner_id": PID, "reviewer_id": "P14", "approver_id": None,
            "current_version_id": uuid.UUID(VER)}]
VERSION_ROW = [{"version_id": uuid.UUID(VER), "doc_id": DOC, "version_no": 3, "status": "draft"}]


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
        self.sql: list[tuple[str, dict]] = []
        self.committed = 0
        self.rolled_back = 0
        self.raise_on: list[tuple[str, Exception]] = []

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.sql.append((sql, params or {}))
        for key, exc in self.raise_on:
            if key in sql:
                raise exc
        for key, rows in self.rules:
            if key in sql:
                return _Res(rows(params) if callable(rows) else rows)
        return _Res([])

    async def commit(self):
        self.committed += 1

    async def rollback(self):
        self.rolled_back += 1

    def find(self, needle):
        return [(s, p) for s, p in self.sql if needle in s]


def client_for(rules):
    sess = FakeSession(rules)

    async def _dep():
        yield sess

    app.dependency_overrides[get_db] = _dep
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    return c, sess


@pytest.fixture(autouse=True)
def _clear():
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _no_real_promotion(monkeypatch):
    """The fake session cannot run promote_version (task 5.6), and it must never reach
    a real Qdrant. Tests that care about promotion install a recorder on top of this."""
    async def _noop(db, *a, **kw):
        return None

    monkeypatch.setattr(org, "promote_version", _noop)


def person_rule(found=True):
    return ("FROM company.people WHERE company_id = :c AND person_id = :p",
            PERSON_ROW if found else [])


# ------------------------------------------------- acceptance: existing shapes
async def test_legacy_read_shapes_unchanged():
    """GET /company/people and GET /engine/people keep their exact response shapes
    after the org router is mounted (routes.py is untouched)."""
    c, _ = client_for([
        ("SELECT person_id, name, title, department, reports_to_id FROM company.people",
         [{"person_id": PID, "name": "A B", "title": "Dir", "department": "CS",
           "reports_to_id": "P01"}]),
        ("SELECT person_id, name, title FROM company.people",
         [{"person_id": PID, "name": "A B", "title": "Dir"}]),
    ])
    async with c:
        comp = (await c.get("/company/people")).json()
        eng = (await c.get("/engine/people")).json()
    assert comp == [{"person_id": PID, "name": "A B", "title": "Dir",
                     "department": "CS", "reports_to_id": "P01"}]
    assert eng == [{"person_id": PID, "name": "A B", "title": "Dir"}]


async def test_profile_fully_populated_from_db_with_no_corpus_files(monkeypatch):
    """GET /company/profile is populated entirely from companies + company_attributes:
    with no corpus files involved at all, name/state/customers/type still come back."""
    c, _ = client_for([
        ("FROM company.companies", [{"name": "Riverplain Energy"}]),
        ("FROM company.company_attributes", [
            {"key": "customer_count_total", "value_text": None, "value_num": 407491,
             "value_bool": None, "source": "api:P18"},
            {"key": "jurisdiction", "value_text": "IN", "value_num": None,
             "value_bool": None, "source": "api:P18"},
            {"key": "ownership", "value_text": "investor_owned", "value_num": None,
             "value_bool": None, "source": "api:P18"},
        ]),
    ])
    async with c:
        body = (await c.get("/company/profile")).json()
    assert body["name"] == "Riverplain Energy"
    assert body["state"] == "Indiana"
    assert body["customers"] == 407491
    assert body["type"] == "Investor-owned utility"
    assert len(body["attributes"]) == 3


async def test_profile_regulator_and_utility_type_come_from_attributes(monkeypatch):
    c, _ = client_for([
        ("FROM company.companies", [{"name": "Riverplain Energy"}]),
        ("FROM company.company_attributes", [
            {"key": "ownership", "value_text": "investor_owned", "value_num": None,
             "value_bool": None, "source": "api:P18"},
            {"key": "regulator", "value_text": "IURC", "value_num": None,
             "value_bool": None, "source": "api:P18"},
            {"key": "utility_type", "value_text": "electric", "value_num": None,
             "value_bool": None, "source": "api:P18"},
        ]),
    ])
    async with c:
        body = (await c.get("/company/profile")).json()
    assert body["regulator"] == "IURC"
    assert body["type"] == "Investor-owned electric utility"


async def test_profile_prefers_the_display_utility_type_without_touching_the_applicability_one():
    """`utility_type` ("electric") is an applicability attribute; `business_utility_type`
    ("electric_distribution") is how the company describes itself. The profile page shows the
    latter when present, and the former remains untouched in the attribute list."""
    attrs = [
        {"key": "ownership", "value_text": "investor_owned", "value_num": None, "value_bool": None, "source": "api:P18"},
        {"key": "utility_type", "value_text": "electric", "value_num": None, "value_bool": None, "source": "api:P18"},
        {"key": "business_utility_type", "value_text": "electric_distribution", "value_num": None,
         "value_bool": None, "source": "api:P18"},
    ]
    c, _ = client_for([("FROM company.companies", [{"name": "Riverplain Energy"}]),
                       ("FROM company.company_attributes", attrs)])
    async with c:
        body = (await c.get("/company/profile")).json()
    assert body["type"] == "Investor-owned electric distribution utility"
    by_key = {a["key"]: a["value"] for a in body["attributes"]}
    assert by_key["utility_type"] == "electric", "the applicability value must be unchanged"


# ------------------------------------------- acceptance: unknown acting person
@pytest.mark.parametrize("method,path,body", [
    ("post", "/company/departments", {"department_id": "D1", "name": "Ops"}),
    ("post", "/company/people", {"person_id": "P99", "name": "New"}),
    ("patch", "/company/profile", {"name": "X"}),
    ("put", "/company/attributes/jurisdiction", {"value": "IN"}),
    ("post", f"/company/documents/{DOC}/roles", {"person_id": PID, "role": "owner"}),
    ("post", "/company/approval-policies", {"name": "P"}),
])
async def test_unknown_acting_person_rejected(method, path, body):
    c, sess = client_for([person_rule(found=False)])
    async with c:
        res = await getattr(c, method)(path, json={**body, "acting_person_id": "GHOST"})
    assert res.status_code == 404
    assert "acting person not found: GHOST" in res.json()["detail"]
    assert sess.committed == 0


async def test_acting_person_id_is_required():
    c, _ = client_for([person_rule()])
    async with c:
        res = await c.post("/company/departments", json={"department_id": "D1", "name": "Ops"})
    assert res.status_code == 422


# ------------------------------------------------------------ departments CRUD
async def test_department_crud():
    c, sess = client_for([
        person_rule(),
        ("UPDATE company.departments", [{"department_id": "D1", "name": "Ops2",
                                         "parent_department_id": None}]),
        ("DELETE FROM company.departments", [{"department_id": "D1"}]),
        ("SELECT department_id, name, parent_department_id FROM company.departments",
         [{"department_id": "D1", "name": "Ops", "parent_department_id": None}]),
    ])
    async with c:
        created = await c.post("/company/departments",
                               json={"department_id": "D1", "name": "Ops",
                                     "acting_person_id": PID})
        listed = await c.get("/company/departments")
        patched = await c.patch("/company/departments/D1",
                                json={"name": "Ops2", "acting_person_id": PID})
        deleted = await c.delete(f"/company/departments/D1?acting_person_id={PID}")
    assert created.status_code == 201 and created.json()["department_id"] == "D1"
    assert listed.json() == [{"department_id": "D1", "name": "Ops", "parent_department_id": None}]
    assert patched.json()["name"] == "Ops2"
    assert deleted.json() == {"deleted": "D1"}
    # delete detaches members first so people.department_id never dangles
    assert sess.find("UPDATE company.people SET department_id = NULL")


async def test_department_patch_clear_parent_and_empty_patch():
    c, sess = client_for([
        person_rule(),
        ("UPDATE company.departments", [{"department_id": "D1", "name": "Ops",
                                         "parent_department_id": None}]),
    ])
    async with c:
        cleared = await c.patch("/company/departments/D1",
                                json={"clear_parent": True, "acting_person_id": PID})
        empty = await c.patch("/company/departments/D1", json={"acting_person_id": PID})
    assert cleared.status_code == 200
    assert "parent_department_id = NULL" in sess.find("UPDATE company.departments")[0][0]
    assert empty.status_code == 400


async def test_department_patch_404():
    c, _ = client_for([person_rule()])
    async with c:
        res = await c.patch("/company/departments/NOPE",
                            json={"name": "x", "acting_person_id": PID})
    assert res.status_code == 404


# ---------------------------------------------------------------- people CRUD
async def test_create_person_writes_new_v2_columns():
    c, sess = client_for([person_rule()])
    async with c:
        res = await c.post("/company/people", json={
            "person_id": "P99", "name": "New Hire", "title": "Analyst",
            "department": "Ops", "department_id": "D1", "reports_to_id": PID,
            "email": "n@x.test", "is_active": True, "acting_person_id": PID})
    assert res.status_code == 201
    assert res.json()["department_id"] == "D1" and res.json()["is_active"] is True
    sql, params = sess.find("INSERT INTO company.people")[0]
    assert "department_id" in sql and "is_active" in sql
    assert params["did"] == "D1" and params["act"] is True


async def test_patch_person_and_soft_delete():
    c, sess = client_for([
        person_rule(),
        ("UPDATE company.people SET", [{"person_id": "P99", "name": "n", "title": "t",
                                        "department": "d", "department_id": "D2",
                                        "reports_to_id": None, "email": None,
                                        "is_active": True}]),
    ])
    async with c:
        patched = await c.patch("/company/people/P99",
                                json={"department_id": "D2", "acting_person_id": PID})
        deleted = await c.delete(f"/company/people/P99?acting_person_id={PID}")
    assert patched.json()["department_id"] == "D2"
    assert deleted.json() == {"person_id": "P99", "is_active": False}
    # soft delete only: history (approval_steps.assignee_person_id) must stay resolvable
    assert sess.find("UPDATE company.people SET is_active = false")
    assert not sess.find("DELETE FROM company.people")


async def test_patch_person_is_active_false_is_not_swallowed():
    """is_active=False must reach SQL: a naive `if val` check would drop it."""
    c, sess = client_for([
        person_rule(),
        ("UPDATE company.people SET", [{"person_id": "P99", "name": "n", "title": None,
                                        "department": None, "department_id": None,
                                        "reports_to_id": None, "email": None,
                                        "is_active": False}]),
    ])
    async with c:
        res = await c.patch("/company/people/P99",
                            json={"is_active": False, "acting_person_id": PID})
    assert res.status_code == 200
    sql, params = sess.find("UPDATE company.people SET")[0]
    assert "is_active = :v_is_active" in sql and params["v_is_active"] is False


async def test_org_people_view_exposes_new_columns():
    c, _ = client_for([
        ("alternate_person_id, is_active",
         [{"person_id": PID, "name": "A", "title": "T", "department": "CS",
           "department_id": "D1", "reports_to_id": None, "email": None,
           "alternate_person_id": "P20", "is_active": True}]),
    ])
    async with c:
        res = await c.get("/company/org/people?include_inactive=false")
    assert res.json()[0]["is_active"] is True
    assert res.json()[0]["alternate_person_id"] == "P20"


async def test_create_and_patch_person_write_alternate_person_id():
    """company.people.alternate_person_id existed with no writer, so a seeder's value
    was silently dropped (pydantic ignores unknown keys). Pinned for create + patch."""
    c, sess = client_for([
        person_rule(),
        ("UPDATE company.people SET", [{"person_id": "P99", "name": "N", "title": None,
                                        "department": None, "department_id": None,
                                        "reports_to_id": None, "email": None,
                                        "alternate_person_id": "P02", "is_active": True}]),
    ])
    async with c:
        created = await c.post("/company/people", json={
            "person_id": "P99", "name": "N", "alternate_person_id": "P01",
            "acting_person_id": PID})
        patched = await c.patch("/company/people/P99", json={
            "alternate_person_id": "P02", "acting_person_id": PID})
    assert created.status_code == 201 and created.json()["alternate_person_id"] == "P01"
    sql, params = sess.find("INSERT INTO company.people")[0]
    assert "alternate_person_id" in sql and params["alt"] == "P01"
    assert patched.status_code == 200 and patched.json()["alternate_person_id"] == "P02"
    usql, uparams = sess.find("UPDATE company.people SET")[0]
    assert "alternate_person_id = :v_alternate_person_id" in usql
    assert uparams["v_alternate_person_id"] == "P02"


async def test_self_registration_is_not_a_bypass_when_people_exist():
    """Fake-session check of the bootstrap guard's ORDER: an actor registering
    themselves while the company already has people is a plain 404 (the count query
    reports 1), and nothing is inserted."""
    c, sess = client_for([
        ("SELECT count(*) AS n FROM company.people", [{"n": 1}]),
        person_rule(found=False),
    ])
    async with c:
        res = await c.post("/company/people", json={
            "person_id": "P77", "name": "Me", "acting_person_id": "P77"})
    assert res.status_code == 404
    assert not sess.find("INSERT INTO company.people")
    assert sess.committed == 0


# --------------------------------------------------- companies and attributes
async def test_patch_profile_upserts_company():
    c, sess = client_for([person_rule()])
    async with c:
        res = await c.patch("/company/profile",
                            json={"name": "Riverplain Energy", "acting_person_id": PID})
    assert res.json()["name"] == "Riverplain Energy"
    assert "ON CONFLICT (company_id)" in sess.find("INSERT INTO company.companies")[0][0]


@pytest.mark.parametrize("value,col", [
    (True, "vb"), (407491, "vn"), (1.5, "vn"), ("IN", "vt"),
])
async def test_attribute_value_routes_to_one_column(value, col):
    """Exactly one of value_bool/value_num/value_text is written, or
    routes.attribute_value reads back the wrong one (bool wins over num over text)."""
    c, sess = client_for([person_rule()])
    async with c:
        res = await c.put("/company/attributes/k",
                          json={"value": value, "acting_person_id": PID})
    assert res.status_code == 200
    _, params = sess.find("INSERT INTO company.company_attributes")[0]
    assert params[col] is not None
    assert [k for k in ("vb", "vn", "vt") if params[k] is not None] == [col]


async def test_attribute_default_source_records_actor_and_delete():
    c, sess = client_for([
        person_rule(),
        ("DELETE FROM company.company_attributes", [{"key": "k"}]),
    ])
    async with c:
        put = await c.put("/company/attributes/jurisdiction",
                          json={"value": "IN", "acting_person_id": PID})
        gone = await c.delete(f"/company/attributes/k?acting_person_id={PID}")
    assert put.json()["source"] == f"api:{PID}"
    assert gone.json() == {"deleted": "k"}


async def test_attribute_delete_404():
    c, _ = client_for([person_rule()])
    async with c:
        res = await c.delete(f"/company/attributes/nope?acting_person_id={PID}")
    assert res.status_code == 404


# ------------------------------------- acceptance: role dual-write to legacy
async def test_owner_assignment_sets_legacy_owner_id():
    c, sess = client_for([
        person_rule(),
        ("FROM company.company_documents WHERE company_id = :c AND doc_id = :d", DOC_ROW),
        ("FROM company.document_role_assignments", [{"person_id": "P42"}]),
    ])
    async with c:
        res = await c.post(f"/company/documents/{DOC}/roles",
                           json={"person_id": "P42", "role": "owner",
                                 "acting_person_id": PID})
    assert res.status_code == 201
    assert res.json()["legacy_column"] == "owner_id"
    assert res.json()["legacy_value"] == "P42"
    sql, params = sess.find("UPDATE company.company_documents SET owner_id")[0]
    assert params == {"p": "P42", "c": org._cid(), "d": DOC}
    assert sess.committed == 1


@pytest.mark.parametrize("role,col", [
    ("owner", "owner_id"), ("reviewer", "reviewer_id"), ("approver", "approver_id"),
])
async def test_each_role_dual_writes_its_own_legacy_column(role, col):
    c, sess = client_for([
        person_rule(),
        ("FROM company.company_documents WHERE company_id = :c AND doc_id = :d", DOC_ROW),
        ("FROM company.document_role_assignments", [{"person_id": "P42"}]),
    ])
    async with c:
        res = await c.post(f"/company/documents/{DOC}/roles",
                           json={"person_id": "P42", "role": role, "acting_person_id": PID})
    assert res.json()["legacy_column"] == col
    assert sess.find(f"UPDATE company.company_documents SET {col} = :p")


async def test_unassigning_last_holder_nulls_the_legacy_column():
    """No assignment left -> legacy column goes NULL, which is also how
    routes.build_document derives two_signature from a null approver_id."""
    c, sess = client_for([
        person_rule(),
        ("DELETE FROM company.document_role_assignments", [{"role": "approver"}]),
        ("SELECT person_id FROM company.document_role_assignments", []),
    ])
    async with c:
        res = await c.delete(
            f"/company/documents/{DOC}/roles/approver/P42?acting_person_id={PID}")
    assert res.json()["legacy_value"] is None
    _, params = sess.find("UPDATE company.company_documents SET approver_id")[0]
    assert params["p"] is None


async def test_role_assignment_rejects_unknown_person_and_document():
    c, _ = client_for([
        ("FROM company.people WHERE company_id = :c AND person_id = :p",
         lambda p: PERSON_ROW if p["p"] == PID else []),
        ("FROM company.company_documents WHERE company_id = :c AND doc_id = :d", DOC_ROW),
    ])
    async with c:
        bad_person = await c.post(f"/company/documents/{DOC}/roles",
                                  json={"person_id": "GHOST", "role": "owner",
                                        "acting_person_id": PID})
    assert bad_person.status_code == 404 and "person not found" in bad_person.json()["detail"]

    c2, _ = client_for([person_rule()])  # document lookup returns []
    async with c2:
        bad_doc = await c2.post("/company/documents/NOPE/roles",
                                json={"person_id": PID, "role": "owner",
                                      "acting_person_id": PID})
    assert bad_doc.status_code == 404 and bad_doc.json()["detail"] == "document not found"


async def test_role_must_be_one_of_three():
    c, _ = client_for([person_rule()])
    async with c:
        res = await c.post(f"/company/documents/{DOC}/roles",
                           json={"person_id": PID, "role": "admin", "acting_person_id": PID})
    assert res.status_code == 422


async def test_list_roles_joins_people():
    c, _ = client_for([
        ("FROM company.document_role_assignments ra",
         [{"doc_id": DOC, "person_id": PID, "role": "owner", "assigned_at": None,
           "name": "A B", "title": "Dir"}]),
    ])
    async with c:
        res = await c.get(f"/company/documents/{DOC}/roles")
    assert res.json() == [{"doc_id": DOC, "person_id": PID, "role": "owner",
                           "assigned_at": None, "name": "A B", "title": "Dir"}]


# ----------------------------------------------------- approval policies CRUD
async def test_create_policy_with_steps():
    c, sess = client_for([person_rule()])
    async with c:
        res = await c.post("/company/approval-policies", json={
            "name": "Procedure sign-off", "applies_to_doc_class": "procedure",
            "steps": [{"step_no": 2, "required_role": "approver"},
                      {"step_no": 1, "required_role": "reviewer"}],
            "acting_person_id": PID})
    body = res.json()
    assert res.status_code == 201
    assert uuid.UUID(body["policy_id"])
    assert [s["step_no"] for s in body["steps"]] == [1, 2]
    assert body["steps"][0]["min_approvals"] == 1
    assert len(sess.find("INSERT INTO company.approval_policy_steps")) == 2


async def test_min_approvals_above_one_rejected():
    """approval_steps is keyed (request_id, step_no): one signature per step. A
    policy claiming min_approvals=2 would approve on one signature, so refuse it."""
    c, sess = client_for([person_rule()])
    async with c:
        res = await c.post("/company/approval-policies", json={
            "name": "P", "steps": [{"step_no": 1, "required_role": "reviewer",
                                    "min_approvals": 2}],
            "acting_person_id": PID})
    assert res.status_code == 422
    assert sess.committed == 0


async def test_duplicate_step_no_rejected():
    c, _ = client_for([person_rule()])
    async with c:
        res = await c.post("/company/approval-policies", json={
            "name": "P", "steps": [{"step_no": 1, "required_role": "owner"},
                                   {"step_no": 1, "required_role": "approver"}],
            "acting_person_id": PID})
    assert res.status_code == 400 and res.json()["detail"] == "duplicate step_no"


POLICY_ROW = [{"policy_id": POL, "name": "P", "applies_to_vertical": None,
               "applies_to_doc_class": "procedure"}]
STEP_ROWS = [{"step_no": 1, "required_role": "reviewer", "min_approvals": 1},
             {"step_no": 2, "required_role": "approver", "min_approvals": 1}]


async def test_get_patch_put_steps_delete_policy():
    c, sess = client_for([
        person_rule(),
        ("FROM company.approval_policies WHERE company_id = :c AND policy_id", POLICY_ROW),
        ("FROM company.approval_policy_steps", STEP_ROWS),
        ("UPDATE company.approval_policies SET", POLICY_ROW),
    ])
    async with c:
        got = await c.get(f"/company/approval-policies/{POL}")
        patched = await c.patch(f"/company/approval-policies/{POL}",
                                json={"name": "P2", "clear_doc_class": True,
                                      "acting_person_id": PID})
        replaced = await c.put(f"/company/approval-policies/{POL}/steps",
                               json={"steps": [{"step_no": 1, "required_role": "owner"}],
                                     "acting_person_id": PID})
        deleted = await c.delete(f"/company/approval-policies/{POL}?acting_person_id={PID}")
    assert [s["step_no"] for s in got.json()["steps"]] == [1, 2]
    assert "applies_to_doc_class = NULL" in sess.find("UPDATE company.approval_policies SET")[0][0]
    assert patched.status_code == 200
    assert replaced.json()["steps"] == [{"step_no": 1, "required_role": "owner",
                                        "min_approvals": 1}]
    assert sess.find("DELETE FROM company.approval_policy_steps")
    assert deleted.json() == {"deleted": str(POL)}
    # historical requests stay readable
    assert sess.find("UPDATE company.approval_requests SET policy_id = NULL")


async def test_list_policies_groups_steps():
    c, _ = client_for([
        ("LEFT JOIN company.approval_policy_steps", [
            {"policy_id": POL, "name": "P", "applies_to_vertical": None,
             "applies_to_doc_class": "procedure", "step_no": 1,
             "required_role": "reviewer", "min_approvals": 1},
            {"policy_id": POL, "name": "P", "applies_to_vertical": None,
             "applies_to_doc_class": "procedure", "step_no": 2,
             "required_role": "approver", "min_approvals": 1},
        ]),
    ])
    async with c:
        res = await c.get("/company/approval-policies")
    assert len(res.json()) == 1
    assert [s["step_no"] for s in res.json()[0]["steps"]] == [1, 2]


async def test_bad_policy_uuid_is_404():
    c, _ = client_for([person_rule()])
    async with c:
        assert (await c.get("/company/approval-policies/not-a-uuid")).status_code == 404


# -------------------------------------------------------- policy selection
async def test_policy_selection_scores_doc_class_above_vertical():
    """(vertical, doc_class)=3 > (doc_class)=2 > (vertical)=1 > default=0, decided by
    the ORDER BY so one round trip picks the winner."""
    captured = {}

    class S(FakeSession):
        pass

    sess = S([("FROM company.approval_policies", POLICY_ROW)])
    picked = await org.select_policy(sess, "Compliance & Legal", "procedure")
    sql, params = sess.find("FROM company.approval_policies")[0]
    captured["sql"] = re.sub(r"\s+", " ", sql)
    assert picked["policy_id"] == POL
    assert params == {"c": org._cid(), "v": "Compliance & Legal", "k": "procedure"}
    assert "applies_to_doc_class IS NULL THEN 0 ELSE 2" in captured["sql"]
    assert "applies_to_vertical IS NULL THEN 0 ELSE 1" in captured["sql"]
    assert "DESC" in captured["sql"] and "LIMIT 1" in captured["sql"]
    # NULL columns are wildcards; non-NULL must match exactly
    assert "applies_to_vertical IS NULL OR applies_to_vertical = :v" in captured["sql"]


async def test_policy_selection_returns_none_when_nothing_matches():
    sess = FakeSession([])
    assert await org.select_policy(sess, "x", "y") is None


# ------------------------------------------------------- approval decisions
def _approval_rules(policy=POLICY_ROW, steps=STEP_ROWS, request_steps=None,
                    request_state="open", holder=PID):
    return [
        person_rule(),
        # the step write is guarded `AND decision IS NULL RETURNING step_no`
        ("UPDATE company.approval_steps SET decision", lambda p: [{"step_no": p.get("s")}]),
        ("FROM company.company_documents WHERE company_id = :c AND doc_id = :d", DOC_ROW),
        ("FROM company.document_versions WHERE company_id = :c AND doc_id = :d", VERSION_ROW),
        ("FROM company.approval_policies", policy),
        ("FROM company.approval_policy_steps", steps),
        ("SELECT person_id FROM company.document_role_assignments", [{"person_id": holder}]),
        ("FROM company.approval_requests r", [{
            "request_id": REQ, "company_id": org._cid(), "version_id": uuid.UUID(VER),
            "policy_id": POL, "state": request_state, "created_at": None,
            "completed_at": None, "doc_id": DOC, "version_no": 3, "status": "in_review"}]),
        ("FROM company.approval_steps WHERE request_id", request_steps or []),
    ]


async def test_open_approval_instantiates_steps_and_sets_in_review():
    c, sess = client_for(_approval_rules(request_steps=[
        {"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
         "decision": None, "decided_at": None, "note": None},
        {"step_no": 2, "required_role": "approver", "assignee_person_id": PID,
         "decision": None, "decided_at": None, "note": None}]))
    async with c:
        res = await c.post(f"/company/documents/{DOC}/versions/{VER}/approval",
                           json={"acting_person_id": PID})
    body = res.json()
    assert res.status_code == 201
    assert body["state"] == "open" and body["auto_approved"] is False
    assert len(body["steps"]) == 2 and body["steps"][0]["assignee_person_id"] == PID
    assert len(sess.find("INSERT INTO company.approval_steps")) == 2
    assert sess.find("SET status = 'in_review'")


async def test_open_approval_duplicate_is_409_from_the_partial_unique_index():
    """approval_requests_open_uq is the only honest gate: two concurrent opens both
    pass a SELECT, so the IntegrityError must become a 409."""
    from sqlalchemy.exc import IntegrityError

    c, sess = client_for(_approval_rules())
    sess.raise_on.append(("INSERT INTO company.approval_requests",
                          IntegrityError("approval_requests_open_uq", {}, Exception())))
    async with c:
        res = await c.post(f"/company/documents/{DOC}/versions/{VER}/approval",
                           json={"acting_person_id": PID})
    assert res.status_code == 409
    assert "open approval request already exists" in res.json()["detail"]
    assert sess.rolled_back == 1 and sess.committed == 0


def _record_promotions(monkeypatch):
    """Replace org.promote_version (task 5.6) with a recorder. The fake session cannot
    run the real promotion; tests/company_ingest/test_promote.py covers that against
    a real Postgres. Records the session, args and the commit count at call time."""
    calls = []

    async def fake_promote(db, company_id, doc_id, version_id, **kw):
        calls.append({"db": db, "company_id": company_id, "doc_id": doc_id,
                      "version_id": version_id, "committed_before": db.committed})

    monkeypatch.setattr(org, "promote_version", fake_promote)
    return calls


async def test_open_approval_auto_approves_and_warns_when_no_policy_matches(caplog, monkeypatch):
    promotions = _record_promotions(monkeypatch)
    c, sess = client_for(_approval_rules(policy=[], steps=[]))
    with caplog.at_level("WARNING"):
        async with c:
            res = await c.post(f"/company/documents/{DOC}/versions/{VER}/approval",
                               json={"acting_person_id": PID})
    body = res.json()
    assert body["auto_approved"] is True and body["state"] == "approved"
    assert body["policy_id"] is None and body["steps"] == []
    assert "auto-approved" in caplog.text and "no approval policy" in caplog.text
    _, params = sess.find("INSERT INTO company.approval_requests")[0]
    assert params["s"] == "approved"
    assert not sess.find("INSERT INTO company.approval_steps")
    # task 5.6: state moves to approved and promote_version runs in the SAME
    # transaction (same session, before the single commit); org.py itself no longer
    # writes any version status.
    assert sess.find("SET state = 'approved'")
    assert not sess.find("SET status = 'approved'")
    assert promotions == [{"db": sess, "company_id": org._cid(), "doc_id": DOC,
                           "version_id": VER, "committed_before": 0}]
    assert sess.committed == 1


async def test_open_approval_unknown_version_and_bad_uuid():
    rules = [r for r in _approval_rules()
             if r[0] != "FROM company.document_versions WHERE company_id = :c AND doc_id = :d"]
    c, _ = client_for(rules)
    async with c:
        missing = await c.post(f"/company/documents/{DOC}/versions/{VER}/approval",
                               json={"acting_person_id": PID})
        bad = await c.post(f"/company/documents/{DOC}/versions/not-a-uuid/approval",
                           json={"acting_person_id": PID})
    assert missing.status_code == 404 and missing.json()["detail"] == "version not found"
    assert bad.status_code == 404


async def test_decision_approve_last_step_approves_request(monkeypatch):
    promotions = _record_promotions(monkeypatch)
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
              "decision": "approved", "decided_at": None, "note": None},
             {"step_no": 2, "required_role": "approver", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None}]
    c, sess = client_for(_approval_rules(request_steps=steps))
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/steps/2/decision",
                           json={"decision": "approved", "note": " looks good ",
                                 "acting_person_id": PID})
    assert res.status_code == 200
    assert res.json()["request_state"] == "approved"
    _, params = sess.find("UPDATE company.approval_steps SET decision")[0]
    assert params["d"] == "approved" and params["n"] == "looks good"
    assert sess.find("SET state = 'approved', completed_at = now()")
    # task 5.6: the last approval promotes, in the same transaction as the decision
    assert promotions == [{"db": sess, "company_id": org._cid(), "doc_id": DOC,
                           "version_id": VER, "committed_before": 0}]
    assert sess.committed == 1
    assert not sess.find("SET status = 'approved'")


async def test_decision_promotion_failure_rolls_back_and_is_not_recorded(monkeypatch):
    """A failed promotion (Qdrant down -> retryable) surfaces as 503 and nothing is
    committed, so the step stays undecided and the signer can retry."""
    from app.company_ingest.promote import PromotionRetryableError

    async def failing(db, *a, **kw):
        await db.rollback()
        raise PromotionRetryableError("qdrant down")

    monkeypatch.setattr(org, "promote_version", failing)
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None}]
    c, sess = client_for(_approval_rules(request_steps=steps))
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                           json={"decision": "approved", "acting_person_id": PID})
    assert res.status_code == 503 and "qdrant down" in res.json()["detail"]
    assert sess.committed == 0 and sess.rolled_back == 1


async def test_decision_approve_non_final_step_keeps_request_open():
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None},
             {"step_no": 2, "required_role": "approver", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None}]
    c, sess = client_for(_approval_rules(request_steps=steps))
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                           json={"decision": "approved", "acting_person_id": PID})
    assert res.json()["request_state"] == "open"
    assert not sess.find("SET state = 'approved'")
    assert not sess.find("SET status = 'approved'")


async def test_rejection_rejects_request_and_never_promotes():
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None}]
    c, sess = client_for(_approval_rules(request_steps=steps))
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                           json={"decision": "rejected", "note": "no",
                                 "acting_person_id": PID})
    assert res.status_code == 200
    assert res.json()["request_state"] == "rejected"
    assert sess.find("SET state = 'rejected'")
    assert not sess.find("SET status = 'approved'")


async def test_concurrent_decision_on_same_step_is_409_and_never_finalizes():
    """The step UPDATE is guarded `AND decision IS NULL`: if a concurrent decision got
    there first the RETURNING is empty, so we must not reach _finalize_approved (which
    is where task 5.6 will promote the version)."""
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None}]
    rules = [("UPDATE company.approval_steps SET decision", [])] + _approval_rules(request_steps=steps)
    c, sess = client_for(rules)
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                           json={"decision": "approved", "acting_person_id": PID})
    assert res.status_code == 409 and res.json()["detail"] == "step already decided"
    assert not sess.find("SET state = 'approved'")
    assert sess.committed == 0 and sess.rolled_back == 1


async def test_inactive_person_cannot_sign_or_be_assigned_a_role():
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None}]
    inactive = ("FROM company.people WHERE company_id = :c AND person_id = :p",
                [{"person_id": PID, "is_active": False}])
    c, sess = client_for([inactive] + _approval_rules(request_steps=steps))
    async with c:
        sign = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                            json={"decision": "approved", "acting_person_id": PID})
        assign = await c.post(f"/company/documents/{DOC}/roles",
                              json={"person_id": PID, "role": "owner", "acting_person_id": PID})
    assert sign.status_code == 403 and "inactive" in sign.json()["detail"]
    assert assign.status_code == 403 and "inactive" in assign.json()["detail"]
    assert sess.committed == 0


async def test_decision_refused_when_version_row_is_missing():
    """Without the version row there is no doc_id, so role membership cannot be
    checked; the step must not be signable by anyone."""
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": None,
              "decision": None, "decided_at": None, "note": None}]
    orphan = ("FROM company.approval_requests r", [{
        "request_id": REQ, "company_id": org._cid(), "version_id": uuid.UUID(VER),
        "policy_id": POL, "state": "open", "created_at": None, "completed_at": None,
        "doc_id": None, "version_no": None, "status": None}])
    c, sess = client_for([orphan] + _approval_rules(request_steps=steps))
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                           json={"decision": "approved", "acting_person_id": PID})
    assert res.status_code == 409
    assert not sess.find("UPDATE company.approval_steps")


async def test_auto_approve_refused_while_a_request_is_open():
    """An 'approved' insert is invisible to the partial index, so the no-policy path
    must check for an open request itself."""
    open_req = ("FROM company.approval_requests WHERE company_id = :c AND version_id",
                [{"request_id": REQ}])
    c, sess = client_for([open_req] + _approval_rules(policy=[], steps=[]))
    async with c:
        res = await c.post(f"/company/documents/{DOC}/versions/{VER}/approval",
                           json={"acting_person_id": PID})
    assert res.status_code == 409
    assert not sess.find("INSERT INTO company.approval_requests")
    assert sess.committed == 0


async def test_other_integrity_errors_are_not_disguised_as_409():
    from sqlalchemy.exc import IntegrityError

    c, sess = client_for(_approval_rules())
    sess.raise_on.append(("INSERT INTO company.approval_requests",
                          IntegrityError("some_other_constraint", {}, Exception())))
    with pytest.raises(IntegrityError):
        async with c:
            await c.post(f"/company/documents/{DOC}/versions/{VER}/approval",
                         json={"acting_person_id": PID})


async def test_decision_requires_the_assigned_person():
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": "P14",
              "decision": None, "decided_at": None, "note": None}]
    c, sess = client_for(_approval_rules(request_steps=steps))
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                           json={"decision": "approved", "acting_person_id": PID})
    assert res.status_code == 403 and "assigned to P14" in res.json()["detail"]
    assert sess.committed == 0


async def test_unassigned_step_falls_back_to_role_membership():
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": None,
              "decision": None, "decided_at": None, "note": None}]
    # neither the assignment table nor the legacy column names P77 for 'reviewer'
    rules = [("SELECT 1 AS ok FROM company.company_documents", [])] + [
        r for r in _approval_rules(request_steps=steps)
        if r[0] != "SELECT person_id FROM company.document_role_assignments"]
    c, _ = client_for(rules)
    async with c:
        denied = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                              json={"decision": "approved", "acting_person_id": "P77"})
    assert denied.status_code == 403 and "does not hold role 'reviewer'" in denied.json()["detail"]

    c2, _ = client_for(_approval_rules(request_steps=steps) +
                       [("FROM company.document_role_assignments "
                         "WHERE company_id = :c AND doc_id = :d AND role = :r AND person_id = :p",
                         [{"ok": 1}])])
    async with c2:
        ok = await c2.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                           json={"decision": "approved", "acting_person_id": PID})
    assert ok.status_code == 200


async def test_decision_rejects_out_of_order_and_already_decided_steps():
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None},
             {"step_no": 2, "required_role": "approver", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None}]
    c, _ = client_for(_approval_rules(request_steps=steps))
    async with c:
        out_of_order = await c.post(f"/company/approval-requests/{REQ}/steps/2/decision",
                                    json={"decision": "approved", "acting_person_id": PID})
        missing = await c.post(f"/company/approval-requests/{REQ}/steps/9/decision",
                               json={"decision": "approved", "acting_person_id": PID})
    assert out_of_order.status_code == 409 and "earlier step(s) [1]" in out_of_order.json()["detail"]
    assert missing.status_code == 404

    decided = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
                "decision": "approved", "decided_at": None, "note": None}]
    c2, _ = client_for(_approval_rules(request_steps=decided))
    async with c2:
        again = await c2.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                              json={"decision": "approved", "acting_person_id": PID})
    assert again.status_code == 409 and again.json()["detail"] == "step already decided"


async def test_decision_on_closed_request_is_409():
    c, _ = client_for(_approval_rules(request_state="rejected"))
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                           json={"decision": "approved", "acting_person_id": PID})
    assert res.status_code == 409 and "is rejected, not open" in res.json()["detail"]


async def test_decision_literal_is_validated():
    c, _ = client_for(_approval_rules())
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                           json={"decision": "maybe", "acting_person_id": PID})
    assert res.status_code == 422


async def test_get_and_cancel_approval_request():
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None}]
    c, sess = client_for(_approval_rules(request_steps=steps))
    async with c:
        got = await c.get(f"/company/approval-requests/{REQ}")
        cancelled = await c.post(f"/company/approval-requests/{REQ}/cancel",
                                 json={"acting_person_id": PID})
        unknown = await c.get("/company/approval-requests/not-a-uuid")
    assert got.json()["request_id"] == str(REQ) and got.json()["doc_id"] == DOC
    assert cancelled.status_code == 200
    assert sess.find("SET state = 'cancelled'")
    assert unknown.status_code == 404


async def test_cancel_retires_the_version_and_clears_its_pending_hash():
    """Task 3.2 decision 1: cancelling retires the version (status 'retired',
    pending_content_hash NULL) in the same transaction as the cancel, and never a
    live version. The real-Postgres version is in test_versions_jobs.py."""
    c, sess = client_for(_approval_rules())
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/cancel",
                           json={"acting_person_id": PID})
    assert res.status_code == 200
    retire = sess.find("SET status = 'retired', pending_content_hash = NULL")
    assert len(retire) == 1
    sql, params = retire[0]
    assert "NOT is_current" in sql and "status IN ('in_review', 'draft')" in sql
    assert params["v"] == VER
    cancel_at = next(i for i, (s, _) in enumerate(sess.sql) if "SET state = 'cancelled'" in s)
    retire_at = next(i for i, (s, _) in enumerate(sess.sql) if "SET status = 'retired'" in s)
    assert cancel_at < retire_at and sess.committed == 1


async def test_cancel_of_a_closed_request_retires_nothing():
    c, sess = client_for(_approval_rules(request_state="approved"))
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/cancel",
                           json={"acting_person_id": PID})
    assert res.status_code == 409
    assert not sess.find("SET status = 'retired'") and sess.committed == 0


@pytest.mark.parametrize("method,path,body", [
    ("post", f"/company/approval-requests/{REQ}/steps/1/decision", {"decision": "approved"}),
    ("post", f"/company/approval-requests/{REQ}/cancel", {}),
    ("post", f"/company/documents/{DOC}/versions/{VER}/approval", {}),
])
async def test_unknown_acting_person_rejected_on_approval_paths(method, path, body):
    rules = [person_rule(found=False)] + _approval_rules(request_steps=[
        {"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
         "decision": None, "decided_at": None, "note": None}])
    c, sess = client_for(rules)
    async with c:
        res = await getattr(c, method)(path, json={**body, "acting_person_id": "GHOST"})
    assert res.status_code == 404
    assert "acting person not found: GHOST" in res.json()["detail"]
    assert sess.committed == 0
    assert not sess.find("UPDATE company.approval_steps")
    assert not sess.find("UPDATE company.approval_requests")


@pytest.mark.parametrize("job_state,hint", [("running", "wait for the ingest job"),
                                            ("queued", "wait for the ingest job"),
                                            ("failed", "retry the ingest job")])
async def test_approval_refused_409_until_ingest_job_succeeded(monkeypatch, job_state, hint):
    promotions = _record_promotions(monkeypatch)
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None}]
    rules = [("FROM company.ingest_jobs", [{"job_id": uuid.UUID(int=7), "state": job_state}])]
    c, sess = client_for(rules + _approval_rules(request_steps=steps))
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                           json={"decision": "approved", "acting_person_id": PID})
    assert res.status_code == 409
    assert f"'{job_state}', not 'succeeded'" in res.json()["detail"]
    assert hint in res.json()["detail"]
    assert not sess.find("UPDATE company.approval_steps") and sess.committed == 0
    assert promotions == []


async def test_approval_proceeds_when_ingest_job_succeeded(monkeypatch):
    promotions = _record_promotions(monkeypatch)
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None}]
    rules = [("FROM company.ingest_jobs", [{"job_id": uuid.UUID(int=7), "state": "succeeded"}])]
    c, _ = client_for(rules + _approval_rules(request_steps=steps))
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                           json={"decision": "approved", "acting_person_id": PID})
    assert res.status_code == 200 and res.json()["request_state"] == "approved"
    assert len(promotions) == 1


async def test_rejection_is_never_blocked_by_ingest_and_never_reaches_qdrant(monkeypatch):
    """A rejection leaves the version in_review / not current: no promotion, no version
    status write, and no Qdrant client is ever built."""
    from app.company_ingest.index import upsert as upsert_module

    def _no_qdrant():
        raise AssertionError("rejection tried to reach Qdrant")

    monkeypatch.setattr(upsert_module, "_make_client", _no_qdrant)
    promotions = _record_promotions(monkeypatch)
    steps = [{"step_no": 1, "required_role": "reviewer", "assignee_person_id": PID,
              "decision": None, "decided_at": None, "note": None}]
    rules = [("FROM company.ingest_jobs", [{"job_id": uuid.UUID(int=7), "state": "running"}])]
    c, sess = client_for(rules + _approval_rules(request_steps=steps))
    async with c:
        res = await c.post(f"/company/approval-requests/{REQ}/steps/1/decision",
                           json={"decision": "rejected", "acting_person_id": PID})
    assert res.status_code == 200 and res.json()["request_state"] == "rejected"
    assert promotions == []
    assert not sess.find("UPDATE company.document_versions")
    assert not sess.find("FROM company.ingest_jobs")


async def test_list_document_approval_requests():
    c, _ = client_for([
        ("JOIN company.document_versions v ON v.version_id = r.version_id", [{
            "request_id": REQ, "version_id": uuid.UUID(VER), "policy_id": POL,
            "state": "approved", "created_at": None, "completed_at": None,
            "doc_id": DOC, "version_no": 3, "status": "approved"}]),
    ])
    async with c:
        res = await c.get(f"/company/documents/{DOC}/approval-requests")
    assert res.json()[0]["state"] == "approved"
    assert res.json()[0]["policy_id"] == str(POL)


# ------------------------------------------------------------ route integrity
async def test_org_router_does_not_shadow_the_read_routes():
    paths = {(r.path, tuple(sorted(r.methods))) for r in app.routes if hasattr(r, "methods")}
    assert ("/company/people", ("GET",)) in paths
    assert ("/company/people", ("POST",)) in paths
    assert ("/company/profile", ("GET",)) in paths
    assert ("/company/profile", ("PATCH",)) in paths
    assert ("/company/documents/{doc_id}", ("GET",)) in paths
    assert ("/company/documents/{doc_id}/roles", ("POST",)) in paths
