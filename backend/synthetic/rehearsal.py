#!/usr/bin/env python
"""End-to-end rehearsal of the v2 stack on a THROWAWAY database (task 9.1, part C).

Run from anywhere::

    backend/.venv/bin/python backend/synthetic/rehearsal.py

It never writes to production and never calls a real external service:

1. ``initdb`` a scratch cluster under a temp dir, listening on 127.0.0.1 and a
   random free port, unix sockets off, SSL on with a throwaway self-signed
   certificate (``app/db.py`` and ``migrations/env.py`` both force
   ``ssl=require``, so a plain cluster would refuse them).
2. Run the REAL migration chain (``alembic upgrade head``) in a subprocess whose
   environment holds only the scratch ``DATABASE_URL`` and dummy values, with the
   v2 wipe token set; then diff the migrated ``company`` schema against
   ``tests/engine/fixtures/company_schema.sql`` (the schema every real-Postgres
   test so far ran against).
3. Copy ``public.code_sections`` and its foreign-key parents from production with
   ``synthetic/copy_kb.py`` (a separate process, read-only session, SELECT only).
4. Run the app + the seeder (``synthetic/seed.py``) in a subprocess
   (``--inner``) whose environment contains ONLY the scratch ``DATABASE_URL`` and
   dummy ``QDRANT_*``/``R2_*``/``LLM_API_KEY`` values, started in an empty working
   directory so pydantic-settings cannot read ``backend/.env``. Inside it, R2 is
   ``moto``, Qdrant is an in-memory fake, embeddings are a deterministic hash, the
   LLM provider is a deterministic stub, and every non-loopback socket is refused.
5. Assert the acceptance criteria, print the parity-prediction table, and stop the
   cluster in a ``finally``.

Exit status 0 = every assertion held.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent          # backend/synthetic
BACKEND = HERE.parent                           # backend
PG_BIN = Path(os.environ.get("STRATA_PG_BIN", "/opt/homebrew/opt/postgresql@17/bin"))
FIXTURE_SQL = BACKEND / "tests" / "engine" / "fixtures" / "company_schema.sql"
BASELINE_JSON = HERE / "baseline_before_v2.json"
WIPE_TOKEN = "yes-destroy-company-and-engine-data"

#: Dummy values for every setting the app requires. None of them can reach a real
#: service: R2 is intercepted by moto, Qdrant/LLM/embeddings are replaced in-process.
DUMMY_SETTINGS = {
    "QDRANT_URL": "http://qdrant.rehearsal.invalid:6333",
    "QDRANT_API_KEY": "rehearsal-dummy",
    "QDRANT_PROJECT_TAG": "strata",
    # An AWS-shaped endpoint so moto recognises (and intercepts) the S3 calls.
    "R2_ENDPOINT": "https://s3.amazonaws.com",
    "R2_ACCESS_KEY_ID": "rehearsal-dummy",
    "R2_SECRET_ACCESS_KEY": "rehearsal-dummy",
    "R2_BUCKET_NAME": "strata-rehearsal",
    "LLM_API_KEY": "rehearsal-dummy",
    "LLM_PROVIDER": "anthropic",
    "FRONTEND_URL": "http://localhost:3000",
    "INGEST_STARTUP_SWEEP": "0",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def banner(msg: str) -> None:
    log("\n" + "=" * 78 + f"\n{msg}\n" + "=" * 78)


# ======================================================================== env
def child_env(db_url: str, workdir: Path, *, extra: dict | None = None) -> dict:
    """A from-scratch environment: nothing inherited except PATH. HOME points at the
    scratch dir so libpq/asyncpg cannot pick up the user's ~/.postgresql certs."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(workdir),
        "PYTHONPATH": str(BACKEND),
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "DATABASE_URL": db_url,
        **DUMMY_SETTINGS,
    }
    if extra:
        env.update(extra)
    return env


def assert_scratch_url(db_url: str) -> None:
    host = urlparse(db_url).hostname
    if host != "127.0.0.1":
        raise SystemExit(f"refusing to run: database host is {host!r}, not 127.0.0.1")


# ===================================================================== cluster
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ScratchCluster:
    def __init__(self, base: Path):
        self.base = base
        self.data = base / "pgdata"
        self.port = _free_port()
        self.started = False

    def _bin(self, name: str) -> str:
        p = PG_BIN / name
        if not p.exists():
            raise SystemExit(f"postgres binary not found: {p}")
        return str(p)

    def start(self) -> None:
        subprocess.run([self._bin("initdb"), "-D", str(self.data), "-A", "trust", "-U", "postgres",
                        "-E", "UTF8", "--no-sync"], check=True, capture_output=True)
        crt, key = self.base / "server.crt", self.base / "server.key"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
                        "-subj", "/CN=127.0.0.1", "-keyout", str(key), "-out", str(crt)],
                       check=True, capture_output=True)
        key.chmod(0o600)
        opts = (f"-p {self.port} -c listen_addresses=127.0.0.1 -c unix_socket_directories='' "
                f"-c fsync=off -c synchronous_commit=off -c full_page_writes=off "
                f"-c ssl=on -c ssl_cert_file={crt} -c ssl_key_file={key} -c max_connections=200")
        subprocess.run([self._bin("pg_ctl"), "start", "-D", str(self.data), "-w", "-t", "60",
                        "-l", str(self.base / "postgres.log"), "-o", opts],
                       check=True, capture_output=True)
        self.started = True
        for db in ("strata", "fixture_schema"):
            self.sql("postgres", f"CREATE DATABASE {db}")

    def stop(self) -> None:
        if self.started:
            subprocess.run([self._bin("pg_ctl"), "-D", str(self.data), "-m", "immediate", "stop"],
                           capture_output=True)
            self.started = False

    def url(self, db: str = "strata") -> str:
        return f"postgresql://postgres@127.0.0.1:{self.port}/{db}"

    def connect(self, db: str = "strata"):
        import psycopg2

        con = psycopg2.connect(host="127.0.0.1", port=self.port, user="postgres", dbname=db,
                               sslmode="require")
        con.autocommit = True
        return con

    def sql(self, db: str, statement: str):
        con = self.connect(db)
        try:
            cur = con.cursor()
            cur.execute(statement)
            return cur.fetchall() if cur.description else None
        finally:
            con.close()


# ================================================================== migration
def migrate_mode(db_url: str) -> int:
    """Child process: run the real alembic chain to head via the Python API, with an
    absolute script_location (alembic.ini's relative paths assume cwd=backend/)."""
    assert_scratch_url(db_url)
    if Path(".env").exists():
        raise SystemExit("refusing to migrate: a .env file is present in the working directory")
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")
    command.current(cfg)
    return 0


_COLS_SQL = """
SELECT table_name, column_name, data_type, is_nullable, coalesce(column_default, '')
FROM information_schema.columns WHERE table_schema = 'company'
ORDER BY table_name, column_name
"""
_IDX_SQL = """
SELECT tablename, regexp_replace(indexdef, ' [a-z_0-9]+ ON ', ' <name> ON ')
FROM pg_indexes WHERE schemaname = 'company' ORDER BY 1, 2
"""


def schema_diff(cluster: ScratchCluster) -> list[str]:
    """Differences between the migrated schema and the hand-written test fixture."""
    cluster.sql("fixture_schema", FIXTURE_SQL.read_text())
    out: list[str] = []
    for label, q in (("column", _COLS_SQL), ("index", _IDX_SQL)):
        mig = set(map(tuple, cluster.sql("strata", q)))
        fix = set(map(tuple, cluster.sql("fixture_schema", q)))
        for row in sorted(mig - fix):
            out.append(f"{label} only in MIGRATION: {row}")
        for row in sorted(fix - mig):
            out.append(f"{label} only in FIXTURE:   {row}")
    return out


# ====================================================================== outer
def run_child(cmd: list[str], env: dict, cwd: Path, title: str) -> None:
    banner(title)
    t0 = time.monotonic()
    proc = subprocess.run(cmd, env=env, cwd=str(cwd), stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True)
    sys.stdout.write(proc.stdout)
    log(f"[{title}] exit={proc.returncode} in {time.monotonic() - t0:.1f}s")
    if proc.returncode != 0:
        raise SystemExit(f"{title} failed (exit {proc.returncode})")


def outer(args) -> int:
    if not PG_BIN.exists():
        raise SystemExit(f"postgres binaries not found at {PG_BIN}")
    base = Path(tempfile.mkdtemp(prefix="strata-rehearsal-"))
    work = base / "work"
    work.mkdir()
    cluster = ScratchCluster(base)
    try:
        banner(f"scratch cluster: 127.0.0.1:{cluster.port} (SSL on, unix sockets off) in {base}")
        cluster.start()
        url = cluster.url()
        assert_scratch_url(url)
        env = child_env(url, work, extra={"STRATA_ALLOW_V2_WIPE": WIPE_TOKEN})
        run_child([sys.executable, str(Path(__file__).resolve()), "--migrate", "--db-url", url],
                  env, work, "alembic upgrade head (real migration chain)")
        banner("schema diff: migrated company.* vs tests/engine/fixtures/company_schema.sql")
        diff = schema_diff(cluster)
        for line in diff:
            log("  " + line)
        log(f"  {len(diff)} difference(s)")
        if args.stop_after == "migrate":
            return 0
        # copy_kb reads the production URL from backend/.env itself; this process never does.
        kb_env = {"PATH": os.environ.get("PATH", ""), "HOME": str(work),
                  "PYTHONPATH": str(BACKEND), "PYTHONUNBUFFERED": "1",
                  "PYTHONDONTWRITEBYTECODE": "1"}
        run_child([sys.executable, str(HERE / "copy_kb.py"), "--target-url", url],
                  kb_env, work, "copy public.code_sections from production (read-only)")
        if args.stop_after == "copy":
            return 0
        run_child([sys.executable, str(Path(__file__).resolve()), "--inner", "--db-url", url],
                  child_env(url, work), work, "app + seeder rehearsal (in-process ASGI)")
        return 0
    finally:
        cluster.stop()
        if not args.keep:
            shutil.rmtree(base, ignore_errors=True)
        else:
            log(f"kept {base}")


# ====================================================================== main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--migrate", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--db-url", help=argparse.SUPPRESS)
    ap.add_argument("--stop-after", choices=["migrate", "copy"], default=None,
                    help="stop after the given stage (debugging)")
    ap.add_argument("--keep", action="store_true", help="keep the scratch directory")
    args = ap.parse_args(argv)
    if args.migrate:
        return migrate_mode(args.db_url)
    if args.inner:
        from synthetic.rehearsal_inner import inner  # lazy: imports app/ under child_env()

        return inner(args.db_url)
    return outer(args)


if __name__ == "__main__":
    sys.exit(main())
