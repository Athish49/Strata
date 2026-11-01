"""Secret-leak regression test (TDD.md section 8).

A Neon connection string was once committed under the corpus tree. The credential has been
rotated and the file deleted; this test makes a recurrence a CI failure.

Scans every git-tracked file in the repository for the four TDD patterns, excluding `.venv/`,
lockfiles, `*.md` and binary assets (the corpus ships PDFs, DOCX, XLSX and PNGs). Reuses the
`scan_file` helper shape from `tests/engine/test_barrier.py`.

Notes:
- Matches are reported as `file:line` with the matched text redacted, so a leaked credential
  never lands in CI logs.
- This module is itself always scanned, so it must never contain a literal that matches a
  pattern. The planted fakes in the self-test are assembled from fragments at runtime.
- Deliberately *not* marked `corpus`: CI runs `-m "not corpus"`, which would disable the guard.
"""
import re
import subprocess
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[2]

# High-confidence patterns: a match is a credential almost by definition, so these
# are applied to EVERY scanned file including placeholder files.
PATTERNS = [
    re.compile(r"npg_[A-Za-z0-9]+"),            # Neon-issued password
    re.compile(r"AKIA[0-9A-Z]{16}"),            # AWS / R2 access key id
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"),   # Anthropic API key
]

# A connection string carrying an inline password. Kept separate because it is the
# one pattern with a legitimate placeholder form (see PLACEHOLDER_FILES).
#
# The `(\+\w+)?` is essential and was missing from the original TDD pattern: this
# app's real DSN scheme is `postgresql+asyncpg://` (built in app/db.py:10 and
# documented in .env.example), so without it the most likely leak of all — a
# developer pasting their working DATABASE_URL — would not be caught.
CONNSTRING_PATTERN = re.compile(r"postgres(ql)?(\+\w+)?://[^ \"'/]*:[^ \"'@/]+@")

# Files whose whole purpose is to show the *shape* of a secret. The connection
# string pattern is not applied to these, but PATTERNS still is — so a real Neon
# password pasted into .env.example is caught even here.
PLACEHOLDER_FILES = {".env.example", ".env.sample", ".env.template"}


def patterns_for(rel: str) -> list[re.Pattern]:
    """Patterns to apply to `rel`. Placeholder files skip the connection string."""
    if PurePosixPath(rel).name in PLACEHOLDER_FILES:
        return list(PATTERNS)
    return [*PATTERNS, CONNSTRING_PATTERN]

LOCKFILE_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "uv.lock"}

# Skipped for speed and to avoid scanning compressed/binary payloads line by line.
BINARY_SUFFIXES = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".png", ".jpg", ".jpeg", ".gif",
    ".webp", ".ico", ".svgz", ".gz", ".zip", ".tar", ".whl", ".pyc", ".db", ".sqlite",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp4", ".mov", ".wasm",
}

# A wrong cwd or an empty `git ls-files` must fail loudly rather than pass vacuously.
MIN_EXPECTED_FILES = 100


def is_excluded(rel: str) -> bool:
    """True for paths the scan skips: `.venv/`, lockfiles, `*.md` and binary assets."""
    p = PurePosixPath(rel)
    if ".venv" in p.parts:
        return True
    suffix = p.suffix.lower()
    if suffix == ".md":
        return True
    if suffix == ".lock" or p.name in LOCKFILE_NAMES:
        return True
    return suffix in BINARY_SUFFIXES


def scan_file(path: Path, patterns, display=None) -> list[str]:
    """Return 'file:line' for every line of `path` matching any pattern (match redacted)."""
    hits: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        # The file vanished or is unreadable between listing and reading.
        return hits
    shown = display if display is not None else path
    for lineno, line in enumerate(text.splitlines(), 1):
        for pat in patterns:
            m = pat.search(line)
            if m:
                prefix = m.group(0)[:4]
                hits.append(f"{shown}:{lineno}: [{pat.pattern}] match begins {prefix!r} (redacted)")
    return hits


def scan_files(rel_paths, root: Path, patterns=None) -> tuple[list[str], int]:
    """Scan `rel_paths` (relative to `root`), returning (hits, number of files actually read).

    Paths that are excluded, or that no longer exist on disk (a concurrent `git mv` or
    deletion), are skipped silently rather than raising.
    """
    hits: list[str] = []
    scanned = 0
    for rel in rel_paths:
        if not rel or is_excluded(rel):
            continue
        path = root / rel
        if not path.is_file():
            continue
        scanned += 1
        pats = patterns if patterns is not None else patterns_for(rel)
        hits += scan_file(path, pats, display=rel)
    return hits, scanned


def tracked_files(root: Path = REPO_ROOT) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, check=True
    ).stdout
    return [p for p in out.split("\0") if p]


def _self_rel() -> str:
    return Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()


# --------------------------------------------------------------------------- the guard


def test_no_secrets_in_tracked_files():
    paths = tracked_files()
    # Scan this module too, so the test behaves identically before and after it is committed.
    if _self_rel() not in paths:
        paths.append(_self_rel())

    hits, scanned = scan_files(paths, REPO_ROOT)

    assert scanned >= MIN_EXPECTED_FILES, (
        f"only {scanned} files scanned (expected >= {MIN_EXPECTED_FILES}); "
        f"the file enumeration is broken, so this test proves nothing"
    )
    assert not hits, (
        "possible committed secret(s) — rotate the credential, then remove it from the file "
        "and from git history:\n" + "\n".join(hits)
    )


# --------------------------------------------------------------------------- self-tests


def test_scanner_detects_planted_secret(tmp_path):
    """Mirrors tests/engine/test_barrier.py:98 — prove the scanner actually fires.

    Every fake is assembled from fragments so that no line of this file matches a pattern.
    """
    neon = "npg" + "_" + "AbC123deadbeef"
    conn = "postgres" + "ql://" + "someuser:s3cret@" + "db.example.net/app"
    aws = "AKIA" + "0123456789ABCDEF"
    pem = "-----BEGIN " + "RSA PRIVATE KEY-----"

    bad = tmp_path / "leak.py"
    bad.write_text(f'A = "{neon}"\nB = "{conn}"\nC = "{aws}"\nD = """{pem}"""\n')

    hits, scanned = scan_files(["leak.py"], tmp_path)
    assert scanned == 1
    assert len(hits) == 4, hits
    for i, hit in enumerate(hits, 1):
        assert hit.startswith(f"leak.py:{i}:"), hit

    # the credential itself is never echoed
    for secret in (neon, conn, aws, pem):
        assert secret not in "\n".join(hits)

    # scan_file keeps the test_barrier shape: absolute path display when no `display` is given
    direct = scan_file(bad, patterns_for("leak.py"))
    assert len(direct) == 4 and direct[0].startswith(f"{bad}:1:")


def test_scanner_skips_excluded_and_missing_paths(tmp_path):
    neon = "npg" + "_" + "AbC123deadbeef"
    body = f'X = "{neon}"\n'

    (tmp_path / "notes.md").write_text(body)
    (tmp_path / "package-lock.json").write_text(body)
    (tmp_path / "poetry.lock").write_text(body)
    (tmp_path / "report.pdf").write_text(body)
    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "mod.py").write_text(body)

    listed = [
        "notes.md",
        "package-lock.json",
        "poetry.lock",
        "report.pdf",
        ".venv/lib/mod.py",
        "moved/away/by/another/agent.py",  # listed by git but gone from disk
        "",
    ]
    hits, scanned = scan_files(listed, tmp_path)
    assert hits == []
    assert scanned == 0

    # sanity: the same content in a scanned path *is* caught
    (tmp_path / "real.py").write_text(body)
    hits, scanned = scan_files(listed + ["real.py"], tmp_path)
    assert scanned == 1 and len(hits) == 1


def test_env_example_placeholders_not_flagged(tmp_path):
    # Built from fragments: this module scans itself, so a literal DSN here would
    # be reported as a leak by the very test it is exercising.
    dsn = "postgres" + "ql+asyncpg://" + "user:password@" + "host/dbname"
    placeholders = (
        f"DATABASE_URL={dsn}\n"
        "QDRANT_API_KEY=your-qdrant-api-key\n"
        "R2_ACCESS_KEY_ID=your-r2-access-key-id\n"
        "R2_SECRET_ACCESS_KEY=your-r2-secret-access-key\n"
        "LLM_API_KEY=your-anthropic-api-key\n"
    )
    (tmp_path / ".env.example").write_text(placeholders)
    hits, scanned = scan_files([".env.example"], tmp_path)
    assert scanned == 1
    assert hits == []

    # and the real one, if present
    real = REPO_ROOT / "backend" / ".env.example"
    if real.is_file():
        assert scan_file(real, PATTERNS) == []


def test_asyncpg_dsn_scheme_is_caught(tmp_path):
    """The app's REAL scheme must be caught, not just the plain psycopg2 one.

    app/db.py:10 rewrites DATABASE_URL to `postgresql+asyncpg://`, and that is the
    form .env.example documents — so it is the form a developer is most likely to
    paste into a committed file. The original TDD pattern omitted the `+driver`
    part and missed it entirely, which made the guard nearly useless for the most
    probable leak. Fragments again, so this file stays clean.
    """
    host = "ep-cool-name-123.us-east-2.aws.neon.tech"
    leaks = [
        "postgres" + "ql+asyncpg://" + "owner:Sup3rS3cret@" + host + "/strata",
        "postgres" + "+asyncpg://" + "owner:Sup3rS3cret@" + host + "/strata",
        "postgres" + "ql://" + "owner:Sup3rS3cret@" + host + "/strata",
        "postgres" + "ql+psycopg2://" + "owner:Sup3rS3cret@" + host + "/strata",
    ]
    for i, dsn in enumerate(leaks):
        f = tmp_path / f"cfg{i}.py"
        f.write_text(f'DATABASE_URL = "{dsn}"\n')
        hits, scanned = scan_files([f.name], tmp_path)
        assert scanned == 1
        assert len(hits) == 1, f"missed {dsn.split('://')[0]}://  -> {hits}"
        assert "Sup3rS3cret" not in "\n".join(hits)


def test_placeholder_exemption_is_narrow(tmp_path):
    """.env.example skips only the DSN pattern — a real Neon password is still caught."""
    neon = "npg" + "_" + "RealLeakedSecret99"
    dsn = "postgres" + "ql+asyncpg://" + "user:password@" + "host/db"

    # placeholder DSN in .env.example: allowed
    (tmp_path / ".env.example").write_text(f"DATABASE_URL={dsn}\n")
    hits, _ = scan_files([".env.example"], tmp_path)
    assert hits == []

    # a genuine Neon credential in the SAME file: still caught
    (tmp_path / ".env.example").write_text(f"DATABASE_URL={dsn}\nPW={neon}\n")
    hits, _ = scan_files([".env.example"], tmp_path)
    assert len(hits) == 1 and ":2:" in hits[0]

    # the exemption must not leak to a normal file
    (tmp_path / "settings.py").write_text(f'URL = "{dsn}"\n')
    hits, _ = scan_files(["settings.py"], tmp_path)
    assert len(hits) == 1
