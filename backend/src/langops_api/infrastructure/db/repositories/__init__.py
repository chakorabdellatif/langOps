"""Postgres implementations of the domain repository Protocols.

Upserts use select-then-insert/update on the OTel natural keys (trace_id /
span_id) inside the request's transaction — portable across dialects and
idempotent under OTLP at-least-once redelivery.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from langops_api.domain.entities import (
    Execution,
    Graph,
    LlmCall,
    LogRecord,
    NodeExecution,
    Project,
    StateSnapshot,
    ToolCall,
)
from langops_api.domain.value_objects import (
    CheckpointRef,
    Cost,
    CostStatus,
    ExecutionStatus,
    TokenUsage,
)
from langops_api.infrastructure.db.models import (
    ExecutionModel,
    GraphModel,
    LlmCallModel,
    LogModel,
    NodeExecutionModel,
    ProjectModel,
    StateSnapshotModel,
    ToolCallModel,
)

# ── entity <-> row mapping ─────────────────────────────────────────────


def _execution_to_entity(row: ExecutionModel) -> Execution:
    return Execution(
        id=row.id,
        project_id=row.project_id,
        graph_id=row.graph_id,
        trace_id=row.trace_id,
        status=ExecutionStatus(row.status),
        checkpoint=CheckpointRef(
            thread_id=row.thread_id,
            checkpoint_id=row.checkpoint_id,
            parent_checkpoint_id=row.parent_checkpoint_id,
            resumed=row.resumed,
        ),
        error=row.error,
        input=row.input,
        output=row.output,
        started_at=row.started_at,
        ended_at=row.ended_at,
        duration_ms=row.duration_ms,
        tokens=TokenUsage(row.total_input_tokens, row.total_output_tokens),
        total_cost=Decimal(row.total_cost or 0),
        sdk_version=row.sdk_version,
    )


def _node_to_entity(row: NodeExecutionModel) -> NodeExecution:
    return NodeExecution(
        id=row.id,
        execution_id=row.execution_id,
        span_id=row.span_id,
        parent_span_id=row.parent_span_id,
        node_name=row.node_name,
        sequence=row.sequence,
        status=ExecutionStatus(row.status),
        retry_count=row.retry_count,
        error=row.error,
        started_at=row.started_at,
        ended_at=row.ended_at,
        duration_ms=row.duration_ms,
    )


def _llm_to_entity(row: LlmCallModel) -> LlmCall:
    return LlmCall(
        id=row.id,
        execution_id=row.execution_id,
        node_execution_id=row.node_execution_id,
        span_id=row.span_id,
        provider=row.provider,
        model=row.model,
        messages=row.messages,
        params=row.params,
        response=row.response,
        tokens=TokenUsage(row.input_tokens, row.output_tokens),
        cost=Cost(
            input_cost=Decimal(row.input_cost) if row.input_cost is not None else None,
            output_cost=Decimal(row.output_cost) if row.output_cost is not None else None,
            total_cost=Decimal(row.cost) if row.cost is not None else None,
            status=CostStatus(row.cost_status),
        ),
        latency_ms=row.latency_ms,
        started_at=row.started_at,
        error=row.error,
    )


def _tool_to_entity(row: ToolCallModel) -> ToolCall:
    return ToolCall(
        id=row.id,
        execution_id=row.execution_id,
        node_execution_id=row.node_execution_id,
        span_id=row.span_id,
        tool_name=row.tool_name,
        input=row.input,
        output=row.output,
        status=ExecutionStatus(row.status),
        error=row.error,
        duration_ms=row.duration_ms,
        started_at=row.started_at,
    )


def _snapshot_to_entity(row: StateSnapshotModel) -> StateSnapshot:
    return StateSnapshot(
        id=row.id,
        execution_id=row.execution_id,
        node_execution_id=row.node_execution_id,
        kind=row.kind,
        state=row.state,
        diff=None if row.diff is None else row.diff,
        size_bytes=row.size_bytes,
        message_count=row.message_count,
        created_at=row.created_at,
    )


def _log_to_entity(row: LogModel) -> LogRecord:
    return LogRecord(
        id=row.id,
        execution_id=row.execution_id,
        node_execution_id=row.node_execution_id,
        level=row.level,
        message=row.message,
        stack_trace=row.stack_trace,
        attributes=row.attributes,
        timestamp=row.timestamp,
    )


# ── repositories ───────────────────────────────────────────────────────


class PostgresProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_default(self) -> Project:
        row = await self._session.scalar(
            sa.select(ProjectModel).where(ProjectModel.slug == "default")
        )
        if row is None:
            row = ProjectModel(
                id=uuid7(),
                name="default",
                slug="default",
                created_at=datetime.now(tz=None).astimezone(),
            )
            self._session.add(row)
            await self._session.flush()
        return Project(id=row.id, name=row.name, slug=row.slug, created_at=row.created_at)


class PostgresGraphRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(
        self, project_id: UUID, name: str, topology: dict[str, Any] | None, topology_hash: str
    ) -> Graph:
        row = await self._session.scalar(
            sa.select(GraphModel).where(
                GraphModel.project_id == project_id,
                GraphModel.name == name,
                GraphModel.topology_hash == topology_hash,
            )
        )
        if row is None:
            row = GraphModel(
                id=uuid7(),
                project_id=project_id,
                name=name,
                topology=topology,
                topology_hash=topology_hash,
                created_at=datetime.now(tz=None).astimezone(),
            )
            self._session.add(row)
            await self._session.flush()
        elif topology is not None and row.topology is None:
            row.topology = topology
        return Graph(
            id=row.id,
            project_id=row.project_id,
            name=row.name,
            topology=row.topology,
            topology_hash=row.topology_hash,
            created_at=row.created_at,
        )

    async def get(self, graph_id: UUID) -> Graph | None:
        row = await self._session.get(GraphModel, graph_id)
        if row is None:
            return None
        return Graph(
            id=row.id,
            project_id=row.project_id,
            name=row.name,
            topology=row.topology,
            topology_hash=row.topology_hash,
            created_at=row.created_at,
        )

    async def list_by_project(self, project_id: UUID) -> list[Graph]:
        rows = await self._session.scalars(
            sa.select(GraphModel)
            .where(GraphModel.project_id == project_id)
            .order_by(GraphModel.created_at.desc())
        )
        return [
            Graph(
                id=r.id,
                project_id=r.project_id,
                name=r.name,
                topology=r.topology,
                topology_hash=r.topology_hash,
                created_at=r.created_at,
            )
            for r in rows
        ]


class PostgresExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, execution_id: UUID) -> Execution | None:
        row = await self._session.get(ExecutionModel, execution_id)
        return None if row is None else _execution_to_entity(row)

    async def list_durations(self, project_id: UUID, since: datetime | None = None) -> list[int]:
        query = sa.select(ExecutionModel.duration_ms).where(
            ExecutionModel.project_id == project_id,
            ExecutionModel.duration_ms.is_not(None),
        )
        if since is not None:
            query = query.where(ExecutionModel.started_at >= since)
        rows = await self._session.scalars(query)
        return [int(d) for d in rows if d is not None]

    async def status_counts(
        self, project_id: UUID, since: datetime | None = None
    ) -> dict[str, int]:
        query = sa.select(ExecutionModel.status, sa.func.count()).where(
            ExecutionModel.project_id == project_id
        )
        if since is not None:
            query = query.where(ExecutionModel.started_at >= since)
        rows = await self._session.execute(query.group_by(ExecutionModel.status))
        return {status: int(count) for status, count in rows.all()}

    async def get_by_trace_id(self, trace_id: str) -> Execution | None:
        row = await self._session.scalar(
            sa.select(ExecutionModel).where(ExecutionModel.trace_id == trace_id)
        )
        return None if row is None else _execution_to_entity(row)

    async def upsert(self, execution: Execution, *, enrich_only: bool = False) -> Execution:
        row = await self._session.scalar(
            sa.select(ExecutionModel).where(ExecutionModel.trace_id == execution.trace_id)
        )
        if row is None:
            row = ExecutionModel(
                id=execution.id,
                project_id=execution.project_id,
                trace_id=execution.trace_id,
                status=execution.status.value,
            )
            self._session.add(row)
            enrich_only = False  # populate everything we have on first sight
        if not enrich_only:
            # Merge non-empty fields; redelivered spans can never blank a value.
            if execution.graph_id is not None:
                row.graph_id = execution.graph_id
            cp = execution.checkpoint
            row.thread_id = cp.thread_id or row.thread_id
            row.checkpoint_id = cp.checkpoint_id or row.checkpoint_id
            row.parent_checkpoint_id = cp.parent_checkpoint_id or row.parent_checkpoint_id
            row.resumed = cp.resumed or row.resumed
            row.status = execution.status.value
            row.error = execution.error if execution.error is not None else row.error
            row.input = execution.input if execution.input is not None else row.input
            row.output = execution.output if execution.output is not None else row.output
            row.started_at = execution.started_at or row.started_at
            row.ended_at = execution.ended_at or row.ended_at
            row.duration_ms = (
                execution.duration_ms if execution.duration_ms is not None else row.duration_ms
            )
            row.sdk_version = execution.sdk_version or row.sdk_version
        await self._session.flush()
        return _execution_to_entity(row)

    async def update_rollups(
        self, execution_id: UUID, tokens: TokenUsage, total_cost: Decimal
    ) -> None:
        await self._session.execute(
            sa.update(ExecutionModel)
            .where(ExecutionModel.id == execution_id)
            .values(
                total_input_tokens=tokens.input_tokens,
                total_output_tokens=tokens.output_tokens,
                total_cost=total_cost,
            )
        )

    async def list_page(
        self,
        project_id: UUID,
        *,
        status: str | None = None,
        graph_id: UUID | None = None,
        thread_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Execution], int]:
        query = sa.select(ExecutionModel).where(ExecutionModel.project_id == project_id)
        if status:
            query = query.where(ExecutionModel.status == status)
        if graph_id:
            query = query.where(ExecutionModel.graph_id == graph_id)
        if thread_id:
            query = query.where(ExecutionModel.thread_id == thread_id)
        if since:
            query = query.where(ExecutionModel.started_at >= since)
        if until:
            query = query.where(ExecutionModel.started_at <= until)

        total = await self._session.scalar(sa.select(sa.func.count()).select_from(query.subquery()))
        rows = await self._session.scalars(
            query.order_by(ExecutionModel.started_at.desc().nulls_last())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [_execution_to_entity(r) for r in rows], int(total or 0)


class PostgresNodeExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, node: NodeExecution) -> NodeExecution:
        row = await self._session.scalar(
            sa.select(NodeExecutionModel).where(NodeExecutionModel.span_id == node.span_id)
        )
        if row is None:
            row = NodeExecutionModel(
                id=node.id, execution_id=node.execution_id, span_id=node.span_id
            )
            self._session.add(row)
        row.parent_span_id = node.parent_span_id or row.parent_span_id
        row.node_name = node.node_name
        row.sequence = node.sequence
        row.status = node.status.value
        row.retry_count = node.retry_count
        row.error = node.error if node.error is not None else row.error
        row.started_at = node.started_at or row.started_at
        row.ended_at = node.ended_at or row.ended_at
        row.duration_ms = node.duration_ms if node.duration_ms is not None else row.duration_ms
        await self._session.flush()
        return _node_to_entity(row)

    async def get(self, node_execution_id: UUID) -> NodeExecution | None:
        row = await self._session.get(NodeExecutionModel, node_execution_id)
        return None if row is None else _node_to_entity(row)

    async def get_by_span_id(self, span_id: str) -> NodeExecution | None:
        row = await self._session.scalar(
            sa.select(NodeExecutionModel).where(NodeExecutionModel.span_id == span_id)
        )
        return None if row is None else _node_to_entity(row)

    async def list_by_execution(self, execution_id: UUID) -> list[NodeExecution]:
        rows = await self._session.scalars(
            sa.select(NodeExecutionModel)
            .where(NodeExecutionModel.execution_id == execution_id)
            .order_by(NodeExecutionModel.sequence)
        )
        return [_node_to_entity(r) for r in rows]


class PostgresLlmCallRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, call: LlmCall) -> LlmCall:
        row = await self._session.scalar(
            sa.select(LlmCallModel).where(LlmCallModel.span_id == call.span_id)
        )
        if row is None:
            row = LlmCallModel(id=call.id, execution_id=call.execution_id, span_id=call.span_id)
            self._session.add(row)
        row.node_execution_id = call.node_execution_id or row.node_execution_id
        row.provider = call.provider or row.provider
        row.model = call.model or row.model
        row.messages = call.messages if call.messages is not None else row.messages
        row.params = call.params if call.params is not None else row.params
        row.response = call.response if call.response is not None else row.response
        row.input_tokens = call.tokens.input_tokens
        row.output_tokens = call.tokens.output_tokens
        row.total_tokens = call.tokens.total_tokens
        row.input_cost = call.cost.input_cost
        row.output_cost = call.cost.output_cost
        row.cost = call.cost.total_cost
        row.cost_status = call.cost.status.value
        row.latency_ms = call.latency_ms if call.latency_ms is not None else row.latency_ms
        row.started_at = call.started_at or row.started_at
        row.error = call.error if call.error is not None else row.error
        await self._session.flush()
        return _llm_to_entity(row)

    async def list_by_execution(self, execution_id: UUID) -> list[LlmCall]:
        rows = await self._session.scalars(
            sa.select(LlmCallModel)
            .where(LlmCallModel.execution_id == execution_id)
            .order_by(LlmCallModel.started_at)
        )
        return [_llm_to_entity(r) for r in rows]

    async def list_by_node(self, node_execution_id: UUID) -> list[LlmCall]:
        rows = await self._session.scalars(
            sa.select(LlmCallModel)
            .where(LlmCallModel.node_execution_id == node_execution_id)
            .order_by(LlmCallModel.started_at)
        )
        return [_llm_to_entity(r) for r in rows]

    async def sum_usage(self, execution_id: UUID) -> tuple[TokenUsage, Decimal]:
        result = (
            await self._session.execute(
                sa.select(
                    sa.func.coalesce(sa.func.sum(LlmCallModel.input_tokens), 0),
                    sa.func.coalesce(sa.func.sum(LlmCallModel.output_tokens), 0),
                    sa.func.coalesce(sa.func.sum(LlmCallModel.cost), 0),
                ).where(LlmCallModel.execution_id == execution_id)
            )
        ).one()
        return TokenUsage(int(result[0]), int(result[1])), Decimal(str(result[2]))

    async def cost_by_model(self, project_id: UUID) -> list[dict[str, Any]]:
        unknown = sa.case((LlmCallModel.cost_status == "unknown", 1), else_=0)
        rows = await self._session.execute(
            sa.select(
                LlmCallModel.provider,
                LlmCallModel.model,
                sa.func.coalesce(sa.func.sum(LlmCallModel.input_tokens), 0),
                sa.func.coalesce(sa.func.sum(LlmCallModel.output_tokens), 0),
                sa.func.coalesce(sa.func.sum(LlmCallModel.cost), 0),
                sa.func.count(),
                sa.func.coalesce(sa.func.sum(unknown), 0),
            )
            .join(ExecutionModel, ExecutionModel.id == LlmCallModel.execution_id)
            .where(ExecutionModel.project_id == project_id)
            .group_by(LlmCallModel.provider, LlmCallModel.model)
            .order_by(sa.func.coalesce(sa.func.sum(LlmCallModel.cost), 0).desc())
        )
        return [
            {
                "provider": provider,
                "model": model,
                "input_tokens": int(inp),
                "output_tokens": int(out),
                "total_cost": float(cost),
                "calls": int(calls),
                "unknown_calls": int(unknown_calls),
            }
            for provider, model, inp, out, cost, calls, unknown_calls in rows.all()
        ]

    async def cost_by_day(self, project_id: UUID) -> list[dict[str, Any]]:
        day = sa.func.date(LlmCallModel.started_at)
        rows = await self._session.execute(
            sa.select(day, sa.func.coalesce(sa.func.sum(LlmCallModel.cost), 0))
            .join(ExecutionModel, ExecutionModel.id == LlmCallModel.execution_id)
            .where(ExecutionModel.project_id == project_id, LlmCallModel.started_at.is_not(None))
            .group_by(day)
            .order_by(day)
        )
        return [{"day": str(d), "total_cost": float(cost)} for d, cost in rows.all()]


class PostgresToolCallRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, call: ToolCall) -> ToolCall:
        row = await self._session.scalar(
            sa.select(ToolCallModel).where(ToolCallModel.span_id == call.span_id)
        )
        if row is None:
            row = ToolCallModel(
                id=call.id,
                execution_id=call.execution_id,
                span_id=call.span_id,
                tool_name=call.tool_name,
            )
            self._session.add(row)
        row.node_execution_id = call.node_execution_id or row.node_execution_id
        row.tool_name = call.tool_name
        row.input = call.input if call.input is not None else row.input
        row.output = call.output if call.output is not None else row.output
        row.status = call.status.value
        row.error = call.error if call.error is not None else row.error
        row.duration_ms = call.duration_ms if call.duration_ms is not None else row.duration_ms
        row.started_at = call.started_at or row.started_at
        await self._session.flush()
        return _tool_to_entity(row)

    async def list_by_execution(self, execution_id: UUID) -> list[ToolCall]:
        rows = await self._session.scalars(
            sa.select(ToolCallModel)
            .where(ToolCallModel.execution_id == execution_id)
            .order_by(ToolCallModel.started_at)
        )
        return [_tool_to_entity(r) for r in rows]

    async def list_by_node(self, node_execution_id: UUID) -> list[ToolCall]:
        rows = await self._session.scalars(
            sa.select(ToolCallModel)
            .where(ToolCallModel.node_execution_id == node_execution_id)
            .order_by(ToolCallModel.started_at)
        )
        return [_tool_to_entity(r) for r in rows]


class PostgresStateSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, snapshot: StateSnapshot) -> StateSnapshot:
        # Snapshot ids are deterministic (uuid5 of span_id + kind), so
        # redelivery hits the same PK and updates in place.
        row = await self._session.get(StateSnapshotModel, snapshot.id)
        if row is None:
            row = StateSnapshotModel(
                id=snapshot.id, execution_id=snapshot.execution_id, kind=snapshot.kind
            )
            self._session.add(row)
        row.node_execution_id = snapshot.node_execution_id or row.node_execution_id
        row.state = snapshot.state if snapshot.state is not None else row.state
        row.diff = snapshot.diff if snapshot.diff is not None else row.diff
        row.size_bytes = snapshot.size_bytes
        row.message_count = snapshot.message_count
        row.created_at = snapshot.created_at or row.created_at
        await self._session.flush()
        return _snapshot_to_entity(row)

    async def list_by_execution(self, execution_id: UUID) -> list[StateSnapshot]:
        rows = await self._session.scalars(
            sa.select(StateSnapshotModel)
            .where(StateSnapshotModel.execution_id == execution_id)
            .order_by(StateSnapshotModel.created_at)
        )
        return [_snapshot_to_entity(r) for r in rows]

    async def list_by_node(self, node_execution_id: UUID) -> list[StateSnapshot]:
        rows = await self._session.scalars(
            sa.select(StateSnapshotModel)
            .where(StateSnapshotModel.node_execution_id == node_execution_id)
            .order_by(StateSnapshotModel.created_at)
        )
        return [_snapshot_to_entity(r) for r in rows]


class PostgresLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, record: LogRecord) -> LogRecord:
        # Log ids are deterministic (uuid5 of span_id + event index).
        row = await self._session.get(LogModel, record.id)
        if row is None:
            row = LogModel(
                id=record.id,
                execution_id=record.execution_id,
                level=record.level,
                message=record.message,
            )
            self._session.add(row)
        row.node_execution_id = record.node_execution_id or row.node_execution_id
        row.level = record.level
        row.message = record.message
        row.stack_trace = record.stack_trace or row.stack_trace
        row.attributes = record.attributes if record.attributes is not None else row.attributes
        row.timestamp = record.timestamp or row.timestamp
        await self._session.flush()
        return _log_to_entity(row)

    async def list_by_execution(self, execution_id: UUID) -> list[LogRecord]:
        rows = await self._session.scalars(
            sa.select(LogModel)
            .where(LogModel.execution_id == execution_id)
            .order_by(LogModel.timestamp)
        )
        return [_log_to_entity(r) for r in rows]

    async def list_by_node(self, node_execution_id: UUID) -> list[LogRecord]:
        rows = await self._session.scalars(
            sa.select(LogModel)
            .where(LogModel.node_execution_id == node_execution_id)
            .order_by(LogModel.timestamp)
        )
        return [_log_to_entity(r) for r in rows]


# Pricing is served from the JSON catalog (infrastructure/pricing/), not the DB
# (ADR-0002). See CatalogPricingRepository.
