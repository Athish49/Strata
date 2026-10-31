#!/usr/bin/env python
"""Seed the synthetic demo company THROUGH THE REAL HTTP API (task 9.1).

    backend/.venv/bin/python backend/synthetic/seed.py --base-url http://localhost:8000
    backend/.venv/bin/python backend/synthetic/seed.py --plan        # print the plan, no HTTP

This is the proof that the customer path works: it uses ONLY HTTP (no database
access, nothing imported from ``app/``), so it runs against any deployment, or
in-process through ``httpx.ASGITransport`` (``synthetic/rehearsal.py`` does that).

Order (each step is read-compare-skip, so a re-run writes nothing):

1. People. ``P01`` (the President) is created first by first-administrator
   bootstrap (``acting_person_id == person_id`` on an empty company), then the
   departments (distinct ``department`` values) and every other person from
   ``people_directory.csv``, acting as P01.
2. Company: ``PATCH /company/profile`` (legal name), then every
   ``applicability_attributes`` key plus ``regulator`` and
   ``business_utility_type`` via ``PUT /company/attributes/{key}``.
3. Approval policies (see :data:`POLICIES`).
4. Documents in register order: the 12 ``.md`` sources as generated DOCX, each
   register CSV as its own document right after its parent (15 in total), uploaded
   as the document's owner with ``vertical``/``doc_class``/``title``/``doc_number``/
   ``law_as_of`` and an explicit ``policy_id``.
5. Per document: role assignments, metadata PATCH (review cycle + version dates,
   BEFORE approval), poll the ingest job, sign every approval step in order as the
   real role holder, verify the version is ``effective``/``is_current``.

Idempotent and resumable: existing documents are found by ``doc_number`` and
finished from wherever they stopped; a 409 duplicate counts as success. Exits
non-zero on any failure.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from synthetic import corpus_meta as cm  # noqa: E402
from synthetic.make_docx import build_docx  # noqa: E402

ADMIN = "P01"
DOCX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

#: Third segment of an RPL id -> ``DocClass`` value (``app/company_ingest/constants.py``).
#: ``PGM`` (RPL-MTR-PGM-001, "Meter Testing Program Plan") is a plan.
TYPE_DOC_CLASS = {
    "PRO": "procedure",
    "PLN": "plan",
    "PGM": "plan",
    "GRR": "tariff",
    "REG": "register",
    "CAL": "calendar",
    "RRS": "retention_schedule",
}
#: Register type -> doc_class of the CSV document.
REGISTER_DOC_CLASS = {"obligation": "register", "event": "calendar", "retention": "retention_schedule"}
#: Declared citation columns per register (TDD §3.3). The retention schedule's
#: regulatory citations live in ``retention_basis`` ("170 IAC 4-1-3; IC 8-1-2-40");
#: its ``regulatory_authority`` column only holds the agency name.
REGISTER_CITATION_COLUMNS = {
    "obligation_id": ["citation"],
    "event_id": ["citation"],
    "rrs_id": ["retention_basis"],
}

#: Approval policies. Both are company-wide (no vertical/doc_class scope) and the
#: seeder always passes ``policy_id`` explicitly, because the corpus needs two chains
#: inside ONE (vertical, doc_class) pair: RPL-CS-PRO-004 has an approver, while
#: RPL-CS-PRO-007 / RPL-CS-PRO-011 are two-signature documents (owner + reviewer, no
#: approver, per org_chart.md). ``select_policy`` breaks the tie by name, so a UI
#: upload with no explicit policy gets "Document control" ("D" < "T").
POLICIES: list[dict[str, Any]] = [
    {"key": "default", "name": "Document control — reviewer then approver",
     "steps": ["reviewer", "approver"]},
    {"key": "two_signature", "name": "Two-signature — owner then reviewer",
     "steps": ["owner", "reviewer"]},
]

ROLES = ("owner", "reviewer", "approver")


class SeedError(RuntimeError):
    pass


# =========================================================================== the plan
@dataclass
class DocPlan:
    doc_number: str           # the RPL id (or "<RPL id>#register")
    parent_id: str            # the RPL id the metadata/roles come from
    title: str
    vertical: str
    doc_class: str
    law_as_of: Optional[str]
    review_cycle: Optional[str]
    next_review: Optional[str]
    effective_date: Optional[str]
    approved_date: Optional[str]
    roles: dict[str, str]     # role -> person_id
    policy_key: str
    path: Path
    kind: str                 # "docx" | "csv"
    register_spec: Optional[dict] = None

    @property
    def filename(self) -> str:
        if self.kind == "csv":
            return self.path.name
        return f"{self.parent_id}.docx"

    def signers(self) -> list[str]:
        steps = next(p["steps"] for p in POLICIES if p["key"] == self.policy_key)
        return [self.roles[r] for r in steps]


def doc_class_for(rpl_id: str) -> str:
    parts = rpl_id.split("-")
    if len(parts) < 3 or parts[2] not in TYPE_DOC_CLASS:
        raise SeedError(f"cannot derive doc_class from {rpl_id!r} (type code {parts[2:3]})")
    return TYPE_DOC_CLASS[parts[2]]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def roles_by_doc(people: list[cm.Person]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for p in people:
        for r in p.document_roles:
            prev = out.setdefault(r.doc_id, {}).get(r.role)
            if prev and prev != p.person_id:
                raise SeedError(f"{r.doc_id}: two {r.role}s ({prev}, {p.person_id})")
            out[r.doc_id][r.role] = p.person_id
    return out


def build_plan() -> list[DocPlan]:
    """The 15 documents, in register order, each register CSV right after its parent."""
    register = {e.doc_id: e for e in cm.read_document_register()}
    files = cm.doc_files()
    roles = roles_by_doc(cm.read_people())
    order = [d for d in register if d in files]
    if sorted(order) != sorted(cm.DEMO_DOC_IDS):
        raise SeedError(f"register rows do not cover the demo documents: {order}")
    plan: list[DocPlan] = []
    for rpl in order:
        e, f = register[rpl], files[rpl]
        r = roles.get(rpl, {})
        # people_directory.document_roles and the register must agree (they are the
        # source of truth; the .md front matter is not).
        for role in ROLES:
            reg_val = getattr(e, f"{role}_id")
            if r.get(role) != reg_val:
                raise SeedError(f"{rpl}: {role} is {r.get(role)!r} in people_directory "
                                f"but {reg_val!r} in the register")
        if not e.canonical_vertical:
            raise SeedError(f"{rpl}: register vertical {e.vertical!r} is not a product vertical")
        if "owner" not in r or "reviewer" not in r:
            raise SeedError(f"{rpl}: needs at least an owner and a reviewer")
        common = dict(parent_id=rpl, vertical=e.canonical_vertical, law_as_of=e.law_as_of,
                      review_cycle=e.review_cycle, next_review=e.next_review_date,
                      effective_date=e.effective_date, approved_date=e.approved_date,
                      roles=dict(r), policy_key="default" if "approver" in r else "two_signature")
        plan.append(DocPlan(doc_number=rpl, title=e.title, doc_class=doc_class_for(rpl),
                            path=f.md_path, kind="docx", **common))
        for reg in f.registers:
            spec = {"register_type": reg.register_type, "id_column": reg.id_column,
                    "citation_columns": REGISTER_CITATION_COLUMNS[reg.id_column]}
            plan.append(DocPlan(doc_number=f"{rpl}#register", title=f"{e.title} — Register",
                                doc_class=REGISTER_DOC_CLASS[reg.register_type],
                                path=reg.path, kind="csv", register_spec=spec, **common))
    return plan


# =========================================================================== HTTP
@dataclass
class Api:
    client: httpx.AsyncClient
    log: Callable[[str], None] = print
    writes: int = 0
    write_log: list[str] = field(default_factory=list)

    async def call(self, method: str, path: str, *, ok=(200, 201), **kw) -> httpx.Response:
        res = await self.client.request(method, path, **kw)
        if method != "GET":
            self.writes += 1
            self.write_log.append(f"{method} {path} -> {res.status_code}")
        if res.status_code not in ok:
            raise SeedError(f"{method} {path} -> {res.status_code}: {res.text[:800]}")
        return res

    async def get(self, path: str, **kw) -> Any:
        return (await self.call("GET", path, ok=(200,), **kw)).json()


# =========================================================================== results
@dataclass
class DocResult:
    doc_number: str
    doc_id: str = ""
    action: str = ""
    version_status: str = ""
    is_current: bool = False
    clauses: Optional[int] = None
    citations: Optional[int] = None
    resolved: Optional[int] = None
    signers: str = ""


@dataclass
class SeedReport:
    people_created: int = 0
    people_updated: int = 0
    departments_created: int = 0
    attributes_written: int = 0
    policies_created: int = 0
    documents: list[DocResult] = field(default_factory=list)
    writes: int = 0
    seconds: float = 0.0

    def table(self) -> str:
        head = ("doc_number", "doc_id", "action", "status", "current", "clauses", "cites", "resolved", "signed by")
        rows = [head] + [(d.doc_number, d.doc_id, d.action, d.version_status, "yes" if d.is_current else "NO",
                          "" if d.clauses is None else str(d.clauses),
                          "" if d.citations is None else str(d.citations),
                          "" if d.resolved is None else str(d.resolved), d.signers)
                         for d in self.documents]
        widths = [max(len(str(r[i])) for r in rows) for i in range(len(head))]
        fmt = lambda r: "  ".join(str(c).ljust(w) for c, w in zip(r, widths))  # noqa: E731
        lines = [fmt(rows[0]), "  ".join("-" * w for w in widths)] + [fmt(r) for r in rows[1:]]
        lines.append(f"people +{self.people_created} (updated {self.people_updated}), departments "
                     f"+{self.departments_created}, attributes written {self.attributes_written}, "
                     f"policies +{self.policies_created}, HTTP writes {self.writes}, {self.seconds:.1f}s")
        return "\n".join(lines)


# =========================================================================== steps
_PERSON_FIELDS = ("name", "title", "department", "department_id", "reports_to_id", "email",
                  "alternate_person_id")


def _person_body(p: cm.Person, dept_ids: dict[str, str]) -> dict:
    return {"person_id": p.person_id, "name": p.name, "title": p.title, "department": p.department,
            "department_id": dept_ids.get(p.department or ""), "reports_to_id": p.reports_to_id,
            "email": p.email, "alternate_person_id": p.alternate_person_id, "is_active": True}


async def seed_people(api: Api, rep: SeedReport) -> None:
    people = cm.read_people()
    by_id = {p.person_id: p for p in people}
    if ADMIN not in by_id:
        raise SeedError(f"{ADMIN} is not in people_directory.csv")
    dept_ids = {d: _slug(d) for d in cm.departments(people)}
    existing = {p["person_id"]: p for p in await api.get("/company/org/people")}

    # 1. P01 first: bootstrap (self-registration) on an empty company.
    if ADMIN not in existing:
        if existing:
            raise SeedError(f"{ADMIN} is missing but the company already has people "
                            f"({', '.join(sorted(existing))}); cannot act as {ADMIN}")
        res = await api.call("POST", "/company/people", ok=(201, 409),
                             json={**_person_body(by_id[ADMIN], dept_ids), "acting_person_id": ADMIN})
        rep.people_created += res.status_code == 201
        api.log(f"  person {ADMIN} bootstrapped (first administrator)")
        existing = {p["person_id"]: p for p in await api.get("/company/org/people")}

    # 2. Departments.
    have = {d["department_id"] for d in await api.get("/company/departments")}
    for name, did in dept_ids.items():
        if did in have:
            continue
        res = await api.call("POST", "/company/departments", ok=(201, 409),
                             json={"department_id": did, "name": name, "acting_person_id": ADMIN})
        rep.departments_created += res.status_code == 201

    # 3. Everyone (P01 included, for read-compare-patch of its fields).
    for p in people:
        want = _person_body(p, dept_ids)
        cur = existing.get(p.person_id)
        if cur is None:
            res = await api.call("POST", "/company/people", ok=(201, 409),
                                 json={**want, "acting_person_id": ADMIN})
            rep.people_created += res.status_code == 201
            continue
        diff = {k: want[k] for k in _PERSON_FIELDS if want[k] is not None and cur.get(k) != want[k]}
        if cur.get("is_active") is False:
            diff["is_active"] = True
        if diff:
            await api.call("PATCH", f"/company/people/{p.person_id}",
                           json={**diff, "acting_person_id": ADMIN})
            rep.people_updated += 1
    api.log(f"  people: {len(people)} in directory, created {rep.people_created}, "
            f"updated {rep.people_updated}; departments created {rep.departments_created}")


def _attr_matches(row: dict, value: Any) -> bool:
    if isinstance(value, bool):
        return row.get("value_bool") is value
    if isinstance(value, (int, float)):
        return row.get("value_num") is not None and float(row["value_num"]) == float(value)
    return row.get("value_text") == value


async def seed_company(api: Api, rep: SeedReport) -> None:
    prof = cm.read_company_profile()
    if (await api.get("/company/profile")).get("name") != prof.legal_name:
        await api.call("PATCH", "/company/profile",
                       json={"name": prof.legal_name, "acting_person_id": ADMIN})
    wanted: dict[str, Any] = {k: a.value for k, a in prof.attributes.items()}
    if not prof.regulator or not prof.business_utility_type:
        raise SeedError("company_profile.yaml lacks company.regulator or business_model.utility_type")
    # `regulator` / `business_utility_type` are profile facts, not applicability ones; the
    # applicability `utility_type` ("electric") is kept as is.
    wanted["regulator"] = prof.regulator
    wanted["business_utility_type"] = prof.business_utility_type
    stored = {r["key"]: r for r in await api.get("/company/attributes")}
    for key, value in wanted.items():
        if key in stored and _attr_matches(stored[key], value):
            continue
        await api.call("PUT", f"/company/attributes/{key}",
                       json={"value": value, "acting_person_id": ADMIN})
        rep.attributes_written += 1
    api.log(f"  company: {prof.legal_name}; {len(wanted)} attributes "
            f"({rep.attributes_written} written)")


async def seed_policies(api: Api, rep: SeedReport) -> dict[str, str]:
    existing = {p["name"]: p for p in await api.get("/company/approval-policies")}
    ids: dict[str, str] = {}
    for pol in POLICIES:
        steps = [{"step_no": i, "required_role": r} for i, r in enumerate(pol["steps"], 1)]
        cur = existing.get(pol["name"])
        if cur is None:
            res = await api.call("POST", "/company/approval-policies", ok=(201,),
                                 json={"name": pol["name"], "steps": steps, "acting_person_id": ADMIN})
            cur = res.json()
            rep.policies_created += 1
        elif [s["required_role"] for s in cur["steps"]] != pol["steps"]:
            await api.call("PUT", f"/company/approval-policies/{cur['policy_id']}/steps",
                           json={"steps": steps, "acting_person_id": ADMIN})
        ids[pol["key"]] = cur["policy_id"]
    api.log("  policies: " + "; ".join(f"{p['name']} [{' -> '.join(p['steps'])}]" for p in POLICIES))
    return ids


async def _poll_job(api: Api, job_id: str, timeout_s: float, interval_s: float) -> dict:
    deadline = time.monotonic() + timeout_s
    while True:
        body = await api.get(f"/company/ingest-jobs/{job_id}")
        state = body["job"]["state"]
        if state == "succeeded":
            return body
        if state == "failed":
            raise SeedError(f"ingest job {job_id} ({body['job']['doc_id']}) FAILED: {body['job']['error']}")
        if time.monotonic() > deadline:
            raise SeedError(f"ingest job {job_id} still {state!r} after {timeout_s:.0f}s")
        await asyncio.sleep(interval_s)


async def _upload(api: Api, d: DocPlan, policy_id: str) -> dict:
    raw = build_docx(d.path, title=d.title) if d.kind == "docx" else d.path.read_bytes()
    ctype = DOCX_CT if d.kind == "docx" else "text/csv"
    data = {"vertical": d.vertical, "doc_class": d.doc_class, "title": d.title,
            "doc_number": d.doc_number, "acting_person_id": d.roles["owner"], "policy_id": policy_id}
    if d.law_as_of:
        data["law_as_of"] = d.law_as_of
    if d.register_spec is not None:
        data["register_spec"] = json.dumps(d.register_spec)
    res = await api.call("POST", "/company/documents", ok=(202, 409),
                         files={"file": (d.filename, raw, ctype)}, data=data)
    body = res.json()
    if res.status_code == 409 and body.get("status") != "duplicate":
        raise SeedError(f"upload of {d.doc_number} -> 409: {body}")
    return {"status": res.status_code, **body}


def _latest_version(versions: dict) -> Optional[dict]:
    live = [v for v in versions["versions"] if v["status"] != "retired"]
    return live[0] if live else None  # newest first


async def _finish_document(api: Api, d: DocPlan, doc_id: str, policy_id: str, res: DocResult,
                           job_timeout: float, poll_interval: float) -> None:
    versions = await api.get(f"/company/documents/{doc_id}/versions")
    v = _latest_version(versions)
    if v is None:
        raise SeedError(f"{d.doc_number} ({doc_id}) has no non-retired version; "
                        "its upload was cancelled or rejected - resolve it by hand")
    job_id = (v.get("ingest_job") or {}).get("job_id")
    if job_id is None:
        raise SeedError(f"{d.doc_number} ({doc_id}) version {v['version_no']} has no ingest job")
    job = await _poll_job(api, job_id, job_timeout, poll_interval)
    st = job.get("stats") or {}
    res.clauses, res.citations, res.resolved = (st.get("clause_count"), st.get("citations_total"),
                                                st.get("citations_resolved"))

    # Roles (needed before anyone can sign: the steps were opened unassigned at upload).
    held = {(r["role"], r["person_id"]) for r in await api.get(f"/company/documents/{doc_id}/roles")}
    for role, pid in d.roles.items():
        if (role, pid) not in held:
            await api.call("POST", f"/company/documents/{doc_id}/roles", ok=(201,),
                           json={"person_id": pid, "role": role, "acting_person_id": ADMIN})

    # Metadata: review cycle + version dates, BEFORE approval (promotion keeps them).
    doc = await api.get(f"/company/documents/{doc_id}")
    want_doc = {"review_cycle": d.review_cycle}
    want_ver = {"next_review": d.next_review, "effective_date": d.effective_date,
                "approved_date": d.approved_date}
    patch = {k: val for k, val in want_doc.items() if val is not None and doc.get(k) != val}
    if not v["is_current"]:
        patch.update({k: val for k, val in want_ver.items() if val is not None})
        if patch.keys() & want_ver.keys():
            patch["version_id"] = v["version_id"]
    else:
        patch.update({k: val for k, val in want_ver.items() if val is not None and doc.get(k) != val})
    if patch:
        await api.call("PATCH", f"/company/documents/{doc_id}", json={**patch, "acting_person_id": ADMIN})

    # Approval: sign every open step in order as the real role holder.
    appr = v.get("approval") or {}
    signed: list[str] = []
    if appr.get("request_id"):
        req = await api.get(f"/company/approval-requests/{appr['request_id']}")
        if req.get("policy_id") != policy_id:
            raise SeedError(f"{d.doc_number}: approval request {req['request_id']} uses policy "
                            f"{req.get('policy_id')}, expected {policy_id}")
        if req["state"] == "open":
            for step in sorted(req["steps"], key=lambda s: s["step_no"]):
                if step["decision"] is not None:
                    continue
                signer = step["assignee_person_id"] or d.roles.get(step["required_role"])
                if not signer:
                    raise SeedError(f"{d.doc_number}: nobody holds {step['required_role']!r} "
                                    f"for step {step['step_no']}")
                await api.call("POST", f"/company/approval-requests/{req['request_id']}"
                               f"/steps/{step['step_no']}/decision", ok=(200,),
                               json={"decision": "approved", "acting_person_id": signer,
                                     "note": "Seeded from the document register"})
                signed.append(f"{step['required_role']}:{signer}")
        elif req["state"] != "approved":
            raise SeedError(f"{d.doc_number}: approval request is {req['state']!r}")
    res.signers = ", ".join(signed) if signed else "-"

    # Verify.
    final = _latest_version(await api.get(f"/company/documents/{doc_id}/versions"))
    res.version_status, res.is_current = final["status"], bool(final["is_current"])
    if not (final["is_current"] and final["status"] == "effective"):
        raise SeedError(f"{d.doc_number} ({doc_id}) version {final['version_no']} is "
                        f"{final['status']!r}, is_current={final['is_current']} after approval")


async def seed_documents(api: Api, rep: SeedReport, policy_ids: dict[str, str], *,
                         job_timeout: float, poll_interval: float) -> None:
    plan = build_plan()
    docs = {d["doc_number"]: d for d in await api.get("/company/documents") if d.get("doc_number")}
    for i, d in enumerate(plan, 1):
        res = DocResult(doc_number=d.doc_number)
        rep.documents.append(res)
        pid = policy_ids[d.policy_key]
        cur = docs.get(d.doc_number)
        if cur is not None and cur.get("has_current_version") and cur.get("lifecycle_state") == "active":
            res.action = "skipped"
        if cur is None:
            up = await _upload(api, d, pid)
            if up["status"] == 409:
                res.action = "duplicate"
                docs = {x["doc_number"]: x for x in await api.get("/company/documents") if x.get("doc_number")}
                cur = next((x for x in docs.values() if x["doc_id"] == up.get("doc_id")), None)
                if cur is None or cur.get("doc_number") != d.doc_number:
                    raise SeedError(f"{d.doc_number}: content already stored as {up.get('doc_id')} "
                                    f"under doc_number {cur and cur.get('doc_number')!r}")
            else:
                res.action = "created"
                cur = {"doc_id": up["doc_id"]}
        elif not res.action:
            res.action = "resumed"
        res.doc_id = cur["doc_id"]
        await _finish_document(api, d, res.doc_id, pid, res, job_timeout, poll_interval)
        api.log(f"  [{i:2}/{len(plan)}] {d.doc_number:28} {res.doc_id}  {res.action:9} "
                f"{d.doc_class:18} clauses={res.clauses} signed={res.signers}")


async def seed(client: httpx.AsyncClient, *, log: Callable[[str], None] = print,
               job_timeout: float = 1800.0, poll_interval: float = 2.0) -> SeedReport:
    """Seed the demo company through *client* (any base URL / transport). Raises
    :class:`SeedError` on the first failure."""
    t0 = time.monotonic()
    api = Api(client, log=log)
    rep = SeedReport()
    log("seed: people and departments")
    await seed_people(api, rep)
    log("seed: company profile and attributes")
    await seed_company(api, rep)
    log("seed: approval policies")
    policy_ids = await seed_policies(api, rep)
    log("seed: documents")
    await seed_documents(api, rep, policy_ids, job_timeout=job_timeout, poll_interval=poll_interval)
    rep.writes = api.writes
    rep.seconds = time.monotonic() - t0
    return rep


# =========================================================================== CLI
def _print_plan() -> None:
    for d in build_plan():
        log_roles = ", ".join(f"{k}={v}" for k, v in d.roles.items())
        print(f"{d.doc_number:28} {d.kind:4} {d.doc_class:18} {d.vertical:24} {d.policy_key:13} "
              f"{log_roles}  signers={'/'.join(d.signers())}")


async def _main(args) -> int:
    async with httpx.AsyncClient(base_url=args.base_url, timeout=httpx.Timeout(args.http_timeout)) as c:
        try:
            rep = await seed(c, job_timeout=args.job_timeout, poll_interval=args.poll_interval)
        except SeedError as exc:
            print(f"SEED FAILED: {exc}", file=sys.stderr)
            return 1
    print("\n" + rep.table())
    bad = [d for d in rep.documents if not (d.is_current and d.version_status == "effective")]
    if len(rep.documents) != 15 or bad:
        print(f"SEED INCOMPLETE: {len(rep.documents)} documents, not effective: "
              f"{[d.doc_number for d in bad]}", file=sys.stderr)
        return 1
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Seed the demo company through the HTTP API.")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--plan", action="store_true", help="print the document plan and exit (no HTTP)")
    ap.add_argument("--job-timeout", type=float, default=1800.0, help="seconds to wait per ingest job")
    ap.add_argument("--poll-interval", type=float, default=2.0)
    ap.add_argument("--http-timeout", type=float, default=600.0)
    args = ap.parse_args(argv)
    if args.plan:
        _print_plan()
        return 0
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())
