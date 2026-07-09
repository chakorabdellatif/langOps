"""IngestTelemetryService — the heart of the backend.

Takes parsed OTLP spans, maps them to domain entities, persists everything
idempotently (spans arrive at-least-once and in any order), recomputes
execution rollups, and publishes execution.updated events.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

from langops_api.application.mappers.otlp_mapper import MappedTrace, map_spans
from langops_api.domain.repositories import (
    ExecutionRepository,
    GraphRepository,
    LlmCallRepository,
    LogRepository,
    NodeExecutionRepository,
    PricingRepository,
    ProjectRepository,
    StateSnapshotRepository,
    ToolCallRepository,
)
from langops_api.domain.services import CostCalculator, StateDiffer
from langops_api.domain.value_objects import Cost
from langops_api.infrastructure.otlp import ParsedSpan

logger = structlog.get_logger("langops_api.ingest")


class EventPublisher(Protocol):
    async def publish(self, event: dict[str, Any]) -> None: ...


class IngestTelemetryService:
    def __init__(
        self,
        projects: ProjectRepository,
        graphs: GraphRepository,
        executions: ExecutionRepository,
        nodes: NodeExecutionRepository,
        llm_calls: LlmCallRepository,
        tool_calls: ToolCallRepository,
        snapshots: StateSnapshotRepository,
        logs: LogRepository,
        pricing: PricingRepository,
        cost_calculator: CostCalculator,
        state_differ: StateDiffer,
        publisher: EventPublisher,
    ) -> None:
        self._projects = projects
        self._graphs = graphs
        self._executions = executions
        self._nodes = nodes
        self._llm_calls = llm_calls
        self._tool_calls = tool_calls
        self._snapshots = snapshots
        self._logs = logs
        self._pricing = pricing
        self._cost_calculator = cost_calculator
        self._state_differ = state_differ
        self._publisher = publisher

    async def ingest(self, spans: list[ParsedSpan]) -> int:
        """Persist a batch of spans; returns the number of traces touched."""
        traces = map_spans(spans)
        project = await self._projects.get_or_create_default()
        for trace in traces:
            await self._ingest_trace(project.id, trace)
        return len(traces)

    async def _ingest_trace(self, project_id: UUID, trace: MappedTrace) -> None:
        try:
            await self._persist_trace(project_id, trace)
        finally:
            clear_contextvars()

    async def _persist_trace(self, project_id: UUID, trace: MappedTrace) -> None:
        execution = trace.execution
        execution.project_id = project_id
        checkpoint = execution.checkpoint
        bind_contextvars(
            trace_id=trace.trace_id,
            thread_id=checkpoint.thread_id,
            checkpoint_id=checkpoint.checkpoint_id,
        )

        if trace.graph is not None:
            graph = await self._graphs.get_or_create(
                project_id, trace.graph.name, trace.graph.topology, trace.graph.topology_hash
            )
            execution.graph_id = graph.id

        # Lazy creation: whichever span arrives first creates the row;
        # the root span enriches it when it lands.
        stored = await self._executions.upsert(execution, enrich_only=not trace.has_root_span)
        execution_id = stored.id
        bind_contextvars(execution_id=str(execution_id))

        # Nodes first so children can link to them; remember span_id -> node id.
        node_ids: dict[str, UUID] = {}
        for node in trace.nodes:
            node.execution_id = execution_id
            persisted = await self._nodes.upsert(node)
            node_ids[node.span_id] = persisted.id

        async def resolve_node(parent_span_id: str | None) -> UUID | None:
            if parent_span_id is None:
                return None
            if parent_span_id in node_ids:
                return node_ids[parent_span_id]
            # Parent node span may have landed in an earlier batch.
            parent = await self._nodes.get_by_span_id(parent_span_id)
            return parent.id if parent else None

        for call, parent_span_id in trace.llm_calls:
            call.execution_id = execution_id
            call.node_execution_id = await resolve_node(parent_span_id)
            if call.stubbed:
                # Served from a recording during cached replay — it cost nothing.
                call.cost = Cost.free()
            elif call.provider and call.model:
                pricing = await self._pricing.get_price(call.provider, call.model, call.started_at)
                call.cost = self._cost_calculator.calculate(call.tokens, pricing)
                if pricing is None:
                    logger.debug("no pricing for %s/%s", call.provider, call.model)
            await self._llm_calls.upsert(call)

        for tool_call, parent_span_id in trace.tool_calls:
            tool_call.execution_id = execution_id
            tool_call.node_execution_id = await resolve_node(parent_span_id)
            await self._tool_calls.upsert(tool_call)

        previous_state: dict[str, Any] | None = None
        for snapshot, node_span_id in sorted(
            trace.snapshots, key=lambda pair: (pair[0].created_at is None, pair[0].created_at)
        ):
            snapshot.execution_id = execution_id
            snapshot.node_execution_id = await resolve_node(node_span_id)
            # Diffs are recomputed server-side so the dashboard never
            # depends on the SDK version (architecture §3.2).
            if isinstance(snapshot.state, dict):
                snapshot.diff = self._state_differ.diff(previous_state, snapshot.state).to_dict()
                previous_state = snapshot.state
            await self._snapshots.upsert(snapshot)

        for record, node_span_id in trace.logs:
            record.execution_id = execution_id
            record.node_execution_id = await resolve_node(node_span_id)
            await self._logs.upsert(record)

        # Per-node rollups + category, recomputed from child rows across the
        # whole execution (not just this batch) so late/out-of-order LLM and
        # tool spans still land on their node. One batched UPDATE, idempotent.
        await self._nodes.recompute_rollups(execution_id)

        # Execution rollups are recomputed from child rows, never incremented —
        # idempotent by construction (architecture §3.6).
        tokens, total_cost = await self._llm_calls.sum_usage(execution_id)
        await self._executions.update_rollups(execution_id, tokens, total_cost)

        await self._publisher.publish(
            {"type": "execution.updated", "execution_id": str(execution_id)}
        )
        logger.info(
            "trace_ingested",
            nodes=len(trace.nodes),
            llm_calls=len(trace.llm_calls),
            tool_calls=len(trace.tool_calls),
        )
