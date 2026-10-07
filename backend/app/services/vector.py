from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from app.config import settings


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )


def project_filter(extra_conditions: list = None) -> Filter:
    """
    Returns a Filter that always includes project=<QDRANT_PROJECT_TAG> as the first must condition.
    All Qdrant queries MUST use this — the cluster is shared with FDAComplianceAI.
    """
    must = [
        FieldCondition(
            key="project",
            match=MatchValue(value=settings.QDRANT_PROJECT_TAG),
        )
    ]
    if extra_conditions:
        must.extend(extra_conditions)
    return Filter(must=must)
