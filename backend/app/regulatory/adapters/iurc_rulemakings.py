"""
IURC Rulemakings adapter — scrapes pending and effective rulemakings from:
https://www.in.gov/iurc/rulemakings/rulemakings-pending-and-effective/
"""

import asyncio
import io
import logging
import re
from datetime import date, datetime
from typing import Optional

import httpx
import pypdf
from bs4 import BeautifulSoup

from app.regulatory.adapters.base import SourceAdapter, upload_raw_to_r2
from app.regulatory.models.sync_state import SyncState

logger = logging.getLogger(__name__)

SOURCE_URL = "https://www.in.gov/iurc/rulemakings/rulemakings-pending-and-effective/"
REQUEST_DELAY = 2.0

# Matches patterns like "170 IAC 4-1-1" or "170IAC4" etc.
_IAC_RE = re.compile(r"(\d{3})\s*iac\s*([\d\-\.]+)", re.IGNORECASE)
# RM number: e.g. RM-24-01, RM 24-01
_RM_RE = re.compile(r"RM[-\s](\d{2,4}[-\s]\d{1,4})", re.IGNORECASE)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

STALE_DAYS = 7

_LSA_RE = re.compile(r"LSA\s*#?\s*(\d{2,4}[-\s]\d{1,4})", re.IGNORECASE)
_DATE_RE = re.compile(
    r"(?:effective|approved|filed|date)[:\s]+(\w+\.?\s+\d{1,2},?\s*\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
# Fallback: any Month DD, YYYY or Month DD YYYY pattern (no keyword prefix required)
_BROAD_DATE_RE = re.compile(
    r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\.?\s+\d{1,2},?\s*\d{4})\b",
    re.IGNORECASE,
)
# Comment deadline: "Comments were/are due by Month DD, YYYY"
_COMMENT_DATE_RE = re.compile(
    r"[Cc]omments?\s+(?:were|are|were\s+due\s+by|are\s+due\s+by|due\s+by|due\s+on)\s+"
    r"(?:by\s+)?"
    r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\.?\s+\d{1,2},?\s*\d{4})",
    re.IGNORECASE,
)
# Subject Matter heading text (h3 on detail pages)
_SUBJECT_MATTER_RE = re.compile(r"subject\s+matter\s+of\s+rule", re.IGNORECASE)


def _extract_iac_refs(text: str) -> list[str]:
    """Extract IAC citations like '170 IAC 4-1-1' from text."""
    refs = []
    for m in _IAC_RE.finditer(text):
        refs.append(f"{m.group(1)} IAC {m.group(2)}")
    return list(dict.fromkeys(refs))  # deduplicate, preserve order


def _normalize_rm_number(raw: str) -> str:
    """Normalize RM number: strip whitespace, uppercase."""
    cleaned = re.sub(r"\s+", "-", raw.strip().upper())
    if not cleaned.startswith("RM-"):
        cleaned = "RM-" + cleaned
    return cleaned


_DETAIL_HREF_RE = re.compile(
    r"/iurc/rulemakings/[^/]*/rm-(\d{2}-\d{2,4})", re.IGNORECASE
)
_DOCKET_HREF_RE = re.compile(r"RM[%20\s_-]+(\d{2}-\d{2,4})", re.IGNORECASE)


def _slug_to_title(slug: str) -> str:
    """Convert a URL slug like 'rm-26-07-amending-170-iac-5-' to a readable title."""
    # Strip leading rm-YY-NN- prefix
    clean = re.sub(r"^rm-\d{2}-\d{2,4}-?", "", slug, flags=re.IGNORECASE)
    clean = clean.strip("-").replace("-", " ").strip()
    return clean.title() if clean else slug


def _parse_page(html: str) -> list[dict]:
    """
    Parse rulemakings from the IURC page HTML.

    The page has no tables — entries are rendered as link groups.
    We find all 'Details' links whose href contains /rm-YY-NN, then
    pair each with its nearby 'Rulemaking Docket' PDF link.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, dict] = {}

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _DETAIL_HREF_RE.search(href)
        if not m:
            continue

        rm_seq = m.group(1)  # e.g. "26-07"
        rm_id = f"RM-{rm_seq.upper()}"

        if rm_id in seen:
            continue

        # Extract slug text for a human-readable title
        slug = href.rstrip("/").rsplit("/", 1)[-1]
        title = _slug_to_title(slug) or rm_id

        # Build full detail URL
        detail_url = href if href.startswith("http") else "https://www.in.gov" + href

        # IAC citations are often in the URL slug: e.g. "amending-170-iac-5-"
        iac_refs = _extract_iac_refs(slug.replace("-", " "))

        # Status: "effective" in slug → approved
        text_lower = slug.lower()
        if "effective" in text_lower or "final" in text_lower:
            status = "approved"
            action_type = "final_rule"
        else:
            status = "in_progress"
            action_type = "proposed_rule"

        seen[rm_id] = {
            "rm_number": rm_id,
            "title": title,
            "status": status,
            "action_type": action_type,
            "detail_url": detail_url,
            "docket_pdf_url": None,
            "iac_refs": iac_refs,
            "raw_text": slug,
        }

    # Second pass: pair each RM with its Rulemaking Docket PDF
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" not in href.lower():
            continue
        dm = _DOCKET_HREF_RE.search(href)
        if not dm:
            continue
        rm_seq = dm.group(1).upper()
        rm_id = f"RM-{rm_seq}"
        if rm_id in seen and not seen[rm_id]["docket_pdf_url"]:
            full = href if href.startswith("http") else "https://www.in.gov" + href
            seen[rm_id]["docket_pdf_url"] = full
            # Also pull IAC refs from text near the PDF link
            parent_text = a.parent.get_text(" ") if a.parent else ""
            seen[rm_id]["iac_refs"] = list(dict.fromkeys(
                seen[rm_id]["iac_refs"] + _extract_iac_refs(parent_text)
            ))

    return list(seen.values())


def _parse_date_str(text: str) -> Optional[str]:
    """Try to parse a date from arbitrary text.

    First looks for a keyword-prefixed date (effective/approved/filed/date:),
    then falls back to any full Month DD, YYYY pattern found in the text.
    """
    _DATE_FMTS = ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%m/%d/%Y", "%Y-%m-%d")

    def _try_parse(raw: str) -> Optional[str]:
        cleaned = re.sub(r"\s+", " ", raw).strip().rstrip(",")
        for fmt in _DATE_FMTS:
            try:
                return datetime.strptime(cleaned, fmt).date().isoformat()
            except ValueError:
                continue
        return None

    m = _DATE_RE.search(text)
    if m:
        result = _try_parse(m.group(1))
        if result:
            return result

    # Fallback: broad month-day-year scan
    m2 = _BROAD_DATE_RE.search(text)
    if m2:
        return _try_parse(m2.group(1))
    return None


def _parse_comment_date(text: str) -> Optional[str]:
    """Extract comment-due date from text like 'Comments were due by July 15, 2026.'"""
    _DATE_FMTS = ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y")
    m = _COMMENT_DATE_RE.search(text)
    if not m:
        return None
    raw = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(",")
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


async def _fetch_detail(client: httpx.AsyncClient, entry: dict) -> dict:
    """
    Fetch an RM detail page and optionally its docket PDF to extract
    LSA number, date_published, date_comment_close, and abstract.
    Returns a dict with those keys (values may be None).
    Best-effort: returns empty dict on any failure.
    """
    detail_url = entry.get("detail_url")
    if not detail_url:
        return {}
    try:
        resp = await client.get(detail_url, timeout=20.0)
        if resp.status_code != 200:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        page_text = soup.get_text(" ")

        # Extract LSA from page text
        lsa_m = _LSA_RE.search(page_text)
        lsa_number = lsa_m.group(1).strip() if lsa_m else None

        # Extract comment-due date (date_comment_close)
        date_comment_close = _parse_comment_date(page_text)

        # Try to get date_published from keyword-prefixed pattern first,
        # then fall back to any month/day/year in the text
        date_published = _parse_date_str(page_text)

        # Extract abstract from "Subject Matter of Rule" h3 section
        abstract: Optional[str] = None
        for tag in soup.find_all("h3"):
            if _SUBJECT_MATTER_RE.search(tag.get_text()):
                # Walk forward siblings to find the first substantial text block
                for sib in tag.next_siblings:
                    if not hasattr(sib, "get_text"):
                        continue
                    text = sib.get_text(" ", strip=True)
                    if len(text) > 30:
                        abstract = text[:600]
                        break
                break

        # If no LSA yet, try fetching the docket PDF
        if not lsa_number and entry.get("docket_pdf_url"):
            try:
                pr = await client.get(entry["docket_pdf_url"], timeout=20.0)
                if pr.status_code == 200:
                    reader = pypdf.PdfReader(io.BytesIO(pr.content))
                    pdf_text = "\n".join(pg.extract_text() or "" for pg in reader.pages[:3])
                    lsa_m2 = _LSA_RE.search(pdf_text)
                    if lsa_m2:
                        lsa_number = lsa_m2.group(1).strip()
                    if not date_published:
                        date_published = _parse_date_str(pdf_text)
            except Exception as exc:
                logger.debug("iurc_rulemakings: PDF fetch/parse failed for %s: %s", entry.get("rm_number"), exc)

        return {
            "lsa_number": lsa_number,
            "date_published": date_published,
            "date_comment_close": date_comment_close,
            "abstract": abstract,
        }
    except Exception as exc:
        logger.debug("iurc_rulemakings: detail fetch failed for %s: %s", entry.get("rm_number"), exc)
        return {}


class IURCRulemakerAdapter(SourceAdapter):
    source_system = "iurc_rulemakings"

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
        """Fetch rulemakings page and return list of raw entry dicts."""
        last_scraped = cursor.get("last_scraped")
        if last_scraped:
            try:
                last_dt = datetime.strptime(last_scraped, "%Y-%m-%d").date()
                if (date.today() - last_dt).days < STALE_DAYS:
                    logger.info(
                        "iurc_rulemakings: last scraped %s, within %d days — skipping",
                        last_scraped, STALE_DAYS,
                    )
                    return []
            except ValueError:
                pass

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=_HEADERS) as client:
            resp = await client.get(SOURCE_URL)
            resp.raise_for_status()
            html = resp.text

        # Upload raw HTML to R2
        try:
            upload_raw_to_r2(
                self.source_system,
                "rulemakings-pending-effective.html",
                html.encode("utf-8"),
                "text/html",
            )
        except Exception as exc:
            logger.warning("R2 upload failed for iurc_rulemakings page: %s", exc)

        entries = _parse_page(html)
        logger.info("iurc_rulemakings: parsed %d entries", len(entries))

        # Fetch detail pages for LSA number and date
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=_HEADERS) as detail_client:
            for entry in entries:
                detail = await _fetch_detail(detail_client, entry)
                entry.update(detail)
                await asyncio.sleep(REQUEST_DELAY)

        # Also upload per-entry raw text to R2
        for entry in entries:
            try:
                rm_slug = entry["rm_number"].replace("/", "_")
                upload_raw_to_r2(
                    self.source_system,
                    f"{rm_slug}.html",
                    (entry.get("raw_text") or "").encode("utf-8"),
                    "text/html",
                )
            except Exception as exc:
                logger.warning("R2 upload failed for %s: %s", entry["rm_number"], exc)

        return entries

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> Optional[dict]:
        rm_id = raw.get("rm_number")
        if not rm_id:
            return None

        title = raw.get("title") or rm_id
        detail_url = raw.get("detail_url") or SOURCE_URL

        docket_pdf = raw.get("docket_pdf_url")
        lsa = raw.get("lsa_number")
        docket_ids = [rm_id]
        if lsa:
            normalized_lsa = re.sub(r"\s+", "-", lsa.strip())
            if not normalized_lsa.upper().startswith("LSA-"):
                normalized_lsa = "LSA-" + normalized_lsa
            docket_ids.append(normalized_lsa.upper())

        iac_refs = raw.get("iac_refs", [])
        return {
            "source_id": rm_id,
            "source_system": self.source_system,
            "jurisdiction_level": "state",
            "jurisdiction_geo": "IN",
            "action_type": raw.get("action_type", "proposed_rule"),
            "source_type": "rulemaking",
            "action_text": None,
            "title": title,
            "abstract": raw.get("abstract"),
            "agency": "iurc",
            "status": raw.get("status", "in_progress"),
            "date_published": raw.get("date_published"),
            "date_effective": None,
            "date_comment_close": raw.get("date_comment_close"),
            "docket_ids": docket_ids,
            "rin": None,
            # IAC citations belong in legal_refs only; cfr_references is for
            # federal CFR citations. The stitcher (stitch_iac_to_codebook) reads
            # both fields combined, so legal_refs alone is sufficient for IAC
            # stitching and cfr_references is intentionally left empty.
            "cfr_references": [],
            "legal_refs": iac_refs,
            "source_url": detail_url,
            "full_text_url": docket_pdf or detail_url,
            "adapter_version": "1.0",
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
            logger.error("iurc_rulemakings health_check failed: %s", exc)
            return False
