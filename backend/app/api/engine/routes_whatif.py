"""What-if routes (api_ui.md section 1). Mounted under /engine by the aggregate router in routes.py."""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.engine import whatif
from app.engine.schemas import (
    RunCreated, WhatIfScenario, WhatIfScenarioCreate, WhatIfScenarioCreated, WhatIfSection, WhatIfSectionText,
)

router = APIRouter(tags=["engine-whatif"])


async def _run_in_background(scenario_id: str, run_id: str) -> None:
    await whatif.run_whatif(scenario_id, run_id=run_id)


@router.get("/whatif/sections", response_model=list[WhatIfSection])
async def list_sections(db: AsyncSession = Depends(get_db)):
    return await whatif.list_editable_sections(db)


@router.get("/whatif/sections/{s1_section_id}", response_model=WhatIfSectionText)
async def get_section(s1_section_id: int, db: AsyncSession = Depends(get_db)):
    sec = await whatif.get_section(db, s1_section_id)
    if sec is None:
        raise HTTPException(404, "section not found")
    return sec


@router.get("/whatif/scenarios", response_model=list[WhatIfScenario])
async def list_scenarios(db: AsyncSession = Depends(get_db)):
    return await whatif.list_scenarios(db)


@router.post("/whatif/scenarios", response_model=WhatIfScenarioCreated)
async def create_scenario(body: WhatIfScenarioCreate, background: BackgroundTasks,
                          db: AsyncSession = Depends(get_db)):
    err = whatif.validate_scenario(body.edit_kind, body.edited_text)
    if err:
        raise HTTPException(422, err)
    if await whatif.get_section(db, body.s1_section_id) is None:
        raise HTTPException(404, "section not found")
    scenario_id = await whatif.create_scenario(
        db, s1_section_id=body.s1_section_id, edit_kind=body.edit_kind,
        edited_text=body.edited_text, title=body.title)
    run_id = str(uuid.uuid4())
    background.add_task(_run_in_background, scenario_id, run_id)
    return WhatIfScenarioCreated(scenario_id=scenario_id, run_id=run_id)


@router.post("/whatif/scenarios/{scenario_id}/run", response_model=RunCreated)
async def rerun_scenario(scenario_id: str, background: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    if await whatif.get_scenario(db, scenario_id) is None:
        raise HTTPException(404, "scenario not found")
    run_id = str(uuid.uuid4())
    background.add_task(_run_in_background, str(uuid.UUID(scenario_id)), run_id)
    return RunCreated(run_id=run_id)
