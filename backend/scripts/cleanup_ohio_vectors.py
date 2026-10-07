"""
Delete all OAC and PUCO DIS vector points from the regulation_chunks collection.
Run from backend/:  .venv/bin/python scripts/cleanup_ohio_vectors.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

from app.services.vector import get_qdrant_client, project_filter
from app.config import settings
from qdrant_client.models import (
    Filter, FieldCondition, MatchAny, FilterSelector
)

COLLECTION = "regulation_chunks"
OHIO_SYSTEMS = ["oac", "puco_dis"]

qdrant = get_qdrant_client()

ohio_filter = Filter(
    must=[
        *project_filter().must,
        FieldCondition(
            key="source_system",
            match=MatchAny(any=OHIO_SYSTEMS),
        ),
    ]
)

before_count = qdrant.count(
    collection_name=COLLECTION,
    count_filter=ohio_filter,
    exact=True,
).count
print(f"Points to delete (oac + puco_dis): {before_count}")

if before_count == 0:
    print("Nothing to delete.")
else:
    qdrant.delete(
        collection_name=COLLECTION,
        points_selector=FilterSelector(filter=ohio_filter),
        wait=True,
    )
    after_count = qdrant.count(
        collection_name=COLLECTION,
        count_filter=ohio_filter,
        exact=True,
    ).count
    print(f"After deletion: {after_count} remaining (expected 0)")
    assert after_count == 0, "Deletion incomplete!"
    print(f"Deleted {before_count} points successfully.")
