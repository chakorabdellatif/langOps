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


class ExecutionRepository(Protocol):
    async def get(self, execution_id: UUID) -> Execution | None: ...

    async def get_by_trace_id(self, trace_id: str) -> Execution | None: ...

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
        since: datetime | None = None,
        until: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Execution], int]:
        """Return (items ordered by started_at desc, total count)."""
        ...


class NodeExecutionRepository(Protocol):
    async def upsert(self, node: NodeExecution) -> NodeExecution: ...

    async def get(self, node_execution_id: UUID) -> NodeExecution | None: ...

    async def get_by_span_id(self, span_id: str) -> NodeExecution | None: ...

    async def list_by_execution(self, execution_id: UUID) -> list[NodeExecution]: ...


class LlmCallRepository(Protocol):
    async def upsert(self, call: LlmCall) -> LlmCall: ...

    async def list_by_execution(self, execution_id: UUID) -> list[LlmCall]: ...

    async def list_by_node(self, node_execution_id: UUID) -> list[LlmCall]: ...

    async def sum_usage(self, execution_id: UUID) -> tuple[TokenUsage, Decimal]: ...


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


class PricingRepository(Protocol):
    async def get_price(self, provider: str, model: str) -> ModelPricing | None:
        """Catalog price for a model, or None when unpriced (ADR-0002)."""
        ...
