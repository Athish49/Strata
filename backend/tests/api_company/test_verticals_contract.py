"""Static contract test (task 3.6 step 4): the 14 (name, slug) pairs the
``verticals_retaxonomy`` migration seeds into ``company.verticals`` must exactly
match the 14 static ``{name, slug}`` pairs ``frontend/lib/verticals.ts`` ships.

No DB connection, no app import: both sides are read as plain text/AST, the same
technique ``tests/synthetic/test_corpus_meta.py`` already uses for this file pair,
so this test can't be broken by `.env`/DB availability during collection.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND.parent
MIGRATIONS_DIR = BACKEND / "migrations" / "versions"
FRONTEND_VERTICALS_TS = REPO_ROOT / "frontend" / "lib" / "verticals.ts"


def _migration_new_verticals() -> list[tuple[str, str]]:
    """``(name, slug)`` pairs from ``NEW_VERTICALS`` in the verticals-retaxonomy
    migration, read with ``ast`` (no import -> no alembic/DB context needed)."""
    candidates = [
        p for p in MIGRATIONS_DIR.glob("*.py")
        if "verticals_retaxonomy" in p.name or "retaxonomy" in p.name
    ]
    assert candidates, "verticals-retaxonomy migration file not found under backend/migrations/versions/"
    assert len(candidates) == 1, f"expected exactly one retaxonomy migration file, found {candidates}"
    tree = ast.parse(candidates[0].read_text(encoding="utf-8"))
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
        if any(isinstance(t, ast.Name) and t.id == "NEW_VERTICALS" for t in targets):
            rows = ast.literal_eval(node.value)
            return [(name, slug) for name, slug, _description in rows]
    raise AssertionError("NEW_VERTICALS not found in verticals-retaxonomy migration")


def _frontend_verticals() -> list[tuple[str, str]]:
    """``(name, slug)`` pairs parsed out of ``frontend/lib/verticals.ts``'s
    ``VERTICALS`` array (field order there is ``slug`` then ``name``)."""
    text = FRONTEND_VERTICALS_TS.read_text(encoding="utf-8")
    entries = re.findall(r'slug:\s*"([^"]+)"\s*,\s*name:\s*"([^"]+)"', text)
    assert entries, "could not parse any {slug, name} entries out of frontend/lib/verticals.ts"
    return [(name, slug) for slug, name in entries]


def test_migration_seed_has_14_rows():
    migration = _migration_new_verticals()
    assert len(migration) == 14
    names = [n for n, _ in migration]
    assert len(set(names)) == 14, "duplicate vertical name in NEW_VERTICALS"
    slugs = [s for _, s in migration]
    assert len(set(slugs)) == 14, "duplicate vertical slug in NEW_VERTICALS"


def test_frontend_verticals_has_14_rows():
    frontend = _frontend_verticals()
    assert len(frontend) == 14


def test_migration_verticals_match_frontend_exactly():
    """Both (name, slug) fields -- not just name -- must agree, in the same order,
    between the backend migration seed and the frontend's static vertical list."""
    migration = _migration_new_verticals()
    frontend = _frontend_verticals()
    assert migration == frontend, (
        "migration NEW_VERTICALS (name, slug) pairs do not exactly match "
        "frontend/lib/verticals.ts's VERTICALS (name, slug) pairs:\n"
        f"migration only: {sorted(set(migration) - set(frontend))}\n"
        f"frontend only: {sorted(set(frontend) - set(migration))}"
    )
