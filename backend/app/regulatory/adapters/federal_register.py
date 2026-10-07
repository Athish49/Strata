"""Federal Register adapter — polls RULE and PRORULE documents for FERC and EPA."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.regulatory.adapters.base import SourceAdapter, upload_raw_to_r2
from app.regulatory.models.sync_state import SyncState

logger = logging.getLogger(__name__)

FR_BASE = "https://www.federalregister.gov/api/v1"
TARGET_AGENCIES = [
    "federal-energy-regulatory-commission",
    "environmental-protection-agency",
]
TARGET_TYPES = ["RULE", "PRORULE"]

AGENCY_SLUG_TO_ID = {
    "federal-energy-regulatory-commission": "ferc",
    "environmental-protection-agency": "epa",
}

# (fr_type, action_text_substring) → action_type
# Order matters — check most specific first; empty string is the catch-all default.
ACTION_TYPE_MAP = {
    ("Rule", "interim final"): "interim_final_rule",
    ("Rule", "direct final"): "direct_final_rule",
    ("Rule", "correction"): "correction",
    ("Rule", "withdrawal"): "withdrawal",
    ("Rule", ""): "final_rule",
    ("Proposed Rule", "advance notice"): "advance_notice",
    ("Proposed Rule", ""): "proposed_rule",
}

# Fields to request from the API (avoids fetching full-text body in the listing call)
_FIELDS = [
    "document_number",
    "title",
    "type",
    "action",
    "abstract",
    "publication_date",
    "effective_on",
    "comments_close_on",
    "docket_ids",
    "regulation_id_numbers",
    "cfr_references",
    "agencies",
    "html_url",
    "full_text_xml_url",
    "body_html_url",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _quarter_label(publication_date: str) -> str:
    """Return 'YYYY-QN' from an ISO date string, e.g. '2025-03-15' → '2025-Q1'."""
    try:
        dt = datetime.strptime(publication_date, "%Y-%m-%d")
        q = (dt.month - 1) // 3 + 1
        return f"{dt.year}-Q{q}"
    except (ValueError, TypeError):
        return "unknown"


def map_action_type(fr_type: str, action_text: str) -> str:
    """Map FR type + free-text action field to a canonical action_type string."""
    text_lower = (action_text or "").lower()
    # Walk the map in definition order; tuples with a non-empty substring first,
    # then the catch-all (empty string matches everything).
    for (t, substr), action_type in ACTION_TYPE_MAP.items():
        if t != fr_type:
            continue
        if substr == "" or substr in text_lower:
            return action_type
    # Fallback for unrecognized type/action combinations
    return "final_rule" if fr_type == "Rule" else "proposed_rule"


def map_status(fr_type: str, effective_on: Optional[str]) -> str:
    """Derive status from FR document type."""
    if fr_type == "Proposed Rule":
        return "in_progress"
    # Rule (including interim, direct, correction, withdrawal) is treated as approved
    return "approved"


def map_agency(agencies_list: list) -> Optional[str]:
    """Return the canonical agency ID for the first matching agency slug."""
    for agency in agencies_list:
        slug = agency.get("slug", "")
        if slug in AGENCY_SLUG_TO_ID:
            return AGENCY_SLUG_TO_ID[slug]
    return None


def extract_rin(rins_list: list) -> Optional[str]:
    """Return the first RIN string, or None."""
    if rins_list:
        return rins_list[0]
    return None


def extract_cfr_refs(cfr_refs_list: list) -> list:
    """Convert cfr_references entries to 'NN CFR PP' strings, deduplicated."""
    seen = set()
    result = []
    for ref in cfr_refs_list:
        title = ref.get("title")
        part = ref.get("part")
        if title is not None and part is not None:
            label = f"{title} CFR {part}"
            if label not in seen:
                seen.add(label)
                result.append(label)
    return result


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class FederalRegisterAdapter(SourceAdapter):
    source_system = "federal_register"

    # ------------------------------------------------------------------
    # Cursor
    # ------------------------------------------------------------------

    async def get_sync_cursor(self, db) -> dict:
        """Return cursor_data from sync_state for this source, or {}."""
        from sqlalchemy import select

        result = await db.execute(
            select(SyncState).where(SyncState.source_system == self.source_system)
        )
        row = result.scalar_one_or_none()
        if row and row.cursor_data:
            return row.cursor_data
        return {}

    async def update_sync_cursor(self, db, new_cursor: dict) -> None:
        """Upsert sync_state cursor for this source."""
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
        """Fetch all matching FR documents since the cursor date. Returns raw dicts."""
        since_date = cursor.get("last_publication_date") or "2025-01-01"
        end_date = cursor.get("end_date")

        params = [
            ("conditions[publication_date][gte]", since_date),
            ("per_page", "100"),
            ("order", "newest"),
        ]
        if end_date:
            params.append(("conditions[publication_date][lte]", end_date))
        for agency in TARGET_AGENCIES:
            params.append(("conditions[agencies][]", agency))
        for doc_type in TARGET_TYPES:
            params.append(("conditions[type][]", doc_type))
        for field in _FIELDS:
            params.append(("fields[]", field))

        url = f"{FR_BASE}/documents.json"
        all_docs: list[dict] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            first_page = True
            while url:
                if not first_page:
                    await asyncio.sleep(1)  # polite 1 req/sec between pages
                first_page = False

                if url == f"{FR_BASE}/documents.json":
                    response = await client.get(url, params=params)
                else:
                    # next_page_url already contains all query params
                    response = await client.get(url)

                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if not results:
                    break

                for doc in results:
                    # Upload raw JSON to R2 for audit trail
                    try:
                        pub_date = doc.get("publication_date", "")
                        quarter = _quarter_label(pub_date)
                        doc_num = doc.get("document_number", "unknown")
                        raw_bytes = json.dumps(doc).encode("utf-8")
                        upload_raw_to_r2(
                            "federal_register",
                            f"{quarter}/{doc_num}.json",
                            raw_bytes,
                            "application/json",
                        )
                    except Exception as exc:
                        logger.warning("R2 upload failed for %s: %s", doc.get("document_number"), exc)

                    all_docs.append(doc)

                url = data.get("next_page_url")  # None when exhausted

        return all_docs

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> Optional[dict]:
        """Convert a raw FR document dict to a RegulatoryAction dict."""
        try:
            agency = map_agency(raw.get("agencies", []))
            if agency is None:
                logger.warning(
                    "normalize: skipping %s — no matching agency in %s",
                    raw.get("document_number"),
                    [a.get("slug") for a in raw.get("agencies", [])],
                )
                return None

            fr_type = raw.get("type", "")
            action_text = raw.get("action", "")

            return {
                "source_id": raw["document_number"],
                "source_system": "federal_register",
                "jurisdiction_level": "federal",
                "action_type": map_action_type(fr_type, action_text),
                "source_type": fr_type,
                "action_text": action_text,
                "title": raw["title"],
                "abstract": raw.get("abstract"),
                "agency": agency,
                "status": map_status(fr_type, raw.get("effective_on")),
                "date_published": raw.get("publication_date"),
                "date_effective": raw.get("effective_on"),
                "date_comment_close": raw.get("comments_close_on"),
                "docket_ids": raw.get("docket_ids", []),
                "rin": extract_rin(raw.get("regulation_id_numbers", [])),
                "cfr_references": extract_cfr_refs(raw.get("cfr_references", [])),
                "source_url": raw["html_url"],
                "full_text_url": raw.get("full_text_xml_url") or raw.get("body_html_url"),
                "adapter_version": "1.0",
            }
        except Exception as exc:
            logger.error("normalize failed for %s: %s", raw.get("document_number"), exc)
            return None

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Return True if the Federal Register API is reachable."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{FR_BASE}/documents.json", params={"per_page": "1"}
                )
                return response.status_code == 200
        except Exception as exc:
            logger.error("health_check failed: %s", exc)
            return False
