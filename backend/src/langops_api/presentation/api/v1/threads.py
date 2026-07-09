"""Thread (conversation/session) endpoints — group executions by thread_id."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from langops_api.application.services.reports import (
    GetThreadDetailService,
    ListThreadsService,
)
from langops_api.composition import get_list_threads_service, get_thread_detail_service
from langops_api.presentation.schemas import ThreadDetailResponse, ThreadListResponse

router = APIRouter(prefix="/threads", tags=["threads"])


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: ListThreadsService = Depends(get_list_threads_service),
) -> ThreadListResponse:
    return ThreadListResponse.from_dto(await service.list(page=page, page_size=page_size))


@router.get("/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(
    thread_id: str,
    service: GetThreadDetailService = Depends(get_thread_detail_service),
) -> ThreadDetailResponse:
    return ThreadDetailResponse.from_dto(await service.get(thread_id))
