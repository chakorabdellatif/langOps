"""Phase 9 — rich graph node inspection.

Covers deterministic category inference (llm / tool / utility, and an
SDK-provided structural category), per-node rollups recomputed idempotently,
state-change key surfacing, and mixed old/new SDK topology payloads.
"""

import json
from typing import Any

import httpx
import pytest

TRACE = "cccccccccccccccccccccccccccccccc"
ROOT = "d000000000000001"


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


def _span(span_id: str, attrs: list[dict], events: list[dict] | None = None, parent: str = ROOT):
    span: dict[str, Any] = {
        "traceId": TRACE,
        "spanId": span_id,
        "parentSpanId": parent,
        "name": "s",
        "startTimeUnixNano": "1700000000500000000",
        "endTimeUnixNano": "1700000001500000000",
        "attributes": attrs,
        "status": {"code": 1},
    }
    if events:
        span["events"] = events
    return span


def _trace(extra_spans: list[dict]) -> dict[str, Any]:
    root = {
        "traceId": TRACE,
        "spanId": ROOT,
        "name": "graph",
        "startTimeUnixNano": "1700000000000000000",
        "endTimeUnixNano": "1700000002000000000",
        "attributes": [
            _attr("langops.kind", "execution"),
            _attr("langops.graph.name", "demo"),
            _attr("langops.graph.topology_hash", "h1"),
        ],
        "status": {"code": 1},
    }
    return {"resourceSpans": [{"resource": {}, "scopeSpans": [{"spans": [root, *extra_spans]}]}]}


async def _ingest(client: httpx.AsyncClient, payload: dict[str, Any]) -> httpx.Response:
    return await client.post(
        "/v1/traces", content=json.dumps(payload), headers={"content-type": "application/json"}
    )


async def _nodes(client: httpx.AsyncClient) -> dict[str, dict]:
    execution = (await client.get("/api/v1/executions")).json()["items"][0]
    detail = (await client.get(f"/api/v1/executions/{execution['id']}")).json()
    return {n["node_name"]: n for n in detail["nodes"]}


@pytest.mark.asyncio
async def test_category_inference_matrix(client: httpx.AsyncClient) -> None:
    """llm node (has LLM child), tool node (has tool child), utility (neither),
    and a router node whose SDK-provided structural category is preserved."""
    spans = [
        _span(
            "e000000000000010",
            [_attr("langops.kind", "node"), _attr("langops.node.name", "llm_node")],
        ),
        _span(
            "e000000000000011",
            [
                _attr("langops.kind", "llm"),
                _attr("gen_ai.system", "openai"),
                _attr("gen_ai.request.model", "gpt-4o-mini"),
                _attr("gen_ai.usage.input_tokens", 100),
                _attr("gen_ai.usage.output_tokens", 50),
            ],
            parent="e000000000000010",
        ),
        _span(
            "e000000000000020",
            [_attr("langops.kind", "node"), _attr("langops.node.name", "tool_node")],
        ),
        _span(
            "e000000000000021",
            [
                _attr("langops.kind", "tool"),
                _attr("langops.tool.name", "search"),
            ],
            parent="e000000000000020",
        ),
        _span(
            "e000000000000030", [_attr("langops.kind", "node"), _attr("langops.node.name", "plain")]
        ),
        _span(
            "e000000000000040",
            [
                _attr("langops.kind", "node"),
                _attr("langops.node.name", "route"),
                _attr("langops.node.category", "router"),
            ],
        ),
    ]
    assert (await _ingest(client, _trace(spans))).status_code == 200

    nodes = await _nodes(client)
    assert nodes["llm_node"]["category"] == "llm"
    assert nodes["llm_node"]["models"] == ["gpt-4o-mini"]
    assert nodes["tool_node"]["category"] == "tool"
    assert nodes["tool_node"]["tool_names"] == ["search"]
    assert nodes["plain"]["category"] == "utility"
    # Structural SDK category wins even though the router made no LLM/tool call.
    assert nodes["route"]["category"] == "router"


@pytest.mark.asyncio
async def test_node_rollups_are_idempotent(client: httpx.AsyncClient) -> None:
    spans = [
        _span(
            "e000000000000010",
            [_attr("langops.kind", "node"), _attr("langops.node.name", "llm_node")],
        ),
        _span(
            "e000000000000011",
            [
                _attr("langops.kind", "llm"),
                _attr("gen_ai.system", "openai"),
                _attr("gen_ai.request.model", "gpt-4o-mini"),
                _attr("gen_ai.usage.input_tokens", 100),
                _attr("gen_ai.usage.output_tokens", 50),
            ],
            parent="e000000000000010",
        ),
    ]
    await _ingest(client, _trace(spans))
    await _ingest(client, _trace(spans))  # redelivery must not double the rollup

    node = (await _nodes(client))["llm_node"]
    assert node["input_tokens"] == 100
    assert node["output_tokens"] == 50


@pytest.mark.asyncio
async def test_state_changes_surface_on_node(client: httpx.AsyncClient) -> None:
    node_span = _span(
        "e000000000000010",
        [_attr("langops.kind", "node"), _attr("langops.node.name", "writer")],
        events=[
            _payload_event("langops.state.input", {"draft": "x"}),
            _payload_event("langops.state.output", {"draft": "y", "report": "done"}),
        ],
    )
    assert (await _ingest(client, _trace([node_span]))).status_code == 200

    node = (await _nodes(client))["writer"]
    changes = node["state_changes"]
    assert "report" in changes["added"]
    assert "draft" in changes["modified"]


@pytest.mark.asyncio
async def test_out_of_order_llm_still_rolls_up_node(client: httpx.AsyncClient) -> None:
    """An LLM span arriving in a later batch must still update its node's rollup."""
    node_only = _trace(
        [
            _span(
                "e000000000000010",
                [_attr("langops.kind", "node"), _attr("langops.node.name", "llm_node")],
            ),
        ]
    )
    llm_only = _trace(
        [
            _span(
                "e000000000000011",
                [
                    _attr("langops.kind", "llm"),
                    _attr("gen_ai.system", "openai"),
                    _attr("gen_ai.request.model", "gpt-4o-mini"),
                    _attr("gen_ai.usage.input_tokens", 100),
                    _attr("gen_ai.usage.output_tokens", 50),
                ],
                parent="e000000000000010",
            ),
        ]
    )
    await _ingest(client, node_only)
    node = (await _nodes(client))["llm_node"]
    assert node["category"] == "utility"  # no children yet

    await _ingest(client, llm_only)  # late child span
    node = (await _nodes(client))["llm_node"]
    assert node["category"] == "llm"
    assert node["input_tokens"] == 100
