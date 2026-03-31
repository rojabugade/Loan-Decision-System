from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Credit Analysis Platform"
    app_version: str = "0.1.0"
    environment: str = "dev"

    postgres_dsn: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/credit_ai"
    )
    redis_url: str = "redis://localhost:6379/0"

    model_version: str = "gpt-5.3-codex"
    prompt_version: str = "credit-workflow-v1"

    low_confidence_threshold: float = 0.55
    retrieval_cache_ttl_seconds: int = 300
    retrieval_top_k: int = 8

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),
    )


settings = Settings()
