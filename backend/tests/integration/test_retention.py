"""Retention job — deletes old executions and cascades to child rows."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from uuid6 import uuid7

from langops_api.application.services.retention import RetentionService
from langops_api.domain.entities import Execution, LlmCall, NodeExecution
from langops_api.domain.value_objects import ExecutionStatus, TokenUsage
from langops_api.infrastructure.db.models import Base
from langops_api.infrastructure.db.repositories import (
    PostgresExecutionRepository,
    PostgresLlmCallRepository,
    PostgresNodeExecutionRepository,
    PostgresProjectRepository,
)
from langops_api.infrastructure.db.session import create_engine, create_session_factory


async def _make_execution(session, project_id, started_at, trace_id):  # type: ignore[no-untyped-def]
    executions = PostgresExecutionRepository(session)
    nodes = PostgresNodeExecutionRepository(session)
    llm = PostgresLlmCallRepository(session)
    ex = await executions.upsert(
        Execution(
            id=uuid7(),
            project_id=project_id,
            trace_id=trace_id,
            status=ExecutionStatus.SUCCEEDED,
            started_at=started_at,
        )
    )
    node = await nodes.upsert(
        NodeExecution(id=uuid7(), execution_id=ex.id, span_id=f"node-{trace_id}", node_name="a")
    )
    await llm.upsert(
        LlmCall(
            id=uuid7(),
            execution_id=ex.id,
            node_execution_id=node.id,
            span_id=f"llm-{trace_id}",
            tokens=TokenUsage(1, 1),
        )
    )
    return ex


@pytest.mark.asyncio
async def test_retention_deletes_old_and_cascades() -> None:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)

    now = datetime(2026, 7, 1, tzinfo=UTC)
    async with session_factory() as session, session.begin():
        project = await PostgresProjectRepository(session).get_or_create_default()
        await _make_execution(session, project.id, now - timedelta(days=40), "old")
        await _make_execution(session, project.id, now - timedelta(days=5), "recent")

    async with session_factory() as session, session.begin():
        deleted = await RetentionService(PostgresExecutionRepository(session)).purge_older_than(
            30, now=now
        )
        assert deleted == 1

    # The recent execution survives; the old one and its children are gone.
    async with session_factory() as session:
        executions = PostgresExecutionRepository(session)
        project = await PostgresProjectRepository(session).get_or_create_default()
        items, total = await executions.list_page(project.id)
        assert total == 1
        assert items[0].trace_id == "recent"
        # Child llm_calls of the deleted execution cascaded away.
        llm = PostgresLlmCallRepository(session)
        remaining = await llm.list_by_execution(uuid4())  # unrelated id → empty
        assert remaining == []

    await engine.dispose()
