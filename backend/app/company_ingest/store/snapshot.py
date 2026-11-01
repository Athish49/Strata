"""Task 8.1.2 / 5.8 — Clause snapshot writer.

Serializes a list of ClauseUnit objects to JSONL format and writes to R2.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.company_ingest.parse.models import ClauseUnit
    from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_citation(entry) -> dict:
    """Serialize a CitationEntry to a plain dict."""
    parsed = getattr(entry, "parsed", None)
    result = {
        "context": entry.context,
        "span_start": entry.span_start,
        "span_end": entry.span_end,
        "resolution_status": entry.resolution_status,
        "code_section_id": entry.code_section_id,
        "in_knowledge_base": entry.in_knowledge_base,
        "normalized_key": parsed.normalized_key if parsed else None,
        "rule_key": parsed.rule_key if parsed else None,
        "source_system": parsed.source_system if parsed else None,
    }
    return result


def _serialize_parameter(entry) -> dict:
    """Serialize a ParameterEntry to a plain dict."""
    return {
        "kind": entry.kind,
        "unit": entry.unit,
        "value_text": entry.value_text,
        "value_num": entry.value_num,
        "value_source": entry.value_source,
        "qualifier": entry.qualifier,
        "day_type": entry.day_type,
        "span_start": entry.span_start,
        "span_end": entry.span_end,
        "method": entry.method,
        "verified": entry.verified,
    }


def _serialize_ref(entry) -> dict:
    """Serialize a RefEntry to a plain dict."""
    return {
        "ref_type": entry.ref_type,
        "raw": entry.raw,
        "span_start": entry.span_start,
        "span_end": entry.span_end,
        "target_hint": entry.target_hint,
    }


def _unit_to_dict(unit: "ClauseUnit") -> dict:
    """Convert a ClauseUnit to a serializable dict (excluding terms)."""
    return {
        "version_id": unit.version_id,
        "doc_id": unit.doc_id,
        "clause_id": unit.clause_id,
        "local_id": unit.local_id,
        "parent_clause_id": unit.parent_clause_id,
        "unit_kind": unit.unit_kind,
        "heading_path": unit.heading_path,
        "section_kind": unit.section_kind,
        "ordinal": unit.ordinal,
        "char_start": unit.char_start,
        "char_end": unit.char_end,
        "line_start": unit.line_start,
        "text_raw": unit.text_raw,
        "text_norm": unit.text_norm,
        "text_sha256": unit.text_sha256,
        "role": unit.role,
        "role_method": unit.role_method,
        "assessable": unit.assessable,
        "normalized_statement": unit.normalized_statement,
        "topic_terms": unit.topic_terms,
        "citations": [_serialize_citation(c) for c in unit.citations],
        "parameters": [_serialize_parameter(p) for p in unit.parameters],
        "refs": [_serialize_ref(r) for r in unit.refs],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_clause_snapshot(units: list["ClauseUnit"]) -> str:
    """
    Serialize all clauses to JSONL format (one JSON object per line).

    Objects are sorted by clause_id. Each object includes: version_id,
    doc_id, clause_id, local_id, parent_clause_id, unit_kind, heading_path,
    section_kind, ordinal, char_start, char_end, line_start, text_raw,
    text_norm, text_sha256, role, role_method, assessable,
    normalized_statement, topic_terms, citations (list of dicts),
    parameters (list of dicts), refs (list of dicts).

    The ``terms`` field is excluded from the snapshot (term data is in its
    own table).
    """
    sorted_units = sorted(units, key=lambda u: u.clause_id)
    lines = [
        json.dumps(_unit_to_dict(u), default=str)
        for u in sorted_units
    ]
    return "\n".join(lines)


def write_clause_snapshot(
    units: list["ClauseUnit"],
    doc_id: str,
    version_id: str,
    company_id: str,
    r2_client,
    ctx: "RunContext",
    force: bool = True,
) -> str:
    """Write clauses.jsonl to R2, keyed by the REAL ``version_id``. Returns the key.

    The key is ``company/{company_id}/derived/{doc_id}/{version_id}/clauses.jsonl``,
    so every version of a document gets its own object (the pre-v2 caller passed
    the literal ``"v1"``, so every version collided on one key).  A non-UUID
    ``version_id`` is rejected to stop that regression from coming back.

    The snapshot is derived data, regenerable from Neon + the raw bytes, so
    ``force`` defaults to True: a retry/re-ingest of the same version whose
    content changed (new LLM output, segmenter fix) overwrites instead of
    tripping the R2 write-once guard.  If a caller explicitly passes
    ``force=False`` and the content differs, the conflict is recorded on
    ``ctx`` as a warning and the existing key is returned — it never raises
    ``ValueError`` and so can never fail the whole ingest run.
    """
    from app.company_ingest.store.r2_keys import derived_clauses_key

    try:
        version_id = str(uuid.UUID(str(version_id)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(
            f"write_clause_snapshot needs the real version_id (a uuid), got {version_id!r}"
        ) from None

    key = derived_clauses_key(company_id, doc_id, version_id)
    jsonl = build_clause_snapshot(units)
    data = jsonl.encode("utf-8")

    try:
        r2_client.put_bytes(
            key,
            data,
            {
                "content_type": "application/x-ndjson",
                "doc_id": doc_id,
                "version": version_id,
                "profile": "clauses",
            },
            "application/x-ndjson",
            force=force,
        )
    except ValueError as exc:  # write-once conflict (only reachable with force=False)
        ctx.issue(
            "warning",
            "snapshot",
            "snapshot_write_once_conflict",
            f"clause snapshot {key} exists with different content and force=False; "
            f"kept the existing object ({exc})",
            doc_id=doc_id,
        )
    return key
