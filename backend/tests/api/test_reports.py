"""Graphs, state-evolution, costs, and metrics query endpoints."""

import json
from typing import Any

import httpx
import pytest

TRACE_ID = "99998888777766665555444433332222"
ROOT = "1111111111111111"
NODE = "2222222222222222"
LLM = "3333333333333333"


def _attr(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    return {"key": key, "value": {"stringValue": str(value)}}


def _event(name: str, obj: Any) -> dict[str, Any]:
    return {
        "name": name,
        "timeUnixNano": "1700000000000000000",
        "attributes": [_attr("langops.payload", json.dumps(obj))],
    }


def _trace() -> dict[str, Any]:
    topology = {"nodes": ["__start__", "agent", "__end__"], "edges": [["__start__", "agent"]]}
    spans = [
        {
            "traceId": TRACE_ID,
            "spanId": ROOT,
            "name": "graph",
            "startTimeUnixNano": "1700000000000000000",
            "endTimeUnixNano": "1700000001500000000",  # 1500 ms
            "attributes": [
                _attr("langops.kind", "execution"),
                _attr("langops.graph.name", "demo"),
                _attr("langops.graph.topology_hash", "h1"),
            ],
            "events": [_event("langops.graph.topology", topology)],
            "status": {"code": 1},
        },
        {
            "traceId": TRACE_ID,
            "spanId": NODE,
            "parentSpanId": ROOT,
            "name": "agent",
            "startTimeUnixNano": "1700000000500000000",
            "endTimeUnixNano": "1700000001000000000",
            "attributes": [
                _attr("langops.kind", "node"),
                _attr("langops.node.name", "agent"),
                _attr("langops.node.sequence", 1),
            ],
            "events": [
                {
                    "name": "langops.state.input",
                    "timeUnixNano": "1700000000500000000",
                    "attributes": [
                        _attr("langops.payload", json.dumps({"messages": ["a"]})),
                        _attr("langops.state.size_bytes", 12),
                        _attr("langops.state.message_count", 1),
                    ],
                },
                {
                    "name": "langops.state.output",
                    "timeUnixNano": "1700000001000000000",
                    "attributes": [
                        _attr("langops.payload", json.dumps({"messages": ["a", "b"]})),
                        _attr("langops.state.size_bytes", 20),
                        _attr("langops.state.message_count", 2),
                    ],
                },
            ],
            "status": {"code": 1},
        },
        {
            "traceId": TRACE_ID,
            "spanId": LLM,
            "parentSpanId": NODE,
            "name": "chat",
            "startTimeUnixNano": "1700000000600000000",
            "endTimeUnixNano": "1700000000900000000",
            "attributes": [
                _attr("langops.kind", "llm"),
                _attr("gen_ai.system", "openai"),
                _attr("gen_ai.request.model", "gpt-4o"),
                _attr("gen_ai.usage.input_tokens", 1_000_000),
                _attr("gen_ai.usage.output_tokens", 1_000_000),
            ],
            "status": {"code": 1},
        },
    ]
    return {"resourceSpans": [{"resource": {}, "scopeSpans": [{"spans": spans}]}]}


@pytest.fixture
async def ingested(client: httpx.AsyncClient) -> dict[str, Any]:
    resp = await client.post(
        "/v1/traces", content=json.dumps(_trace()), headers={"content-type": "application/json"}
    )
    assert resp.status_code == 200
    return (await client.get("/api/v1/executions")).json()["items"][0]


@pytest.mark.asyncio
async def test_graphs_and_topology(client: httpx.AsyncClient, ingested: dict[str, Any]) -> None:
    graphs = (await client.get("/api/v1/graphs")).json()
    assert len(graphs) == 1
    assert graphs[0]["name"] == "demo"

    topology = (await client.get(f"/api/v1/graphs/{graphs[0]['id']}/topology")).json()
    assert "agent" in topology["nodes"]
    assert topology["edges"] == [["__start__", "agent"]]


@pytest.mark.asyncio
async def test_state_evolution(client: httpx.AsyncClient, ingested: dict[str, Any]) -> None:
    state = (await client.get(f"/api/v1/executions/{ingested['id']}/state")).json()
    assert len(state["steps"]) == 2
    # Server-recomputed diff: the second snapshot added a message.
    output_step = state["steps"][1]
    assert output_step["node_name"] == "agent"
    assert output_step["diff"]["modified"]  # messages channel changed
    # Context-growth series drives the chart.
    assert [g["message_count"] for g in state["context_growth"]] == [1, 2]


@pytest.mark.asyncio
async def test_cost_summary(client: httpx.AsyncClient, ingested: dict[str, Any]) -> None:
    summary = (await client.get("/api/v1/costs/summary")).json()
    # gpt-4o: 1M in * $2.50 + 1M out * $10 = 12.5
    assert summary["total_cost"] == pytest.approx(12.5)
    assert summary["by_model"][0]["model"] == "gpt-4o"
    assert summary["by_model"][0]["unknown_calls"] == 0


@pytest.mark.asyncio
async def test_metrics_overview(client: httpx.AsyncClient, ingested: dict[str, Any]) -> None:
    metrics = (await client.get("/api/v1/metrics/overview")).json()
    assert metrics["total_executions"] == 1
    assert metrics["succeeded"] == 1
    assert metrics["failure_rate"] == 0.0
    assert metrics["latency_p50_ms"] == 1500
    assert metrics["avg_latency_ms"] == 1500
