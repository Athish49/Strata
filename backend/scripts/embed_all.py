"""
One-off embedding pass: embeds all CodeSection and RegulatoryAction records into Qdrant.
Run: cd backend && .venv/bin/python scripts/embed_all.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.db import AsyncSessionLocal
from app.regulatory.ingestion.embedder import (
    embed_and_store_code_section,
    embed_and_store_action,
    get_embedding_model,
)
from app.regulatory.models.code_section import CodeSection
from app.regulatory.models.regulatory_action import RegulatoryAction
from app.services.vector import get_qdrant_client
from sqlalchemy import select


async def embed_all():
    print("Loading embedding model...")
    model = get_embedding_model()
    print("Model loaded.")

    qdrant_client = get_qdrant_client()

    async with AsyncSessionLocal() as db:
        # Embed all CodeSections
        result = await db.execute(select(CodeSection))
        sections = result.scalars().all()
        print(f"Embedding {len(sections)} code sections...")
        total_section_chunks = 0
        for i, section in enumerate(sections):
            try:
                n_chunks = embed_and_store_code_section(
                    record_id=section.id,
                    citation=section.citation,
                    source_system=section.source_system,
                    heading=section.heading,
                    body_text=section.body_text,
                    agency=section.owning_agency,
                    status=section.status,
                    jurisdiction_level=section.jurisdiction_level,
                    qdrant_client=qdrant_client,
                    title_number=section.title_number or "",
                    part=section.part or "",
                    subpart=getattr(section, "subpart", "") or "",
                )
                total_section_chunks += n_chunks
                if (i + 1) % 50 == 0:
                    print(f"  {i + 1}/{len(sections)} sections embedded ({total_section_chunks} chunks so far)")
            except Exception as e:
                print(f"  ERROR on section {section.id} ({section.citation}): {e}")
        print(f"Code sections done: {len(sections)} processed, {total_section_chunks} total chunks")

        # Embed all RegulatoryActions
        result2 = await db.execute(select(RegulatoryAction))
        actions = result2.scalars().all()
        print(f"Embedding {len(actions)} regulatory actions...")
        total_action_chunks = 0
        for i, action in enumerate(actions):
            try:
                n_chunks = embed_and_store_action(
                    record_id=action.id,
                    source_id=action.source_id,
                    source_system=action.source_system,
                    title=action.title,
                    abstract=action.abstract,
                    agency=action.agency,
                    status=action.status,
                    action_type=action.action_type,
                    qdrant_client=qdrant_client,
                )
                total_action_chunks += n_chunks
                if (i + 1) % 50 == 0:
                    print(f"  {i + 1}/{len(actions)} actions embedded ({total_action_chunks} chunks so far)")
            except Exception as e:
                print(f"  ERROR on action {action.id} ({action.source_id}): {e}")
        print(f"Actions done: {len(actions)} processed, {total_action_chunks} total chunks")

    print("\nEmbedding pass complete.")


if __name__ == "__main__":
    asyncio.run(embed_all())
