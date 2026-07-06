"""Ingest a real OTLP/protobuf ExportTraceServiceRequest.

The Collector re-exports SDK spans to the API as OTLP/HTTP **protobuf** (the
default), so this exercises the wire format that actually reaches production —
Phase 2 only covered the JSON path. Built from opentelemetry-proto directly so
no SDK/encoder dependency is needed.
"""

import httpx
import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span, Status

TRACE_ID = bytes.fromhex("11112222333344445555666677778888")
ROOT_SPAN = bytes.fromhex("aaaaaaaaaaaaaaaa")
NODE_SPAN = bytes.fromhex("bbbbbbbbbbbbbbbb")
LLM_SPAN = bytes.fromhex("cccccccccccccccc")


def _kv(key: str, value: object) -> KeyValue:
    if isinstance(value, bool):
        return KeyValue(key=key, value=AnyValue(bool_value=value))
    if isinstance(value, int):
        return KeyValue(key=key, value=AnyValue(int_value=value))
    return KeyValue(key=key, value=AnyValue(string_value=str(value)))


def _payload_event(name: str, obj: str, ts: int) -> Span.Event:
    return Span.Event(name=name, time_unix_nano=ts, attributes=[_kv("langops.payload", obj)])


def _request() -> bytes:
    root = Span(
        trace_id=TRACE_ID,
        span_id=ROOT_SPAN,
        name="graph",
        start_time_unix_nano=1_700_000_000_000_000_000,
        end_time_unix_nano=1_700_000_002_000_000_000,
        attributes=[
            _kv("langops.kind", "execution"),
            _kv("langops.execution.id", "exec-pb"),
            _kv("langops.graph.name", "demo"),
            _kv("langops.graph.topology_hash", "hash-pb"),
            _kv("langops.thread.id", "thread-pb"),
        ],
        events=[
            _payload_event("langops.execution.input", '{"q": "hi"}', 1_700_000_000_000_000_000),
            _payload_event("langops.execution.output", '{"a": "yo"}', 1_700_000_002_000_000_000),
        ],
        status=Status(code=Status.STATUS_CODE_OK),
    )
    node = Span(
        trace_id=TRACE_ID,
        span_id=NODE_SPAN,
        parent_span_id=ROOT_SPAN,
        name="agent",
        start_time_unix_nano=1_700_000_000_500_000_000,
        end_time_unix_nano=1_700_000_001_500_000_000,
        attributes=[
            _kv("langops.kind", "node"),
            _kv("langops.node.name", "agent"),
            _kv("langops.node.sequence", 1),
        ],
        status=Status(code=Status.STATUS_CODE_OK),
    )
    llm = Span(
        trace_id=TRACE_ID,
        span_id=LLM_SPAN,
        parent_span_id=NODE_SPAN,
        name="chat",
        start_time_unix_nano=1_700_000_000_600_000_000,
        end_time_unix_nano=1_700_000_001_000_000_000,
        attributes=[
            _kv("langops.kind", "llm"),
            _kv("gen_ai.system", "anthropic"),
            _kv("gen_ai.request.model", "claude-opus-4-8"),
            _kv("gen_ai.usage.input_tokens", 1_000_000),
            _kv("gen_ai.usage.output_tokens", 500_000),
        ],
        status=Status(code=Status.STATUS_CODE_OK),
    )
    request = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=Resource(attributes=[_kv("langops.sdk.version", "0.1.0")]),
                scope_spans=[ScopeSpans(spans=[root, node, llm])],
            )
        ]
    )
    return request.SerializeToString()


async def _post(client: httpx.AsyncClient, body: bytes) -> httpx.Response:
    return await client.post(
        "/v1/traces", content=body, headers={"content-type": "application/x-protobuf"}
    )


@pytest.mark.asyncio
async def test_protobuf_ingest_then_query(client: httpx.AsyncClient) -> None:
    body = _request()
    assert (await _post(client, body)).status_code == 200

    listing = (await client.get("/api/v1/executions")).json()
    assert listing["total"] == 1
    execution = listing["items"][0]
    assert execution["status"] == "succeeded"
    assert execution["thread_id"] == "thread-pb"
    assert execution["total_input_tokens"] == 1_000_000
    assert execution["total_cost"] == pytest.approx(17.5)

    detail = (await client.get(f"/api/v1/executions/{execution['id']}")).json()
    assert detail["graph_name"] == "demo"
    assert [n["node_name"] for n in detail["nodes"]] == ["agent"]

    # Same payload redelivered (Collector retry) must not duplicate.
    assert (await _post(client, body)).status_code == 200
    assert (await client.get("/api/v1/executions")).json()["total"] == 1


@pytest.mark.asyncio
async def test_protobuf_garbage_is_rejected(client: httpx.AsyncClient) -> None:
    response = await _post(client, b"\xff\xfe not a protobuf \x00\x01")
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_telemetry"
