"""
Task 1.2.3 — Qdrant collection setup for company_clauses.

Creates the `company_clauses` collection with:
  - named dense vector  "dense"  (dim=384, Cosine) matching the regulatory collection
  - named sparse vector "bm25"   (IDF modifier) for hybrid search

Also creates payload indexes for every filterable field in SPEC §9, plus `project`
for cluster isolation (shared cluster with FDAComplianceAI).
"""
from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    SparseVectorParams,
    VectorParams,
    VectorsConfig,
)

try:
    from qdrant_client.models import Modifier, SparseVectorsConfig  # type: ignore[attr-defined]

    _SPARSE_PARAMS = SparseVectorParams(modifier=Modifier.IDF)
except (ImportError, AttributeError):
    from qdrant_client.models import SparseVectorsConfig  # type: ignore[no-redef]

    _SPARSE_PARAMS = SparseVectorParams()  # type: ignore[call-arg]

COMPANY_COLLECTION = "company_clauses"

# ---------------------------------------------------------------------------
# Payload index definitions — every field in SPEC §9 payload table + project
# ---------------------------------------------------------------------------

_KEYWORD_FIELDS = [
    "company_id",
    "doc_id",
    "version_id",
    "clause_id",
    "clause_role",
    "unit_kind",
    "section_kind",
    "cited_sections",
    "cited_rules",
    "param_kinds",
    "param_units",
    "terms_used",
    "doc_class",
    "owner_id",
    "project",  # cluster isolation — always filter by project = settings.QDRANT_PROJECT_TAG
]

_BOOL_FIELDS = [
    "is_current",
    "assessable",
]


def ensure_company_collection(
    client: QdrantClient,
    embed_dim: int = 384,
) -> None:
    """
    Create `company_clauses` if it does not exist, with the correct vector config.

    - Idempotent: if the collection already exists with a matching config, returns silently.
    - Raises ValueError if the collection exists but has a different dense vector size
      or distance (manual resolution required — could mean stale data from another model).
    - Also creates (or re-creates, which is a no-op) all payload indexes on every call,
      so the function remains idempotent end-to-end.
    """
    if client.collection_exists(COMPANY_COLLECTION):
        # Inspect the existing config for compatibility.
        info = client.get_collection(COMPANY_COLLECTION)
        vectors_cfg = info.config.params.vectors  # dict[str, VectorParams] for named vectors

        # Normalise: VectorsConfig may be a plain dict or a NamedVectors mapping.
        if isinstance(vectors_cfg, dict):
            dense_cfg = vectors_cfg.get("dense")
        else:
            # NamedVectors / VectorsConfig object — access as attribute or mapping
            try:
                dense_cfg = vectors_cfg["dense"]
            except (KeyError, TypeError):
                dense_cfg = getattr(vectors_cfg, "dense", None)

        if dense_cfg is None:
            raise ValueError(
                f"{COMPANY_COLLECTION} exists with incompatible vector config"
                " — manual resolution required"
            )

        existing_size = getattr(dense_cfg, "size", None)
        existing_distance = getattr(dense_cfg, "distance", None)

        if existing_size != embed_dim or existing_distance != Distance.COSINE:
            raise ValueError(
                f"{COMPANY_COLLECTION} exists with incompatible vector config"
                " — manual resolution required"
            )

        # Compatible — fall through to payload index creation (idempotent).
    else:
        client.create_collection(
            collection_name=COMPANY_COLLECTION,
            vectors_config={
                "dense": VectorParams(size=embed_dim, distance=Distance.COSINE),
            },
            sparse_vectors_config={
                "bm25": _SPARSE_PARAMS,
            },
        )

    # Create payload indexes — qdrant-client skips silently if already present,
    # so this block is safe to re-run on every call.
    for field in _KEYWORD_FIELDS:
        client.create_payload_index(
            collection_name=COMPANY_COLLECTION,
            field_name=field,
            field_schema=PayloadSchemaType.KEYWORD,
        )

    for field in _BOOL_FIELDS:
        client.create_payload_index(
            collection_name=COMPANY_COLLECTION,
            field_name=field,
            field_schema=PayloadSchemaType.BOOL,
        )
