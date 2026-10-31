"""Shared fixture for the task 9.1d tests: a throwaway local PostgreSQL cluster.

``initdb`` in a pytest tmp dir, unix socket only (``listen_addresses=''``), torn down
afterwards - the same pattern as ``tests/company_ingest/test_promote.py``. It never
connects to ``DATABASE_URL`` and nothing here reads ``backend/.env``.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import uuid
from pathlib import Path

import pytest


def _pg_bin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for cand in sorted(Path("/opt/homebrew/opt").glob("postgresql@*/bin/" + name), reverse=True):
        return str(cand)
    return None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def scratch_pg(tmp_path_factory):
    """``{"host": <socket dir>, "port": int, "dsn": psycopg2 kwargs, "async_url": str}``."""
    initdb, pg_ctl = _pg_bin("initdb"), _pg_bin("pg_ctl")
    if not (initdb and pg_ctl):
        pytest.skip("no local initdb/pg_ctl for a scratch PostgreSQL cluster")
    base = tmp_path_factory.mktemp("pg91d")
    data, sock = base / "data", Path(f"/tmp/strata-pg-{uuid.uuid4().hex[:8]}")
    sock.mkdir()
    port = _free_port()
    subprocess.run([initdb, "-D", str(data), "-A", "trust", "-U", "postgres", "--no-sync"],
                   check=True, capture_output=True)
    # macOS postgres refuses to start without a valid LC_ALL ("postmaster became multithreaded")
    env = {**os.environ, "LC_ALL": os.environ.get("LC_ALL") or "C"}
    subprocess.run([pg_ctl, "start", "-D", str(data), "-w", "-l", str(base / "log"), "-o",
                    f"-p {port} -k {sock} -c listen_addresses='' -c fsync=off"],
                   check=True, capture_output=True, env=env)
    try:
        yield {"host": str(sock), "port": port,
               "dsn": {"host": str(sock), "port": port, "user": "postgres"},
               "async_url_tpl": f"postgresql+asyncpg://postgres@/{{db}}?host={sock}&port={port}"}
    finally:
        subprocess.run([pg_ctl, "-D", str(data), "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(sock, ignore_errors=True)


def fresh_database(pg: dict, name: str):
    """(Re)create database *name* and return an autocommit psycopg2 connection to it."""
    import psycopg2

    admin = psycopg2.connect(dbname="postgres", **pg["dsn"])
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        cur.execute(f'CREATE DATABASE "{name}"')
    admin.close()
    con = psycopg2.connect(dbname=name, **pg["dsn"])
    con.autocommit = True
    return con
