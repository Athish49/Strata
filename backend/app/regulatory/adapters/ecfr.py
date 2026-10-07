"""
eCFR adapter — ingests CFR sections for Title 18 (FERC) and Title 40 (EPA).

Scope:
  Title 18: Parts 35, 37, 38
  Title 40: Parts 60 (subparts Da, KKKK, TTTTa, UUUUb),
             63 (subparts UUUUU, YYYY), 72, 73
"""

import asyncio
import copy
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.regulatory.adapters.base import (
    SourceAdapter,
    compute_content_hash,
    upload_raw_to_r2,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scope constants
# ---------------------------------------------------------------------------

TITLE_18_PARTS = [35, 37, 38]
TITLE_40_PARTS = [60, 63, 72, 73]
TITLE_40_PART_60_SUBPARTS = ["Da", "KKKK", "TTTTa", "UUUUb"]
TITLE_40_PART_63_SUBPARTS = ["UUUUU", "YYYY"]
ECFR_BASE = "https://www.ecfr.gov/api"

# Parts that require subpart-level filtering  {(title, part): [subpart_ids, ...]}
_SUBPART_FILTER: dict[tuple[int, int], list[str]] = {
    (40, 60): TITLE_40_PART_60_SUBPARTS,
    (40, 63): TITLE_40_PART_63_SUBPARTS,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _map_title_to_agency(title_number: int) -> str:
    return {18: "ferc", 40: "epa"}.get(title_number, "unknown")


def _extract_body_text(section_tag) -> str:
    """Strip <HEAD> and return concatenated text of all remaining content."""
    # Work on a copy so we don't mutate the tree
    tag = copy.copy(section_tag)
    head = tag.find("HEAD")
    if head:
        head.decompose()
    return " ".join(tag.get_text(separator=" ").split())


def _get_subpart_name(section_tag) -> Optional[str]:
    """Walk parent chain to find the enclosing DIV6 SUBPART N attribute."""
    parent = section_tag.parent
    while parent:
        if getattr(parent, "name", None) == "DIV6" and parent.get("TYPE") == "SUBPART":
            return parent.get("N", "")
        parent = getattr(parent, "parent", None)
    return None


async def _fetch_with_fallback(
    client: httpx.AsyncClient, url: str, params: dict | None = None
) -> tuple[httpx.Response, str]:
    """
    GET url, falling back day-by-day (up to 7 days earlier) on 404.

    Returns (response, actual_date_used) where actual_date_used is the
    ISO date string that succeeded — may differ from the one in `url`.
    """
    # Extract the date from the URL for rollback reference
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", url)
    if date_match:
        url_date = date.fromisoformat(date_match.group(1))
    else:
        url_date = None

    resp = await client.get(url, params=params)
    if resp.status_code != 404:
        resp.raise_for_status()
        actual = url_date.isoformat() if url_date else ""
        return resp, actual

    if url_date is None:
        resp.raise_for_status()  # No date to roll back — raise

    # 404 — step back from the URL's date, not today's date
    for delta in range(1, 8):
        fallback = (url_date - timedelta(days=delta)).isoformat()
        new_url = re.sub(r"\d{4}-\d{2}-\d{2}", fallback, url, count=1)
        resp = await client.get(new_url, params=params)
        if resp.status_code != 404:
            resp.raise_for_status()
            return resp, fallback

    raise httpx.HTTPStatusError(
        f"404 after fallback for {url}", request=resp.request, response=resp
    )


# ---------------------------------------------------------------------------
# ECFRAdapter
# ---------------------------------------------------------------------------

class ECFRAdapter(SourceAdapter):
    source_system = "cfr"

    # ------------------------------------------------------------------
    # Cursor helpers
    # ------------------------------------------------------------------

    async def get_sync_cursor(self, db) -> dict:
        """Return cursor_data for source_system='cfr', or {} if none."""
        from sqlalchemy import select
        from app.regulatory.models.sync_state import SyncState

        result = await db.execute(
            select(SyncState).where(SyncState.source_system == "cfr")
        )
        row = result.scalar_one_or_none()
        if row is None or row.cursor_data is None:
            return {}
        return row.cursor_data

    async def update_sync_cursor(self, db, new_cursor: dict) -> None:
        """Upsert sync_state row for source_system='cfr'."""
        from sqlalchemy import select
        from app.regulatory.models.sync_state import SyncState

        result = await db.execute(
            select(SyncState).where(SyncState.source_system == "cfr")
        )
        row = result.scalar_one_or_none()
        now = datetime.utcnow()
        if row is None:
            row = SyncState(
                source_system="cfr",
                cursor_data=new_cursor,
                last_sync_at=now,
            )
            db.add(row)
        else:
            row.cursor_data = new_cursor
            row.last_sync_at = now
        await db.commit()

    # ------------------------------------------------------------------
    # Core ingestion
    # ------------------------------------------------------------------

    async def poll(self, cursor: dict) -> list[dict]:
        """
        Fetch all in-scope CFR sections, comparing against cursor dates.

        cursor shape (incremental): {"title_18_amended_on": "YYYY-MM-DD",
                                     "title_40_amended_on": "YYYY-MM-DD"}

        cursor shape (historical):  {"as_of_date": "YYYY-MM-DD"}
          → fetches XML at exactly that date; snapshot_date is set to as_of_date.

        Returns a list of raw section dicts ready for normalize().
        """
        # Historical mode: if cursor has 'as_of_date', fetch at that specific date
        as_of_date = cursor.get("as_of_date")
        if as_of_date:
            results: list[dict] = []
            async with httpx.AsyncClient(timeout=30.0) as client:
                for title_num, parts_config in [(18, TITLE_18_PARTS), (40, TITLE_40_PARTS)]:
                    for part in parts_config:
                        await asyncio.sleep(1)  # polite rate limiting

                        xml_url = (
                            f"{ECFR_BASE}/versioner/v1/full/{as_of_date}"
                            f"/title-{title_num}.xml"
                        )
                        try:
                            resp, actual_date = await _fetch_with_fallback(
                                client, xml_url, params={"part": str(part)}
                            )
                            xml_bytes = resp.content
                            effective_date = actual_date or as_of_date
                        except Exception as exc:
                            logger.error(
                                "Failed to fetch Title %d Part %d: %s", title_num, part, exc
                            )
                            continue

                        # Upload raw XML to R2 (non-fatal on failure)
                        try:
                            upload_raw_to_r2(
                                "cfr",
                                f"{effective_date}/title-{title_num}-part-{part}.xml",
                                xml_bytes,
                                "application/xml",
                            )
                        except Exception as exc:
                            logger.warning(
                                "R2 upload failed for Title %d Part %d: %s", title_num, part, exc
                            )

                        # Parse XML
                        try:
                            sections = _parse_part_xml(
                                xml_bytes, title_num, part, effective_date
                            )
                            results.extend(sections)
                            logger.info(
                                "Title %d Part %d: extracted %d sections",
                                title_num, part, len(sections),
                            )
                        except Exception as exc:
                            logger.error(
                                "XML parse failed for Title %d Part %d: %s", title_num, part, exc
                            )
                            continue

            return results

        raw_records: list[dict] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1 — Get titles metadata
            titles_resp = await client.get(f"{ECFR_BASE}/versioner/v1/titles")
            titles_resp.raise_for_status()
            titles_data = titles_resp.json().get("titles", [])

            title_meta: dict[int, dict] = {}
            for t in titles_data:
                num = t.get("number")
                if num in (18, 40):
                    title_meta[num] = t

            # Step 2 — Decide which titles need re-ingestion
            titles_to_process: list[tuple[int, str]] = []  # (title_num, date_str)

            for title_num in (18, 40):
                if title_num not in title_meta:
                    logger.warning("Title %d not found in eCFR titles response", title_num)
                    continue

                latest = title_meta[title_num].get("latest_amended_on", "")
                cursor_key = f"title_{title_num}_amended_on"
                stored = cursor.get(cursor_key, "")

                if not stored or latest > stored:
                    titles_to_process.append((title_num, latest))
                    logger.info(
                        "Title %d: latest_amended_on=%s > cursor=%s — will ingest",
                        title_num, latest, stored or "(none)",
                    )
                else:
                    logger.info(
                        "Title %d: no change (latest=%s, cursor=%s) — skipping",
                        title_num, latest, stored,
                    )

            # Step 3 — Fetch per-part XML and parse sections
            parts_map = {18: TITLE_18_PARTS, 40: TITLE_40_PARTS}

            for title_num, amendment_date in titles_to_process:
                for part in parts_map[title_num]:
                    await asyncio.sleep(1)  # polite rate limiting

                    xml_url = (
                        f"{ECFR_BASE}/versioner/v1/full/{amendment_date}"
                        f"/title-{title_num}.xml"
                    )
                    try:
                        resp, actual_date = await _fetch_with_fallback(
                            client, xml_url, params={"part": str(part)}
                        )
                        xml_bytes = resp.content
                        # Use actual date (may differ from amendment_date on fallback)
                        effective_date = actual_date or amendment_date
                    except Exception as exc:
                        logger.error(
                            "Failed to fetch Title %d Part %d: %s", title_num, part, exc
                        )
                        continue

                    # Upload raw XML to R2 (non-fatal on failure)
                    try:
                        upload_raw_to_r2(
                            "cfr",
                            f"{effective_date}/title-{title_num}-part-{part}.xml",
                            xml_bytes,
                            "application/xml",
                        )
                    except Exception as exc:
                        logger.warning(
                            "R2 upload failed for Title %d Part %d: %s", title_num, part, exc
                        )

                    # Parse XML
                    try:
                        sections = _parse_part_xml(
                            xml_bytes, title_num, part, effective_date
                        )
                        raw_records.extend(sections)
                        logger.info(
                            "Title %d Part %d: extracted %d sections",
                            title_num, part, len(sections),
                        )
                    except Exception as exc:
                        logger.error(
                            "XML parse failed for Title %d Part %d: %s", title_num, part, exc
                        )
                        continue

        return raw_records

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> dict | None:
        """Convert a raw section dict → CodeSection dict."""
        title_num = raw["title_number"]
        part = raw["part"]
        bare_section = raw["section_number"]          # e.g. "28"
        section_n_full = raw.get("section_n_full", f"{part}.{bare_section}")  # e.g. "35.28"
        heading = raw.get("heading", "")
        body_text = raw.get("body_text", "")
        amendment_date = raw.get("amendment_date", "")

        # citation = "18 CFR 35.28"
        citation = f"{title_num} CFR {section_n_full}"

        # effective_date
        try:
            effective = date.fromisoformat(amendment_date) if amendment_date else None
        except ValueError:
            effective = None

        return {
            "citation": citation,
            "source_system": "cfr",
            "jurisdiction_level": "federal",
            "title_number": str(title_num),
            "part": str(part),
            "section_number": bare_section,
            "subpart": raw.get("subpart", ""),
            "heading": heading,
            "body_text": body_text,
            "content_hash": compute_content_hash(body_text),
            "jurisdiction_geo": "US",
            "owning_agency": _map_title_to_agency(title_num),
            "effective_date": effective,
            "status": "approved",
            "snapshot_date": date.fromisoformat(amendment_date) if amendment_date else date.today(),
            "source_url": (
                f"https://www.ecfr.gov/current/title-{title_num}"
                f"/part-{part}/section-{section_n_full}"
            ),
        }

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{ECFR_BASE}/versioner/v1/titles")
                return resp.status_code == 200
        except Exception as exc:
            logger.warning("eCFR health check failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# XML parsing helper (module-level so it's easy to test in isolation)
# ---------------------------------------------------------------------------

def _parse_part_xml(
    xml_bytes: bytes, title_num: int, part: int, amendment_date: str
) -> list[dict]:
    """
    Parse eCFR XML bytes and return a list of raw section dicts.

    Applies subpart filter for Title 40 parts 60 and 63.
    """
    soup = BeautifulSoup(xml_bytes, "lxml-xml")

    target_subparts = _SUBPART_FILTER.get((title_num, part))

    sections: list[dict] = []

    for div8 in soup.find_all("DIV8", attrs={"TYPE": "SECTION"}):
        section_n = div8.get("N", "").strip()
        if not section_n:
            continue

        # Subpart filter
        subpart_name = _get_subpart_name(div8)
        if target_subparts is not None:
            if subpart_name not in target_subparts:
                continue

        # Extract heading
        head_tag = div8.find("HEAD")
        heading = head_tag.get_text(separator=" ").strip() if head_tag else section_n

        # Body text (all text except HEAD)
        body_text = _extract_body_text(div8)

        # section_number: strip "PART." prefix per spec (e.g. "35.28" → "28")
        # citation = "18 CFR 35.28" is built by normalize() as "{title} CFR {section_n}"
        bare_section = section_n.split(".", 1)[1] if "." in section_n else section_n

        sections.append(
            {
                "title_number": title_num,
                "part": part,
                "section_number": bare_section,
                "section_n_full": section_n,   # keep for citation / URL building
                "subpart": subpart_name,
                "heading": heading,
                "body_text": body_text,
                "amendment_date": amendment_date,
            }
        )

    return sections
