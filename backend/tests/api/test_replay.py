"""Phase 12 — replay lineage ingestion + API exposure."""

import json
from typing import Any

import httpx
import pytest


def _attr(key: str, value: Any) -> dict[str, Any]:
    return {"key": key, "value": {"stringValue": str(value)}}


def _payload_event(name: str, obj: Any) -> dict[str, Any]:
    return {
        "name": name,
        "timeUnixNano": "1700000000000000000",
        "attributes": [_attr("langops.payload", json.dumps(obj))],
    }


def _execution(trace_id: str, span_id: str, *, replay_of: str | None = None) -> dict[str, Any]:
    attrs = [_attr("langops.kind", "execution"), _attr("langops.graph.name", "demo")]
    events = [_payload_event("langops.execution.input", {"x": 1})]
    if replay_of:
        attrs.append(_attr("langops.execution.replay_of", replay_of))
        events.append(_payload_event("langops.execution.overrides", {"model": "gpt-5"}))
    span = {
        "traceId": trace_id,
        "spanId": span_id,
        "name": "graph",
        "startTimeUnixNano": "1700000000000000000",
        "endTimeUnixNano": "1700000002000000000",
        "attributes": attrs,
        "events": events,
        "status": {"code": 1},
    }
    return {"resourceSpans": [{"resource": {}, "scopeSpans": [{"spans": [span]}]}]}


async def _ingest(client: httpx.AsyncClient, payload: dict[str, Any]) -> None:
    resp = await client.post(
        "/v1/traces", content=json.dumps(payload), headers={"content-type": "application/json"}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_replay_lineage_exposed_both_directions(client: httpx.AsyncClient) -> None:
    # Original run.
    await _ingest(client, _execution("a" * 32, "1" * 16))
    original_id = (await client.get("/api/v1/executions")).json()["items"][0]["id"]

    # A replay of it, with a model override.
    await _ingest(client, _execution("b" * 32, "2" * 16, replay_of=original_id))

    # The replay points back to the original + records its overrides.
    replay = next(
        e
        for e in (await client.get("/api/v1/executions")).json()["items"]
        if e["replay_of_execution_id"] is not None
    )
    assert replay["replay_of_execution_id"] == original_id

    replay_detail = (await client.get(f"/api/v1/executions/{replay['id']}")).json()
    assert replay_detail["replay_of_execution_id"] == original_id
    assert replay_detail["replay_overrides"] == {"model": "gpt-5"}

    # The original lists its replays.
    original_detail = (await client.get(f"/api/v1/executions/{original_id}")).json()
    assert len(original_detail["replays"]) == 1
    assert original_detail["replays"][0]["id"] == replay["id"]
    assert original_detail["replays"][0]["overrides"] == {"model": "gpt-5"}


@pytest.mark.asyncio
async def test_non_replay_execution_has_null_lineage(client: httpx.AsyncClient) -> None:
    await _ingest(client, _execution("c" * 32, "3" * 16))
    detail_id = (await client.get("/api/v1/executions")).json()["items"][0]["id"]
    detail = (await client.get(f"/api/v1/executions/{detail_id}")).json()
    assert detail["replay_of_execution_id"] is None
    assert detail["replays"] == []
