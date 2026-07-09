"""Inter-layer data carriers returned by application services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from langops_api.domain.entities import (
    Execution,
    LlmCall,
    LogRecord,
    NodeExecution,
    StateSnapshot,
    ToolCall,
)
from langops_api.domain.services.execution_comparator import ComparisonResult


@dataclass
class ExecutionPage:
    items: list[Execution]
    total: int
    page: int
    page_size: int


@dataclass
class NodeView:
    """A node plus display derivations for the graph tooltip/inspector.

    ``node`` carries the persisted rollup (category, tokens, cost); the rest are
    derived once per execution from child rows (no per-node fetch on hover).
    """

    node: NodeExecution
    models: list[str]  # distinct models across this node's LLM calls
    tool_names: list[str]  # distinct tools this node invoked
    state_added: list[str]
    state_modified: list[str]
    state_removed: list[str]


@dataclass
class ExecutionDetail:
    execution: Execution
    graph_name: str | None
    nodes: list[NodeView]
    # v0.2: executions that replayed this one (lineage links).
    replays: list[Execution] = field(default_factory=list)


@dataclass
class LogPage:
    items: list[LogRecord]
    total: int
    limit: int
    offset: int


@dataclass
class ThreadSummary:
    """One conversation/session: all executions sharing a thread_id."""

    thread_id: str
    run_count: int
    first_at: datetime | None
    last_at: datetime | None
    total_tokens: int
    total_cost: float
    succeeded: int
    failed: int
    running: int


@dataclass
class ThreadPage:
    items: list[ThreadSummary]
    total: int
    page: int
    page_size: int


@dataclass
class ThreadRun:
    """One execution within a thread, with running cumulative totals."""

    execution: Execution
    cumulative_tokens: int
    cumulative_cost: float


@dataclass
class ThreadDetail:
    thread_id: str
    runs: list[ThreadRun]


@dataclass
class ErrorGroup:
    error_type: str
    node_name: str
    count: int
    first_seen: datetime | None
    last_seen: datetime | None
    sample_execution_id: str


@dataclass
class ErrorReport:
    total: int
    groups: list[ErrorGroup]
    trend: list[dict[str, object]]  # [{day, count}]


@dataclass
class SearchHit:
    kind: str  # execution | graph | node | tool | log | llm
    label: str
    detail: str | None
    execution_id: str | None
    node_execution_id: str | None


@dataclass
class SearchGroup:
    kind: str
    total: int
    hits: list[SearchHit]


@dataclass
class SearchResults:
    query: str
    groups: list[SearchGroup]


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
    avg_latency_ms: int | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    latency_p99_ms: int | None


@dataclass
class ExecutionComparison:
    """Side-by-side of two executions (the 'diff two runs' differentiator)."""

    a: ExecutionDetail
    b: ExecutionDetail
    # StateDiff of the two final outputs (added/modified/removed), or None.
    final_state_diff: dict[str, object] | None
    # Deterministic execution/performance/LLM diff + insights (v0.2). Optional
    # so callers that only want the state diff need not build it.
    result: ComparisonResult | None = None
