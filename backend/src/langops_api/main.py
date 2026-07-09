"""Application factory and lifespan."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from langops_api.composition import Container
from langops_api.domain.errors import (
    InvalidTelemetry,
    LangOpsError,
    NotFoundError,
    RequestTooLarge,
)
from langops_api.infrastructure.logging_config import configure_logging
from langops_api.infrastructure.settings import Settings
from langops_api.presentation.api.v1.costs import router as costs_router
from langops_api.presentation.api.v1.executions import router as executions_router
from langops_api.presentation.api.v1.graphs import router as graphs_router
from langops_api.presentation.api.v1.health import router as health_router
from langops_api.presentation.api.v1.logs import router as logs_router
from langops_api.presentation.api.v1.metrics import router as metrics_router
from langops_api.presentation.api.v1.nodes import router as nodes_router
from langops_api.presentation.api.v1.search import router as search_router
from langops_api.presentation.api.v1.threads import router as threads_router
from langops_api.presentation.events import router as events_router
from langops_api.presentation.ingest import router as ingest_router

logger = structlog.get_logger("langops_api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = Container(settings)
        if settings.db_create_tables:
            # Test/dev convenience; real deployments migrate via Alembic.
            # Pricing needs no seeding — it loads from the JSON catalog (ADR-0002).
            from langops_api.infrastructure.db.models import Base

            async with container.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        await container.ensure_default_project()
        app.state.container = container
        yield
        await container.dispose()

    app = FastAPI(title="LangOps API", version="0.1.0", docs_url="/docs", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Uniform error contract: {code, message, detail}
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"code": exc.code, "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(InvalidTelemetry)
    async def invalid_telemetry_handler(request: Request, exc: InvalidTelemetry) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"code": exc.code, "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(RequestTooLarge)
    async def too_large_handler(request: Request, exc: RequestTooLarge) -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={"code": exc.code, "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(LangOpsError)
    async def langops_error_handler(request: Request, exc: LangOpsError) -> JSONResponse:
        logger.error("langops_error", code=exc.code, message=exc.message)
        return JSONResponse(
            status_code=500,
            content={"code": exc.code, "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log the full trace server-side; never expose it over the API.
        logger.exception("unhandled_exception", error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"code": "internal_error", "message": "Internal server error", "detail": None},
        )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(executions_router, prefix="/api/v1")
    app.include_router(nodes_router, prefix="/api/v1")
    app.include_router(graphs_router, prefix="/api/v1")
    app.include_router(costs_router, prefix="/api/v1")
    app.include_router(metrics_router, prefix="/api/v1")
    app.include_router(logs_router, prefix="/api/v1")
    app.include_router(threads_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(events_router, prefix="/api/v1")
    app.include_router(ingest_router)  # OTLP-spec path: POST /v1/traces

    return app


app = create_app()
