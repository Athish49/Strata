"""Task 4.2 — extraction package and content-type registry.

Adding a structured-extraction vendor later is one new class plus one
``register_extractor`` call; the API layer only ever asks the registry.
"""
from __future__ import annotations

from app.company_ingest.extract.base import DocumentExtractor, ExtractedDocument
from app.company_ingest.extract.docx import (
    DOCX_CONTENT_TYPE,
    DocxExtractor,
    anchor_clauses,
    marker_doc_id_supported,
)

_REGISTRY: dict[str, DocumentExtractor] = {}


def register_extractor(extractor: DocumentExtractor) -> None:
    """Register *extractor* for each of its declared content types."""
    for content_type in extractor.content_types:
        _REGISTRY[content_type.lower()] = extractor


def extractor_for(content_type: str | None) -> DocumentExtractor | None:
    """Return the extractor for *content_type*, or ``None`` if unsupported.

    ``None`` is the 415 case: PDF is deliberately not registered (see
    ``docx.py`` module docstring).
    """
    if not content_type:
        return None
    # Tolerate "...document; charset=utf-8" style headers.
    key = content_type.split(";")[0].strip().lower()
    return _REGISTRY.get(key)


def supported_content_types() -> frozenset[str]:
    return frozenset(_REGISTRY)


register_extractor(DocxExtractor())

__all__ = [
    "DOCX_CONTENT_TYPE",
    "DocumentExtractor",
    "DocxExtractor",
    "ExtractedDocument",
    "anchor_clauses",
    "extractor_for",
    "marker_doc_id_supported",
    "register_extractor",
    "supported_content_types",
]
