"""Query-side use cases consumed by the REST API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from langops_api.application.dto import (
    ExecutionDetail,
    ExecutionPage,
    NodeDetail,
    TimelineEntry,
)
from langops_api.domain.entities import LlmCall, LogRecord, ToolCall
from langops_api.domain.errors import ExecutionNotFound, NodeExecutionNotFound
from langops_api.domain.repositories import (
    ExecutionRepository,
    GraphRepository,
    LlmCallRepository,
    LogRepository,
    NodeExecutionRepository,
    ProjectRepository,
    StateSnapshotRepository,
    ToolCallRepository,
)

MAX_PAGE_SIZE = 100


class ListExecutionsService:
    def __init__(self, projects: ProjectRepository, executions: ExecutionRepository) -> None:
        self._projects = projects
        self._executions = executions

    async def list(
        self,
        *,
        status: str | None = None,
        graph_id: UUID | None = None,
        thread_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ExecutionPage:
        page = max(1, page)
        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        project = await self._projects.get_or_create_default()
        items, total = await self._executions.list_page(
            project.id,
            status=status,
            graph_id=graph_id,
            thread_id=thread_id,
            since=since,
            until=until,
            page=page,
            page_size=page_size,
        )
        return ExecutionPage(items=items, total=total, page=page, page_size=page_size)


class GetExecutionDetailService:
    def __init__(
        self,
        executions: ExecutionRepository,
        nodes: NodeExecutionRepository,
        graphs: GraphRepository,
        llm_calls: LlmCallRepository,
        tool_calls: ToolCallRepository,
        logs: LogRepository,
    ) -> None:
        self._executions = executions
        self._nodes = nodes
        self._graphs = graphs
        self._llm_calls = llm_calls
        self._tool_calls = tool_calls
        self._logs = logs

    async def get(self, execution_id: UUID) -> ExecutionDetail:
        execution = await self._executions.get(execution_id)
        if execution is None:
            raise ExecutionNotFound(f"Execution {execution_id} not found")
        graph = await self._graphs.get(execution.graph_id) if execution.graph_id else None
        nodes = await self._nodes.list_by_execution(execution_id)
        return ExecutionDetail(
            execution=execution,
            graph_name=graph.name if graph else None,
            nodes=nodes,
        )

    async def timeline(self, execution_id: UUID) -> list[TimelineEntry]:
        if await self._executions.get(execution_id) is None:
            raise ExecutionNotFound(f"Execution {execution_id} not found")

        entries = [
            TimelineEntry(
                kind="node",
                id=str(node.id),
                name=node.node_name,
                status=node.status.value,
                started_at=node.started_at,
                ended_at=node.ended_at,
                duration_ms=node.duration_ms,
            )
            for node in await self._nodes.list_by_execution(execution_id)
        ]
        entries += [
            TimelineEntry(
                kind="llm",
                id=str(call.id),
                name=call.model or "llm",
                status="failed" if call.error else "succeeded",
                started_at=call.started_at,
                ended_at=None,
                duration_ms=call.latency_ms,
            )
            for call in await self._llm_calls.list_by_execution(execution_id)
        ]
        entries += [
            TimelineEntry(
                kind="tool",
                id=str(call.id),
                name=call.tool_name,
                status=call.status.value,
                started_at=call.started_at,
                ended_at=None,
                duration_ms=call.duration_ms,
            )
            for call in await self._tool_calls.list_by_execution(execution_id)
        ]
        entries.sort(key=lambda e: (e.started_at is None, e.started_at))
        return entries

    async def logs(self, execution_id: UUID) -> list[LogRecord]:
        if await self._executions.get(execution_id) is None:
            raise ExecutionNotFound(f"Execution {execution_id} not found")
        return await self._logs.list_by_execution(execution_id)

    async def llm_calls(self, execution_id: UUID) -> list[LlmCall]:
        if await self._executions.get(execution_id) is None:
            raise ExecutionNotFound(f"Execution {execution_id} not found")
        return await self._llm_calls.list_by_execution(execution_id)

    async def tool_calls(self, execution_id: UUID) -> list[ToolCall]:
        if await self._executions.get(execution_id) is None:
            raise ExecutionNotFound(f"Execution {execution_id} not found")
        return await self._tool_calls.list_by_execution(execution_id)


class GetNodeDetailService:
    def __init__(
        self,
        nodes: NodeExecutionRepository,
        llm_calls: LlmCallRepository,
        tool_calls: ToolCallRepository,
        snapshots: StateSnapshotRepository,
        logs: LogRepository,
    ) -> None:
        self._nodes = nodes
        self._llm_calls = llm_calls
        self._tool_calls = tool_calls
        self._snapshots = snapshots
        self._logs = logs

    async def get(self, node_execution_id: UUID) -> NodeDetail:
        node = await self._nodes.get(node_execution_id)
        if node is None:
            raise NodeExecutionNotFound(f"Node execution {node_execution_id} not found")
        return NodeDetail(
            node=node,
            llm_calls=await self._llm_calls.list_by_node(node_execution_id),
            tool_calls=await self._tool_calls.list_by_node(node_execution_id),
            state_snapshots=await self._snapshots.list_by_node(node_execution_id),
            logs=await self._logs.list_by_node(node_execution_id),
        )
