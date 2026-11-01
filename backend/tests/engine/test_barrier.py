"""Enforces architecture.md section 5 guardrails 1 (information barrier) and 2 (no hardcoded identifiers),
and architecture.md section 10 (the synthetic boundary: `backend/synthetic/` is deletable).

Pure file scanning, two scopes:
- all of app/ (source and runtime-loaded text such as prompt templates) against every forbidden path
  pattern, including the synthetic-boundary ones (`synthetic/`, `corpus/`, `app/company`);
- scripts/ against the grader-barrier patterns only. Operator scripts may legitimately drive demo
  tooling under synthetic/, but must never read grader answers (eval, grounding, basis, ...).
"""
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND / "app"
SCRIPTS_DIR = BACKEND / "scripts"
SCAN_DIRS = [APP_DIR]
ENGINE_DIR = APP_DIR / "engine"

# Files read at runtime alongside the Python (prompt templates etc.) are scanned too.
SCAN_SUFFIXES = {".py", ".md", ".txt", ".yaml", ".yml", ".json", ".sql", ".toml", ".csv"}

# guardrail 1: grader-only paths the engine / scripts must never reference
BARRIER_PATTERNS = [
    re.compile(r"corpus/eval"),
    re.compile(r"corpus/grounding"),
    re.compile(r"corpus/qa"),
    re.compile(r"corpus/validation"),
    re.compile(r"basis\.json"),  # also covers .basis.json
    re.compile(r"expected_findings"),
    re.compile(r"_manifest\.json"),
    re.compile(r"corpus/docs/[^\s'\"]*scripts"),
]

# synthetic boundary: app/ may not reference the synthetic tree at all. These MUST stay path-shaped:
# a bare `synthetic` false-hits `_synthetic_unit` (app/engine/params_text.py) and a bare `corpus`
# false-hits prose comments (app/engine/delta.py) and the plural list in enrich/terms.py.
SYNTHETIC_PATTERNS = [
    re.compile(r"synthetic/"),
    re.compile(r"corpus/"),
    re.compile(r"app/company\b"),
    # pathlib joins, e.g. BACKEND / "synthetic" / "corpus" or ... / "company" / "corpus"
    re.compile(r"""/\s*["'](?:synthetic|corpus)["']|["'](?:synthetic|corpus)["']\s*/"""),
]

FORBIDDEN_PATH_PATTERNS = BARRIER_PATTERNS + SYNTHETIC_PATTERNS

# Pre-existing files that violate the barrier (none at time of writing). Document any here.
ALLOWLIST_EXISTING: set[str] = set()

# guardrail 2: literals not allowed in app/engine/**/*.py (case-sensitive)
FORBIDDEN_IDENTIFIER_PATTERNS = [
    re.compile(r"RPL-"),
    re.compile(r" IAC "),
    re.compile(r" CFR "),
]


def _files(dirs, suffixes=frozenset({".py"})):
    for d in dirs:
        if d.is_dir():
            yield from sorted(
                p for p in d.rglob("*")
                if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts
            )


def scan_file(path: Path, patterns) -> list[str]:
    """Return one 'file:line: [patterns] text' entry for every line of `path` matching any pattern."""
    hits = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        matched = [pat.pattern for pat in patterns if pat.search(line)]
        if matched:
            hits.append(f"{path}:{lineno}: [{' | '.join(matched)}] {line.strip()}")
    return hits


def scan_barrier(dirs=SCAN_DIRS, patterns=FORBIDDEN_PATH_PATTERNS, allowlist=ALLOWLIST_EXISTING) -> list[str]:
    violations = []
    for f in _files(dirs, SCAN_SUFFIXES):
        if f.name in allowlist:
            continue
        violations += scan_file(f, patterns)
    return violations


def scan_identifiers(engine_dir=ENGINE_DIR) -> list[str]:
    violations = []
    for f in _files([engine_dir]):
        violations += scan_file(f, FORBIDDEN_IDENTIFIER_PATTERNS)
    return violations


def test_information_barrier():
    violations = scan_barrier()
    assert not violations, "information barrier / synthetic boundary violated:\n" + "\n".join(violations)


def test_scripts_information_barrier():
    violations = scan_barrier(dirs=[SCRIPTS_DIR], patterns=BARRIER_PATTERNS)
    assert not violations, "scripts read grader-only data:\n" + "\n".join(violations)


def test_no_hardcoded_identifiers_in_engine():
    violations = scan_identifiers()
    assert not violations, "hardcoded identifiers in app/engine:\n" + "\n".join(violations)


def test_scan_dirs_cover_app_and_exclude_synthetic():
    assert APP_DIR in SCAN_DIRS
    for d in SCAN_DIRS + [SCRIPTS_DIR]:
        assert "synthetic" not in d.relative_to(BACKEND).parts
    # the synthetic corpus moved out of the app package (task 2.1)
    assert not (APP_DIR / "company").exists()


def test_scanner_detects_barrier_violation(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text('p = "app/company/corpus/eval/x.json"\nq = open("a.basis.json")\nok = 1\n')
    hits = scan_barrier(dirs=[tmp_path], allowlist=set())
    assert len(hits) == 2
    assert f"{bad}:1:" in hits[0] and f"{bad}:2:" in hits[1]
    # allowlisted file name is skipped
    assert scan_barrier(dirs=[tmp_path], allowlist={"bad.py"}) == []


def test_scanner_no_score_run_exemption(tmp_path):
    # score_run.py lives in synthetic/ now; nothing in app/ or scripts/ may name the grader.
    sr = tmp_path / "score_run.py"
    sr.write_text('S = "synthetic/corpus/eval/scoring.py"\n')
    assert len(scan_barrier(dirs=[tmp_path], allowlist=set())) == 1
    assert len(scan_barrier(dirs=[tmp_path], patterns=BARRIER_PATTERNS, allowlist=set())) == 1


def test_scanner_detects_synthetic_reference(tmp_path):
    bad = tmp_path / "pkg" / "loader.py"
    bad.parent.mkdir()
    bad.write_text(
        'ROOT = "backend/synthetic/corpus/docs/x.md"\n'
        'ROOT2 = BACKEND / "synthetic" / "corpus"\n'
        'OLD = Path(__file__).parent / "app" / "company" / "corpus"\n'
        'LEGACY = "app/company"\n'
    )
    prompt = tmp_path / "pkg" / "prompt.md"
    prompt.write_text("Read backend/synthetic/corpus/_global/company_profile.yaml first.\n")
    hits = scan_barrier(dirs=[tmp_path], allowlist=set())
    assert len(hits) == 5, hits
    assert all(f"{bad}:{n}:" in h for n, h in zip(range(1, 5), hits[:4]))
    assert f"{prompt}:1:" in hits[4]
    # scripts scope ignores the synthetic-boundary patterns (demo tooling may call into synthetic/)
    assert scan_barrier(dirs=[tmp_path], patterns=BARRIER_PATTERNS, allowlist=set()) == []


def test_scanner_synthetic_patterns_have_no_false_positives(tmp_path):
    ok = tmp_path / "ok.py"
    ok.write_text(
        "def _synthetic_unit(text):\n"
        "    return text\n"
        "# compares the corpus of clauses before and after a change\n"
        'IRREGULAR = {"caucus", "corpus", "hiatus"}\n'
        'from app.company_ingest import service  # app/company_ingest/service.py\n'
        'ROUTE = "app/api/company/routes.py"\n'
        'r = "synthetic_unit"\n'
    )
    assert scan_barrier(dirs=[tmp_path], allowlist=set()) == []


def test_scanner_detects_identifier_violation(tmp_path):
    bad = tmp_path / "e.py"
    bad.write_text('a = "RPL-001"\nb = "see 328 IAC 2"\nc = "12 CFR 5"\nd = "iac"\n')
    hits = scan_identifiers(tmp_path)
    assert len(hits) == 3
    assert f"{bad}:1:" in hits[0]
