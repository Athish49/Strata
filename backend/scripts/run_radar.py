"""Run only the radar stage against an existing run's change_records.

Usage (from backend/): PYTHONPATH=. .venv/bin/python scripts/run_radar.py RUN_ID
Writes engine.radar_items and merges stats['radar'] into engine.runs.stats.
"""
import argparse
import asyncio
import json
import logging

from sqlalchemy import text

from app.db import AsyncSessionLocal, engine
from app.engine.config import MAX_LLM_CALLS_KB, engine_settings
from app.engine.radar import run_radar


async def run_radar_for_existing_run(run_id: str) -> dict:
    stats, calls = await run_radar(AsyncSessionLocal, run_id, engine_settings.ENGINE_COMPANY_ID,
                                   MAX_LLM_CALLS_KB)
    async with AsyncSessionLocal() as s:
        await s.execute(text(
            "UPDATE engine.runs SET stats = COALESCE(stats, '{}'::jsonb) || CAST(:p AS jsonb) "
            "WHERE run_id = CAST(:r AS uuid)"), {"r": run_id, "p": json.dumps({"radar": stats})})
        await s.commit()
    print(f"radar counts={stats} llm_calls={calls}")
    return stats


async def main(run_id: str) -> None:
    try:
        await run_radar_for_existing_run(run_id)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(ap.parse_args().run_id))
