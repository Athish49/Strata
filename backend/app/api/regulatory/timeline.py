from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import Optional
from datetime import date, timedelta
from app.db import get_db
from app.regulatory.models.code_section import CodeSection
from app.regulatory.models.regulatory_action import RegulatoryAction

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("/deadlines")
async def get_deadlines(
    days_ahead: int = Query(default=90),
    agency: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    end_date = today + timedelta(days=days_ahead)

    filters = [
        or_(
            and_(
                RegulatoryAction.date_effective >= today,
                RegulatoryAction.date_effective <= end_date,
            ),
            and_(
                RegulatoryAction.date_comment_close >= today,
                RegulatoryAction.date_comment_close <= end_date,
            ),
        )
    ]

    if agency:
        filters.append(RegulatoryAction.agency == agency)
    if status:
        filters.append(RegulatoryAction.status == status)

    result = await db.execute(
        select(RegulatoryAction).where(and_(*filters))
    )
    actions = result.scalars().all()

    deadlines = []
    for action in actions:
        if (
            action.date_effective
            and today <= action.date_effective <= end_date
        ):
            deadlines.append({
                "date": action.date_effective.isoformat(),
                "deadline_type": "effective",
                "source_id": action.source_id,
                "source_system": action.source_system,
                "title": action.title,
                "action_type": action.action_type,
                "agency": action.agency,
                "status": action.status,
            })
        if (
            action.date_comment_close
            and today <= action.date_comment_close <= end_date
        ):
            deadlines.append({
                "date": action.date_comment_close.isoformat(),
                "deadline_type": "comment_close",
                "source_id": action.source_id,
                "source_system": action.source_system,
                "title": action.title,
                "action_type": action.action_type,
                "agency": action.agency,
                "status": action.status,
            })

    deadlines.sort(key=lambda d: d["date"])

    return {"deadlines": deadlines, "total": len(deadlines)}


@router.get("/{source_system}/{citation:path}")
async def get_regulation_timeline(
    source_system: str,
    citation: str,
    db: AsyncSession = Depends(get_db),
):
    # Fetch CodeSection version changes for this (source_system, citation)
    cs_result = await db.execute(
        select(CodeSection).where(
            and_(
                CodeSection.source_system == source_system,
                CodeSection.citation == citation,
            )
        )
    )
    code_sections = cs_result.scalars().all()

    if not code_sections:
        # Check if any regulatory actions reference this citation
        ra_result = await db.execute(
            select(RegulatoryAction).where(
                RegulatoryAction.cfr_references.contains([citation])
            )
        )
        regulatory_actions = ra_result.scalars().all()
        if not regulatory_actions:
            raise HTTPException(status_code=404, detail=f"Citation '{citation}' not found")
    else:
        # Fetch RegulatoryActions referencing this citation
        ra_result = await db.execute(
            select(RegulatoryAction).where(
                RegulatoryAction.cfr_references.contains([citation])
            )
        )
        regulatory_actions = ra_result.scalars().all()

    events = []

    for cs in code_sections:
        event_date = cs.snapshot_date
        events.append({
            "event_type": "code_change",
            "date": event_date.isoformat() if event_date else None,
            "snapshot_date": cs.snapshot_date.isoformat() if cs.snapshot_date else None,
            "effective_date": cs.effective_date.isoformat() if cs.effective_date else None,
            "content_hash": cs.content_hash,
            "amendment_source": cs.amendment_source,
            "heading": cs.heading,
        })

    for action in regulatory_actions:
        event_date = action.date_published
        events.append({
            "event_type": "regulatory_action",
            "date": event_date.isoformat() if event_date else None,
            "source_id": action.source_id,
            "source_system": action.source_system,
            "action_type": action.action_type,
            "title": action.title,
            "status": action.status,
            "agency": action.agency,
        })

    # Sort by date descending (newest first), None dates go last
    events.sort(key=lambda e: e["date"] or "", reverse=False)

    return {
        "citation": citation,
        "source_system": source_system,
        "events": events,
    }
