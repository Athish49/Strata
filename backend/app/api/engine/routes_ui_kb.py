"""UI knowledge-base routes: agencies, code sections, version history (contract 4.1-4.3).

Read-only. Mounted under /engine by routes.py. The `/versions` route is declared BEFORE the
plain section route because the citation segment is a greedy `:path`.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.engine import routes_ui_common as ui
from app.api.engine.routes import _all, _one
from app.db import get_db
from app.engine.footprint import rule_key

router = APIRouter(tags=["engine-ui-kb"])

_AGENCY_ORDER = ("ferc", "epa", "iurc", "idem", "idol", "ifpbsc")
_SECTION_SYSTEM_SYNC = {"iac": "iac", "cfr": "cfr"}


def _iso(v: Any) -> str:
    if v is None:
        return ""
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _int_key(s: str):
    try:
        return (0, int(s), s)
    except (TypeError, ValueError):
        return (1, 0, str(s))


def _agency_rank(a: dict):
    lvl = 0 if a["level"] == "federal" else 1
    aid = a["agency_id"]
    idx = _AGENCY_ORDER.index(aid) if aid in _AGENCY_ORDER else len(_AGENCY_ORDER)
    return (lvl, idx, aid or "")


async def _build_agencies(db: AsyncSession) -> list[dict]:
    ag = await _all(db, "SELECT agency_id, name, jurisdiction_level, jurisdiction_geo, domain FROM agencies")
    secs = await _all(db, """
        SELECT agency_id, count(DISTINCT citation) AS n, min(snapshot_date) AS s1, max(snapshot_date) AS s2,
               array_agg(DISTINCT source_system) AS systems
        FROM public.code_sections WHERE agency_id IS NOT NULL GROUP BY agency_id""")
    titles = await _all(db, """
        SELECT DISTINCT agency_id, source_system, title_number, part
        FROM public.code_sections WHERE agency_id IS NOT NULL""")
    acts = await _all(db, """
        SELECT agency, count(*) AS n, array_agg(DISTINCT source_system) AS streams
        FROM public.regulatory_actions WHERE agency IS NOT NULL GROUP BY agency""")
    sync = {r["source_system"]: r["last_sync_at"]
            for r in await _all(db, "SELECT source_system, last_sync_at FROM sync_state")}
    secs_by = {r["agency_id"]: r for r in secs}
    acts_by = {r["agency"]: r for r in acts}
    out = []
    for a in ag:
        aid = a["agency_id"]
        s = secs_by.get(aid) or {}
        ac = acts_by.get(aid) or {}
        tset: set[tuple[str, str]] = set()
        for t in titles:
            if t["agency_id"] != aid or not t["title_number"]:
                continue
            if t["source_system"] == "cfr":
                tset.add((t["title_number"], f"{t['title_number']} CFR {t['part']}" if t["part"]
                          else f"{t['title_number']} CFR"))
            else:
                tset.add((t["title_number"], f"{t['title_number']} IAC"))
        codebook = [lbl for _, lbl in sorted(tset, key=lambda x: (_int_key(x[0]), x[1]))]
        streams = sorted(ac.get("streams") or [])
        sync_keys = [_SECTION_SYSTEM_SYNC.get(x, x) for x in (s.get("systems") or [])] + streams
        syncs = [sync[k] for k in sync_keys if sync.get(k)]
        action_count = int(ac.get("n") or 0)
        out.append({
            "agency_id": aid, "slug": aid, "name": a["name"],
            "level": a["jurisdiction_level"] if a["jurisdiction_level"] in ("federal", "state") else "state",
            "geo": a["jurisdiction_geo"] or "US",
            "domains": list(a["domain"] or []),
            "codebook_titles": codebook,
            "section_count": int(s.get("n") or 0),
            "action_count": action_count,
            "s1_snapshot": _iso(s.get("s1")), "s2_snapshot": _iso(s.get("s2")),
            "last_sync_at": (max(syncs).isoformat() + "Z") if syncs else "",
            "has_activity_feed": action_count > 0,
            "streams": streams,
        })
    out.sort(key=_agency_rank)
    return out


@router.get("/ui/kb/agencies")
async def ui_kb_agencies(db: AsyncSession = Depends(get_db)):
    return await _build_agencies(db)


@router.get("/ui/kb/agencies/{slug}")
async def ui_kb_agency(slug: str, db: AsyncSession = Depends(get_db)):
    for a in await _build_agencies(db):
        if a["slug"] == slug.lower():
            return a
    raise HTTPException(404, "agency not found")


# ---------------------------------------------------------------- sections
_LATEST = """
    (SELECT DISTINCT ON (source_system, citation) citation, source_system, title_number, part,
            section_number, heading, status, snapshot_date, agency_id, amendment_source,
            federal_refs, iac_cross_refs
       FROM public.code_sections
      ORDER BY source_system, citation, snapshot_date DESC, id DESC) cs"""

_COLS = """cs.citation, cs.source_system, cs.title_number, cs.part, cs.section_number, cs.heading,
           cs.status, cs.snapshot_date, cs.agency_id, cs.amendment_source, cs.federal_refs,
           cs.iac_cross_refs"""


def _section(r: dict, with_body: bool) -> dict:
    cit = r["citation"]
    return {
        "citation": cit,
        "source_system": r["source_system"],
        "title_number": r["title_number"] or "",
        "part_or_article": r["part"] or "",
        "rule_key": rule_key(cit) or cit,
        "section_number": r["section_number"] or "",
        "heading": ui.clean_heading(cit, r["heading"]),
        "body_text": (r.get("body_text") or "") if with_body else "",
        "status": r["status"],
        "snapshot_date": _iso(r["snapshot_date"]),
        "owning_agency": r["agency_id"] or "",
        "amendment_source": r["amendment_source"],
        "federal_refs": list(r["federal_refs"] or []),
        "iac_cross_refs": list(r["iac_cross_refs"] or []),
    }


@router.get("/ui/kb/sections")
async def ui_kb_sections(
    agency: Optional[str] = Query(None),
    source_system: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
):
    where = """WHERE (CAST(:agency AS text) IS NULL OR cs.agency_id = :agency)
           AND (CAST(:ss AS text) IS NULL OR cs.source_system = :ss)
           AND (CAST(:status AS text) IS NULL OR cs.status = :status)
           AND (CAST(:search AS text) IS NULL OR cs.citation ILIKE :pat OR cs.heading ILIKE :pat)"""
    params = {"agency": agency, "ss": source_system, "status": status, "search": search,
              "pat": f"%{search}%" if search else None}
    total = (await _one(db, f"SELECT count(*) AS n FROM {_LATEST} {where}", **params))["n"]
    rows = await _all(db, f"SELECT {_COLS} FROM {_LATEST} {where} "
                          "ORDER BY cs.citation, cs.source_system LIMIT :lim OFFSET :off",
                      lim=limit, off=(page - 1) * limit, **params)
    return {"items": [_section(r, False) for r in rows], "total": int(total), "page": page, "limit": limit}


@router.get("/ui/kb/sections/{source_system}/{citation:path}/versions")
async def ui_kb_versions(source_system: str, citation: str, db: AsyncSession = Depends(get_db)):
    rows = await _all(db, """
        SELECT snapshot_date, body_text FROM public.code_sections
        WHERE source_system = :ss AND citation = :c ORDER BY snapshot_date, id""", ss=source_system, c=citation)
    if not rows:
        return []
    first = (await _one(db, "SELECT min(snapshot_date) AS d FROM public.code_sections WHERE source_system = :ss",
                        ss=source_system))["d"]
    return [{"snapshot": "S1" if r["snapshot_date"] == first else "S2",
             "snapshot_date": _iso(r["snapshot_date"]), "text": r["body_text"] or ""} for r in rows]


@router.get("/ui/kb/sections/{source_system}/{citation:path}")
async def ui_kb_section(source_system: str, citation: str, db: AsyncSession = Depends(get_db)):
    r = await _one(db, f"SELECT {_COLS}, cs.body_text FROM public.code_sections cs "
                       "WHERE cs.source_system = :ss AND cs.citation = :c "
                       "ORDER BY cs.snapshot_date DESC, cs.id DESC LIMIT 1", ss=source_system, c=citation)
    if not r:
        raise HTTPException(404, "section not found")
    return _section(r, True)
