#!/usr/bin/env python
"""Copy the regulatory knowledge base from production into a SCRATCH database (task 9.1 C3).

    backend/.venv/bin/python backend/synthetic/copy_kb.py --target-url postgresql://postgres@127.0.0.1:PORT/strata

Copies ``public.code_sections`` (the 4,603-row KB the citation resolver reads) plus
every table it has a foreign key to (``public.agencies``), so a rehearsal resolves
citations against real data.

Safety rules, all enforced here:

* The production URL is read from ``backend/.env`` with ``dotenv_values`` (it never
  enters ``os.environ``, so no child process can inherit it) and is never printed or
  logged; connection errors are re-raised with a sanitised message.
* The production session is ``readonly=True`` and only ever runs SELECTs.
* The target must be on 127.0.0.1 and must not be the production database.
* ``pg_dump`` is not used: production is Postgres 18 and the local client is 17.
  Rows are read with SELECT and written with batched INSERTs into the tables the
  real migration chain already created, using the intersection of the two column
  sets (differences are reported).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

BACKEND = Path(__file__).resolve().parents[1]
ROOT_TABLE = ("public", "code_sections")

_FK_SQL = """
SELECT DISTINCT ccu.table_schema, ccu.table_name
FROM information_schema.table_constraints tc
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name AND ccu.constraint_schema = tc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s AND tc.table_name = %s
"""
_COLS_SQL = """
SELECT column_name FROM information_schema.columns
WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position
"""
_SELF_FK_SQL = """
SELECT kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON kcu.constraint_name = tc.constraint_name AND kcu.constraint_schema = tc.constraint_schema
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name AND ccu.constraint_schema = tc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s AND tc.table_name = %s
  AND ccu.table_schema = %s AND ccu.table_name = %s
"""


def _psycopg2_dsn(url: str) -> str:
    """postgresql+asyncpg://… -> postgresql://… (keeps the query string, e.g. sslmode)."""
    scheme, sep, rest = url.partition("://")
    return "postgresql://" + rest if sep else url


def _prod_url() -> str:
    from dotenv import dotenv_values

    env_file = BACKEND / ".env"
    if not env_file.is_file():
        raise SystemExit("no backend/.env: production read credentials are unavailable")
    url = (dotenv_values(env_file).get("DATABASE_URL") or "").strip()
    if not url:
        raise SystemExit("backend/.env has no DATABASE_URL")
    return url


def _connect_prod():
    import psycopg2

    url = _prod_url()
    try:
        con = psycopg2.connect(_psycopg2_dsn(url))
    except Exception as exc:  # the message may contain the host: never echo it
        raise SystemExit(f"could not connect to the production KB ({type(exc).__name__}); "
                         "details suppressed to avoid printing credentials") from None
    con.set_session(readonly=True, autocommit=False)
    return con, urlparse(_psycopg2_dsn(url)).hostname


def _connect_target(url: str):
    import psycopg2

    con = psycopg2.connect(_psycopg2_dsn(url), sslmode="require")
    con.autocommit = False
    return con


def _q(schema: str, table: str) -> str:
    return f'"{schema}"."{table}"'


def _tables_to_copy(prod) -> list[tuple[str, str]]:
    """ROOT_TABLE and its FK parents (transitively), parents first."""
    order: list[tuple[str, str]] = []

    def visit(t: tuple[str, str], stack: tuple) -> None:
        if t in order or t in stack:
            return
        with prod.cursor() as cur:
            cur.execute(_FK_SQL, t)
            parents = [tuple(r) for r in cur.fetchall() if tuple(r) != t]
        for p in parents:
            visit(p, stack + (t,))
        order.append(t)

    visit(ROOT_TABLE, ())
    return order


def _columns(con, t) -> list[str]:
    with con.cursor() as cur:
        cur.execute(_COLS_SQL, t)
        return [r[0] for r in cur.fetchall()]


def _self_fk_columns(con, t) -> list[str]:
    with con.cursor() as cur:
        cur.execute(_SELF_FK_SQL, (*t, *t))
        return [r[0] for r in cur.fetchall()]


def copy_table(prod, target, t, batch: int = 500) -> int:
    from psycopg2.extras import execute_values

    pcols, tcols = _columns(prod, t), _columns(target, t)
    if not tcols:
        raise SystemExit(f"target has no table {_q(*t)} (did the migration run?)")
    cols = [c for c in pcols if c in tcols]
    only_prod = [c for c in pcols if c not in tcols]
    only_target = [c for c in tcols if c not in pcols]
    if only_prod or only_target:
        print(f"  {_q(*t)} column differences: only in production={only_prod} "
              f"only in scratch={only_target}")
    deferred = [c for c in _self_fk_columns(target, t) if c in cols]
    col_sql = ", ".join(f'"{c}"' for c in cols)
    with target.cursor() as tc:
        tc.execute(f"TRUNCATE {_q(*t)} CASCADE")
    n = 0
    later: list[tuple] = []
    with prod.cursor(name=f"copy_{t[1]}") as pc:  # server-side cursor: streams
        pc.itersize = batch
        pc.execute(f"SELECT {col_sql} FROM {_q(*t)} ORDER BY 1")
        while True:
            rows = pc.fetchmany(batch)
            if not rows:
                break
            if deferred:  # self-references are filled in a second pass
                idx = [cols.index(c) for c in deferred]
                for r in rows:
                    if any(r[i] is not None for i in idx):
                        later.append((r[0], *[r[i] for i in idx]))
                rows = [tuple(None if i in idx else v for i, v in enumerate(r)) for r in rows]
            with target.cursor() as tc:
                execute_values(tc, f"INSERT INTO {_q(*t)} ({col_sql}) VALUES %s", rows,
                               page_size=batch)
            n += len(rows)
    if later:
        with target.cursor() as tc:
            sets = ", ".join(f'"{c}" = %s' for c in deferred)
            for row in later:
                tc.execute(f'UPDATE {_q(*t)} SET {sets} WHERE "{cols[0]}" = %s', (*row[1:], row[0]))
    # Keep serial sequences ahead of the copied ids.
    with target.cursor() as tc:
        tc.execute("SELECT pg_get_serial_sequence(%s, %s)", (f"{t[0]}.{t[1]}", cols[0]))
        seq = tc.fetchone()[0]
        if seq:
            tc.execute(f'SELECT setval(%s, COALESCE((SELECT MAX("{cols[0]}") FROM {_q(*t)}), 1))', (seq,))
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Copy the KB from production into a scratch DB.")
    ap.add_argument("--target-url", required=True, help="scratch database URL (must be 127.0.0.1)")
    args = ap.parse_args(argv)

    if urlparse(_psycopg2_dsn(args.target_url)).hostname != "127.0.0.1":
        raise SystemExit("refusing: the target database must be on 127.0.0.1")

    prod, prod_host = _connect_prod()
    if prod_host in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("refusing: backend/.env points at a local database, not production")
    target = _connect_target(args.target_url)
    try:
        tables = _tables_to_copy(prod)
        print(f"copying (parents first): {', '.join(_q(*t) for t in tables)}")
        counts = {}
        for t in tables:
            counts[t] = copy_table(prod, target, t)
            print(f"  {_q(*t)}: {counts[t]} rows")
        # Verify against the source, then commit the target.
        for t, n in counts.items():
            with prod.cursor() as pc:
                pc.execute(f"SELECT count(*) FROM {_q(*t)}")
                src = pc.fetchone()[0]
            if src != n:
                raise SystemExit(f"{_q(*t)}: copied {n} rows but production has {src}")
        target.commit()
        prod.rollback()  # read-only transaction: nothing to keep
        print("KB copy verified against production row counts and committed to the scratch DB")
    finally:
        prod.close()
        target.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
