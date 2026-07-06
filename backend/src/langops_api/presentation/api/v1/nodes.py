"""Node inspection endpoint."""

from uuid import UUID

from fastapi import APIRouter, Depends

from langops_api.application.services.queries import GetNodeDetailService
from langops_api.composition import get_node_detail_service
from langops_api.presentation.schemas import NodeDetailResponse

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("/{node_execution_id}", response_model=NodeDetailResponse)
async def get_node(
    node_execution_id: UUID,
    service: GetNodeDetailService = Depends(get_node_detail_service),
) -> NodeDetailResponse:
    return NodeDetailResponse.from_dto(await service.get(node_execution_id))
