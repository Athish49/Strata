"""
Tests for task 1.2.2: R2 client (r2.py) and key builder (r2_keys.py).

All R2 client tests use moto to mock S3 — no real R2 calls are made.
moto does not intercept custom endpoint_url values, so we patch
`app.company_ingest.store.r2._get_client` to return a standard boto3
S3 client (no endpoint_url) that moto can intercept.
"""

import hashlib
from pathlib import Path
from unittest import mock

import boto3
import pytest
from moto import mock_aws

# ---------------------------------------------------------------------------
# Key-builder tests (pure functions – no mock needed)
# ---------------------------------------------------------------------------

from app.company_ingest.store import r2_keys  # noqa: E402
import app.company_ingest.store.r2 as r2_mod   # noqa: E402


FAKE_BUCKET = "test-bucket"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_moto_client():
    """Return a plain boto3 S3 client that moto can intercept."""
    return boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="fake-key",
        aws_secret_access_key="fake-secret",
    )


@pytest.fixture()
def r2(monkeypatch):
    """
    Activate moto, create the fake bucket, and patch r2_mod so it uses
    the moto-interceptable client and the fake bucket name.
    """
    with mock_aws():
        client = _make_moto_client()
        client.create_bucket(Bucket=FAKE_BUCKET)

        monkeypatch.setattr(r2_mod, "_get_client", lambda: _make_moto_client())
        monkeypatch.setattr(r2_mod.settings, "R2_BUCKET_NAME", FAKE_BUCKET)

        yield r2_mod


def _good_meta(data: bytes) -> dict:
    return {
        "sha256": _sha256(data),
        "content_type": "application/octet-stream",
        "doc_id": "doc_001",
        "version": "v1",
        "profile": "tariff",
    }


# ===========================================================================
# Key-builder tests
# ===========================================================================

class TestR2Keys:
    COMPANY = "rpl"
    DOC = "doc_001"
    VER = "v1"
    RUN = "run_abc"

    def test_raw_doc_key(self):
        key = r2_keys.raw_doc_key(self.COMPANY, self.DOC, self.VER, "doc_001_v1.md")
        assert key == "company/rpl/raw/doc_001/v1/doc_001_v1.md"

    def test_raw_dataset_key(self):
        key = r2_keys.raw_dataset_key(self.COMPANY, self.DOC, self.VER, "tariff_table")
        assert key == "company/rpl/raw/doc_001/v1/data/tariff_table.csv"

    def test_raw_render_key(self):
        key = r2_keys.raw_render_key(self.COMPANY, self.DOC, self.VER, "page1.png")
        assert key == "company/rpl/raw/doc_001/v1/render/page1.png"

    def test_global_file_key(self):
        key = r2_keys.global_file_key(self.COMPANY, self.RUN, "manifest.json")
        assert key == "company/rpl/global/run_abc/manifest.json"

    def test_derived_clauses_key(self):
        key = r2_keys.derived_clauses_key(self.COMPANY, self.DOC, self.VER)
        assert key == "company/rpl/derived/doc_001/v1/clauses.jsonl"

    def test_parquet_key(self):
        key = r2_keys.parquet_key(self.COMPANY, self.DOC, self.VER, "prices")
        assert key == "company/rpl/derived/doc_001/v1/datasets/prices.parquet"

    def test_global_parquet_key(self):
        key = r2_keys.global_parquet_key(self.COMPANY, "all_ops")
        assert key == "company/rpl/derived/global/ops/all_ops.parquet"

    def test_report_key(self):
        key = r2_keys.report_key(self.COMPANY, self.RUN)
        assert key == "company/rpl/ingest_runs/run_abc/report.json"

    def test_llm_key(self):
        key = r2_keys.llm_key(self.COMPANY, self.RUN, "parse", "unit_01")
        assert key == "company/rpl/ingest_runs/run_abc/llm/parse/unit_01.json"

    def test_sanitize_version_spaces(self):
        assert r2_keys.sanitize_version("v 1 2") == "v_1_2"

    def test_sanitize_version_no_spaces(self):
        assert r2_keys.sanitize_version("v1.2") == "v1.2"

    def test_version_with_spaces_in_key(self):
        key = r2_keys.raw_doc_key(self.COMPANY, self.DOC, "v 1", "file.md")
        assert " " not in key
        assert "v_1" in key


# ===========================================================================
# R2 client tests
# ===========================================================================

class TestR2Client:

    # --- put_bytes / write-once -----------------------------------------

    def test_put_bytes_returns_ok(self, r2):
        data = b"hello world"
        result = r2.put_bytes("test/key.txt", data, _good_meta(data))
        assert result == "ok"

    def test_put_bytes_same_sha256_returns_unchanged(self, r2):
        data = b"idempotent content"
        meta = _good_meta(data)
        r2.put_bytes("test/same.txt", data, meta)
        result = r2.put_bytes("test/same.txt", data, meta)
        assert result == "unchanged"

    def test_put_bytes_different_sha256_raises(self, r2):
        data1 = b"version one"
        data2 = b"version two"
        r2.put_bytes("test/conflict.txt", data1, _good_meta(data1))
        with pytest.raises(ValueError, match="different sha256"):
            r2.put_bytes("test/conflict.txt", data2, _good_meta(data2))

    def test_put_bytes_injects_sha256_if_missing(self, r2):
        data = b"auto hash"
        meta = {
            "content_type": "text/plain",
            "doc_id": "d1",
            "version": "v1",
            "profile": "x",
        }
        result = r2.put_bytes("test/auto.txt", data, meta)
        assert result == "ok"

    # --- put_file --------------------------------------------------------

    def test_put_file(self, r2, tmp_path):
        p = tmp_path / "doc.md"
        p.write_bytes(b"# Doc\ncontent")
        result = r2.put_file("test/doc.md", p, _good_meta(p.read_bytes()))
        assert result == "ok"

    # --- get_bytes -------------------------------------------------------

    def test_get_bytes_roundtrip(self, r2):
        data = b"roundtrip data"
        r2.put_bytes("test/rt.bin", data, _good_meta(data))
        assert r2.get_bytes("test/rt.bin") == data

    # --- exists ----------------------------------------------------------

    def test_exists_true(self, r2):
        data = b"exists test"
        r2.put_bytes("test/ex.bin", data, _good_meta(data))
        assert r2.exists("test/ex.bin") is True

    def test_exists_false(self, r2):
        assert r2.exists("test/no_such_key.bin") is False

    # --- list_prefix -----------------------------------------------------

    def test_list_prefix(self, r2):
        for k in ["prefix/a.txt", "prefix/b.txt", "other/c.txt"]:
            data = k.encode()
            r2.put_bytes(k, data, _good_meta(data))
        result = r2.list_prefix("prefix/")
        assert sorted(result) == ["prefix/a.txt", "prefix/b.txt"]

    def test_list_prefix_empty(self, r2):
        assert r2.list_prefix("nonexistent/") == []
