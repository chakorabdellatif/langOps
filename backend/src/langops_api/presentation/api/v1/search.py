"""Global search endpoint (v0.1) — one query, typed result groups."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from langops_api.application.services.queries import SearchService
from langops_api.composition import get_search_service
from langops_api.presentation.schemas import SearchResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="search text"),
    per_group: int = Query(default=8, ge=1, le=25),
    service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    return SearchResponse.from_dto(await service.search(q, per_group=per_group))
