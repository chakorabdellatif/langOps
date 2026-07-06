"""Dependency-injection composition root — the only place the object graph
is built (no DI framework; architecture §3.7).

settings → engine/session factory → repositories → domain services →
application services. Routers depend on the thin providers below; tests
build the same graph against SQLite with a null event publisher.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from langops_api.application.services.ingest import EventPublisher, IngestTelemetryService
from langops_api.application.services.queries import (
    GetExecutionDetailService,
    GetNodeDetailService,
    ListExecutionsService,
)
from langops_api.domain.services import CostCalculator, StateDiffer
from langops_api.infrastructure.cache import NullEventPublisher, RedisEventPublisher
from langops_api.infrastructure.db.repositories import (
    PostgresExecutionRepository,
    PostgresGraphRepository,
    PostgresLlmCallRepository,
    PostgresLogRepository,
    PostgresNodeExecutionRepository,
    PostgresProjectRepository,
    PostgresStateSnapshotRepository,
    PostgresToolCallRepository,
)
from langops_api.infrastructure.db.session import create_engine, create_session_factory
from langops_api.infrastructure.otlp import ParsedSpan, parse_traces
from langops_api.infrastructure.pricing import CatalogPricingRepository
from langops_api.infrastructure.settings import Settings


class Container:
    """Long-lived resources, created in the FastAPI lifespan."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = create_engine(settings.database_url)
        self.session_factory = create_session_factory(self.engine)
        self.cost_calculator = CostCalculator()
        self.state_differ = StateDiffer()
        # Pricing catalog is loaded once from JSON at startup (ADR-0002).
        self.pricing = CatalogPricingRepository.load(settings.pricing_catalog_dir)
        self.publisher: EventPublisher
        if settings.redis_url:
            self.redis: Redis | None = Redis.from_url(settings.redis_url)
            self.publisher = RedisEventPublisher(self.redis)
        else:
            self.redis = None
            self.publisher = NullEventPublisher()

    async def dispose(self) -> None:
        await self.engine.dispose()
        if self.redis is not None:
            await self.redis.aclose()


# ── request-scoped providers ───────────────────────────────────────────


def get_container(request: Request) -> Container:
    return request.app.state.container


async def get_session(
    container: Container = Depends(get_container),
) -> AsyncIterator[AsyncSession]:
    async with container.session_factory() as session, session.begin():
        yield session


def get_ingest_service(
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> IngestTelemetryService:
    return IngestTelemetryService(
        projects=PostgresProjectRepository(session),
        graphs=PostgresGraphRepository(session),
        executions=PostgresExecutionRepository(session),
        nodes=PostgresNodeExecutionRepository(session),
        llm_calls=PostgresLlmCallRepository(session),
        tool_calls=PostgresToolCallRepository(session),
        snapshots=PostgresStateSnapshotRepository(session),
        logs=PostgresLogRepository(session),
        pricing=container.pricing,
        cost_calculator=container.cost_calculator,
        state_differ=container.state_differ,
        publisher=container.publisher,
    )


def get_list_executions_service(
    session: AsyncSession = Depends(get_session),
) -> ListExecutionsService:
    return ListExecutionsService(
        projects=PostgresProjectRepository(session),
        executions=PostgresExecutionRepository(session),
    )


def get_execution_detail_service(
    session: AsyncSession = Depends(get_session),
) -> GetExecutionDetailService:
    return GetExecutionDetailService(
        executions=PostgresExecutionRepository(session),
        nodes=PostgresNodeExecutionRepository(session),
        graphs=PostgresGraphRepository(session),
        llm_calls=PostgresLlmCallRepository(session),
        tool_calls=PostgresToolCallRepository(session),
        logs=PostgresLogRepository(session),
    )


def get_node_detail_service(
    session: AsyncSession = Depends(get_session),
) -> GetNodeDetailService:
    return GetNodeDetailService(
        nodes=PostgresNodeExecutionRepository(session),
        llm_calls=PostgresLlmCallRepository(session),
        tool_calls=PostgresToolCallRepository(session),
        snapshots=PostgresStateSnapshotRepository(session),
        logs=PostgresLogRepository(session),
    )


def get_trace_parser() -> Callable[[bytes, str], list[ParsedSpan]]:
    return parse_traces
