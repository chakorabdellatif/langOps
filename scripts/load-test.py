#!/usr/bin/env python3
"""Ingestion load test (Phase 8 / M4).

Fires N concurrent synthetic OTLP/JSON traces at the API and reports
throughput and per-request latency. Run against a running stack:

    docker compose up -d
    python scripts/load-test.py --count 100 --concurrency 20

Each trace is a distinct execution with one node + one LLM call, so this also
exercises cost pricing and rollups. Requires `httpx` (pip install httpx).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import uuid

import httpx


def _attr(key: str, value: object) -> dict:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    return {"key": key, "value": {"stringValue": str(value)}}


def _trace() -> dict:
    trace_id = uuid.uuid4().hex  # 32 hex chars
    root, node, llm = (uuid.uuid4().hex[:16] for _ in range(3))
    spans = [
        {
            "traceId": trace_id, "spanId": root, "name": "graph",
            "startTimeUnixNano": "1700000000000000000",
            "endTimeUnixNano": "1700000001000000000",
            "attributes": [_attr("langops.kind", "execution"), _attr("langops.graph.name", "load")],
            "status": {"code": 1},
        },
        {
            "traceId": trace_id, "spanId": node, "parentSpanId": root, "name": "agent",
            "startTimeUnixNano": "1700000000200000000",
            "endTimeUnixNano": "1700000000800000000",
            "attributes": [
                _attr("langops.kind", "node"),
                _attr("langops.node.name", "agent"),
                _attr("langops.node.sequence", 1),
            ],
            "status": {"code": 1},
        },
        {
            "traceId": trace_id, "spanId": llm, "parentSpanId": node, "name": "chat",
            "startTimeUnixNano": "1700000000300000000",
            "endTimeUnixNano": "1700000000700000000",
            "attributes": [
                _attr("langops.kind", "llm"),
                _attr("gen_ai.system", "openai"),
                _attr("gen_ai.request.model", "gpt-4o-mini"),
                _attr("gen_ai.usage.input_tokens", 500),
                _attr("gen_ai.usage.output_tokens", 200),
            ],
            "status": {"code": 1},
        },
    ]
    return {"resourceSpans": [{"resource": {}, "scopeSpans": [{"spans": spans}]}]}


async def _worker(client: httpx.AsyncClient, url: str, latencies: list[float]) -> None:
    body = json.dumps(_trace())
    start = time.perf_counter()
    resp = await client.post(url, content=body, headers={"content-type": "application/json"})
    resp.raise_for_status()
    latencies.append((time.perf_counter() - start) * 1000)


async def _run(base_url: str, count: int, concurrency: int) -> None:
    url = f"{base_url}/v1/traces"
    latencies: list[float] = []
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=30.0) as client:

        async def bounded() -> None:
            async with sem:
                await _worker(client, url, latencies)

        wall_start = time.perf_counter()
        await asyncio.gather(*(bounded() for _ in range(count)))
        wall = time.perf_counter() - wall_start

    latencies.sort()
    p = lambda q: latencies[min(len(latencies) - 1, round(q * (len(latencies) - 1)))]  # noqa: E731
    print(f"ingested {count} traces in {wall:.2f}s  ({count / wall:.0f} req/s)")
    print(f"latency ms  mean={statistics.mean(latencies):.1f}  p50={p(0.5):.1f}  "
          f"p95={p(0.95):.1f}  p99={p(0.99):.1f}  max={latencies[-1]:.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LangOps ingestion load test.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(_run(args.base_url, args.count, args.concurrency))


if __name__ == "__main__":
    main()
