from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    QDRANT_URL: str
    QDRANT_API_KEY: str
    QDRANT_PROJECT_TAG: str = "strata"
    R2_ENDPOINT: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str

    # Company ingest settings
    CORPUS_ROOT: str = str(Path(__file__).parent.parent / "app" / "company" / "corpus")
    COMPANY_ID: str = "rpl"
    LLM_PROVIDER: str = "anthropic"
    LLM_MODEL: str = "claude-sonnet-5-5"
    LLM_API_KEY: str = ""
    EMBED_MODEL: str = "all-MiniLM-L6-v2"
    EMBED_DIM: int = 384

    class Config:
        env_file = ".env"


settings = Settings()
