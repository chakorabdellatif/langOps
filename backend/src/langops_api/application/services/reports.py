"""Graph, state-evolution, cost, and metrics query use cases."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from langops_api.application.dto import (
    ExecutionComparison,
    ExecutionDetail,
    MetricsOverview,
    StateEvolution,
    StateStep,
)
from langops_api.application.services.queries import GetExecutionDetailService
from langops_api.domain.entities import Graph
from langops_api.domain.errors import ExecutionNotFound
from langops_api.domain.repositories import (
    ExecutionRepository,
    GraphRepository,
    LlmCallRepository,
    NodeExecutionRepository,
    ProjectRepository,
    StateSnapshotRepository,
)
from langops_api.domain.services import ExecutionComparator, StateDiffer
from langops_api.domain.services.execution_comparator import (
    ComparisonInput,
    LlmStat,
    NodeStat,
)
from langops_api.domain.value_objects import ExecutionStatus


class ListGraphsService:
    def __init__(self, projects: ProjectRepository, graphs: GraphRepository) -> None:
        self._projects = projects
        self._graphs = graphs

    async def list(self) -> list[Graph]:
        project = await self._projects.get_or_create_default()
        return await self._graphs.list_by_project(project.id)

    async def topology(self, graph_id: UUID) -> dict[str, Any] | None:
        graph = await self._graphs.get(graph_id)
        return graph.topology if graph else None


class GetStateEvolutionService:
    """Ordered state snapshots + diffs + context-growth series for one run."""

    def __init__(
        self,
        executions: ExecutionRepository,
        snapshots: StateSnapshotRepository,
        nodes: NodeExecutionRepository,
    ) -> None:
        self._executions = executions
        self._snapshots = snapshots
        self._nodes = nodes

    async def get(self, execution_id: UUID) -> StateEvolution:
        if await self._executions.get(execution_id) is None:
            raise ExecutionNotFound(f"Execution {execution_id} not found")
        node_names = {n.id: n.node_name for n in await self._nodes.list_by_execution(execution_id)}
        steps = [
            StateStep(
                snapshot=snap,
                node_name=node_names.get(snap.node_execution_id)
                if snap.node_execution_id
                else None,
            )
            for snap in await self._snapshots.list_by_execution(execution_id)
        ]
        return StateEvolution(steps=steps)


class GetCostReportService:
    def __init__(self, projects: ProjectRepository, llm_calls: LlmCallRepository) -> None:
        self._projects = projects
        self._llm_calls = llm_calls

    async def summary(self) -> dict[str, Any]:
        project = await self._projects.get_or_create_default()
        by_model = await self._llm_calls.cost_by_model(project.id)
        by_day = await self._llm_calls.cost_by_day(project.id)
        total_cost = sum(row["total_cost"] for row in by_model)
        total_tokens = sum(row["input_tokens"] + row["output_tokens"] for row in by_model)
        return {
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "by_model": by_model,
            "by_day": by_day,
        }


class GetMetricsService:
    def __init__(self, projects: ProjectRepository, executions: ExecutionRepository) -> None:
        self._projects = projects
        self._executions = executions

    async def overview(self, since: datetime | None = None) -> MetricsOverview:
        project = await self._projects.get_or_create_default()
        counts = await self._executions.status_counts(project.id, since)
        durations = sorted(await self._executions.list_durations(project.id, since))

        total = sum(counts.values())
        succeeded = counts.get(ExecutionStatus.SUCCEEDED, 0)
        failed = counts.get(ExecutionStatus.FAILED, 0)
        running = counts.get(ExecutionStatus.RUNNING, 0)
        finished = succeeded + failed
        return MetricsOverview(
            total_executions=total,
            succeeded=succeeded,
            failed=failed,
            running=running,
            failure_rate=(failed / finished) if finished else 0.0,
            avg_latency_ms=round(sum(durations) / len(durations)) if durations else None,
            latency_p50_ms=_percentile(durations, 0.50),
            latency_p95_ms=_percentile(durations, 0.95),
            latency_p99_ms=_percentile(durations, 0.99),
        )


class CompareExecutionsService:
    """Fetch two executions and diff them across state, structure, performance,
    and LLM usage — deterministically (reuses StateDiffer + ExecutionComparator,
    never an LLM)."""

    def __init__(
        self,
        detail: GetExecutionDetailService,
        state_differ: StateDiffer,
        comparator: ExecutionComparator,
        snapshots: StateSnapshotRepository,
    ) -> None:
        self._detail = detail
        self._state_differ = state_differ
        self._comparator = comparator
        self._snapshots = snapshots

    async def compare(self, a_id: UUID, b_id: UUID) -> ExecutionComparison:
        a = await self._detail.get(a_id)
        b = await self._detail.get(b_id)
        diff = None
        if isinstance(a.execution.output, dict) and isinstance(b.execution.output, dict):
            diff = self._state_differ.diff(a.execution.output, b.execution.output).to_dict()
        input_a = await self._build_input(a_id, a)
        input_b = await self._build_input(b_id, b)
        result = self._comparator.compare(input_a, input_b)
        return ExecutionComparison(a=a, b=b, final_state_diff=diff, result=result)

    async def _build_input(self, execution_id: UUID, detail: ExecutionDetail) -> ComparisonInput:
        execution = detail.execution
        node_stats = [
            NodeStat(
                name=view.node.node_name,
                sequence=view.node.sequence,
                retry_count=view.node.retry_count,
                duration_ms=view.node.duration_ms,
                category=view.node.category or "utility",
            )
            for view in detail.nodes
        ]
        llm_stats = [
            LlmStat(
                model=call.model,
                temperature=_temperature(call.params),
                prompt_chars=_json_len(call.messages),
                response_chars=_json_len(call.response),
            )
            for call in await self._detail.llm_calls(execution_id)
        ]
        tool_calls = await self._detail.tool_calls(execution_id)
        snapshots = await self._snapshots.list_by_execution(execution_id)
        context_size = max((s.size_bytes for s in snapshots), default=0)
        return ComparisonInput(
            status=execution.status.value,
            duration_ms=execution.duration_ms,
            total_tokens=execution.tokens.total_tokens,
            total_cost=execution.total_cost if execution.total_cost else None,
            topology_hash=str(execution.graph_id) if execution.graph_id else None,
            context_size_bytes=context_size,
            nodes=node_stats,
            llm_calls=llm_stats,
            tool_call_count=len(tool_calls),
        )


def _temperature(params: dict[str, Any] | None) -> float | None:
    if not isinstance(params, dict):
        return None
    value = params.get("temperature")
    return float(value) if isinstance(value, (int, float)) else None


def _json_len(value: Any) -> int:
    if value is None:
        return 0
    try:
        return len(json.dumps(value, default=str))
    except (TypeError, ValueError):
        return len(str(value))


def _percentile(sorted_values: list[int], q: float) -> int | None:
    """Nearest-rank percentile (computed in Python for cross-DB portability)."""
    if not sorted_values:
        return None
    rank = max(0, min(len(sorted_values) - 1, round(q * (len(sorted_values) - 1))))
    return sorted_values[rank]
