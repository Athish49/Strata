from pydantic_settings import BaseSettings, SettingsConfigDict


class EngineSettings(BaseSettings):
    """Engine settings (architecture.md section 6). Reads .env, ignores non-engine keys."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENGINE_COMPANY_ID: str = "rpl"
    ENGINE_CHARACTERIZE_MODEL: str = "claude-sonnet-5-5"
    ENGINE_JUDGE_MODEL: str = "claude-sonnet-5-5"
    ENGINE_RADAR_MODEL: str = "claude-haiku-4-5-20251001"
    ENGINE_MIN_CONFIDENCE: float = 0.6
    ENGINE_RENUMBER_JACCARD: float = 0.80
    ENGINE_JUDGE_MAX_SECTION_CHARS: int = 8000
    ENGINE_JUDGE_WINDOW_CHARS: int = 1500

    # Cost caps and concurrency (architecture.md section 5, rule 7)
    ENGINE_MAX_LLM_CALLS_KB: int = 900
    ENGINE_MAX_LLM_CALLS_WHATIF: int = 300
    ENGINE_LLM_CONCURRENCY: int = 8
    ENGINE_RADAR_CONCURRENCY: int = 16


engine_settings = EngineSettings()

# Module-level aliases for the constants named in the spec.
MAX_LLM_CALLS_KB = engine_settings.ENGINE_MAX_LLM_CALLS_KB
MAX_LLM_CALLS_WHATIF = engine_settings.ENGINE_MAX_LLM_CALLS_WHATIF
LLM_CONCURRENCY = engine_settings.ENGINE_LLM_CONCURRENCY
RADAR_CONCURRENCY = engine_settings.ENGINE_RADAR_CONCURRENCY
JUDGE_WINDOW_CHARS = engine_settings.ENGINE_JUDGE_WINDOW_CHARS
