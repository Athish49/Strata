from fastapi import APIRouter, Depends, Query, HTTPException
from qdrant_client.models import Filter, FieldCondition, MatchValue
from app.services.vector import get_qdrant_client, project_filter
from app.config import settings
from app.regulatory.ingestion.embedder import get_embedding_model

router = APIRouter(prefix="/search", tags=["search"])
COLLECTION_NAME = "regulation_chunks"


@router.get("")
def semantic_search(
    q: str = Query(..., description="The search query"),
    source_system: str = Query(None, description="Filter by source system"),
    agency: str = Query(None, description="Filter by agency"),
    status: str = Query(None, description="Filter by status"),
    k: int = Query(10, ge=1, le=50, description="Number of results to return"),
):
    """Semantic search across regulations and regulatory actions."""
    # Embed the query
    embedding = get_embedding_model().encode([q])[0].tolist()

    # Build filter using project_filter() as base — ALWAYS required for cluster isolation
    base_filter = project_filter()  # already has project=strata as first must

    # Add optional user filters to base_filter.must
    if source_system:
        base_filter.must.append(
            FieldCondition(key="source_system", match=MatchValue(value=source_system))
        )
    if agency:
        base_filter.must.append(
            FieldCondition(key="agency", match=MatchValue(value=agency))
        )
    if status:
        base_filter.must.append(
            FieldCondition(key="status", match=MatchValue(value=status))
        )

    # Execute search
    qdrant_client = get_qdrant_client()
    try:
        response = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=embedding,
            query_filter=base_filter,
            limit=k,
        )
        hits = response.points
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Vector search failed: {str(e)}")

    results = []
    for hit in hits:
        payload = hit.payload or {}
        result = {
            "citation": payload.get("citation"),
            "source_system": payload.get("source_system"),
            "heading": payload.get("heading"),
            "chunk_text": payload.get("chunk_text"),
            "agency": payload.get("agency"),
            "status": payload.get("status"),
            "score": hit.score,
        }
        results.append(result)

    return {
        "query": q,
        "results": results,
        "total": len(results),
    }
