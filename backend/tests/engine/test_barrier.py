"""Enforces architecture.md section 5 guardrails 1 (information barrier) and 2 (no hardcoded identifiers).

Pure file scanning: app/engine/, app/api/engine/ and scripts/ only (never app/company/, which is data,
and never company_ingest/collect/allowlist.py, which is outside the scanned dirs anyway).
"""
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
SCAN_DIRS = [BACKEND / "app" / "engine", BACKEND / "app" / "api" / "engine", BACKEND / "scripts"]
ENGINE_DIR = BACKEND / "app" / "engine"

# guardrail 1: paths the engine / scripts must never reference
FORBIDDEN_PATH_PATTERNS = [
    re.compile(r"corpus/eval"),
    re.compile(r"corpus/grounding"),
    re.compile(r"corpus/qa"),
    re.compile(r"corpus/validation"),
    re.compile(r"basis\.json"),  # also covers .basis.json
    re.compile(r"expected_findings"),
    re.compile(r"_manifest\.json"),
    re.compile(r"corpus/docs/[^\s'\"]*scripts"),
]

# The single sanctioned exception: score_run.py may name scoring.py (to run it as a subprocess),
# but never --verbose or expected_findings.
SCORE_RUN = BACKEND / "scripts" / "score_run.py"
SCORE_RUN_ALLOWED = [re.compile(r"corpus/eval/scoring\.py"), re.compile(r"\bscoring\.py")]
SCORE_RUN_FORBIDDEN = [re.compile(r"--verbose"), re.compile(r"expected_findings")]

# Pre-existing scripts that violate the barrier (none at time of writing). Document any here.
ALLOWLIST_EXISTING: set[str] = set()

# guardrail 2: literals not allowed in app/engine/**/*.py (case-sensitive)
FORBIDDEN_IDENTIFIER_PATTERNS = [
    re.compile(r"RPL-"),
    re.compile(r" IAC "),
    re.compile(r" CFR "),
]


def _py_files(dirs):
    for d in dirs:
        if d.is_dir():
            yield from sorted(d.rglob("*.py"))


def scan_file(path: Path, patterns) -> list[str]:
    """Return 'file:line: text' for every line of `path` matching any pattern."""
    hits = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for pat in patterns:
            if pat.search(line):
                hits.append(f"{path}:{lineno}: [{pat.pattern}] {line.strip()}")
    return hits


def scan_barrier(dirs=SCAN_DIRS, score_run=SCORE_RUN, allowlist=ALLOWLIST_EXISTING) -> list[str]:
    violations = []
    for f in _py_files(dirs):
        if f == score_run:
            # allowed to mention scoring.py, but nothing else forbidden
            hits = scan_file(f, SCORE_RUN_FORBIDDEN)
            for lineno, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                for pat in FORBIDDEN_PATH_PATTERNS:
                    if pat.search(line) and not any(a.search(line) for a in SCORE_RUN_ALLOWED):
                        hits.append(f"{f}:{lineno}: [{pat.pattern}] {line.strip()}")
            violations += hits
        elif f.name in allowlist:
            continue
        else:
            violations += scan_file(f, FORBIDDEN_PATH_PATTERNS)
    return violations


def scan_identifiers(engine_dir=ENGINE_DIR) -> list[str]:
    violations = []
    for f in _py_files([engine_dir]):
        violations += scan_file(f, FORBIDDEN_IDENTIFIER_PATTERNS)
    return violations


def test_information_barrier():
    violations = scan_barrier()
    assert not violations, "information barrier violated:\n" + "\n".join(violations)


def test_no_hardcoded_identifiers_in_engine():
    violations = scan_identifiers()
    assert not violations, "hardcoded identifiers in app/engine:\n" + "\n".join(violations)


def test_scan_dirs_are_not_company_data():
    for d in SCAN_DIRS:
        assert "company" not in d.relative_to(BACKEND).parts


def test_scanner_detects_barrier_violation(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text('p = "app/company/corpus/eval/x.json"\nq = open("a.basis.json")\nok = 1\n')
    hits = scan_barrier(dirs=[tmp_path], score_run=tmp_path / "nope.py", allowlist=set())
    assert len(hits) == 2
    assert f"{bad}:1:" in hits[0] and f"{bad}:2:" in hits[1]
    # allowlisted file name is skipped
    assert scan_barrier(dirs=[tmp_path], score_run=tmp_path / "nope.py", allowlist={"bad.py"}) == []


def test_scanner_score_run_exception(tmp_path):
    sr = tmp_path / "score_run.py"
    sr.write_text('S = "app/company/corpus/eval/scoring.py"\n')
    assert scan_barrier(dirs=[tmp_path], score_run=sr, allowlist=set()) == []
    sr.write_text('S = "app/company/corpus/eval/scoring.py"\nargs = ["--verbose"]\nx = "expected_findings"\n')
    assert len(scan_barrier(dirs=[tmp_path], score_run=sr, allowlist=set())) >= 2
    sr.write_text('S = "app/company/corpus/eval/gold.json"\n')
    assert len(scan_barrier(dirs=[tmp_path], score_run=sr, allowlist=set())) == 1


def test_scanner_detects_identifier_violation(tmp_path):
    bad = tmp_path / "e.py"
    bad.write_text('a = "RPL-001"\nb = "see 328 IAC 2"\nc = "12 CFR 5"\nd = "iac"\n')
    hits = scan_identifiers(tmp_path)
    assert len(hits) == 3
    assert f"{bad}:1:" in hits[0]
