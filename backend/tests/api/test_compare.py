"""Execution comparison endpoint — diff two runs side by side."""

import json
from typing import Any

import httpx
import pytest


def _attr(key: str, value: Any) -> dict[str, Any]:
    return {"key": key, "value": {"stringValue": str(value)}}


def _trace(trace_id: str, span_id: str, output: dict[str, Any]) -> dict[str, Any]:
    span = {
        "traceId": trace_id,
        "spanId": span_id,
        "name": "graph",
        "startTimeUnixNano": "1700000000000000000",
        "endTimeUnixNano": "1700000001000000000",
        "attributes": [_attr("langops.kind", "execution"), _attr("langops.graph.name", "demo")],
        "events": [
            {
                "name": "langops.execution.output",
                "timeUnixNano": "1700000001000000000",
                "attributes": [_attr("langops.payload", json.dumps(output))],
            }
        ],
        "status": {"code": 1},
    }
    return {"resourceSpans": [{"resource": {}, "scopeSpans": [{"spans": [span]}]}]}


async def _ingest(client: httpx.AsyncClient, payload: dict[str, Any]) -> None:
    resp = await client.post(
        "/v1/traces", content=json.dumps(payload), headers={"content-type": "application/json"}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_compare_two_executions(client: httpx.AsyncClient) -> None:
    await _ingest(client, _trace("a" * 32, "1" * 16, {"answer": "yes", "score": 1}))
    await _ingest(client, _trace("b" * 32, "2" * 16, {"answer": "no", "extra": True}))

    items = (await client.get("/api/v1/executions")).json()["items"]
    a_id, b_id = items[1]["id"], items[0]["id"]

    comparison = (await client.get(f"/api/v1/executions/compare?a={a_id}&b={b_id}")).json()
    assert comparison["a"]["execution"]["id"] == a_id
    assert comparison["b"]["execution"]["id"] == b_id

    diff = comparison["final_state_diff"]
    assert diff["added"] == {"extra": True}  # b added `extra`
    assert diff["removed"] == ["score"]  # b dropped `score`
    assert diff["modified"]["answer"] == {"old": "yes", "new": "no"}


@pytest.mark.asyncio
async def test_compare_missing_execution_404(client: httpx.AsyncClient) -> None:
    await _ingest(client, _trace("c" * 32, "3" * 16, {"x": 1}))
    real = (await client.get("/api/v1/executions")).json()["items"][0]["id"]
    missing = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"/api/v1/executions/compare?a={real}&b={missing}")
    assert resp.status_code == 404
