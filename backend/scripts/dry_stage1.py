"""Read-only dry run of Stage 1 on the real snapshots (no DB writes): class counts and in-footprint list.

Usage (from backend/): PYTHONPATH=. .venv/bin/python scripts/dry_stage1.py
"""
import asyncio

from sqlalchemy import text

from app.db import AsyncSessionLocal, engine
from app.engine.config import engine_settings
from app.engine.delta import format_in_footprint, run_stage1, stage1_stats
from app.engine.footprint import load_footprint
from app.engine.inputs import build_kb_inputs


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        inputs = await build_kb_inputs(session)
        fp = await load_footprint(session, engine_settings.ENGINE_COMPANY_ID)
        stage1 = await run_stage1(session, "dry-run", inputs, fp)
        await session.rollback()
    stats = stage1_stats(stage1.results)
    print(f"inputs={len(inputs)} eligible_clauses={fp.eligible_clauses} "
          f"noise_candidates={len(stage1.candidates)}")
    for src, counts in sorted(stats["by_source"].items()):
        print(f"{src}: {dict(sorted(counts.items()))}")
    print("total:", dict(sorted(stats["by_class"].items())))
    print("dispositions:", stats["dispositions"])
    print("in_footprint_by_class:", stats["in_footprint_by_class"])
    print("renumbered:", stats["renumbered"])
    print("in-footprint changes (citation | class | #cited clauses):")
    for line in format_in_footprint(stats):
        print(" ", line)
    await engine.dispose()


asyncio.run(main())
