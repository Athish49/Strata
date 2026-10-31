"""Task 4.2 — extractor contract (TDD §3).

The contract is **Markdown out**: ``parse/markdown_segmenter.py`` derives all
document structure from Markdown (``_HEADING_RE`` on ``#`` markers and pipe
tables), so every extractor must emit Markdown rather than flat text.  This is
what lets the existing segmentation / enrichment / indexing pipeline be reused
unchanged for uploaded customer documents.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ExtractedDocument:
    """The result of extracting one uploaded file.

    Attributes
    ----------
    markdown:
        Markdown that satisfies the ``markdown_segmenter`` contract.  This is
        the text that task 4.1 canonicalizes and hashes, so it must contain
        **no** identifiers derived from the filename or the declared ``doc_id``
        — otherwise the same content uploaded under a different name would hash
        differently and the ``current_content_hash`` uniqueness check would
        stop catching re-saved duplicates.
    method:
        Library and version that produced the Markdown, e.g.
        ``"python-docx/1.2.0"``.
    page_count:
        Page count when the format exposes one.  DOCX does not (pagination is
        decided by the renderer), so it is ``None`` there.
    confidence:
        Optional 0..1 extraction-confidence score.  Style-driven DOCX
        extraction is deterministic, so it reports ``1.0``; a future OCR or
        vendor extractor would report something lower.
    """

    markdown: str
    method: str
    page_count: int | None = None
    confidence: float | None = None


@runtime_checkable
class DocumentExtractor(Protocol):
    """Structural type for an extractor.

    Adding a vendor later is one new class plus one registry entry; see
    ``app.company_ingest.extract.register_extractor``.
    """

    content_types: frozenset[str]

    def extract(self, raw: bytes, filename: str) -> ExtractedDocument: ...
