"""
IURC Investigations adapter — discovers docket cases via weekly filings PDFs.

Weekly filings listing page:
  https://www.in.gov/iurc/docketed-cases/find-a-docketed-case/weekly-filings

PDF links on that page have inconsistent filenames, so we scrape the page
instead of constructing URLs, then parse each PDF with pypdf.
"""

import io
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
import pypdf
from bs4 import BeautifulSoup

from app.regulatory.adapters.base import SourceAdapter, upload_raw_to_r2
from app.regulatory.models.sync_state import SyncState

logger = logging.getLogger(__name__)

IURC_FILINGS_PAGE = (
    "https://www.in.gov/iurc/docketed-cases/find-a-docketed-case/weekly-filings"
)
IURC_BASE = "https://www.in.gov"
REQUEST_DELAY = 2.0

# PDF text line format: "9/21/2026 38703 - FAC 153 Utility Name  Description"
# Cause number is the 5-digit number after the date
_LINE_RE = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{4})\s+(\d{4,6})\s*[-–]?\s*([A-Z0-9]*)\s+(.{0,200})"
)

# Matches commission investigation sub-code and description keywords.
# \binvestigation\b is guarded in the parser to NONE/empty sub-codes only
# to avoid false positives from procedural filings in sub-docket cases.
_INVESTIGATION_KEYWORDS = re.compile(
    r"\binvestigation\b|commission\s+investigation|order\s+commencing\s+investigation"
    r"|investigative\s+inquiry|generic\s+proceeding",
    re.IGNORECASE,
)

# Page headers and footers produced by the PDF that should be skipped
_SKIP_LINE_RE = re.compile(
    r"^Date Filed\s+Case Number|^Weekly Filings Report"
    r"|^\d{1,2}/\d{1,2}/\d{4}\s+through|Prepared by.+\d+\s+of\s+\d+",
    re.IGNORECASE,
)

KNOWN_GENERIC_CAUSES = [
    {
        "cause_number": "45816",
        "title": "PURPA Section 111(d) Standards — IIJA amendments",
        "date_filed": "01/01/2023",
        "week_label": "backfill",
    },
    {
        "cause_number": "46043",
        "title": "DER Aggregator Public Utility Status — FERC Order 2222",
        "date_filed": "01/01/2024",
        "week_label": "backfill",
    },
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Limit how many weekly PDFs to fetch per poll (most recent N weeks)
MAX_WEEKS = 4


def _scrape_pdf_links(html: str) -> list[tuple[str, str]]:
    """
    Extract (link_text, href) pairs for weekly filings PDFs from the listing page.
    Returns in page order (newest first).
    """
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "weekly" in href.lower() and ".pdf" in href.lower():
            full = href if href.startswith("http") else IURC_BASE + href
            links.append((a.get_text(strip=True), full))
    return links


def _parse_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from a PDF using pypdf."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _parse_cause_entries(text: str, week_label: str) -> list[dict]:
    """
    Parse cause numbers from weekly filings PDF text.

    Handles multi-line entries by accumulating continuation lines onto the
    current cause's description before evaluating investigation keywords.

    Each data line: date  cause_number  sub-code  sub-num  utility  description
    Continuation lines: utility name or description text with no date prefix.

    Returns deduplicated list of {cause_number, title, date_filed, is_investigation}.
    """
    # First pass: accumulate all description text per cause, preserving first-line title.
    cause_data: dict[str, dict] = {}
    current_cause: Optional[str] = None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            current_cause = None
            continue
        # Skip page headers and footers
        if _SKIP_LINE_RE.search(line):
            current_cause = None
            continue

        m = _LINE_RE.match(line)
        if m:
            date_filed, cause, _sub, rest = (
                m.group(1),
                m.group(2),
                m.group(3),
                m.group(4),
            )
            # Strip sub-case artifact from the rest field
            rest = re.sub(r"^\s*[-–]\s*[A-Z]+\s*\d+\s*", "", rest)
            rest = re.sub(r"^\s*\d+\s+(?=[A-Z])", "", rest)
            desc = re.sub(r"\s+", " ", rest).strip()

            current_cause = cause
            if cause not in cause_data:
                cause_data[cause] = {
                    "cause_number": cause,
                    "date_filed": date_filed,
                    "week_label": week_label,
                    "sub": _sub,
                    "all_text": desc,
                    "first_desc": desc,
                }
            else:
                # Cause already seen in this PDF — accumulate additional filing text
                cause_data[cause]["all_text"] += " " + desc
        else:
            # Continuation line (wrapped utility name or description)
            if current_cause and current_cause in cause_data:
                continuation = re.sub(r"\s+", " ", line).strip()
                cause_data[current_cause]["all_text"] += " " + continuation

    # Second pass: determine is_investigation from sub-code and full accumulated text.
    results = []
    for cause, data in cause_data.items():
        sub = data["sub"]
        all_text = data["all_text"]

        # "CI" sub-code is the definitive Commission Investigation marker.
        # For cases with NONE/empty sub-code, match description keywords;
        # guard against false positives in sub-docket cases (GCA, FAC, etc.).
        if sub == "CI":
            is_investigation = True
        elif _INVESTIGATION_KEYWORDS.search(all_text) and sub in ("NONE", ""):
            is_investigation = True
        else:
            is_investigation = False

        title = data["first_desc"][:300] or f"IURC Cause {cause}"
        results.append(
            {
                "cause_number": cause,
                "title": title,
                "date_filed": data["date_filed"],
                "week_label": data["week_label"],
                "is_investigation": is_investigation,
            }
        )

    return results


class IURCInvestigationsAdapter(SourceAdapter):
    source_system = "iurc_investigations"

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
        """
        Persist sync cursor, enriched with the full set of known cause numbers.

        Loads source_ids from the DB (covering all previously ingested causes)
        and merges them with any causes accumulated during this poll run.
        This makes the known_causes list the authoritative deduplication source
        for future runs, avoiding redundant DB round-trips per cause.
        """
        from sqlalchemy import select, text as sql_text

        # Query all cause numbers already stored in DB for this source
        result = await db.execute(
            sql_text(
                "SELECT source_id FROM regulatory_actions WHERE source_system = :sys"
            ),
            {"sys": self.source_system},
        )
        db_source_ids = {row[0] for row in result.fetchall()}

        # Merge DB ids with causes encountered during this poll run
        accumulated = getattr(self, "_accumulated_causes", set())
        all_known = db_source_ids | accumulated

        merged = {**new_cursor, "known_causes": sorted(all_known)}

        result2 = await db.execute(
            select(SyncState).where(SyncState.source_system == self.source_system)
        )
        row = result2.scalar_one_or_none()
        now = datetime.utcnow()
        if row:
            row.cursor_data = merged
            row.last_sync_at = now
        else:
            db.add(
                SyncState(
                    source_system=self.source_system,
                    cursor_data=merged,
                    last_sync_at=now,
                )
            )
        await db.commit()

    # ------------------------------------------------------------------
    # Poll
    # ------------------------------------------------------------------

    async def poll(self, cursor: dict) -> list[dict]:
        """
        Scrape the weekly filings listing page, download the most recent PDFs,
        and extract cause numbers from each.

        Incremental: skips cause numbers already present in known_causes cursor.
        Merges is_investigation=True across multiple weeks for the same cause.
        """
        import asyncio

        # Causes already ingested in prior runs — skip them to avoid redundant work
        known_causes: set[str] = set(cursor.get("known_causes", []))

        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, headers=_HEADERS
        ) as client:
            # Step 1: get the listing page and extract PDF links
            resp = await client.get(IURC_FILINGS_PAGE)
            resp.raise_for_status()
            pdf_links = _scrape_pdf_links(resp.text)

            if not pdf_links:
                logger.warning(
                    "iurc_investigations: no weekly PDF links found on listing page"
                )
                return []

            # Limit to most recent MAX_WEEKS PDFs
            recent_links = pdf_links[:MAX_WEEKS]
            logger.info(
                "iurc_investigations: fetching %d weekly PDFs", len(recent_links)
            )

            all_entries: list[dict] = []
            # Dict keyed by cause_number so we can update is_investigation across weeks
            seen_causes: dict[str, dict] = {}

            for week_label, pdf_url in recent_links:
                logger.info(
                    "iurc_investigations: fetching %s (%s)", week_label, pdf_url
                )
                try:
                    r = await client.get(pdf_url)
                    if r.status_code != 200:
                        logger.warning(
                            "iurc_investigations: %s returned %s",
                            pdf_url,
                            r.status_code,
                        )
                        continue
                    pdf_bytes = r.content
                except Exception as exc:
                    logger.warning(
                        "iurc_investigations: failed to fetch %s: %s", pdf_url, exc
                    )
                    continue

                try:
                    text = _parse_pdf_text(pdf_bytes)
                except Exception as exc:
                    logger.warning(
                        "iurc_investigations: PDF parse failed for %s: %s",
                        pdf_url,
                        exc,
                    )
                    continue

                # Upload raw text to R2
                try:
                    safe_label = re.sub(r"[^\w\-]", "_", week_label)
                    upload_raw_to_r2(
                        self.source_system,
                        f"weekly-{safe_label}.txt",
                        text.encode("utf-8"),
                        "text/plain",
                    )
                except Exception as exc:
                    logger.warning("R2 upload failed for weekly text: %s", exc)

                entries = _parse_cause_entries(text, week_label)
                new_this_week = 0
                for e in entries:
                    cause = e["cause_number"]
                    if cause in seen_causes:
                        # Cause already encountered in a newer week's PDF.
                        # OR the is_investigation flag — if any week detects it, keep True.
                        if e.get("is_investigation") and not seen_causes[cause].get(
                            "is_investigation"
                        ):
                            seen_causes[cause]["is_investigation"] = True
                        continue

                    # Track for cross-week OR and for KNOWN_GENERIC_CAUSES override
                    seen_causes[cause] = e

                    if cause in known_causes:
                        # Already ingested in a prior run — skip to avoid duplicate work.
                        # The SQL UPDATE step (run separately) handles retroactive
                        # action_type corrections on stored rows.
                        continue

                    e["source_pdf_url"] = pdf_url
                    all_entries.append(e)
                    new_this_week += 1

                logger.info(
                    "iurc_investigations: %s — %d new cause numbers",
                    week_label,
                    new_this_week,
                )
                await asyncio.sleep(REQUEST_DELAY)

        # Force is_investigation=True for known generic commission investigations.
        # These may appear in the PDF without keywords in the filing description,
        # or may not appear in the recent 4-week window at all.
        for known in KNOWN_GENERIC_CAUSES:
            cause = known["cause_number"]
            if cause in seen_causes:
                # Cause came from this run's PDFs — force the flag on the shared dict.
                # Because all_entries holds a reference to the same dict object,
                # this update is reflected in all_entries automatically.
                seen_causes[cause]["is_investigation"] = True
            elif cause not in known_causes:
                # Not in recent PDFs and not already known — add as backfill entry.
                new_entry = {**known, "is_investigation": True}
                all_entries.append(new_entry)
            # If cause is in known_causes but not seen_causes:
            # it's already in DB; the SQL UPDATE step handles retroactive correction.

        # Stash accumulated causes for update_sync_cursor to merge into cursor
        self._accumulated_causes = set(e["cause_number"] for e in all_entries)

        logger.info(
            "iurc_investigations: total %d unique causes found", len(all_entries)
        )
        return all_entries

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> Optional[dict]:
        cause = raw.get("cause_number")
        if not cause:
            return None

        title = raw.get("title") or f"IURC Cause {cause}"
        source_pdf = raw.get("source_pdf_url", IURC_FILINGS_PAGE)

        # Parse date_filed from "9/21/2026" format
        date_published = None
        raw_date = raw.get("date_filed", "")
        try:
            date_published = datetime.strptime(raw_date, "%m/%d/%Y").date().isoformat()
        except (ValueError, TypeError):
            pass

        is_investigation = raw.get("is_investigation", False)
        action_type = "commission_investigation" if is_investigation else "order"
        action_type_label = "Commission Investigation" if is_investigation else "Docketed Case"
        abstract = f"IURC {action_type_label}: {title}" if title else None

        return {
            "source_id": cause,
            "source_system": self.source_system,
            "jurisdiction_level": "state",
            "jurisdiction_geo": "IN",
            "action_type": action_type,
            "source_type": "order",
            "action_text": None,
            "title": title,
            "abstract": abstract,
            "agency": "iurc",
            "status": "in_progress",
            "date_published": date_published,
            "date_effective": None,
            "date_comment_close": None,
            "docket_ids": [cause],
            "rin": None,
            "cfr_references": [],
            "source_url": IURC_FILINGS_PAGE,
            "full_text_url": source_pdf,
            "adapter_version": "1.0",
        }

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Check that the IURC files directory is reachable."""
        try:
            async with httpx.AsyncClient(
                timeout=15.0, follow_redirects=True, headers=_HEADERS
            ) as client:
                resp = await client.get("https://www.in.gov/iurc/")
                return resp.status_code == 200
        except Exception as exc:
            logger.error("iurc_investigations health_check failed: %s", exc)
            return False
