"""Inter-layer data carriers returned by application services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from langops_api.domain.entities import (
    Execution,
    LlmCall,
    LogRecord,
    NodeExecution,
    StateSnapshot,
    ToolCall,
)


@dataclass
class ExecutionPage:
    items: list[Execution]
    total: int
    page: int
    page_size: int


@dataclass
class ExecutionDetail:
    execution: Execution
    graph_name: str | None
    nodes: list[NodeExecution]


@dataclass
class TimelineEntry:
    kind: str  # node | llm | tool
    id: str
    name: str
    status: str | None
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: int | None


@dataclass
class NodeDetail:
    node: NodeExecution
    llm_calls: list[LlmCall]
    tool_calls: list[ToolCall]
    state_snapshots: list[StateSnapshot]
    logs: list[LogRecord]


@dataclass
class StateStep:
    """One state snapshot in an execution's evolution, with its node name."""

    snapshot: StateSnapshot
    node_name: str | None


@dataclass
class StateEvolution:
    steps: list[StateStep]


@dataclass
class MetricsOverview:
    total_executions: int
    succeeded: int
    failed: int
    running: int
    failure_rate: float
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    latency_p99_ms: int | None
