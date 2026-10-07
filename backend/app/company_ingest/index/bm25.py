"""Task 6.2.1 — Sparse BM25-style vector helpers for company clause indexing."""
from __future__ import annotations

import re

from app.company_ingest.parse.models import ClauseUnit


def build_sparse_vector(text: str) -> dict[int, float]:
    """Build a simple BM25-style sparse vector over normalized tokens.

    Returns {token_hash: tf_score} as a dict.
    This is a local approximation (no corpus IDF) — just TF with hash keys.

    Steps:
    1. Tokenize: split on non-alphanumeric, lowercase, filter tokens < 2 chars
    2. Count term frequencies
    3. hash_id = hash(token) % (2**20) — 20-bit hash space
    4. tf = count / total_tokens (normalized)
    5. Deduplicate by hash_id (keep highest TF)
    """
    tokens = [t for t in re.split(r"[^a-zA-Z0-9]+", text.lower()) if len(t) >= 2]
    if not tokens:
        return {}

    total = len(tokens)
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1

    result: dict[int, float] = {}
    for token, count in counts.items():
        hash_id = hash(token) % (2 ** 20)
        tf = count / total
        if hash_id not in result or tf > result[hash_id]:
            result[hash_id] = tf

    return result


def build_sparse_vector_for_unit(unit: ClauseUnit) -> dict[int, float]:
    """Build sparse vector from unit.text_norm."""
    return build_sparse_vector(unit.text_norm)
