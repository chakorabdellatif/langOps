"""Graph, state-evolution, cost, and metrics query use cases."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from langops_api.application.dto import (
    ExecutionComparison,
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
from langops_api.domain.services import StateDiffer
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
    """Fetch two executions and diff their final states (reuses StateDiffer)."""

    def __init__(self, detail: GetExecutionDetailService, state_differ: StateDiffer) -> None:
        self._detail = detail
        self._state_differ = state_differ

    async def compare(self, a_id: UUID, b_id: UUID) -> ExecutionComparison:
        a = await self._detail.get(a_id)
        b = await self._detail.get(b_id)
        diff = None
        if isinstance(a.execution.output, dict) and isinstance(b.execution.output, dict):
            diff = self._state_differ.diff(a.execution.output, b.execution.output).to_dict()
        return ExecutionComparison(a=a, b=b, final_state_diff=diff)


def _percentile(sorted_values: list[int], q: float) -> int | None:
    """Nearest-rank percentile (computed in Python for cross-DB portability)."""
    if not sorted_values:
        return None
    rank = max(0, min(len(sorted_values) - 1, round(q * (len(sorted_values) - 1))))
    return sorted_values[rank]
