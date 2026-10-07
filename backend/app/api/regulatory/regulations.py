from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional
from app.db import get_db
from app.regulatory.models.code_section import CodeSection

router = APIRouter(prefix="/regulations", tags=["regulations"])


def _build_latest_subquery():
    """Build a subquery that gets max snapshot_date per (source_system, citation)."""
    return (
        select(
            CodeSection.source_system,
            CodeSection.citation,
            func.max(CodeSection.snapshot_date).label("max_date"),
        )
        .group_by(CodeSection.source_system, CodeSection.citation)
        .subquery()
    )


@router.get("")
async def list_regulations(
    source_system: Optional[str] = Query(None, description="Filter by source system: cfr"),
    agency: Optional[str] = Query(None, description="Filter by owning_agency"),
    jurisdiction_level: Optional[str] = Query(None, description="Filter by jurisdiction level: federal or state"),
    status: Optional[str] = Query(None, description="Filter by status enum"),
    search: Optional[str] = Query(None, description="Text search on heading or citation (ILIKE)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=200, description="Items per page, max 200"),
    db: AsyncSession = Depends(get_db),
):
    latest = _build_latest_subquery()

    # Base query: join to get only the latest snapshot per (source_system, citation)
    base_q = select(CodeSection).join(
        latest,
        and_(
            CodeSection.source_system == latest.c.source_system,
            CodeSection.citation == latest.c.citation,
            CodeSection.snapshot_date == latest.c.max_date,
        ),
    )

    # Apply filters
    filters = []
    if source_system:
        filters.append(CodeSection.source_system == source_system)
    if agency:
        filters.append(CodeSection.owning_agency == agency)
    if jurisdiction_level:
        filters.append(CodeSection.jurisdiction_level == jurisdiction_level)
    if status:
        filters.append(CodeSection.status == status)
    if search:
        pattern = f"%{search}%"
        filters.append(
            CodeSection.heading.ilike(pattern) | CodeSection.citation.ilike(pattern)
        )

    if filters:
        base_q = base_q.where(and_(*filters))

    # Count total
    count_q = select(func.count()).select_from(base_q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    # Fetch page
    offset = (page - 1) * limit
    items_q = base_q.order_by(CodeSection.citation).offset(offset).limit(limit)
    items_result = await db.execute(items_q)
    sections = items_result.scalars().all()

    items = [
        {
            "id": s.id,
            "citation": s.citation,
            "source_system": s.source_system,
            "jurisdiction_level": s.jurisdiction_level,
            "jurisdiction_geo": s.jurisdiction_geo,
            "heading": s.heading,
            "owning_agency": s.owning_agency,
            "status": s.status,
            "effective_date": s.effective_date,
            "snapshot_date": s.snapshot_date,
            "source_url": s.source_url,
            "content_hash": s.content_hash,
        }
        for s in sections
    ]

    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/{source_system}/{citation:path}")
async def get_regulation(
    source_system: str,
    citation: str,
    db: AsyncSession = Depends(get_db),
):
    latest = _build_latest_subquery()

    # Fetch the current (latest snapshot) for this (source_system, citation)
    q = (
        select(CodeSection)
        .join(
            latest,
            and_(
                CodeSection.source_system == latest.c.source_system,
                CodeSection.citation == latest.c.citation,
                CodeSection.snapshot_date == latest.c.max_date,
            ),
        )
        .where(
            and_(
                CodeSection.source_system == source_system,
                CodeSection.citation == citation,
            )
        )
    )
    result = await db.execute(q)
    section = result.scalar_one_or_none()

    if section is None:
        raise HTTPException(status_code=404, detail="Regulation not found")

    # Count total versions (snapshots) for this (source_system, citation)
    version_count_q = select(func.count()).where(
        and_(
            CodeSection.source_system == source_system,
            CodeSection.citation == citation,
        )
    )
    vc_result = await db.execute(version_count_q)
    version_count = vc_result.scalar_one()

    return {
        "id": section.id,
        "citation": section.citation,
        "source_system": section.source_system,
        "jurisdiction_level": section.jurisdiction_level,
        "jurisdiction_geo": section.jurisdiction_geo,
        "title_number": section.title_number,
        "part": section.part,
        "section_number": section.section_number,
        "heading": section.heading,
        "body_text": section.body_text,
        "content_hash": section.content_hash,
        "owning_agency": section.owning_agency,
        "effective_date": section.effective_date,
        "status": section.status,
        "snapshot_date": section.snapshot_date,
        "source_url": section.source_url,
        "amendment_source": section.amendment_source,
        "prior_version_id": section.prior_version_id,
        # NOTE: superseded_by is always NULL — no adapter populates this field yet.
        "superseded_by": section.superseded_by,
        # NOTE: repealed_date is always NULL — no adapter populates this field yet.
        "repealed_date": section.repealed_date,
        "ingested_at": section.ingested_at,
        "version_count": version_count,
    }
