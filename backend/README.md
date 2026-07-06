# langops-api

FastAPI backend for LangOps: OTLP ingestion (`POST /v1/traces`) and the
query REST API (`/api/v1/...`) consumed by the dashboard.

Design: `docs/architecture.md` §3 (layering), §4 (database schema).
Layering is enforced by import-linter (`lint-imports`).
