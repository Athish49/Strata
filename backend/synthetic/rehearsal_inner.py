"""The ``--inner`` stage of ``synthetic/rehearsal.py`` (task 9.1, part C4/C5).

Runs in the child process ``rehearsal.outer()`` starts with ``child_env()``: the
scratch ``DATABASE_URL``, dummy ``QDRANT_*``/``R2_*``/``LLM_API_KEY`` values, an
empty working directory (pydantic-settings finds no ``.env``) and ``HOME`` in the
scratch dir. Inside this ONE interpreter:

* every non-loopback socket ``connect`` and every non-loopback name lookup is
  refused and recorded (:class:`NetGuard`) - installed before ``app`` is imported;
* R2 is ``moto`` (``mock_aws()``), with ``store.r2._get_client`` returning a plain
  ``us-east-1`` client exactly as ``tests/company_ingest/test_r2.py`` does (moto
  does not intercept a custom ``endpoint_url``);
* Qdrant is the library's own ``QdrantClient(location=":memory:")`` returned by
  ``index.upsert._make_client`` - the seam every production path goes through
  (``promote.reindex_document`` -> ``_upsert._make_client()``), and a real store:
  upserts, the filtered delete-and-replace sweep and the payload scroll all run.
  ``ensure_company_collection`` creates it first, as the cutover does (9.2 step 3);
* embeddings are :func:`hash_embed` behind ``index.embed._get_model`` (the single
  seam under both ``upsert.build_points`` and ``link.restates``, which import
  ``embed_texts`` by name);
* the LLM is :func:`stub_provider` behind ``llm.client._call_provider`` - UNDER the
  persistent cache (TDD §4.3), so the read-through/write-back tier, schema
  augmentation, validation and the R2 audit write all run for real;
* ``app.main.app`` is driven by ``synthetic.seed.seed()`` over
  ``httpx.ASGITransport`` (no lifespan, so no startup sweep; BackgroundTasks - the
  ingest jobs - run before each response returns).

Then it checks the task 9.1 acceptance criteria against the scratch database and
the in-memory collection, re-runs ``seed()`` to prove it writes nothing, and prints
the parity-prediction table against ``baseline_before_v2.json``. The task 9.3 hard
gates are PREDICTED here and printed (a predicted failure is a loud warning, not a
9.1 failure: 9.3 judges them on the post-cutover database and allows a written
explanation). Exit status 0 = every 9.1 check held; 1 = a check failed; 2 = the
seeder raised.
"""
from __future__ import annotations

import ast
import asyncio
import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent          # backend/synthetic
BACKEND = HERE.parent                           # backend
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

BASELINE_JSON = HERE / "baseline_before_v2.json"
SEED_PY = HERE / "seed.py"
BASE_URL = "http://rehearsal.invalid"
EMBED_DIM = 384

#: Task 9.1 / 9.3 numbers this stage is judged against.
EXPECTED_DOCUMENTS = 15              # 12 DOCX + 3 register CSVs (9.1 decision (a))
EXPECTED_DOCX_DOCUMENTS = 12
DOCX_PATH_PROJECTION = 2731          # make_docx fidelity run: 2,527 + 204 register rows
CLAUSE_SOFT_BAND = 0.35              # 9.3: investigate total clauses only outside ±35%
REGISTER_ROWS_MIN = 200              # 9.3 hard gate
RESOLVED_MIN_FRACTION = 0.90         # 9.3 hard gate vs baseline 1,284
DISTINCT_MIN_FRACTION = 0.95         # 9.3 hard gate vs baseline 75
#: Modules ``seed.py`` must never import: it talks to the API over HTTP only.
FORBIDDEN_SEED_IMPORTS = ("app", "sqlalchemy", "asyncpg", "psycopg2", "psycopg", "qdrant_client",
                          "boto3")


def log(msg: str = "") -> None:
    print(msg, flush=True)


# ================================================================ network guard
def _is_loopback(host: Any) -> bool:
    if host is None:
        return True  # getaddrinfo(None, port) = a local wildcard, no lookup
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    h = str(host).strip("[]").split("%", 1)[0]
    if h.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


@dataclass
class NetGuard:
    """Refuses every non-loopback ``socket.connect``/``connect_ex`` and every
    non-loopback ``getaddrinfo`` in THIS process, and records each attempt (a
    refused attempt fails the rehearsal even if the caller swallowed the error)."""

    refused: list[str] = field(default_factory=list)
    _saved: dict = field(default_factory=dict)

    def _check(self, what: str, host: Any, port: Any = None) -> None:
        if not _is_loopback(host):
            self.refused.append(f"{what} {host}:{port}")
            raise ConnectionRefusedError(f"rehearsal network guard: {what} to {host}:{port} refused")

    def install(self) -> "NetGuard":
        real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
        real_gai = socket.getaddrinfo
        guard = self

        def _addr(sock: socket.socket, address: Any) -> None:
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                guard._check("connect", address[0], address[1])

        def connect(sock, address):
            _addr(sock, address)
            return real_connect(sock, address)

        def connect_ex(sock, address):
            _addr(sock, address)
            return real_connect_ex(sock, address)

        def getaddrinfo(host, port, *a, **k):
            guard._check("getaddrinfo", host, port)
            return real_gai(host, port, *a, **k)

        self._saved = {"connect": real_connect, "connect_ex": real_connect_ex, "gai": real_gai}
        socket.socket.connect = connect          # type: ignore[method-assign]
        socket.socket.connect_ex = connect_ex    # type: ignore[method-assign]
        socket.getaddrinfo = getaddrinfo         # type: ignore[assignment]
        return self

    def uninstall(self) -> None:
        if self._saved:
            socket.socket.connect = self._saved["connect"]        # type: ignore[method-assign]
            socket.socket.connect_ex = self._saved["connect_ex"]  # type: ignore[method-assign]
            socket.getaddrinfo = self._saved["gai"]               # type: ignore[assignment]
            self._saved = {}


# ============================================================ deterministic fakes
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def hash_embed(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic unit-length bag-of-words embedding (signed feature hashing).

    Not random noise: two texts sharing words get a positive cosine, so
    ``link.restates``' 0.6 threshold still means "mostly the same words". Same
    text -> bit-identical vector in any process (sha256, no ``hash()`` salt)."""
    vec = [0.0] * dim
    for tok in _TOKEN_RE.findall(text.lower()):
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        vec[int.from_bytes(h[:4], "big") % dim] += 1.0 if h[4] & 1 else -1.0
    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0.0:
        vec[0] = 1.0
        return vec
    return [v / norm for v in vec]


class _Rows(list):
    """``model.encode(...)`` returns an ndarray; ``embed_texts`` only calls ``.tolist()``."""

    def tolist(self) -> list:
        return list(self)


class HashEmbeddingModel:
    """Stands in for the ``SentenceTransformer`` ``embed._get_model()`` returns."""

    def __init__(self) -> None:
        self.texts_encoded = 0

    def encode(self, batch: list[str], normalize_embeddings: bool = True, **_: Any) -> _Rows:
        self.texts_encoded += len(batch)
        return _Rows(hash_embed(t) for t in batch)


@dataclass
class StubLLM:
    """Deterministic replacement for ``llm.client._call_provider(system, user, model)``.

    Dispatches on the JSON-Schema title ``call_structured`` appends to the system
    prompt, and answers only what the deterministic stages could know:

    * ``ClauseEnrichment``: ``clause_role`` mirrors the ``no_llm`` heuristic of
      ``run_clause_enrichment`` (``regulatory_restatement`` iff the message lists
      ``CITATIONS_FOUND``, else ``internal_procedure``; it is applied only where
      stage 4 left the role unset); no statement, terms or parameters.
    * ``ColumnRolesResponse``: every column under "Columns needing classification"
      -> ``free_text``.

    Any other schema raises: a new LLM stage must be stubbed on purpose, not by
    accident."""

    calls: dict[str, int] = field(default_factory=dict)

    async def __call__(self, system: str, user: str, model: str) -> str:
        return self.answer(system, user)

    def answer(self, system: str, user: str) -> str:
        if '"title": "ClauseEnrichment"' in system:
            kind = "clause_enrichment"
            role = "regulatory_restatement" if "CITATIONS_FOUND" in user else "internal_procedure"
            out: dict = {"clause_role": role, "normalized_statement": None, "topic_terms": [],
                         "parameters": [], "citation_links": []}
        elif '"title": "ColumnRolesResponse"' in system:
            kind = "column_roles"
            out = {"assignments": [{"column_name": c, "role": "free_text"}
                                   for c in _columns_needing_classification(user)]}
        else:
            raise RuntimeError("rehearsal StubLLM: no stub for this schema "
                               f"(system prompt starts {system[:80]!r})")
        self.calls[kind] = self.calls.get(kind, 0) + 1
        return json.dumps(out, sort_keys=True)


def _columns_needing_classification(user: str) -> list[str]:
    cols: list[str] = []
    lines = iter(user.splitlines())
    for line in lines:
        if line.strip() == "Columns needing classification:":
            for col in lines:
                if not col.strip():
                    break
                cols.append(col.strip())
            break
    return cols


# ================================================================ static checks
def seed_imports(path: Path = SEED_PY) -> set[str]:
    """Top-level module names ``seed.py`` imports (absolute imports only)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


# ================================================================== DB metrics
#: Every metric reads the CURRENT version of each document only (the version-scoped
#: view the engine and the API see); on a fresh seed that is every version.
_CUR = ("JOIN company.company_documents d ON d.company_id = c.company_id AND d.doc_id = c.doc_id "
        "AND c.version_id = d.current_version_id")
METRIC_SQL: dict[str, tuple[str, str]] = {
    "documents_total": ("SELECT count(*) FROM company.company_documents", "scalar"),
    "documents_current": ("SELECT count(*) FROM company.company_documents "
                          "WHERE current_version_id IS NOT NULL", "scalar"),
    "document_versions_total": ("SELECT count(*) FROM company.document_versions", "scalar"),
    "versions_effective_current": ("SELECT count(*) FROM company.document_versions "
                                   "WHERE status = 'effective' AND is_current", "scalar"),
    "clauses_all_versions": ("SELECT count(*) FROM company.clauses", "scalar"),
    "clauses_total": (f"SELECT count(*) FROM company.clauses c {_CUR}", "scalar"),
    "clauses_by_unit_kind": (f"SELECT c.unit_kind, count(*) FROM company.clauses c {_CUR} "
                             "GROUP BY 1 ORDER BY 2 DESC", "rows"),
    "citations_total": (f"SELECT count(*) FROM company.clause_citations cc JOIN company.clauses c "
                        f"ON c.clause_pk = cc.clause_pk {_CUR}", "scalar"),
    "citations_resolved": (f"SELECT count(cc.code_section_id) FROM company.clause_citations cc "
                           f"JOIN company.clauses c ON c.clause_pk = cc.clause_pk {_CUR}", "scalar"),
    "citations_by_status": (f"SELECT cc.resolution_status, count(*) FROM company.clause_citations cc "
                            f"JOIN company.clauses c ON c.clause_pk = cc.clause_pk {_CUR} "
                            "GROUP BY 1 ORDER BY 2 DESC", "rows"),
    "citations_resolved_by_unit_kind": (
        f"SELECT c.unit_kind, count(cc.code_section_id) FROM company.clause_citations cc "
        f"JOIN company.clauses c ON c.clause_pk = cc.clause_pk {_CUR} GROUP BY 1 ORDER BY 2 DESC",
        "rows"),
    "distinct_code_sections_total": (
        f"SELECT count(DISTINCT cc.code_section_id) FROM company.clause_citations cc "
        f"JOIN company.clauses c ON c.clause_pk = cc.clause_pk {_CUR} "
        "WHERE cc.code_section_id IS NOT NULL", "scalar"),
    "distinct_code_sections_by_unit_kind": (
        f"SELECT c.unit_kind, count(DISTINCT cc.code_section_id) FROM company.clause_citations cc "
        f"JOIN company.clauses c ON c.clause_pk = cc.clause_pk {_CUR} "
        "WHERE cc.code_section_id IS NOT NULL GROUP BY 1 ORDER BY 2 DESC", "rows"),
    "current_version_ids": ("SELECT current_version_id::text FROM company.company_documents "
                            "WHERE current_version_id IS NOT NULL", "list"),
    "code_sections_total": ("SELECT count(*) FROM public.code_sections", "scalar"),
    "approval_requests": ("SELECT count(*) FROM company.approval_requests", "scalar"),
    "approval_decisions": ("SELECT count(*) FROM company.approval_steps WHERE decision IS NOT NULL",
                           "scalar"),
    "ingest_jobs": ("SELECT count(*) FROM company.ingest_jobs", "scalar"),
    "llm_extractions": ("SELECT count(*) FROM company.llm_extractions", "scalar"),
    "people": ("SELECT count(*) FROM company.people", "scalar"),
    "company_attributes": ("SELECT count(*) FROM company.company_attributes", "scalar"),
    "role_assignments": ("SELECT count(*) FROM company.document_role_assignments", "scalar"),
}


def read_metrics(db_url: str) -> dict:
    """One read-only session against the scratch database (verification only: the
    seeder itself never touches the database)."""
    import psycopg2

    p = urlparse(db_url)
    con = psycopg2.connect(host=p.hostname, port=p.port, user=p.username or "postgres",
                           dbname=p.path.lstrip("/"), sslmode="require")
    con.set_session(readonly=True)
    out: dict = {}
    try:
        cur = con.cursor()
        for key, (sql, kind) in METRIC_SQL.items():
            cur.execute(sql)
            if kind == "scalar":
                out[key] = cur.fetchone()[0]
            elif kind == "list":
                out[key] = sorted(r[0] for r in cur.fetchall())
            else:
                out[key] = {str(r[0]): r[1] for r in cur.fetchall()}
    finally:
        con.close()
    return out


def qdrant_versions(client: Any, collection: str) -> dict[str, int]:
    """version_id -> point count, over every point in the collection."""
    counts: dict[str, int] = {}
    offset = None
    while True:
        points, offset = client.scroll(collection, limit=1000, offset=offset, with_payload=True,
                                       with_vectors=False)
        for p in points:
            v = (p.payload or {}).get("version_id")
            counts[v] = counts.get(v, 0) + 1
        if offset is None:
            return counts


# ===================================================================== checks
@dataclass
class Checks:
    results: list[tuple[bool, str]] = field(default_factory=list)

    def check(self, ok: bool, msg: str) -> bool:
        self.results.append((bool(ok), msg))
        log(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
        return bool(ok)

    @property
    def failed(self) -> list[str]:
        return [m for ok, m in self.results if not ok]


def _pct(new: float, base: float) -> str:
    return f"{(new - base) / base * 100:+.1f}%" if base else "n/a"


def parity_table(m: dict, base: dict) -> tuple[str, list[tuple[bool, str]]]:
    """Task 9.3's per-metric table, predicted from the rehearsal. Returns the text
    and the hard-gate verdicts (findings are not computed here: the engine is 9.2)."""
    rows: list[tuple[str, str, str, str, str]] = []
    gates: list[tuple[bool, str]] = []

    def row(name: str, b: Any, n: Any, gate: str, ok: Optional[bool]) -> None:
        delta = _pct(n, b) if isinstance(b, (int, float)) and isinstance(n, (int, float)) else ""
        verdict = "" if ok is None else ("PASS" if ok else "FAIL")
        rows.append((name, str(b), str(n), delta, f"{gate} {verdict}".strip()))
        if ok is not None:
            gates.append((ok, f"9.3 gate {name}: {n} ({gate})"))

    bres, bdist = base["citations_resolved"], base["distinct_code_sections_total"]
    breg = base["clauses_by_unit_kind"].get("register_row", 0)
    nreg = m["clauses_by_unit_kind"].get("register_row", 0)
    row("citations_resolved", bres, m["citations_resolved"], f"hard >= {RESOLVED_MIN_FRACTION:.0%}",
        m["citations_resolved"] >= RESOLVED_MIN_FRACTION * bres)
    row("distinct_code_sections", bdist, m["distinct_code_sections_total"],
        f"hard >= {DISTINCT_MIN_FRACTION:.0%}",
        m["distinct_code_sections_total"] >= DISTINCT_MIN_FRACTION * bdist)
    row("register_row clauses", breg, nreg, f"hard >= {REGISTER_ROWS_MIN}", nreg >= REGISTER_ROWS_MIN)
    row("code_sections (KB)", base["code_sections_total"], m["code_sections_total"], "hard unchanged",
        m["code_sections_total"] == base["code_sections_total"])
    row("findings_total", base["findings_total"], "-", "hard >= 85% (engine run: 9.2)", None)
    row("clauses_total", base["clauses_total"], m["clauses_total"],
        f"soft ±{CLAUSE_SOFT_BAND:.0%}", None)
    row("  vs DOCX projection", DOCX_PATH_PROJECTION, m["clauses_total"], "info", None)
    row("citations_total", base["citations_total"], m["citations_total"], "info", None)
    kinds = sorted(set(base["clauses_by_unit_kind"]) | set(m["clauses_by_unit_kind"]))
    for k in kinds:
        row(f"  clauses[{k}]", base["clauses_by_unit_kind"].get(k, 0),
            m["clauses_by_unit_kind"].get(k, 0), "soft", None)
    for k in sorted(set(base["citations_resolved_by_unit_kind"]) |
                    set(m["citations_resolved_by_unit_kind"])):
        row(f"  resolved[{k}]", base["citations_resolved_by_unit_kind"].get(k, 0),
            m["citations_resolved_by_unit_kind"].get(k, 0), "info", None)
    dk = base["distinct_code_sections_by_unit_kind"]
    nk = m["distinct_code_sections_by_unit_kind"]
    for k in sorted(set(dk) | set(nk)):
        row(f"  distinct[{k}]", dk.get(k, 0), nk.get(k, 0), "info", None)
    top = max(nk, key=nk.get) if nk else "-"
    row("largest distinct contributor", max(dk, key=dk.get), top, "9.3: register_row",
        top == "register_row")

    head = ("metric", "baseline", "rehearsal", "delta", "gate")
    allrows = [head] + rows
    w = [max(len(r[i]) for r in allrows) for i in range(len(head))]
    fmt = lambda r: "  ".join(c.ljust(x) for c, x in zip(r, w)).rstrip()  # noqa: E731
    text = "\n".join([fmt(head), "  ".join("-" * x for x in w)] + [fmt(r) for r in rows])
    return text, gates


def fingerprint(m: dict, qcounts: dict[str, int]) -> dict:
    """What a no-op re-run must leave byte-identical."""
    keys = ("documents_total", "document_versions_total", "clauses_all_versions", "citations_total",
            "citations_resolved", "approval_requests", "approval_decisions", "ingest_jobs",
            "llm_extractions", "people", "company_attributes", "role_assignments",
            "current_version_ids")
    return {**{k: m[k] for k in keys}, "qdrant_points": sum(qcounts.values()),
            "qdrant_versions": sorted(qcounts)}


# ====================================================================== run
def _assert_isolated(db_url: str) -> None:
    host = urlparse(db_url).hostname
    if host != "127.0.0.1":
        raise SystemExit(f"refusing to run: database host is {host!r}, not 127.0.0.1")
    if Path(".env").exists():
        raise SystemExit("refusing to run: a .env file is present in the working directory")
    if os.environ.get("DATABASE_URL") != db_url:
        raise SystemExit("refusing to run: DATABASE_URL in the environment is not the scratch URL")


async def _run(db_url: str, guard: NetGuard) -> int:
    import boto3
    import httpx
    from moto import mock_aws
    from qdrant_client import QdrantClient

    with mock_aws():
        # --- import the real app (settings come from child_env(), not a .env) -------
        from app.config import settings
        from app.company_ingest.index import embed as embed_mod
        from app.company_ingest.index import upsert as upsert_mod
        from app.company_ingest.index.qdrant_setup import COMPANY_COLLECTION, ensure_company_collection
        from app.company_ingest.llm import client as llm_client
        from app.company_ingest.store import r2 as r2_mod
        from app.db import engine as db_engine
        from app.main import app
        from synthetic.seed import SeedError, seed

        if settings.DATABASE_URL != db_url:
            raise SystemExit("app settings did not pick up the scratch DATABASE_URL")

        # --- R2 = moto -----------------------------------------------------------------
        def _moto_s3():
            return boto3.client("s3", region_name="us-east-1", aws_access_key_id="rehearsal",
                                aws_secret_access_key="rehearsal")

        _moto_s3().create_bucket(Bucket=settings.R2_BUCKET_NAME)
        r2_mod._get_client = _moto_s3

        # --- Qdrant = the library's in-memory store ------------------------------------
        qdrant = QdrantClient(location=":memory:")
        ensure_company_collection(qdrant, embed_dim=settings.EMBED_DIM)
        upsert_mod._make_client = lambda: qdrant

        # --- embeddings + LLM -------------------------------------------------------------
        model = HashEmbeddingModel()
        embed_mod._get_model = lambda: model
        stub = StubLLM()
        llm_client._call_provider = stub

        checks = Checks()
        bad_imports = seed_imports() & set(FORBIDDEN_SEED_IMPORTS)
        checks.check(not bad_imports, "seed.py imports nothing that can reach the DB/Qdrant/R2 "
                     f"directly (forbidden imports found: {sorted(bad_imports) or 'none'})")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE_URL,
                                     timeout=httpx.Timeout(600.0)) as client:
            log("\n--- seed run 1 (empty database) " + "-" * 45)
            try:
                rep1 = await seed(client, log=log, job_timeout=600.0, poll_interval=0.05)
            except SeedError as exc:
                log(f"SEED FAILED: {exc}")
                return 2
            log("\n" + rep1.table())
            m1 = read_metrics(db_url)
            q1 = qdrant_versions(qdrant, COMPANY_COLLECTION)
            fp1 = fingerprint(m1, q1)

            log("\n--- seed run 2 (same state: must write nothing) " + "-" * 29)
            try:
                rep2 = await seed(client, log=log, job_timeout=600.0, poll_interval=0.05)
            except SeedError as exc:
                log(f"SEED (re-run) FAILED: {exc}")
                return 2
            m2 = read_metrics(db_url)
            q2 = qdrant_versions(qdrant, COMPANY_COLLECTION)
            fp2 = fingerprint(m2, q2)
            docs_api = (await client.get("/company/documents")).json()

        await db_engine.dispose()

    # --- acceptance (task 9.1) --------------------------------------------------------
    base = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    log("\n--- acceptance (task 9.1) " + "-" * 52)
    docs1 = rep1.documents
    checks.check(len(docs1) == EXPECTED_DOCUMENTS and m1["documents_total"] == EXPECTED_DOCUMENTS,
                 f"{EXPECTED_DOCUMENTS} documents from an empty database (seed report "
                 f"{len(docs1)}, company_documents {m1['documents_total']})")
    not_ok = [d.doc_number for d in docs1 if not (d.is_current and d.version_status == "effective")]
    checks.check(not not_ok and m1["versions_effective_current"] == EXPECTED_DOCUMENTS
                 and m1["documents_current"] == EXPECTED_DOCUMENTS,
                 f"all effective/is_current ({m1['versions_effective_current']} effective+current "
                 f"versions, {m1['documents_current']} documents with a current version; "
                 f"not effective: {not_ok or 'none'})")
    api_ok = [d for d in docs_api if d.get("has_current_version")]
    checks.check(len(docs_api) == EXPECTED_DOCUMENTS and len(api_ok) == EXPECTED_DOCUMENTS
                 and all(d.get("vertical") and d.get("vertical") != "unclassified" for d in docs_api),
                 f"GET /company/documents lists {len(docs_api)} documents, {len(api_ok)} with a "
                 "current version, none unclassified")
    tot, bt = m1["clauses_total"], base["clauses_total"]
    checks.check(abs(tot - bt) <= CLAUSE_SOFT_BAND * bt,
                 f"clauses {tot} within ±{CLAUSE_SOFT_BAND:.0%} of the 0.1 baseline {bt} "
                 f"({_pct(tot, bt)}; DOCX-path projection {DOCX_PATH_PROJECTION}: "
                 f"{_pct(tot, DOCX_PATH_PROJECTION)})")
    checks.check(m1["clauses_all_versions"] == tot,
                 f"no clauses outside the current versions ({m1['clauses_all_versions']} total)")
    nreg = m1["clauses_by_unit_kind"].get("register_row", 0)
    checks.check(nreg == base["clauses_by_unit_kind"]["register_row"],
                 f"register_row clauses {nreg} == baseline "
                 f"{base['clauses_by_unit_kind']['register_row']} (70 + 86 + 48 CSV rows)")
    res, bres = m1["citations_resolved"], base["citations_resolved"]
    dist, bdist = m1["distinct_code_sections_total"], base["distinct_code_sections_total"]
    checks.check(res > 0 and dist >= DISTINCT_MIN_FRACTION * bdist,
                 f"citations resolved {res} > 0 and comparable to baseline {bres} ({_pct(res, bres)}): "
                 f"they reach {dist} distinct code sections vs {bdist} "
                 f"(>= {DISTINCT_MIN_FRACTION:.0%}; the raw-count gate is 9.3's, predicted below)")
    cur_ids = set(m1["current_version_ids"])
    checks.check(set(q1) == cur_ids and all(n > 0 for n in q1.values()),
                 f"Qdrant holds points for the current versions only: {len(q1)} versions "
                 f"({sum(q1.values())} points) == {len(cur_ids)} current version ids "
                 f"({EXPECTED_DOCX_DOCUMENTS} DOCX + {EXPECTED_DOCUMENTS - EXPECTED_DOCX_DOCUMENTS} "
                 "register documents)")
    checks.check(rep2.writes == 0, f"re-run made {rep2.writes} HTTP writes (expected 0)"
                 + (f": {rep2.documents and [d.doc_number for d in rep2.documents if d.action != 'skipped']}"
                    if rep2.writes else ""))
    checks.check(all(d.action == "skipped" for d in rep2.documents) and len(rep2.documents) == 15,
                 "re-run skipped all 15 documents")
    changed = {k: (fp1[k], fp2[k]) for k in fp1 if fp1[k] != fp2[k]}
    checks.check(not changed, f"re-run left the database and Qdrant unchanged "
                 f"({len(fp1)} fingerprint keys; changed: {sorted(changed) or 'none'})")
    checks.check(m1["code_sections_total"] == base["code_sections_total"],
                 f"public.code_sections {m1['code_sections_total']} == {base['code_sections_total']}")
    checks.check(stub.calls.get("clause_enrichment", 0) > 0 and model.texts_encoded > 0,
                 f"stubs were exercised (LLM calls {dict(sorted(stub.calls.items()))}, "
                 f"texts embedded {model.texts_encoded}, llm_extractions rows "
                 f"{m1['llm_extractions']})")
    checks.check(not guard.refused, f"no non-loopback network attempt "
                 f"({len(guard.refused)} refused{': ' + '; '.join(guard.refused[:5]) if guard.refused else ''})")

    # --- parity prediction (task 9.3) -------------------------------------------------
    log("\n--- parity prediction vs baseline_before_v2.json (task 9.3) " + "-" * 18)
    text, gates = parity_table(m1, base)
    log(text)
    log("\n  citations by status: " + json.dumps(m1["citations_by_status"], sort_keys=True))
    log(f"  baseline:            {json.dumps(base['citations_by_status'], sort_keys=True)}")
    log("\n--- 9.3 hard gates predicted from the rehearsal (informational) " + "-" * 14)
    predicted_fail = [msg for ok, msg in gates if not ok]
    for ok, msg in gates:
        log(f"  [{'PASS' if ok else 'PREDICTED FAIL'}] {msg}")

    log("\n" + "=" * 78)
    if predicted_fail:
        log(f"WARNING: {len(predicted_fail)} task 9.3 hard gate(s) predicted to FAIL after the "
            "cutover; 9.3 requires each to be explained and accepted in writing:")
        for msg in predicted_fail:
            log(f"  - {msg}")
    if checks.failed:
        log(f"REHEARSAL FAILED: {len(checks.failed)} of {len(checks.results)} checks failed")
        for msg in checks.failed:
            log(f"  - {msg}")
        return 1
    log(f"REHEARSAL PASSED: {len(checks.results)} checks; seed run 1 {rep1.writes} HTTP writes in "
        f"{rep1.seconds:.1f}s, run 2 {rep2.writes} writes in {rep2.seconds:.1f}s")
    return 0


def inner(db_url: str) -> int:
    """Entry point for ``rehearsal.py --inner --db-url <scratch url>``."""
    _assert_isolated(db_url)
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s %(name)s: %(message)s")
    guard = NetGuard().install()   # before anything from app/ is imported
    t0 = time.monotonic()
    try:
        return asyncio.run(_run(db_url, guard))
    finally:
        guard.uninstall()
        log(f"[inner] {time.monotonic() - t0:.1f}s")
