"""Application factory and lifespan."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from langops_api.composition import Container
from langops_api.domain.errors import InvalidTelemetry, LangOpsError, NotFoundError
from langops_api.infrastructure.settings import Settings
from langops_api.presentation.api.v1.executions import router as executions_router
from langops_api.presentation.api.v1.health import router as health_router
from langops_api.presentation.api.v1.nodes import router as nodes_router
from langops_api.presentation.ingest import router as ingest_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = Container(settings)
        if settings.db_create_tables:
            # Test/dev convenience; real deployments migrate via Alembic.
            # Pricing needs no seeding — it loads from the JSON catalog (ADR-0002).
            from langops_api.infrastructure.db.models import Base

            async with container.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
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

    @app.exception_handler(LangOpsError)
    async def langops_error_handler(request: Request, exc: LangOpsError) -> JSONResponse:
        logger.exception("unhandled LangOpsError", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"code": exc.code, "message": exc.message, "detail": exc.detail},
        )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(executions_router, prefix="/api/v1")
    app.include_router(nodes_router, prefix="/api/v1")
    app.include_router(ingest_router)  # OTLP-spec path: POST /v1/traces

    return app


app = create_app()
