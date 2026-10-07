import logging
import re
from datetime import date, datetime, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    pass


def _validate_date(field_name: str, value) -> None:
    """Accept date, datetime, or ISO string (YYYY-MM-DD). Raise ValidationError if unparseable."""
    if isinstance(value, (date, datetime)):
        return
    if isinstance(value, str):
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return
        except ValueError:
            raise ValidationError(
                f"Field '{field_name}' has invalid date format '{value}'; expected YYYY-MM-DD."
            )
    raise ValidationError(
        f"Field '{field_name}' must be a date, datetime, or YYYY-MM-DD string; got {type(value).__name__}."
    )


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

_CODE_SECTION_SOURCE_SYSTEMS = {"cfr", "iac"}
_REGULATORY_ACTION_SOURCE_SYSTEMS = {
    "federal_register",
    "iurc_rulemakings",
    "iurc_gaos",
    "iurc_investigations",
    "idem_rulemakings",
}
_JURISDICTION_LEVELS = {"federal", "state", "local", "international"}
_STATUSES = {"in_progress", "approved", "blocked_suspended"}

_CODE_SECTION_DATE_FIELDS = {"effective_date", "snapshot_date", "repealed_date"}
_REGULATORY_ACTION_DATE_FIELDS = {
    "date_effective",
    "date_published",
    "date_comment_close",
    "date_filed",
}


def validate_record(record: dict, record_type: str) -> bool:
    """
    Validate a record dict against the CodeSection or RegulatoryAction schema.

    Parameters
    ----------
    record : dict
        The raw record to validate.
    record_type : str
        Either ``"code_section"`` or ``"regulatory_action"``.

    Returns
    -------
    bool
        ``True`` when the record is valid.

    Raises
    ------
    ValidationError
        With a descriptive message when any constraint is violated.

    Notes
    -----
    Regulatory action date fields validated: date_effective, date_published,
    date_comment_close, date_filed.
    Code section date fields validated: effective_date, snapshot_date, repealed_date.
    """
    if record_type == "code_section":
        _validate_code_section(record)
    elif record_type == "regulatory_action":
        _validate_regulatory_action(record)
    else:
        raise ValidationError(
            f"Unknown record_type '{record_type}'. Expected 'code_section' or 'regulatory_action'."
        )
    return True


def _require(record: dict, field: str) -> None:
    """Raise ValidationError if field is absent or None."""
    if record.get(field) is None:
        raise ValidationError(f"Required field '{field}' is missing or None.")


def _validate_enum(record: dict, field: str, allowed: set) -> None:
    """Raise ValidationError if field value is not in the allowed set."""
    value = record.get(field)
    if value is not None and value not in allowed:
        raise ValidationError(
            f"Field '{field}' has invalid value '{value}'. "
            f"Allowed values: {sorted(allowed)}."
        )


def _validate_hash_field(record: dict, field: str) -> None:
    """If field is present and not None, validate it is a 64-char hex string."""
    value = record.get(field)
    if value is not None and not _HASH_RE.match(str(value)):
        raise ValidationError(
            f"Field '{field}' must be a 64-character lowercase hex string; got '{value}'."
        )


def _validate_date_fields(record: dict, fields: set) -> None:
    """Validate all date-like fields that are present and not None."""
    for field in fields:
        value = record.get(field)
        if value is not None:
            _validate_date(field, value)


def _validate_code_section(record: dict) -> None:
    required_fields = [
        "citation",
        "source_system",
        "jurisdiction_level",
        "heading",
        "body_text",
        "content_hash",
        "owning_agency",
        "status",
        "snapshot_date",
    ]
    for field in required_fields:
        _require(record, field)

    _validate_enum(record, "source_system", _CODE_SECTION_SOURCE_SYSTEMS)
    _validate_enum(record, "jurisdiction_level", _JURISDICTION_LEVELS)
    _validate_enum(record, "status", _STATUSES)

    _validate_hash_field(record, "content_hash")
    _validate_date_fields(record, _CODE_SECTION_DATE_FIELDS)


def _infer_record_type(record: dict) -> str:
    """Return 'code_section' for codebook sources, else 'regulatory_action'."""
    return "code_section" if record.get("source_system") in _CODE_SECTION_SOURCE_SYSTEMS else "regulatory_action"


def _build_new_cursor(source_system: str, raw_records: list) -> dict:
    """Build an updated sync cursor after a successful ingestion run."""
    today = date.today()
    if source_system == "cfr":
        if not raw_records:
            return {}
        cursor: dict = {}
        for r in raw_records:
            title_num = r.get("title_number")
            amd = r.get("amendment_date")
            if title_num is None or not amd:
                continue
            key = f"title_{title_num}_amended_on"
            if key not in cursor or amd > cursor[key]:
                cursor[key] = amd
        return cursor
    elif source_system == "federal_register":
        dates = [r.get("publication_date") for r in raw_records if r.get("publication_date")]
        if not dates:
            return {}
        max_date = max(dates)
        return {"last_publication_date": (date.fromisoformat(max_date) + timedelta(days=1)).isoformat()}
    elif source_system == "iac":
        if not raw_records:
            return {}
        # Carry forward edition_year and snapshot_date from the records themselves
        first = raw_records[0]
        return {
            "edition_year": first.get("edition_year", 2025),
            "snapshot_date": first.get("snapshot_date", "2024-12-31"),
        }
    elif source_system in ("iurc_rulemakings", "iurc_gaos", "idem_rulemakings"):
        # Simple date cursor — re-scrape if stale (>7 days)
        return {"last_scraped": date.today().isoformat()}
    elif source_system == "iurc_investigations":
        # Track last weekly filings list date checked
        return {"last_fetched_week": date.today().isoformat()}
    else:
        return {}


async def _retroactive_stitch(db: AsyncSession) -> int:
    """Find CodeSections with no amendment_source and try to stitch them retroactively."""
    from sqlalchemy import select
    from app.regulatory.models.code_section import CodeSection
    from app.regulatory.ingestion.stitcher import stitch_codebook_to_action

    # Find up to 100 unlinked CodeSections (most recent first)
    stmt = (
        select(CodeSection)
        .where(CodeSection.amendment_source == None)
        .order_by(CodeSection.snapshot_date.desc())
        .limit(100)
    )
    result = await db.execute(stmt)
    unlinked = result.scalars().all()

    linked = 0
    for cs in unlinked:
        n = await stitch_codebook_to_action(cs, db)
        linked += n
    return linked


async def run_ingestion(adapter, db: AsyncSession) -> dict:
    """
    Runs a full ingestion cycle for one adapter.
    Returns summary: {"new": N, "changed": N, "unchanged": N, "skipped": N, "errors": N}
    """
    from app.regulatory.ingestion.change_detector import detect_changes, detect_action_duplicate
    from app.regulatory.ingestion.version_chain import create_version_chain, store_regulatory_action
    from app.regulatory.ingestion.stitcher import stitch_action_to_codebook, stitch_action_chains, stitch_codebook_to_action

    summary = {"new": 0, "changed": 0, "unchanged": 0, "skipped": 0, "errors": 0}

    # 1. Get sync cursor
    cursor = await adapter.get_sync_cursor(db)

    # 2. Poll for raw records
    raw_records = await adapter.poll(cursor)

    # 3. Process each record
    for raw in raw_records:
        try:
            # Normalize
            record = adapter.normalize(raw)
            if record is None:
                summary["skipped"] += 1
                continue

            # Determine record type from source_system
            record_type = _infer_record_type(record)

            # Validate
            validate_record(record, record_type)

            if record_type == "code_section":
                change = await detect_changes(record, db)
                if change == "unchanged":
                    summary["unchanged"] += 1
                    continue
                stored_section = await create_version_chain(record, db)
                # Stitch: find the FR action that caused this change
                await stitch_codebook_to_action(stored_section, db)
                # Embed: store vector representation in Qdrant
                try:
                    from app.regulatory.ingestion.embedder import embed_and_store_code_section
                    from app.services.vector import get_qdrant_client
                    qdrant = get_qdrant_client()
                    embed_and_store_code_section(
                        record_id=stored_section.id,
                        citation=stored_section.citation,
                        source_system=stored_section.source_system,
                        heading=stored_section.heading or "",
                        body_text=stored_section.body_text or "",
                        agency=stored_section.owning_agency or "",
                        status=stored_section.status or "approved",
                        jurisdiction_level=stored_section.jurisdiction_level or "federal",
                        qdrant_client=qdrant,
                        title_number=stored_section.title_number or "",
                        part=stored_section.part or "",
                        subpart=getattr(stored_section, "subpart", "") or "",
                        section_number=getattr(stored_section, "section_number", "") or "",
                        snapshot_date=str(stored_section.snapshot_date) if stored_section.snapshot_date else "",
                    )
                except Exception as e:
                    logger.error(
                        "embed failed for %s %s: %s",
                        stored_section.source_system,
                        stored_section.id,
                        e,
                        exc_info=True,
                    )
                if change == "new":
                    summary["new"] += 1
                else:
                    summary["changed"] += 1

            elif record_type == "regulatory_action":
                is_dup = await detect_action_duplicate(record, db)
                if is_dup:
                    summary["skipped"] += 1
                    continue
                stored_action = await store_regulatory_action(record, db)
                # Stitch: link this action to codebook sections via cfr_references
                await stitch_action_to_codebook(stored_action, db)
                # Stitch: link this action to related actions via RIN/docket
                await stitch_action_chains(stored_action, db)
                # Embed: store vector representation in Qdrant
                try:
                    from app.regulatory.ingestion.embedder import embed_and_store_action
                    from app.services.vector import get_qdrant_client
                    qdrant = get_qdrant_client()
                    embed_and_store_action(
                        record_id=stored_action.id,
                        source_id=stored_action.source_id,
                        source_system=stored_action.source_system,
                        title=stored_action.title or "",
                        abstract=stored_action.abstract or "",
                        agency=stored_action.agency or "",
                        status=stored_action.status or "in_progress",
                        action_type=stored_action.action_type or "",
                        qdrant_client=qdrant,
                    )
                except Exception as e:
                    logger.error(
                        "embed failed for %s %s: %s",
                        stored_action.source_system,
                        stored_action.id,
                        e,
                        exc_info=True,
                    )
                summary["new"] += 1

        except Exception as e:
            summary["errors"] += 1
            print(f"[ingestion error] {adapter.source_system}: {e}")
            try:
                await db.rollback()
            except Exception:
                pass
            continue

    # 4. Post-ingestion retroactive stitch: handle timing gaps (eCFR lags FR by 1-2 days)
    # Find CodeSections without amendment_source and try to link them
    await _retroactive_stitch(db)

    # 5. Commit all changes
    await db.commit()

    # 6. Update sync cursor (after successful commit)
    new_cursor = _build_new_cursor(adapter.source_system, raw_records)
    if new_cursor:
        if adapter.source_system == "cfr":
            # Merge: preserve existing title keys, drop as_of_date (historical mode key)
            merged = {k: v for k, v in cursor.items() if k != "as_of_date"}
            merged.update(new_cursor)
            new_cursor = merged
        await adapter.update_sync_cursor(db, new_cursor)
        await db.commit()

    return summary


def _validate_regulatory_action(record: dict) -> None:
    required_fields = [
        "source_id",
        "source_system",
        "jurisdiction_level",
        "action_type",
        "title",
        "agency",
        "status",
        "source_url",
        "adapter_version",
    ]
    for field in required_fields:
        _require(record, field)

    _validate_enum(record, "source_system", _REGULATORY_ACTION_SOURCE_SYSTEMS)
    _validate_enum(record, "jurisdiction_level", _JURISDICTION_LEVELS)
    _validate_enum(record, "status", _STATUSES)

    _validate_hash_field(record, "content_hash")
    _validate_date_fields(record, _REGULATORY_ACTION_DATE_FIELDS)
