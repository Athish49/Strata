"""Radar route (api_ui.md section 1): GET /engine/runs/{run_id}/radar. Mounted by routes.py."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.engine.routes import _all, _get_run
from app.db import get_db
from app.engine.schemas import RadarItem

router = APIRouter()

_ORDER = "CASE r.applicable WHEN 'yes' THEN 0 WHEN 'unclear' THEN 1 ELSE 2 END"


@router.get("/runs/{run_id}/radar", response_model=list[RadarItem])
async def get_radar(run_id: str, applicable: Optional[str] = Query(None, pattern="^(yes|no|unclear)$"),
                    db: AsyncSession = Depends(get_db)):
    run = await _get_run(db, run_id)
    rows = await _all(db, f"""
        SELECT r.change_id, ch.citation, ch.heading, COALESCE(a.name, cs.owning_agency) AS agency,
               r.obligation_changed, r.applicable, r.attribute_basis, r.affected_activity, r.reason,
               r.quote_s2, r.rule_covered_by_docs
        FROM engine.radar_items r
        JOIN engine.change_records ch ON ch.change_id = r.change_id
        LEFT JOIN public.code_sections cs ON cs.id = COALESCE(ch.s2_section_id, ch.s1_section_id)
        LEFT JOIN public.agencies a ON a.agency_id = cs.agency_id
        WHERE r.run_id = CAST(:rid AS uuid) AND (CAST(:app AS text) IS NULL OR r.applicable = :app)
        ORDER BY {_ORDER}, ch.citation""", rid=str(run["run_id"]), app=applicable)
    return [{**r, "change_id": str(r["change_id"]), "attribute_basis": r["attribute_basis"] or [],
             "rule_covered_by_docs": r["rule_covered_by_docs"] or []} for r in rows]
