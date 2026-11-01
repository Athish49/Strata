"""Contract tests for the 14 verticals (tasks 3.6/3.7).

Since the frontend now fetches GET /company/verticals dynamically (task 3.7)
rather than carrying its own static copy, there is no second hand-synced list
to compare the backend against any more. What remains worth guarding, with no
DB connection and no app import needed for the first two:

1. The verticals-retaxonomy migration's NEW_VERTICALS seed is well-formed
   (14 rows, no duplicate name or slug).
2. The newer sort_order migration's ordering never silently drifts from
   NEW_VERTICALS' own order (they're two separate files; nothing but this test
   keeps them in sync).
3. GET /company/verticals actually returns all 14, ordered by sort_order,
   matching that same order -- via a FakeSession, the same technique
   test_company_routes.py already uses for this router.
"""
from __future__ import annotations

import ast
import pathlib

import httpx
import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = BACKEND / "migrations" / "versions"


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


def _sort_order_migration_slugs() -> list[str]:
    """``ORDERED_SLUGS`` from the sort_order migration, read with ``ast``."""
    candidates = [p for p in MIGRATIONS_DIR.glob("*.py") if "verticals_sort_order" in p.name]
    assert candidates, "verticals_sort_order migration file not found under backend/migrations/versions/"
    assert len(candidates) == 1, f"expected exactly one sort_order migration file, found {candidates}"
    tree = ast.parse(candidates[0].read_text(encoding="utf-8"))
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
        if any(isinstance(t, ast.Name) and t.id == "ORDERED_SLUGS" for t in targets):
            return ast.literal_eval(node.value)
    raise AssertionError("ORDERED_SLUGS not found in verticals_sort_order migration")


def test_migration_seed_has_14_rows():
    migration = _migration_new_verticals()
    assert len(migration) == 14
    names = [n for n, _ in migration]
    assert len(set(names)) == 14, "duplicate vertical name in NEW_VERTICALS"
    slugs = [s for _, s in migration]
    assert len(set(slugs)) == 14, "duplicate vertical slug in NEW_VERTICALS"


def test_sort_order_migration_matches_new_verticals_order():
    """The sort_order migration's ORDERED_SLUGS must be the exact same 14 slugs,
    in the exact same order, as NEW_VERTICALS -- these are two separate files
    and nothing but this test keeps them from drifting apart."""
    expected = [slug for _name, slug in _migration_new_verticals()]
    actual = _sort_order_migration_slugs()
    assert actual == expected, (
        "verticals_sort_order's ORDERED_SLUGS does not match NEW_VERTICALS' order:\n"
        f"NEW_VERTICALS order: {expected}\n"
        f"ORDERED_SLUGS:       {actual}"
    )


# ------------------------------------------------- GET /company/verticals


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    """Returns the 14 verticals, already ordered by sort_order, for any query
    whose text mentions company.verticals -- matches list_verticals()'s SQL."""

    def __init__(self, rows):
        self._rows = rows

    async def execute(self, stmt, params=None):
        if "company.verticals" in str(stmt):
            return _Res(self._rows)
        return _Res([])


@pytest.fixture
def _clear_overrides():
    yield
    from app.main import app
    app.dependency_overrides.clear()


async def test_list_verticals_returns_all_14_ordered_by_sort_order(_clear_overrides):
    from app.db import get_db
    from app.main import app

    expected_order = [slug for _name, slug in _migration_new_verticals()]
    rows = [
        {"name": name, "slug": slug, "description": "x", "sort_order": i}
        for i, (name, slug) in enumerate(_migration_new_verticals(), start=1)
    ]
    sess = _FakeSession(rows)

    async def _dep():
        yield sess

    app.dependency_overrides[get_db] = _dep
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get("/company/verticals")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 14
    assert [r["slug"] for r in body] == expected_order
    assert [r["sort_order"] for r in body] == list(range(1, 15))
    assert all(r["name"] and r["description"] for r in body)
