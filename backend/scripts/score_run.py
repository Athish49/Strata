"""Export a run, score it with the scoring script, and store the aggregate metrics.

Usage (from backend/): PYTHONPATH=. .venv/bin/python scripts/score_run.py --run <id> [--snapshot S1|S2] [--out PATH]
Snapshot defaults to S1 for baseline runs and S2 otherwise.
"""
import argparse
import asyncio
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import text

from app.db import AsyncSessionLocal, engine
from app.engine.export import build_export

SCORING = Path(__file__).resolve().parents[1] / "app" / "company" / "corpus" / "eval" / "scoring.py"

_NUM = r"(-?\d+(?:\.\d+)?)"
# label -> metric key; matched against the "Label     value" table rows of the scoring output
_METRIC_ROWS = [
    (r"Expected non-informational findings", "expected_non_informational", int),
    (r"System non-informational findings", "system_non_informational", int),
    (r"Matched", "matched", int),
    (r"Recall \(overall\)", "recall", float),
    (r"Recall \(medium severity\)", "recall_medium", float),
    (r"Recall \(low severity\)", "recall_low", float),
    (r"Precision", "precision", float),
    (r"FP rate on negative set", "fp_rate_must_not_flag", float),
    (r"Routing accuracy[^\n\d-]*", "routing_accuracy", float),
    (r"(?:Cohen'?s )?kappa[^\n\d-]*", "kappa", float),
]
_DOC_LINE = re.compile(
    r"^\s*\S\s+(\S+)\s+expected=(\w+)\s+system=(\w+)\s+exp=(\d+)\s+sys=(\d+)\s+matched=(\d+)", re.M)
_TARGET_LINE = re.compile(r"^\s*\[(PASS|FAIL)\]\s+(.+?)\s*$", re.M)
_BASELINE = re.compile(r"^(PASS|FAIL)\s*[—-].*S1.*$", re.M)
_OVERALL = re.compile(r"^Overall:\s*(PASS|FAIL)", re.M)


def parse_metrics(stdout: str) -> dict:
    """Tolerant parse of the aggregate lines only; anything absent is simply omitted."""
    m: dict = {}
    for label, key, cast in _METRIC_ROWS:
        hit = re.search(rf"^[ \t]*{label}[ \t]*{_NUM}[ \t]*$", stdout, re.M | re.I)
        if hit:
            m[key] = cast(float(hit.group(1))) if cast is int else float(hit.group(1))
    docs = [
        {"doc_id": d, "expected": e, "system": s, "expected_count": int(a), "system_count": int(b), "matched": int(c)}
        for d, e, s, a, b, c in _DOC_LINE.findall(stdout)
    ]
    if docs:
        m["per_doc"] = docs
    targets = [{"target": t, "result": r} for r, t in _TARGET_LINE.findall(stdout)]
    if targets:
        m["targets"] = targets
    b = _BASELINE.search(stdout)
    if b:
        m["baseline_check"] = b.group(1)
        m["baseline_line"] = b.group(0).strip()
    o = _OVERALL.search(stdout)
    if o:
        m["overall"] = o.group(1)
    return m


async def main(args: argparse.Namespace) -> None:
    try:
        async with AsyncSessionLocal() as s:
            kind = (await s.execute(text("SELECT kind FROM engine.runs WHERE run_id = CAST(:r AS uuid)"),
                                    {"r": args.run})).scalar_one()
            export = await build_export(s, args.run)
        snapshot = (args.snapshot or ("S1" if kind == "baseline" else "S2")).upper()
        out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="score_run_")) / f"export_{args.run}.json"
        out.write_text(json.dumps(export, indent=2))

        proc = subprocess.run([sys.executable, str(SCORING), str(out), "--snapshot", snapshot],
                              capture_output=True, text=True)
        stdout = proc.stdout
        metrics = parse_metrics(stdout)
        metrics["returncode"] = proc.returncode
        print(stdout)
        if proc.returncode != 0 and proc.stderr:
            print(proc.stderr, file=sys.stderr)

        async with AsyncSessionLocal() as s:
            await s.execute(text("""
                INSERT INTO engine.score_reports (run_id, snapshot, metrics, raw_stdout)
                VALUES (CAST(:r AS uuid), :snap, CAST(:m AS jsonb), :raw)
                ON CONFLICT (run_id) DO UPDATE SET snapshot = EXCLUDED.snapshot, metrics = EXCLUDED.metrics,
                    raw_stdout = EXCLUDED.raw_stdout, created_at = now()"""),
                {"r": args.run, "snap": snapshot, "m": json.dumps(metrics), "raw": stdout})
            await s.commit()
        print("stored metrics:", json.dumps({k: v for k, v in metrics.items() if k != "per_doc"}, sort_keys=True))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--snapshot", choices=["S1", "S2"], default=None)
    ap.add_argument("--out", default=None)
    asyncio.run(main(ap.parse_args()))
