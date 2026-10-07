"""Task 2.1.1 — Allowlist / denylist for the corpus file collector.

rel_path conventions
--------------------
All rel_path values are computed relative to CORPUS_ROOT.parent, which
means they carry the ``corpus/`` prefix:

    corpus/docs/RPL-CMP-REG-001/RPL-CMP-REG-001_v4.0.md
    corpus/_global/company_profile.yaml
    corpus/grounding/T10.json
"""
from __future__ import annotations

from pathlib import PurePosixPath

ALLOW_GLOBS = [
    "corpus/docs/*/*.md",
    "corpus/docs/*/data/*.csv",
    "corpus/docs/*/render/**",
    "corpus/_global/**",
]

DENY_GLOBS = [
    "**/*.basis.json",
    "**/scripts/**",
    "**/data/README.md",
    "**/_manifest.json",
    "corpus/grounding/**",
    "corpus/qa/**",
    "corpus/validation/**",
    "corpus/eval/**",
]


def is_allowed(rel_path: str) -> bool:
    """Return True if *rel_path* should be processed.

    DENY wins over ALLOW.  *rel_path* must include the ``corpus/`` prefix
    (i.e. be relative to CORPUS_ROOT.parent).
    """
    p = PurePosixPath(rel_path)

    for pattern in DENY_GLOBS:
        if p.full_match(pattern):
            return False

    for pattern in ALLOW_GLOBS:
        if p.full_match(pattern):
            return True

    return False
