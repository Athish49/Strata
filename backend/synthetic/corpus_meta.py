"""Pure loaders for the synthetic demo corpus metadata (task 9.1 step 1 inputs).

Everything here only *reads* files under ``backend/synthetic/corpus``; nothing talks
to the API or a database. The seeder turns these values into HTTP calls.

* :func:`read_front_matter` - a document's own header (YAML, HTML-comment or
  marker style), exactly as the file states it. Nothing is back-filled from the
  register: a field the file does not state is ``None``.
* :func:`read_document_register` - ``_global/document_register.csv``.
* :func:`read_people` - ``_global/people_directory.csv`` including the
  ``document_roles`` ``DOC:role`` pairs (the source for document_role_assignments).
* :func:`read_company_profile` - ``_global/company_profile.yaml``: legal name,
  ``company.regulator``, ``business_model.utility_type`` and every
  ``applicability_attributes`` key with its type.
* :func:`doc_files` - the 12 demo documents -> ``.md`` source + register CSV(s).

Note the two different ``utility_type`` values in the profile:
``business_model.utility_type`` (``electric_distribution``) and
``applicability_attributes.utility_type`` (``electric``). They are returned
separately (``CompanyProfile.business_utility_type`` vs
``CompanyProfile.attributes["utility_type"]``) so a caller cannot silently let
one overwrite the other.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Union

import yaml

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
GLOBAL_DIR = CORPUS / "_global"
DOCS_DIR = CORPUS / "docs"
REGISTER_CSV = GLOBAL_DIR / "document_register.csv"
PEOPLE_CSV = GLOBAL_DIR / "people_directory.csv"
PROFILE_YAML = GLOBAL_DIR / "company_profile.yaml"

#: The 14 product verticals (display names). Must stay in sync with
#: ``app/api/company/routes.py`` ``VERTICAL_SLUGS`` (keys are these, lower-cased);
#: ``tests/synthetic/test_corpus_meta.py`` checks it.
CANONICAL_VERTICALS: tuple[str, ...] = (
    "Compliance & Legal",
    "Policy & Governance",
    "Operations & Processes",
    "Environmental",
    "Workforce & Safety",
    "Financial & Reporting",
    "Revenue & Pricing",
    "Technology & Systems",
    "Supply Chain & Procurement",
    "Risk & Insurance",
    "Strategic & Competitive",
    "Reputational & Stakeholder",
    "Contractual & Third-Party Obligations",
    "Capital & Infrastructure",
)
_VERTICAL_BY_KEY = {v.lower(): v for v in CANONICAL_VERTICALS}

#: The 12 demo documents seeded through the API (the register's 4 ``RPL-INF-*``
#: rows describe the corpus scaffolding itself and are not uploaded).
DEMO_DOC_IDS: tuple[str, ...] = (
    "RPL-CMP-REG-001",
    "RPL-CS-PRO-004",
    "RPL-CS-PRO-007",
    "RPL-CS-PRO-011",
    "RPL-DCC-PRO-003",
    "RPL-DO-PLN-002",
    "RPL-ENV-PRO-005",
    "RPL-LEG-RRS-001",
    "RPL-MTR-PGM-001",
    "RPL-REG-CAL-2025",
    "RPL-SAF-PRO-009",
    "RPL-TAR-GRR-012",
)

RegisterType = Literal["obligation", "event", "retention", "other"]

#: Register CSVs per document: (relative path, id column, register type).
_REGISTERS: dict[str, tuple[tuple[str, str, RegisterType], ...]] = {
    "RPL-CMP-REG-001": (("data/compliance_register_2024-12-31.csv", "obligation_id", "obligation"),),
    "RPL-LEG-RRS-001": (("data/retention_schedule_2024-12-31.csv", "rrs_id", "retention"),),
    "RPL-REG-CAL-2025": (("data/calendar_events_2025.csv", "event_id", "event"),),
}


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def canonical_vertical(name: str | None) -> str | None:
    """Register vertical -> one of :data:`CANONICAL_VERTICALS`, or ``None``."""
    if not name:
        return None
    return _VERTICAL_BY_KEY.get(name.strip().lower())


# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DocFrontMatter:
    doc_id: str
    title: str | None
    version: str | None
    status: str | None
    effective_date: str | None
    approved_date: str | None
    law_as_of: str | None
    next_review: str | None
    classification: str | None
    regulatory_basis: tuple[str, ...]
    supersedes: str | None
    owner_id: str | None
    reviewer_id: str | None
    approver_id: str | None


def _doc_id_from_path(md_path: Path) -> str:
    return md_path.stem.split("_v", 1)[0]


_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_PERSON_RE = re.compile(r"\b(P\d{2,})\b")
_BOLD_KV_RE = re.compile(r"\*\*([^*]+?):?\*\*:?\s*(.*?)\s*$")
_TABLE_KV_RE = re.compile(r"^\|\s*\*\*([^*|]+?)\*\*\s*\|\s*(.*?)\s*\|\s*$")
_COMMENT_RE = re.compile(r"^<!--(.*)-->\s*$")

#: normalised header key -> DocFrontMatter field
_KEY_FIELDS = {
    "title": "title", "document title": "title",
    "version": "version",
    "status": "status",
    "effective": "effective_date", "effective date": "effective_date",
    "approved": "approved_date", "approved date": "approved_date",
    "law as of": "law_as_of", "law as of date": "law_as_of",
    "next review": "next_review", "next review date": "next_review",
    "classification": "classification",
    "supersedes": "supersedes",
    "owner": "owner_id", "prepared by": "owner_id",
    "reviewer": "reviewer_id",
    "approver": "approver_id",
}
_DATE_FIELDS = {"effective_date", "approved_date", "law_as_of", "next_review"}
_PERSON_FIELDS = {"owner_id", "reviewer_id", "approver_id"}


def _norm_key(key: str) -> str:
    return re.sub(r"[\s_\-]+", " ", key.replace("*", "").strip().rstrip(":")).strip().lower()


def _header_pairs(header: str) -> list[tuple[str, str]]:
    """``(key, value)`` pairs from a non-YAML header block: ``**Key:** value``
    lines (several per line, ``|``-separated), ``| **Key** | value |`` rows and
    ``<!-- Key: value | Key: value -->`` comment lines."""
    pairs: list[tuple[str, str]] = []
    for line in header.splitlines():
        line = line.strip()
        m = _TABLE_KV_RE.match(line)
        if m:
            pairs.append((m.group(1), m.group(2).replace("**", "").strip()))
            continue
        cm_ = _COMMENT_RE.match(line)
        segments = cm_.group(1).split("|") if cm_ else (line.split(" | ") if "**" in line else [])
        for seg in segments:
            seg = seg.strip()
            bm = _BOLD_KV_RE.match(seg)
            if bm:
                pairs.append((bm.group(1), bm.group(2).replace("**", "").strip()))
            elif cm_ and ":" in seg:
                k, _, v = seg.partition(":")
                pairs.append((k, v.strip()))
    return pairs


def read_front_matter(md_path: str | Path) -> DocFrontMatter:
    """The header of one ``.md`` source, as the file states it (``None`` = not stated).

    Handles the three header styles the corpus uses: YAML front matter; an
    H1 + ``<!-- DOC:meta -->`` marker followed by ``**Key:** value`` lines or a
    ``| **Key** | value |`` table; and the tariff's ``<!-- ... -->`` comment
    header. A non-YAML header ends at the first ``---`` rule. (Implemented here
    rather than via ``app.company_ingest.parse.front_matter``, whose marker style
    decides "table style" by scanning the WHOLE remaining document, so for
    RPL-CMP-REG-001 and RPL-LEG-RRS-001 it returns no fields at all.)
    """
    md_path = Path(md_path)
    doc_id = _doc_id_from_path(md_path)
    text = md_path.read_text(encoding="utf-8").lstrip("\ufeff")
    values: dict[str, object] = {}
    basis: tuple[str, ...] = ()

    if text.startswith("---\n"):
        close = re.search(r"^---\s*$", text[4:], re.MULTILINE)
        data = yaml.safe_load(text[4:4 + close.start()]) if close else {}
        data = data if isinstance(data, dict) else {}
        for key, fld in (("title", "title"), ("version", "version"), ("status", "status"),
                         ("effective_date", "effective_date"), ("approved_date", "approved_date"),
                         ("law_as_of", "law_as_of"), ("next_review", "next_review"),
                         ("classification", "classification"), ("supersedes", "supersedes")):
            if data.get(key) is not None:
                values[fld] = str(data[key]).strip() or None
        for key in ("owner", "reviewer", "approver"):
            val = data.get(key)
            if isinstance(val, dict):
                val = val.get("id")
            if val:
                m = _PERSON_RE.search(str(val))
                values[f"{key}_id"] = m.group(1) if m else None
        rb = data.get("regulatory_basis")
        if isinstance(rb, list):
            basis = tuple(str(x).strip() for x in rb if x is not None)
        elif rb:
            basis = (str(rb).strip(),)
    else:
        rule = re.search(r"^---\s*$", text, re.MULTILINE)
        header = text[: rule.start()] if rule else ""
        for key, raw in _header_pairs(header):
            fld = _KEY_FIELDS.get(_norm_key(key))
            if fld is None or fld in values or not raw:
                continue
            if fld in _DATE_FIELDS:
                m = _DATE_RE.search(raw)
                values[fld] = m.group(0) if m else raw
            elif fld in _PERSON_FIELDS:
                m = _PERSON_RE.search(raw)
                values[fld] = m.group(1) if m else None
            else:
                values[fld] = raw

    return DocFrontMatter(
        doc_id=doc_id,
        title=values.get("title"),
        version=values.get("version"),
        status=values.get("status"),
        effective_date=values.get("effective_date"),
        approved_date=values.get("approved_date"),
        law_as_of=values.get("law_as_of"),
        next_review=values.get("next_review"),
        classification=values.get("classification"),
        regulatory_basis=basis,
        supersedes=values.get("supersedes"),
        owner_id=values.get("owner_id"),
        reviewer_id=values.get("reviewer_id"),
        approver_id=values.get("approver_id"),
    )


# ---------------------------------------------------------------------------
# Document register
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegisterEntry:
    doc_id: str
    title: str
    vertical: str | None  # as written in the CSV
    canonical_vertical: str | None  # one of CANONICAL_VERTICALS, None if unmapped
    version: str | None
    status: str | None
    effective_date: str | None
    approved_date: str | None
    law_as_of: str | None
    owner_id: str | None
    reviewer_id: str | None
    approver_id: str | None
    review_cycle: str | None
    next_review_date: str | None
    supersedes_version: str | None
    supersedes_date: str | None
    file_path: str | None  # relative to backend/synthetic/


def read_document_register(path: str | Path = REGISTER_CSV) -> list[RegisterEntry]:
    entries: list[RegisterEntry] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            g = lambda k: _blank_to_none(row.get(k))  # noqa: E731
            entries.append(RegisterEntry(
                doc_id=row["doc_id"].strip(),
                title=row["title"].strip(),
                vertical=g("vertical"),
                canonical_vertical=canonical_vertical(row.get("vertical")),
                version=g("version"),
                status=g("status"),
                effective_date=g("effective_date"),
                approved_date=g("approved_date"),
                law_as_of=g("law_as_of"),
                owner_id=g("owner_id"),
                reviewer_id=g("reviewer_id"),
                approver_id=g("approver_id"),
                review_cycle=g("review_cycle"),
                next_review_date=g("next_review_date"),
                supersedes_version=g("supersedes_version"),
                supersedes_date=g("supersedes_date"),
                file_path=g("file_path"),
            ))
    return entries


def unmapped_register_verticals(entries: list[RegisterEntry] | None = None) -> dict[str, str | None]:
    """``doc_id -> vertical`` for every register row whose vertical is not a product vertical."""
    entries = read_document_register() if entries is None else entries
    return {e.doc_id: e.vertical for e in entries if e.canonical_vertical is None}


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentRole:
    doc_id: str
    role: str  # owner | reviewer | approver


@dataclass(frozen=True)
class Person:
    person_id: str
    name: str
    title: str | None
    department: str | None
    reports_to_id: str | None
    email: str | None
    phone_ext: str | None
    location: str | None
    document_roles: tuple[DocumentRole, ...]
    oncall_roles: tuple[str, ...]
    alternate_person_id: str | None


def _parse_document_roles(raw: str | None) -> tuple[DocumentRole, ...]:
    roles: list[DocumentRole] = []
    for item in (raw or "").split(";"):
        item = item.strip()
        if not item:
            continue
        doc_id, sep, role = item.rpartition(":")
        if not sep or not doc_id or not role:
            raise ValueError(f"malformed document_roles entry {item!r}")
        roles.append(DocumentRole(doc_id.strip(), role.strip().lower()))
    return tuple(roles)


def read_people(path: str | Path = PEOPLE_CSV) -> list[Person]:
    people: list[Person] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            g = lambda k: _blank_to_none(row.get(k))  # noqa: E731
            people.append(Person(
                person_id=row["person_id"].strip(),
                name=row["name"].strip(),
                title=g("title"),
                department=g("department"),
                reports_to_id=g("reports_to_id"),
                email=g("email"),
                phone_ext=g("phone_ext"),
                location=g("location"),
                document_roles=_parse_document_roles(row.get("document_roles")),
                oncall_roles=tuple(r.strip() for r in (row.get("oncall_roles") or "").split(";") if r.strip()),
                alternate_person_id=g("alternate_person_id"),
            ))
    return people


def departments(people: list[Person] | None = None) -> list[str]:
    """Distinct departments, in first-seen order."""
    people = read_people() if people is None else people
    seen: dict[str, None] = {}
    for p in people:
        if p.department:
            seen.setdefault(p.department, None)
    return list(seen)


# ---------------------------------------------------------------------------
# Company profile
# ---------------------------------------------------------------------------

AttrType = Literal["bool", "number", "string"]
AttrValue = Union[bool, int, float, str]


@dataclass(frozen=True)
class CompanyAttribute:
    key: str
    type: AttrType
    value: AttrValue


@dataclass(frozen=True)
class CompanyProfile:
    legal_name: str
    regulator: str | None  # company.regulator
    business_utility_type: str | None  # business_model.utility_type
    attributes: dict[str, CompanyAttribute] = field(default_factory=dict)  # applicability_attributes


def _attr_type(value: object) -> AttrType:
    # bool before number: ``True`` is an ``int``.
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    raise TypeError(f"unsupported applicability attribute value {value!r}")


def read_company_profile(path: str | Path = PROFILE_YAML) -> CompanyProfile:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    company = data.get("company") or {}
    business = data.get("business_model") or {}
    attrs = {
        str(k): CompanyAttribute(str(k), _attr_type(v), v)
        for k, v in (data.get("applicability_attributes") or {}).items()
    }
    return CompanyProfile(
        legal_name=str(company["legal_name"]),
        regulator=_blank_to_none(company.get("regulator")),
        business_utility_type=_blank_to_none(business.get("utility_type")),
        attributes=attrs,
    )


# ---------------------------------------------------------------------------
# Document files
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegisterFile:
    path: Path
    id_column: str
    register_type: RegisterType


@dataclass(frozen=True)
class DocFiles:
    doc_id: str
    md_path: Path
    registers: tuple[RegisterFile, ...]


def doc_files(docs_dir: str | Path = DOCS_DIR) -> dict[str, DocFiles]:
    """The 12 demo documents -> their ``.md`` source and register CSV(s)."""
    docs_dir = Path(docs_dir)
    out: dict[str, DocFiles] = {}
    for doc_id in DEMO_DOC_IDS:
        mds = sorted((docs_dir / doc_id).glob(f"{doc_id}_v*.md"))
        if len(mds) != 1:
            raise FileNotFoundError(f"expected exactly one {doc_id}_v*.md, found {mds}")
        regs = tuple(
            RegisterFile(docs_dir / doc_id / rel, id_col, rtype)
            for rel, id_col, rtype in _REGISTERS.get(doc_id, ())
        )
        for r in regs:
            if not r.path.is_file():
                raise FileNotFoundError(r.path)
        out[doc_id] = DocFiles(doc_id, mds[0], regs)
    return out
