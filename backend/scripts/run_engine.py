"""Run the impact engine and print the run id and stats.

Usage (from backend/): PYTHONPATH=. .venv/bin/python scripts/run_engine.py --kind kb|baseline|whatif [--scenario ID] [--radar]
"""
import argparse
import asyncio
import json
import logging

from sqlalchemy import text

from app.db import AsyncSessionLocal, engine
from app.engine.run import run_engine


async def main(args: argparse.Namespace) -> None:
    try:
        run_id = await run_engine(args.kind, args.scenario, radar=args.radar)
        async with AsyncSessionLocal() as s:
            row = (await s.execute(text(
                "SELECT status, stats FROM engine.runs WHERE run_id = CAST(:r AS uuid)"), {"r": run_id}
            )).mappings().one()
        print(f"run_id={run_id} status={row['status']}")
        print(json.dumps(row["stats"], indent=2, sort_keys=True))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=["kb", "baseline", "whatif"])
    ap.add_argument("--scenario", default=None)
    ap.add_argument("--radar", action="store_true")
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(ap.parse_args()))
