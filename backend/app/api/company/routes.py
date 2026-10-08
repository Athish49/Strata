"""Company endpoints (read-only): documents, clauses, people, profile.

Shapes follow frontend/lib/api/schemas/company.ts (contract sections 5 and 8).
"""
from __future__ import annotations

import csv
import logging
import pathlib
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.engine.config import engine_settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/company", tags=["company"])

_GLOBAL = pathlib.Path(__file__).resolve().parents[2] / "company" / "corpus" / "_global"

# backend vertical name -> frontend slug (keep in sync with frontend/lib/verticals.ts)
VERTICAL_SLUGS = {
    "compliance & legal": "compliance-legal",
    "policy & governance": "policy-governance",
    "operations & processes": "operations-processes",
    "environmental": "environmental-esg",
    "workforce & safety": "workforce-hr",
}
_DOC_TYPES = {
    "PRO": "Procedure", "PLN": "Plan", "PGM": "Program Plan", "GRR": "Tariff",
    "REG": "Register", "RRS": "Register", "CAL": "Register", "POL": "Policy", "STD": "Standard",
}
_UNIT_KINDS = {"section", "table_row", "register_row", "form_field", "tariff_subrule", "appendix"}
_STATES = {
    "IN": "Indiana", "IL": "Illinois", "OH": "Ohio", "KY": "Kentucky", "MI": "Michigan",
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IA": "Iowa", "KS": "Kansas", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

_register_cache: Optional[dict[str, dict[str, str]]] = None
_yaml_cache: Optional[dict] = None


# ---------------------------------------------------------------- pure helpers
def vertical_slug(name: Optional[str]) -> str:
    if not name:
        return "unclassified"
    return VERTICAL_SLUGS.get(name.strip().lower(), "unclassified")


def derive_doc_type(doc_id: str) -> str:
    parts = (doc_id or "").split("-")
    if len(parts) >= 3:
        return _DOC_TYPES.get(parts[-2].upper(), "Document")
    return "Document"


def clean_unit_kind(kind: Optional[str]) -> str:
    return kind if kind in _UNIT_KINDS else "section"


def clean_row_cells(cells: Any) -> Optional[dict[str, str]]:
    if not isinstance(cells, dict):
        return None
    return {str(k): v for k, v in cells.items() if isinstance(v, str)}


def attribute_value(value_bool, value_num, value_text):
    if value_bool is not None:
        return bool(value_bool)
    if value_num is not None:
        f = float(value_num)
        return int(f) if f == int(f) else f
    return value_text if value_text is not None else ""


def attribute_source(source: Optional[str]) -> str:
    return (source or "").split(":", 1)[0].strip()


def _iso(d: Any) -> Optional[str]:
    return d.isoformat() if d is not None else None


def load_register() -> dict[str, dict[str, str]]:
    global _register_cache
    if _register_cache is None:
        data: dict[str, dict[str, str]] = {}
        try:
            with open(_GLOBAL / "document_register.csv", newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    if row.get("doc_id"):
                        data[row["doc_id"]] = row
        except Exception as exc:  # missing/unreadable -> nulls
            log.warning("document_register.csv unavailable: %s", exc)
        _register_cache = data
    return _register_cache


def load_profile_yaml() -> dict:
    global _yaml_cache
    if _yaml_cache is None:
        data: dict = {}
        try:
            import yaml

            with open(_GLOBAL / "company_profile.yaml", encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh)
            if isinstance(loaded, dict):
                data = loaded
        except Exception as exc:
            log.warning("company_profile.yaml unavailable: %s", exc)
        _yaml_cache = data
    return _yaml_cache


def _person(row: dict, prefix: str) -> Optional[dict]:
    if row.get(f"{prefix}_pid") is None:
        return None
    return {
        "person_id": row[f"{prefix}_pid"],
        "name": row[f"{prefix}_name"] or "",
        "title": row[f"{prefix}_title"] or "",
        "department": row[f"{prefix}_dept"] or "",
        "reports_to_id": row[f"{prefix}_rt"],
    }


def build_document(row: dict, cited: list[str], register: dict[str, dict[str, str]]) -> dict:
    reg = register.get(row["doc_id"], {})
    vname = row.get("vertical") or reg.get("vertical") or None
    next_review = _iso(row.get("next_review")) or (reg.get("next_review_date") or None)
    review_cycle = row.get("review_cycle") or reg.get("review_cycle") or None
    owner = _person(row, "o")
    reviewer = _person(row, "r")
    approver = _person(row, "a")
    # owner/reviewer are required by the schema; fall back to a bare id record if a join misses
    blank = lambda pid: {"person_id": pid or "", "name": "", "title": "", "department": "", "reports_to_id": None}
    return {
        "doc_id": row["doc_id"],
        "title": row["title"] or "",
        "version": row.get("version") or "",
        "status": row.get("status") or "",
        "effective_date": _iso(row.get("effective_date")),
        "approved_date": _iso(row.get("approved_date")),
        "law_as_of": _iso(row.get("law_as_of")),
        "next_review": next_review,
        "review_cycle": review_cycle,
        "vertical": vertical_slug(vname),
        "vertical_name": vname,
        "owner": owner or blank(row.get("owner_id")),
        "reviewer": reviewer or blank(row.get("reviewer_id")),
        "approver": approver,
        "two_signature": row.get("approver_id") is None,
        "monitored": row.get("ingest_status") == "ingested",
        "doc_type": derive_doc_type(row["doc_id"]),
        "cited_citations": cited,
    }


# ------------------------------------------------------------------------ SQL
_DOC_SQL = """
SELECT cd.doc_id, cd.title, cd.vertical, cd.review_cycle, cd.owner_id, cd.reviewer_id, cd.approver_id,
       v.version, v.status, v.effective_date, v.approved_date, v.law_as_of, v.next_review, v.ingest_status,
       po.person_id AS o_pid, po.name AS o_name, po.title AS o_title, po.department AS o_dept, po.reports_to_id AS o_rt,
       pr.person_id AS r_pid, pr.name AS r_name, pr.title AS r_title, pr.department AS r_dept, pr.reports_to_id AS r_rt,
       pa.person_id AS a_pid, pa.name AS a_name, pa.title AS a_title, pa.department AS a_dept, pa.reports_to_id AS a_rt
FROM company.company_documents cd
LEFT JOIN company.document_versions v ON v.version_id = cd.current_version_id
LEFT JOIN company.people po ON po.company_id = cd.company_id AND po.person_id = cd.owner_id
LEFT JOIN company.people pr ON pr.company_id = cd.company_id AND pr.person_id = cd.reviewer_id
LEFT JOIN company.people pa ON pa.company_id = cd.company_id AND pa.person_id = cd.approver_id
WHERE cd.company_id = :cid {extra}
ORDER BY cd.doc_id
"""

_CITED_SQL = """
SELECT DISTINCT c.doc_id, cs.citation
FROM company.clauses c
JOIN company.clause_citations cc ON cc.clause_pk = c.clause_pk
JOIN public.code_sections cs ON cs.id = cc.code_section_id::int
WHERE c.company_id = :cid AND cc.resolution_status IN ('resolved','resolved_rule')
  AND cc.code_section_id ~ '^[0-9]+$' {extra}
"""


async def _documents(db: AsyncSession, doc_id: Optional[str] = None) -> list[dict]:
    params: dict[str, Any] = {"cid": engine_settings.ENGINE_COMPANY_ID}
    extra = ""
    cextra = ""
    if doc_id is not None:
        extra = "AND cd.doc_id = :doc_id"
        cextra = "AND c.doc_id = :doc_id"
        params["doc_id"] = doc_id
    rows = (await db.execute(text(_DOC_SQL.format(extra=extra)), params)).mappings().all()
    if not rows:
        return []
    cited: dict[str, list[str]] = {}
    for r in (await db.execute(text(_CITED_SQL.format(extra=cextra)), params)).mappings().all():
        cited.setdefault(r["doc_id"], []).append(r["citation"])
    register = load_register()
    return [build_document(dict(r), sorted(set(cited.get(r["doc_id"], []))), register) for r in rows]


# ------------------------------------------------------------------ endpoints
@router.get("/documents")
async def list_documents(db: AsyncSession = Depends(get_db)):
    return await _documents(db)


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    docs = await _documents(db, doc_id)
    if not docs:
        raise HTTPException(status_code=404, detail="document not found")
    return docs[0]


@router.get("/documents/{doc_id}/clauses")
async def list_clauses(doc_id: str, db: AsyncSession = Depends(get_db)):
    sql = """
    SELECT clause_id, doc_id, heading_path, unit_kind, text_raw, row_cells, parent_clause_id,
           ROW_NUMBER() OVER (ORDER BY (version_id = current_version_id) DESC, ordinal, clause_id) AS dense_ord
    FROM (
      SELECT c.*, cd.current_version_id
      FROM company.clauses c
      JOIN company.company_documents cd ON cd.company_id = c.company_id AND cd.doc_id = c.doc_id
      WHERE c.company_id = :cid AND c.doc_id = :doc_id
    ) x
    ORDER BY dense_ord
    """
    rows = (await db.execute(text(sql), {"cid": engine_settings.ENGINE_COMPANY_ID, "doc_id": doc_id})).mappings().all()
    return [
        {
            "clause_id": r["clause_id"],
            "doc_id": r["doc_id"],
            "ordinal": int(r["dense_ord"]),
            "heading_path": list(r["heading_path"] or []),
            "unit_kind": clean_unit_kind(r["unit_kind"]),
            "text_raw": r["text_raw"] or "",
            "row_cells": clean_row_cells(r["row_cells"]),
            "parent_clause_id": r["parent_clause_id"],
        }
        for r in rows
    ]


@router.get("/people")
async def list_people(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        text("SELECT person_id, name, title, department, reports_to_id FROM company.people "
             "WHERE company_id = :cid ORDER BY person_id"),
        {"cid": engine_settings.ENGINE_COMPANY_ID},
    )
    return [
        {"person_id": r["person_id"], "name": r["name"] or "", "title": r["title"] or "",
         "department": r["department"] or "", "reports_to_id": r["reports_to_id"]}
        for r in res.mappings().all()
    ]


@router.get("/profile")
async def get_profile(db: AsyncSession = Depends(get_db)):
    cid = engine_settings.ENGINE_COMPANY_ID
    co = (await db.execute(text("SELECT name FROM company.companies WHERE company_id = :cid"), {"cid": cid})).mappings().first()
    rows = (await db.execute(
        text("SELECT key, value_text, value_num, value_bool, source FROM company.company_attributes "
             "WHERE company_id = :cid ORDER BY key"), {"cid": cid})).mappings().all()
    attributes = [
        {"key": r["key"], "value": attribute_value(r["value_bool"], r["value_num"], r["value_text"]),
         "source": attribute_source(r["source"])}
        for r in rows
    ]
    by_key = {a["key"]: a["value"] for a in attributes}
    yml = load_profile_yaml()
    regulator = ((yml.get("company") or {}).get("regulator")) or ""
    utility = ((yml.get("business_model") or {}).get("utility_type")) or ""
    ownership = by_key.get("ownership")
    words = [str(w).replace("_", " ") for w in (ownership, utility) if w]
    ctype = (" ".join(words) + " utility") if words else ""
    ctype = (ctype[:1].upper() + ctype[1:]) if ctype else ""
    ctype = ctype.replace("Investor owned", "Investor-owned")
    code = by_key.get("jurisdiction")
    state = _STATES.get(str(code), str(code)) if code else ""
    cust = by_key.get("customer_count_total")
    try:
        customers = int(float(cust)) if cust is not None else 0
    except (TypeError, ValueError):
        customers = 0
    return {
        "name": (co["name"] if co else "") or "",
        "type": ctype,
        "state": state,
        "customers": customers,
        "regulator": regulator,
        "attributes": attributes,
    }
