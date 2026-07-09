"""Domain entities — plain dataclasses, no ORM, no framework imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from langops_api.domain.value_objects import (
    CheckpointRef,
    Cost,
    ExecutionStatus,
    TokenUsage,
)


@dataclass
class Project:
    id: UUID
    name: str
    slug: str
    created_at: datetime


@dataclass
class Graph:
    id: UUID
    project_id: UUID
    name: str
    topology: dict[str, Any] | None
    topology_hash: str
    created_at: datetime


@dataclass
class Execution:
    """One end-to-end graph run (≙ one OTel trace)."""

    id: UUID
    project_id: UUID
    trace_id: str
    graph_id: UUID | None = None
    status: ExecutionStatus = ExecutionStatus.RUNNING
    checkpoint: CheckpointRef = field(default_factory=CheckpointRef)
    error: dict[str, Any] | None = None
    input: Any | None = None
    output: Any | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int | None = None
    tokens: TokenUsage = field(default_factory=TokenUsage)
    total_cost: Decimal = Decimal(0)
    sdk_version: str | None = None
    # v0.2 replay lineage: the original execution this run replayed + overrides.
    replay_of_execution_id: UUID | None = None
    replay_overrides: dict[str, Any] | None = None


@dataclass
class NodeExecution:
    """One node run within an execution (≙ one OTel span)."""

    id: UUID
    execution_id: UUID
    span_id: str
    node_name: str
    parent_span_id: str | None = None
    sequence: int = 0
    status: ExecutionStatus = ExecutionStatus.SUCCEEDED
    retry_count: int = 0
    error: dict[str, Any] | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int | None = None
    # v0.2: category (llm|tool|utility|router|conditional|checkpoint|subgraph)
    # and per-node rollups recomputed from child LLM calls during ingestion.
    # ``category`` is None until inferred; the API renders "utility" as fallback.
    category: str | None = None
    tokens: TokenUsage = field(default_factory=TokenUsage)
    cost: Cost = field(default_factory=Cost.unknown)


@dataclass
class LlmCall:
    id: UUID
    execution_id: UUID
    span_id: str
    node_execution_id: UUID | None = None
    provider: str | None = None
    model: str | None = None
    messages: Any | None = None
    params: dict[str, Any] | None = None
    response: Any | None = None
    tokens: TokenUsage = field(default_factory=TokenUsage)
    cost: Cost = field(default_factory=Cost.unknown)
    latency_ms: int | None = None
    started_at: datetime | None = None
    error: dict[str, Any] | None = None
    # v0.1 cached replay: response was served from a recording — costs nothing.
    stubbed: bool = False
    # Flattened prompt+response text for full-text search (extracted at ingest).
    text_content: str | None = None


@dataclass
class ToolCall:
    id: UUID
    execution_id: UUID
    span_id: str
    tool_name: str
    node_execution_id: UUID | None = None
    input: Any | None = None
    output: Any | None = None
    status: ExecutionStatus = ExecutionStatus.SUCCEEDED
    error: dict[str, Any] | None = None
    duration_ms: int | None = None
    started_at: datetime | None = None


@dataclass
class StateSnapshot:
    id: UUID
    execution_id: UUID
    kind: str  # "input" | "output"
    node_execution_id: UUID | None = None
    state: Any | None = None
    # {added, modified, removed}; recomputed server-side, stored as JSON.
    diff: dict[str, Any] | None = None
    size_bytes: int = 0
    message_count: int | None = None
    created_at: datetime | None = None


@dataclass
class LogRecord:
    id: UUID
    execution_id: UUID
    level: str
    message: str
    node_execution_id: UUID | None = None
    # v0.2: origin channel — app | sdk | llm | tool | exception.
    source: str = "app"
    logger: str | None = None
    stack_trace: str | None = None
    attributes: dict[str, Any] | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class ModelPricing:
    """A catalog price for one model (USD per 1M tokens)."""

    provider: str
    model: str
    input_price_per_1m: Decimal
    output_price_per_1m: Decimal
