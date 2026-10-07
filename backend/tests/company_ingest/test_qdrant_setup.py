"""
Tests for task 1.2.3: Qdrant collection setup (company_clauses).

Unit tests use a mock QdrantClient — no real Qdrant connection required.
Integration tests that need a live Qdrant instance are marked @pytest.mark.qdrant
and are skipped unless QDRANT_URL is set in the environment.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from app.company_ingest.index.qdrant_setup import (
    COMPANY_COLLECTION,
    _BOOL_FIELDS,
    _KEYWORD_FIELDS,
    ensure_company_collection,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXPECTED_KEYWORD_FIELDS = {
    "company_id",
    "doc_id",
    "version_id",
    "clause_id",
    "clause_role",
    "unit_kind",
    "section_kind",
    "cited_sections",
    "cited_rules",
    "param_kinds",
    "param_units",
    "terms_used",
    "doc_class",
    "owner_id",
    "project",
}

_EXPECTED_BOOL_FIELDS = {
    "is_current",
    "assessable",
}


def _make_mock_client(collection_exists: bool = False, dense_size: int = 384) -> MagicMock:
    """Return a mock QdrantClient configured for the given scenario."""
    client = MagicMock()
    client.collection_exists.return_value = collection_exists

    if collection_exists:
        from qdrant_client.models import Distance

        dense_params = SimpleNamespace(size=dense_size, distance=Distance.COSINE)
        vectors_cfg = {"dense": dense_params}
        collection_info = SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(vectors=vectors_cfg)
            )
        )
        client.get_collection.return_value = collection_info

    return client


# ---------------------------------------------------------------------------
# Payload index field coverage
# ---------------------------------------------------------------------------

def test_keyword_fields_match_spec():
    """_KEYWORD_FIELDS must exactly match the SPEC §9 keyword payload table (+ project)."""
    assert set(_KEYWORD_FIELDS) == _EXPECTED_KEYWORD_FIELDS


def test_bool_fields_match_spec():
    """_BOOL_FIELDS must exactly match the SPEC §9 bool payload table."""
    assert set(_BOOL_FIELDS) == _EXPECTED_BOOL_FIELDS


def test_all_payload_indexes_created_on_new_collection():
    """
    On first call (collection absent), every field in SPEC §9 plus 'project' must
    get a payload index.  Uses a mock — no real Qdrant needed.
    """
    client = _make_mock_client(collection_exists=False)

    ensure_company_collection(client, embed_dim=384)

    index_calls = [
        c.kwargs["field_name"]
        for c in client.create_payload_index.call_args_list
    ]
    assert set(index_calls) == _EXPECTED_KEYWORD_FIELDS | _EXPECTED_BOOL_FIELDS


def test_all_payload_indexes_created_on_existing_compatible_collection():
    """
    On a repeat call where the collection already exists with matching config,
    the function must still create all payload indexes (idempotent index pass).
    """
    client = _make_mock_client(collection_exists=True, dense_size=384)

    ensure_company_collection(client, embed_dim=384)

    index_calls = {
        c.kwargs["field_name"]
        for c in client.create_payload_index.call_args_list
    }
    assert index_calls == _EXPECTED_KEYWORD_FIELDS | _EXPECTED_BOOL_FIELDS


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_idempotent_first_call_creates_collection():
    """First call must invoke create_collection exactly once."""
    client = _make_mock_client(collection_exists=False)
    ensure_company_collection(client)
    client.create_collection.assert_called_once()


def test_idempotent_second_call_does_not_create_collection():
    """Second call (collection already exists, compatible) must NOT call create_collection."""
    client = _make_mock_client(collection_exists=True, dense_size=384)
    ensure_company_collection(client)
    client.create_collection.assert_not_called()


def test_idempotent_two_calls_do_not_raise():
    """
    Simulating two sequential calls:
      call 1 → collection absent  (creates it)
      call 2 → collection present (returns silently)
    Neither call may raise.
    """
    # First call: collection absent.
    client_1 = _make_mock_client(collection_exists=False)
    ensure_company_collection(client_1)  # must not raise

    # Second call: collection now present with correct config.
    client_2 = _make_mock_client(collection_exists=True, dense_size=384)
    ensure_company_collection(client_2)  # must not raise


# ---------------------------------------------------------------------------
# Incompatible vector config → ValueError
# ---------------------------------------------------------------------------

def test_incompatible_dense_size_raises():
    """
    If the collection exists but its dense vector has a different size,
    ensure_company_collection must raise ValueError.
    """
    client = _make_mock_client(collection_exists=True, dense_size=768)  # wrong dim

    with pytest.raises(ValueError, match="incompatible vector config"):
        ensure_company_collection(client, embed_dim=384)


def test_incompatible_distance_raises():
    """
    If the collection exists but its dense vector uses a different distance,
    ensure_company_collection must raise ValueError.
    """
    from qdrant_client.models import Distance

    dense_params = SimpleNamespace(size=384, distance=Distance.DOT)  # wrong distance
    vectors_cfg = {"dense": dense_params}
    collection_info = SimpleNamespace(
        config=SimpleNamespace(params=SimpleNamespace(vectors=vectors_cfg))
    )
    client = MagicMock()
    client.collection_exists.return_value = True
    client.get_collection.return_value = collection_info

    with pytest.raises(ValueError, match="incompatible vector config"):
        ensure_company_collection(client, embed_dim=384)


def test_missing_dense_vector_raises():
    """
    If the collection exists but has no 'dense' named vector at all,
    ensure_company_collection must raise ValueError.
    """
    vectors_cfg = {}  # no "dense" key
    collection_info = SimpleNamespace(
        config=SimpleNamespace(params=SimpleNamespace(vectors=vectors_cfg))
    )
    client = MagicMock()
    client.collection_exists.return_value = True
    client.get_collection.return_value = collection_info

    with pytest.raises(ValueError, match="incompatible vector config"):
        ensure_company_collection(client, embed_dim=384)


# ---------------------------------------------------------------------------
# COMPANY_COLLECTION constant
# ---------------------------------------------------------------------------

def test_collection_name_constant():
    assert COMPANY_COLLECTION == "company_clauses"


# ---------------------------------------------------------------------------
# Integration tests (require real Qdrant — skipped unless QDRANT_URL is set)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qdrant_client():
    """Real QdrantClient, skipped when QDRANT_URL is not set."""
    qdrant_url = os.environ.get("QDRANT_URL")
    if not qdrant_url:
        pytest.skip("QDRANT_URL not set — skipping Qdrant integration tests")

    from qdrant_client import QdrantClient as _QC

    api_key = os.environ.get("QDRANT_API_KEY", "")
    client = _QC(url=qdrant_url, api_key=api_key)
    yield client

    # Teardown: remove test collection if it was created.
    try:
        client.delete_collection(COMPANY_COLLECTION)
    except Exception:
        pass


@pytest.mark.qdrant
def test_integration_create_collection(qdrant_client):
    """Integration: ensure_company_collection creates the collection on a real cluster."""
    ensure_company_collection(qdrant_client, embed_dim=384)
    assert qdrant_client.collection_exists(COMPANY_COLLECTION)


@pytest.mark.qdrant
def test_integration_idempotent(qdrant_client):
    """Integration: calling twice on a real cluster must not raise."""
    ensure_company_collection(qdrant_client, embed_dim=384)
    ensure_company_collection(qdrant_client, embed_dim=384)  # must not raise
