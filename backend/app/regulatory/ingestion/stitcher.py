import re
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_, text
from app.regulatory.models.code_section import CodeSection
from app.regulatory.models.regulatory_action import RegulatoryAction
from app.regulatory.models.relationship import ActionRelationship
from app.regulatory.ingestion.change_detector import get_current_code_section

# Only final/amending actions cause codebook text changes and should set amendment_source.
_AMENDING_ACTION_TYPES = frozenset({
    "final_rule",
    "interim_final_rule",
    "direct_final_rule",
    "correction",
})

# State systems where we stitch by source_system regardless of action_type
# (Indiana rulemakings are ingested as 'proposed_rule' even when final).
_STATE_AMENDING_SYSTEMS = frozenset({
    "iurc_rulemakings",
    "idem_rulemakings",
})


def infer_codebook(citation: str) -> str:
    """Infer the source_system (codebook) from a citation string.

    - IAC citations contain ' IAC ' (e.g. '170 IAC 4-1-6') → 'iac'
    - CFR citations start with digits (e.g. '18 CFR 35.28') → 'cfr'
    - Default → 'cfr'
    """
    if citation and " IAC " in citation:
        return "iac"
    if citation and citation[0].isdigit():
        return "cfr"
    return "cfr"


def _dates_align(
    action_date: object,
    section_date: object,
    window_days: int = 365,
) -> bool:
    """Return True if the action date precedes or closely follows the section date.

    Logic:
    - Both None → False (no information, don't assume alignment).
    - One None → True (give benefit of the doubt; eCFR lags FR).
    - Otherwise one-directional: the action date must be at most window_days
      before the section date.  A small forward tolerance of 7 days is allowed
      to absorb eCFR publication lag (eCFR sometimes captures the snapshot a
      few days before the FR effective date lands).

    The window_days default was raised from 30 to 365 so that a CFR snapshot
    taken up to a year after a Federal Register action still links correctly.
    Pass action.date_effective or action.date_published (coalesced) as
    action_date so that actions with no date_effective still participate.
    """
    if action_date is None and section_date is None:
        return False  # both unknown — don't assume alignment
    if action_date is None or section_date is None:
        return True   # one unknown — give benefit of the doubt (eCFR lags FR)
    # delta > 0 means action is before section (the normal case)
    delta = (section_date - action_date).days
    return -7 <= delta <= window_days


async def _get_sections_by_part_prefix(
    source_system: str, part_citation: str, db: AsyncSession
) -> list:
    """Return all CodeSections whose citation starts with part_citation followed by '.' or '-'.

    CFR uses dots: "18 CFR 35" → matches "18 CFR 35.1", "18 CFR 35.28", etc.
    IAC uses dashes: "170 IAC 4" → matches "170 IAC 4-1-1", "170 IAC 4-2-3", etc.
    """
    dot_prefix = part_citation + "."
    dash_prefix = part_citation + "-"
    stmt = (
        select(CodeSection)
        .where(
            CodeSection.source_system == source_system,
            or_(
                CodeSection.citation.like(dot_prefix + "%"),
                CodeSection.citation.like(dash_prefix + "%"),
            ),
        )
        .order_by(CodeSection.snapshot_date.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def stitch_action_to_codebook(
    action: RegulatoryAction, db: AsyncSession
) -> int:
    """Link a RegulatoryAction's cfr_references to matching CodeSection records.

    For each citation in action.cfr_references:
      - First tries an exact match via get_current_code_section.
      - If not found (part-level reference like '40 CFR 63'), falls back to
        prefix matching against all sections in that part.
      - If the CodeSection has no amendment_source yet and the dates align
        (within 365 days, or either date is None), sets amendment_source to
        action.source_id.

    The action date used is date_effective coalesced with date_published so
    that actions without a separate effective date still participate.

    Returns the number of CodeSections updated.
    """
    if not action.cfr_references:
        return 0
    if action.action_type not in _AMENDING_ACTION_TYPES:
        return 0

    # Coalesce: prefer date_effective, fall back to date_published
    action_date = action.date_effective or action.date_published

    updated = 0
    for citation in action.cfr_references:
        codebook = infer_codebook(citation)

        # Try exact match first
        exact_section = await get_current_code_section(codebook, citation, db)
        if exact_section is not None:
            if exact_section.amendment_source is None and _dates_align(
                action_date, exact_section.effective_date
            ):
                exact_section.amendment_source = action.source_id
                db.add(exact_section)
                updated += 1
            continue

        # Fall back to part-level prefix matching (FR refs are typically part-level)
        sections = await _get_sections_by_part_prefix(codebook, citation, db)
        for code_section in sections:
            if code_section.amendment_source is not None:
                continue
            if _dates_align(action_date, code_section.effective_date):
                code_section.amendment_source = action.source_id
                db.add(code_section)
                updated += 1

    if updated:
        await db.flush()

    return updated


async def stitch_codebook_to_action(
    code_section: CodeSection, db: AsyncSession
) -> int:
    """Reverse stitch — find the FR action that caused a newly ingested CodeSection.

    If code_section.amendment_source is already set, skips immediately.
    Otherwise queries RegulatoryAction records whose cfr_references contain
    code_section.citation. For each candidate, checks date alignment
    (within 30 days, or either date is None). Sets amendment_source on the
    first aligned match.

    Falls back to a part-level query when the exact citation finds no match,
    because Federal Register stores part-level refs (e.g. "18 CFR 35") while
    code sections use section-level citations (e.g. "18 CFR 35.28").

    Returns 1 if linked, 0 if not.
    """
    if code_section.amendment_source is not None:
        return 0

    stmt = (
        select(RegulatoryAction)
        .where(
            RegulatoryAction.cfr_references.any(code_section.citation),
            RegulatoryAction.action_type.in_(_AMENDING_ACTION_TYPES),
        )
        .order_by(RegulatoryAction.date_effective.desc().nulls_last())
    )
    result = await db.execute(stmt)
    candidates = result.scalars().all()

    for action in candidates:
        action_date = action.date_effective or action.date_published
        if _dates_align(action_date, code_section.effective_date):
            code_section.amendment_source = action.source_id
            db.add(code_section)
            await db.flush()
            return 1

    # Fallback: FR stores part-level refs; strip section suffix and retry
    part_prefix = code_section.citation.rsplit(".", 1)[0]
    if part_prefix == code_section.citation:
        return 0

    stmt_part = (
        select(RegulatoryAction)
        .where(
            RegulatoryAction.cfr_references.any(part_prefix),
            RegulatoryAction.action_type.in_(_AMENDING_ACTION_TYPES),
        )
        .order_by(RegulatoryAction.date_effective.desc().nulls_last())
    )
    result_part = await db.execute(stmt_part)
    part_candidates = result_part.scalars().all()

    for action in part_candidates:
        action_date = action.date_effective or action.date_published
        if _dates_align(action_date, code_section.effective_date):
            code_section.amendment_source = action.source_id
            db.add(code_section)
            await db.flush()
            return 1

    return 0


def _infer_relationship_type(
    action_a: RegulatoryAction, action_b: RegulatoryAction
) -> str:
    """Infer relationship type from the action_type fields of two actions.

    Inference table (from stitching.md):
      proposed_rule + final_rule  → 'supersedes'  (A superseded_by B)
      final_rule + correction     → 'corrects'    (B corrects A)
      final_rule + withdrawal     → 'withdraws'   (B withdraws A)
      order + responds_to         → 'responds_to' (B responds_to A)
      any + any (no match)        → 'related_to'
    """
    a = action_a.action_type
    b = action_b.action_type

    if a == "proposed_rule" and b == "final_rule":
        return "supersedes"
    if a == "final_rule" and b == "correction":
        return "corrects"
    if a == "final_rule" and b == "withdrawal":
        return "withdraws"
    if a == "order" and b == "responds_to":
        return "responds_to"
    return "related_to"


async def _create_relationship(
    from_action: RegulatoryAction,
    to_action: RegulatoryAction,
    db: AsyncSession,
) -> bool:
    """Create an ActionRelationship record if it does not already exist.

    The relationship type is inferred via _infer_relationship_type.
    Returns True if a new record was created, False if it already existed.
    """
    relationship_type = _infer_relationship_type(from_action, to_action)

    stmt = select(ActionRelationship).where(
        ActionRelationship.from_action_id == from_action.id,
        ActionRelationship.to_action_id == to_action.id,
        ActionRelationship.relationship_type == relationship_type,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        return False

    db.add(
        ActionRelationship(
            from_action_id=from_action.id,
            to_action_id=to_action.id,
            relationship_type=relationship_type,
            created_at=datetime.utcnow(),
        )
    )
    await db.flush()
    return True


async def stitch_action_chains(action: RegulatoryAction, db: AsyncSession) -> int:
    """Link a RegulatoryAction to related actions via RIN, docket IDs, and explicit refs.

    1. RIN-based: find all other actions with the same RIN and create relationships.
    2. Docket-based: find actions sharing any docket_id not already linked.
    3. Explicit related_actions: look up each entry by (source_system, source_id)
       and create the relationship with the given type.

    Returns total count of new relationships created.
    """
    created = 0
    linked_ids: set[int] = set()

    # --- 1. RIN-based linking ---
    if action.rin is not None:
        stmt = select(RegulatoryAction).where(
            RegulatoryAction.rin == action.rin,
            RegulatoryAction.id != action.id,
        )
        result = await db.execute(stmt)
        rin_matches = result.scalars().all()
        for related in rin_matches:
            if await _create_relationship(action, related, db):
                created += 1
            linked_ids.add(related.id)

    # --- 2. Docket-based linking ---
    # Docket-linked pairs always get 'related_to' (no sequence known).
    if action.docket_ids:
        for docket_id in action.docket_ids:
            stmt = select(RegulatoryAction).where(
                RegulatoryAction.docket_ids.any(docket_id),
                RegulatoryAction.id != action.id,
            )
            result = await db.execute(stmt)
            docket_matches = result.scalars().all()
            for related in docket_matches:
                if related.id in linked_ids:
                    continue
                stmt_check = select(ActionRelationship).where(
                    ActionRelationship.from_action_id == action.id,
                    ActionRelationship.to_action_id == related.id,
                    ActionRelationship.relationship_type == "related_to",
                )
                check_result = await db.execute(stmt_check)
                if check_result.scalar_one_or_none() is None:
                    db.add(
                        ActionRelationship(
                            from_action_id=action.id,
                            to_action_id=related.id,
                            relationship_type="related_to",
                            created_at=datetime.utcnow(),
                        )
                    )
                    await db.flush()
                    created += 1
                linked_ids.add(related.id)

    # --- 3. Explicit related_actions from source ---
    if action.related_actions is not None:
        # related_actions may be stored as a list of entry dicts or a dict with a list
        entries = action.related_actions
        if isinstance(entries, dict):
            entries = list(entries.values())
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            src_system = entry.get("source_system")
            src_id = entry.get("source_id")
            rel_type = entry.get("relationship_type", "related_to")
            if not src_system or not src_id:
                continue
            stmt = select(RegulatoryAction).where(
                RegulatoryAction.source_system == src_system,
                RegulatoryAction.source_id == src_id,
            )
            result = await db.execute(stmt)
            target = result.scalar_one_or_none()
            if target is None:
                continue

            # Use the explicit relationship type instead of inferring
            stmt_check = select(ActionRelationship).where(
                ActionRelationship.from_action_id == action.id,
                ActionRelationship.to_action_id == target.id,
                ActionRelationship.relationship_type == rel_type,
            )
            check_result = await db.execute(stmt_check)
            if check_result.scalar_one_or_none() is not None:
                continue

            db.add(
                ActionRelationship(
                    from_action_id=action.id,
                    to_action_id=target.id,
                    relationship_type=rel_type,
                    created_at=datetime.utcnow(),
                )
            )
            await db.flush()
            created += 1

    return created


async def _stitch_idem_via_din(action: RegulatoryAction, db: AsyncSession) -> int:
    """Link an IDEM rulemaking to IAC sections via DIN-encoded LSA number.

    IDEM rulemakings have source_id like "LSA-YY-NNN" and abstracts like
    "IDEM Environmental Rules Board rulemaking: Title TTT ... Rule".

    IAC section 'dins' records the Document Index Numbers of each amendment,
    embedding the IAC title and LSA number in a fixed 9-character fragment:
      YYYYMMDD-IR-{TITLE3D}{YEAR2D}{LSA4D}{TYPE}
    e.g. "20241113-IR-326230809RFA" for LSA-23-809 (Title 326).

    For IDEM source_id "LSA-YY-NNN" with title TTT extracted from abstract,
    the DIN fragment is "{TTT}{YY}{NNN:04d}".  Matching is narrow and
    verifiable — it finds only sections that were directly amended by that LSA.

    Returns the number of CodeSections updated.
    """
    if action.source_system != "idem_rulemakings":
        return 0

    # Extract IAC title number from abstract: e.g. "Title 326 ..."
    abstract = action.abstract or ""
    title_match = re.search(r"\bTitle\s+(\d{3})\b", abstract)
    if not title_match:
        return 0
    title = title_match.group(1)  # e.g. "326"

    # Extract year and LSA number from source_id: "LSA-YY-NNN"
    lsa_match = re.match(r"LSA-(\d{2})-(\d+)$", action.source_id or "")
    if not lsa_match:
        return 0
    year = lsa_match.group(1)
    lsa_num = int(lsa_match.group(2))

    # 9-char fragment embedded in every DIN that records this LSA
    din_fragment = f"{title}{year}{lsa_num:04d}"  # e.g. "326230809"

    # Use date_published; state rulemakings have no date_effective
    action_date = action.date_published

    stmt = (
        select(CodeSection)
        .where(
            CodeSection.source_system == "iac",
            CodeSection.title_number == title,
            CodeSection.amendment_source.is_(None),
            text("EXISTS (SELECT 1 FROM unnest(dins) AS d WHERE d LIKE :din_pat)").bindparams(
                din_pat=f"%-IR-{din_fragment}%"
            ),
        )
        .order_by(CodeSection.snapshot_date.desc())
    )
    result = await db.execute(stmt)
    sections = result.scalars().all()

    updated = 0
    for cs in sections:
        # Temporal guard: rulemaking must precede (or be same day as) the snapshot
        if action_date is not None and cs.snapshot_date is not None:
            if action_date > cs.snapshot_date:
                continue
        cs.amendment_source = action.source_id
        db.add(cs)
        updated += 1

    if updated:
        await db.flush()

    return updated


async def stitch_state_action_to_iac(
    action: RegulatoryAction, db: AsyncSession
) -> int:
    """Link an IURC or IDEM rulemaking's IAC references to matching IAC CodeSections.

    Unlike stitch_action_to_codebook, this function:
    - Accepts any action_type (state systems use 'proposed_rule' for all rulemakings).
    - Only processes actions from _STATE_AMENDING_SYSTEMS.
    - Only processes IAC citations (those containing ' IAC ').
    - Combines cfr_references and legal_refs, deduped, to find all IAC refs.
    - Matches IAC CodeSections by dash-prefix (e.g. '170 IAC 4' → '170 IAC 4-*').
    - Temporal guard: action.date_published must be <= section.snapshot_date so
      that a 2026 rulemaking does not claim credit for a 2024 or 2025 snapshot.
    - Does NOT overwrite existing amendment_source values.

    Returns the number of CodeSections updated.
    """
    if action.source_system not in _STATE_AMENDING_SYSTEMS:
        return 0

    # Combine cfr_references and legal_refs, preserving order, deduped
    refs: list[str] = []
    seen: set[str] = set()
    for ref_list in (action.cfr_references or [], action.legal_refs or []):
        for ref in ref_list:
            if ref not in seen:
                refs.append(ref)
                seen.add(ref)

    iac_refs = [r for r in refs if " IAC " in r]
    if not iac_refs:
        # IDEM rulemakings carry no IAC refs in legal_refs/cfr_references.
        # Fall back to DIN-based matching via the LSA number encoded in section dins.
        if action.source_system == "idem_rulemakings":
            return await _stitch_idem_via_din(action, db)
        return 0

    # Use date_published; date_effective is always None for state rulemakings
    action_date = action.date_published

    updated = 0
    for citation in iac_refs:
        # IAC uses dashes: "170 IAC 4" + "-" → "170 IAC 4-1-1", "170 IAC 4-10-2", …
        dash_prefix = citation + "-"
        stmt = (
            select(CodeSection)
            .where(
                CodeSection.source_system == "iac",
                CodeSection.amendment_source.is_(None),
                or_(
                    CodeSection.citation == citation,
                    CodeSection.citation.like(dash_prefix + "%"),
                ),
            )
            .order_by(CodeSection.snapshot_date.desc())
        )
        result = await db.execute(stmt)
        sections = result.scalars().all()

        for cs in sections:
            # Temporal guard: rulemaking must precede (or be same day as) the snapshot
            if action_date is not None and cs.snapshot_date is not None:
                if action_date > cs.snapshot_date:
                    continue
            cs.amendment_source = action.source_id
            db.add(cs)
            updated += 1

    if updated:
        await db.flush()

    return updated


async def run_all_stitching() -> dict:
    """Bulk stitching pass over all existing data.  Opens its own session and commits.

    Passes:
    1. All FR amending actions → stitch to CFR sections (action→codebook direction).
    2. All still-unlinked CFR sections → reverse-stitch to FR actions.
    3. All IURC/IDEM actions → stitch to IAC sections.
       IURC: matched via IAC citation refs in legal_refs.
       IDEM: matched via DIN-encoded LSA number in IAC section dins (see
             _stitch_idem_via_din).

    Idempotent: every helper skips sections that already have amendment_source set,
    so a second run produces 0 new links.

    CFR data-gap ceiling (~48.5%): 108 of 170 unlinked CFR sections have no
    matching FR action in the DB for their part (40 CFR 72/73 etc.); 61 have FR
    actions that all post-date the section snapshot (baseline pre-data-window
    snapshots); and 1 section falls just outside the 365-day window.  These are
    ingestion-coverage gaps, not stitcher bugs.

    IAC titles 610 and 675 are at 0% linkage because no rulemakings for those
    titles are present in the iurc_rulemakings or idem_rulemakings tables — a
    data gap at the adapter level, not in the stitcher.

    action_relationships (state↔federal): No verifiable cross-links exist between
    IURC/IDEM rulemakings and FR actions.  IURC refs are 170 IAC only; IDEM has
    no IAC/CFR refs; FR Indiana SIP approvals reference IAC by article only (no
    LSA numbers).  Cross-links would require topic-similarity heuristics.

    Returns a dict with update counts per pass.
    """
    from app.db import AsyncSessionLocal

    stats: dict[str, int] = {}

    async with AsyncSessionLocal() as db:
        # --- Pass 1: FR actions → CFR sections ---
        stmt_fr = (
            select(RegulatoryAction)
            .where(
                RegulatoryAction.source_system == "federal_register",
                RegulatoryAction.action_type.in_(_AMENDING_ACTION_TYPES),
            )
        )
        result_fr = await db.execute(stmt_fr)
        fr_actions = result_fr.scalars().all()
        fr_to_cfr = 0
        for action in fr_actions:
            fr_to_cfr += await stitch_action_to_codebook(action, db)
        stats["fr_to_cfr"] = fr_to_cfr

        # --- Pass 2: Unlinked CFR sections → FR actions (reverse) ---
        stmt_cfr = (
            select(CodeSection)
            .where(
                CodeSection.source_system == "cfr",
                CodeSection.amendment_source.is_(None),
            )
        )
        result_cfr = await db.execute(stmt_cfr)
        cfr_sections = result_cfr.scalars().all()
        cfr_reverse = 0
        for cs in cfr_sections:
            cfr_reverse += await stitch_codebook_to_action(cs, db)
        stats["cfr_reverse"] = cfr_reverse

        # --- Pass 3: State rulemakings → IAC sections ---
        stmt_state = (
            select(RegulatoryAction)
            .where(
                RegulatoryAction.source_system.in_(_STATE_AMENDING_SYSTEMS),
            )
        )
        result_state = await db.execute(stmt_state)
        state_actions = result_state.scalars().all()
        state_to_iac = 0
        for action in state_actions:
            state_to_iac += await stitch_state_action_to_iac(action, db)
        stats["state_to_iac"] = state_to_iac

        await db.commit()

    print(f"run_all_stitching complete: {stats}")
    return stats
