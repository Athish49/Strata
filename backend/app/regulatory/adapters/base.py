import hashlib
from abc import ABC, abstractmethod
from typing import Union

from app.regulatory.models.code_section import CodeSection
from app.regulatory.models.regulatory_action import RegulatoryAction
from app.services.storage import upload_to_r2


class SourceAdapter(ABC):
    source_system: str  # e.g. "cfr", "federal_register"

    @abstractmethod
    async def get_sync_cursor(self, db) -> dict:
        """Return the last-pulled state for this source from sync_state table."""
        ...

    @abstractmethod
    async def poll(self, cursor: dict) -> list[dict]:
        """Fetch raw records from the source since the given cursor. Returns raw dicts."""
        ...

    @abstractmethod
    def normalize(self, raw: dict) -> Union[dict, None]:
        """Normalize a raw record into a CodeSection or RegulatoryAction dict. Returns None to skip."""
        ...

    @abstractmethod
    async def update_sync_cursor(self, db, new_cursor: dict) -> None:
        """Persist the new cursor to sync_state after a successful batch."""
        ...

    async def health_check(self) -> bool:
        """Check if the source is accessible. Override for custom health checks."""
        return True


def compute_content_hash(text: str) -> str:
    """SHA-256 hash of text. Used as change-detection key for CodeSection records."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def upload_raw_to_r2(source_system: str, key: str, data: bytes, content_type: str = "text/plain") -> None:
    """Upload raw source data to R2 for audit trail. Key should be relative path like 'ecfr/2025-01-01/title-18-part-35.xml'."""
    full_key = f"raw-sources/{source_system}/{key}"
    upload_to_r2(full_key, data, content_type)
