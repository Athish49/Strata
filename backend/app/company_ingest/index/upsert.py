"""Task 6.2.1 — Qdrant upsert helpers for company clause indexing."""
from __future__ import annotations

from app.config import settings
from app.company_ingest.index.bm25 import build_sparse_vector_for_unit
from app.company_ingest.index.embed import build_embedded_text, embed_texts
from app.company_ingest.index.qdrant_setup import COMPANY_COLLECTION
from app.company_ingest.ids import stable_uuid
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext


def _make_client():  # type: ignore[return]
    from qdrant_client import QdrantClient  # type: ignore[import-untyped]
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)


def _build_payload(unit: ClauseUnit, company_id: str, version_id: str) -> dict:
    return {
        "project": settings.QDRANT_PROJECT_TAG,
        "company_id": company_id,
        "doc_id": unit.doc_id,
        "version_id": version_id,
        "clause_id": unit.clause_id,
        "local_id": unit.local_id,
        "heading_path": unit.heading_path,
        "unit_kind": unit.unit_kind,
        "section_kind": unit.section_kind,
        "clause_role": unit.role,
        "assessable": unit.assessable,
        "is_current": True,
        "cited_sections": [
            e.parsed.normalized_key
            for e in unit.citations
            if hasattr(e, "parsed") and e.parsed.normalized_key
        ],
        "cited_rules": list({
            e.parsed.rule_key
            for e in unit.citations
            if hasattr(e, "parsed") and e.parsed.rule_key
        }),
        "param_kinds": list({p.kind for p in unit.parameters if hasattr(p, "kind")}),
        "param_units": list({
            p.unit for p in unit.parameters if hasattr(p, "unit") and p.unit
        }),
        "terms_used": [t.term for t in unit.terms if hasattr(t, "term")],
        "text_preview": unit.text_raw[:200],
    }


async def upsert_clauses(
    units: list[ClauseUnit],
    company_id: str,
    version_id: str,
    ctx: RunContext,
    batch_size: int = 128,
) -> None:
    """Upsert ClauseUnit objects into the company_clauses Qdrant collection.

    Builds dense and sparse vectors, constructs payload per SPEC §9, upserts in batches.
    Skips units where build_embedded_text returns "".
    """
    from qdrant_client.models import PointStruct, SparseVector  # type: ignore[import-untyped]

    client = _make_client()

    # Filter to embeddable units
    embeddable: list[ClauseUnit] = []
    for unit in units:
        if build_embedded_text(unit):
            embeddable.append(unit)

    # Process in batches
    for i in range(0, len(embeddable), batch_size):
        batch_units = embeddable[i : i + batch_size]

        # Build embedded texts for the batch
        texts = [build_embedded_text(u) for u in batch_units]
        dense_vectors = embed_texts(texts)

        points = []
        for unit, dense_vec in zip(batch_units, dense_vectors):
            point_id = str(stable_uuid(company_id, version_id, unit.clause_id))
            sparse_dict = build_sparse_vector_for_unit(unit)

            payload = _build_payload(unit, company_id, version_id)

            # Build named vectors dict
            vectors: dict = {
                "dense": dense_vec,
                "bm25": SparseVector(
                    indices=list(sparse_dict.keys()),
                    values=list(sparse_dict.values()),
                ),
            }

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vectors,
                    payload=payload,
                )
            )

        client.upsert(collection_name=COMPANY_COLLECTION, points=points)
        ctx.count("clauses_indexed", len(points))


async def mark_previous_versions_stale(
    doc_id: str,
    current_version_id: str,
    company_id: str,
) -> None:
    """Set is_current=False on all points for this doc_id except current_version_id."""
    from qdrant_client.models import (  # type: ignore[import-untyped]
        FieldCondition,
        Filter,
        MatchValue,
        MatchExcept,
    )

    client = _make_client()

    stale_filter = Filter(
        must=[
            FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
            FieldCondition(key="company_id", match=MatchValue(value=company_id)),
        ],
        must_not=[
            FieldCondition(key="version_id", match=MatchValue(value=current_version_id)),
        ],
    )

    client.set_payload(
        collection_name=COMPANY_COLLECTION,
        payload={"is_current": False},
        points=stale_filter,
    )
