import difflib
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.db import get_db
from app.regulatory.models.code_section import CodeSection

router = APIRouter(prefix="/diff", tags=["diff"])


@router.get("/{source_system}/{citation:path}/compare")
async def compare_snapshots(
    source_system: str,
    citation: str,
    date_a: str = Query(..., description="ISO date string YYYY-MM-DD"),
    date_b: str = Query(..., description="ISO date string YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """Compare two specific snapshots of a CodeSection by date."""
    result = await db.execute(
        select(CodeSection)
        .where(
            CodeSection.source_system == source_system,
            CodeSection.citation == citation,
        )
        .order_by(CodeSection.snapshot_date)
    )
    versions = result.scalars().all()

    if not versions:
        raise HTTPException(status_code=404, detail=f"Citation '{citation}' not found in source_system '{source_system}'")

    from datetime import date as date_type

    def parse_date(ds: str) -> date_type:
        try:
            return date_type.fromisoformat(ds)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid date format: {ds}. Use YYYY-MM-DD.")

    target_a = parse_date(date_a)
    target_b = parse_date(date_b)

    def nearest(target: date_type):
        return min(versions, key=lambda v: abs((v.snapshot_date - target).days))

    snap_a = nearest(target_a)
    snap_b = nearest(target_b)

    # Verify snapshots exist (nearest always returns something, but confirm they're reasonable)
    if snap_a is None:
        raise HTTPException(status_code=404, detail=f"No snapshot found near date_a={date_a}")
    if snap_b is None:
        raise HTTPException(status_code=404, detail=f"No snapshot found near date_b={date_b}")

    diff_lines = list(
        difflib.unified_diff(
            snap_a.body_text.splitlines(),
            snap_b.body_text.splitlines(),
            lineterm="",
        )
    )
    diff_str = "\n".join(diff_lines) if diff_lines else ""

    return {
        "citation": citation,
        "source_system": source_system,
        "date_a": snap_a.snapshot_date.isoformat(),
        "date_b": snap_b.snapshot_date.isoformat(),
        "diff": diff_str,
    }


@router.get("/{source_system}/{citation:path}")
async def version_history(
    source_system: str,
    citation: str,
    db: AsyncSession = Depends(get_db),
):
    """Return the version chain for a CodeSection with diffs between consecutive versions."""
    result = await db.execute(
        select(CodeSection)
        .where(
            CodeSection.source_system == source_system,
            CodeSection.citation == citation,
        )
        .order_by(CodeSection.snapshot_date)
    )
    versions = result.scalars().all()

    if not versions:
        raise HTTPException(status_code=404, detail=f"Citation '{citation}' not found in source_system '{source_system}'")

    version_list = []
    for i, v in enumerate(versions):
        if i == 0:
            diff_from_previous = None
        else:
            prev = versions[i - 1]
            diff_lines = list(
                difflib.unified_diff(
                    prev.body_text.splitlines(),
                    v.body_text.splitlines(),
                    lineterm="",
                )
            )
            diff_from_previous = "\n".join(diff_lines) if diff_lines else ""

        version_list.append(
            {
                "id": v.id,
                "snapshot_date": v.snapshot_date.isoformat() if v.snapshot_date else None,
                "effective_date": v.effective_date.isoformat() if v.effective_date else None,
                "content_hash": v.content_hash,
                "amendment_source": v.amendment_source,
                "heading": v.heading,
                "diff_from_previous": diff_from_previous,
            }
        )

    return {
        "citation": citation,
        "source_system": source_system,
        "version_count": len(versions),
        "versions": version_list,
    }
