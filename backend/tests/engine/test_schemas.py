import pytest
from pydantic import ValidationError

from app.engine import config as ec
from app.engine import schemas as s


def _vc():
    return dict(kind="period", unit="days", day_type="business", old_value_text="10",
                new_value_text="15", old_value_num=10, new_value_num=15, subject="response time")


def test_characterization_round_trip():
    c = s.Characterization(obligation_changed=True, direction="tightened", summary="x",
                           value_changes=[_vc()], added_requirements=[], removed_requirements=[],
                           quotes={"s1": "a", "s2": "b"})
    assert s.Characterization.model_validate_json(c.model_dump_json()) == c


def test_value_change_bad_kind():
    with pytest.raises(ValidationError):
        s.ValueChange(**{**_vc(), "kind": "bogus"})


def test_invalid_enums_rejected():
    with pytest.raises(ValidationError):
        s.JudgeResult(affected=True, finding_type="nope", severity="high", quotes={},
                      rationale="r", confidence=0.9)
    with pytest.raises(ValidationError):
        s.RadarResult(obligation_changed=True, applicable="maybe", attribute_basis=[],
                      affected_activity="a", reason="r")
    with pytest.raises(ValidationError):
        s.ChangeInput(origin="other", source_system="iac", citation="c")


def test_change_input_defaults_and_radar_round_trip():
    ci = s.ChangeInput(origin="whatif", source_system="iac", citation="c")
    assert ci.s2_section_id is None and ci.s1_text is None
    r = s.RadarResult(obligation_changed=True, applicable="yes", attribute_basis=["k"],
                      affected_activity="a", reason="r")
    assert s.RadarResult.model_validate(r.model_dump()) == r


def test_enum_tuples():
    assert s.MATCH_PATHS == ("direct_section", "direct_rule", "register_hop", "value_echo")
    assert set(s.NOISE_CLASSES) <= set(s.CHANGE_CLASSES)
    assert len(s.FINDING_TYPES) == 7 and len(s.VERDICTS) == 5


def test_review_request_validation():
    with pytest.raises(ValidationError):
        s.ReviewRequest(action="reject", person_id="P1")
    with pytest.raises(ValidationError):
        s.ReviewRequest(action="reject", note="  ", person_id="P1")
    assert s.ReviewRequest(action="reject", note="wrong", person_id="P1").note == "wrong"
    assert s.ReviewRequest(action="accept", person_id="P1").note is None


def test_finding_item_and_ledger_row():
    f = s.FindingItem(finding_id="f", clause_id="c", citation="x", finding_type="conflict",
                      verdict="review", severity="low", short_rationale="r")
    assert f.model_dump()["short_rationale"] == "r"
    with pytest.raises(ValidationError):
        s.LedgerRow(change_id="1", citation="x", change_class="bad", in_footprint=True,
                    cited_clause_count=0)


def test_engine_settings_defaults(monkeypatch):
    for k in list(ec.EngineSettings.model_fields):
        monkeypatch.delenv(k, raising=False)
    e = ec.EngineSettings(_env_file=None)
    assert e.ENGINE_CHARACTERIZE_MODEL == "claude-sonnet-5-5"
    assert e.ENGINE_RADAR_MODEL == "claude-haiku-4-5-20251001"
    assert e.ENGINE_MIN_CONFIDENCE == 0.6 and e.ENGINE_RENUMBER_JACCARD == 0.80
    assert e.ENGINE_JUDGE_MAX_SECTION_CHARS == 8000 and e.ENGINE_COMPANY_ID == "rpl"
    assert (e.ENGINE_MAX_LLM_CALLS_KB, e.ENGINE_MAX_LLM_CALLS_WHATIF) == (900, 300)
    assert (e.ENGINE_LLM_CONCURRENCY, e.ENGINE_RADAR_CONCURRENCY) == (8, 16)


def test_engine_settings_env_override(monkeypatch):
    monkeypatch.setenv("ENGINE_MIN_CONFIDENCE", "0.75")
    monkeypatch.setenv("ENGINE_MAX_LLM_CALLS_KB", "10")
    e = ec.EngineSettings(_env_file=None)
    assert e.ENGINE_MIN_CONFIDENCE == 0.75 and e.ENGINE_MAX_LLM_CALLS_KB == 10


def test_app_config_import_and_engine_keys_tolerated(monkeypatch):
    from app.config import Settings, settings
    assert settings.DATABASE_URL
    monkeypatch.setenv("ENGINE_JUDGE_MODEL", "x")
    Settings()  # must not raise on ENGINE_* keys
