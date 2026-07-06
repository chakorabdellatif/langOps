"""Application factory and lifespan.

Router mounting order and the composition root are wired here; see
architecture.md §3.7. The lifespan owns the async engine, Redis pool, and
pricing cache (created on startup, disposed on shutdown) — added in Phase 2.
"""

from fastapi import FastAPI

from langops_api.presentation.api.v1.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="LangOps API",
        version="0.1.0",
        docs_url="/docs",
    )

    app.include_router(health_router, prefix="/api/v1")
    # Phase 2 (tasks.md): query routers (executions, nodes, graphs, costs,
    # metrics, logs), the OTLP ingest router at /v1/traces, and the SSE
    # events endpoint.

    return app


app = create_app()
