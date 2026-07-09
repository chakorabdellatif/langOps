"""Execution query endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from langops_api.application.services.queries import (
    GetExecutionDetailService,
    ListExecutionsService,
)
from langops_api.application.services.reports import (
    CompareExecutionsService,
    GetStateEvolutionService,
)
from langops_api.composition import (
    get_compare_service,
    get_execution_detail_service,
    get_list_executions_service,
    get_state_evolution_service,
)
from langops_api.presentation.schemas import (
    ExecutionComparisonResponse,
    ExecutionDetailResponse,
    ExecutionListResponse,
    LlmCallResponse,
    LogResponse,
    StateEvolutionResponse,
    TimelineEntryResponse,
    ToolCallResponse,
)

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("", response_model=ExecutionListResponse)
async def list_executions(
    status: str | None = Query(default=None),
    graph_id: UUID | None = Query(default=None),
    thread_id: str | None = Query(default=None),
    model: str | None = Query(default=None),
    has_retries: bool | None = Query(default=None),
    error_type: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: ListExecutionsService = Depends(get_list_executions_service),
) -> ExecutionListResponse:
    result = await service.list(
        status=status,
        graph_id=graph_id,
        thread_id=thread_id,
        model=model,
        has_retries=has_retries,
        error_type=error_type,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )
    return ExecutionListResponse.from_dto(result)


# Declared before /{execution_id} so "compare" is not parsed as a UUID.
@router.get("/compare", response_model=ExecutionComparisonResponse)
async def compare_executions(
    a: UUID = Query(...),
    b: UUID = Query(...),
    service: CompareExecutionsService = Depends(get_compare_service),
) -> ExecutionComparisonResponse:
    return ExecutionComparisonResponse.from_dto(await service.compare(a, b))


@router.get("/{execution_id}", response_model=ExecutionDetailResponse)
async def get_execution(
    execution_id: UUID,
    service: GetExecutionDetailService = Depends(get_execution_detail_service),
) -> ExecutionDetailResponse:
    return ExecutionDetailResponse.from_dto(await service.get(execution_id))


@router.get("/{execution_id}/timeline", response_model=list[TimelineEntryResponse])
async def get_execution_timeline(
    execution_id: UUID,
    service: GetExecutionDetailService = Depends(get_execution_detail_service),
) -> list[TimelineEntryResponse]:
    return [TimelineEntryResponse.from_dto(e) for e in await service.timeline(execution_id)]


@router.get("/{execution_id}/logs", response_model=list[LogResponse])
async def get_execution_logs(
    execution_id: UUID,
    service: GetExecutionDetailService = Depends(get_execution_detail_service),
) -> list[LogResponse]:
    return [LogResponse.from_entity(r) for r in await service.logs(execution_id)]


@router.get("/{execution_id}/state", response_model=StateEvolutionResponse)
async def get_execution_state(
    execution_id: UUID,
    service: GetStateEvolutionService = Depends(get_state_evolution_service),
) -> StateEvolutionResponse:
    return StateEvolutionResponse.from_dto(await service.get(execution_id))


@router.get("/{execution_id}/llm-calls", response_model=list[LlmCallResponse])
async def get_execution_llm_calls(
    execution_id: UUID,
    service: GetExecutionDetailService = Depends(get_execution_detail_service),
) -> list[LlmCallResponse]:
    return [LlmCallResponse.from_entity(c) for c in await service.llm_calls(execution_id)]


@router.get("/{execution_id}/tool-calls", response_model=list[ToolCallResponse])
async def get_execution_tool_calls(
    execution_id: UUID,
    service: GetExecutionDetailService = Depends(get_execution_detail_service),
) -> list[ToolCallResponse]:
    return [ToolCallResponse.from_entity(c) for c in await service.tool_calls(execution_id)]
