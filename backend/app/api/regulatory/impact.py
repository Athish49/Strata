from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from typing import Optional
from datetime import date, timedelta
from app.db import get_db
from app.regulatory.models.regulatory_action import RegulatoryAction
from app.regulatory.models.code_section import CodeSection

router = APIRouter(prefix="/impact", tags=["impact"])


@router.get("/cross-agency")
async def cross_agency_correlations(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Find pairs of actions from different agencies sharing CFR references or affected entities."""
    stmt = select(RegulatoryAction)
    filters = []
    if date_from:
        filters.append(RegulatoryAction.date_published >= date_from)
    if date_to:
        filters.append(RegulatoryAction.date_published <= date_to)
    if filters:
        stmt = stmt.where(and_(*filters))

    result = await db.execute(stmt)
    actions = result.scalars().all()

    # Group by CFR reference
    cfr_map: dict[str, list] = {}
    for action in actions:
        for ref in (action.cfr_references or []):
            cfr_map.setdefault(ref, []).append(action)

    correlations = []
    seen_pairs: set[tuple] = set()

    for ref, ref_actions in cfr_map.items():
        # Find distinct agencies in this group
        agency_actions: dict[str, list] = {}
        for a in ref_actions:
            agency_actions.setdefault(a.agency, []).append(a)

        agencies = list(agency_actions.keys())
        if len(agencies) < 2:
            continue

        # Emit one correlation per unique agency pair
        for i in range(len(agencies)):
            for j in range(i + 1, len(agencies)):
                ag1, ag2 = agencies[i], agencies[j]
                # Pick one representative action from each agency
                a1 = agency_actions[ag1][0]
                a2 = agency_actions[ag2][0]
                pair_key = tuple(sorted([a1.source_id, a2.source_id]) + [ref])
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                correlations.append({
                    "correlation_type": "cfr_reference",
                    "shared_references": [ref],
                    "actions": [
                        {
                            "source_id": a1.source_id,
                            "agency": a1.agency,
                            "title": a1.title,
                            "date_published": a1.date_published.isoformat() if a1.date_published else None,
                        },
                        {
                            "source_id": a2.source_id,
                            "agency": a2.agency,
                            "title": a2.title,
                            "date_published": a2.date_published.isoformat() if a2.date_published else None,
                        },
                    ],
                })

    # Pass 2 — Shared affected entities
    # Populated for: FR/EPA state-name rows (~432) and IURC investigation utility names (~50)
    entity_map: dict[str, list] = {}
    for action in actions:
        for ent in (action.affected_entities or []):
            entity_map.setdefault(ent.lower(), []).append(action)

    for entity, ent_actions in entity_map.items():
        agency_actions: dict[str, list] = {}
        for a in ent_actions:
            agency_actions.setdefault(a.agency, []).append(a)
        agencies = list(agency_actions.keys())
        if len(agencies) < 2:
            continue
        for i in range(len(agencies)):
            for j in range(i + 1, len(agencies)):
                ag1, ag2 = agencies[i], agencies[j]
                a1 = agency_actions[ag1][0]
                a2 = agency_actions[ag2][0]
                pair_key = tuple(sorted([a1.source_id, a2.source_id]) + ["entity:" + entity])
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                correlations.append({
                    "correlation_type": "shared_entity",
                    "shared_entity": entity,
                    "actions": [
                        {"source_id": a1.source_id, "agency": a1.agency, "title": a1.title,
                         "date_published": a1.date_published.isoformat() if a1.date_published else None},
                        {"source_id": a2.source_id, "agency": a2.agency, "title": a2.title,
                         "date_published": a2.date_published.isoformat() if a2.date_published else None},
                    ],
                })

    # Pass 3 — Temporal proximity (±30 days, different agencies)
    dated_actions = [a for a in actions if a.date_published]
    dated_actions.sort(key=lambda a: a.date_published)
    for i, a1 in enumerate(dated_actions):
        for a2 in dated_actions[i + 1:]:
            if (a2.date_published - a1.date_published).days > 30:
                break
            if a1.agency == a2.agency:
                continue
            pair_key = tuple(sorted([a1.source_id, a2.source_id]) + ["temporal"])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            correlations.append({
                "correlation_type": "temporal_proximity",
                "days_apart": (a2.date_published - a1.date_published).days,
                "actions": [
                    {"source_id": a1.source_id, "agency": a1.agency, "title": a1.title,
                     "date_published": a1.date_published.isoformat()},
                    {"source_id": a2.source_id, "agency": a2.agency, "title": a2.title,
                     "date_published": a2.date_published.isoformat()},
                ],
            })

    return {"correlations": correlations, "total": len(correlations)}


@router.get("/agency/{agency_id}")
async def actions_by_agency(
    agency_id: str,
    days_back: int = Query(90, ge=1),
    status: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return recent actions from one agency, sorted by date_published DESC."""
    cutoff = date.today() - timedelta(days=days_back)
    filters = [
        RegulatoryAction.agency == agency_id,
        RegulatoryAction.date_published >= cutoff,
    ]
    if status:
        filters.append(RegulatoryAction.status == status)
    if action_type:
        filters.append(RegulatoryAction.action_type == action_type)

    stmt = (
        select(RegulatoryAction)
        .where(and_(*filters))
        .order_by(RegulatoryAction.date_published.desc())
    )
    result = await db.execute(stmt)
    actions = result.scalars().all()

    def _serialize(a: RegulatoryAction) -> dict:
        return {
            "id": a.id,
            "source_id": a.source_id,
            "source_system": a.source_system,
            "agency": a.agency,
            "title": a.title,
            "action_type": a.action_type,
            "status": a.status,
            "date_published": a.date_published.isoformat() if a.date_published else None,
            "date_effective": a.date_effective.isoformat() if a.date_effective else None,
            "cfr_references": a.cfr_references,
            "affected_entities": a.affected_entities,
            "source_url": a.source_url,
        }

    return {
        "agency_id": agency_id,
        "actions": [_serialize(a) for a in actions],
        "total": len(actions),
    }


@router.get("/{entity}")
async def actions_affecting_entity(
    entity: str,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return all actions affecting a named entity (company/organization)."""
    # PostgreSQL ARRAY contains check — case-insensitive via lower()
    # Populated for FR/EPA (state names) and IURC investigations (utility names)
    filters = [
        RegulatoryAction.affected_entities.any(entity.lower())
    ]
    if date_from:
        filters.append(RegulatoryAction.date_published >= date_from)
    if date_to:
        filters.append(RegulatoryAction.date_published <= date_to)

    stmt = (
        select(RegulatoryAction)
        .where(and_(*filters))
        .order_by(RegulatoryAction.date_published.desc())
    )
    result = await db.execute(stmt)
    actions = result.scalars().all()

    def _serialize(a: RegulatoryAction) -> dict:
        return {
            "id": a.id,
            "source_id": a.source_id,
            "source_system": a.source_system,
            "agency": a.agency,
            "title": a.title,
            "action_type": a.action_type,
            "status": a.status,
            "date_published": a.date_published.isoformat() if a.date_published else None,
            "date_effective": a.date_effective.isoformat() if a.date_effective else None,
            "cfr_references": a.cfr_references,
            "affected_entities": a.affected_entities,
            "source_url": a.source_url,
        }

    return {
        "entity": entity,
        "actions": [_serialize(a) for a in actions],
        "total": len(actions),
    }
