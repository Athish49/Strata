"""
Indiana Administrative Code (IAC) adapter.

Fetches codified Indiana regulations from the IAC portal at https://iar.iga.in.gov/,
backed by CloudFront API at https://drxya2s1hkmtl.cloudfront.net.

Scope:
    Title 170 — IURC (electric, gas, water, telecom regulation)
    Title 326 — Air quality / IDEM
    Title 327 — Water quality / IDEM
    Title 610 — OSHA / labor safety
    Title 675 — Fire prevention & building safety

Two snapshots:
    Phase 1: edition_year=2025  → snapshot_date = 2024-12-31
    Phase 2: edition_year=2026  → snapshot_date = 2025-12-31

API notes (verified against live API):
    - Tree endpoint returns {"iar_iac_title_article_list": [...]} where each item
      is a title with a nested "article" list.
    - Article endpoint returns {"iar_iac_article_doc": {..., "doc_html": "..."}}
    - Sections in doc_html are <h1 id="TTT-A-R-S"> elements; body follows as
      <div class="subsection"> siblings until the next section h1.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup, Tag

from app.regulatory.adapters.base import (
    SourceAdapter,
    compute_content_hash,
    upload_raw_to_r2,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEED_TITLES = [170, 326, 327, 610, 675]

IAC_API_BASE = "https://drxya2s1hkmtl.cloudfront.net"

IAC_HEADERS = {
    "Referer": "https://iar.iga.in.gov/",
    "Origin": "https://iar.iga.in.gov",
    "content-type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}

REQUEST_DELAY = 0.5  # seconds between article fetches

# Regex for section IDs: exactly 4 dash-separated numeric segments
_SECTION_ID_RE = re.compile(r"^\d+-\d+-\d+-\d+$")

# Pattern to detect filed dates in <em> footer text — broadened to catch all common formats
_FILED_DATE_RE = re.compile(
    r"filed[:\s]+(\w+\.?\s+\d{1,2},?\s*\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

_DIN_RE = re.compile(r"\d{8}-IR-\d{9}[A-Z]{2,4}")
_FR_CITE_RE = re.compile(r"\b(\d{1,3})\s+FR\s+([\d,]+)\b")
_CFR_CITE_RE = re.compile(r"\b(\d+)\s+CFR\s+[Pp]art\s+(\d+(?:\.\d+)?)\b")
_IAC_CITE_RE = re.compile(r"\b(\d+)\s+IAC\s+(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\b")


def extract_cross_refs(text: str) -> dict:
    """
    Extract cross-citations from IAC section body text.

    Returns a dict with three keys:
        federal_refs   — FR citations (e.g. "88 FR 12345") followed by
                         CFR Part citations (e.g. "18 CFR Part 35").
                         Note: _CFR_CITE_RE requires the literal word "Part",
                         so inline CFR citations like "18 CFR 35.1" are not
                         captured; this is a known limitation.
        iac_cross_refs — IAC self-references (e.g. "170 IAC 4-1-6")
        dins           — DIN numbers extracted from body_text, which includes
                         the <em> footer text (a superset of em_full alone).

    Duplicates are removed while preserving order.
    """
    if not text:
        return {"federal_refs": [], "iac_cross_refs": [], "dins": []}

    fr = [f"{m.group(1)} FR {m.group(2)}" for m in _FR_CITE_RE.finditer(text)]
    cfr = [f"{m.group(1)} CFR Part {m.group(2)}" for m in _CFR_CITE_RE.finditer(text)]
    iac = [
        f"{m.group(1)} IAC {m.group(2)}-{m.group(3)}-{m.group(4)}"
        for m in _IAC_CITE_RE.finditer(text)
    ]
    dins = _DIN_RE.findall(text)

    return {
        "federal_refs": list(dict.fromkeys(fr + cfr)),
        "iac_cross_refs": list(dict.fromkeys(iac)),
        "dins": list(dict.fromkeys(dins)),
    }


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_effective_date(em_text: str) -> Optional[str]:
    """
    Parse the most-recent filed date from the <em> footer of an IAC section.

    Handles formats:
        "filed Sep 12, 2025, 11:43 a.m.: ..."   → 2025-09-12
        "filed Oct 1, 2024: ..."                 → 2024-10-01
        "filed: September 12, 2024"              → 2024-09-12
        "Filed 9/12/2024"                        → 2024-09-12
        "Filed 2024-09-12"                       → 2024-09-12
    Returns an ISO YYYY-MM-DD string, or None.
    """
    matches = _FILED_DATE_RE.findall(em_text)
    if not matches:
        return None

    last_match = re.sub(r"\s+", " ", matches[-1]).strip().rstrip(",").rstrip(".")
    for fmt in (
        "%b %d, %Y", "%B %d, %Y",
        "%b %d %Y", "%B %d %Y",
        "%b. %d, %Y", "%B. %d, %Y",
        "%m/%d/%Y",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(last_match, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _collect_section_body(section_h1: Tag) -> tuple[str, str]:
    """
    Starting from a section <h1> tag, collect the body text and effective date
    by walking forward siblings until the next section-level <h1>.

    Returns (body_text, effective_date_iso_or_empty).
    """
    body_parts: list[str] = []
    em_parts: list[str] = []

    from bs4 import NavigableString as _NavStr

    for sibling in section_h1.next_siblings:
        # Plain text nodes — no attributes, no find_all
        if isinstance(sibling, _NavStr):
            text = str(sibling).strip()
            if text:
                body_parts.append(text)
            continue

        # Stop at the next section h1 (has a 4-segment id)
        if getattr(sibling, "name", None) == "h1":
            sid = sibling.get("id", "")
            if _SECTION_ID_RE.match(sid):
                break

        # Collect <em> text for date extraction
        for em in sibling.find_all("em"):
            em_parts.append(em.get_text())

        tag_text = re.sub(r"\s+", " ", sibling.get_text(separator=" ")).strip()
        if tag_text:
            body_parts.append(tag_text)

    body_text = " ".join(body_parts)
    body_text = re.sub(r"\s+", " ", body_text).strip()

    em_full = " ".join(em_parts)
    effective_date = _parse_effective_date(em_full) or ""
    dins = _DIN_RE.findall(em_full)
    return body_text, effective_date, dins


def _parse_sections_from_html(
    doc_html: str,
    title_num: str,
    article_num: str,
    agency_name: str,
    edition_year: int,
    snapshot_date: str,
) -> list[dict]:
    """
    Parse all sections from an IAC article's doc_html.

    Sections are <h1> elements whose id matches TTT-A-R-S (4 numeric segments).
    Returns a list of raw section dicts.
    """
    soup = BeautifulSoup(doc_html, "html.parser")

    # Find all h1 elements with 4-part numeric IDs
    section_h1s = [
        tag for tag in soup.find_all("h1")
        if _SECTION_ID_RE.match(tag.get("id", ""))
    ]

    if not section_h1s:
        logger.debug(
            "No section h1s found for title %s article %s edition %s (may be a temp-rule index article)",
            title_num, article_num, edition_year,
        )
        return []

    records: list[dict] = []
    for h1 in section_h1s:
        section_id = h1.get("id", "")
        parts = section_id.split("-")
        if len(parts) != 4:
            continue

        t_num, a_num, rule_num, sec_num = parts

        # Citation: e.g. "170 IAC 4-1-1"
        citation = f"{t_num} IAC {a_num}-{rule_num}-{sec_num}"

        # Heading: text of the h1 element
        heading = re.sub(r"\s+", " ", h1.get_text(separator=" ")).strip()

        body_text, effective_date, dins = _collect_section_body(h1)

        source_url = (
            f"https://iar.iga.in.gov/rules/{edition_year}/{t_num}/{a_num}"
        )

        # Extract cross-citations from body text
        fr_refs = [f"{m.group(1)} FR {m.group(2)}" for m in _FR_CITE_RE.finditer(body_text)]
        cfr_refs = [f"{m.group(1)} CFR Part {m.group(2)}" for m in _CFR_CITE_RE.finditer(body_text)]
        iac_cross_refs = [
            f"{m.group(1)} IAC {m.group(2)}-{m.group(3)}-{m.group(4)}"
            for m in _IAC_CITE_RE.finditer(body_text)
        ]

        records.append({
            "section_id": section_id,
            "citation": citation,
            "title_num": t_num,
            "article_num": a_num,
            "rule_num": rule_num,
            "section_num": sec_num,
            "heading": heading,
            "body_text": body_text,
            "owning_agency": agency_name,
            "effective_date": effective_date or None,
            "edition_year": edition_year,
            "snapshot_date": snapshot_date,
            "source_url": source_url,
            "dins": dins,
            "fr_refs": fr_refs,
            "cfr_refs": cfr_refs,
            "iac_cross_refs": iac_cross_refs,
        })

    return records


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class IACAdapter(SourceAdapter):
    source_system = "iac"

    # Expose as class-level attributes for external scripts
    IAC_HEADERS = IAC_HEADERS
    SEED_TITLES = SEED_TITLES

    # ------------------------------------------------------------------
    # Cursor management
    # ------------------------------------------------------------------

    async def get_sync_cursor(self, db) -> dict:
        """Read cursor from sync_state table; default to Phase 1."""
        from sqlalchemy import select
        from app.regulatory.models.sync_state import SyncState

        stmt = select(SyncState).where(SyncState.source_system == self.source_system)
        result = await db.execute(stmt)
        state = result.scalar_one_or_none()
        if state is None or not state.cursor_data:
            return {"edition_year": 2025, "snapshot_date": "2024-12-31"}
        return state.cursor_data

    async def update_sync_cursor(self, db, new_cursor: dict) -> None:
        """Upsert new cursor into sync_state."""
        from sqlalchemy.dialects.postgresql import insert
        from app.regulatory.models.sync_state import SyncState

        stmt = (
            insert(SyncState)
            .values(
                source_system=self.source_system,
                cursor_data=new_cursor,
                last_sync_at=datetime.utcnow(),
            )
            .on_conflict_do_update(
                index_elements=["source_system"],
                set_={"cursor_data": new_cursor, "last_sync_at": datetime.utcnow()},
            )
        )
        await db.execute(stmt)
        await db.flush()

    # ------------------------------------------------------------------
    # Poll
    # ------------------------------------------------------------------

    async def poll(self, cursor: dict) -> list[dict]:
        """
        Fetch all sections for SEED_TITLES from the edition in cursor.

        Cursor shape: {"edition_year": 2025, "snapshot_date": "2024-12-31"}

        Uploads raw article HTML to R2:
            raw-sources/iac/{edition_year}/{title_num}/{article_num}.html
        Returns list of raw section dicts.
        """
        edition_year = cursor.get("edition_year", 2025)
        snapshot_date = cursor.get("snapshot_date", "2024-12-31")
        seed_set = set(SEED_TITLES)

        all_records: list[dict] = []

        async with httpx.AsyncClient(timeout=30, headers=IAC_HEADERS) as client:
            # Fetch tree — returns {"iar_iac_title_article_list": [...]}
            tree_resp = await client.get(
                f"{IAC_API_BASE}/api/adminCodeTree",
                params={"edition_year": edition_year, "doc_stage": "public"},
            )
            tree_resp.raise_for_status()
            tree_data = tree_resp.json()
            title_list = tree_data.get("iar_iac_title_article_list", [])

            # Build flat list of (title_num_str, article_num_str, agency_name) tuples
            articles_to_fetch: list[tuple[str, str, str]] = []
            for title_item in title_list:
                t_num_raw = title_item.get("title_num", "")
                try:
                    t_int = int(t_num_raw)
                except (ValueError, TypeError):
                    continue
                if t_int not in seed_set:
                    continue

                agency_name = title_item.get("title_name", f"Title {t_num_raw}")
                for article_item in title_item.get("article", []):
                    a_num = str(article_item.get("article_num", ""))
                    articles_to_fetch.append((str(t_num_raw), a_num, agency_name))

            logger.info(
                "IAC poll: edition=%s, %d articles in scope for titles %s",
                edition_year, len(articles_to_fetch), sorted(seed_set),
            )

            for i, (title_num, article_num, agency_name) in enumerate(articles_to_fetch):
                logger.info(
                    "IAC [%d/%d] title %s article %s",
                    i + 1, len(articles_to_fetch), title_num, article_num,
                )
                try:
                    article_resp = await client.get(
                        f"{IAC_API_BASE}/api/adminCodeArticle",
                        params={
                            "doc_stage": "public",
                            "edition_year": edition_year,
                            "title_num": title_num,
                            "article_num": article_num,
                        },
                    )
                    article_resp.raise_for_status()
                    article_data = article_resp.json()
                except Exception as e:
                    logger.warning(
                        "Failed to fetch IAC title %s article %s: %s",
                        title_num, article_num, e,
                    )
                    if i < len(articles_to_fetch) - 1:
                        await asyncio.sleep(REQUEST_DELAY)
                    continue

                # Response: {"iar_iac_article_doc": {..., "doc_html": "..."}}
                article_doc = article_data.get("iar_iac_article_doc", {})
                doc_html = article_doc.get("doc_html", "")

                # Prefer agency_name from API over title_name
                api_agency = article_doc.get("agency_name") or agency_name

                # Upload raw HTML to R2
                if doc_html:
                    try:
                        r2_key = f"{edition_year}/{title_num}/{article_num}.html"
                        upload_raw_to_r2(
                            self.source_system,
                            r2_key,
                            doc_html.encode("utf-8"),
                            "text/html",
                        )
                    except Exception as e:
                        logger.warning(
                            "R2 upload failed for iac %s/%s/%s: %s",
                            edition_year, title_num, article_num, e,
                        )

                # Parse sections
                sections = _parse_sections_from_html(
                    doc_html=doc_html,
                    title_num=title_num,
                    article_num=article_num,
                    agency_name=api_agency,
                    edition_year=edition_year,
                    snapshot_date=snapshot_date,
                )
                all_records.extend(sections)

                logger.debug(
                    "IAC title %s article %s: %d sections",
                    title_num, article_num, len(sections),
                )

                if i < len(articles_to_fetch) - 1:
                    await asyncio.sleep(REQUEST_DELAY)

        logger.info(
            "IAC poll complete: edition=%s, %d total sections",
            edition_year, len(all_records),
        )
        return all_records

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> Optional[dict]:
        """Map raw IAC section dict to CodeSection field dict."""
        body_text = raw.get("body_text") or ""
        heading = raw.get("heading") or ""

        # Skip completely empty sections
        if not body_text and not heading:
            return None

        content_hash = compute_content_hash((heading or "") + "\n" + (body_text or ""))
        cross_refs = extract_cross_refs(body_text)

        return {
            "citation": raw["citation"],
            "source_system": self.source_system,
            "jurisdiction_level": "state",
            "jurisdiction_geo": "IN",
            "title_number": raw.get("title_num", ""),
            "part": raw.get("article_num", ""),
            "subpart": raw.get("rule_num", ""),
            "section_number": raw.get("section_num", ""),
            "heading": heading,
            "body_text": body_text,
            "content_hash": content_hash,
            "owning_agency": raw.get("owning_agency", ""),
            "effective_date": raw.get("effective_date") or None,
            "status": "repealed" if "(Repealed)" in (heading or "") else "approved",
            "snapshot_date": raw["snapshot_date"],
            "source_url": raw.get("source_url"),
            "adapter_version": "1.0",
            "federal_refs": cross_refs["federal_refs"],
            "iac_cross_refs": cross_refs["iac_cross_refs"],
            "dins": cross_refs["dins"],
        }

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Quick GET to /api/adminCodeEditions; return True if 200."""
        try:
            async with httpx.AsyncClient(timeout=10, headers=IAC_HEADERS) as client:
                resp = await client.get(f"{IAC_API_BASE}/api/adminCodeEditions")
                return resp.status_code == 200
        except Exception:
            return False
