"""Phase 11 — structured log ingestion + search."""

import json
from typing import Any

import httpx
import pytest

TRACE = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
ROOT = "f000000000000001"
NODE = "f000000000000002"


def _attr(key: str, value: Any) -> dict[str, Any]:
    return {"key": key, "value": {"stringValue": str(value)}}


def _log_event(level: str, source: str, message: str) -> dict[str, Any]:
    return {
        "name": "langops.log",
        "timeUnixNano": "1700000000500000000",
        "attributes": [
            _attr("langops.log.level", level),
            _attr("langops.log.source", source),
            _attr("langops.log.logger", "myapp"),
            _attr("langops.payload", json.dumps({"message": message})),
        ],
    }


def _trace() -> dict[str, Any]:
    root = {
        "traceId": TRACE,
        "spanId": ROOT,
        "name": "graph",
        "startTimeUnixNano": "1700000000000000000",
        "endTimeUnixNano": "1700000002000000000",
        "attributes": [_attr("langops.kind", "execution"), _attr("langops.graph.name", "demo")],
        "status": {"code": 1},
    }
    node = {
        "traceId": TRACE,
        "spanId": NODE,
        "parentSpanId": ROOT,
        "name": "worker",
        "startTimeUnixNano": "1700000000500000000",
        "endTimeUnixNano": "1700000001500000000",
        "attributes": [_attr("langops.kind", "node"), _attr("langops.node.name", "worker")],
        "events": [
            _log_event("info", "app", "starting work"),
            _log_event("warning", "app", "slow response detected"),
            _log_event("debug", "sdk", "internal trace"),
        ],
        "status": {"code": 1},
    }
    return {"resourceSpans": [{"resource": {}, "scopeSpans": [{"spans": [root, node]}]}]}


async def _ingest(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/v1/traces",
        content=json.dumps(_trace()),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_structured_logs_ingested_and_attributed_to_node(client: httpx.AsyncClient) -> None:
    await _ingest(client)
    execution = (await client.get("/api/v1/executions")).json()["items"][0]

    logs = (await client.get(f"/api/v1/logs?execution_id={execution['id']}")).json()
    assert logs["total"] == 3
    messages = {row["message"] for row in logs["items"]}
    assert "starting work" in messages
    # Every structured log is attributed to the worker node.
    assert all(row["node_execution_id"] is not None for row in logs["items"])
    assert all(row["logger"] == "myapp" for row in logs["items"])


@pytest.mark.asyncio
async def test_log_search_filters(client: httpx.AsyncClient) -> None:
    await _ingest(client)

    by_level = (await client.get("/api/v1/logs?level=warning")).json()
    assert by_level["total"] == 1
    assert by_level["items"][0]["message"] == "slow response detected"

    by_source = (await client.get("/api/v1/logs?source=sdk")).json()
    assert by_source["total"] == 1
    assert by_source["items"][0]["source"] == "sdk"

    by_text = (await client.get("/api/v1/logs?q=slow")).json()
    assert by_text["total"] == 1


@pytest.mark.asyncio
async def test_exception_logs_classified_as_exception_source(client: httpx.AsyncClient) -> None:
    trace = {
        "resourceSpans": [
            {
                "resource": {},
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "1" * 32,
                                "spanId": "1" * 16,
                                "name": "graph",
                                "startTimeUnixNano": "1700000000000000000",
                                "endTimeUnixNano": "1700000002000000000",
                                "attributes": [_attr("langops.kind", "execution")],
                                "events": [
                                    {
                                        "name": "exception",
                                        "timeUnixNano": "1700000001000000000",
                                        "attributes": [
                                            _attr("exception.type", "TimeoutError"),
                                            _attr("exception.message", "timed out"),
                                        ],
                                    }
                                ],
                                "status": {"code": 2},
                            }
                        ]
                    }
                ],
            }
        ]
    }
    resp = await client.post(
        "/v1/traces", content=json.dumps(trace), headers={"content-type": "application/json"}
    )
    assert resp.status_code == 200

    logs = (await client.get("/api/v1/logs?source=exception")).json()
    assert logs["total"] == 1
    assert logs["items"][0]["source"] == "exception"
    assert logs["items"][0]["level"] == "error"
