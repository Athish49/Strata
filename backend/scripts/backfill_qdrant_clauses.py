"""T7 — Qdrant company_clauses parity backfill.

Steps:
1. Identify missing clauses (Neon point IDs not in Qdrant)
2. Upsert missing clauses with real version_id in payload
3. Fix version_id on all existing points (was "v1", should be real UUID)
4. Backfill owner_id and doc_class on all existing points
5. Verify
"""
from __future__ import annotations

import os
import sys
import re

from dotenv import load_dotenv
load_dotenv()

# Ensure app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from app.config import settings
from app.company_ingest.ids import stable_uuid
from app.company_ingest.index.bm25 import build_sparse_vector
from app.company_ingest.index.embed import embed_texts
from app.company_ingest.index.qdrant_setup import COMPANY_COLLECTION
from app.services.vector import get_qdrant_client, project_filter
from qdrant_client.models import (  # type: ignore[import-untyped]
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    SparseVector,
)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_db_conn():
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "").split("?")[0]
    return psycopg2.connect(url, sslmode="require")


# ---------------------------------------------------------------------------
# Embedded text builder (inlined — mirrors embed.py logic without ClauseUnit)
# ---------------------------------------------------------------------------

def build_embedded_text_raw(
    heading_path: list[str],
    text_norm: str,
    role: str | None,
    section_kind: str,
    unit_kind: str,
) -> str:
    if role == "boilerplate":
        return ""
    if section_kind == "front_matter":
        return ""
    if unit_kind == "table_row" and not (text_norm or "").strip():
        return ""
    prefix = " > ".join(heading_path or [])
    body = (text_norm or "")[:2048]
    return f"{prefix} | {body}"


# ---------------------------------------------------------------------------
# 1. Gather Qdrant point IDs
# ---------------------------------------------------------------------------

def get_qdrant_point_ids(client) -> set[str]:
    """Scroll all point IDs from company_clauses filtered by project."""
    filt = project_filter()
    ids: set[str] = set()
    offset = None
    while True:
        results, next_offset = client.scroll(
            collection_name=COMPANY_COLLECTION,
            scroll_filter=filt,
            limit=500,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        for pt in results:
            ids.add(str(pt.id))
        if next_offset is None:
            break
        offset = next_offset
    return ids


# ---------------------------------------------------------------------------
# 2. Gather Neon clauses
# ---------------------------------------------------------------------------

def get_neon_clauses(conn):
    """Return all clause rows with their computed Qdrant point ID."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            clause_pk::text,
            company_id,
            version_id::text,
            doc_id,
            clause_id,
            local_id,
            parent_clause_id,
            ordinal,
            unit_kind,
            heading_path,
            section_kind,
            text_raw,
            text_norm,
            clause_role,
            assessable
        FROM company.clauses
        ORDER BY ordinal
        """
    )
    rows = cur.fetchall()
    clauses = []
    for row in rows:
        (
            clause_pk, company_id, version_id, doc_id, clause_id,
            local_id, parent_clause_id, ordinal, unit_kind, heading_path,
            section_kind, text_raw, text_norm, clause_role, assessable,
        ) = row
        point_id = str(stable_uuid(company_id, "v1", clause_id))
        clauses.append({
            "clause_pk": clause_pk,
            "company_id": company_id,
            "version_id": version_id,
            "doc_id": doc_id,
            "clause_id": clause_id,
            "local_id": local_id,
            "parent_clause_id": parent_clause_id,
            "ordinal": ordinal,
            "unit_kind": unit_kind,
            "heading_path": heading_path or [],
            "section_kind": section_kind,
            "text_raw": text_raw or "",
            "text_norm": text_norm or "",
            "clause_role": clause_role,
            "assessable": assessable,
            "point_id": point_id,
        })
    return clauses


# ---------------------------------------------------------------------------
# 3. Get doc metadata (version_id, owner_id, doc_class)
# ---------------------------------------------------------------------------

def get_doc_metadata(conn) -> dict[str, dict]:
    """Return {doc_id: {version_id, owner_id, doc_class}} for all rpl docs."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT doc_id, current_version_id::text, owner_id, doc_class
        FROM company.company_documents
        WHERE company_id = 'rpl'
        """
    )
    return {
        row[0]: {
            "version_id": row[1],
            "owner_id": row[2],
            "doc_class": row[3],
        }
        for row in cur.fetchall()
    }


# ---------------------------------------------------------------------------
# 4. Upsert missing clauses
# ---------------------------------------------------------------------------

def upsert_missing(client, missing_clauses: list[dict], doc_meta: dict) -> int:
    """Embed and upsert missing clause points. Returns count upserted."""
    if not missing_clauses:
        return 0

    # Filter to embeddable
    embeddable = [
        c for c in missing_clauses
        if build_embedded_text_raw(
            c["heading_path"], c["text_norm"],
            c["clause_role"], c["section_kind"], c["unit_kind"]
        )
    ]
    skipped = len(missing_clauses) - len(embeddable)
    if skipped:
        print(f"  Skipping {skipped} non-embeddable clauses (boilerplate/front_matter/blank table rows)")

    batch_size = 64
    total_upserted = 0

    for i in range(0, len(embeddable), batch_size):
        batch = embeddable[i : i + batch_size]
        texts = [
            build_embedded_text_raw(
                c["heading_path"], c["text_norm"],
                c["clause_role"], c["section_kind"], c["unit_kind"]
            )
            for c in batch
        ]
        dense_vecs = embed_texts(texts)

        points = []
        for clause, dense_vec in zip(batch, dense_vecs):
            doc_id = clause["doc_id"]
            meta = doc_meta.get(doc_id, {})
            real_version_id = meta.get("version_id") or clause["version_id"]
            owner_id = meta.get("owner_id")
            doc_class = meta.get("doc_class")

            sparse_dict = build_sparse_vector(clause["text_norm"])

            payload = {
                "project": settings.QDRANT_PROJECT_TAG,
                "company_id": clause["company_id"],
                "doc_id": doc_id,
                "version_id": real_version_id,
                "clause_id": clause["clause_id"],
                "local_id": clause["local_id"],
                "heading_path": clause["heading_path"],
                "unit_kind": clause["unit_kind"],
                "section_kind": clause["section_kind"],
                "clause_role": clause["clause_role"],
                "assessable": clause["assessable"],
                "is_current": True,
                "cited_sections": [],
                "cited_rules": [],
                "param_kinds": [],
                "param_units": [],
                "terms_used": [],
                "text_preview": clause["text_raw"][:200],
            }
            if owner_id is not None:
                payload["owner_id"] = owner_id
            if doc_class is not None:
                payload["doc_class"] = doc_class

            vectors = {
                "dense": dense_vec,
                "bm25": SparseVector(
                    indices=list(sparse_dict.keys()),
                    values=list(sparse_dict.values()),
                ),
            }

            points.append(
                PointStruct(
                    id=clause["point_id"],
                    vector=vectors,
                    payload=payload,
                )
            )

        client.upsert(collection_name=COMPANY_COLLECTION, points=points)
        total_upserted += len(points)
        print(f"  Upserted batch {i // batch_size + 1}: {len(points)} points")

    return total_upserted


# ---------------------------------------------------------------------------
# 5. Fix version_id / backfill owner_id + doc_class on existing points
# ---------------------------------------------------------------------------

def fix_payloads_by_doc(client, doc_meta: dict) -> int:
    """For each doc_id, use set_payload to correct version_id, owner_id, doc_class."""
    total_docs = 0
    for doc_id, meta in doc_meta.items():
        real_version_id = meta.get("version_id")
        owner_id = meta.get("owner_id")
        doc_class = meta.get("doc_class")

        doc_filter = project_filter([
            FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
        ])

        patch = {"version_id": real_version_id}
        if owner_id is not None:
            patch["owner_id"] = owner_id
        if doc_class is not None:
            patch["doc_class"] = doc_class

        client.set_payload(
            collection_name=COMPANY_COLLECTION,
            payload=patch,
            points=doc_filter,
        )
        total_docs += 1
        print(f"  Patched payload for doc_id={doc_id}: version_id={real_version_id}, owner_id={owner_id}, doc_class={doc_class}")

    return total_docs


# ---------------------------------------------------------------------------
# 6. Verify
# ---------------------------------------------------------------------------

def verify(client, neon_count: int):
    filt = project_filter()
    info = client.count(collection_name=COMPANY_COLLECTION, count_filter=filt)
    print(f"\nVerification:")
    print(f"  Qdrant total points: {info.count}")
    print(f"  Neon total clauses:  {neon_count}")
    if info.count == neon_count:
        print("  COUNT MATCH")
    else:
        print(f"  MISMATCH: still {neon_count - info.count} points short")

    # Sample 5 points and check payload
    results, _ = client.scroll(
        collection_name=COMPANY_COLLECTION,
        scroll_filter=filt,
        limit=5,
        with_payload=True,
        with_vectors=False,
    )
    print("\n  Sample payloads:")
    for pt in results:
        p = pt.payload or {}
        print(f"    id={pt.id}")
        print(f"      version_id={p.get('version_id')}, owner_id={p.get('owner_id')}, doc_class={p.get('doc_class')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== T7 Qdrant company_clauses parity backfill ===\n")

    client = get_qdrant_client()
    conn = get_db_conn()

    # Initial counts
    filt = project_filter()
    qdrant_before = client.count(collection_name=COMPANY_COLLECTION, count_filter=filt).count
    print(f"Before: Qdrant count={qdrant_before}")

    # Get all data
    print("\nFetching Neon clauses...")
    all_clauses = get_neon_clauses(conn)
    neon_count = len(all_clauses)
    print(f"Neon count: {neon_count}")

    print("\nFetching Qdrant point IDs...")
    qdrant_ids = get_qdrant_point_ids(client)
    print(f"Qdrant IDs fetched: {len(qdrant_ids)}")

    # Find missing
    missing = [c for c in all_clauses if c["point_id"] not in qdrant_ids]
    print(f"\nMissing clauses: {len(missing)}")
    for c in missing:
        print(f"  clause_id={c['clause_id']} doc_id={c['doc_id']} point_id={c['point_id']}")

    # Doc metadata
    print("\nFetching doc metadata...")
    doc_meta = get_doc_metadata(conn)
    print(f"Docs found: {len(doc_meta)}")

    # Upsert missing
    print("\n--- Step 2: Upserting missing clauses ---")
    n_upserted = upsert_missing(client, missing, doc_meta)
    print(f"Upserted: {n_upserted}")

    # Fix payloads on all existing points
    print("\n--- Steps 3-4: Fixing version_id / owner_id / doc_class on all points ---")
    n_docs_patched = fix_payloads_by_doc(client, doc_meta)
    print(f"Patched {n_docs_patched} doc_ids")

    conn.close()

    # Verify
    qdrant_after = client.count(collection_name=COMPANY_COLLECTION, count_filter=filt).count
    print(f"\nAfter: Qdrant count={qdrant_after}")
    verify(client, neon_count)

    print("\n=== Done ===")
    print(f"Before: Qdrant count={qdrant_before}, Neon count={neon_count}, missing={len(missing)}")
    print(f"After: Qdrant count={qdrant_after}")
    print(f"version_id fix: applied to {n_docs_patched} doc_ids (all points updated)")
    print(f"owner_id backfill: applied to {n_docs_patched} doc_ids")
    print(f"doc_class backfill: applied to {n_docs_patched} doc_ids")


if __name__ == "__main__":
    main()
