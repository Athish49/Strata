"""Task 6.1.2 — Find 'restates' links between clause pairs.

Finds pairs of clauses that "restate" the same regulatory obligation — one in
a procedure document and one in a register or template.  Uses parameter
matching + cosine similarity.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from app.company_ingest.index.embed import build_embedded_text, embed_texts
from app.company_ingest.link.resolve_refs import ClauseLink
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext

logger = logging.getLogger(__name__)

_MAX_GROUP_SIZE = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cited_sections(unit: ClauseUnit) -> list[str]:
    """Return list of normalized_key strings from unit.citations."""
    result = []
    for e in unit.citations:
        try:
            key = e.parsed.normalized_key
            if key:
                result.append(key)
        except AttributeError:
            pass
    return result


def _cosine(v1: list[float], v2: list[float]) -> float:
    """Dot product of two already-L2-normalised vectors == cosine similarity."""
    return sum(a * b for a, b in zip(v1, v2))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def find_restates_links(
    units: list[ClauseUnit],
    existing_links: list[ClauseLink],
    ctx: RunContext,
) -> list[ClauseLink]:
    """Find pairs of clauses that restate the same obligation.

    Returns new ClauseLink objects with link_type="restates".
    """
    # ------------------------------------------------------------------
    # Step 1: Group by parameter signature
    # ------------------------------------------------------------------
    # signature = (kind, round(value_num, 6), unit, day_type, qualifier)
    groups: dict[tuple, list[ClauseUnit]] = defaultdict(list)

    for unit in units:
        seen_sigs: set[tuple] = set()
        for entry in unit.parameters:
            if not getattr(entry, "verified", False):
                continue
            if getattr(entry, "value_num", None) is None:
                continue
            sig = (
                entry.kind,
                round(entry.value_num, 6),
                entry.unit,
                entry.day_type,
                entry.qualifier,
            )
            if sig not in seen_sigs:
                seen_sigs.add(sig)
                groups[sig].append(unit)

    # ------------------------------------------------------------------
    # Step 2: Cap groups
    # ------------------------------------------------------------------
    # Pre-build set of existing link edges (clause_id pairs, any direction)
    existing_edges: set[tuple[str, str]] = set()
    for lnk in existing_links:
        if lnk.from_clause_id and lnk.to_clause_id:
            existing_edges.add((lnk.from_clause_id, lnk.to_clause_id))
            existing_edges.add((lnk.to_clause_id, lnk.from_clause_id))

    # ------------------------------------------------------------------
    # Collect candidates: (signature, unit_A, unit_B)
    # ------------------------------------------------------------------
    # Track best confidence per directed pair for deduplication
    best: dict[tuple[str, str], tuple[float, str]] = {}  # (from, to) -> (conf, evidence)

    for sig, members in groups.items():
        if len(members) > _MAX_GROUP_SIZE:
            logger.warning(
                "restates_group_too_large: sig=%s members=%d — skipping",
                sig,
                len(members),
            )
            ctx.issue(
                "warning",
                stage="6.1.2_restates",
                code="restates_group_too_large",
                message=f"Parameter group has {len(members)} members (>{_MAX_GROUP_SIZE}); skipping",
                details={"signature": str(sig), "member_count": len(members)},
            )
            ctx.count("restates_groups_skipped")
            continue

        n = len(members)
        for i in range(n):
            for j in range(i + 1, n):
                unit_a = members[i]
                unit_b = members[j]

                if unit_a.clause_id == unit_b.clause_id:
                    continue

                # ----------------------------------------------------------
                # Step 3: Scope filter
                # ----------------------------------------------------------
                sections_a = set(_cited_sections(unit_a))
                sections_b = set(_cited_sections(unit_b))

                shared_sections = sections_a & sections_b
                cond1 = bool(shared_sections)

                no_citations_a = len(sections_a) == 0
                no_citations_b = len(sections_b) == 0
                same_doc = unit_a.doc_id == unit_b.doc_id
                connected = (
                    (unit_a.clause_id, unit_b.clause_id) in existing_edges
                    or (unit_b.clause_id, unit_a.clause_id) in existing_edges
                )
                cond2 = (no_citations_a or no_citations_b) and (same_doc or connected)

                if not cond1 and not cond2:
                    continue

                # ----------------------------------------------------------
                # Step 4: Embedding similarity
                # ----------------------------------------------------------
                text_a = build_embedded_text(unit_a)
                text_b = build_embedded_text(unit_b)

                if not text_a or not text_b:
                    continue

                vectors = embed_texts([text_a, text_b])
                if len(vectors) < 2:
                    continue

                cosine = _cosine(vectors[0], vectors[1])

                if cosine < 0.6:
                    continue

                evidence = f"parameter: {sig}"

                # Directed A→B
                key_ab = (unit_a.clause_id, unit_b.clause_id)
                if key_ab not in best or cosine > best[key_ab][0]:
                    best[key_ab] = (cosine, evidence)

                # Directed B→A
                key_ba = (unit_b.clause_id, unit_a.clause_id)
                if key_ba not in best or cosine > best[key_ba][0]:
                    best[key_ba] = (cosine, evidence)

    # ------------------------------------------------------------------
    # Build final links from best map
    # ------------------------------------------------------------------
    links: list[ClauseLink] = []
    for (from_id, to_id), (confidence, evidence) in best.items():
        links.append(
            ClauseLink(
                from_clause_id=from_id,
                to_clause_id=to_id,
                to_doc_id=None,
                link_type="restates",
                method="parameter_match",
                evidence=evidence,
                confidence=confidence,
            )
        )
        ctx.count("restates_links")

    # ------------------------------------------------------------------
    # Step 5: Confirm assessable for internal_procedure clauses
    # ------------------------------------------------------------------
    # Collect clause_ids that appear in restates links
    restates_from_ids: set[str] = {lnk.from_clause_id for lnk in links}
    restates_to_ids: set[str] = {lnk.to_clause_id for lnk in links if lnk.to_clause_id}
    restates_ids = restates_from_ids | restates_to_ids

    for unit in units:
        if unit.role == "internal_procedure":
            if unit.clause_id in restates_ids:
                unit.assessable = True

    return links
