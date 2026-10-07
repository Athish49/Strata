"""Task 2.2.1 — Document registration: parse front matter and upsert DB rows.

For each P1 SourceFile:
  - Parse front matter with split_front_matter()
  - Fall back to register_entries for any missing fields
  - Upsert company_documents
  - Insert document_versions row with ingest_status='pending'
  - Cross-check with register_entries and warn on mismatches
  - Skip (mark 'unchanged') when sha256 + ingest_status='ingested' are unchanged
    unless ctx.rebuild is set

Returns: {doc_id: (front_matter, body_text, body_char_offset)}
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.company_ingest.collect.collector import SourceFile
from app.company_ingest.constants import DocClass, Profile
from app.company_ingest.ids import stable_uuid
from app.company_ingest.parse.front_matter import FrontMatter, split_front_matter
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# RegisterEntry — mirrors document_register.csv columns
# ---------------------------------------------------------------------------

@dataclass
class RegisterEntry:
    doc_id: str
    title: str | None = None
    vertical: str | None = None
    version: str | None = None
    status: str | None = None
    effective_date: str | None = None
    approved_date: str | None = None
    law_as_of: str | None = None
    owner_id: str | None = None
    reviewer_id: str | None = None
    approver_id: str | None = None
    review_cycle: str | None = None
    next_review_date: str | None = None
    supersedes_version: str | None = None
    supersedes_date: str | None = None
    file_path: str | None = None
    render_path: str | None = None
    record_series_ids: str | None = None
    regulatory_basis_sections: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Provisional doc_class detection
# ---------------------------------------------------------------------------

_RE_SHEET_MARKER = re.compile(r'<!--\s*sheet\s*:', re.IGNORECASE)
_RE_CLAUSE_MARKER = re.compile(r'<!--\s*clause\s*:', re.IGNORECASE)
_RE_DOCID_CLAUSE_MARKER = re.compile(r'<!--\s*RPL-[A-Z0-9-]+:\S+\s*-->')


def _provisional_doc_class(md_text: str) -> str | None:
    """Determine a provisional DocClass from structural markers in the document body."""
    if _RE_SHEET_MARKER.search(md_text):
        return DocClass.TARIFF
    if _RE_CLAUSE_MARKER.search(md_text):
        return DocClass.PROCEDURE
    return None


# ---------------------------------------------------------------------------
# Field fallback helpers
# ---------------------------------------------------------------------------

def _apply_register_fallback(fm: FrontMatter, entry: RegisterEntry | None) -> FrontMatter:
    """Fill missing FrontMatter fields from a RegisterEntry."""
    if entry is None:
        return fm
    if fm.title is None:
        fm.title = entry.title
    if fm.version is None:
        fm.version = entry.version
    if fm.status is None:
        fm.status = entry.status
    if fm.effective_date is None:
        fm.effective_date = entry.effective_date
    if fm.approved_date is None:
        fm.approved_date = entry.approved_date
    if fm.law_as_of is None:
        fm.law_as_of = entry.law_as_of
    if fm.owner_id is None:
        fm.owner_id = entry.owner_id
    if fm.reviewer_id is None:
        fm.reviewer_id = entry.reviewer_id
    if fm.approver_id is None:
        fm.approver_id = entry.approver_id
    if fm.review_cycle is None:
        fm.review_cycle = entry.review_cycle
    if fm.next_review is None:
        fm.next_review = entry.next_review_date
    if fm.supersedes is None and entry.supersedes_version:
        parts = [entry.supersedes_version]
        if entry.supersedes_date:
            parts.append(f"({entry.supersedes_date})")
        fm.supersedes = " ".join(parts)
    if fm.vertical is None:
        fm.vertical = entry.vertical
    return fm


def _cross_check(
    doc_id: str,
    fm: FrontMatter,
    entry: RegisterEntry | None,
    ctx: RunContext,
) -> None:
    """Warn on mismatches between parsed front matter and register entry."""
    if entry is None:
        return

    def _warn(field: str, fm_val: str | None, reg_val: str | None) -> None:
        ctx.issue(
            "warning",
            "register_docs",
            "fm_register_mismatch",
            (
                f"doc_id={doc_id}: front-matter {field!r} ({fm_val!r}) "
                f"differs from register ({reg_val!r})"
            ),
            doc_id=doc_id,
        )

    # title
    if fm.title and entry.title and fm.title.strip() != entry.title.strip():
        _warn("title", fm.title, entry.title)

    # version
    if fm.version and entry.version and str(fm.version).strip() != str(entry.version).strip():
        _warn("version", fm.version, entry.version)

    # effective_date
    if fm.effective_date and entry.effective_date:
        fm_d = str(fm.effective_date).strip()
        reg_d = str(entry.effective_date).strip()
        if fm_d != reg_d:
            _warn("effective_date", fm_d, reg_d)

    # owner_id
    if fm.owner_id and entry.owner_id and fm.owner_id != entry.owner_id:
        _warn("owner_id", fm.owner_id, entry.owner_id)

    # reviewer_id
    if fm.reviewer_id and entry.reviewer_id and fm.reviewer_id != entry.reviewer_id:
        _warn("reviewer_id", fm.reviewer_id, entry.reviewer_id)

    # approver_id — skip if either is None (two-signature docs)
    if fm.approver_id and entry.approver_id and fm.approver_id != entry.approver_id:
        _warn("approver_id", fm.approver_id, entry.approver_id)


# ---------------------------------------------------------------------------
# R2 key helper
# ---------------------------------------------------------------------------

def _r2_key_for_source(sf: SourceFile, version: str, company_id: str) -> str | None:
    """Compute the R2 raw doc key for a P1 SourceFile."""
    if sf.doc_id is None:
        return None
    from app.company_ingest.store.r2_keys import raw_doc_key
    return raw_doc_key(company_id, sf.doc_id, version, sf.abs_path.name)


# ---------------------------------------------------------------------------
# Main register_documents()
# ---------------------------------------------------------------------------

async def register_documents(
    sources: list[SourceFile],
    register_entries: list[RegisterEntry],
    session: AsyncSession,
    company_id: str,
    ctx: RunContext,
) -> dict[str, tuple[FrontMatter, str, int]]:
    """Register P1 prose documents in the database.

    For each P1 SourceFile:
      - Parse front matter
      - Fall back to register_entries for missing fields
      - Upsert company_documents
      - Insert document_versions with ingest_status='pending'
      - Skip if sha256 unchanged and ingest_status='ingested' (unless ctx.rebuild)

    Returns:
        {doc_id: (front_matter, body_text, body_char_offset)} for downstream segmentation
    """
    # Build a quick lookup from doc_id → RegisterEntry
    entry_map: dict[str, RegisterEntry] = {e.doc_id: e for e in (register_entries or [])}

    result: dict[str, tuple[FrontMatter, str, int]] = {}

    p1_sources = [sf for sf in sources if sf.profile == Profile.P1_PROSE and sf.doc_id]

    for sf in p1_sources:
        doc_id = sf.doc_id  # not None — filtered above
        assert doc_id is not None

        # Read file content
        try:
            md_text = sf.abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            ctx.issue(
                "error",
                "register_docs",
                "read_failed",
                f"Failed to read {sf.abs_path}: {exc}",
                doc_id=doc_id,
            )
            continue

        # Parse front matter
        try:
            fm, body_text, body_offset = split_front_matter(md_text, doc_id)
        except Exception as exc:
            ctx.issue(
                "error",
                "register_docs",
                "parse_failed",
                f"Front-matter parse failed for {doc_id}: {exc}",
                doc_id=doc_id,
            )
            fm = FrontMatter(doc_id=doc_id)
            body_text = md_text
            body_offset = 0

        # Apply register fallback for missing fields
        entry = entry_map.get(doc_id)
        fm = _apply_register_fallback(fm, entry)

        # Ensure doc_id is set
        if not fm.doc_id:
            fm.doc_id = doc_id

        # Cross-check with register
        _cross_check(doc_id, fm, entry, ctx)

        # Determine version
        version = fm.version or "unknown"

        # Compute version_id
        version_id: uuid.UUID = stable_uuid(company_id, doc_id, version)

        # Determine provisional doc_class
        doc_class = _provisional_doc_class(md_text)

        # Check for unchanged: existing row with same sha256 and ingest_status='ingested'
        if not ctx.rebuild:
            try:
                row = await session.execute(
                    text(
                        """
                        SELECT ingest_status, file_sha256
                        FROM company.document_versions
                        WHERE version_id = :vid
                        LIMIT 1
                        """
                    ),
                    {"vid": str(version_id)},
                )
                existing = row.fetchone()
                if (
                    existing is not None
                    and existing.ingest_status == "ingested"
                    and existing.file_sha256 == sf.sha256
                ):
                    ctx.count("unchanged")
                    ctx.issue(
                        "info",
                        "register_docs",
                        "unchanged",
                        f"Skipping {doc_id} v{version}: sha256 unchanged and already ingested",
                        doc_id=doc_id,
                    )
                    # Still return it for downstream use
                    result[doc_id] = (fm, body_text, body_offset)
                    continue
            except Exception:
                pass  # DB not available or schema not yet created — proceed with upsert

        # Compute R2 key
        source_r2_key = _r2_key_for_source(sf, version, company_id)

        # Upsert company_documents
        try:
            await session.execute(
                text(
                    """
                    INSERT INTO company.company_documents
                        (company_id, doc_id, title, doc_class, vertical,
                         owner_id, reviewer_id, approver_id, review_cycle, current_version_id)
                    VALUES
                        (:company_id, :doc_id, :title, :doc_class, :vertical,
                         :owner_id, :reviewer_id, :approver_id, :review_cycle, :version_id)
                    ON CONFLICT (company_id, doc_id) DO UPDATE SET
                        title          = EXCLUDED.title,
                        doc_class      = COALESCE(EXCLUDED.doc_class, company_documents.doc_class),
                        vertical       = COALESCE(EXCLUDED.vertical, company_documents.vertical),
                        owner_id       = COALESCE(EXCLUDED.owner_id, company_documents.owner_id),
                        reviewer_id    = COALESCE(EXCLUDED.reviewer_id, company_documents.reviewer_id),
                        approver_id    = EXCLUDED.approver_id,
                        review_cycle   = COALESCE(EXCLUDED.review_cycle, company_documents.review_cycle),
                        current_version_id = EXCLUDED.current_version_id
                    """
                ),
                {
                    "company_id": company_id,
                    "doc_id": doc_id,
                    "title": fm.title,
                    "doc_class": doc_class,
                    "vertical": fm.vertical,
                    "owner_id": fm.owner_id,
                    "reviewer_id": fm.reviewer_id,
                    "approver_id": fm.approver_id,
                    "review_cycle": fm.review_cycle,
                    "version_id": str(version_id),
                },
            )
        except Exception as exc:
            ctx.issue(
                "error",
                "register_docs",
                "upsert_document_failed",
                f"Failed to upsert company_documents for {doc_id}: {exc}",
                doc_id=doc_id,
            )

        # Insert document_versions
        try:
            await session.execute(
                text(
                    """
                    INSERT INTO company.document_versions
                        (version_id, company_id, doc_id, version, status,
                         effective_date, approved_date, law_as_of, next_review,
                         supersedes, classification, regulatory_basis,
                         source_r2_key, file_sha256, ingest_status, ingest_run_id)
                    VALUES
                        (:version_id, :company_id, :doc_id, :version, :status,
                         :effective_date, :approved_date, :law_as_of, :next_review,
                         :supersedes, :classification, :regulatory_basis,
                         :source_r2_key, :file_sha256, 'pending', :run_id)
                    ON CONFLICT (version_id) DO UPDATE SET
                        status           = EXCLUDED.status,
                        effective_date   = EXCLUDED.effective_date,
                        approved_date    = EXCLUDED.approved_date,
                        law_as_of        = EXCLUDED.law_as_of,
                        next_review      = EXCLUDED.next_review,
                        supersedes       = EXCLUDED.supersedes,
                        classification   = EXCLUDED.classification,
                        regulatory_basis = EXCLUDED.regulatory_basis,
                        source_r2_key    = EXCLUDED.source_r2_key,
                        file_sha256      = EXCLUDED.file_sha256,
                        ingest_status    = CASE
                            WHEN company.document_versions.ingest_status = 'ingested'
                             AND :rebuild = FALSE
                            THEN 'ingested'
                            ELSE 'pending'
                        END,
                        ingest_run_id    = EXCLUDED.ingest_run_id
                    """
                ),
                {
                    "version_id": str(version_id),
                    "company_id": company_id,
                    "doc_id": doc_id,
                    "version": version,
                    "status": fm.status,
                    "effective_date": fm.effective_date,
                    "approved_date": fm.approved_date,
                    "law_as_of": fm.law_as_of,
                    "next_review": fm.next_review,
                    "supersedes": fm.supersedes,
                    "classification": fm.classification,
                    "regulatory_basis": fm.regulatory_basis or [],
                    "source_r2_key": source_r2_key,
                    "file_sha256": sf.sha256,
                    "run_id": str(ctx.run_id),
                    "rebuild": ctx.rebuild,
                },
            )
            await session.commit()
            ctx.count("documents_registered")
        except Exception as exc:
            await session.rollback()
            ctx.issue(
                "error",
                "register_docs",
                "insert_version_failed",
                f"Failed to insert document_versions for {doc_id}: {exc}",
                doc_id=doc_id,
            )

        result[doc_id] = (fm, body_text, body_offset)

    return result
