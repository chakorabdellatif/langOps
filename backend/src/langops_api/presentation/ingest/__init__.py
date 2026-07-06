"""OTLP/HTTP receiver — POST /v1/traces (OTLP-spec path, not under /api).

Accepts application/x-protobuf (what the Collector sends) and
application/json. Kept in its own module so it can be extracted into a
separate deployable later (architecture §3.4).
"""

from fastapi import APIRouter, Depends, Request, Response

from langops_api.application.services.ingest import IngestTelemetryService
from langops_api.composition import Container, get_container, get_ingest_service, get_trace_parser
from langops_api.domain.errors import RequestTooLarge

router = APIRouter(tags=["ingest"])


@router.post("/v1/traces")
async def ingest_traces(
    request: Request,
    service: IngestTelemetryService = Depends(get_ingest_service),
    parse=Depends(get_trace_parser),
    container: Container = Depends(get_container),
) -> Response:
    body = await request.body()
    limit = container.settings.ingest_max_payload_bytes
    if len(body) > limit:
        raise RequestTooLarge(f"OTLP payload exceeds {limit} bytes", f"received {len(body)} bytes")
    content_type = request.headers.get("content-type", "application/x-protobuf")
    spans = parse(body, content_type)
    await service.ingest(spans)
    # OTLP/HTTP success response: empty ExportTraceServiceResponse.
    if "json" in content_type:
        return Response(content="{}", media_type="application/json")
    return Response(content=b"", media_type="application/x-protobuf")
