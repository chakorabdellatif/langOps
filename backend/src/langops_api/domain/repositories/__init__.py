"""Repository interfaces (typing.Protocol, async).

Infrastructure implements these against Postgres; tests may use in-memory
fakes. Methods are intent-revealing, not generic CRUD.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from langops_api.domain.entities import (
    Execution,
    Graph,
    LlmCall,
    LogRecord,
    ModelPricing,
    NodeExecution,
    Project,
    StateSnapshot,
    ToolCall,
)
from langops_api.domain.value_objects import TokenUsage


class ProjectRepository(Protocol):
    async def get_or_create_default(self) -> Project: ...


class GraphRepository(Protocol):
    async def get_or_create(
        self, project_id: UUID, name: str, topology: dict[str, Any] | None, topology_hash: str
    ) -> Graph: ...

    async def get(self, graph_id: UUID) -> Graph | None: ...

    async def list_by_project(self, project_id: UUID) -> list[Graph]: ...


class ExecutionRepository(Protocol):
    async def get(self, execution_id: UUID) -> Execution | None: ...

    async def get_by_trace_id(self, trace_id: str) -> Execution | None: ...

    async def list_replays_of(self, execution_id: UUID) -> list[Execution]:
        """Executions that replayed ``execution_id`` (newest first)."""
        ...

    async def list_threads(
        self, project_id: UUID, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        """Executions grouped by thread_id (most-recent first) + total thread count."""
        ...

    async def list_by_thread(self, project_id: UUID, thread_id: str) -> list[Execution]:
        """All executions of a thread, oldest first (conversation order)."""
        ...

    async def upsert(self, execution: Execution, *, enrich_only: bool = False) -> Execution:
        """Insert by trace_id or merge non-empty fields into the existing row.

        With enrich_only=True (lazy creation from a child span) an existing
        row is left untouched.
        """
        ...

    async def update_rollups(
        self,
        execution_id: UUID,
        tokens: TokenUsage,
        total_cost: Decimal,
    ) -> None: ...

    async def list_page(
        self,
        project_id: UUID,
        *,
        status: str | None = None,
        graph_id: UUID | None = None,
        thread_id: str | None = None,
        model: str | None = None,
        has_retries: bool | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Execution], int]:
        """Return (items ordered by started_at desc, total count)."""
        ...

    async def list_durations(self, project_id: UUID, since: datetime | None = None) -> list[int]:
        """Completed-execution durations (ms), for latency percentiles."""
        ...

    async def status_counts(
        self, project_id: UUID, since: datetime | None = None
    ) -> dict[str, int]:
        """Execution count grouped by status."""
        ...

    async def delete_older_than(self, cutoff: datetime) -> int:
        """Delete executions started before ``cutoff``; returns the count.

        Child rows cascade. This is the retention job's single operation.
        """
        ...


class NodeExecutionRepository(Protocol):
    async def upsert(self, node: NodeExecution) -> NodeExecution: ...

    async def recompute_rollups(self, execution_id: UUID) -> None:
        """Recompute every node's category + token/cost rollup for an execution
        from its child rows, in a single batched statement (recomputed, never
        incremented — idempotent under OTLP redelivery)."""
        ...

    async def get(self, node_execution_id: UUID) -> NodeExecution | None: ...

    async def get_by_span_id(self, span_id: str) -> NodeExecution | None: ...

    async def list_by_execution(self, execution_id: UUID) -> list[NodeExecution]: ...


class LlmCallRepository(Protocol):
    async def upsert(self, call: LlmCall) -> LlmCall: ...

    async def list_by_execution(self, execution_id: UUID) -> list[LlmCall]: ...

    async def list_by_node(self, node_execution_id: UUID) -> list[LlmCall]: ...

    async def sum_usage(self, execution_id: UUID) -> tuple[TokenUsage, Decimal]: ...

    async def cost_by_model(self, project_id: UUID) -> list[dict[str, Any]]:
        """Per-model rollup: provider, model, tokens, cost, calls, unknown count."""
        ...

    async def cost_by_day(self, project_id: UUID) -> list[dict[str, Any]]:
        """Per-day total cost (UTC), oldest first."""
        ...

    async def cost_by_node(
        self, project_id: UUID, graph_id: UUID | None = None
    ) -> list[dict[str, Any]]:
        """Per-node-name rollup: tokens, cost, calls, unknown count."""
        ...


class ToolCallRepository(Protocol):
    async def upsert(self, call: ToolCall) -> ToolCall: ...

    async def list_by_execution(self, execution_id: UUID) -> list[ToolCall]: ...

    async def list_by_node(self, node_execution_id: UUID) -> list[ToolCall]: ...


class StateSnapshotRepository(Protocol):
    async def upsert(self, snapshot: StateSnapshot) -> StateSnapshot: ...

    async def list_by_execution(self, execution_id: UUID) -> list[StateSnapshot]: ...

    async def list_by_node(self, node_execution_id: UUID) -> list[StateSnapshot]: ...


class LogRepository(Protocol):
    async def upsert(self, record: LogRecord) -> LogRecord: ...

    async def list_by_execution(self, execution_id: UUID) -> list[LogRecord]: ...

    async def list_by_node(self, node_execution_id: UUID) -> list[LogRecord]: ...

    async def search(
        self,
        *,
        execution_id: UUID | None = None,
        node_execution_id: UUID | None = None,
        level: str | None = None,
        source: str | None = None,
        q: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[LogRecord], int]:
        """Filtered log search (newest first) + total count."""
        ...


class SearchRepository(Protocol):
    async def search(
        self, project_id: UUID, q: str, *, per_group: int = 8
    ) -> dict[str, tuple[int, list[dict[str, Any]]]]:
        """Full-text search across entities; returns kind → (total, hits)."""
        ...


class PricingRepository(Protocol):
    async def get_price(
        self, provider: str, model: str, at: datetime | None = None
    ) -> ModelPricing | None:
        """Catalog price effective at ``at`` (default now), or None when unpriced.

        Implementations may prefix-match dated model variants (ADR-0002).
        """
        ...
