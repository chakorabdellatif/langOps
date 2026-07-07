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


def _rich_trace(trace_id: str, root: str, *, tokens: int, model: str) -> dict[str, Any]:
    """Execution with one llm node so comparison has performance/LLM data."""
    node = f"{root[:-1]}a"
    llm = f"{root[:-1]}b"
    spans = [
        {
            "traceId": trace_id,
            "spanId": root,
            "name": "graph",
            "startTimeUnixNano": "1700000000000000000",
            "endTimeUnixNano": "1700000002000000000",
            "attributes": [
                _attr("langops.kind", "execution"),
                _attr("langops.graph.name", "demo"),
                _attr("langops.graph.topology_hash", "hash-1"),
            ],
            "events": [
                {
                    "name": "langops.execution.output",
                    "timeUnixNano": "1700000001000000000",
                    "attributes": [_attr("langops.payload", json.dumps({"answer": "x"}))],
                }
            ],
            "status": {"code": 1},
        },
        {
            "traceId": trace_id,
            "spanId": node,
            "parentSpanId": root,
            "name": "plan",
            "startTimeUnixNano": "1700000000100000000",
            "endTimeUnixNano": "1700000001100000000",
            "attributes": [_attr("langops.kind", "node"), _attr("langops.node.name", "plan")],
            "status": {"code": 1},
        },
        {
            "traceId": trace_id,
            "spanId": llm,
            "parentSpanId": node,
            "name": "chat",
            "startTimeUnixNano": "1700000000200000000",
            "endTimeUnixNano": "1700000000900000000",
            "attributes": [
                _attr("langops.kind", "llm"),
                _attr("gen_ai.system", "openai"),
                _attr("gen_ai.request.model", model),
                {"key": "gen_ai.usage.input_tokens", "value": {"intValue": str(tokens)}},
                {"key": "gen_ai.usage.output_tokens", "value": {"intValue": "10"}},
            ],
            "status": {"code": 1},
        },
    ]
    return {"resourceSpans": [{"resource": {}, "scopeSpans": [{"spans": spans}]}]}


@pytest.mark.asyncio
async def test_compare_surfaces_deterministic_sections(client: httpx.AsyncClient) -> None:
    # Same graph/thread, but a model swap and a token increase between runs.
    await _ingest(client, _rich_trace("a" * 32, "1" * 16, tokens=100, model="gpt-4o-mini"))
    await _ingest(client, _rich_trace("b" * 32, "2" * 16, tokens=200, model="gpt-5"))

    items = (await client.get("/api/v1/executions")).json()["items"]
    a_id, b_id = items[1]["id"], items[0]["id"]
    comparison = (await client.get(f"/api/v1/executions/compare?a={a_id}&b={b_id}")).json()

    result = comparison["result"]
    assert result is not None
    # Performance: tokens went from 110 -> 210.
    assert result["performance"]["total_tokens"]["delta"] == 100.0
    # LLM: model changed.
    assert result["llm_changes"]["model_changed"] is True
    # Insights mention the model change and the token increase.
    metrics = {i["metric"] for i in result["insights"]}
    assert "model" in metrics
    assert "tokens" in metrics


@pytest.mark.asyncio
async def test_compare_missing_execution_404(client: httpx.AsyncClient) -> None:
    await _ingest(client, _trace("c" * 32, "3" * 16, {"x": 1}))
    real = (await client.get("/api/v1/executions")).json()["items"][0]["id"]
    missing = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"/api/v1/executions/compare?a={real}&b={missing}")
    assert resp.status_code == 404
