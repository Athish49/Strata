from typing import Union
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.vector import get_qdrant_client, project_filter
from app.config import settings

COLLECTION_NAME = "regulation_chunks"
CHUNK_SIZE = 500  # words per chunk
CHUNK_OVERLAP = 50  # overlapping words between chunks

_model = None


def get_embedding_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping word-based chunks."""
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start = end - overlap

    return chunks


def embed_text(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using the model. Return list of embedding vectors."""
    model = get_embedding_model()
    embeddings = model.encode(texts)
    return [emb.tolist() for emb in embeddings]


def embed_and_store_code_section(
    record_id: int,
    citation: str,
    source_system: str,
    heading: str,
    body_text: str,
    agency: str,
    status: str,
    jurisdiction_level: str,
    qdrant_client: QdrantClient,
    title_number: str = "",
    part: str = "",
    subpart: str = "",
    section_number: str = "",
    snapshot_date: str = "",
) -> int:
    """
    Chunk, embed, and upsert a code section to Qdrant.
    Returns the number of chunks upserted.
    """
    full_text = heading + " " + body_text
    chunks = chunk_text(full_text)
    if not chunks:
        return 0

    if source_system == "cfr":
        breadcrumb = f"Title {title_number} CFR Part {part}"
        if subpart:
            breadcrumb += f" > Subpart {subpart}"
    elif source_system == "iac":
        breadcrumb = f"Indiana Admin Code Title {title_number} Article {part}"
        if subpart:
            breadcrumb += f" Rule {subpart}"
    else:
        breadcrumb = citation
    breadcrumb += f" > {citation}: {heading} | "

    chunks_with_context = [breadcrumb + c for c in chunks]
    embeddings = embed_text(chunks_with_context)

    points = []
    for chunk_index, (chunk_text_str, vector) in enumerate(zip(chunks, embeddings)):
        point_id = record_id * 1000 + chunk_index
        payload = {
            "project": settings.QDRANT_PROJECT_TAG,  # MANDATORY — cluster isolation
            "record_type": "code_section",
            "db_id": record_id,
            "citation": citation,
            "source_system": source_system,
            "heading": heading,
            "chunk_text": chunk_text_str,
            "agency": agency,
            "status": status,
            "jurisdiction_level": jurisdiction_level,
            "title_number": title_number,
            "part": part,
            "subpart": subpart,
            "section_number": section_number,
            "snapshot_date": snapshot_date,
        }
        points.append(PointStruct(id=point_id, vector=vector, payload=payload))

    qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(chunks)


def embed_and_store_action(
    record_id: int,
    source_id: str,
    source_system: str,
    title: str,
    abstract: str,
    agency: str,
    status: str,
    action_type: str,
    qdrant_client: QdrantClient,
) -> int:
    """
    Chunk, embed, and upsert a regulatory action to Qdrant.
    Returns the number of chunks upserted.
    """
    # Build source breadcrumb for context
    if source_system == "federal_register":
        breadcrumb = "Federal Register"
    elif source_system == "iurc_rulemakings":
        breadcrumb = "IURC Rulemaking"
    elif source_system == "iurc_gaos":
        breadcrumb = "IURC General Administrative Order"
    elif source_system == "iurc_investigations":
        breadcrumb = "IURC Investigation Order"
    elif source_system == "idem_rulemakings":
        breadcrumb = "IDEM Rulemaking"
    else:
        breadcrumb = source_system

    full_text = f"{breadcrumb} | {abstract}" if abstract else f"{breadcrumb} | {title}"
    chunks = chunk_text(full_text)
    if not chunks:
        return 0

    embeddings = embed_text(chunks)

    points = []
    for chunk_index, (chunk_text_str, vector) in enumerate(zip(chunks, embeddings)):
        # Offset by 500M to avoid collision with code_section IDs (which use record_id * 1000)
        point_id = 500_000_000 + record_id * 1000 + chunk_index
        payload = {
            "project": settings.QDRANT_PROJECT_TAG,  # MANDATORY — cluster isolation
            "record_type": "regulatory_action",
            "db_id": record_id,
            "source_id": source_id,
            "source_system": source_system,
            "title": title,
            "chunk_text": chunk_text_str,
            "agency": agency,
            "status": status,
            "action_type": action_type,
        }
        points.append(PointStruct(id=point_id, vector=vector, payload=payload))

    qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(chunks)
