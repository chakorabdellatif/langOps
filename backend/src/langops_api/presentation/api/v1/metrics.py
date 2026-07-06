"""Metrics overview endpoint."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from langops_api.application.services.reports import GetMetricsService
from langops_api.composition import get_metrics_service
from langops_api.presentation.schemas import MetricsOverviewResponse

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/overview", response_model=MetricsOverviewResponse)
async def metrics_overview(
    since: datetime | None = Query(default=None),
    service: GetMetricsService = Depends(get_metrics_service),
) -> MetricsOverviewResponse:
    return MetricsOverviewResponse.from_dto(await service.overview(since))
