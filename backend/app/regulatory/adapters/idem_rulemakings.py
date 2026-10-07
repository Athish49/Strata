"""
IDEM Rulemakings adapter — scrapes Environmental Rules Board packets from:
https://www.in.gov/idem/legal/rulemaking/environmental-rules-board-packets/
"""

import logging
import re
from datetime import date, datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.regulatory.adapters.base import SourceAdapter, upload_raw_to_r2
from app.regulatory.models.sync_state import SyncState

logger = logging.getLogger(__name__)

SOURCE_URL = "https://www.in.gov/idem/legal/rulemaking/environmental-rules-board-packets/"
REQUEST_DELAY = 2.0

# LSA number patterns: LSA-YY-NNN or LSA-YYYY-NNN
_LSA_RE = re.compile(r"LSA[-\s](\d{2,4})[-\s](\d{1,4})", re.IGNORECASE)

# IAC reference extraction
_IAC_RE = re.compile(r"(\d{3})\s*iac\s*([\d\-\.]+)", re.IGNORECASE)

# Date patterns
_DATE_PATTERNS = [
    (re.compile(r"\b(\w+ \d{1,2},?\s*\d{4})\b"), ["%B %d, %Y", "%B %d %Y"]),
    (re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b"), ["%m/%d/%Y"]),
    (re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"), ["%Y-%m-%d"]),
    (re.compile(r"\b(\d{8})\b"), ["%Y%m%d"]),
]

# Status keywords: "final" → approved, else in_progress
_FINAL_RE = re.compile(r"\b(final|adopted|effective)\b", re.IGNORECASE)
_PROPOSED_RE = re.compile(r"\b(proposed|draft|pending|preliminary)\b", re.IGNORECASE)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

STALE_DAYS = 7


def _parse_date(text: str) -> Optional[str]:
    """Try to parse a date string from text."""
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


def _extract_iac_refs(text: str) -> list[str]:
    """Extract IAC citations like '326 IAC 2-2' from text."""
    refs = []
    for m in _IAC_RE.finditer(text):
        refs.append(f"{m.group(1)} IAC {m.group(2)}")
    return list(dict.fromkeys(refs))


def _normalize_lsa_id(year_str: str, num_str: str) -> str:
    """Normalize LSA id: LSA-YY-NNN → LSA-20YY-NNN."""
    year = year_str.zfill(2)
    if len(year) == 2:
        year = "20" + year
    return f"LSA-{year}-{num_str.zfill(3)}"


def _infer_status(text: str) -> tuple[str, str]:
    """Infer (status, action_type) from document description text."""
    if _FINAL_RE.search(text):
        return "approved", "final_rule"
    if _PROPOSED_RE.search(text):
        return "in_progress", "rulemaking"
    return "in_progress", "rulemaking"


# Matches any path containing the ERB filename pattern, regardless of path prefix.
# Covers both /idem/legal/files/rules_erb_... (new uploads) and
# /dA/<hash>/rules_erb_... (older CMS-asset paths).
# The query string (?language_id=1) is handled by not anchoring with $.
_ERB_PDF_RE = re.compile(
    r"rules_erb_(\d{8})_(\d{2,4}-\d{1,4})_([a-z0-9_]+)\.pdf",
    re.IGNORECASE,
)

# Prefer the "infosheet" / "info_sheet" PDF as canonical; fall back to first seen.
# Both spellings appear: /idem/legal/files/ uses "infosheet", /dA/ uses "info_sheet".
_INFO_TYPE_PRIORITY = ["infosheet", "info_sheet", "draft_rule", "reg_analysis", "rtc", "final_rule"]


def _parse_page(html: str) -> list[dict]:
    """
    Parse IDEM ERB rulemaking entries from the page.

    The page has no structured table of LSA entries — data lives in PDF
    link hrefs following the pattern:
        /idem/legal/files/rules_erb_{YYYYMMDD}_{YY-NNN}_{type}.pdf

    We parse every such href, group by LSA number, and build one entry per LSA.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, dict] = {}  # lsa_id → entry dict

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _ERB_PDF_RE.search(href)
        if not m:
            continue

        date_str, lsa_raw, doc_type = m.group(1), m.group(2), m.group(3).lower()
        lsa_id = f"LSA-{lsa_raw}"

        # Parse the date from the filename: YYYYMMDD
        date_published = None
        try:
            date_published = datetime.strptime(date_str, "%Y%m%d").date().isoformat()
        except ValueError:
            pass

        full_href = href if href.startswith("http") else "https://www.in.gov" + href

        # Infer status from document type
        if doc_type in ("final_rule", "adopted", "effective"):
            status, action_type = "approved", "final_rule"
        else:
            status, action_type = "in_progress", "rulemaking"

        # Link text may contain IAC citations and useful title text
        link_text = a.get_text(" ").strip()
        iac_refs = _extract_iac_refs(link_text)

        # Extract rule heading from grandparent <li> (a→li→ul→li structure):
        # <li>Title 329 Coal Combustion Residuals Rule, LSA #21-458
        #   <ul><li><a href="...">LSA #21-458 Rule Information Sheet</a></li>...</ul>
        # </li>
        rule_heading = ""
        inner_li = a.parent  # <li>
        if inner_li and getattr(inner_li, "name", None) == "li":
            inner_ul = inner_li.parent  # <ul>
            if inner_ul and getattr(inner_ul, "name", None) == "ul":
                outer_li = inner_ul.parent  # outer <li>
                if outer_li and getattr(outer_li, "name", None) == "li":
                    # Collect text children before the nested <ul>
                    parts = []
                    for child in outer_li.children:
                        if getattr(child, "name", None) == "ul":
                            break
                        if hasattr(child, "get_text"):
                            parts.append(child.get_text(" "))
                        else:
                            parts.append(str(child))
                    rule_heading = " ".join(parts).strip().strip(",").strip()

        if lsa_id not in seen:
            seen[lsa_id] = {
                "lsa_id": lsa_id,
                "title": rule_heading[:300] or link_text[:300] or lsa_id,
                "date_published": date_published,
                "status": status,
                "action_type": action_type,
                "iac_refs": iac_refs,
                "pdf_url": full_href,
                "pdf_type": doc_type,
                "row_text": link_text,
                "rule_heading": rule_heading,
            }
        else:
            entry = seen[lsa_id]
            # Upgrade to final if we see a final document type
            if status == "approved" and entry["status"] != "approved":
                entry["status"] = "approved"
                entry["action_type"] = action_type
            # Use more informative date (latest wins)
            if date_published and (not entry["date_published"] or date_published > entry["date_published"]):
                entry["date_published"] = date_published
            # Prefer infosheet as canonical PDF URL
            current_priority = next(
                (i for i, t in enumerate(_INFO_TYPE_PRIORITY) if t in entry.get("pdf_type", "")), 99
            )
            new_priority = next(
                (i for i, t in enumerate(_INFO_TYPE_PRIORITY) if t in doc_type), 99
            )
            if new_priority < current_priority:
                entry["pdf_url"] = full_href
                entry["pdf_type"] = doc_type
            entry["iac_refs"] = list(dict.fromkeys(entry["iac_refs"] + iac_refs))

    return list(seen.values())


class IDEMRulemakerAdapter(SourceAdapter):
    source_system = "idem_rulemakings"

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
        """Fetch ERB packets listing page and return raw entry dicts."""
        last_scraped = cursor.get("last_scraped")
        if last_scraped:
            try:
                last_dt = datetime.strptime(last_scraped, "%Y-%m-%d").date()
                if (date.today() - last_dt).days < STALE_DAYS:
                    logger.info(
                        "idem_rulemakings: last scraped %s, within %d days — skipping",
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
                "erb-packets.html",
                html.encode("utf-8"),
                "text/html",
            )
        except Exception as exc:
            logger.warning("R2 upload failed for idem_rulemakings page: %s", exc)

        entries = _parse_page(html)
        logger.info("idem_rulemakings: parsed %d entries", len(entries))

        for entry in entries:
            try:
                lsa_slug = entry["lsa_id"].replace("/", "_")
                upload_raw_to_r2(
                    self.source_system,
                    f"{lsa_slug}.html",
                    (entry.get("row_text") or "").encode("utf-8"),
                    "text/html",
                )
            except Exception as exc:
                logger.warning("R2 upload failed for %s: %s", entry["lsa_id"], exc)

        return entries

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> Optional[dict]:
        lsa_id = raw.get("lsa_id")
        if not lsa_id:
            return None

        title = raw.get("title") or lsa_id
        pdf_url = raw.get("pdf_url")

        iac_refs = raw.get("iac_refs", [])
        rule_heading = raw.get("rule_heading", "").strip()
        doc_type = raw.get("pdf_type", "").replace("_", " ")
        # Build abstract from rule heading + doc type; omit blank segments
        if rule_heading:
            abstract = f"IDEM Environmental Rules Board rulemaking: {rule_heading}"
            if doc_type:
                abstract = f"{abstract} ({doc_type})"
        else:
            abstract = None

        return {
            "source_id": lsa_id,
            "source_system": self.source_system,
            "jurisdiction_level": "state",
            "jurisdiction_geo": "IN",
            "action_type": raw.get("action_type", "rulemaking"),
            "source_type": "rulemaking",
            "action_text": None,
            "title": title,
            "abstract": abstract,
            "agency": "idem",
            "status": raw.get("status", "in_progress"),
            "date_published": raw.get("date_published"),
            "date_effective": None,
            "date_comment_close": None,
            "docket_ids": [lsa_id] if lsa_id else [],
            "rin": None,
            # NOTE: cfr_references intentionally keeps IAC citations because
            # stitcher.stitch_action_to_codebook reads cfr_references and uses
            # infer_codebook() to route IAC citations to 'iac' CodeSections.
            # Both fields are populated so legal_refs is also semantically correct.
            "cfr_references": iac_refs,
            "legal_refs": iac_refs,
            "source_url": SOURCE_URL,
            "full_text_url": pdf_url,
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
            logger.error("idem_rulemakings health_check failed: %s", exc)
            return False
