"""Phase 17 — global search + LLM-content search + facets."""

import json
from typing import Any

import httpx
import pytest


def _attr(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    return {"key": key, "value": {"stringValue": str(value)}}


def _payload_event(name: str, obj: Any) -> dict[str, Any]:
    return {
        "name": name,
        "timeUnixNano": "1700000000000000000",
        "attributes": [_attr("langops.payload", json.dumps(obj))],
    }


def _trace(*, thread: str, model: str, response_text: str, retries: int) -> dict[str, Any]:
    tid = thread.encode().hex().ljust(32, "0")[:32]
    root, node, llm = f"{tid[:15]}1", f"{tid[:15]}2", f"{tid[:15]}3"
    spans = [
        {
            "traceId": tid,
            "spanId": root,
            "name": "graph",
            "startTimeUnixNano": "1700000000000000000",
            "endTimeUnixNano": "1700000002000000000",
            "attributes": [
                _attr("langops.kind", "execution"),
                _attr("langops.graph.name", "citybot"),
                _attr("langops.thread.id", thread),
            ],
            "status": {"code": 1},
        },
        {
            "traceId": tid,
            "spanId": node,
            "parentSpanId": root,
            "name": "planner",
            "startTimeUnixNano": "1700000000100000000",
            "endTimeUnixNano": "1700000001000000000",
            "attributes": [
                _attr("langops.kind", "node"),
                _attr("langops.node.name", "planner"),
                _attr("langops.node.retry_count", retries),
            ],
            "status": {"code": 1},
        },
        {
            "traceId": tid,
            "spanId": llm,
            "parentSpanId": node,
            "name": "chat",
            "startTimeUnixNano": "1700000000200000000",
            "endTimeUnixNano": "1700000000900000000",
            "attributes": [
                _attr("langops.kind", "llm"),
                _attr("gen_ai.system", "openai"),
                _attr("gen_ai.request.model", model),
                _attr("gen_ai.usage.input_tokens", 10),
                _attr("gen_ai.usage.output_tokens", 5),
            ],
            "events": [
                _payload_event("langops.llm.messages", [{"type": "human", "content": "hi"}]),
                _payload_event("langops.llm.response", {"content": response_text}),
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
async def test_search_finds_llm_content(client: httpx.AsyncClient) -> None:
    await _ingest(
        client,
        _trace(
            thread="paris",
            model="gpt-4o-mini",
            response_text="The Eiffel Tower is iconic.",
            retries=0,
        ),
    )
    await _ingest(
        client,
        _trace(thread="tokyo", model="gpt-5", response_text="Shibuya crossing is busy.", retries=0),
    )

    # A phrase that only appears inside an LLM response finds its execution.
    result = (await client.get("/api/v1/search?q=Eiffel")).json()
    groups = {g["kind"]: g for g in result["groups"]}
    assert "llm" in groups
    assert groups["llm"]["total"] == 1
    hit = groups["llm"]["hits"][0]
    assert "Eiffel" in hit["label"]
    assert hit["execution_id"] is not None


@pytest.mark.asyncio
async def test_search_groups_by_kind(client: httpx.AsyncClient) -> None:
    await _ingest(
        client,
        _trace(thread="paris", model="gpt-4o-mini", response_text="hello world", retries=0),
    )
    result = (await client.get("/api/v1/search?q=paris")).json()
    kinds = {g["kind"] for g in result["groups"]}
    # "paris" matches the thread (execution) and nothing else surprising.
    assert "execution" in kinds


@pytest.mark.asyncio
async def test_search_empty_query_422(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/search?q=")).status_code == 422


@pytest.mark.asyncio
async def test_execution_facets_model_and_has_retries(client: httpx.AsyncClient) -> None:
    await _ingest(
        client,
        _trace(thread="a", model="gpt-4o-mini", response_text="x", retries=0),
    )
    await _ingest(
        client,
        _trace(thread="b", model="gpt-5", response_text="y", retries=2),
    )

    by_model = (await client.get("/api/v1/executions?model=gpt-5")).json()
    assert by_model["total"] == 1
    assert by_model["items"][0]["thread_id"] == "b"

    retried = (await client.get("/api/v1/executions?has_retries=true")).json()
    assert retried["total"] == 1
    assert retried["items"][0]["thread_id"] == "b"
