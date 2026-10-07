"""Task 2.1.2 — Reference data loaders.

Parses the P4 reference files from the company corpus:
  - company_profile.yaml   → upsert companies + company_attributes
  - people_directory.csv   → upsert people
  - document_register.csv  → parse into RegisterEntry list (returned for 2.2.1)
  - org_chart.md / company_fact_sheet.md → collected by collector (R2 only), not parsed here
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.company_ingest.collect.collector import SourceFile
from app.company_ingest.constants import Profile
from app.company_ingest.run_context import RunContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RegisterEntry:
    doc_id: str
    title: str
    version: str
    status: str
    effective_date: str | None
    approved_date: str | None
    law_as_of: str | None
    owner_id: str
    reviewer_id: str
    approver_id: str | None
    file_path: str
    regulatory_basis_sections: str  # raw value from CSV


# ---------------------------------------------------------------------------
# company_profile.yaml
# ---------------------------------------------------------------------------

def load_company_profile(yaml_path: Path, ctx: RunContext) -> dict:
    """Read company_profile.yaml and return the parsed dict (raw)."""
    with yaml_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data or {}


async def upsert_company(
    session: AsyncSession,
    company_id: str,
    name: str,
) -> None:
    """INSERT INTO company.companies ... ON CONFLICT (company_id) DO UPDATE SET name=..."""
    await session.execute(
        text(
            """
            INSERT INTO company.companies (company_id, name)
            VALUES (:company_id, :name)
            ON CONFLICT (company_id) DO UPDATE SET name = EXCLUDED.name
            """
        ),
        {"company_id": company_id, "name": name},
    )


async def upsert_company_attributes(
    session: AsyncSession,
    company_id: str,
    yaml_path: Path,
    ctx: RunContext,
) -> None:
    """Load applicability_attributes from company_profile.yaml and upsert into company.company_attributes."""
    profile_data = load_company_profile(yaml_path, ctx)

    # applicability_attributes is at the top level of the YAML
    attrs: dict[str, Any] = profile_data.get("applicability_attributes", {})
    if not attrs:
        ctx.issue(
            "warning",
            "reference",
            "no_applicability_attributes",
            f"No applicability_attributes found in {yaml_path.name}",
            path=str(yaml_path),
        )
        return

    source = "company_profile.yaml:applicability_attributes"

    for key, raw_value in attrs.items():
        value_text = str(raw_value)
        value_num: float | None = None
        value_bool: bool | None = None

        # Determine typed values
        if isinstance(raw_value, bool):
            value_bool = raw_value
        elif isinstance(raw_value, (int, float)):
            value_num = float(raw_value)
        else:
            # Try to parse numeric
            try:
                value_num = float(str(raw_value))
            except (ValueError, TypeError):
                pass

        await session.execute(
            text(
                """
                INSERT INTO company.company_attributes
                    (company_id, key, value_text, value_num, value_bool, source)
                VALUES
                    (:company_id, :key, :value_text, :value_num, :value_bool, :source)
                ON CONFLICT (company_id, key) DO UPDATE SET
                    value_text = EXCLUDED.value_text,
                    value_num  = EXCLUDED.value_num,
                    value_bool = EXCLUDED.value_bool,
                    source     = EXCLUDED.source
                """
            ),
            {
                "company_id": company_id,
                "key": key,
                "value_text": value_text,
                "value_num": value_num,
                "value_bool": value_bool,
                "source": source,
            },
        )

    ctx.count("company_attributes_upserted", len(attrs))


# ---------------------------------------------------------------------------
# people_directory.csv
# ---------------------------------------------------------------------------

_KNOWN_PEOPLE_HEADERS = {
    "person_id", "name", "title", "department", "reports_to_id",
    "email", "phone_ext", "location", "document_roles", "oncall_roles",
    "alternate_person_id",
}

_REQUIRED_PEOPLE_HEADERS = {
    "person_id", "name", "title", "department", "reports_to_id",
    "email", "oncall_roles", "alternate_person_id",
}


async def load_people(
    session: AsyncSession,
    company_id: str,
    csv_path: Path,
    ctx: RunContext,
) -> None:
    """Read people_directory.csv and upsert each row into company.people."""
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = set(reader.fieldnames or [])

        # Log unknown headers as info issues
        unknown = headers - _KNOWN_PEOPLE_HEADERS
        for h in sorted(unknown):
            ctx.issue(
                "info",
                "reference",
                "unknown_header",
                f"Unknown column '{h}' in {csv_path.name}",
                path=str(csv_path),
            )

        count = 0
        for row in reader:
            person_id = row.get("person_id", "").strip()
            if not person_id:
                continue

            # Parse oncall_roles: split on ';', strip whitespace, filter empty
            raw_oncall = row.get("oncall_roles", "").strip()
            oncall_roles = [r.strip() for r in raw_oncall.split(";") if r.strip()] if raw_oncall else []

            # Parse alternate_person_id: nullable
            raw_alt = row.get("alternate_person_id", "").strip()
            alternate_person_id = raw_alt if raw_alt else None

            await session.execute(
                text(
                    """
                    INSERT INTO company.people
                        (company_id, person_id, name, title, department,
                         reports_to_id, email, alternate_person_id, oncall_roles)
                    VALUES
                        (:company_id, :person_id, :name, :title, :department,
                         :reports_to_id, :email, :alternate_person_id, :oncall_roles)
                    ON CONFLICT (company_id, person_id) DO UPDATE SET
                        name               = EXCLUDED.name,
                        title              = EXCLUDED.title,
                        department         = EXCLUDED.department,
                        reports_to_id      = EXCLUDED.reports_to_id,
                        email              = EXCLUDED.email,
                        alternate_person_id = EXCLUDED.alternate_person_id,
                        oncall_roles       = EXCLUDED.oncall_roles
                    """
                ),
                {
                    "company_id": company_id,
                    "person_id": person_id,
                    "name": row.get("name", "").strip(),
                    "title": row.get("title", "").strip(),
                    "department": row.get("department", "").strip(),
                    "reports_to_id": row.get("reports_to_id", "").strip() or None,
                    "email": row.get("email", "").strip() or None,
                    "alternate_person_id": alternate_person_id,
                    "oncall_roles": oncall_roles,
                },
            )
            count += 1

    ctx.count("people_upserted", count)


# ---------------------------------------------------------------------------
# document_register.csv
# ---------------------------------------------------------------------------

def load_document_register(csv_path: Path, ctx: RunContext) -> list[RegisterEntry]:
    """Read document_register.csv and return a list of RegisterEntry objects.

    Does NOT write to any DB table; parsing only — the results are consumed by 2.2.1.
    """
    entries: list[RegisterEntry] = []

    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            doc_id = row.get("doc_id", "").strip()
            if not doc_id:
                continue

            def _nullable(col: str) -> str | None:
                val = row.get(col, "").strip()
                return val if val else None

            entries.append(
                RegisterEntry(
                    doc_id=doc_id,
                    title=row.get("title", "").strip(),
                    version=row.get("version", "").strip(),
                    status=row.get("status", "").strip(),
                    effective_date=_nullable("effective_date"),
                    approved_date=_nullable("approved_date"),
                    law_as_of=_nullable("law_as_of"),
                    owner_id=row.get("owner_id", "").strip(),
                    reviewer_id=row.get("reviewer_id", "").strip(),
                    approver_id=_nullable("approver_id"),
                    file_path=row.get("file_path", "").strip(),
                    regulatory_basis_sections=row.get("regulatory_basis_sections", "").strip(),
                )
            )

    ctx.count("register_entries_loaded", len(entries))
    return entries


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

# P4 filenames that are parsed (vs stored in R2 only)
_PROFILE_YAML = "company_profile.yaml"
_PEOPLE_CSV = "people_directory.csv"
_DOC_REGISTER_CSV = "document_register.csv"


async def load_reference_data(
    sources: list[SourceFile],
    session: AsyncSession,
    company_id: str,
    ctx: RunContext,
) -> list[RegisterEntry]:
    """Find P4 files in sources, process each, and return the RegisterEntry list.

    - company_profile.yaml → upsert company + attributes
    - people_directory.csv → upsert people
    - document_register.csv → parse and return RegisterEntry list
    - org_chart.md / company_fact_sheet.md → P4 but NOT parsed here (R2 only)
    """
    p4_files: dict[str, SourceFile] = {}
    for sf in sources:
        if sf.profile == Profile.P4_REFERENCE:
            p4_files[sf.abs_path.name] = sf

    register_entries: list[RegisterEntry] = []

    # 1. company_profile.yaml → company + attributes
    if _PROFILE_YAML in p4_files:
        sf = p4_files[_PROFILE_YAML]
        profile_data = load_company_profile(sf.abs_path, ctx)
        company_name = (
            profile_data.get("company", {}).get("legal_name", "")
            or profile_data.get("legal_name", company_id)
        )
        await upsert_company(session, company_id, company_name)
        await upsert_company_attributes(session, company_id, sf.abs_path, ctx)
    else:
        ctx.issue(
            "warning",
            "reference",
            "missing_company_profile",
            "company_profile.yaml not found in P4 sources",
        )

    # 2. people_directory.csv → people
    if _PEOPLE_CSV in p4_files:
        sf = p4_files[_PEOPLE_CSV]
        await load_people(session, company_id, sf.abs_path, ctx)
    else:
        ctx.issue(
            "warning",
            "reference",
            "missing_people_csv",
            "people_directory.csv not found in P4 sources",
        )

    # 3. document_register.csv → RegisterEntry list
    if _DOC_REGISTER_CSV in p4_files:
        sf = p4_files[_DOC_REGISTER_CSV]
        register_entries = load_document_register(sf.abs_path, ctx)
    else:
        ctx.issue(
            "warning",
            "reference",
            "missing_document_register",
            "document_register.csv not found in P4 sources",
        )

    return register_entries
