"""
delta.py — Stage 1 (Delta): classify every change, diff it, date it, place it against the
company footprint and set the Stage 1 disposition (engine_spec.md sections 1.2-1.6).

``classify_change`` is pure.  ``run_stage1`` adds the DB reads (FR dates, S1 corpus for
renumber detection, clause ids for the "cleared with proof" candidates);
``persist_stage1`` writes ``engine.change_records`` and ``engine.candidates``.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.company_ingest.enrich.citations_grammar import find_citation_spans
from app.engine.config import engine_settings
from app.engine.dates import compute_publication, lookup_fr_dates_batch
from app.engine.diffing import (
    all_changed_inside_spans,
    changed_tokens,
    diff_segments,
    only_punct,
)
from app.engine.footprint import Footprint, rule_key
from app.engine.schemas import NOISE_CLASSES, ChangeInput
from app.engine.textnorm import normalize, strip_metadata

logger = logging.getLogger(__name__)

SHINGLE_N = 5
_WORD_RE = re.compile(r"\w+")
_REPEAL_STATUSES = {"repealed", "expired"}

CLASS_EXPLANATIONS = {
    "cosmetic": "Only formatting differs; the normalized text is identical.",
    "metadata_only": "Only non-obligation metadata (statute references, source history) changed.",
    "punctuation_only": "Only punctuation or whitespace changed in the wording.",
    "cross_ref_only": "Only cross-reference citations changed; the wording is otherwise identical.",
}
NEW_SECTION_REASON = "New section inside a rule your documents cover"


# ---------------------------------------------------------------------------
# Renumber detection (5-gram word shingle Jaccard)
# ---------------------------------------------------------------------------

def shingles(norm_text: str, n: int = SHINGLE_N) -> frozenset:
    """Set of n-gram word shingles; texts shorter than n words yield one shingle."""
    words = [w.lower() for w in _WORD_RE.findall(norm_text or "")]
    if not words:
        return frozenset()
    if len(words) < n:
        return frozenset({tuple(words)})
    return frozenset(tuple(words[i:i + n]) for i in range(len(words) - n + 1))


def jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class ShingleIndex:
    """S1 rows grouped by (source_system, title_number); shingles are computed lazily per group.

    ``s2_titles`` maps S2 section id -> title_number (the inputs carry no title).
    """
    s1_rows: dict[tuple[str, str], list[dict]] = field(default_factory=dict)
    s2_titles: dict[int, str] = field(default_factory=dict)
    _shingles: dict[int, frozenset] = field(default_factory=dict, repr=False)

    @classmethod
    def from_rows(cls, s1_rows: Iterable[dict], s2_titles: dict[int, str] | None = None) -> "ShingleIndex":
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for r in s1_rows:
            grouped[(r["source_system"], r["title_number"])].append(r)
        return cls(dict(grouped), dict(s2_titles or {}))

    def _shingles_of(self, row: dict) -> frozenset:
        rid = row["id"]
        if rid not in self._shingles:
            self._shingles[rid] = shingles(normalize(row.get("body_text") or "", row["source_system"]))
        return self._shingles[rid]

    def best_match(self, inp: ChangeInput, s2_norm: str) -> tuple[dict, float] | None:
        """Best S1 row (same system and title, different citation) by Jaccard, if any."""
        title = self.s2_titles.get(inp.s2_section_id) if inp.s2_section_id is not None else None
        if title is None:
            return None
        target = shingles(s2_norm)
        best: tuple[dict, float] | None = None
        for row in self.s1_rows.get((inp.source_system, title), []):
            if row["citation"] == inp.citation:
                continue
            score = jaccard(target, self._shingles_of(row))
            if best is None or score > best[1]:
                best = (row, score)
        return best


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class DeltaResult:
    change_id: str
    origin: str
    source_system: str
    citation: str
    rule_key: str
    heading: str | None
    s1_section_id: int | None
    s2_section_id: int | None
    renumbered_from: str | None
    change_class: str
    s1_text_norm: str | None
    s2_text_norm: str | None
    diff_segments: list[dict] | None
    published_date: date | None
    date_basis: str | None
    din: str | None
    amendment_source: str | None
    in_footprint: bool
    cited_clause_count: int
    disposition: str | None
    disposition_reason: str | None
    noise_clause_pks: list[str] = field(default_factory=list)


@dataclass
class CandidateSpec:
    candidate_id: str
    change_id: str
    clause_pk: str
    clause_id: str
    doc_id: str
    cited_citation: str | None
    match_path: str
    path_detail: list[dict]
    judged_by: str | None
    skip_reason: str | None
    affected: bool | None
    rationale: str | None


@dataclass
class Stage1Result:
    results: list[DeltaResult]
    candidates: list[CandidateSpec]


# ---------------------------------------------------------------------------
# Pure core
# ---------------------------------------------------------------------------

def _classify_text(s1_norm: str, s2_norm: str, s1_stripped: str, s2_stripped: str) -> str:
    if s1_norm == s2_norm:
        return "cosmetic"
    if s1_stripped == s2_stripped:
        return "metadata_only"
    changed = changed_tokens(s1_stripped, s2_stripped)
    if only_punct(changed):
        return "punctuation_only"
    # all_changed_inside_spans is vacuously True for an empty side; require a real change
    if (changed["deleted"] or changed["inserted"]) and all_changed_inside_spans(
        changed["deleted"], s1_stripped, find_citation_spans(s1_stripped)
    ) and all_changed_inside_spans(
        changed["inserted"], s2_stripped, find_citation_spans(s2_stripped)
    ):
        return "cross_ref_only"
    return "substantive"


def classify_change(
    inp: ChangeInput,
    shingle_index: ShingleIndex | None = None,
    *,
    footprint: Footprint | None = None,
    fr_lookup: dict | None = None,
    jaccard_threshold: float | None = None,
) -> DeltaResult:
    """Apply the section 1.2 table (first match wins) and the section 1.6 dispositions."""
    thr = engine_settings.ENGINE_RENUMBER_JACCARD if jaccard_threshold is None else jaccard_threshold
    sys = inp.source_system
    s1_raw, s2_raw = inp.s1_text, inp.s2_text
    s1_norm = normalize(s1_raw, sys) if s1_raw is not None else None
    s2_norm = normalize(s2_raw, sys) if s2_raw is not None else None
    s1_strip = strip_metadata(s1_norm, sys) if s1_norm is not None else None
    s2_strip = strip_metadata(s2_norm, sys) if s2_norm is not None else None

    s1_section_id = inp.s1_section_id
    renumbered_from: str | None = None
    is_new = inp.s1_section_id is None and s1_raw is None and inp.origin == "kb"

    if (inp.s2_status or "").lower() in _REPEAL_STATUSES and (inp.s1_status or "").lower() not in _REPEAL_STATUSES:
        cls = "repealed"
    elif is_new:
        cls = "new_section"
        if shingle_index is not None and s2_norm:
            hit = shingle_index.best_match(inp, s2_norm)
            if hit is not None and hit[1] >= thr:
                cls = "renumbered"
                renumbered_from = hit[0]["citation"]
                s1_section_id = hit[0]["id"]
                s1_raw = hit[0].get("body_text")
                s1_norm = normalize(s1_raw or "", sys)
                s1_strip = strip_metadata(s1_norm, sys)
    elif s1_norm is not None and s2_norm is not None:
        cls = _classify_text(s1_norm, s2_norm, s1_strip, s2_strip)
    else:
        cls = "substantive"  # defensive: pair with a missing text side

    diff = None
    if s1_strip is not None and s2_strip is not None and cls != "new_section":
        diff = diff_segments(s1_strip, s2_strip)

    pub = compute_publication(sys, inp.s1_text, inp.s2_text, inp.amendment_source, fr_lookup)

    rk = rule_key(inp.citation) or inp.citation
    in_fp = False
    n_cited = 0
    if footprint is not None:
        in_fp = footprint.in_footprint(s1_section_id, inp.citation)
        n_cited = footprint.cited_clause_count(s1_section_id, inp.citation)

    disposition: str | None = None
    reason: str | None = None
    noise_pks: list[str] = []
    if cls in NOISE_CLASSES:
        disposition = "excluded_noise"
        reason = CLASS_EXPLANATIONS[cls]
        if in_fp and footprint is not None and s1_section_id is not None:
            noise_pks = sorted(footprint.clauses_by_section.get(int(s1_section_id), set()))
    elif not in_fp:
        disposition = "not_in_footprint"
        reason = "No company clause cites this section or its rule"
    elif cls == "new_section":
        disposition = "needs_review"
        reason = NEW_SECTION_REASON

    return DeltaResult(
        change_id=str(uuid.uuid4()),
        origin=inp.origin,
        source_system=sys,
        citation=inp.citation,
        rule_key=rk,
        heading=inp.heading,
        s1_section_id=s1_section_id,
        s2_section_id=inp.s2_section_id,
        renumbered_from=renumbered_from,
        change_class=cls,
        s1_text_norm=s1_strip,
        s2_text_norm=s2_strip,
        diff_segments=diff,
        published_date=pub["published_date"],
        date_basis=pub["date_basis"],
        din=pub["din"],
        amendment_source=inp.amendment_source,
        in_footprint=in_fp,
        cited_clause_count=n_cited,
        disposition=disposition,
        disposition_reason=reason,
        noise_clause_pks=noise_pks,
    )


# ---------------------------------------------------------------------------
# Async wrapper
# ---------------------------------------------------------------------------

_S1_CORPUS_SQL = text("""
    SELECT id, source_system, title_number, citation, body_text
    FROM public.code_sections
    WHERE (source_system, snapshot_date) IN (
        SELECT source_system, MIN(snapshot_date) FROM public.code_sections GROUP BY source_system
    )
""")

_S2_TITLES_SQL = text("""
    SELECT id, title_number FROM public.code_sections WHERE id = ANY(:ids)
""")

_CLAUSE_IDS_SQL = text("""
    SELECT clause_pk::text AS clause_pk, clause_id, doc_id
    FROM company.clauses
    WHERE clause_pk = ANY(CAST(:pks AS uuid[]))
""")


async def _load_shingle_index(session: AsyncSession, inputs: list[ChangeInput]) -> ShingleIndex:
    new_ids = [i.s2_section_id for i in inputs
               if i.origin == "kb" and i.s1_section_id is None and i.s2_section_id is not None]
    if not new_ids:
        return ShingleIndex()
    titles = {r["id"]: r["title_number"] for r in
              (await session.execute(_S2_TITLES_SQL, {"ids": sorted(set(new_ids))})).mappings().all()}
    rows = [dict(r) for r in (await session.execute(_S1_CORPUS_SQL)).mappings().all()]
    return ShingleIndex.from_rows(rows, titles)


async def run_stage1(
    session: AsyncSession,
    run_id: str,
    inputs: list[ChangeInput],
    footprint: Footprint,
) -> Stage1Result:
    """Classify all inputs; builds the noise "cleared with proof" candidates. Read-only."""
    fr_ids = [i.amendment_source for i in inputs if i.source_system == "cfr" and i.amendment_source]
    fr_lookup = await lookup_fr_dates_batch(session, fr_ids)
    index = await _load_shingle_index(session, inputs)

    results = [classify_change(i, index, footprint=footprint, fr_lookup=fr_lookup) for i in inputs]

    pks = sorted({pk for r in results for pk in r.noise_clause_pks})
    clause_rows: dict[str, dict] = {}
    if pks:
        for row in (await session.execute(_CLAUSE_IDS_SQL, {"pks": pks})).mappings().all():
            clause_rows[row["clause_pk"]] = dict(row)

    candidates: list[CandidateSpec] = []
    for r in results:
        for pk in r.noise_clause_pks:
            cr = clause_rows.get(pk)
            if cr is None:
                logger.warning("noise candidate clause %s not found", pk)
                continue
            candidates.append(CandidateSpec(
                candidate_id=str(uuid.uuid4()),
                change_id=r.change_id,
                clause_pk=pk,
                clause_id=cr["clause_id"],
                doc_id=cr["doc_id"],
                cited_citation=r.citation,
                match_path="direct_section",
                path_detail=[{"path": "direct_section", "via_clause_id": None,
                              "link_type": None, "value": r.citation}],
                judged_by=None,
                skip_reason=f"noise:{r.change_class}",
                affected=False,
                rationale=f"{r.change_class}: {CLASS_EXPLANATIONS[r.change_class]}",
            ))
    return Stage1Result(results, candidates)


_INSERT_CHANGE_SQL = text("""
    INSERT INTO engine.change_records
        (change_id, run_id, origin, source_system, citation, rule_key, heading,
         s1_section_id, s2_section_id, renumbered_from, change_class,
         s1_text_norm, s2_text_norm, diff_segments, published_date, date_basis, din,
         amendment_source, in_footprint, cited_clause_count, disposition, disposition_reason)
    VALUES
        (:change_id, :run_id, :origin, :source_system, :citation, :rule_key, :heading,
         :s1_section_id, :s2_section_id, :renumbered_from, :change_class,
         :s1_text_norm, :s2_text_norm, CAST(:diff_segments AS jsonb), :published_date, :date_basis, :din,
         :amendment_source, :in_footprint, :cited_clause_count, :disposition, :disposition_reason)
""")

_INSERT_CANDIDATE_SQL = text("""
    INSERT INTO engine.candidates
        (candidate_id, run_id, change_id, clause_pk, clause_id, doc_id, cited_citation,
         match_path, path_detail, judged_by, skip_reason, affected, rationale)
    VALUES
        (:candidate_id, :run_id, :change_id, CAST(:clause_pk AS uuid), :clause_id, :doc_id, :cited_citation,
         :match_path, CAST(:path_detail AS jsonb), :judged_by, :skip_reason, :affected, :rationale)
""")


async def persist_stage1(session: AsyncSession, run_id: str, stage1: Stage1Result) -> None:
    """Insert change_records then candidates (candidates reference change_records). No commit."""
    if stage1.results:
        await session.execute(_INSERT_CHANGE_SQL, [
            {
                "change_id": r.change_id, "run_id": run_id, "origin": r.origin,
                "source_system": r.source_system, "citation": r.citation, "rule_key": r.rule_key,
                "heading": r.heading, "s1_section_id": r.s1_section_id,
                "s2_section_id": r.s2_section_id, "renumbered_from": r.renumbered_from,
                "change_class": r.change_class, "s1_text_norm": r.s1_text_norm,
                "s2_text_norm": r.s2_text_norm,
                "diff_segments": json.dumps(r.diff_segments) if r.diff_segments is not None else None,
                "published_date": r.published_date, "date_basis": r.date_basis, "din": r.din,
                "amendment_source": r.amendment_source, "in_footprint": r.in_footprint,
                "cited_clause_count": r.cited_clause_count, "disposition": r.disposition,
                "disposition_reason": r.disposition_reason,
            }
            for r in stage1.results
        ])
    if stage1.candidates:
        await session.execute(_INSERT_CANDIDATE_SQL, [
            {
                "candidate_id": c.candidate_id, "run_id": run_id, "change_id": c.change_id,
                "clause_pk": c.clause_pk, "clause_id": c.clause_id, "doc_id": c.doc_id,
                "cited_citation": c.cited_citation, "match_path": c.match_path,
                "path_detail": json.dumps(c.path_detail), "judged_by": c.judged_by,
                "skip_reason": c.skip_reason, "affected": c.affected, "rationale": c.rationale,
            }
            for c in stage1.candidates
        ])


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def stage1_stats(results: Iterable[DeltaResult]) -> dict[str, Any]:
    """Class counts per source, totals, and the in-footprint changes for the checkpoint report."""
    results = list(results)
    by_source: dict[str, Counter] = defaultdict(Counter)
    for r in results:
        by_source[r.source_system][r.change_class] += 1
    by_class = Counter(r.change_class for r in results)
    in_fp = [(r.citation, r.change_class, r.cited_clause_count) for r in results if r.in_footprint]
    in_fp.sort(key=lambda t: (-t[2], t[0]))
    return {
        "total": len(results),
        "by_source": {k: dict(v) for k, v in by_source.items()},
        "by_class": dict(by_class),
        "in_footprint_by_class": dict(Counter(c for _, c, _ in in_fp)),
        "in_footprint": in_fp,
        "renumbered": [(r.citation, r.renumbered_from) for r in results if r.change_class == "renumbered"],
        "dispositions": dict(Counter(r.disposition for r in results)),
    }


def format_in_footprint(stats: dict[str, Any]) -> list[str]:
    return [f"{c} | {k} | {n}" for c, k, n in stats["in_footprint"]]
