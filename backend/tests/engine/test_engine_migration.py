"""Pure string checks on the engine schema migration (no DB)."""
import importlib.util
from pathlib import Path
from unittest import mock

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[2]
MIG = BACKEND / "migrations" / "versions" / "e5a1c7d9b304_engine_schema.py"

TABLES = [
    "runs", "change_records", "candidates", "findings", "doc_rollups",
    "radar_items", "whatif_scenarios", "finding_reviews", "score_reports", "llm_calls",
]
CHECK_VALUES = [
    "'kb'", "'baseline'", "'whatif'", "'running'", "'done'", "'failed'",
    "'high'", "'medium'", "'low'", "'rule'", "'llm'", "'flagged'", "'cleared'",
    "'yes'", "'no'", "'unclear'", "'text_edit'", "'repeal'", "'accept'", "'reject'",
]


def _load():
    spec = importlib.util.spec_from_file_location("engine_mig", MIG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _capture(fn):
    mod = _load()
    out = []
    with mock.patch.object(mod.op, "execute", side_effect=lambda s: out.append(str(s))):
        getattr(mod, fn)()
    return "\n".join(out)


def _script():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return ScriptDirectory.from_config(cfg)


def test_single_head_and_chain():
    script = _script()
    assert script.get_heads() == ["e5a1c7d9b304"]
    rev = script.get_revision("e5a1c7d9b304")
    assert rev.down_revision == "34ff74b6868a"


def test_upgrade_sql_has_tables_and_checks():
    sql = _capture("upgrade")
    assert "CREATE SCHEMA IF NOT EXISTS engine" in sql
    for t in TABLES:
        assert f"CREATE TABLE engine.{t} " in sql
    for v in CHECK_VALUES:
        assert v in sql
    assert "UNIQUE (change_id, clause_pk)" in sql
    assert "WHERE valid" in sql
    assert "PRIMARY KEY (run_id, doc_id)" in sql
    assert "PRIMARY KEY (run_id, change_id)" in sql


def test_downgrade_drops_schema():
    sql = _capture("downgrade")
    assert "DROP SCHEMA IF EXISTS engine CASCADE" in sql
