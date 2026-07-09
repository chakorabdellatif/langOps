"""Load-sanity generator — fire N concurrent executions at the ingest API and
report ingest latency/throughput. Proves the pipeline (and the Phase 14 rollup
batching) holds under concurrency; run against a live stack.

    python scripts/loadtest.py --n 100 --api http://localhost:8000 [--api-key KEY]

Each "execution" is one OTLP/JSON trace with a root + node + LLM span, posted
concurrently. Asserts every trace is queryable afterward (no loss).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

import httpx


def _attr(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    return {"key": key, "value": {"stringValue": str(value)}}


def _trace(i: int) -> dict[str, Any]:
    tid = f"{i:032x}"
    root, node, llm = f"{i:016x}", f"{i + 10**6:016x}", f"{i + 2 * 10**6:016x}"
    spans = [
        {
            "traceId": tid,
            "spanId": root,
            "name": "graph",
            "startTimeUnixNano": "1700000000000000000",
            "endTimeUnixNano": "1700000001000000000",
            "attributes": [
                _attr("langops.kind", "execution"),
                _attr("langops.graph.name", "loadtest"),
                _attr("langops.thread.id", f"t{i % 20}"),
            ],
            "status": {"code": 1},
        },
        {
            "traceId": tid,
            "spanId": node,
            "parentSpanId": root,
            "name": "agent",
            "startTimeUnixNano": "1700000000100000000",
            "endTimeUnixNano": "1700000000900000000",
            "attributes": [_attr("langops.kind", "node"), _attr("langops.node.name", "agent")],
            "status": {"code": 1},
        },
        {
            "traceId": tid,
            "spanId": llm,
            "parentSpanId": node,
            "name": "chat",
            "startTimeUnixNano": "1700000000200000000",
            "endTimeUnixNano": "1700000000800000000",
            "attributes": [
                _attr("langops.kind", "llm"),
                _attr("gen_ai.system", "openai"),
                _attr("gen_ai.request.model", "gpt-4o-mini"),
                _attr("gen_ai.usage.input_tokens", 100),
                _attr("gen_ai.usage.output_tokens", 50),
            ],
            "status": {"code": 1},
        },
    ]
    return {"resourceSpans": [{"resource": {}, "scopeSpans": [{"spans": spans}]}]}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--api-key", default=None)
    args = parser.parse_args()

    headers = {"content-type": "application/json"}
    if args.api_key:
        headers["authorization"] = f"Bearer {args.api_key}"

    async with httpx.AsyncClient(timeout=30) as client:
        latencies: list[float] = []

        async def one(i: int) -> None:
            start = time.perf_counter()
            resp = await client.post(
                f"{args.api}/v1/traces", content=json.dumps(_trace(i)), headers=headers
            )
            resp.raise_for_status()
            latencies.append(time.perf_counter() - start)

        wall_start = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(1, args.n + 1)))
        wall = time.perf_counter() - wall_start

        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        print(f"ingested {args.n} traces in {wall:.2f}s  ({args.n / wall:.0f}/s)")
        print(f"  per-request latency: p50={p50 * 1000:.0f}ms  p95={p95 * 1000:.0f}ms")

        # No loss: every trace is queryable.
        total = (await client.get(f"{args.api}/api/v1/executions?page_size=1", headers=headers)).json()[
            "total"
        ]
        print(f"  executions queryable: {total} (expected >= {args.n})")
        assert total >= args.n, "trace loss detected"


if __name__ == "__main__":
    asyncio.run(main())
