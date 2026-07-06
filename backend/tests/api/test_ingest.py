"""End-to-end: post an OTLP/JSON trace, then read it back through the query API.

Also covers the two hard ingestion cases: duplicate delivery and a child span
arriving before its execution root (out-of-order).
"""

import json
from typing import Any

import httpx
import pytest

TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
ROOT_SPAN = "b7ad6b7169203331"
NODE_SPAN = "aaaa000000000001"
LLM_SPAN = "aaaa000000000002"


def _attr(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    return {"key": key, "value": {"stringValue": str(value)}}


def _payload_event(name: str, obj: Any) -> dict[str, Any]:
    return {
        "name": name,
        "timeUnixNano": "1700000000000000000",
        "attributes": [_attr("langops.payload", json.dumps(obj))],
    }


def _otlp_trace() -> dict[str, Any]:
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": [_attr("langops.sdk.version", "0.1.0")]},
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": TRACE_ID,
                                "spanId": ROOT_SPAN,
                                "name": "graph",
                                "startTimeUnixNano": "1700000000000000000",
                                "endTimeUnixNano": "1700000002000000000",
                                "attributes": [
                                    _attr("langops.kind", "execution"),
                                    _attr("langops.execution.id", "exec-1"),
                                    _attr("langops.graph.name", "demo"),
                                    _attr("langops.graph.topology_hash", "hash-1"),
                                    _attr("langops.thread.id", "thread-1"),
                                ],
                                "events": [
                                    _payload_event("langops.execution.input", {"q": "hi"}),
                                    _payload_event("langops.execution.output", {"a": "yo"}),
                                ],
                                "status": {"code": 1},
                            },
                            {
                                "traceId": TRACE_ID,
                                "spanId": NODE_SPAN,
                                "parentSpanId": ROOT_SPAN,
                                "name": "agent",
                                "startTimeUnixNano": "1700000000500000000",
                                "endTimeUnixNano": "1700000001500000000",
                                "attributes": [
                                    _attr("langops.kind", "node"),
                                    _attr("langops.node.name", "agent"),
                                    _attr("langops.node.sequence", 0),
                                ],
                                "status": {"code": 1},
                            },
                            {
                                "traceId": TRACE_ID,
                                "spanId": LLM_SPAN,
                                "parentSpanId": NODE_SPAN,
                                "name": "chat",
                                "startTimeUnixNano": "1700000000600000000",
                                "endTimeUnixNano": "1700000001000000000",
                                "attributes": [
                                    _attr("langops.kind", "llm"),
                                    _attr("gen_ai.system", "anthropic"),
                                    _attr("gen_ai.request.model", "claude-opus-4-8"),
                                    _attr("gen_ai.usage.input_tokens", 1_000_000),
                                    _attr("gen_ai.usage.output_tokens", 500_000),
                                ],
                                "status": {"code": 1},
                            },
                        ]
                    }
                ],
            }
        ]
    }


async def _ingest(client: httpx.AsyncClient, payload: dict[str, Any]) -> httpx.Response:
    return await client.post(
        "/v1/traces", content=json.dumps(payload), headers={"content-type": "application/json"}
    )


@pytest.mark.asyncio
async def test_ingest_then_query(client: httpx.AsyncClient) -> None:
    assert (await _ingest(client, _otlp_trace())).status_code == 200

    listing = (await client.get("/api/v1/executions")).json()
    assert listing["total"] == 1
    execution = listing["items"][0]
    assert execution["status"] == "succeeded"
    assert execution["thread_id"] == "thread-1"
    assert execution["total_input_tokens"] == 1_000_000
    # 1M input * $5 + 0.5M output * $25 = 17.5 (seeded pricing)
    assert execution["total_cost"] == pytest.approx(17.5)

    detail = (await client.get(f"/api/v1/executions/{execution['id']}")).json()
    assert detail["graph_name"] == "demo"
    assert len(detail["nodes"]) == 1
    node = detail["nodes"][0]

    node_detail = (await client.get(f"/api/v1/nodes/{node['id']}")).json()
    assert len(node_detail["llm_calls"]) == 1
    call = node_detail["llm_calls"][0]
    assert call["model"] == "claude-opus-4-8"
    # Priced from the JSON catalog, split by direction.
    assert call["cost_status"] == "priced"
    assert call["total_cost"] == pytest.approx(17.5)
    assert call["input_cost"] == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_ingest_is_idempotent(client: httpx.AsyncClient) -> None:
    await _ingest(client, _otlp_trace())
    await _ingest(client, _otlp_trace())  # redelivery must not duplicate

    listing = (await client.get("/api/v1/executions")).json()
    assert listing["total"] == 1


@pytest.mark.asyncio
async def test_ingest_out_of_order(client: httpx.AsyncClient) -> None:
    # Child spans arrive first (root span dropped from this batch).
    full = _otlp_trace()
    spans = full["resourceSpans"][0]["scopeSpans"][0]["spans"]
    children = {
        "resourceSpans": [
            {"resource": full["resourceSpans"][0]["resource"], "scopeSpans": [{"spans": spans[1:]}]}
        ]
    }
    root = {
        "resourceSpans": [
            {"resource": full["resourceSpans"][0]["resource"], "scopeSpans": [{"spans": spans[:1]}]}
        ]
    }

    assert (await _ingest(client, children)).status_code == 200
    assert (await _ingest(client, root)).status_code == 200

    listing = (await client.get("/api/v1/executions")).json()
    assert listing["total"] == 1
    execution = listing["items"][0]
    assert execution["status"] == "succeeded"  # enriched once the root landed
    assert execution["total_input_tokens"] == 1_000_000


@pytest.mark.asyncio
async def test_malformed_json_is_rejected(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/v1/traces", content="not json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_telemetry"


@pytest.mark.asyncio
async def test_unknown_execution_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/executions/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["code"] == "execution_not_found"


@pytest.mark.asyncio
async def test_oversized_payload_rejected(client: httpx.AsyncClient) -> None:
    # Default limit is 4 MiB; exceed it with junk bytes.
    huge = b"x" * (4_194_304 + 1)
    response = await client.post(
        "/v1/traces", content=huge, headers={"content-type": "application/x-protobuf"}
    )
    assert response.status_code == 413
    assert response.json()["code"] == "request_too_large"
