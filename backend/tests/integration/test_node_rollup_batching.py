"""Phase 14 — per-node rollups recompute in a single UPDATE.

The old implementation issued one SELECT + one UPDATE per node per span batch;
under real throughput that is the ingest hotspot. This proves the rollup is now
one statement regardless of node count, and that it still produces the same
category/token results.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event

from langops_api.infrastructure.db.models import (
    Base,
    ExecutionModel,
    LlmCallModel,
    NodeExecutionModel,
    ProjectModel,
)
from langops_api.infrastructure.db.repositories import PostgresNodeExecutionRepository
from langops_api.infrastructure.db.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_recompute_rollups_is_one_update_for_many_nodes() -> None:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)

    project_id, execution_id = uuid4(), uuid4()
    async with factory() as session, session.begin():
        session.add(ProjectModel(id=project_id, name="d", slug="d", created_at=datetime.now(UTC)))
        await session.flush()
        session.add(ExecutionModel(id=execution_id, project_id=project_id, trace_id="t"))
        await session.flush()
        # 25 llm nodes, each with one priced LLM call.
        node_ids = [uuid4() for _ in range(25)]
        for i, node_id in enumerate(node_ids):
            session.add(
                NodeExecutionModel(
                    id=node_id, execution_id=execution_id, span_id=f"n{i}", node_name=f"n{i}"
                )
            )
        await session.flush()
        for i, node_id in enumerate(node_ids):
            session.add(
                LlmCallModel(
                    id=uuid4(),
                    execution_id=execution_id,
                    node_execution_id=node_id,
                    span_id=f"l{i}",
                    input_tokens=10,
                    output_tokens=5,
                    cost=Decimal("0.001"),
                    cost_status="priced",
                )
            )

    # Count UPDATE statements against node_executions during the recompute.
    updates: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _count(conn, cursor, statement, params, context, executemany):  # noqa: ANN001
        if statement.lstrip().upper().startswith("UPDATE NODE_EXECUTIONS"):
            updates.append(statement)

    async with factory() as session, session.begin():
        await PostgresNodeExecutionRepository(session).recompute_rollups(execution_id)

    assert len(updates) == 1, f"expected one batched UPDATE, got {len(updates)}"

    # And the rollup is correct: every node is an llm agent with its tokens.
    async with factory() as session:
        rows = (await session.execute(NodeExecutionModel.__table__.select())).mappings().all()
    assert len(rows) == 25
    assert all(r["category"] == "llm" for r in rows)
    assert all(r["input_tokens"] == 10 and r["output_tokens"] == 5 for r in rows)
    assert all(r["cost_status"] == "priced" for r in rows)
    await engine.dispose()
