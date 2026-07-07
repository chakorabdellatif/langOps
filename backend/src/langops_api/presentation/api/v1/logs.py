"""Log search endpoint (v0.2) — filter/search across app/sdk/llm/tool logs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from langops_api.application.services.queries import SearchLogsService
from langops_api.composition import get_search_logs_service
from langops_api.presentation.schemas import LogPageResponse

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=LogPageResponse)
async def search_logs(
    execution_id: UUID | None = Query(default=None),
    node_execution_id: UUID | None = Query(default=None),
    level: str | None = Query(default=None),
    source: str | None = Query(default=None),
    q: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: SearchLogsService = Depends(get_search_logs_service),
) -> LogPageResponse:
    page = await service.search(
        execution_id=execution_id,
        node_execution_id=node_execution_id,
        level=level,
        source=source,
        q=q,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return LogPageResponse.from_dto(page)
