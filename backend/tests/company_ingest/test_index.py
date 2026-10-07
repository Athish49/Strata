"""Task 6.2.1 — Tests for embed.py, bm25.py, and upsert.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_unit(**kwargs) -> ClauseUnit:
    defaults = dict(
        version_id="ver-1",
        doc_id="doc-1",
        clause_id="doc-1:c1",
        local_id="c1",
        parent_clause_id=None,
        unit_kind="section",
        heading_path=["Scope", "Definitions"],
        section_kind="scope",
        ordinal=1,
        char_start=0,
        char_end=100,
        line_start=1,
        text_raw="Raw clause text here.",
        text_norm="Normalized clause text here.",
        text_sha256="abc123",
        role=None,
        assessable=True,
        citations=[],
        parameters=[],
        refs=[],
        terms=[],
    )
    defaults.update(kwargs)
    return ClauseUnit(**defaults)


# ===========================================================================
# embed.py — build_embedded_text
# ===========================================================================

class TestBuildEmbeddedText:
    def test_normal_unit_returns_heading_and_text(self):
        from app.company_ingest.index.embed import build_embedded_text

        unit = make_unit(
            heading_path=["heading", "path"],
            text_norm="some normalized text",
            role="internal_procedure",
            section_kind="scope",
            unit_kind="section",
        )
        result = build_embedded_text(unit)
        assert result == "heading > path | some normalized text"

    def test_boilerplate_returns_empty(self):
        from app.company_ingest.index.embed import build_embedded_text

        unit = make_unit(role="boilerplate")
        result = build_embedded_text(unit)
        assert result == ""

    def test_front_matter_returns_empty(self):
        from app.company_ingest.index.embed import build_embedded_text

        unit = make_unit(section_kind="front_matter")
        result = build_embedded_text(unit)
        assert result == ""

    def test_table_row_with_empty_text_norm_returns_empty(self):
        from app.company_ingest.index.embed import build_embedded_text

        unit = make_unit(unit_kind="table_row", text_norm="   ")
        result = build_embedded_text(unit)
        assert result == ""

    def test_table_row_with_text_norm_is_embedded(self):
        from app.company_ingest.index.embed import build_embedded_text

        unit = make_unit(
            unit_kind="table_row",
            text_norm="some row content",
            heading_path=["Table"],
        )
        result = build_embedded_text(unit)
        assert result != ""
        assert "some row content" in result

    def test_text_norm_truncated_at_2048_chars(self):
        from app.company_ingest.index.embed import build_embedded_text

        long_text = "x" * 3000
        unit = make_unit(text_norm=long_text, heading_path=["H"])
        result = build_embedded_text(unit)
        # The body part (after "H | ") should be at most 2048 chars
        body = result.split(" | ", 1)[1]
        assert len(body) == 2048


# ===========================================================================
# embed.py — embed_texts
# ===========================================================================

class TestEmbedTexts:
    def test_embed_texts_batches_over_64(self):
        from app.company_ingest.index import embed as embed_module

        mock_model = MagicMock()
        # Return correctly-sized arrays for each batch call
        mock_model.encode.side_effect = lambda batch, normalize_embeddings=True: np.zeros(
            (len(batch), 384), dtype=np.float32
        )

        with patch.object(embed_module, "_get_model", return_value=mock_model):
            texts = [f"text {i}" for i in range(100)]
            results = embed_module.embed_texts(texts)

        # Should have been called twice: batch of 64 + batch of 36
        assert mock_model.encode.call_count == 2
        assert len(results) == 100

    def test_embed_texts_empty_returns_empty(self):
        from app.company_ingest.index.embed import embed_texts

        assert embed_texts([]) == []

    def test_embed_texts_returns_list_of_lists(self):
        from app.company_ingest.index import embed as embed_module

        fake_array = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_array

        with patch.object(embed_module, "_get_model", return_value=mock_model):
            results = embed_module.embed_texts(["hello"])

        assert isinstance(results, list)
        assert isinstance(results[0], list)
        assert results[0] == pytest.approx([0.1, 0.2, 0.3], abs=1e-5)


# ===========================================================================
# bm25.py — build_sparse_vector
# ===========================================================================

class TestBuildSparseVector:
    def test_known_text_returns_nonempty_dict_with_floats(self):
        from app.company_ingest.index.bm25 import build_sparse_vector

        result = build_sparse_vector("hello world foo")
        assert len(result) > 0
        for k, v in result.items():
            assert isinstance(k, int)
            assert isinstance(v, float)

    def test_empty_text_returns_empty_dict(self):
        from app.company_ingest.index.bm25 import build_sparse_vector

        assert build_sparse_vector("") == {}

    def test_repeated_token_has_higher_tf(self):
        from app.company_ingest.index.bm25 import build_sparse_vector

        once = build_sparse_vector("hello world")
        twice = build_sparse_vector("hello hello world")

        hello_hash = hash("hello") % (2 ** 20)
        assert hello_hash in once
        assert hello_hash in twice
        assert twice[hello_hash] > once[hello_hash]

    def test_short_tokens_excluded(self):
        from app.company_ingest.index.bm25 import build_sparse_vector

        # "a" and "b" are < 2 chars, "ab" is fine
        result = build_sparse_vector("a b ab")
        a_hash = hash("a") % (2 ** 20)
        b_hash = hash("b") % (2 ** 20)
        ab_hash = hash("ab") % (2 ** 20)

        # "ab" should be present (2 chars)
        assert ab_hash in result
        # "a" and "b" should not be present (unless there is a hash collision)
        # We check by verifying the tokenized count is just "ab"
        tokens = [t for t in result.keys()]
        # Verify we have exactly one unique token (ab)
        assert len(result) == 1

    def test_all_short_tokens_gives_empty(self):
        from app.company_ingest.index.bm25 import build_sparse_vector

        result = build_sparse_vector("a b c")
        assert result == {}


# ===========================================================================
# upsert.py
# ===========================================================================

class TestUpsertClauses:
    def _make_mock_client(self):
        mock_client = MagicMock()
        mock_client.upsert = MagicMock()
        return mock_client

    @pytest.mark.asyncio
    async def test_units_with_embedded_text_call_upsert(self):
        from app.company_ingest.index import upsert as upsert_module

        unit = make_unit(
            heading_path=["Section"],
            text_norm="some text content",
            role="internal_procedure",
        )
        ctx = RunContext()
        mock_client = self._make_mock_client()

        with patch.object(upsert_module, "_make_client", return_value=mock_client), \
             patch("app.company_ingest.index.upsert.embed_texts", return_value=[[0.1] * 384]):
            await upsert_module.upsert_clauses(
                [unit], company_id="comp1", version_id="ver1", ctx=ctx
            )

        mock_client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_boilerplate_units_skipped(self):
        from app.company_ingest.index import upsert as upsert_module

        unit = make_unit(role="boilerplate", text_norm="should be skipped")
        ctx = RunContext()
        mock_client = self._make_mock_client()

        with patch.object(upsert_module, "_make_client", return_value=mock_client), \
             patch("app.company_ingest.index.upsert.embed_texts", return_value=[]):
            await upsert_module.upsert_clauses(
                [unit], company_id="comp1", version_id="ver1", ctx=ctx
            )

        mock_client.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_point_id_is_deterministic(self):
        from app.company_ingest.index import upsert as upsert_module
        from app.company_ingest.ids import stable_uuid

        unit = make_unit(
            clause_id="doc-1:c1",
            heading_path=["Section"],
            text_norm="content",
            role="internal_procedure",
        )
        ctx = RunContext()
        captured_points = []

        def capture_upsert(collection_name, points):
            captured_points.extend(points)

        mock_client = self._make_mock_client()
        mock_client.upsert.side_effect = capture_upsert

        with patch.object(upsert_module, "_make_client", return_value=mock_client), \
             patch("app.company_ingest.index.upsert.embed_texts", return_value=[[0.0] * 384]):
            await upsert_module.upsert_clauses(
                [unit], company_id="comp1", version_id="ver1", ctx=ctx
            )

        expected_id = str(stable_uuid("comp1", "ver1", "doc-1:c1"))
        assert captured_points[0].id == expected_id

    @pytest.mark.asyncio
    async def test_payload_includes_required_fields(self):
        from app.company_ingest.index import upsert as upsert_module

        unit = make_unit(
            heading_path=["Section"],
            text_norm="some text",
            role="internal_procedure",
            doc_id="doc-42",
            clause_id="doc-42:c5",
        )
        ctx = RunContext()
        captured_points = []

        def capture_upsert(collection_name, points):
            captured_points.extend(points)

        mock_client = self._make_mock_client()
        mock_client.upsert.side_effect = capture_upsert

        with patch.object(upsert_module, "_make_client", return_value=mock_client), \
             patch("app.company_ingest.index.upsert.embed_texts", return_value=[[0.0] * 384]):
            await upsert_module.upsert_clauses(
                [unit], company_id="testco", version_id="v99", ctx=ctx
            )

        payload = captured_points[0].payload
        assert payload["company_id"] == "testco"
        assert payload["clause_id"] == "doc-42:c5"
        assert "project" in payload

    @pytest.mark.asyncio
    async def test_batch_size_respected(self):
        from app.company_ingest.index import upsert as upsert_module

        units = [
            make_unit(
                clause_id=f"doc-1:c{i}",
                local_id=f"c{i}",
                heading_path=["Section"],
                text_norm=f"content {i}",
                role="internal_procedure",
            )
            for i in range(2)
        ]
        ctx = RunContext()
        mock_client = self._make_mock_client()

        with patch.object(upsert_module, "_make_client", return_value=mock_client), \
             patch(
                 "app.company_ingest.index.upsert.embed_texts",
                 side_effect=[[[0.0] * 384], [[0.0] * 384]],
             ):
            await upsert_module.upsert_clauses(
                units, company_id="comp1", version_id="ver1", ctx=ctx, batch_size=1
            )

        # batch_size=1 → 2 separate upsert calls
        assert mock_client.upsert.call_count == 2

    @pytest.mark.asyncio
    async def test_ctx_count_incremented_per_point(self):
        from app.company_ingest.index import upsert as upsert_module

        units = [
            make_unit(
                clause_id=f"doc-1:c{i}",
                local_id=f"c{i}",
                heading_path=["Section"],
                text_norm=f"content {i}",
                role="internal_procedure",
            )
            for i in range(3)
        ]
        ctx = RunContext()
        mock_client = self._make_mock_client()

        with patch.object(upsert_module, "_make_client", return_value=mock_client), \
             patch(
                 "app.company_ingest.index.upsert.embed_texts",
                 return_value=[[0.0] * 384, [0.0] * 384, [0.0] * 384],
             ):
            await upsert_module.upsert_clauses(
                units, company_id="comp1", version_id="ver1", ctx=ctx
            )

        assert ctx.stats.get("clauses_indexed") == 3
