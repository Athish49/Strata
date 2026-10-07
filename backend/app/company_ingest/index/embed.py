"""Task 6.2.1 — Dense embedding helpers for company clause indexing."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.config import settings
from app.company_ingest.parse.models import ClauseUnit

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer

_model: "_SentenceTransformer | None" = None


def _get_model() -> "_SentenceTransformer":
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        _model = SentenceTransformer(settings.EMBED_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using settings.EMBED_MODEL (all-MiniLM-L6-v2).

    Returns list of float vectors, one per input text.
    Batches in groups of 64 with retry on failure (3 retries, exponential backoff).
    """
    if not texts:
        return []

    model = _get_model()
    results: list[list[float]] = []
    batch_size = 64

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                encoded = model.encode(batch, normalize_embeddings=True)
                results.extend(encoded.tolist())
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError(
                f"embed_texts: failed after 3 retries on batch {i // batch_size}"
            ) from last_exc

    return results


def build_embedded_text(unit: ClauseUnit) -> str:
    """Build the embedded text for a ClauseUnit per SPEC §9 template.

    Template: "[heading_path joined with ' > '] | [text_norm truncated to ~2048 chars]"

    Returns empty string if the unit should NOT be embedded:
    - role == 'boilerplate'
    - section_kind == 'front_matter'
    - unit_kind == 'table_row' AND text_norm is blank
    """
    if unit.role == "boilerplate":
        return ""
    if unit.section_kind == "front_matter":
        return ""
    if unit.unit_kind == "table_row" and not unit.text_norm.strip():
        return ""

    prefix = " > ".join(unit.heading_path)
    body = unit.text_norm[:2048]
    return f"{prefix} | {body}"
