"""
One-time setup script: creates the regulation_chunks collection in Qdrant Cloud.
Run once: cd backend && .venv/bin/python scripts/setup_qdrant.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance,
    PayloadSchemaType,
)
from app.config import settings

COLLECTION_NAME = "regulation_chunks"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2

def setup():
    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

    # Check if collection already exists
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        print(f"Collection '{COLLECTION_NAME}' already exists — skipping creation.")
    else:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"Created collection '{COLLECTION_NAME}' (size={VECTOR_SIZE}, distance=COSINE)")

    # Create payload indexes for efficient filtering
    # project index MUST be first — it's the isolation key for this shared cluster
    indexes = [
        ("project", PayloadSchemaType.KEYWORD),
        ("source_system", PayloadSchemaType.KEYWORD),
        ("citation", PayloadSchemaType.KEYWORD),
        ("agency", PayloadSchemaType.KEYWORD),
        ("status", PayloadSchemaType.KEYWORD),
        ("jurisdiction_level", PayloadSchemaType.KEYWORD),
        ("title_number", PayloadSchemaType.KEYWORD),
        ("part", PayloadSchemaType.KEYWORD),
        ("subpart", PayloadSchemaType.KEYWORD),
    ]

    for field_name, schema_type in indexes:
        try:
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field_name,
                field_schema=schema_type,
            )
            print(f"  Index created: {field_name}")
        except Exception as e:
            # Index may already exist
            print(f"  Index {field_name}: {e}")

    # Verify
    info = client.get_collection(COLLECTION_NAME)
    print(f"\nCollection info:")
    print(f"  Name: {COLLECTION_NAME}")
    print(f"  Vectors config: {info.config.params.vectors}")
    print(f"  Points count: {info.points_count}")
    print(f"  Status: {info.status}")
    print("\nSetup complete.")

if __name__ == "__main__":
    setup()
