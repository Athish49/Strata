"""Load offline judge answers into engine.llm_calls (the cache) - the only write this script makes.

Usage (from backend/):
  PYTHONPATH=. .venv/bin/python scripts/offline_judge_import.py --in <dir> [--dry-run]

Reads <dir>/MANIFEST.json, <dir>/batch_NN.json (prompts) and <dir>/answers_NN.json
([{"id", "answer": <JudgeResult JSON>}]). Each answer is validated against JudgeResult and must
refer to an exported id; the cache key is recomputed from the stored prompt and must equal the
exported hash. Quote checks (verify_quote against the prompt text) are report-only.
Rows are written exactly like llm.call_cached logs a call (stage 'judge', same model, valid=true),
tagged via error = PROVENANCE like the earlier offline rows. Idempotent: a (stage, model, sha)
that already has a valid row is skipped.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
import offline_judge_common as C  # noqa: E402
from app.engine.quotes import verify_quote  # noqa: E402


def load_prompts(d: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted(d.glob("batch_*.json")):
        for e in C.read_json(f):
            out[e["id"]] = e
    return out


def check_answers(d: Path, prompts: dict[str, dict]):
    """Returns (good, rejected, quote_warnings). good: [(id, sha, system, user, JudgeResult)]."""
    good, rejected, qwarn = [], [], []
    seen: set[str] = set()
    for f in sorted(d.glob("answers_*.json")):
        try:
            items = C.read_json(f)
        except ValueError as exc:
            rejected.append({"file": f.name, "id": None, "reason": f"invalid JSON file: {exc}"})
            continue
        for it in items if isinstance(items, list) else []:
            cid = it.get("id") if isinstance(it, dict) else None
            ent = prompts.get(cid)
            if ent is None:
                rejected.append({"file": f.name, "id": cid, "reason": "unknown id (not in any batch)"})
                continue
            if cid in seen:
                rejected.append({"file": f.name, "id": cid, "reason": "duplicate answer for id"})
                continue
            try:
                res = C.SCHEMA.model_validate(it.get("answer"))
            except ValidationError as exc:
                rejected.append({"file": f.name, "id": cid, "reason": "schema: " + "; ".join(
                    f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())})
                continue
            if not (0.0 <= res.confidence <= 1.0):
                rejected.append({"file": f.name, "id": cid, "reason": "confidence outside 0..1"})
                continue
            sha = C.cache_key(ent["system"], ent["user"])
            if sha != ent["prompt_sha256"]:
                rejected.append({"file": f.name, "id": cid, "reason": "batch prompt hash mismatch"})
                continue
            seen.add(cid)
            for k, q in (res.quotes or {}).items():
                if isinstance(q, str) and q.strip() and not verify_quote(q, ent["user"]):
                    qwarn.append({"id": cid, "quote": k})
            good.append((cid, sha, ent["system"], ent["user"], res))
    return good, rejected, qwarn


def build_row(model: str, run_id: str | None, sha: str, system: str, user: str, res) -> dict:
    """Same shape llm.call_cached._log_call writes for a successful call."""
    return {
        "call_id": str(uuid.uuid4()), "run_id": run_id, "stage": C.STAGE, "model": model, "sha": sha,
        "request": json.dumps({"system": system, "user": user, "schema_name": C.SCHEMA.__name__}),
        "response": json.dumps(res.model_dump(mode="json")), "valid": True,
        "error": C.PROVENANCE, "latency": 0,
    }


_INSERT = text(
    "INSERT INTO engine.llm_calls (call_id, run_id, stage, model, prompt_sha256, request, response, "
    "valid, error, latency_ms) VALUES (:call_id, CAST(:run_id AS uuid), :stage, :model, :sha, "
    "CAST(:request AS jsonb), CAST(:response AS jsonb), :valid, :error, :latency)")
_EXISTS = text("SELECT 1 FROM engine.llm_calls WHERE stage=:s AND model=:m AND prompt_sha256=:h AND valid LIMIT 1")


async def run_import(session, rows_in, model: str, run_id: str | None, dry_run: bool) -> dict:
    inserted = skipped = 0
    batch_seen: set[str] = set()
    for cid, sha, system, user, res in rows_in:
        if sha in batch_seen or (await session.execute(
                _EXISTS, {"s": C.STAGE, "m": model, "h": sha})).first():
            skipped += 1
            continue
        batch_seen.add(sha)
        inserted += 1
        if not dry_run:
            await session.execute(_INSERT, build_row(model, run_id, sha, system, user, res))
    if not dry_run:
        await session.commit()
    return {"inserted": inserted, "skipped_existing": skipped}


async def main_async(args) -> dict:
    d = Path(args.indir)
    man = C.read_json(d / "MANIFEST.json")
    prompts = load_prompts(d)
    good, rejected, qwarn = check_answers(d, prompts)
    report = {"dry_run": args.dry_run, "exported": len(prompts), "answers_valid": len(good),
              "rejected": rejected, "quote_warnings": qwarn,
              "unanswered": len(prompts) - len(good) - len(rejected)}
    from app.db import AsyncSessionLocal

    async with AsyncSessionLocal() as s:
        report.update(await run_import(s, good, man["model"], man.get("run_id"), args.dry_run))
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    r = asyncio.run(main_async(args))
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in r.items()}))
    for x in r["rejected"]:
        print("REJECTED", x)
    for x in r["quote_warnings"]:
        print("QUOTE-WARN", x)


if __name__ == "__main__":
    main()
