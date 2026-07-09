"""Dependency-injection composition root — the only place the object graph
is built (no DI framework; architecture §3.7).

settings → engine/session factory → repositories → domain services →
application services. Routers depend on the thin providers below; tests
build the same graph against SQLite with a null event publisher.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from langops_api.application.services.ingest import EventPublisher, IngestTelemetryService
from langops_api.application.services.queries import (
    GetExecutionDetailService,
    GetNodeDetailService,
    ListExecutionsService,
    SearchLogsService,
    SearchService,
)
from langops_api.application.services.reports import (
    CompareExecutionsService,
    GetCostReportService,
    GetMetricsService,
    GetStateEvolutionService,
    GetThreadDetailService,
    ListGraphsService,
    ListThreadsService,
)
from langops_api.domain.services import CostCalculator, ExecutionComparator, StateDiffer
from langops_api.infrastructure.cache import (
    EVENTS_CHANNEL,
    NullEventPublisher,
    RedisEventPublisher,
)
from langops_api.infrastructure.db.repositories import (
    PostgresExecutionRepository,
    PostgresGraphRepository,
    PostgresLlmCallRepository,
    PostgresLogRepository,
    PostgresNodeExecutionRepository,
    PostgresProjectRepository,
    PostgresSearchRepository,
    PostgresStateSnapshotRepository,
    PostgresToolCallRepository,
)
from langops_api.infrastructure.db.session import create_engine, create_session_factory
from langops_api.infrastructure.otlp import ParsedSpan, parse_traces
from langops_api.infrastructure.pricing import PricingCatalog
from langops_api.infrastructure.settings import Settings


class Container:
    """Long-lived resources, created in the FastAPI lifespan."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = create_engine(settings.database_url)
        self.session_factory = create_session_factory(self.engine)
        self.cost_calculator = CostCalculator()
        self.state_differ = StateDiffer()
        self.execution_comparator = ExecutionComparator()
        # Pricing catalog is loaded once from JSON at startup (ADR-0002).
        self.pricing = PricingCatalog(settings.pricing_catalog_dir)
        self.publisher: EventPublisher
        if settings.redis_url:
            self.redis: Redis | None = Redis.from_url(settings.redis_url)
            self.publisher = RedisEventPublisher(self.redis)
        else:
            self.redis = None
            self.publisher = NullEventPublisher()

    async def ensure_default_project(self) -> None:
        """Create the default project once at startup, before serving requests.

        Removes the first-request creation race under concurrent ingestion.
        """
        async with self.session_factory() as session, session.begin():
            await PostgresProjectRepository(session).get_or_create_default()

    async def dispose(self) -> None:
        await self.engine.dispose()
        if self.redis is not None:
            await self.redis.aclose()

    async def subscribe_events(self) -> AsyncIterator[str | None]:
        """Yield each `execution.updated` payload; `None` is a keep-alive tick.

        Bridges the Redis pub/sub channel to the SSE endpoint. Without Redis it
        just emits keep-alives so the connection stays open.
        """
        if self.redis is None:
            while True:
                yield None
                await asyncio.sleep(15)
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(EVENTS_CHANNEL)
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
                if message is None:
                    yield None
                    continue
                data = message["data"]
                yield data.decode() if isinstance(data, bytes) else str(data)
        finally:
            await pubsub.unsubscribe(EVENTS_CHANNEL)
            await pubsub.aclose()


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
        snapshots=PostgresStateSnapshotRepository(session),
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


def get_search_logs_service(
    session: AsyncSession = Depends(get_session),
) -> SearchLogsService:
    return SearchLogsService(logs=PostgresLogRepository(session))


def get_list_graphs_service(
    session: AsyncSession = Depends(get_session),
) -> ListGraphsService:
    return ListGraphsService(
        projects=PostgresProjectRepository(session),
        graphs=PostgresGraphRepository(session),
    )


def get_state_evolution_service(
    session: AsyncSession = Depends(get_session),
) -> GetStateEvolutionService:
    return GetStateEvolutionService(
        executions=PostgresExecutionRepository(session),
        snapshots=PostgresStateSnapshotRepository(session),
        nodes=PostgresNodeExecutionRepository(session),
    )


def get_cost_report_service(
    session: AsyncSession = Depends(get_session),
) -> GetCostReportService:
    return GetCostReportService(
        projects=PostgresProjectRepository(session),
        llm_calls=PostgresLlmCallRepository(session),
    )


def get_search_service(
    session: AsyncSession = Depends(get_session),
) -> SearchService:
    return SearchService(
        projects=PostgresProjectRepository(session),
        search=PostgresSearchRepository(session),
    )


def get_list_threads_service(
    session: AsyncSession = Depends(get_session),
) -> ListThreadsService:
    return ListThreadsService(
        projects=PostgresProjectRepository(session),
        executions=PostgresExecutionRepository(session),
    )


def get_thread_detail_service(
    session: AsyncSession = Depends(get_session),
) -> GetThreadDetailService:
    return GetThreadDetailService(
        projects=PostgresProjectRepository(session),
        executions=PostgresExecutionRepository(session),
    )


def get_metrics_service(
    session: AsyncSession = Depends(get_session),
) -> GetMetricsService:
    return GetMetricsService(
        projects=PostgresProjectRepository(session),
        executions=PostgresExecutionRepository(session),
    )


def get_compare_service(
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> CompareExecutionsService:
    return CompareExecutionsService(
        detail=get_execution_detail_service(session),
        state_differ=container.state_differ,
        comparator=container.execution_comparator,
        snapshots=PostgresStateSnapshotRepository(session),
    )


def get_trace_parser() -> Callable[[bytes, str], list[ParsedSpan]]:
    return parse_traces
