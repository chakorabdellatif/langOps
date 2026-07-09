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

    # Optional single-tenant API key. When set, every ingest + query request
    # must send `Authorization: Bearer <key>`; empty disables auth (default).
    api_key: str = ""

    # Retention: delete executions older than N days on a periodic in-process
    # task. 0 disables it. `retention_prune_payloads_days` instead nulls large
    # payload columns (messages/response/state) while keeping rollup rows, so
    # metrics history survives; 0 disables.
    retention_days: int = 0
    retention_prune_payloads_days: int = 0
    retention_interval_hours: int = 24

    # Ingestion limits
    ingest_max_payload_bytes: int = 4_194_304
    ingest_max_batch_spans: int = 2_048

    # Optional directory of extra pricing JSON files (ADR-0002); extends the
    # built-in catalog for custom/self-hosted models.
    pricing_catalog_dir: str | None = None

    # Create tables at startup instead of via Alembic (tests/dev only).
    db_create_tables: bool = False
