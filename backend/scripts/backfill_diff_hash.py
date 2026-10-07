"""
backfill_diff_hash.py — Compute and store diff_hash for all code_sections rows.

diff_hash = SHA-256( normalize_for_diff(body_text, source_system) )

Only updates rows where diff_hash IS NULL (idempotent / safe to re-run).

Run::

    cd /Users/athish/Documents/Strata/backend
    .venv/bin/python scripts/backfill_diff_hash.py

Add --dry-run to count rows without writing.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

# Make project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import psycopg2

from app.regulatory.ingestion.normalize import normalize_for_diff


BATCH_SIZE = 200


def compute_diff_hash(body_text: str, source_system: str) -> str:
    normalized = normalize_for_diff(body_text, source_system)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def make_conn(db_url: str) -> psycopg2.extensions.connection:
    return psycopg2.connect(db_url, sslmode="require", connect_timeout=30)


def main(dry_run: bool = False) -> None:
    db_url = os.environ["DATABASE_URL"].replace("+asyncpg", "").split("?")[0]

    conn = make_conn(db_url)
    cur = conn.cursor()

    # Count rows to update
    cur.execute("SELECT COUNT(*) FROM code_sections WHERE diff_hash IS NULL")
    total = cur.fetchone()[0]
    print(f"Rows with diff_hash IS NULL: {total}")
    conn.close()

    if total == 0:
        print("Nothing to update.")
        return

    if dry_run:
        print("--dry-run: no writes performed.")
        return

    # Fetch IDs first (cheap), then process in small batches
    conn = make_conn(db_url)
    cur = conn.cursor()
    cur.execute("SELECT id FROM code_sections WHERE diff_hash IS NULL ORDER BY id")
    all_ids = [r[0] for r in cur.fetchall()]
    conn.close()

    updated = 0
    for batch_start in range(0, len(all_ids), BATCH_SIZE):
        batch_ids = all_ids[batch_start : batch_start + BATCH_SIZE]

        conn = make_conn(db_url)
        conn.autocommit = False
        cur = conn.cursor()

        # Fetch body_text for this batch
        cur.execute(
            "SELECT id, body_text, source_system FROM code_sections"
            " WHERE id = ANY(%s) AND diff_hash IS NULL",
            (batch_ids,),
        )
        rows = cur.fetchall()

        updates = [
            (compute_diff_hash(body_text or "", source_system or ""), row_id)
            for row_id, body_text, source_system in rows
        ]

        if updates:
            cur.executemany(
                "UPDATE code_sections SET diff_hash = %s"
                " WHERE id = %s AND diff_hash IS NULL",
                updates,
            )
            conn.commit()
            updated += len(updates)

        conn.close()
        print(f"  Updated {updated}/{total}…")

    print(f"Done. Rows updated: {updated}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill diff_hash on code_sections.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count rows without writing.",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
