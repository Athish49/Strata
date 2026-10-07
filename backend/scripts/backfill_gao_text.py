"""
Backfill abstract, action_text, and docket_ids for existing iurc_gaos rows.

Run once after deploying the updated iurc_gaos adapter:

    cd /path/to/backend
    source .venv/bin/activate
    python scripts/backfill_gao_text.py

What it does:
  1. Re-scrapes the active and superseded GAO listing pages.
  2. Builds a {gao_id: entry} lookup from the fresh scrape.
  3. For each DB row with source_system='iurc_gaos':
       - Refreshes title and full_text_url from the scrape when available
         (fixes rows like GAO-2019-02 that were ingested with title='PDF').
       - Computes abstract = f"IURC General Administrative Order {id}: {title} ..."
       - Sets docket_ids = [source_id]
       - Fetches the PDF and sets action_text (first 2000 chars of first 2 pages).
  4. Commits all updates.

Note: Qdrant embeddings are NOT updated here; run scripts/reembed_state_actions.py
      afterwards to refresh the 42 stale vectors.
"""

import asyncio
import logging
import sys
import os

# Allow running from repo root or scripts/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

import httpx
from sqlalchemy import select, update

from app.db import AsyncSessionLocal
from app.regulatory.models.regulatory_action import RegulatoryAction
from app.regulatory.adapters.iurc_gaos import (
    SOURCE_URL,
    SUPERSEDED_URL,
    REQUEST_DELAY,
    _HEADERS,
    _parse_page,
    _parse_superseded_page,
    _categorize_gao,
    _fetch_pdf_text,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    # 1. Scrape both listing pages
    logger.info("Fetching GAO listing pages...")
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=_HEADERS) as client:
        resp = await client.get(SOURCE_URL)
        resp.raise_for_status()
        active_entries = _parse_page(resp.text)
        logger.info("  Active GAOs scraped: %d", len(active_entries))

        superseded_entries: list[dict] = []
        try:
            s_resp = await client.get(SUPERSEDED_URL)
            if s_resp.status_code == 200:
                superseded_entries = _parse_superseded_page(s_resp.text)
                logger.info("  Superseded GAOs scraped: %d", len(superseded_entries))
        except Exception as exc:
            logger.warning("Could not fetch superseded page: %s", exc)

    # Build lookup keyed by gao_id
    scrape_map: dict[str, dict] = {}
    for entry in active_entries + superseded_entries:
        gao_id = entry["gao_id"]
        if gao_id not in scrape_map:
            scrape_map[gao_id] = entry

    # 2. Load all iurc_gaos rows from DB
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RegulatoryAction).where(
                RegulatoryAction.source_system == "iurc_gaos"
            )
        )
        rows: list[RegulatoryAction] = result.scalars().all()
        logger.info("DB rows to backfill: %d", len(rows))

    # 3. For each row: refresh metadata, fetch PDF text
    updates: list[dict] = []

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=_HEADERS) as pdf_client:
        for i, row in enumerate(rows):
            gao_id: str = row.source_id
            scraped = scrape_map.get(gao_id)

            # Refresh title and full_text_url from fresh scrape when available
            title: str = row.title or gao_id
            pdf_url: str | None = row.full_text_url

            if scraped:
                scraped_title = scraped.get("title", "")
                # Always prefer the freshly-scraped title — it's authoritative and
                # also corrects rows like GAO-2021-01 that were misidentified due to
                # a site typo in the original parse.
                if scraped_title:
                    title = scraped_title
                # Always prefer the freshly-scraped PDF URL (dA/ format is stable)
                if scraped.get("pdf_url"):
                    pdf_url = scraped["pdf_url"]

            row_text = scraped.get("row_text", "") if scraped else ""
            category = _categorize_gao(title, row_text)
            abstract = f"IURC General Administrative Order {gao_id}: {title} (category: {category})"

            # Fetch PDF text
            action_text: str | None = None
            if pdf_url:
                logger.info("[%d/%d] Fetching PDF for %s ...", i + 1, len(rows), gao_id)
                action_text = await _fetch_pdf_text(pdf_client, pdf_url)
                if action_text:
                    logger.info("  -> extracted %d chars", len(action_text))
                else:
                    logger.info("  -> no text extracted")
                await asyncio.sleep(REQUEST_DELAY)
            else:
                logger.info("[%d/%d] No PDF URL for %s", i + 1, len(rows), gao_id)

            updates.append(
                {
                    "id": row.id,
                    "title": title,
                    "abstract": abstract,
                    "action_text": action_text,
                    "docket_ids": [gao_id],
                    "full_text_url": pdf_url,
                }
            )

    # 4. Persist updates
    logger.info("Writing %d updates to DB...", len(updates))
    async with AsyncSessionLocal() as db:
        for upd in updates:
            await db.execute(
                update(RegulatoryAction)
                .where(RegulatoryAction.id == upd["id"])
                .values(
                    title=upd["title"],
                    abstract=upd["abstract"],
                    action_text=upd["action_text"],
                    docket_ids=upd["docket_ids"],
                    full_text_url=upd["full_text_url"],
                )
            )
        await db.commit()
        logger.info("Commit successful.")

    # 5. Summary
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        r = await db.execute(
            text(
                """
                SELECT
                    count(*) AS n,
                    count(abstract) AS has_abstract,
                    count(action_text) AS has_action_text,
                    count(CASE WHEN docket_ids != '{}' THEN 1 END) AS has_docket
                FROM regulatory_actions
                WHERE source_system = 'iurc_gaos'
                """
            )
        )
        row = r.one()
        logger.info(
            "Final: %d rows | %d with abstract | %d with action_text | %d with docket_ids",
            row.n,
            row.has_abstract,
            row.has_action_text,
            row.has_docket,
        )
        logger.info(
            "NOTE: Qdrant vectors are now stale. Run scripts/reembed_state_actions.py to refresh."
        )


if __name__ == "__main__":
    asyncio.run(main())
