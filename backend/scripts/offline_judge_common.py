"""Shared helpers for the offline judge export/import scripts (no LLM calls)."""
from __future__ import annotations

import json
from pathlib import Path

from app.engine import judge as J
from app.engine import llm as L
from app.engine.schemas import JudgeResult

STAGE = J.STAGE
SCHEMA = JudgeResult
PROVENANCE = "produced in-session by the assistant (offline stand-in for the API; Anthropic spend limit)"


def build_prompts(item) -> tuple[str, str]:
    """(system, user) exactly as judge.judge_item sends them on the first attempt."""
    return J.system_prompt_for(item), J.build_user_prompt(item)


def cache_key(system: str, user: str) -> str:
    return L.prompt_sha256(system, user, SCHEMA)


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
