"""Cost reporting endpoint."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from langops_api.application.services.reports import GetCostReportService
from langops_api.composition import get_cost_report_service
from langops_api.presentation.schemas import CostSummaryResponse

router = APIRouter(prefix="/costs", tags=["costs"])


@router.get("/summary", response_model=CostSummaryResponse)
async def cost_summary(
    graph_id: UUID | None = Query(default=None),
    service: GetCostReportService = Depends(get_cost_report_service),
) -> CostSummaryResponse:
    return CostSummaryResponse(**await service.summary(graph_id))
