"""Phase 18 — failure analytics: group failures by exception type × node."""

import json
from typing import Any

import httpx
import pytest


def _attr(key: str, value: Any) -> dict[str, Any]:
    return {"key": key, "value": {"stringValue": str(value)}}


def _exception_event(exc_type: str, message: str) -> dict[str, Any]:
    return {
        "name": "exception",
        "timeUnixNano": "1700000001000000000",
        "attributes": [
            _attr("exception.type", exc_type),
            _attr("exception.message", message),
        ],
    }


def _failing_trace(trace_id: str, root: str, *, node: str, exc_type: str) -> dict[str, Any]:
    node_span = f"{root[:-1]}a"
    spans = [
        {
            "traceId": trace_id,
            "spanId": root,
            "name": "graph",
            "startTimeUnixNano": "1700000000000000000",
            "endTimeUnixNano": "1700000002000000000",
            "attributes": [_attr("langops.kind", "execution"), _attr("langops.graph.name", "g")],
            "events": [_exception_event(exc_type, "boom")],  # SDK record_exception on root
            "status": {"code": 2},
        },
        {
            "traceId": trace_id,
            "spanId": node_span,
            "parentSpanId": root,
            "name": node,
            "startTimeUnixNano": "1700000000500000000",
            "endTimeUnixNano": "1700000001500000000",
            "attributes": [_attr("langops.kind", "node"), _attr("langops.node.name", node)],
            "events": [_exception_event(exc_type, "boom")],
            "status": {"code": 2},
        },
    ]
    return {"resourceSpans": [{"resource": {}, "scopeSpans": [{"spans": spans}]}]}


async def _ingest(client: httpx.AsyncClient, payload: dict[str, Any]) -> None:
    resp = await client.post(
        "/v1/traces", content=json.dumps(payload), headers={"content-type": "application/json"}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_errors_group_by_type_and_node(client: httpx.AsyncClient) -> None:
    # 3 TimeoutErrors in "weather", 1 ValueError in "planner".
    for i in range(3):
        await _ingest(
            client,
            _failing_trace(f"{i}" * 32, f"{i}" * 16, node="weather", exc_type="TimeoutError"),
        )
    await _ingest(client, _failing_trace("9" * 32, "9" * 16, node="planner", exc_type="ValueError"))

    report = (await client.get("/api/v1/errors/summary")).json()
    assert report["total"] == 4
    groups = {(g["error_type"], g["node_name"]): g for g in report["groups"]}
    assert groups[("TimeoutError", "weather")]["count"] == 3
    assert groups[("ValueError", "planner")]["count"] == 1
    assert groups[("TimeoutError", "weather")]["sample_execution_id"] is not None
    # A daily trend is present.
    assert sum(t["count"] for t in report["trend"]) == 4


@pytest.mark.asyncio
async def test_error_type_facet_on_executions(client: httpx.AsyncClient) -> None:
    await _ingest(
        client, _failing_trace("a" * 32, "1" * 16, node="weather", exc_type="TimeoutError")
    )
    await _ingest(client, _failing_trace("b" * 32, "2" * 16, node="planner", exc_type="ValueError"))

    filtered = (await client.get("/api/v1/executions?error_type=TimeoutError")).json()
    assert filtered["total"] == 1
