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

    class Config:
        env_file = ".env"


settings = Settings()
