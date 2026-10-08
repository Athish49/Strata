from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import Optional
from datetime import date
from app.db import get_db
from app.regulatory.models.regulatory_action import RegulatoryAction
from app.regulatory.models.relationship import ActionRelationship

router = APIRouter(prefix="/actions", tags=["actions"])


def _action_to_dict(a: RegulatoryAction, include_abstract: bool = False) -> dict:
    d = {
        "id": a.id,
        "source_id": a.source_id,
        "source_system": a.source_system,
        "jurisdiction_level": a.jurisdiction_level,
        "jurisdiction_geo": a.jurisdiction_geo,
        "action_type": a.action_type,
        "source_type": a.source_type,
        "action_text": a.action_text,
        "title": a.title,
        "agency": a.agency,
        "status": a.status,
        "date_published": a.date_published,
        "date_effective": a.date_effective,
        "date_comment_close": a.date_comment_close,
        "date_filed": a.date_filed,
        "docket_ids": a.docket_ids,
        "rin": a.rin,
        "cfr_references": a.cfr_references,
        # NOTE: legal_refs is always NULL — will be populated after state_adapters fix.
        "legal_refs": a.legal_refs,
        # NOTE: affected_entities is always NULL — no adapter populates this field yet.
        "affected_entities": a.affected_entities,
        # NOTE: related_actions column is always NULL — stitcher uses action_relationships
        # table instead; see related_actions_resolved in the detail endpoint.
        "related_actions": a.related_actions,
        "source_url": a.source_url,
        "full_text_url": a.full_text_url,
        "ingested_at": a.ingested_at,
        "adapter_version": a.adapter_version,
    }
    if include_abstract:
        d["abstract"] = a.abstract
    return d


@router.get("")
async def list_actions(
    source_system: Optional[str] = Query(None, description="Filter by source system: federal_register"),
    agency: Optional[str] = Query(None, description="Filter by agency canonical ID: ferc, epa, iurc, idem"),
    status: Optional[str] = Query(None, description="Filter by status: in_progress, approved, blocked_suspended"),
    action_type: Optional[str] = Query(None, description="Filter by action_type (e.g. final_rule, rate_case)"),
    date_from: Optional[date] = Query(None, description="Filter date_published >= date_from (ISO date)"),
    date_to: Optional[date] = Query(None, description="Filter date_published <= date_to (ISO date)"),
    search: Optional[str] = Query(None, description="ILIKE search on title or abstract"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=200, description="Items per page, max 200"),
    db: AsyncSession = Depends(get_db),
):
    base_q = select(RegulatoryAction)

    filters = []
    if source_system:
        filters.append(RegulatoryAction.source_system == source_system)
    if agency:
        filters.append(RegulatoryAction.agency == agency)
    if status:
        filters.append(RegulatoryAction.status == status)
    if action_type:
        filters.append(RegulatoryAction.action_type == action_type)
    if date_from:
        filters.append(RegulatoryAction.date_published >= date_from)
    if date_to:
        filters.append(RegulatoryAction.date_published <= date_to)
    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(
                RegulatoryAction.title.ilike(pattern),
                RegulatoryAction.abstract.ilike(pattern),
            )
        )

    if filters:
        base_q = base_q.where(and_(*filters))

    # Count total
    count_q = select(func.count()).select_from(base_q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    # Fetch page
    offset = (page - 1) * limit
    items_q = base_q.order_by(RegulatoryAction.date_published.desc().nulls_last(), RegulatoryAction.id.desc()).offset(offset).limit(limit)
    items_result = await db.execute(items_q)
    actions = items_result.scalars().all()

    items = [_action_to_dict(a, include_abstract=False) for a in actions]

    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/{source_system}/{source_id:path}")
async def get_action(
    source_system: str,
    source_id: str,
    db: AsyncSession = Depends(get_db),
):
    q = select(RegulatoryAction).where(
        and_(
            RegulatoryAction.source_system == source_system,
            RegulatoryAction.source_id == source_id,
        )
    )
    result = await db.execute(q)
    action = result.scalar_one_or_none()

    if action is None:
        raise HTTPException(status_code=404, detail="Regulatory action not found")

    # Fetch related actions via ActionRelationship
    rel_q = (
        select(ActionRelationship, RegulatoryAction)
        .join(RegulatoryAction, ActionRelationship.to_action_id == RegulatoryAction.id)
        .where(ActionRelationship.from_action_id == action.id)
    )
    rel_result = await db.execute(rel_q)
    rel_rows = rel_result.all()

    related_actions_resolved = [
        {
            "relationship_type": rel.relationship_type,
            "action": _action_to_dict(related, include_abstract=True),
        }
        for rel, related in rel_rows
    ]

    response = _action_to_dict(action, include_abstract=True)
    response["related_actions_resolved"] = related_actions_resolved

    return response
