"""Phase 16 — thread (conversation) view + per-node cost breakdown."""

import json
from typing import Any

import httpx
import pytest


def _attr(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    return {"key": key, "value": {"stringValue": str(value)}}


def _trace(trace_id: str, root: str, *, thread: str, tokens: int, end_ns: str) -> dict[str, Any]:
    node = f"{root[:-1]}a"
    llm = f"{root[:-1]}b"
    spans = [
        {
            "traceId": trace_id,
            "spanId": root,
            "name": "graph",
            "startTimeUnixNano": "1700000000000000000",
            "endTimeUnixNano": end_ns,
            "attributes": [
                _attr("langops.kind", "execution"),
                _attr("langops.graph.name", "demo"),
                _attr("langops.thread.id", thread),
            ],
            "status": {"code": 1},
        },
        {
            "traceId": trace_id,
            "spanId": node,
            "parentSpanId": root,
            "name": "agent",
            "startTimeUnixNano": "1700000000100000000",
            "endTimeUnixNano": "1700000001000000000",
            "attributes": [_attr("langops.kind", "node"), _attr("langops.node.name", "agent")],
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
                _attr("gen_ai.request.model", "gpt-4o-mini"),
                _attr("gen_ai.usage.input_tokens", tokens),
                _attr("gen_ai.usage.output_tokens", 0),
            ],
            "status": {"code": 1},
        },
    ]
    return {"resourceSpans": [{"resource": {}, "scopeSpans": [{"spans": spans}]}]}


async def _ingest(client: httpx.AsyncClient, payload: dict[str, Any]) -> None:
    resp = await client.post(
        "/v1/traces", content=json.dumps(payload), headers={"content-type": "application/json"}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_threads_group_and_paginate(client: httpx.AsyncClient) -> None:
    # Two runs on "chat-1", one on "chat-2".
    await _ingest(
        client,
        _trace("a" * 32, "1" * 16, thread="chat-1", tokens=100, end_ns="1700000001000000000"),
    )
    await _ingest(
        client,
        _trace("b" * 32, "2" * 16, thread="chat-1", tokens=200, end_ns="1700000002000000000"),
    )
    await _ingest(
        client, _trace("c" * 32, "3" * 16, thread="chat-2", tokens=50, end_ns="1700000001500000000")
    )

    threads = (await client.get("/api/v1/threads")).json()
    assert threads["total"] == 2
    by_id = {t["thread_id"]: t for t in threads["items"]}
    assert by_id["chat-1"]["run_count"] == 2
    assert by_id["chat-1"]["total_tokens"] == 300
    assert by_id["chat-1"]["succeeded"] == 2
    assert by_id["chat-2"]["run_count"] == 1


@pytest.mark.asyncio
async def test_thread_detail_has_cumulative_totals(client: httpx.AsyncClient) -> None:
    await _ingest(
        client,
        _trace("a" * 32, "1" * 16, thread="chat-1", tokens=100, end_ns="1700000001000000000"),
    )
    await _ingest(
        client,
        _trace("b" * 32, "2" * 16, thread="chat-1", tokens=200, end_ns="1700000002000000000"),
    )

    detail = (await client.get("/api/v1/threads/chat-1")).json()
    assert detail["thread_id"] == "chat-1"
    runs = detail["runs"]
    assert len(runs) == 2  # oldest first
    assert runs[0]["cumulative_tokens"] == 100
    assert runs[1]["cumulative_tokens"] == 300  # running total across the conversation


@pytest.mark.asyncio
async def test_missing_thread_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/threads/nope")
    assert resp.status_code == 404
    assert resp.json()["code"] == "thread_not_found"


@pytest.mark.asyncio
async def test_cost_by_node_in_summary(client: httpx.AsyncClient) -> None:
    await _ingest(
        client,
        _trace("a" * 32, "1" * 16, thread="chat-1", tokens=100, end_ns="1700000001000000000"),
    )
    summary = (await client.get("/api/v1/costs/summary")).json()
    by_node = {row["node_name"]: row for row in summary["by_node"]}
    assert "agent" in by_node
    assert by_node["agent"]["input_tokens"] == 100
    assert by_node["agent"]["calls"] == 1
