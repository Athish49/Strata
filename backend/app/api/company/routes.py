"""Company endpoints (read-only): documents, clauses, people, profile.

Shapes follow frontend/lib/api/schemas/company.ts (contract sections 5 and 8).
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.engine.config import engine_settings
from app.engine.footprint import VERSION_SCOPE

router = APIRouter(prefix="/company", tags=["company"])

# backend vertical name -> frontend slug (keep in sync with frontend/lib/verticals.ts)
VERTICAL_SLUGS = {
    "compliance & legal": "compliance-legal",
    "policy & governance": "policy-governance",
    "operations & processes": "operations-processes",
    "environmental": "environmental-esg",
    "workforce & safety": "workforce-hr",
    # The other nine verticals the product offers. No synthetic document used them, but
    # a customer can upload into any of the 14, and an unmapped name was rejected with 422.
    "financial & reporting": "financial-reporting",
    "revenue & pricing": "revenue-pricing",
    "technology & systems": "technology-systems",
    "supply chain & procurement": "supply-chain-procurement",
    "risk & insurance": "risk-insurance",
    "strategic & competitive": "strategic-competitive",
    "reputational & stakeholder": "reputational-stakeholder",
    "contractual & third-party obligations": "contractual-third-party",
    "capital & infrastructure": "capital-infrastructure",
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


# ---------------------------------------------------------------- pure helpers
def vertical_slug(name: Optional[str]) -> str:
    if not name:
        return "unclassified"
    return VERTICAL_SLUGS.get(name.strip().lower(), "unclassified")


def doc_type_label(doc_class: Optional[str]) -> str:
    """Display label for `company_documents.doc_class` (e.g. "retention_schedule" ->
    "Retention Schedule"). The frontend's `doc_type` is a required string, so an
    unclassified document reads "Document"."""
    if not doc_class or not str(doc_class).strip():
        return "Document"
    return " ".join(w.capitalize() for w in str(doc_class).strip().replace("_", " ").split())


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


def build_document(row: dict, cited: list[str]) -> dict:
    """Every field comes from the database row (TDD 7.6): company_documents,
    its current document_versions row, and the people joins."""
    vname = row.get("vertical") or None
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
        "next_review": _iso(row.get("next_review")),
        "review_cycle": row.get("review_cycle") or None,
        "vertical": vertical_slug(vname),
        "vertical_name": vname,
        "owner": owner or blank(row.get("owner_id")),
        "reviewer": reviewer or blank(row.get("reviewer_id")),
        "approver": approver,
        "two_signature": row.get("approver_id") is None,
        # `monitored` means the CURRENT version is ingested; a document still in review
        # (no current version) is not monitored yet.
        "monitored": row.get("ingest_status") == "ingested",
        # What the UI needs to show a document that has no current version: the document's
        # lifecycle (pending / active / failed / retired) and its newest non-retired version.
        "lifecycle_state": row.get("lifecycle_state") or None,
        "has_current_version": row.get("version_status") is not None,
        "latest_version_no": row.get("latest_version_no"),
        "latest_version_status": row.get("latest_version_status"),
        "latest_ingest_status": row.get("latest_ingest_status"),
        "doc_type": doc_type_label(row.get("doc_class")),
        "doc_number": row.get("doc_number"),
        "cited_citations": cited,
    }


# ------------------------------------------------------------------------ SQL
_DOC_SQL = """
SELECT cd.doc_id, cd.title, cd.doc_class, cd.doc_number, cd.vertical, cd.review_cycle, cd.owner_id, cd.reviewer_id, cd.approver_id,
       cd.lifecycle_state,
       v.version, v.status, v.status AS version_status, v.effective_date, v.approved_date, v.law_as_of, v.next_review, v.ingest_status,
       lat.version_no AS latest_version_no, lat.status AS latest_version_status, lat.ingest_status AS latest_ingest_status,
       po.person_id AS o_pid, po.name AS o_name, po.title AS o_title, po.department AS o_dept, po.reports_to_id AS o_rt,
       pr.person_id AS r_pid, pr.name AS r_name, pr.title AS r_title, pr.department AS r_dept, pr.reports_to_id AS r_rt,
       pa.person_id AS a_pid, pa.name AS a_name, pa.title AS a_title, pa.department AS a_dept, pa.reports_to_id AS a_rt
FROM company.company_documents cd
LEFT JOIN company.document_versions v ON v.version_id = cd.current_version_id
LEFT JOIN LATERAL (
    SELECT lv.version_no, lv.status, lv.ingest_status
    FROM company.document_versions lv
    WHERE lv.company_id = cd.company_id AND lv.doc_id = cd.doc_id AND lv.status <> 'retired'
    ORDER BY lv.version_no DESC LIMIT 1
) lat ON true
LEFT JOIN company.people po ON po.company_id = cd.company_id AND po.person_id = cd.owner_id
LEFT JOIN company.people pr ON pr.company_id = cd.company_id AND pr.person_id = cd.reviewer_id
LEFT JOIN company.people pa ON pa.company_id = cd.company_id AND pa.person_id = cd.approver_id
WHERE cd.company_id = :cid {extra}
ORDER BY cd.doc_id
"""

_CITED_SQL = """
SELECT DISTINCT c.doc_id, cs.citation
FROM company.clauses c
JOIN company.company_documents d ON d.company_id = c.company_id AND d.doc_id = c.doc_id
JOIN company.clause_citations cc ON cc.clause_pk = c.clause_pk
JOIN public.code_sections cs ON cs.id = cc.code_section_id::int
WHERE c.company_id = :cid AND cc.resolution_status IN ('resolved','resolved_rule')
  AND cc.code_section_id ~ '^[0-9]+$' {extra}
  AND """ + VERSION_SCOPE + """
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
    return [build_document(dict(r), sorted(set(cited.get(r["doc_id"], [])))) for r in rows]


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
      SELECT c.*, d.current_version_id
      FROM company.clauses c
      JOIN company.company_documents d ON d.company_id = c.company_id AND d.doc_id = c.doc_id
      WHERE c.company_id = :cid AND c.doc_id = :doc_id
        AND """ + VERSION_SCOPE + """
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
    # TDD 7.6: regulator / utility_type come from company_attributes (writable via
    # PUT /company/attributes/{key}); nothing in this module reads files.
    regulator = str(by_key.get("regulator") or "")
    # Two different facts share the name "utility type": `utility_type` ("electric") is an
    # applicability attribute and must not change, while `business_utility_type`
    # ("electric_distribution") is how the company describes itself on the profile page.
    # Prefer the display value and fall back, so a company that only has the former still renders.
    utility = by_key.get("business_utility_type") or by_key.get("utility_type") or ""
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
