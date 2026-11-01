"""Document-metadata editor: ``PATCH /company/documents/{doc_id}`` (task 9.1 step 1a; TDD §7.6).

After v2 nothing writes ``company_documents.vertical/doc_class/review_cycle`` or a
version's ``version`` label/``next_review``/``effective_date``/``approved_date`` except the upload form
(``vertical``, ``doc_class``, ``doc_number``, ``law_as_of``); extraction of the rest is
not built. This endpoint is the user-editable writer TDD §7.6 assigns those fields to,
and the demo seeder uses it to write the values from ``document_register.csv``.

Same conventions as ``org.py``: no auth, an explicit ``acting_person_id`` validated
against ``company.people``, single tenant ``engine_settings.ENGINE_COMPANY_ID``.
The response is exactly ``GET /company/documents/{doc_id}`` (``routes._documents``).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.company import routes
from app.api.company.org import _as_uuid, _require_person
from app.api.company.upload import _canonical_vertical
from app.company_ingest.constants import DocClass
from app.db import get_db
from app.engine.config import engine_settings

router = APIRouter(prefix="/company", tags=["company-doc-admin"])

DOC_CLASSES: tuple[str, ...] = tuple(c.value for c in DocClass)

# SET clauses are built only from these fixed column names, never from request keys.
# Document columns: title, doc_class, vertical, doc_number, review_cycle (see _validated).
# Version columns: ``version`` (free-text label, see _validated) plus these ISO dates.
# request field -> company.document_versions column
_VERSION_COLS = {"next_review": "next_review", "effective_date": "effective_date",
                 "approved_date": "approved_date", "law_as_of": "law_as_of"}


def _cid() -> str:
    return engine_settings.ENGINE_COMPANY_ID


class DocumentPatch(BaseModel):
    """Only keys present in the body change. An explicit ``null`` clears the field
    (except ``title`` and ``vertical``, which a document always has). Unknown keys —
    including ``status``, ``lifecycle_state``, ``version_no``, content hashes and
    ``doc_id`` — are rejected with 422 rather than silently ignored."""

    model_config = ConfigDict(extra="forbid")

    acting_person_id: str = Field(min_length=1)
    title: Optional[str] = None
    doc_class: Optional[str] = None
    vertical: Optional[str] = None
    doc_number: Optional[str] = None
    review_cycle: Optional[str] = None
    # version-level
    version_id: Optional[str] = None
    version: Optional[str] = None  # human-readable label, e.g. "5.1" (not version_id)
    next_review: Optional[str] = None
    effective_date: Optional[str] = None
    approved_date: Optional[str] = None
    law_as_of: Optional[str] = None


# -------------------------------------------------------------------- validation
def _text(field: str, value: Optional[str], *, nullable: bool) -> Optional[str]:
    if value is None:
        if not nullable:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null.")
        return None
    v = value.strip()
    if not v:
        raise HTTPException(status_code=422,
                            detail=f"{field} cannot be blank; send null to clear it."
                            if nullable else f"{field} cannot be blank.")
    return v


def _doc_class(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = value.strip().lower()
    if v not in DOC_CLASSES:
        raise HTTPException(status_code=422,
                            detail=f"Unknown doc_class {value!r}. Use one of: {', '.join(DOC_CLASSES)} (or null).")
    return v


def _iso_date(field: str, value: Optional[str]) -> Optional[date]:
    """Strict ISO date. ``null`` clears; ``""`` is an error (it would otherwise be a silent clear)."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(status_code=422,
                            detail=f"{field} must be an ISO date (YYYY-MM-DD) or null.") from exc


async def _validated(db: AsyncSession, body: DocumentPatch) -> tuple[dict[str, Any], dict[str, Any]]:
    """-> (company_documents values, document_versions values), keyed by column."""
    sent = body.model_fields_set - {"acting_person_id", "version_id"}
    if not sent:
        raise HTTPException(status_code=422, detail="Nothing to update: send at least one editable field.")
    doc: dict[str, Any] = {}
    ver: dict[str, Any] = {}
    if "title" in sent:
        doc["title"] = _text("title", body.title, nullable=False)
    if "vertical" in sent:
        if body.vertical is None:
            raise HTTPException(status_code=422, detail="vertical cannot be null.")
        doc["vertical"] = _canonical_vertical(body.vertical, await routes.fetch_vertical_slugs(db))  # same rules as upload; rejects 'unclassified'
    if "doc_class" in sent:
        doc["doc_class"] = _doc_class(body.doc_class)
    if "doc_number" in sent:
        doc["doc_number"] = _text("doc_number", body.doc_number, nullable=True)
    if "review_cycle" in sent:
        doc["review_cycle"] = _text("review_cycle", body.review_cycle, nullable=True)
    if "version" in sent:
        ver["version"] = _text("version", body.version, nullable=True)
    for field, col in _VERSION_COLS.items():
        if field in sent:
            ver[col] = _iso_date(field, getattr(body, field))
    if body.version_id is not None and not ver:
        raise HTTPException(status_code=422,
                            detail="version_id was given but no version-level field "
                                   "(version, next_review, effective_date, approved_date, law_as_of).")
    return doc, ver


# -------------------------------------------------------------------- resolution
async def _target_version(db: AsyncSession, doc: dict, version_id: Optional[str]) -> str:
    """The version a version-level edit applies to; row-locked for the transaction."""
    if version_id is not None:
        vid = _as_uuid(version_id, "version not found")
        rows = (await db.execute(text(
            "SELECT version_id, status FROM company.document_versions "
            "WHERE company_id = :c AND doc_id = :d AND version_id = CAST(:v AS uuid) FOR UPDATE"),
            {"c": _cid(), "d": doc["doc_id"], "v": vid})).mappings().all()
        if not rows:
            raise HTTPException(status_code=404, detail="version not found for this document")
    elif doc.get("current_version_id") is not None:
        rows = (await db.execute(text(
            "SELECT version_id, status FROM company.document_versions "
            "WHERE company_id = :c AND doc_id = :d AND version_id = CAST(:v AS uuid) FOR UPDATE"),
            {"c": _cid(), "d": doc["doc_id"], "v": str(doc["current_version_id"])})).mappings().all()
    else:
        rows = []
    if not rows and version_id is None:
        # No current version (a new upload still in review): the newest non-retired
        # version, the same one GET reports as latest_version_* (routes._DOC_SQL).
        rows = (await db.execute(text(
            "SELECT version_id, status FROM company.document_versions "
            "WHERE company_id = :c AND doc_id = :d AND status <> 'retired' "
            "ORDER BY version_no DESC NULLS LAST, created_at DESC LIMIT 1 FOR UPDATE"),
            {"c": _cid(), "d": doc["doc_id"]})).mappings().all()
        if not rows:
            raise HTTPException(status_code=409,
                                detail="this document has no editable (non-retired) version")
    row = rows[0]
    if row["status"] == "retired":
        raise HTTPException(status_code=409, detail="a retired version cannot be edited")
    return str(row["version_id"])


# ---------------------------------------------------------------------- endpoint
@router.patch("/documents/{doc_id}")
async def patch_document(doc_id: str, body: DocumentPatch, db: AsyncSession = Depends(get_db)):
    """Edit a document's metadata (PATCH semantics: only keys present change).

    Document fields: ``title``, ``doc_class`` (a ``DocClass`` value or null), ``vertical``
    (backend name in any case or the frontend slug, stored title-cased; one of the 14,
    never ``unclassified``), ``doc_number``, ``review_cycle``. Version fields:
    ``version`` (the display label, e.g. "5.1"; text or null), ``next_review``,
    ``effective_date``, ``approved_date``, ``law_as_of`` (ISO dates or null), applied to ``version_id`` if given, else the current version, else the
    newest non-retired version. A retired version (or a document with no non-retired
    version) is 409; a ``version_id`` of another document is 404.

    Content, hashes, ``doc_id``, ``lifecycle_state``, ``version_no`` and ``status`` are
    not editable (unknown keys are 422). ``company_documents.updated_at`` is bumped on
    every successful patch.

    Caveats, by design (nothing is recomputed here):
    * ``law_as_of`` is the date the citation resolver resolves a version's citations
      against. Changing it on a version that already has ``clause_citations`` does NOT
      re-resolve them; they stay as resolved at ingest until the version is re-ingested.
    * The approval policy is selected from ``vertical``/``doc_class`` when the approval
      request is opened (at upload). Changing either here does not re-select the policy
      of an already-open request; it affects only requests opened later.
    """
    doc_vals, ver_vals = await _validated(db, body)
    await _require_person(db, body.acting_person_id)
    docs = (await db.execute(text(
        "SELECT doc_id, current_version_id FROM company.company_documents "
        "WHERE company_id = :c AND doc_id = :d FOR UPDATE"),
        {"c": _cid(), "d": doc_id})).mappings().all()
    if not docs:
        raise HTTPException(status_code=404, detail="document not found")
    vid = await _target_version(db, dict(docs[0]), body.version_id) if ver_vals else None

    if vid is not None:
        sets = [f"{col} = :v_{col}" for col in ver_vals]
        res = await db.execute(text(
            f"UPDATE company.document_versions SET {', '.join(sets)} "
            "WHERE company_id = :c AND doc_id = :d AND version_id = CAST(:v AS uuid) "
            "AND status <> 'retired' RETURNING version_id"),
            {"c": _cid(), "d": doc_id, "v": vid, **{f"v_{k}": v for k, v in ver_vals.items()}})
        if not res.mappings().all():
            await db.rollback()
            raise HTTPException(status_code=409, detail="a retired version cannot be edited")

    sets = [f"{col} = :d_{col}" for col in doc_vals] + ["updated_at = now()"]
    await db.execute(text(
        f"UPDATE company.company_documents SET {', '.join(sets)} "
        "WHERE company_id = :c AND doc_id = :d"),
        {"c": _cid(), "d": doc_id, **{f"d_{k}": v for k, v in doc_vals.items()}})
    await db.commit()

    out = await routes._documents(db, doc_id)
    if not out:  # deleted concurrently between commit and read
        raise HTTPException(status_code=404, detail="document not found")
    return out[0]
