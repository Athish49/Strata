"""Task 1.1.5 - parameter extraction from free text for the impact engine.

Wraps the company-ingest regex pass (enrich_parameters) around a synthetic
ClauseUnit so the engine sees exactly the same parameters the ingest pipeline
would. Pure in-memory; no network or DB.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from app.company_ingest.enrich.citations_grammar import find_citation_spans
from app.company_ingest.enrich.parameters_regex import enrich_parameters
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext


def _synthetic_unit(text: str) -> ClauseUnit:
    return ClauseUnit(
        version_id="", doc_id="", clause_id=":", local_id="",
        parent_clause_id=None, unit_kind="clause", heading_path=[],
        section_kind="body", ordinal=0, char_start=0, char_end=len(text),
        line_start=0, text_raw=text, text_norm=text, text_sha256="",
    )


def _overlaps(s: int, e: int, spans: list[tuple[int, int]]) -> bool:
    return any(s < ce and e > cs for cs, ce in spans)


def extract_parameters_from_text(text: str) -> list[dict]:
    """Return parameters found in *text*, sorted by span start.

    Each dict: {kind, unit, value_num, value_text, day_type, span=(start, end)}.
    Parameters overlapping a citation span are dropped (citation fragments such
    as the "170" or "4-1-16" of a rule cite).
    """
    if not text:
        return []
    unit = _synthetic_unit(text)
    enrich_parameters([unit], RunContext())
    cit = [(s, e) for s, e, _ in find_citation_spans(text)]

    out: list[dict] = []
    for p in unit.parameters:
        s, e = p.span_start, p.span_end
        if _overlaps(s, e, cit):
            continue
        out.append({
            "kind": getattr(p.kind, "value", p.kind),
            "unit": p.unit,
            "value_num": p.value_num,
            "value_text": p.value_text,
            "day_type": getattr(p.day_type, "value", p.day_type),
            "span": (s, e),
        })
    out.sort(key=lambda d: (d["span"][0], d["span"][1], d["kind"], d["unit"] or ""))
    return out


def _key(p: dict) -> tuple:
    return (p["kind"], p["unit"], p["value_num"], p["day_type"])


def param_multiset_diff(
    a_params: Iterable[dict], b_params: Iterable[dict]
) -> tuple[list[dict], list[dict]]:
    """Compare two parameter lists as multisets keyed by (kind, unit, value_num, day_type).

    Returns (only_in_a, only_in_b), each in input order.
    """
    a_list, b_list = list(a_params), list(b_params)
    ca, cb = Counter(map(_key, a_list)), Counter(map(_key, b_list))

    def _take(items: list[dict], surplus: Counter) -> list[dict]:
        left = dict(surplus)
        res = []
        for p in items:
            k = _key(p)
            if left.get(k, 0) > 0:
                left[k] -= 1
                res.append(p)
        return res

    return _take(a_list, ca - cb), _take(b_list, cb - ca)
