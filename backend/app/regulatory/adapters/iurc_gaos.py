"""
IURC General Administrative Orders adapter — scrapes:
https://www.in.gov/iurc/general-administrative-orders/
"""

import io
import logging
import re
from datetime import date, datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.regulatory.adapters.base import SourceAdapter, upload_raw_to_r2
from app.regulatory.models.sync_state import SyncState

logger = logging.getLogger(__name__)

SOURCE_URL = "https://www.in.gov/iurc/general-administrative-orders/"
SUPERSEDED_URL = "https://www.in.gov/iurc/general-administrative-orders/superseded-inactive-repealed-gaos/"
REQUEST_DELAY = 2.0

_CATEGORY_MAP = {
    "energy": ["electric", "generation", "cpcn", "net metering", "interconnect", "rate", "affordability", "miso", "eras", "renewable", "solar", "wind", "nuclear", "iija"],
    "pipeline_safety": ["pipeline", "natural gas", "distribution", "transmission line"],
    "communications": ["telecom", "telephone", "communication", "broadband", "carrier"],
    "water": ["water", "wastewater", "sewer", "liquid waste"],
    "procedural": ["procedure", "filing", "service", "administrative", "docket", "hearing"],
}


def _categorize_gao(title: str, row_text: str) -> str:
    combined = (title + " " + row_text).lower()
    for cat, keywords in _CATEGORY_MAP.items():
        if any(kw in combined for kw in keywords):
            return cat
    return "general"

# Matches a leading YYYY-NN prefix at the start of parent_text (most reliable source)
_PREFIX_RE = re.compile(r"^(\d{4})-(\d{1,2})\s")

# Matches GAO-YYYY-NN or GAO YYYY-NN in body text (fallback)
_GAO_RE = re.compile(r"GAO[-\s](\d{4})[-\s](\d{1,4})", re.IGNORECASE)

# Date patterns: Month DD, YYYY  or  MM/DD/YYYY  or  YYYY-MM-DD
_DATE_PATTERNS = [
    (re.compile(r"\b(\w+ \d{1,2},?\s*\d{4})\b"), ["%B %d, %Y", "%B %d %Y"]),
    (re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b"), ["%m/%d/%Y"]),
    (re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"), ["%Y-%m-%d"]),
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

STALE_DAYS = 7


def _parse_date(text: str) -> Optional[str]:
    """Try to parse a date string from arbitrary text."""
    for pattern, fmts in _DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        raw = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(",")
        for fmt in fmts:
            try:
                return datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                continue
    return None


def _build_gao_id(year: str, num: str) -> str:
    return f"GAO-{year}-{num.zfill(2)}"


# Matches "Approved Month Day, YYYY" or "Approved MM/DD/YYYY" in parent text
_APPROVED_DATE_RE = re.compile(
    r"Approved\s+(\w+\.?\s+\d{1,2},?\s*\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def _parse_approved_date(text: str) -> Optional[str]:
    """Extract 'Approved <date>' from GAO parent text."""
    m = _APPROVED_DATE_RE.search(text)
    if not m:
        return _parse_date(text)
    raw = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(",")
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
                "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_page(html: str) -> list[dict]:
    """
    Parse GAO entries from the IURC page HTML.

    The page has no tables. Each entry is a link (<a> text="PDF") whose parent
    element contains the full entry text like:
        "2026-02 Multi-year Rate Plan Guidance GAO 2026-02 | Approved June 3, 2026 | PDF"

    We find all PDF links under /dA/, extract the GAO ID and Approved date from the
    parent text, and derive the title by stripping the GAO/date/PDF boilerplate.
    """
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    seen_ids: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Only GAO PDF links (under /dA/ with .pdf)
        if "/dA/" not in href or ".pdf" not in href.lower():
            continue

        parent = a.parent
        if parent is None:
            continue
        parent_text = re.sub(r"\s+", " ", parent.get_text(" ", strip=True))

        # Primary: leading "YYYY-NN " prefix in parent text (avoids site typos)
        prefix_match = _PREFIX_RE.match(parent_text)
        if prefix_match:
            year, num = prefix_match.group(1), prefix_match.group(2)
        else:
            # Fallback: "GAO YYYY-NN" anywhere in text
            gao_match = _GAO_RE.search(parent_text)
            if not gao_match:
                # Last resort: try the href filename
                gao_match = _GAO_RE.search(href)
            if not gao_match:
                continue
            year, num = gao_match.group(1), gao_match.group(2)
        gao_id = _build_gao_id(year, num)
        if gao_id in seen_ids:
            continue
        seen_ids.add(gao_id)

        # Title: strip leading "YY-NN " prefix and trailing " GAO ... | Approved ... | PDF"
        title = parent_text
        # Remove trailing pipe-separated boilerplate
        title = re.sub(r"\s*\|\s*GAO\s+\d{4}-\d+.*$", "", title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\s*GAO\s+\d{4}-\d+.*$", "", title, flags=re.IGNORECASE).strip()
        # Remove leading "YY-NN " short prefix (e.g. "2026-02 ")
        title = re.sub(r"^\d{4}-\d{2}\s+", "", title).strip()
        title = title[:300] or gao_id

        date_published = _parse_approved_date(parent_text)

        full_href = href if href.startswith("http") else "https://www.in.gov" + href

        entries.append({
            "gao_id": gao_id,
            "title": title,
            "date_published": date_published,
            "pdf_url": full_href,
            "row_text": parent_text,
            "status": "approved",
        })

    return entries


def _parse_superseded_page(html: str) -> list[dict]:
    """Parse withdrawn/superseded GAO entries; same structure as active page but status=withdrawn."""
    entries = _parse_page(html)
    for e in entries:
        e["status"] = "withdrawn"
    return entries


async def _fetch_pdf_text(
    client: httpx.AsyncClient, pdf_url: str, max_chars: int = 2000
) -> Optional[str]:
    """Fetch a GAO PDF and return extracted text from the first 2 pages.

    Returns None if the URL is unreachable, the response is not a PDF, or
    no text can be extracted (e.g. scanned image PDFs).
    """
    try:
        from pypdf import PdfReader

        resp = await client.get(pdf_url, timeout=30.0)
        if resp.status_code != 200:
            return None
        content = resp.content
        # Verify PDF magic bytes
        if content[:4] != b"%PDF":
            return None
        reader = PdfReader(io.BytesIO(content), strict=False)
        page_texts: list[str] = []
        for page in reader.pages[:2]:
            try:
                page_texts.append(page.extract_text() or "")
            except Exception:
                pass
        combined = re.sub(r"\s+", " ", " ".join(page_texts)).strip()
        return combined[:max_chars] if combined else None
    except Exception as exc:
        logger.warning("_fetch_pdf_text failed for %s: %s", pdf_url, exc)
        return None


class IURCGAOAdapter(SourceAdapter):
    source_system = "iurc_gaos"

    # ------------------------------------------------------------------
    # Cursor
    # ------------------------------------------------------------------

    async def get_sync_cursor(self, db) -> dict:
        from sqlalchemy import select

        result = await db.execute(
            select(SyncState).where(SyncState.source_system == self.source_system)
        )
        row = result.scalar_one_or_none()
        if row and row.cursor_data:
            return row.cursor_data
        return {}

    async def update_sync_cursor(self, db, new_cursor: dict) -> None:
        from sqlalchemy import select

        result = await db.execute(
            select(SyncState).where(SyncState.source_system == self.source_system)
        )
        row = result.scalar_one_or_none()
        now = datetime.utcnow()
        if row:
            row.cursor_data = new_cursor
            row.last_sync_at = now
        else:
            db.add(
                SyncState(
                    source_system=self.source_system,
                    cursor_data=new_cursor,
                    last_sync_at=now,
                )
            )
        await db.commit()

    # ------------------------------------------------------------------
    # Poll
    # ------------------------------------------------------------------

    async def poll(self, cursor: dict) -> list[dict]:
        """Fetch GAO listing page and return raw entry dicts."""
        last_scraped = cursor.get("last_scraped")
        if last_scraped:
            try:
                last_dt = datetime.strptime(last_scraped, "%Y-%m-%d").date()
                if (date.today() - last_dt).days < STALE_DAYS:
                    logger.info(
                        "iurc_gaos: last scraped %s, within %d days — skipping",
                        last_scraped, STALE_DAYS,
                    )
                    return []
            except ValueError:
                pass

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=_HEADERS) as client:
            resp = await client.get(SOURCE_URL)
            resp.raise_for_status()
            html = resp.text

            # Also fetch superseded/withdrawn GAOs
            superseded_html = ""
            try:
                s_resp = await client.get(SUPERSEDED_URL)
                if s_resp.status_code == 200:
                    superseded_html = s_resp.text
            except Exception as exc:
                logger.warning("iurc_gaos: failed to fetch superseded page: %s", exc)

        # Upload raw HTML to R2
        try:
            upload_raw_to_r2(
                self.source_system,
                "general-administrative-orders.html",
                html.encode("utf-8"),
                "text/html",
            )
        except Exception as exc:
            logger.warning("R2 upload failed for iurc_gaos page: %s", exc)

        entries = _parse_page(html)
        logger.info("iurc_gaos: parsed %d active entries", len(entries))

        if superseded_html:
            superseded_entries = _parse_superseded_page(superseded_html)
            logger.info("iurc_gaos: parsed %d superseded entries", len(superseded_entries))
            # Only add superseded entries not already in active list
            active_ids = {e["gao_id"] for e in entries}
            entries.extend(e for e in superseded_entries if e["gao_id"] not in active_ids)

        for entry in entries:
            try:
                gao_slug = entry["gao_id"].replace("/", "_")
                upload_raw_to_r2(
                    self.source_system,
                    f"{gao_slug}.html",
                    (entry.get("row_text") or "").encode("utf-8"),
                    "text/html",
                )
            except Exception as exc:
                logger.warning("R2 upload failed for %s: %s", entry["gao_id"], exc)

        # Fetch PDF text for action_text (one HTTP client shared across all fetches)
        import asyncio as _asyncio

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=_HEADERS) as pdf_client:
            for entry in entries:
                pdf_url = entry.get("pdf_url")
                if not pdf_url:
                    entry["pdf_text"] = None
                    continue
                try:
                    entry["pdf_text"] = await _fetch_pdf_text(pdf_client, pdf_url)
                except Exception as exc:
                    logger.warning(
                        "iurc_gaos: PDF text fetch failed for %s: %s",
                        entry["gao_id"], exc,
                    )
                    entry["pdf_text"] = None
                await _asyncio.sleep(REQUEST_DELAY)

        logger.info(
            "iurc_gaos: fetched PDF text for %d/%d entries",
            sum(1 for e in entries if e.get("pdf_text")),
            len(entries),
        )
        return entries

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> Optional[dict]:
        gao_id = raw.get("gao_id")
        if not gao_id:
            return None

        title = raw.get("title") or gao_id
        pdf_url = raw.get("pdf_url")
        row_text = raw.get("row_text", "")
        category = _categorize_gao(title, row_text)

        # Build a meaningful, non-NULL abstract for search
        abstract = f"IURC General Administrative Order {gao_id}: {title} (category: {category})"

        # Use extracted PDF text as action_text when available
        action_text = raw.get("pdf_text") or None

        return {
            "source_id": gao_id,
            "source_system": self.source_system,
            "jurisdiction_level": "state",
            "jurisdiction_geo": "IN",
            "action_type": "order",
            "source_type": "order",
            "action_text": action_text,
            "title": title,
            "abstract": abstract,
            "agency": "iurc",
            "status": raw.get("status", "approved"),
            "date_published": raw.get("date_published"),
            "date_effective": None,
            "date_comment_close": None,
            "docket_ids": [gao_id],
            "rin": None,
            "cfr_references": [],
            "source_url": raw.get("pdf_url") or SOURCE_URL,
            "full_text_url": pdf_url,
            "adapter_version": "1.1",
        }

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=_HEADERS) as client:
                resp = await client.get(SOURCE_URL)
                return resp.status_code == 200
        except Exception as exc:
            logger.error("iurc_gaos health_check failed: %s", exc)
            return False
