"""Graph topology endpoints (the DAG for the dashboard's Graph tab)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from langops_api.application.services.reports import ListGraphsService
from langops_api.composition import get_list_graphs_service
from langops_api.domain.errors import NotFoundError
from langops_api.presentation.schemas import GraphResponse

router = APIRouter(prefix="/graphs", tags=["graphs"])


class GraphNotFound(NotFoundError):
    code = "graph_not_found"


@router.get("", response_model=list[GraphResponse])
async def list_graphs(
    service: ListGraphsService = Depends(get_list_graphs_service),
) -> list[GraphResponse]:
    return [GraphResponse.from_entity(g) for g in await service.list()]


@router.get("/{graph_id}/topology")
async def get_graph_topology(
    graph_id: UUID,
    service: ListGraphsService = Depends(get_list_graphs_service),
) -> dict[str, Any]:
    topology = await service.topology(graph_id)
    if topology is None:
        raise GraphNotFound(f"Graph {graph_id} not found or has no topology")
    return topology
