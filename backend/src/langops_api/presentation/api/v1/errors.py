"""Failure-analytics endpoint — group failures by exception type × node."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from langops_api.application.services.reports import GetErrorReportService
from langops_api.composition import get_error_report_service
from langops_api.presentation.schemas import ErrorReportResponse

router = APIRouter(prefix="/errors", tags=["errors"])


@router.get("/summary", response_model=ErrorReportResponse)
async def error_summary(
    since: datetime | None = Query(default=None),
    service: GetErrorReportService = Depends(get_error_report_service),
) -> ErrorReportResponse:
    return ErrorReportResponse.from_dto(await service.summary(since))
