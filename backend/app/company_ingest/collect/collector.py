"""Task 2.1.1 — Corpus file collector.

Walks CORPUS_ROOT, applies the allowlist, detects profiles, computes SHA-256
digests and (optionally) uploads each allowed file to R2.
"""
from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.company_ingest.collect.allowlist import is_allowed
from app.company_ingest.constants import Profile
from app.company_ingest.run_context import RunContext
from app.config import settings


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------

@dataclass
class SourceFile:
    rel_path: str          # relative to CORPUS_ROOT.parent (includes 'corpus/' prefix)
    abs_path: Path
    sha256: str            # SHA-256 hex of file contents
    size: int              # bytes
    doc_id: str | None     # from corpus/docs/<DOC_ID>/…, or None for global files
    profile: Profile       # P1_PROSE, P2_REGISTER, P3_DATASET, P4_REFERENCE, RENDER


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_doc_id(rel_path: str) -> str | None:
    """Return the DOC_ID component for paths under corpus/docs/<DOC_ID>/."""
    parts = PurePosixPath(rel_path).parts
    if len(parts) >= 3 and parts[0] == "corpus" and parts[1] == "docs":
        return parts[2]
    return None


# Version extraction -----------------------------------------------------------

_RE_VERSION_FILENAME = re.compile(r"_v([^_]+)\.md$", re.IGNORECASE)
_RE_VERSION_FRONTMATTER = re.compile(r"(?m)^version\s*:\s*(.+)$", re.IGNORECASE)


def _version_from_filename(name: str) -> str | None:
    m = _RE_VERSION_FILENAME.search(name)
    return m.group(1).strip() if m else None


def _version_from_content(abs_path: Path) -> str | None:
    try:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
        m = _RE_VERSION_FRONTMATTER.search(text[:2000])
        if m:
            return m.group(1).strip()
    except OSError:
        pass
    return None


def _get_p1_version(abs_path: Path) -> str:
    v = _version_from_filename(abs_path.name)
    if v:
        return v
    v = _version_from_content(abs_path)
    if v:
        return v
    return "unknown"


# P2 detection ----------------------------------------------------------------

_RE_OBL = re.compile(r"^OBL-\d{4}-\d{4}$")
_RE_EVT = re.compile(r"^EVT-\d{4}-\d{4}$")
_RE_RRS = re.compile(r"^RRS-[A-Z]+-\d+$")


def _detect_p2(abs_path: Path) -> bool:
    """Return True if this CSV is a P2 register file."""
    try:
        with abs_path.open(encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if not header or not header[0].strip().endswith("_id"):
                return False
            first_row = next(reader, None)
            if not first_row:
                return False
            val = first_row[0].strip()
            return bool(_RE_OBL.match(val) or _RE_EVT.match(val) or _RE_RRS.match(val))
    except OSError:
        return False


# Profile detection -----------------------------------------------------------

def _detect_profile(rel_path: str, abs_path: Path) -> Profile:
    """Assign a Profile to an allowed file (priority order matches spec)."""
    parts = PurePosixPath(rel_path).parts  # e.g. ('corpus','docs','RPL-…','render','x.pdf')

    # 1. RENDER: 'render' appears as a directory component (not the filename)
    if "render" in parts[:-1]:
        return Profile.RENDER

    # 2/3. Under corpus/_global/
    if len(parts) >= 2 and parts[0] == "corpus" and parts[1] == "_global":
        if len(parts) >= 3 and parts[2] == "ops":
            # P3 for CSVs, P4 for everything else
            if abs_path.suffix.lower() == ".csv":
                return Profile.P3_DATASET
            return Profile.P4_REFERENCE
        return Profile.P4_REFERENCE

    # 4. P1: .md directly under corpus/docs/<DOC_ID>/ (exactly 4 parts)
    if (
        len(parts) == 4
        and parts[0] == "corpus"
        and parts[1] == "docs"
        and abs_path.suffix.lower() == ".md"
    ):
        return Profile.P1_PROSE

    # 5. CSV under corpus/docs/<DOC_ID>/data/
    if (
        len(parts) == 5
        and parts[0] == "corpus"
        and parts[1] == "docs"
        and parts[3] == "data"
        and abs_path.suffix.lower() == ".csv"
    ):
        return Profile.P2_REGISTER if _detect_p2(abs_path) else Profile.P3_DATASET

    # 6. Fallback
    return Profile.P3_DATASET


# R2 key construction ---------------------------------------------------------

def _content_type(abs_path: Path) -> str:
    suffix = abs_path.suffix.lower()
    return {
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".json": "application/json",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
        ".py": "text/x-python",
        ".txt": "text/plain",
    }.get(suffix, "application/octet-stream")


def _r2_key_for(
    sf: SourceFile,
    version: str,
    run_id: str,
    company_id: str,
) -> str | None:
    """Return the R2 object key for *sf*, or None if no key applies."""
    from app.company_ingest.store.r2_keys import (
        global_file_key,
        raw_dataset_key,
        raw_doc_key,
        raw_render_key,
    )

    parts = PurePosixPath(sf.rel_path).parts

    if sf.profile == Profile.P1_PROSE:
        assert sf.doc_id is not None
        return raw_doc_key(company_id, sf.doc_id, version, sf.abs_path.name)

    if sf.profile in (Profile.P2_REGISTER, Profile.P3_DATASET):
        if sf.doc_id is not None:
            name_no_ext = sf.abs_path.stem
            return raw_dataset_key(company_id, sf.doc_id, version, name_no_ext)
        # Global ops CSV
        rel_within_global = "/".join(parts[2:])  # e.g. ops/circuits_master.csv
        return global_file_key(company_id, run_id, rel_within_global)

    if sf.profile == Profile.RENDER:
        if sf.doc_id is not None:
            return raw_render_key(company_id, sf.doc_id, version, sf.abs_path.name)
        # Global render file
        rel_within_global = "/".join(parts[2:])
        return global_file_key(company_id, run_id, rel_within_global)

    if sf.profile == Profile.P4_REFERENCE:
        rel_within_global = "/".join(parts[2:])
        return global_file_key(company_id, run_id, rel_within_global)

    return None


# ---------------------------------------------------------------------------
# Public collect()
# ---------------------------------------------------------------------------

_MAX_DENIED_ISSUES = 50


def collect(ctx: RunContext, upload_r2: bool = True) -> list[SourceFile]:
    """Walk CORPUS_ROOT, apply allowlist, detect profiles, return SourceFiles.

    Parameters
    ----------
    ctx:
        Active RunContext; stats and issues are mutated in place.
    upload_r2:
        When True (default), each allowed file is uploaded to R2 using
        best-effort semantics (failures are logged as issues, not raised).
    """
    corpus_root = Path(settings.CORPUS_ROOT)
    corpus_parent = corpus_root.parent  # rel_paths will include 'corpus/' prefix

    # ------------------------------------------------------------------ walk
    # Pass 1: collect allowed files with basic metadata.
    allowed_entries: list[tuple[str, Path]] = []  # (rel_path, abs_path)
    denied_count = 0

    for abs_path in sorted(corpus_root.rglob("*")):
        if not abs_path.is_file():
            continue

        rel_path = abs_path.relative_to(corpus_parent).as_posix()

        if not is_allowed(rel_path):
            denied_count += 1
            ctx.count("denied_paths")
            if denied_count <= _MAX_DENIED_ISSUES:
                ctx.issue(
                    "info",
                    "collect",
                    "denied_path",
                    f"Path denied by allowlist: {rel_path}",
                    path=rel_path,
                )
            continue

        allowed_entries.append((rel_path, abs_path))

    # ------------------------------------------------------------------ pass 2: versions
    # Build doc_id → version map from P1 files so P2/P3 can inherit them.
    doc_version_map: dict[str, str] = {}
    for rel_path, abs_path in allowed_entries:
        parts = PurePosixPath(rel_path).parts
        if (
            len(parts) == 4
            and parts[0] == "corpus"
            and parts[1] == "docs"
            and abs_path.suffix.lower() == ".md"
        ):
            doc_id = parts[2]
            doc_version_map[doc_id] = _get_p1_version(abs_path)

    # ------------------------------------------------------------------ pass 3: SourceFile objects
    result: list[SourceFile] = []
    run_id = str(ctx.run_id)
    company_id = ctx.company_id or settings.COMPANY_ID

    for rel_path, abs_path in allowed_entries:
        data = abs_path.read_bytes()
        digest = _sha256(data)
        size = len(data)
        doc_id = _extract_doc_id(rel_path)
        profile = _detect_profile(rel_path, abs_path)

        sf = SourceFile(
            rel_path=rel_path,
            abs_path=abs_path,
            sha256=digest,
            size=size,
            doc_id=doc_id,
            profile=profile,
        )
        result.append(sf)

        if not upload_r2:
            continue

        # Resolve version for this file
        if profile == Profile.P1_PROSE:
            version = _get_p1_version(abs_path)
        elif doc_id is not None:
            version = doc_version_map.get(doc_id, "unknown")
        else:
            version = "unknown"

        key = _r2_key_for(sf, version, run_id, company_id)
        if key is None:
            continue

        try:
            from app.company_ingest.store import r2

            r2.put_bytes(
                key=key,
                data=data,
                metadata={
                    "sha256": digest,
                    "content_type": _content_type(abs_path),
                    "doc_id": doc_id or "",
                    "version": version,
                    "profile": str(profile),
                },
                content_type=_content_type(abs_path),
            )
        except Exception as exc:  # best-effort
            ctx.issue(
                "warning",
                "collect",
                "r2_upload_failed",
                f"R2 upload failed for {rel_path}: {exc}",
                path=rel_path,
                doc_id=doc_id,
            )

    return result
