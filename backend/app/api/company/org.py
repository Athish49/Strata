"""Org and approval write endpoints (TDD.md 1.5, 7.3, 7.5; architecture.md 9).

Replaces the synthetic `_global/company_profile.yaml` + `_global/people_directory.csv`
as the source of `company.companies`, `company.company_attributes` and
`company.people`, and adds the document-control tables introduced by migration
f7b2c91d4a08: departments, document_role_assignments, approval_policies(+steps),
approval_requests(+steps).

**No authentication, by design.** There is no auth anywhere in this app and none
is added here. Every write instead carries an explicit `acting_person_id`, which
is validated against `company.people` (same idiom as
`app/api/engine/routes_reviews.py`) and recorded on approval records. That is what
makes the authorization hierarchy demonstrable without accounts.

`company_id` is always the single-tenant `engine_settings.ENGINE_COMPANY_ID`.

This module deliberately does NOT import or edit `app/api/company/routes.py`; the
read endpoints there keep their response shapes.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.company_ingest.promote import PromotionError, promote_version
from app.db import get_db
from app.engine.config import engine_settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/company", tags=["company-org"])

Role = Literal["owner", "reviewer", "approver"]

# role -> legacy flat column on company.company_documents. These three columns are
# retained and dual-written because app/engine/ledger.py (_ROUTE_SQL) and
# app/engine/export.py read them; dropping the dual-write silently breaks routing
# and export.
_LEGACY_COL = {"owner": "owner_id", "reviewer": "reviewer_id", "approver": "approver_id"}


def _cid() -> str:
    return engine_settings.ENGINE_COMPANY_ID


def _iso(v: Any) -> Optional[str]:
    return v.isoformat() if isinstance(v, datetime) else (v.isoformat() if hasattr(v, "isoformat") else None)


# --------------------------------------------------------------------- bodies
class _Acting(BaseModel):
    acting_person_id: str = Field(min_length=1)


class DepartmentIn(_Acting):
    department_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    parent_department_id: Optional[str] = None


class DepartmentPatch(_Acting):
    name: Optional[str] = None
    parent_department_id: Optional[str] = None
    clear_parent: bool = False


class PersonIn(_Acting):
    person_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    title: Optional[str] = None
    department: Optional[str] = None
    department_id: Optional[str] = None
    reports_to_id: Optional[str] = None
    email: Optional[str] = None
    #: Who covers for this person (company.people.alternate_person_id; existed since
    #: c3d4e5f6a7b8 but had no writer, so the seeder's value was silently dropped).
    alternate_person_id: Optional[str] = None
    is_active: bool = True


class PersonPatch(_Acting):
    name: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    department_id: Optional[str] = None
    reports_to_id: Optional[str] = None
    email: Optional[str] = None
    alternate_person_id: Optional[str] = None
    is_active: Optional[bool] = None


class AttributeIn(_Acting):
    value: Union[bool, int, float, str]
    source: Optional[str] = None


class CompanyPatch(_Acting):
    name: str = Field(min_length=1)


class RoleAssignmentIn(_Acting):
    person_id: str = Field(min_length=1)
    role: Role


class PolicyStepIn(BaseModel):
    step_no: int = Field(ge=1)
    required_role: Role
    # Capped at 1 on purpose: approval_steps is keyed (request_id, step_no), so a
    # step holds exactly one signature. Accepting min_approvals=3 would store a
    # policy that then approves on a single signature -- a silent lie. N-of-M
    # signing needs a per-signature table (see TDD 1.5 gaps).
    min_approvals: int = Field(default=1, ge=1, le=1)


class PolicyIn(_Acting):
    name: str = Field(min_length=1)
    applies_to_vertical: Optional[str] = None
    applies_to_doc_class: Optional[str] = None
    steps: list[PolicyStepIn] = Field(default_factory=list)


class PolicyPatch(_Acting):
    name: Optional[str] = None
    applies_to_vertical: Optional[str] = None
    applies_to_doc_class: Optional[str] = None
    clear_vertical: bool = False
    clear_doc_class: bool = False


class StepsIn(_Acting):
    steps: list[PolicyStepIn]


class DecisionIn(_Acting):
    decision: Literal["approved", "rejected"]
    note: Optional[str] = None


class OpenApprovalIn(_Acting):
    policy_id: Optional[str] = None


# -------------------------------------------------------------------- helpers
async def _require_person(db: AsyncSession, person_id: str, *, what: str = "acting person",
                          active_only: bool = False) -> None:
    """Mirror of routes_reviews.create_review's person check: an unknown id is rejected.

    `active_only` additionally refuses a soft-deleted person (is_active = false):
    a leaver must not sign an approval step or be given a document role.
    """
    rows = (await db.execute(
        text("SELECT person_id, is_active FROM company.people WHERE company_id = :c AND person_id = :p"),
        {"c": _cid(), "p": person_id},
    )).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"{what} not found: {person_id}")
    if active_only and rows[0].get("is_active", True) is False:
        raise HTTPException(status_code=403, detail=f"{what} is inactive: {person_id}")


async def _require_document(db: AsyncSession, doc_id: str) -> dict:
    rows = (await db.execute(
        text("SELECT doc_id, doc_class, vertical, owner_id, reviewer_id, approver_id, current_version_id "
             "FROM company.company_documents WHERE company_id = :c AND doc_id = :d"),
        {"c": _cid(), "d": doc_id},
    )).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail="document not found")
    return dict(rows[0])


def _as_uuid(value: str, detail: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=404, detail=detail)


async def _sync_legacy_role_column(db: AsyncSession, doc_id: str, role: str) -> Optional[str]:
    """Dual-write: project document_role_assignments onto the flat legacy column.

    REQUIRED, not cosmetic. `app/engine/ledger.py` routes findings from
    company_documents.owner_id/reviewer_id/approver_id and `app/engine/export.py`
    exports them. The new table is many-to-one per role, the legacy column holds
    one id, so the most recently assigned person wins (ties broken by person_id).
    No assignment left for the role -> the column goes NULL, which is also how
    routes.build_document derives `two_signature` from a null approver_id.
    """
    col = _LEGACY_COL[role]
    rows = (await db.execute(
        text("SELECT person_id FROM company.document_role_assignments "
             "WHERE company_id = :c AND doc_id = :d AND role = :r "
             "ORDER BY assigned_at DESC, person_id LIMIT 1"),
        {"c": _cid(), "d": doc_id, "r": role},
    )).mappings().all()
    winner = rows[0]["person_id"] if rows else None
    await db.execute(
        text(f"UPDATE company.company_documents SET {col} = :p "
             "WHERE company_id = :c AND doc_id = :d"),
        {"p": winner, "c": _cid(), "d": doc_id},
    )
    return winner


async def select_policy(db: AsyncSession, vertical: Optional[str], doc_class: Optional[str]) -> Optional[dict]:
    """Most specific match wins: (vertical, doc_class) -> (doc_class) -> (vertical) -> default.

    Scored in SQL so one round trip decides it: doc_class contributes 2, vertical 1,
    so both=3 > doc_class=2 > vertical=1 > default(both NULL)=0. A policy column that
    is NULL matches any document; a non-NULL column must match exactly, and a
    document with no vertical/doc_class therefore only matches the NULL side.
    Returns None when nothing matches at all (caller auto-approves and warns).
    """
    rows = (await db.execute(text("""
        SELECT policy_id, name, applies_to_vertical, applies_to_doc_class
        FROM company.approval_policies
        WHERE company_id = :c
          AND (applies_to_vertical  IS NULL OR applies_to_vertical  = :v)
          AND (applies_to_doc_class IS NULL OR applies_to_doc_class = :k)
        ORDER BY (CASE WHEN applies_to_doc_class IS NULL THEN 0 ELSE 2 END)
               + (CASE WHEN applies_to_vertical  IS NULL THEN 0 ELSE 1 END) DESC,
                 name
        LIMIT 1
    """), {"c": _cid(), "v": vertical, "k": doc_class})).mappings().all()
    return dict(rows[0]) if rows else None


async def _policy_steps(db: AsyncSession, policy_id: str) -> list[dict]:
    rows = (await db.execute(
        text("SELECT step_no, required_role, min_approvals FROM company.approval_policy_steps "
             "WHERE policy_id = CAST(:p AS uuid) ORDER BY step_no"),
        {"p": policy_id},
    )).mappings().all()
    return [dict(r) for r in rows]


async def _role_holder(db: AsyncSession, doc_id: str, role: str, legacy: Optional[str]) -> Optional[str]:
    """Who should sign a step requiring `role`: the assignment table, else the legacy column."""
    rows = (await db.execute(
        text("SELECT person_id FROM company.document_role_assignments "
             "WHERE company_id = :c AND doc_id = :d AND role = :r "
             "ORDER BY assigned_at DESC, person_id LIMIT 1"),
        {"c": _cid(), "d": doc_id, "r": role},
    )).mappings().all()
    return rows[0]["person_id"] if rows else legacy


async def _holds_role(db: AsyncSession, doc_id: str, role: str, person_id: str) -> bool:
    rows = (await db.execute(
        text("SELECT 1 AS ok FROM company.document_role_assignments "
             "WHERE company_id = :c AND doc_id = :d AND role = :r AND person_id = :p"),
        {"c": _cid(), "d": doc_id, "r": role, "p": person_id},
    )).mappings().all()
    if rows:
        return True
    col = _LEGACY_COL[role]
    rows = (await db.execute(
        text(f"SELECT 1 AS ok FROM company.company_documents "
             f"WHERE company_id = :c AND doc_id = :d AND {col} = :p"),
        {"c": _cid(), "d": doc_id, "p": person_id},
    )).mappings().all()
    return bool(rows)


# ---------------------------------------------------------------- departments
@router.get("/departments")
async def list_departments(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        text("SELECT department_id, name, parent_department_id FROM company.departments "
             "WHERE company_id = :c ORDER BY department_id"), {"c": _cid()})).mappings().all()
    return [dict(r) for r in rows]


@router.post("/departments", status_code=201)
async def create_department(body: DepartmentIn, db: AsyncSession = Depends(get_db)):
    await _require_person(db, body.acting_person_id)
    try:
        await db.execute(text(
            "INSERT INTO company.departments (company_id, department_id, name, parent_department_id) "
            "VALUES (:c, :d, :n, :p)"),
            {"c": _cid(), "d": body.department_id, "n": body.name, "p": body.parent_department_id})
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="department already exists")
    return {"department_id": body.department_id, "name": body.name,
            "parent_department_id": body.parent_department_id}


@router.patch("/departments/{department_id}")
async def update_department(department_id: str, body: DepartmentPatch, db: AsyncSession = Depends(get_db)):
    await _require_person(db, body.acting_person_id)
    sets, params = [], {"c": _cid(), "d": department_id}
    if body.name is not None:
        sets.append("name = :n")
        params["n"] = body.name
    if body.clear_parent:
        sets.append("parent_department_id = NULL")
    elif body.parent_department_id is not None:
        sets.append("parent_department_id = :pp")
        params["pp"] = body.parent_department_id
    if not sets:
        raise HTTPException(status_code=400, detail="no fields to update")
    res = await db.execute(text(
        f"UPDATE company.departments SET {', '.join(sets)} "
        "WHERE company_id = :c AND department_id = :d "
        "RETURNING department_id, name, parent_department_id"), params)
    rows = res.mappings().all()
    if not rows:
        await db.rollback()
        raise HTTPException(status_code=404, detail="department not found")
    await db.commit()
    return dict(rows[0])


@router.delete("/departments/{department_id}")
async def delete_department(department_id: str, acting_person_id: str,
                            db: AsyncSession = Depends(get_db)):
    await _require_person(db, acting_person_id)
    # people.department_id is a plain text column (no FK), so detach members first
    # rather than leaving dangling pointers behind.
    await db.execute(text("UPDATE company.people SET department_id = NULL "
                          "WHERE company_id = :c AND department_id = :d"),
                     {"c": _cid(), "d": department_id})
    res = await db.execute(text("DELETE FROM company.departments "
                                "WHERE company_id = :c AND department_id = :d "
                                "RETURNING department_id"),
                           {"c": _cid(), "d": department_id})
    if not res.mappings().all():
        await db.rollback()
        raise HTTPException(status_code=404, detail="department not found")
    await db.commit()
    return {"deleted": department_id}


# --------------------------------------------------------------------- people
# NOTE: GET /company/people lives in routes.py and keeps its exact legacy shape
# (person_id, name, title, department, reports_to_id). The org view below is a
# separate path so that shape is never widened.
@router.get("/org/people")
async def list_people_org(include_inactive: bool = True, db: AsyncSession = Depends(get_db)):
    extra = "" if include_inactive else "AND is_active"
    rows = (await db.execute(text(
        "SELECT person_id, name, title, department, department_id, reports_to_id, email, "
        "alternate_person_id, is_active "
        f"FROM company.people WHERE company_id = :c {extra} ORDER BY person_id"),
        {"c": _cid()})).mappings().all()
    return [dict(r) for r in rows]


_INSERT_PERSON_SQL = (
    "INSERT INTO company.people (company_id, person_id, name, title, department, "
    "department_id, reports_to_id, email, alternate_person_id, is_active) "
    "VALUES (:c, :p, :n, :t, :dept, :did, :rt, :e, :alt, :act)")

_BOOTSTRAP_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"
_PEOPLE_COUNT_SQL = "SELECT count(*) AS n FROM company.people WHERE company_id = :c"


async def _person_exists(db: AsyncSession, person_id: str) -> bool:
    rows = (await db.execute(
        text("SELECT person_id, is_active FROM company.people WHERE company_id = :c AND person_id = :p"),
        {"c": _cid(), "p": person_id},
    )).mappings().all()
    return bool(rows)


#: Test seam between the existence check and the bootstrap lock (a barrier forces two
#: concurrent bootstraps past the check together, so they contend for the lock).
async def _before_bootstrap_lock_hook() -> None:
    """No-op; tests patch it."""


async def _bootstrap_allowed(db: AsyncSession, body: PersonIn) -> bool:
    """The ONE exception to "the acting person must exist" (first-administrator bootstrap).

    True only when the actor is registering *themselves* (``acting_person_id ==
    person_id``) AND ``company.people`` has zero rows for this company. Race-safe: a
    transaction-scoped advisory lock serialises bootstraps, and the count is re-read
    under it (READ COMMITTED takes a fresh snapshot per statement, so the loser sees
    the winner's committed row and is refused). The lock is held until the caller's
    commit/rollback, so the INSERT that follows happens inside it.
    """
    if body.acting_person_id != body.person_id:
        return False
    if await _person_exists(db, body.acting_person_id):
        return False  # ordinary path (the INSERT will 409)
    await _before_bootstrap_lock_hook()
    await db.execute(text(_BOOTSTRAP_LOCK_SQL), {"k": f"strata:people:bootstrap:{_cid()}"})
    row = (await db.execute(text(_PEOPLE_COUNT_SQL), {"c": _cid()})).mappings().first()
    return int((row or {}).get("n") or 0) == 0


@router.post("/people", status_code=201)
async def create_person(body: PersonIn, db: AsyncSession = Depends(get_db)):
    """Create a person. ``acting_person_id`` must be an existing person, with exactly
    one exception — **bootstrap of the first administrator**:

    when ``company.people`` has ZERO rows for the company, the first person may be
    created with ``acting_person_id`` equal to their own ``person_id``
    (self-registration). Nothing else is relaxed: an unknown actor creating someone
    else is 404, a self-registration once anyone exists is 404, and every other
    endpoint keeps requiring an existing actor. Two concurrent bootstraps are
    serialised by an advisory lock; the loser is 404 (different id) or 409 (same id).
    A fresh install needs this because every write requires an existing actor; the
    v2 migration preserves existing people, so production never takes this path.
    """
    if not await _bootstrap_allowed(db, body):
        await _require_person(db, body.acting_person_id)
    try:
        await db.execute(text(_INSERT_PERSON_SQL),
            {"c": _cid(), "p": body.person_id, "n": body.name, "t": body.title,
             "dept": body.department, "did": body.department_id, "rt": body.reports_to_id,
             "e": body.email, "alt": body.alternate_person_id, "act": body.is_active})
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="person already exists")
    return {"person_id": body.person_id, "name": body.name, "title": body.title,
            "department": body.department, "department_id": body.department_id,
            "reports_to_id": body.reports_to_id, "email": body.email,
            "alternate_person_id": body.alternate_person_id,
            "is_active": body.is_active}


@router.patch("/people/{person_id}")
async def update_person(person_id: str, body: PersonPatch, db: AsyncSession = Depends(get_db)):
    await _require_person(db, body.acting_person_id)
    cols = {"name": "name", "title": "title", "department": "department",
            "department_id": "department_id", "reports_to_id": "reports_to_id",
            "email": "email", "alternate_person_id": "alternate_person_id",
            "is_active": "is_active"}
    sets, params = [], {"c": _cid(), "p": person_id}
    for field, col in cols.items():
        val = getattr(body, field)
        if val is not None:
            sets.append(f"{col} = :v_{field}")
            params[f"v_{field}"] = val
    if not sets:
        raise HTTPException(status_code=400, detail="no fields to update")
    res = await db.execute(text(
        f"UPDATE company.people SET {', '.join(sets)} "
        "WHERE company_id = :c AND person_id = :p "
        "RETURNING person_id, name, title, department, department_id, reports_to_id, email, "
        "alternate_person_id, is_active"),
        params)
    rows = res.mappings().all()
    if not rows:
        await db.rollback()
        raise HTTPException(status_code=404, detail="person not found")
    await db.commit()
    return dict(rows[0])


@router.delete("/people/{person_id}")
async def deactivate_person(person_id: str, acting_person_id: str,
                            db: AsyncSession = Depends(get_db)):
    """Soft delete. A hard DELETE would orphan every approval_steps.assignee_person_id
    and company_documents.*_id that already points at this person, so `is_active`
    exists precisely so leavers can be retired without rewriting history."""
    await _require_person(db, acting_person_id)
    res = await db.execute(text("UPDATE company.people SET is_active = false "
                                "WHERE company_id = :c AND person_id = :p RETURNING person_id"),
                           {"c": _cid(), "p": person_id})
    if not res.mappings().all():
        await db.rollback()
        raise HTTPException(status_code=404, detail="person not found")
    await db.commit()
    return {"person_id": person_id, "is_active": False}


# -------------------------------------------------------- company + attributes
@router.patch("/profile")
async def update_company(body: CompanyPatch, db: AsyncSession = Depends(get_db)):
    """Upsert company.companies. GET /company/profile (routes.py) reads name from here."""
    await _require_person(db, body.acting_person_id)
    await db.execute(text(
        "INSERT INTO company.companies (company_id, name) VALUES (:c, :n) "
        "ON CONFLICT (company_id) DO UPDATE SET name = EXCLUDED.name"),
        {"c": _cid(), "n": body.name})
    await db.commit()
    return {"company_id": _cid(), "name": body.name}


@router.get("/attributes")
async def list_attributes(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text(
        "SELECT key, value_text, value_num, value_bool, source FROM company.company_attributes "
        "WHERE company_id = :c ORDER BY key"), {"c": _cid()})).mappings().all()
    return [dict(r) for r in rows]


@router.put("/attributes/{key}")
async def upsert_attribute(key: str, body: AttributeIn, db: AsyncSession = Depends(get_db)):
    """Upsert one company attribute. The value's Python type picks the column, and
    exactly one of value_bool/value_num/value_text is set so routes.attribute_value
    reads back what was written (bool first, then num, then text)."""
    await _require_person(db, body.acting_person_id)
    v = body.value
    v_bool = v if isinstance(v, bool) else None
    v_num = float(v) if (not isinstance(v, bool) and isinstance(v, (int, float))) else None
    v_text = v if isinstance(v, str) else None
    source = body.source or f"api:{body.acting_person_id}"
    await db.execute(text(
        "INSERT INTO company.company_attributes (company_id, key, value_text, value_num, value_bool, source) "
        "VALUES (:c, :k, :vt, :vn, :vb, :s) "
        "ON CONFLICT (company_id, key) DO UPDATE SET value_text = EXCLUDED.value_text, "
        "value_num = EXCLUDED.value_num, value_bool = EXCLUDED.value_bool, source = EXCLUDED.source"),
        {"c": _cid(), "k": key, "vt": v_text, "vn": v_num, "vb": v_bool, "s": source})
    await db.commit()
    return {"key": key, "value": v, "source": source}


@router.delete("/attributes/{key}")
async def delete_attribute(key: str, acting_person_id: str, db: AsyncSession = Depends(get_db)):
    await _require_person(db, acting_person_id)
    res = await db.execute(text("DELETE FROM company.company_attributes "
                                "WHERE company_id = :c AND key = :k RETURNING key"),
                           {"c": _cid(), "k": key})
    if not res.mappings().all():
        await db.rollback()
        raise HTTPException(status_code=404, detail="attribute not found")
    await db.commit()
    return {"deleted": key}


# ----------------------------------------------------------- role assignments
@router.get("/documents/{doc_id}/roles")
async def list_roles(doc_id: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text(
        "SELECT ra.doc_id, ra.person_id, ra.role, ra.assigned_at, p.name, p.title "
        "FROM company.document_role_assignments ra "
        "LEFT JOIN company.people p ON p.company_id = ra.company_id AND p.person_id = ra.person_id "
        "WHERE ra.company_id = :c AND ra.doc_id = :d ORDER BY ra.role, ra.person_id"),
        {"c": _cid(), "d": doc_id})).mappings().all()
    return [{"doc_id": r["doc_id"], "person_id": r["person_id"], "role": r["role"],
             "assigned_at": _iso(r["assigned_at"]), "name": r["name"] or "", "title": r["title"] or ""}
            for r in rows]


@router.post("/documents/{doc_id}/roles", status_code=201)
async def assign_role(doc_id: str, body: RoleAssignmentIn, db: AsyncSession = Depends(get_db)):
    await _require_person(db, body.acting_person_id)
    await _require_person(db, body.person_id, what="person", active_only=True)
    await _require_document(db, doc_id)
    try:
        await db.execute(text(
            "INSERT INTO company.document_role_assignments (company_id, doc_id, person_id, role) "
            "VALUES (:c, :d, :p, :r) "
            "ON CONFLICT (company_id, doc_id, person_id, role) DO UPDATE SET assigned_at = now()"),
            {"c": _cid(), "d": doc_id, "p": body.person_id, "r": body.role})
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="invalid role")
    legacy = await _sync_legacy_role_column(db, doc_id, body.role)
    await db.commit()
    return {"doc_id": doc_id, "person_id": body.person_id, "role": body.role,
            "legacy_column": _LEGACY_COL[body.role], "legacy_value": legacy}


@router.delete("/documents/{doc_id}/roles/{role}/{person_id}")
async def unassign_role(doc_id: str, role: Role, person_id: str, acting_person_id: str,
                        db: AsyncSession = Depends(get_db)):
    await _require_person(db, acting_person_id)
    res = await db.execute(text(
        "DELETE FROM company.document_role_assignments "
        "WHERE company_id = :c AND doc_id = :d AND person_id = :p AND role = :r RETURNING role"),
        {"c": _cid(), "d": doc_id, "p": person_id, "r": role})
    if not res.mappings().all():
        await db.rollback()
        raise HTTPException(status_code=404, detail="role assignment not found")
    legacy = await _sync_legacy_role_column(db, doc_id, role)
    await db.commit()
    return {"deleted": {"doc_id": doc_id, "person_id": person_id, "role": role},
            "legacy_column": _LEGACY_COL[role], "legacy_value": legacy}


# --------------------------------------------------------- approval policies
async def _policy_or_404(db: AsyncSession, policy_id: str) -> dict:
    pid = _as_uuid(policy_id, "policy not found")
    rows = (await db.execute(text(
        "SELECT policy_id, name, applies_to_vertical, applies_to_doc_class "
        "FROM company.approval_policies WHERE company_id = :c AND policy_id = CAST(:p AS uuid)"),
        {"c": _cid(), "p": pid})).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail="policy not found")
    return dict(rows[0])


def _policy_out(row: dict, steps: list[dict]) -> dict:
    return {"policy_id": str(row["policy_id"]), "name": row["name"],
            "applies_to_vertical": row["applies_to_vertical"],
            "applies_to_doc_class": row["applies_to_doc_class"],
            "steps": [{"step_no": s["step_no"], "required_role": s["required_role"],
                       "min_approvals": s["min_approvals"]} for s in steps]}


@router.get("/approval-policies")
async def list_policies(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text(
        "SELECT p.policy_id, p.name, p.applies_to_vertical, p.applies_to_doc_class, "
        "s.step_no, s.required_role, s.min_approvals "
        "FROM company.approval_policies p "
        "LEFT JOIN company.approval_policy_steps s ON s.policy_id = p.policy_id "
        "WHERE p.company_id = :c ORDER BY p.name, s.step_no"), {"c": _cid()})).mappings().all()
    out: dict[str, dict] = {}
    for r in rows:
        key = str(r["policy_id"])
        entry = out.setdefault(key, _policy_out(dict(r), []))
        if r["step_no"] is not None:
            entry["steps"].append({"step_no": r["step_no"], "required_role": r["required_role"],
                                   "min_approvals": r["min_approvals"]})
    return list(out.values())


@router.get("/approval-policies/{policy_id}")
async def get_policy(policy_id: str, db: AsyncSession = Depends(get_db)):
    row = await _policy_or_404(db, policy_id)
    return _policy_out(row, await _policy_steps(db, str(row["policy_id"])))


@router.post("/approval-policies", status_code=201)
async def create_policy(body: PolicyIn, db: AsyncSession = Depends(get_db)):
    from app.api.company.routes import fetch_vertical_slugs  # local import: no circularity, just kept next to the upload.py import below
    from app.api.company.upload import _canonical_vertical  # deferred: upload.py imports this module
    await _require_person(db, body.acting_person_id)
    pid = str(uuid.uuid4())
    vertical = (_canonical_vertical(body.applies_to_vertical, await fetch_vertical_slugs(db))
                if body.applies_to_vertical is not None else None)
    await db.execute(text(
        "INSERT INTO company.approval_policies (company_id, policy_id, name, "
        "applies_to_vertical, applies_to_doc_class) VALUES (:c, CAST(:p AS uuid), :n, :v, :k)"),
        {"c": _cid(), "p": pid, "n": body.name, "v": vertical,
         "k": body.applies_to_doc_class})
    await _write_steps(db, pid, body.steps)
    await db.commit()
    return _policy_out({"policy_id": pid, "name": body.name,
                        "applies_to_vertical": vertical,
                        "applies_to_doc_class": body.applies_to_doc_class},
                       [s.model_dump() for s in sorted(body.steps, key=lambda s: s.step_no)])


async def _write_steps(db: AsyncSession, policy_id: str, steps: list[PolicyStepIn]) -> None:
    seen = {s.step_no for s in steps}
    if len(seen) != len(steps):
        raise HTTPException(status_code=400, detail="duplicate step_no")
    for s in steps:
        await db.execute(text(
            "INSERT INTO company.approval_policy_steps (policy_id, step_no, required_role, min_approvals) "
            "VALUES (CAST(:p AS uuid), :n, :r, :m)"),
            {"p": policy_id, "n": s.step_no, "r": s.required_role, "m": s.min_approvals})


@router.patch("/approval-policies/{policy_id}")
async def update_policy(policy_id: str, body: PolicyPatch, db: AsyncSession = Depends(get_db)):
    from app.api.company.routes import fetch_vertical_slugs  # local import: no circularity, just kept next to the upload.py import below
    from app.api.company.upload import _canonical_vertical  # deferred: upload.py imports this module
    await _require_person(db, body.acting_person_id)
    row = await _policy_or_404(db, policy_id)
    pid = str(row["policy_id"])
    sets, params = [], {"c": _cid(), "p": pid}
    if body.name is not None:
        sets.append("name = :n")
        params["n"] = body.name
    if body.clear_vertical:
        sets.append("applies_to_vertical = NULL")
    elif body.applies_to_vertical is not None:
        sets.append("applies_to_vertical = :v")
        params["v"] = _canonical_vertical(body.applies_to_vertical, await fetch_vertical_slugs(db))
    if body.clear_doc_class:
        sets.append("applies_to_doc_class = NULL")
    elif body.applies_to_doc_class is not None:
        sets.append("applies_to_doc_class = :k")
        params["k"] = body.applies_to_doc_class
    if not sets:
        raise HTTPException(status_code=400, detail="no fields to update")
    res = await db.execute(text(
        f"UPDATE company.approval_policies SET {', '.join(sets)} "
        "WHERE company_id = :c AND policy_id = CAST(:p AS uuid) "
        "RETURNING policy_id, name, applies_to_vertical, applies_to_doc_class"), params)
    updated = res.mappings().all()
    await db.commit()
    base = dict(updated[0]) if updated else row
    return _policy_out(base, await _policy_steps(db, pid))


@router.put("/approval-policies/{policy_id}/steps")
async def replace_policy_steps(policy_id: str, body: StepsIn, db: AsyncSession = Depends(get_db)):
    """Whole-list replace. Steps are an ordered chain, so patching one at a time
    invites a policy with a gap or two step 2s; replacing the list keeps it coherent."""
    await _require_person(db, body.acting_person_id)
    row = await _policy_or_404(db, policy_id)
    pid = str(row["policy_id"])
    await db.execute(text("DELETE FROM company.approval_policy_steps WHERE policy_id = CAST(:p AS uuid)"),
                     {"p": pid})
    await _write_steps(db, pid, body.steps)
    await db.commit()
    return _policy_out(row, [s.model_dump() for s in sorted(body.steps, key=lambda s: s.step_no)])


@router.delete("/approval-policies/{policy_id}")
async def delete_policy(policy_id: str, acting_person_id: str, db: AsyncSession = Depends(get_db)):
    await _require_person(db, acting_person_id)
    row = await _policy_or_404(db, policy_id)
    pid = str(row["policy_id"])
    await db.execute(text("DELETE FROM company.approval_policy_steps WHERE policy_id = CAST(:p AS uuid)"),
                     {"p": pid})
    await db.execute(text("DELETE FROM company.approval_policies "
                          "WHERE company_id = :c AND policy_id = CAST(:p AS uuid)"),
                     {"c": _cid(), "p": pid})
    # approval_requests.policy_id has no FK; null it so historical requests stay readable.
    await db.execute(text("UPDATE company.approval_requests SET policy_id = NULL "
                          "WHERE company_id = :c AND policy_id = CAST(:p AS uuid)"),
                     {"c": _cid(), "p": pid})
    await db.commit()
    return {"deleted": pid}


# ------------------------------------------------------------------ approvals
async def _request_or_404(db: AsyncSession, request_id: str) -> dict:
    rid = _as_uuid(request_id, "approval request not found")
    rows = (await db.execute(text(
        "SELECT r.request_id, r.company_id, r.version_id, r.policy_id, r.state, r.created_at, "
        "r.completed_at, v.doc_id, v.version_no, v.status "
        "FROM company.approval_requests r "
        "LEFT JOIN company.document_versions v ON v.version_id = r.version_id "
        "WHERE r.company_id = :c AND r.request_id = CAST(:r AS uuid)"),
        {"c": _cid(), "r": rid})).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail="approval request not found")
    return dict(rows[0])


async def _request_steps(db: AsyncSession, request_id: str) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT step_no, required_role, assignee_person_id, decision, decided_at, note "
        "FROM company.approval_steps WHERE request_id = CAST(:r AS uuid) ORDER BY step_no"),
        {"r": request_id})).mappings().all()
    return [dict(r) for r in rows]


def _request_out(row: dict, steps: list[dict]) -> dict:
    return {
        "request_id": str(row["request_id"]),
        "version_id": str(row["version_id"]),
        "doc_id": row.get("doc_id"),
        "version_no": row.get("version_no"),
        "version_status": row.get("status"),
        "policy_id": str(row["policy_id"]) if row.get("policy_id") else None,
        "state": row["state"],
        "created_at": _iso(row.get("created_at")),
        "completed_at": _iso(row.get("completed_at")),
        "steps": [{"step_no": s["step_no"], "required_role": s["required_role"],
                   "assignee_person_id": s["assignee_person_id"], "decision": s["decision"],
                   "decided_at": _iso(s["decided_at"]), "note": s["note"]} for s in steps],
    }


@router.post("/documents/{doc_id}/versions/{version_id}/approval", status_code=201)
async def open_approval(doc_id: str, version_id: str, body: OpenApprovalIn,
                        db: AsyncSession = Depends(get_db)):
    """Open an approval request for a version (TDD 7.3).

    Instantiates the selected policy's steps onto approval_steps, pre-assigning each
    step to whoever currently holds the required role on the document. With no
    matching policy the request is created already `approved` and a warning is
    logged — documented behaviour per TDD 1.5, not a failure.
    """
    await _require_person(db, body.acting_person_id)
    doc = await _require_document(db, doc_id)
    vid = _as_uuid(version_id, "version not found")
    vrows = (await db.execute(text(
        "SELECT version_id, doc_id, version_no, status FROM company.document_versions "
        "WHERE company_id = :c AND doc_id = :d AND version_id = CAST(:v AS uuid)"),
        {"c": _cid(), "d": doc_id, "v": vid})).mappings().all()
    if not vrows:
        raise HTTPException(status_code=404, detail="version not found")
    version = dict(vrows[0])

    if body.policy_id is not None:
        policy = await _policy_or_404(db, body.policy_id)
    else:
        policy = await select_policy(db, doc.get("vertical"), doc.get("doc_class"))

    steps = await _policy_steps(db, str(policy["policy_id"])) if policy else []
    if policy is None or not steps:
        # Documented fallback (TDD 1.5): no policy (or an empty one) means nothing to
        # sign, so the version auto-approves. Loud, because an org that *meant* to
        # require signatures has just had a document pass with none.
        log.warning(
            "approval auto-approved: no approval policy with steps matched doc_id=%s "
            "vertical=%r doc_class=%r version_id=%s — version promotes with no signatures",
            doc_id, doc.get("vertical"), doc.get("doc_class"), vid,
        )

    rid = str(uuid.uuid4())
    state = "open" if steps else "approved"
    if not steps:
        # An 'approved' insert is invisible to approval_requests_open_uq, so without
        # this check an auto-approve could promote a version under an open request.
        open_rows = (await db.execute(text(
            "SELECT request_id FROM company.approval_requests "
            "WHERE company_id = :c AND version_id = CAST(:v AS uuid) AND state = 'open'"),
            {"c": _cid(), "v": vid})).mappings().all()
        if open_rows:
            raise HTTPException(status_code=409,
                                detail="an open approval request already exists for this version")
    try:
        await db.execute(text(
            "INSERT INTO company.approval_requests "
            "(request_id, company_id, version_id, policy_id, state, completed_at) "
            "VALUES (CAST(:r AS uuid), :c, CAST(:v AS uuid), "
            "CAST(:p AS uuid), :s, CASE WHEN :s2 = 'open' THEN NULL ELSE now() END)"),
            {"r": rid, "c": _cid(), "v": vid,
             "p": str(policy["policy_id"]) if policy else None, "s": state, "s2": state})
    except IntegrityError as exc:
        # approval_requests_open_uq: a partial unique index on (version_id) WHERE
        # state = 'open'. Two concurrent opens both pass a SELECT, so the DB is the
        # only honest gate; surface it as a conflict. Any other integrity error is a
        # real bug and must not be disguised as a 409.
        await db.rollback()
        if "approval_requests_open_uq" not in str(exc):
            raise
        raise HTTPException(status_code=409, detail="an open approval request already exists for this version")

    for s in steps:
        assignee = await _role_holder(db, doc_id, s["required_role"],
                                     doc.get(_LEGACY_COL[s["required_role"]]))
        await db.execute(text(
            "INSERT INTO company.approval_steps (request_id, step_no, required_role, assignee_person_id) "
            "VALUES (CAST(:r AS uuid), :n, :role, :a)"),
            {"r": rid, "n": s["step_no"], "role": s["required_role"], "a": assignee})

    if steps:
        await db.execute(text(
            "UPDATE company.document_versions SET status = 'in_review' "
            "WHERE company_id = :c AND version_id = CAST(:v AS uuid) AND status = 'draft'"),
            {"c": _cid(), "v": vid})
    else:
        await _finalize_approved(db, rid, vid, doc_id)

    await db.commit()
    # Re-read the version AFTER the commit: an auto-approve has just promoted it
    # (status 'effective'), so the status read at the top of this handler is stale.
    fresh_v = (await db.execute(text(
        "SELECT version_id, doc_id, version_no, status FROM company.document_versions "
        "WHERE company_id = :c AND doc_id = :d AND version_id = CAST(:v AS uuid)"),
        {"c": _cid(), "d": doc_id, "v": vid})).mappings().first()
    row = {"request_id": rid, "version_id": vid,
           "policy_id": str(policy["policy_id"]) if policy else None, "state": state,
           "created_at": None, "completed_at": None,
           "doc_id": doc_id, "version_no": version["version_no"],
           "status": fresh_v["status"] if fresh_v else version["status"]}
    return {**_request_out(row, await _request_steps(db, rid)),
            "auto_approved": not steps,
            "policy_name": policy["name"] if policy else None}


async def _finalize_approved(db: AsyncSession, request_id: str, version_id: str, doc_id: str) -> None:
    """Last required step approved (or nothing to sign): close the request and promote.

    TDD 7.3: the version is promoted in the same transaction as this state change.
    `promote_version` (task 5.6) owns every "make it live" write — status
    'effective', is_current, approved_date, superseding the prior version,
    company_documents.current_version_id / current_content_hash — plus the Qdrant
    delete-and-replace, which it runs last. It does not commit; the caller's
    `db.commit()` covers the approval write and the promotion together.

    On failure promote_version has already rolled the session back, so the step
    decision is undone too (`decision IS NULL` holds again) and the signer can simply
    retry. Qdrant failure -> 503 (retryable); not ingested / no pending hash /
    hash already live on another document -> 409.

    The content hash is not passed here: promote_version reads the version's
    document_versions.pending_content_hash (set at upload, task 3.2), falling back to
    the first-version reservation on company_documents (TDD 6.2). A version with
    neither 409s (PromotionHashUnavailable).
    """
    await db.execute(text(
        "UPDATE company.approval_requests SET state = 'approved', completed_at = now() "
        "WHERE request_id = CAST(:r AS uuid)"), {"r": request_id})
    try:
        await promote_version(db, _cid(), doc_id, version_id)
    except PromotionError as exc:
        raise HTTPException(status_code=503 if exc.retryable else 409,
                            detail=f"approval not recorded: promotion failed: {exc}") from exc


async def _require_ingest_succeeded(db: AsyncSession, version_id: str) -> None:
    """Refuse an approving signature (409) until the version's ingest job has succeeded.

    Without this, signatures collected while ingest is still running (or after it
    failed) end at a final approval that promote_version refuses (PromotionNotReady:
    not 'ingested') and rolls back — and nothing promotes later (TDD 6.2, task 3.2).
    The latest job for the version decides. A version with no job row at all (seeded
    or pre-job data) is not blocked here; promote_version's ingest_status check still
    applies to it at the final step. Rejecting is always allowed.
    """
    rows = (await db.execute(text(
        "SELECT job_id, state FROM company.ingest_jobs "
        "WHERE version_id = CAST(:v AS uuid) ORDER BY created_at DESC, job_id DESC LIMIT 1"),
        {"v": version_id})).mappings().all()
    if not rows or rows[0]["state"] == "succeeded":
        return
    state = rows[0]["state"]
    hint = ("retry the ingest job first" if state == "failed"
            else "wait for the ingest job to finish")
    raise HTTPException(
        status_code=409,
        detail=f"cannot approve: this version's ingest job ({rows[0]['job_id']}) is "
               f"'{state}', not 'succeeded'; {hint}")


@router.get("/approval-requests/{request_id}")
async def get_approval_request(request_id: str, db: AsyncSession = Depends(get_db)):
    row = await _request_or_404(db, request_id)
    return _request_out(row, await _request_steps(db, str(row["request_id"])))


@router.get("/documents/{doc_id}/approval-requests")
async def list_document_approval_requests(doc_id: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text(
        "SELECT r.request_id, r.version_id, r.policy_id, r.state, r.created_at, r.completed_at, "
        "v.doc_id, v.version_no, v.status "
        "FROM company.approval_requests r "
        "JOIN company.document_versions v ON v.version_id = r.version_id "
        "WHERE r.company_id = :c AND v.doc_id = :d ORDER BY r.created_at DESC"),
        {"c": _cid(), "d": doc_id})).mappings().all()
    return [_request_out(dict(r), []) for r in rows]


@router.post("/approval-requests/{request_id}/steps/{step_no}/decision")
async def decide_step(request_id: str, step_no: int, body: DecisionIn,
                      db: AsyncSession = Depends(get_db)):
    """Record one signature (TDD 7.3).

    Authorization without auth: `acting_person_id` must be the step's assignee, or —
    when the step has no assignee — must hold the step's `required_role` on the
    document. That is the whole point of carrying the id explicitly.
    """
    await _require_person(db, body.acting_person_id, active_only=True)
    req = await _request_or_404(db, request_id)
    rid = str(req["request_id"])
    if req["state"] != "open":
        raise HTTPException(status_code=409, detail=f"approval request is {req['state']}, not open")

    steps = await _request_steps(db, rid)
    step = next((s for s in steps if s["step_no"] == step_no), None)
    if step is None:
        raise HTTPException(status_code=404, detail="step not found")
    if step["decision"] is not None:
        raise HTTPException(status_code=409, detail="step already decided")
    # Steps are an ordered chain: an earlier undecided step must be signed first.
    pending_earlier = [s["step_no"] for s in steps if s["step_no"] < step_no and s["decision"] is None]
    if pending_earlier:
        raise HTTPException(status_code=409,
                            detail=f"earlier step(s) {pending_earlier} not yet decided")

    doc_id = req.get("doc_id")
    if not doc_id:
        # The version row is gone (LEFT JOIN miss), so role membership cannot be
        # checked. Refuse rather than let anyone sign.
        raise HTTPException(status_code=409, detail="approval request's version no longer exists")
    if step["assignee_person_id"]:
        if body.acting_person_id != step["assignee_person_id"]:
            raise HTTPException(status_code=403,
                                detail=f"step {step_no} is assigned to {step['assignee_person_id']}")
    elif not await _holds_role(db, doc_id, step["required_role"], body.acting_person_id):
        raise HTTPException(status_code=403,
                            detail=f"{body.acting_person_id} does not hold role "
                                   f"'{step['required_role']}' on {doc_id}")

    if body.decision == "approved":
        await _require_ingest_succeeded(db, str(req["version_id"]))

    note = body.note.strip() if body.note and body.note.strip() else None
    # `AND decision IS NULL` makes the write the gate: two concurrent decisions on
    # the final step would otherwise both reach _finalize_approved, i.e. promote the
    # version twice once task 5.6 wires promote_version in.
    claimed = (await db.execute(text(
        "UPDATE company.approval_steps SET decision = :d, decided_at = now(), note = :n, "
        "assignee_person_id = :a WHERE request_id = CAST(:r AS uuid) AND step_no = :s "
        "AND decision IS NULL RETURNING step_no"),
        {"d": body.decision, "n": note, "a": body.acting_person_id, "r": rid, "s": step_no})
    ).mappings().all()
    if not claimed:
        await db.rollback()
        raise HTTPException(status_code=409, detail="step already decided")

    vid = str(req["version_id"])
    if body.decision == "rejected":
        # TDD 7.3: any rejected step rejects the request; the version stays in_review
        # and never promotes.
        await db.execute(text(
            "UPDATE company.approval_requests SET state = 'rejected', completed_at = now() "
            "WHERE request_id = CAST(:r AS uuid) AND state = 'open'"), {"r": rid})
        new_state = "rejected"
    else:
        remaining = [s["step_no"] for s in steps
                     if s["step_no"] != step_no and s["decision"] is None]
        if remaining:
            new_state = "open"
        else:
            await _finalize_approved(db, rid, vid, doc_id or "")
            new_state = "approved"

    await db.commit()
    fresh = await _request_or_404(db, rid)
    return {**_request_out(fresh, await _request_steps(db, rid)),
            "decided_step": step_no, "decided_by": body.acting_person_id,
            "request_state": new_state}


@router.post("/approval-requests/{request_id}/cancel")
async def cancel_approval_request(request_id: str, body: _Acting,
                                  db: AsyncSession = Depends(get_db)):
    await _require_person(db, body.acting_person_id)
    req = await _request_or_404(db, request_id)
    if req["state"] != "open":
        raise HTTPException(status_code=409, detail=f"approval request is {req['state']}, not open")
    rid = str(req["request_id"])
    await db.execute(text(
        "UPDATE company.approval_requests SET state = 'cancelled', completed_at = now() "
        "WHERE request_id = CAST(:r AS uuid)"), {"r": rid})
    # Task 3.2 decision 1: a cancelled request retires its version, and the pending
    # hash goes with it (the only durable hash is company_documents.current_content_hash).
    # Same transaction as the cancel. Never touches a live version.
    await db.execute(text(
        "UPDATE company.document_versions SET status = 'retired', pending_content_hash = NULL "
        "WHERE company_id = :c AND version_id = CAST(:v AS uuid) "
        "AND NOT is_current AND status IN ('in_review', 'draft')"),
        {"c": _cid(), "v": str(req["version_id"])})
    # A cancelled FIRST version must also release its document's reserved hash.
    # Otherwise the document sits `pending` with a hash and no live version, and a
    # re-upload of the same content is rejected as a duplicate of a document that
    # has nothing live. Only when the document has no current version and no other
    # non-retired version.
    await db.execute(text(
        "UPDATE company.company_documents d "
        "SET current_content_hash = NULL, lifecycle_state = 'retired', updated_at = now() "
        "FROM company.document_versions v "
        "WHERE v.version_id = CAST(:v AS uuid) AND d.company_id = :c AND d.doc_id = v.doc_id "
        "AND v.status = 'retired' AND d.current_version_id IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM company.document_versions o "
        "                WHERE o.company_id = d.company_id AND o.doc_id = d.doc_id "
        "                AND o.version_id <> v.version_id AND o.status <> 'retired')"),
        {"c": _cid(), "v": str(req["version_id"])})
    await db.commit()
    fresh = await _request_or_404(db, rid)
    return _request_out(fresh, await _request_steps(db, rid))
