from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.regulatory.models.code_section import CodeSection
from app.regulatory.models.regulatory_action import RegulatoryAction
from typing import Literal


async def detect_changes(
    record: dict, db: AsyncSession
) -> Literal["new", "unchanged", "changed"]:
    """Detect whether a CodeSection record is new, unchanged, or changed.

    Queries the DB for the most recent CodeSection with the same
    (source_system, citation), ordered by snapshot_date DESC.

    Returns:
        "new"       — no existing record found
        "unchanged" — existing record found with matching content_hash
        "changed"   — existing record found with differing content_hash
    """
    stmt = (
        select(CodeSection)
        .where(
            CodeSection.source_system == record["source_system"],
            CodeSection.citation == record["citation"],
        )
        .order_by(CodeSection.snapshot_date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is None:
        return "new"
    if existing.content_hash == record["content_hash"]:
        return "unchanged"
    return "changed"


async def detect_action_duplicate(record: dict, db: AsyncSession) -> bool:
    """Detect whether a RegulatoryAction record already exists in the DB.

    Checks for a match on (source_system, source_id), which is the unique
    key for journal records per the deduplication rules.

    Returns:
        True  — record already exists (is a duplicate; skip)
        False — record is new (safe to ingest)
    """
    stmt = (
        select(RegulatoryAction)
        .where(
            RegulatoryAction.source_system == record["source_system"],
            RegulatoryAction.source_id == record["source_id"],
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    return existing is not None


async def get_current_code_section(
    source_system: str, citation: str, db: AsyncSession
) -> CodeSection | None:
    """Return the most recent CodeSection for a given (source_system, citation).

    Used by the stitching engine to find the current snapshot when linking
    a RegulatoryAction's cfr_references to its corresponding CodeSection.

    Returns:
        The most recent CodeSection, or None if no record exists.
    """
    stmt = (
        select(CodeSection)
        .where(
            CodeSection.source_system == source_system,
            CodeSection.citation == citation,
        )
        .order_by(CodeSection.snapshot_date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
