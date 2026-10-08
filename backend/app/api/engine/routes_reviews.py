"""Review + people routes (api_ui.md section 1). Mounted under /engine by routes.py."""
import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.engine.config import engine_settings
from app.engine.schemas import ReviewRequest

router = APIRouter()


class ReviewBody(ReviewRequest):
    """schemas.ReviewRequest validation (reject needs a note), action limited to the two literals."""
    action: Literal["accept", "reject"]  # type: ignore[assignment]


class ReviewOut(BaseModel):
    review_id: str
    finding_id: str
    action: str
    note: Optional[str] = None
    person_id: str
    created_at: Optional[datetime] = None


class PersonOut(BaseModel):
    person_id: str
    name: str
    title: Optional[str] = None


@router.get("/people", response_model=list[PersonOut])
async def list_people(db: AsyncSession = Depends(get_db)):
    res = await db.execute(text("SELECT person_id, name, title FROM company.people "
                                "WHERE company_id = :c ORDER BY name"),
                           {"c": engine_settings.ENGINE_COMPANY_ID})
    return [dict(r) for r in res.mappings().all()]


@router.post("/findings/{finding_id}/reviews", response_model=ReviewOut)
async def create_review(finding_id: str, body: ReviewBody, db: AsyncSession = Depends(get_db)):
    try:
        fid = str(uuid.UUID(finding_id))
    except ValueError:
        raise HTTPException(404, "finding not found")
    f = (await db.execute(text("SELECT finding_id FROM engine.findings WHERE finding_id = CAST(:f AS uuid)"),
                          {"f": fid})).mappings().all()
    if not f:
        raise HTTPException(404, "finding not found")
    p = (await db.execute(text("SELECT person_id FROM company.people WHERE company_id = :c AND person_id = :p"),
                          {"c": engine_settings.ENGINE_COMPANY_ID, "p": body.person_id})).mappings().all()
    if not p:
        raise HTTPException(404, "person not found")
    note = body.note.strip() if body.note and body.note.strip() else None
    res = await db.execute(text(
        "INSERT INTO engine.finding_reviews (review_id, finding_id, action, note, person_id) "
        "VALUES (CAST(:r AS uuid), CAST(:f AS uuid), :a, :n, :p) "
        "RETURNING review_id, finding_id, action, note, person_id, created_at"),
        {"r": str(uuid.uuid4()), "f": fid, "a": body.action, "n": note, "p": body.person_id})
    row = dict(res.mappings().all()[0])
    await db.commit()
    return {**row, "review_id": str(row["review_id"]), "finding_id": str(row["finding_id"])}
