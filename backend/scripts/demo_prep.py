"""Demo prep: run baseline, kb (+radar), what-if presets, score, warm caches, verify the API.

Usage (from backend/): PYTHONPATH=. .venv/bin/python scripts/demo_prep.py [--api-base URL] [--skip-llm] [--force]

Steps (each prints a header; safe to re-run, finished runs are reused unless --force):
  1 api reachable      2 baseline run      3 score baseline (S1)   4 kb run (+radar)
  5 score kb (S2)      6 radar backfill    7 what-if presets       8 run presets
  9 warm caches       10 verify routes    11 summary table
--skip-llm runs only the steps that need no LLM (1,2,3,9,10,11); kb, radar and preset runs are
reused if they already exist but never started. The API at --api-base must be running.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
SCRIPTS = BACKEND / "scripts"


def step(n: int, title: str) -> None:
    print(f"\n[{n}/11] {title}")


def sh(script: str, *args: str) -> str:
    env = {**os.environ, "PYTHONPATH": str(BACKEND)}
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=BACKEND, env=env,
                       capture_output=True, text=True)
    out = p.stdout + p.stderr
    tail = "\n".join(out.strip().splitlines()[-6:])
    print("   " + tail.replace("\n", "\n   "))
    if p.returncode != 0:
        raise RuntimeError(f"{script} {' '.join(args)} exited {p.returncode}")
    return p.stdout


def get(c: httpx.Client, path: str, **params):
    r = c.get(path, params=params or None)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else None)


def latest_run(c: httpx.Client, kind: str, title: str | None = None, force: bool = False):
    if force:
        return None
    _, runs = get(c, "/engine/runs", kind=kind)
    for r in runs or []:
        if r["status"] == "done" and (title is None or r.get("scenario_title") == title):
            return r
    return None


def run_id_of(stdout: str) -> str:
    m = re.search(r"run_id=([0-9a-f-]{36})", stdout)
    if not m:
        raise RuntimeError("no run_id in output")
    return m.group(1)


def main(a: argparse.Namespace) -> int:
    c = httpx.Client(base_url=a.api_base.rstrip("/"), timeout=60)
    runs: dict[str, str] = {}  # label -> run_id
    problems: list[str] = []

    step(1, f"API reachable at {a.api_base}")
    code, _ = get(c, "/health")
    print(f"   /health -> {code}")
    if code != 200:
        print("   API not reachable; start it with: uvicorn app.main:app --port 8000")
        return 2

    step(2, "baseline run (S1 vs S1, no LLM expected)")
    r = latest_run(c, "baseline", force=a.force)
    runs["baseline"] = r["run_id"] if r else run_id_of(sh("run_engine.py", "--kind", "baseline"))
    print(f"   baseline={runs['baseline']}")

    step(3, "score baseline against S1")
    sh("score_run.py", "--run", runs["baseline"], "--snapshot", "S1")

    step(4, "kb run (S1 -> S2) with radar")
    r = latest_run(c, "kb", force=a.force)
    if r:
        runs["kb"] = r["run_id"]
    elif a.skip_llm:
        print("   skipped (--skip-llm), no finished kb run")
    else:
        runs["kb"] = run_id_of(sh("run_engine.py", "--kind", "kb", "--radar"))
    print(f"   kb={runs.get('kb')}")

    step(5, "score kb against S2")
    if "kb" in runs:
        sh("score_run.py", "--run", runs["kb"], "--snapshot", "S2")
    else:
        print("   skipped (no kb run)")

    step(6, "radar backfill (only if the kb run has no radar items)")
    if "kb" in runs:
        _, items = get(c, f"/engine/runs/{runs['kb']}/radar")
        if items:
            print(f"   {len(items)} radar items present")
        elif a.skip_llm:
            print("   skipped (--skip-llm)")
        else:
            sh("run_radar.py", runs["kb"])
    else:
        print("   skipped (no kb run)")

    step(7, "what-if presets (create/refresh)")
    if a.skip_llm:
        print("   skipped (--skip-llm); listing existing scenarios")
    else:
        sh("make_whatif_presets.py")
    _, scen = get(c, "/engine/whatif/scenarios")
    print(f"   {len(scen or [])} scenarios")

    step(8, "run presets")
    if a.skip_llm:
        print("   skipped (--skip-llm)")
    else:
        sh("make_whatif_presets.py", "--run")
    _, wruns = get(c, "/engine/runs", kind="whatif")
    for w in wruns or []:
        if w["status"] == "done":
            runs.setdefault(f"whatif:{w.get('scenario_title') or w['run_id'][:8]}", w["run_id"])

    step(9, "warm caches (first hit of every run page)")
    # verified in step 10; this pass is deliberately fire-and-forget
    for rid in runs.values():
        for p in ("", "/documents", "/ledger", "/scorecard", "/radar"):
            try:
                c.get(f"/engine/runs/{rid}{p}")
            except httpx.HTTPError:
                pass
    get(c, "/engine/whatif/sections")
    print(f"   warmed {len(runs)} runs")

    step(10, "verify routes for every run")
    for label, rid in runs.items():
        for p in ("", "/documents", "/ledger", "/scorecard", "/radar"):
            code, _ = get(c, f"/engine/runs/{rid}{p}")
            if code != 200:
                problems.append(f"{label} {p or '/'} -> {code}")
        _, docs = get(c, f"/engine/runs/{rid}/documents")
        if docs:
            code, _ = get(c, f"/engine/runs/{rid}/documents/{docs[0]['doc_id']}")
            if code != 200:
                problems.append(f"{label} document detail -> {code}")
        _, ledger = get(c, f"/engine/runs/{rid}/ledger")
        fid = next((x.get("finding_id") for x in ledger or [] if x.get("finding_id")), None)
        if fid:
            code, _ = get(c, f"/engine/findings/{fid}")
            if code != 200:
                problems.append(f"{label} finding {fid} -> {code}")
    for p in ("/engine/whatif/sections", "/engine/whatif/scenarios", "/engine/people"):
        code, _ = get(c, p)
        if code != 200:
            problems.append(f"{p} -> {code}")
    print("   all OK" if not problems else "   " + "\n   ".join(problems))

    step(11, "summary")
    print(f"   {'run':<34}{'run_id':<38}{'status':<9}metrics")
    for label, rid in runs.items():
        _, d = get(c, f"/engine/runs/{rid}")
        _, sc = get(c, f"/engine/runs/{rid}/scorecard")
        st = (d or {}).get("stats") or {}
        m = ""
        mm = (sc or {}).get("metrics") if isinstance(sc, dict) else None
        if mm:
            m = " ".join(f"{k}={mm[k]}" for k in ("recall", "precision", "overall", "baseline_check") if k in mm)
        print(f"   {label[:32]:<34}{rid:<38}{(d or {}).get('run', {}).get('status', '?'):<9}"
              f"llm={st.get('llm_calls', '-')} {m}")
    return 1 if problems else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api-base", default="http://localhost:8000")
    ap.add_argument("--skip-llm", action="store_true", help="never start a run that needs the LLM")
    ap.add_argument("--force", action="store_true", help="ignore finished runs and start new ones")
    sys.exit(main(ap.parse_args()))
