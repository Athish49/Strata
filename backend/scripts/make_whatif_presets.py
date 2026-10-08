"""Create (idempotently) the what-if presets of engine_spec.md section 8, optionally run them.

3 value presets (top S1 sections, distinct rules, by eligible clauses citing them that carry a
non-fragment parameter whose value and unit appear in the section's S1 text) + 1 repeal preset
on the most-cited section.

    PYTHONPATH=. .venv/bin/python scripts/make_whatif_presets.py --dry-run
    PYTHONPATH=. .venv/bin/python scripts/make_whatif_presets.py [--run]
"""
from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal

from sqlalchemy import text

from app.db import AsyncSessionLocal
from app.engine import whatif
from app.engine.config import engine_settings
from app.engine import textnorm
from app.engine.params_text import extract_parameters_from_text

_CANDIDATES_SQL = text("""
    SELECT cs.id AS s1_section_id, cs.citation, cs.body_text, cs.source_system,
           c.clause_pk::text AS clause_pk, p.value_num, p.unit, p.kind, p.name
    FROM company.clauses c
    JOIN company.company_documents d ON d.doc_id = c.doc_id AND d.company_id = :company_id
    JOIN company.clause_citations cc ON cc.clause_pk = c.clause_pk AND cc.resolution_status = 'resolved'
    JOIN public.code_sections cs ON CAST(cs.id AS text) = CAST(cc.code_section_id AS text)
    JOIN (SELECT source_system, MIN(snapshot_date) AS d FROM public.code_sections GROUP BY source_system) s1
      ON s1.source_system = cs.source_system AND s1.d = cs.snapshot_date
    JOIN company.clause_parameters p ON p.clause_pk = c.clause_pk
    WHERE c.company_id = :company_id AND c.assessable = true AND c.clause_role <> 'boilerplate'
      AND COALESCE(p.is_citation_fragment, false) = false
      AND p.kind IN ('period', 'deadline', 'amount', 'threshold')
      AND p.value_num IS NOT NULL
""")


def _as_int(v) -> int | None:
    if v is None:
        return None
    d = Decimal(str(v))
    return int(d) if d == d.to_integral_value() and 1 <= d < 1000 else None


def build_candidates(rows: list[dict]) -> list[dict]:
    """Keep rows whose (value, unit) occurs in the section's S1 text and is replaceable there."""
    parsed: dict[int, list[dict]] = {}
    out: list[dict] = []
    for r in rows:
        n = _as_int(r["value_num"])
        if n is None:
            continue
        sid = r["s1_section_id"]
        if sid not in parsed:
            parsed[sid] = extract_parameters_from_text(r["body_text"] or "")
        hit = next((p for p in parsed[sid]
                    if p["value_num"] is not None and _as_int(p["value_num"]) == n
                    and (p["unit"] or None) == (r["unit"] or None)), None)
        if hit is None:
            continue
        rep = whatif.replace_value(r["body_text"], n, whatif.changed_value(n), near=hit["span"][0])
        if rep is None:
            continue
        # the edit must be an obligation-bearing change, not one that disappears under metadata stripping
        src = r.get("source_system") or "iac"
        if textnorm.strip_metadata(textnorm.normalize(rep[0], src), src) == \
                textnorm.strip_metadata(textnorm.normalize(r["body_text"], src), src):
            continue
        out.append({"s1_section_id": sid, "citation": r["citation"], "value_num": n, "unit": r["unit"],
                    "kind": r["kind"], "name": r["name"], "clause_pk": r["clause_pk"],
                    "body_text": r["body_text"], "near": hit["span"][0]})
    return out


def make_value_preset(c: dict) -> dict:
    n = c["value_num"]
    new = whatif.changed_value(n)
    edited, old_s, new_s = whatif.replace_value(c["body_text"], n, new, near=c["near"])
    subject = (c.get("name") or c.get("unit") or c.get("kind") or "value").replace("_", " ")
    return {"title": whatif.preset_title(c["citation"], subject, str(n), str(new)),
            "s1_section_id": c["s1_section_id"], "edit_kind": "text_edit", "edited_text": edited,
            "clause_count": c["clause_count"], "surface": f"{old_s!r} -> {new_s!r}"}


async def choose_presets(session) -> list[dict]:
    rows = [dict(r) for r in (await session.execute(
        _CANDIDATES_SQL, {"company_id": engine_settings.ENGINE_COMPANY_ID})).mappings().all()]
    chosen = whatif.pick_value_presets(build_candidates(rows), limit=3)
    presets = [make_value_preset(c) for c in chosen]
    sections = await whatif.list_editable_sections(session)
    if sections:
        top = sections[0]
        presets.append({"title": f"{top['citation']}: repeal section", "s1_section_id": top["s1_section_id"],
                        "edit_kind": "repeal", "edited_text": None, "clause_count": top["cited_clause_count"],
                        "surface": "repeal"})
    return presets


async def main(dry_run: bool, run: bool) -> None:
    async with AsyncSessionLocal() as session:
        presets = await choose_presets(session)
        for p in presets:
            print(f"{p['title']} | section {p['s1_section_id']} | {p['edit_kind']} | "
                  f"{p['clause_count']} clauses | {p['surface']}")
        if dry_run:
            return
        ids = [await whatif.upsert_preset(session, title=p["title"], s1_section_id=p["s1_section_id"],
                                          edit_kind=p["edit_kind"], edited_text=p["edited_text"])
               for p in presets]
    print(f"upserted {len(ids)} presets")
    if run:
        for sid, p in zip(ids, presets):
            run_id = await whatif.run_whatif(sid)
            print(f"ran {p['title']} -> {run_id}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the chosen presets, write nothing")
    ap.add_argument("--run", action="store_true", help="also run every preset")
    a = ap.parse_args()
    asyncio.run(main(a.dry_run, a.run))
