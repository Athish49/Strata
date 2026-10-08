"""Export the judge prompts that MISS the LLM cache for a finished run (no LLM calls, read-only DB).

Usage (from backend/):
  PYTHONPATH=. .venv/bin/python scripts/offline_judge_export.py --run <run_id> --out <dir> [--batch-size 50]

Writes <dir>/batch_NN.json  [{"id", "prompt_sha256", "system", "user"}], <dir>/MANIFEST.json and
<dir>/ANSWERING_GUIDE.md. Idempotent: the output dir's batch_*.json / MANIFEST.json are rewritten.
Answers go to <dir>/answers_NN.json and are loaded with offline_judge_import.py.
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
import offline_judge_common as C  # noqa: E402
from app.engine import judge as J  # noqa: E402
from app.engine.config import engine_settings  # noqa: E402

GUIDE = Path(__file__).resolve().parent / "offline_judge_GUIDE.md"
# Same candidate query the engine uses, minus the "still open" filter (the run is already judged).
_ALL_SQL = text(J._OPEN_SQL.text.replace(
    "k.judged_by IS NULL AND k.skip_reason IS NULL", "k.skip_reason IS NULL"))


async def load_cached_shas(session, model: str) -> set[str]:
    """prompt_sha256 of valid judge cache rows whose response still validates (a hit for the engine)."""
    rows = (await session.execute(text(
        "SELECT prompt_sha256, response FROM engine.llm_calls "
        "WHERE stage=:s AND model=:m AND valid"), {"s": C.STAGE, "m": model})).all()
    out: set[str] = set()
    for sha, resp in rows:
        try:
            C.SCHEMA.model_validate(resp)
            out.add(sha)
        except Exception:  # noqa: BLE001 - engine would re-call -> a miss
            pass
    return out


def plan(items, cached: set[str]) -> dict:
    """Pure: split LLM-judged items into hits / misses (deduplicated by prompt hash)."""
    llm_items = [it for it in items if J.decide_by_rules(it) is None]
    hits = misses = 0
    entries: list[dict] = []
    seen: dict[str, str] = {}
    dups: dict[str, list[str]] = {}
    by_role: dict[str, int] = {}
    for it in llm_items:
        system, user = C.build_prompts(it)
        sha = C.cache_key(system, user)
        if sha in cached:
            hits += 1
            continue
        misses += 1
        if sha in seen:
            dups.setdefault(seen[sha], []).append(it.candidate_id)
            continue
        seen[sha] = it.candidate_id
        by_role[str(it.clause_role)] = by_role.get(str(it.clause_role), 0) + 1
        entries.append({"id": it.candidate_id, "prompt_sha256": sha, "system": system, "user": user})
    return {"llm_judged": len(llm_items), "cache_hits": hits, "cache_misses": misses,
            "entries": entries, "duplicate_prompts": dups, "misses_by_role": by_role}


def write_out(out: Path, run_id: str, model: str, p: dict, batch_size: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("batch_*.json"):
        old.unlink()
    entries = p["entries"]
    files = []
    for n, i in enumerate(range(0, len(entries), batch_size), start=1):
        name = f"batch_{n:02d}.json"
        C.write_json(out / name, entries[i:i + batch_size])
        files.append({"file": name, "count": len(entries[i:i + batch_size])})
    manifest = {
        "run_id": run_id, "stage": C.STAGE, "model": model, "schema": C.SCHEMA.__name__,
        "judge_max_section_chars": engine_settings.ENGINE_JUDGE_MAX_SECTION_CHARS,
        "judge_window_chars": engine_settings.ENGINE_JUDGE_WINDOW_CHARS,
        "llm_judged_candidates": p["llm_judged"], "cache_hits": p["cache_hits"],
        "cache_misses": p["cache_misses"], "unique_prompts_exported": len(entries),
        "misses_by_clause_role": p["misses_by_role"],
        "duplicate_prompts": p["duplicate_prompts"], "batch_size": batch_size, "batches": files,
        "provenance_tag": C.PROVENANCE,
    }
    C.write_json(out / "MANIFEST.json", manifest)
    if GUIDE.exists():
        shutil.copyfile(GUIDE, out / "ANSWERING_GUIDE.md")
    return manifest


async def main_async(args) -> dict:
    from app.db import AsyncSessionLocal

    model = engine_settings.ENGINE_JUDGE_MODEL
    async with AsyncSessionLocal() as s:
        items = await _load_items(s, args.run)
        cached = await load_cached_shas(s, model)
    p = plan(items, cached)
    return write_out(Path(args.out), args.run, model, p, args.batch_size)


async def _load_items(session, run_id: str):
    """J.load_open_items with the open-only filter relaxed (same row -> JudgeItem mapping)."""
    orig = J._OPEN_SQL
    J._OPEN_SQL = _ALL_SQL
    try:
        return await J.load_open_items(session, run_id)
    finally:
        J._OPEN_SQL = orig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch-size", type=int, default=50)
    args = ap.parse_args()
    m = asyncio.run(main_async(args))
    print({k: m[k] for k in ("run_id", "model", "llm_judged_candidates", "cache_hits", "cache_misses",
                             "unique_prompts_exported")}, [b["file"] for b in m["batches"]])


if __name__ == "__main__":
    main()
