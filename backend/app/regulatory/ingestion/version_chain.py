from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.regulatory.models.code_section import CodeSection
from app.regulatory.models.regulatory_action import RegulatoryAction


def _to_date(value) -> date | None:
    """Convert a string 'YYYY-MM-DD', a date object, or None to a date (or None)."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


async def create_version_chain(record: dict, db: AsyncSession) -> CodeSection:
    """Create a new CodeSection snapshot, linking it to the previous version if one exists.

    Steps:
    1. Find the most recent CodeSection with matching (source_system, citation).
    2. Create a new CodeSection from the record dict.
    3. If a prior version exists, set new_section.prior_version_id = previous.id.
    4. db.add and await db.flush() to get the new ID without committing.
    5. Return the new CodeSection.
    """
    # 1. Find existing (previous) version
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
    previous = result.scalar_one_or_none()

    # 2. Build new CodeSection
    new_section = CodeSection(
        citation=record["citation"],
        source_system=record["source_system"],
        jurisdiction_level=record["jurisdiction_level"],
        jurisdiction_geo=record.get("jurisdiction_geo"),
        title_number=record.get("title_number"),
        part=record.get("part"),
        section_number=record.get("section_number"),
        subpart=record.get("subpart"),
        heading=record["heading"],
        body_text=record["body_text"],
        content_hash=record["content_hash"],
        owning_agency=record["owning_agency"],
        effective_date=_to_date(record.get("effective_date")),
        status=record["status"],
        snapshot_date=_to_date(record.get("snapshot_date")),
        source_url=record.get("source_url"),
        amendment_source=record.get("amendment_source"),
        superseded_by=record.get("superseded_by"),
        repealed_date=_to_date(record.get("repealed_date")),
        federal_refs=record.get("federal_refs") or [],
        iac_cross_refs=record.get("iac_cross_refs") or [],
        dins=record.get("dins") or [],
        ingested_at=record.get("ingested_at") or datetime.utcnow(),
    )

    # 3. Link to previous version if one exists
    if previous is not None:
        new_section.prior_version_id = previous.id

    # 4. Persist (flush to get ID, without committing)
    db.add(new_section)
    await db.flush()

    return new_section


async def store_regulatory_action(record: dict, db: AsyncSession) -> RegulatoryAction:
    """Store a new RegulatoryAction (immutable — no version chain).

    Steps:
    1. Create a new RegulatoryAction from the record dict.
    2. db.add and await db.flush() to get the ID without committing.
    3. Return the action.
    """
    action = RegulatoryAction(
        source_id=record["source_id"],
        source_system=record["source_system"],
        jurisdiction_level=record["jurisdiction_level"],
        jurisdiction_geo=record.get("jurisdiction_geo"),
        action_type=record["action_type"],
        source_type=record.get("source_type"),
        action_text=record.get("action_text"),
        title=record["title"],
        abstract=record.get("abstract"),
        agency=record["agency"],
        status=record["status"],
        date_published=_to_date(record.get("date_published")),
        date_effective=_to_date(record.get("date_effective")),
        date_comment_close=_to_date(record.get("date_comment_close")),
        date_filed=_to_date(record.get("date_filed")),
        docket_ids=record.get("docket_ids"),
        rin=record.get("rin"),
        cfr_references=record.get("cfr_references"),
        legal_refs=record.get("legal_refs"),
        affected_entities=record.get("affected_entities"),
        related_actions=record.get("related_actions"),
        source_url=record["source_url"],
        full_text_url=record.get("full_text_url"),
        ingested_at=record.get("ingested_at") or datetime.utcnow(),
        adapter_version=record.get("adapter_version", "1.0"),
    )

    db.add(action)
    await db.flush()

    return action
