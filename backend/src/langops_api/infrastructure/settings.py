"""Runtime configuration — environment variables only (12-factor).

Fail fast at startup on invalid config. Inside Docker Compose the defaults
are overridden by service environment; locally they match .env.example.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://langops:langops@localhost:5432/langops"
    redis_url: str = "redis://localhost:6379/0"

    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # Ingestion limits
    ingest_max_payload_bytes: int = 4_194_304
    ingest_max_batch_spans: int = 2_048

    # Create tables at startup instead of via Alembic (tests/dev only).
    db_create_tables: bool = False
