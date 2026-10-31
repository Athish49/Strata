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


def build_points(
    units: list[ClauseUnit],
    company_id: str,
    version_id: str,
    batch_size: int = 128,
) -> list[list]:
    """Embed and build Qdrant points for ``units``, grouped into upsert batches.

    Point id is ``stable_uuid(company_id, version_id, clause_id)`` with the REAL
    ``version_id`` (v1 passed the literal ``"v1"``, so every version overwrote the
    previous one's vectors). Units for which ``build_embedded_text`` is ``""``
    (boilerplate, front matter, blank table rows) are skipped.
    """
    from qdrant_client.models import PointStruct, SparseVector  # type: ignore[import-untyped]

    embeddable = [u for u in units if build_embedded_text(u)]
    batches: list[list] = []
    for i in range(0, len(embeddable), batch_size):
        batch_units = embeddable[i : i + batch_size]
        dense_vectors = embed_texts([build_embedded_text(u) for u in batch_units])
        points = []
        for unit, dense_vec in zip(batch_units, dense_vectors):
            sparse_dict = build_sparse_vector_for_unit(unit)
            points.append(
                PointStruct(
                    id=str(stable_uuid(company_id, version_id, unit.clause_id)),
                    vector={
                        "dense": dense_vec,
                        "bm25": SparseVector(
                            indices=list(sparse_dict.keys()),
                            values=list(sparse_dict.values()),
                        ),
                    },
                    payload=_build_payload(unit, company_id, version_id),
                )
            )
        batches.append(points)
    return batches


async def upsert_clauses(
    units: list[ClauseUnit],
    company_id: str,
    version_id: str,
    ctx: RunContext,
    batch_size: int = 128,
    client=None,
) -> None:
    """Upsert ClauseUnit objects into the company_clauses Qdrant collection.

    Builds dense and sparse vectors, constructs payload per SPEC §9, upserts in batches.
    Skips units where build_embedded_text returns "".

    This is a raw write with no delete. The only production caller is
    ``promote.reindex_document`` (task 5.6), which deletes the document's points
    first — presence in the collection means live, so nothing else may index.
    """
    client = client or _make_client()
    for points in build_points(units, company_id, version_id, batch_size):
        client.upsert(collection_name=COMPANY_COLLECTION, points=points)
        ctx.count("clauses_indexed", len(points))
