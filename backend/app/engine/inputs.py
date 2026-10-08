"""Stage 0 input builders: ChangeInput lists for kb, baseline and whatif runs (engine_spec.md section 0).

Read-only. Snapshot dates are discovered per source_system (S1 = min, S2 = max), never hardcoded.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.schemas import ChangeInput

logger = logging.getLogger(__name__)

_SNAPSHOTS_SQL = text("""
    SELECT source_system, MIN(snapshot_date) AS s1_date, MAX(snapshot_date) AS s2_date
    FROM public.code_sections
    GROUP BY source_system
    ORDER BY source_system
""")

_S2_ROWS_SQL = text("""
    SELECT s2.id AS s2_id, s2.citation AS s2_citation, s2.body_text AS s2_text,
           s2.status AS s2_status, s2.heading AS s2_heading,
           s2.amendment_source AS s2_amendment_source, s2.prior_version_id AS prior_version_id,
           s1.id AS s1_id, s1.body_text AS s1_text, s1.status AS s1_status,
           s1.snapshot_date AS s1_snapshot_date
    FROM public.code_sections s2
    LEFT JOIN public.code_sections s1 ON s1.id = s2.prior_version_id
    WHERE s2.source_system = :source_system AND s2.snapshot_date = :s2_date
    ORDER BY s2.citation, s2.id
""")

_S1_ROW_SQL = text("""
    SELECT id, source_system, citation, heading, body_text, status, amendment_source
    FROM public.code_sections
    WHERE id = :id
""")


async def snapshot_pairs(session: AsyncSession) -> dict[str, tuple[Any, Any]]:
    """{source_system: (s1_date, s2_date)}; systems with a single snapshot are omitted."""
    rows = (await session.execute(_SNAPSHOTS_SQL)).mappings().all()
    return {r["source_system"]: (r["s1_date"], r["s2_date"]) for r in rows if r["s1_date"] != r["s2_date"]}


async def build_kb_inputs(session: AsyncSession) -> list[ChangeInput]:
    """One ChangeInput per S2 row: a pair when prior_version_id is set, else a new section."""
    out: list[ChangeInput] = []
    for source_system, (s1_date, s2_date) in (await snapshot_pairs(session)).items():
        rows = (await session.execute(
            _S2_ROWS_SQL, {"source_system": source_system, "s2_date": s2_date}
        )).mappings().all()
        for r in rows:
            has_prior = r["prior_version_id"] is not None
            if has_prior and r["s1_id"] is None:
                logger.warning("dangling prior_version_id %s on section %s", r["prior_version_id"], r["s2_id"])
            elif has_prior and r["s1_snapshot_date"] != s1_date:
                logger.warning("section %s prior_version_id points to snapshot %s, not S1 %s",
                               r["s2_id"], r["s1_snapshot_date"], s1_date)
            paired = r["s1_id"] is not None
            out.append(ChangeInput(
                origin="kb",
                source_system=source_system,
                citation=r["s2_citation"],
                s1_section_id=r["s1_id"] if paired else None,
                s2_section_id=r["s2_id"],
                s1_text=r["s1_text"] if paired else None,
                s2_text=r["s2_text"],
                s1_status=r["s1_status"] if paired else None,
                s2_status=r["s2_status"],
                heading=r["s2_heading"],
                amendment_source=r["s2_amendment_source"],
            ))
    out.sort(key=lambda c: (c.source_system, c.citation, c.s2_section_id or 0))
    return out


def build_baseline_inputs() -> list[ChangeInput]:
    """Baseline compares S1 with S1: no changes."""
    return []


def _get(scenario: Any, key: str) -> Any:
    if isinstance(scenario, Mapping):
        return scenario.get(key)
    return getattr(scenario, key, None)


async def build_whatif_inputs(session: AsyncSession, scenario: Any) -> list[ChangeInput]:
    """One ChangeInput from a whatif scenario (s1_section_id, edit_kind, edited_text)."""
    s1_id = _get(scenario, "s1_section_id")
    edit_kind = _get(scenario, "edit_kind")
    edited_text = _get(scenario, "edited_text")
    if edit_kind not in ("text_edit", "repeal"):
        raise ValueError(f"unknown edit_kind: {edit_kind!r}")
    row = (await session.execute(_S1_ROW_SQL, {"id": s1_id})).mappings().first()
    if row is None:
        raise ValueError(f"S1 section not found: {s1_id}")
    if edit_kind == "text_edit":
        s2_text, s2_status = edited_text, row["status"]
    else:
        s2_text, s2_status = None, "repealed"
    return [ChangeInput(
        origin="whatif",
        source_system=row["source_system"],
        citation=row["citation"],
        s1_section_id=row["id"],
        s2_section_id=None,
        s1_text=row["body_text"],
        s2_text=s2_text,
        s1_status=row["status"],
        s2_status=s2_status,
        heading=row["heading"],
        amendment_source=row["amendment_source"],
    )]
