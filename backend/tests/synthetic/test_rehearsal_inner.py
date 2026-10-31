"""Tests for ``synthetic/rehearsal_inner.py`` (task 9.1, part C4): the deterministic
stand-ins the rehearsal runs the real app with, and the network guard.

* :func:`hash_embed` / :class:`HashEmbeddingModel` - deterministic within AND across
  processes (sha256, never the salted builtin ``hash``), unit length, word-overlap
  similarity, and the ``embed_texts`` contract.
* :class:`StubLLM` - driven through the REAL ``llm.client.call_structured`` so its
  output is validated against the real schemas and prompt augmentation.
* :class:`NetGuard` - refuses non-loopback connects and lookups, allows loopback,
  restores the socket module on uninstall.

Skips cleanly when ``backend/synthetic/`` is absent.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
SYNTHETIC = BACKEND / "synthetic"
if not (SYNTHETIC / "rehearsal_inner.py").is_file():
    pytest.skip("backend/synthetic/ is absent", allow_module_level=True)

from synthetic import rehearsal_inner as ri  # noqa: E402

pytestmark = pytest.mark.corpus


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # both unit length


# ------------------------------------------------------------------ embeddings
def test_hash_embed_is_deterministic_and_unit_length():
    text = "Customer complaints are logged within one business day | 170 IAC 4-1-16"
    a, b = ri.hash_embed(text), ri.hash_embed(text)
    assert a == b
    assert len(a) == ri.EMBED_DIM == 384
    assert abs(sum(v * v for v in a) - 1.0) < 1e-9


def test_hash_embed_is_identical_across_processes_with_different_hash_seeds():
    """Pins that the vector does not depend on PYTHONHASHSEED: a rehearsal run and
    its reseed must index bit-identical vectors."""
    text = "Spill response | report to IDEM within two hours"
    code = ("import json, sys; sys.path.insert(0, %r); "
            "from synthetic.rehearsal_inner import hash_embed; "
            "print(json.dumps(hash_embed(%r)))") % (str(BACKEND), text)
    outs = []
    for seed in ("1", "2"):
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": seed}
        res = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True,
                             text=True, check=True, cwd=str(BACKEND))
        outs.append(json.loads(res.stdout))
    assert outs[0] == outs[1] == ri.hash_embed(text)


def test_hash_embed_similarity_tracks_word_overlap():
    base = ri.hash_embed("notify the commission within ten business days of the outage")
    near = ri.hash_embed("notify the commission within ten business days of an outage")
    far = ri.hash_embed("meter test equipment calibration certificate retention")
    assert _cos(base, near) > 0.6 > _cos(base, far)  # restates' threshold is 0.6


def test_hash_embed_of_text_without_tokens_is_a_fixed_unit_vector():
    assert ri.hash_embed("") == ri.hash_embed(" | ") == [1.0] + [0.0] * 383


def test_hash_model_satisfies_the_embed_texts_contract(monkeypatch):
    from app.company_ingest.index import embed as embed_mod

    model = ri.HashEmbeddingModel()
    monkeypatch.setattr(embed_mod, "_get_model", lambda: model)
    texts = [f"clause {i} text" for i in range(130)]  # > one 64-text batch
    out = embed_mod.embed_texts(texts)
    assert out == [ri.hash_embed(t) for t in texts]
    assert model.texts_encoded == 130


# ------------------------------------------------------------------------- LLM
@pytest.fixture
def stubbed(monkeypatch):
    from app.company_ingest.llm import client as llm_client

    stub = ri.StubLLM()
    monkeypatch.setattr(llm_client, "_call_provider", stub)

    async def _no_audit(*a, **k):  # the rehearsal routes this to moto; here: nowhere
        return None

    monkeypatch.setattr(llm_client, "_write_audit", _no_audit)
    return stub


def _structured(stage, user, schema, system="You classify things."):
    from app.company_ingest.llm.client import call_structured
    from app.company_ingest.run_context import RunContext

    return asyncio.run(call_structured(stage, "U1", system, user, schema,
                                       RunContext(company_id="rpl"), model="stub"))


def test_stub_clause_enrichment_is_deterministic_and_schema_valid(stubbed):
    from app.company_ingest.llm.schemas import ClauseEnrichment

    cited = "CLAUSE_ID: D:1\n\nCITATIONS_FOUND (deterministic, from stage 4.1.1):\n  [0] 170 IAC 4-1-16\n"
    plain = "CLAUSE_ID: D:2\n\nCLAUSE_TEXT:\nKeep the log.\n"
    a = _structured("clause_enrichment", cited, ClauseEnrichment)
    b = _structured("clause_enrichment", cited, ClauseEnrichment)
    c = _structured("clause_enrichment", plain, ClauseEnrichment)
    assert isinstance(a, ClauseEnrichment) and a == b
    assert a.clause_role == "regulatory_restatement"
    assert c.clause_role == "internal_procedure"
    assert (a.normalized_statement, a.topic_terms, a.parameters, a.citation_links) == (None, [], [], [])
    assert stubbed.calls == {"clause_enrichment": 3}


def test_stub_column_roles_answers_exactly_the_requested_columns(stubbed):
    from app.company_ingest.llm.run_column_roles import (
        SYSTEM_PROMPT,
        ColumnRolesResponse,
        _build_user_message,
    )

    user = _build_user_message("DOC-1", ["rrs_id", "media", "notes", "owner_dept"],
                               {"rrs_id": "id", "media": None, "notes": "summary_text",
                                "owner_dept": None},
                               ["media", "owner_dept"], [{"media": "paper", "owner_dept": "HR"}])
    a = _structured("column_roles", user, ColumnRolesResponse, system=SYSTEM_PROMPT)
    b = _structured("column_roles", user, ColumnRolesResponse, system=SYSTEM_PROMPT)
    assert a == b
    assert [(x.column_name, x.role) for x in a.assignments] == [("media", "free_text"),
                                                                ("owner_dept", "free_text")]


def test_stub_refuses_a_schema_it_was_not_written_for():
    from pydantic import BaseModel

    class Other(BaseModel):
        x: int

    system = 'Do it.\n\n```json\n' + json.dumps(Other.model_json_schema(), indent=2) + "\n```"
    with pytest.raises(RuntimeError, match="no stub for this schema"):
        ri.StubLLM().answer(system, "anything")


# ------------------------------------------------------------------- NetGuard
@pytest.fixture
def guard():
    g = ri.NetGuard().install()
    try:
        yield g
    finally:
        g.uninstall()


def test_guard_refuses_a_non_loopback_connect_and_records_it(guard):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        with pytest.raises(ConnectionRefusedError, match="network guard"):
            s.connect(("192.0.2.1", 443))  # TEST-NET-1: never routable
        assert s.connect_ex is not None
        with pytest.raises(ConnectionRefusedError):
            s.connect_ex(("198.51.100.7", 5432))
    assert guard.refused == ["connect 192.0.2.1:443", "connect 198.51.100.7:5432"]


def test_guard_refuses_non_loopback_name_lookups(guard):
    with pytest.raises(ConnectionRefusedError):
        socket.getaddrinfo("api.anthropic.com", 443)
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("qdrant.rehearsal.invalid", 6333), timeout=1)
    assert [r.split()[0] for r in guard.refused] == ["getaddrinfo", "getaddrinfo"]


def test_guard_allows_loopback(guard):
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(8)
        port = srv.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
        with socket.create_connection(("localhost", port), timeout=2):
            pass
    assert guard.refused == []


@pytest.mark.parametrize("host,ok", [
    ("127.0.0.1", True), ("127.8.9.10", True), ("::1", True), ("[::1]", True),
    ("localhost", True), (None, True), (b"127.0.0.1", True),
    ("10.0.0.1", False), ("8.8.8.8", False), ("example.com", False), ("::ffff:1.2.3.4", False),
])
def test_is_loopback(host, ok):
    assert ri._is_loopback(host) is ok


def test_guard_uninstall_restores_the_socket_module():
    before = (socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo)
    g = ri.NetGuard().install()
    assert socket.getaddrinfo is not before[2]
    g.uninstall()
    assert (socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo) == before


# ------------------------------------------------------------ parity table
def test_parity_table_marks_the_9_3_hard_gates():
    import json as _json

    base = _json.loads(ri.BASELINE_JSON.read_text(encoding="utf-8"))
    m = {"citations_resolved": 1151, "distinct_code_sections_total": 75,
         "clauses_by_unit_kind": {"register_row": 204, "section": 659, "table_row": 1868},
         "code_sections_total": 4603, "clauses_total": 2731, "citations_total": 1416,
         "citations_resolved_by_unit_kind": {"register_row": 162},
         "distinct_code_sections_by_unit_kind": {"register_row": 69, "section": 59}}
    text, gates = ri.parity_table(m, base)
    verdict = {msg.split(":")[0]: ok for ok, msg in gates}
    assert verdict == {"9.3 gate citations_resolved": False,          # 1151 < 0.9 * 1284
                       "9.3 gate distinct_code_sections": True,
                       "9.3 gate register_row clauses": True,
                       "9.3 gate code_sections (KB)": True,
                       "9.3 gate largest distinct contributor": True}
    assert "clauses[form_field]" in text and "vs DOCX projection" in text
