"""Pydantic response models — the wire contract with the dashboard.

Never reused as domain objects or ORM models. Converters from domain
entities live next to the models they serve.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from langops_api.application.dto import (
    ExecutionDetail,
    ExecutionPage,
    NodeDetail,
    TimelineEntry,
)
from langops_api.domain.entities import (
    Execution,
    LlmCall,
    LogRecord,
    NodeExecution,
    StateSnapshot,
    ToolCall,
)


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: str | None = None


class ExecutionSummaryResponse(BaseModel):
    id: UUID
    trace_id: str
    graph_id: UUID | None
    status: str
    thread_id: str | None
    checkpoint_id: str | None
    resumed: bool
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: int | None
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    sdk_version: str | None

    @classmethod
    def from_entity(cls, execution: Execution) -> ExecutionSummaryResponse:
        return cls(
            id=execution.id,
            trace_id=execution.trace_id,
            graph_id=execution.graph_id,
            status=execution.status.value,
            thread_id=execution.checkpoint.thread_id,
            checkpoint_id=execution.checkpoint.checkpoint_id,
            resumed=execution.checkpoint.resumed,
            started_at=execution.started_at,
            ended_at=execution.ended_at,
            duration_ms=execution.duration_ms,
            total_input_tokens=execution.tokens.input_tokens,
            total_output_tokens=execution.tokens.output_tokens,
            total_cost=float(execution.total_cost),
            sdk_version=execution.sdk_version,
        )


class ExecutionListResponse(BaseModel):
    items: list[ExecutionSummaryResponse]
    total: int
    page: int
    page_size: int

    @classmethod
    def from_dto(cls, page: ExecutionPage) -> ExecutionListResponse:
        return cls(
            items=[ExecutionSummaryResponse.from_entity(e) for e in page.items],
            total=page.total,
            page=page.page,
            page_size=page.page_size,
        )


class NodeSummaryResponse(BaseModel):
    id: UUID
    node_name: str
    sequence: int
    status: str
    retry_count: int
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: int | None
    error: dict[str, Any] | None

    @classmethod
    def from_entity(cls, node: NodeExecution) -> NodeSummaryResponse:
        return cls(
            id=node.id,
            node_name=node.node_name,
            sequence=node.sequence,
            status=node.status.value,
            retry_count=node.retry_count,
            started_at=node.started_at,
            ended_at=node.ended_at,
            duration_ms=node.duration_ms,
            error=node.error,
        )


class ExecutionDetailResponse(BaseModel):
    execution: ExecutionSummaryResponse
    graph_name: str | None
    parent_checkpoint_id: str | None
    error: dict[str, Any] | None
    input: Any | None
    output: Any | None
    nodes: list[NodeSummaryResponse]

    @classmethod
    def from_dto(cls, detail: ExecutionDetail) -> ExecutionDetailResponse:
        execution = detail.execution
        return cls(
            execution=ExecutionSummaryResponse.from_entity(execution),
            graph_name=detail.graph_name,
            parent_checkpoint_id=execution.checkpoint.parent_checkpoint_id,
            error=execution.error,
            input=execution.input,
            output=execution.output,
            nodes=[NodeSummaryResponse.from_entity(n) for n in detail.nodes],
        )


class TimelineEntryResponse(BaseModel):
    kind: str
    id: str
    name: str
    status: str | None
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: int | None

    @classmethod
    def from_dto(cls, entry: TimelineEntry) -> TimelineEntryResponse:
        return cls(
            kind=entry.kind,
            id=entry.id,
            name=entry.name,
            status=entry.status,
            started_at=entry.started_at,
            ended_at=entry.ended_at,
            duration_ms=entry.duration_ms,
        )


class LlmCallResponse(BaseModel):
    id: UUID
    node_execution_id: UUID | None
    provider: str | None
    model: str | None
    messages: Any | None
    params: Any | None
    response: Any | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost: float | None
    output_cost: float | None
    total_cost: float | None
    cost_status: str
    latency_ms: int | None
    started_at: datetime | None
    error: dict[str, Any] | None

    @classmethod
    def from_entity(cls, call: LlmCall) -> LlmCallResponse:
        cost = call.cost
        return cls(
            id=call.id,
            node_execution_id=call.node_execution_id,
            provider=call.provider,
            model=call.model,
            messages=call.messages,
            params=call.params,
            response=call.response,
            input_tokens=call.tokens.input_tokens,
            output_tokens=call.tokens.output_tokens,
            total_tokens=call.tokens.total_tokens,
            input_cost=float(cost.input_cost) if cost.input_cost is not None else None,
            output_cost=float(cost.output_cost) if cost.output_cost is not None else None,
            total_cost=float(cost.total_cost) if cost.total_cost is not None else None,
            cost_status=cost.status.value,
            latency_ms=call.latency_ms,
            started_at=call.started_at,
            error=call.error,
        )


class ToolCallResponse(BaseModel):
    id: UUID
    node_execution_id: UUID | None
    tool_name: str
    input: Any | None
    output: Any | None
    status: str
    error: dict[str, Any] | None
    duration_ms: int | None
    started_at: datetime | None

    @classmethod
    def from_entity(cls, call: ToolCall) -> ToolCallResponse:
        return cls(
            id=call.id,
            node_execution_id=call.node_execution_id,
            tool_name=call.tool_name,
            input=call.input,
            output=call.output,
            status=call.status.value,
            error=call.error,
            duration_ms=call.duration_ms,
            started_at=call.started_at,
        )


class StateSnapshotResponse(BaseModel):
    id: UUID
    node_execution_id: UUID | None
    kind: str
    state: Any | None
    diff: dict[str, Any] | None
    size_bytes: int
    message_count: int | None
    created_at: datetime | None

    @classmethod
    def from_entity(cls, snapshot: StateSnapshot) -> StateSnapshotResponse:
        return cls(
            id=snapshot.id,
            node_execution_id=snapshot.node_execution_id,
            kind=snapshot.kind,
            state=snapshot.state,
            diff=snapshot.diff.to_dict() if snapshot.diff is not None else None,
            size_bytes=snapshot.size_bytes,
            message_count=snapshot.message_count,
            created_at=snapshot.created_at,
        )


class LogResponse(BaseModel):
    id: UUID
    node_execution_id: UUID | None
    level: str
    message: str
    stack_trace: str | None
    attributes: dict[str, Any] | None
    timestamp: datetime | None

    @classmethod
    def from_entity(cls, record: LogRecord) -> LogResponse:
        return cls(
            id=record.id,
            node_execution_id=record.node_execution_id,
            level=record.level,
            message=record.message,
            stack_trace=record.stack_trace,
            attributes=record.attributes,
            timestamp=record.timestamp,
        )


class NodeDetailResponse(BaseModel):
    node: NodeSummaryResponse
    llm_calls: list[LlmCallResponse]
    tool_calls: list[ToolCallResponse]
    state_snapshots: list[StateSnapshotResponse]
    logs: list[LogResponse]

    @classmethod
    def from_dto(cls, detail: NodeDetail) -> NodeDetailResponse:
        return cls(
            node=NodeSummaryResponse.from_entity(detail.node),
            llm_calls=[LlmCallResponse.from_entity(c) for c in detail.llm_calls],
            tool_calls=[ToolCallResponse.from_entity(c) for c in detail.tool_calls],
            state_snapshots=[StateSnapshotResponse.from_entity(s) for s in detail.state_snapshots],
            logs=[LogResponse.from_entity(r) for r in detail.logs],
        )
