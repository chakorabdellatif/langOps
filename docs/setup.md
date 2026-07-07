# Setup & Usage

How to run LangOps and instrument your own LangGraph application.

- [Requirements](#requirements)
- [Quick start (Docker)](#quick-start-docker)
- [Instrument your own LangGraph app](#instrument-your-own-langgraph-app)
- [SDK configuration](#sdk-configuration)
- [Environment variables](#environment-variables)
- [Local development (without Docker)](#local-development-without-docker)
- [Verifying the pipeline](#verifying-the-pipeline)
- [Troubleshooting](#troubleshooting)

---

## Requirements

| Tool | Version | Needed for |
|---|---|---|
| Docker + Docker Compose v2 | latest | running the full stack |
| Python | 3.12 | backend / SDK dev; instrumenting your app |
| Node.js | 20+ | dashboard dev |

The only thing your instrumented app needs at runtime is the `langops` SDK and a
reachable OTLP endpoint (the Collector, default `localhost:4317`).

---

## Quick start (Docker)

Bring up the whole platform — API, dashboard, Postgres, Redis, and the OTel
Collector — with one command:

```bash
cp .env.example .env          # every value has a working default
docker compose up --build
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs (OpenAPI) | http://localhost:8000/docs |
| OTLP ingest (gRPC / HTTP) | localhost:4317 / 4318 |

Your instrumented app runs on the **host** and sends telemetry to the Collector
at `localhost:4317`. Reset everything (including the database) with
`docker compose down -v`.

---

## Instrument your own LangGraph app

Install the SDK (published as `langops`; from source during development):

```bash
pip install -e ./sdk          # or: pip install langops
```

Wrap your compiled graph — one line, nothing else changes:

```python
from langgraph.graph import StateGraph
from langops import instrument

graph = build_my_graph().compile()
graph = instrument(graph)                 # wraps invoke/ainvoke/stream/astream

graph.invoke(
    {"messages": [...]},
    config={"configurable": {"thread_id": "session-1"}},   # thread → conversation view
)
```

Run your app while `docker compose up` is running, then open
http://localhost:3000 — the execution appears within seconds, with every node,
LLM call, tool call, state diff, token count, and cost.

**Guarantees:**

- **Zero behavior change** — `instrument()` returns the same graph object;
  invoke/stream signatures are unchanged.
- **Fault-isolated** — if telemetry ever errors, your graph still runs. The SDK
  logs one warning per failure class and drops the datum.
- **No pricing in the SDK** — it only observes (model, tokens, prompts). Cost is
  computed server-side from the pricing catalog.

---

## SDK configuration

Pass a `LangOpsConfig` for anything beyond the defaults:

```python
from langops import instrument, LangOpsConfig

graph = instrument(graph, LangOpsConfig(
    endpoint="http://localhost:4317",   # OTLP Collector endpoint
    service_name="my-agent",            # shows as the service in telemetry
    graph_name="research-agent",        # defaults to the LangGraph graph name
    project="default",                  # telemetry namespace (MVP: single project)
    max_payload_bytes=65_536,           # per-payload cap; larger ones are truncated
    redaction_hook=lambda payload: scrub(payload),  # runs before export; fail-closed
    sampling_ratio=1.0,                 # 0.0–1.0
))
```

| Field | Default | Purpose |
|---|---|---|
| `endpoint` | `http://localhost:4317` | where spans are exported (Collector) |
| `service_name` | `langgraph-app` | `service.name` resource attribute |
| `graph_name` | LangGraph graph name | groups executions of the same graph |
| `project` | `default` | telemetry namespace |
| `capture_state` / `capture_llm_payloads` / `capture_tool_payloads` | `True` | toggle payload capture |
| `max_payload_bytes` | `65536` | size cap; oversized payloads get a `truncated` marker |
| `redaction_hook` | `None` | scrub secrets before anything leaves the process |
| `sampling_ratio` | `1.0` | trace sampling |

---

## Environment variables

Copy `.env.example` → `.env`; every value has a working local default.

| Variable | Default | Used by |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://langops:langops@localhost:5432/langops` | backend |
| `REDIS_URL` | `redis://localhost:6379/0` | backend (cache + SSE pub/sub) |
| `CORS_ORIGINS` | `http://localhost:3000` | backend |
| `INGEST_MAX_PAYLOAD_BYTES` | `4194304` | backend ingest limit (→ HTTP 413) |
| `PRICING_CATALOG_DIR` | _unset_ | extra pricing JSON dir (custom models) |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | dashboard (baked at build time) |
| `LANGOPS_ENDPOINT` | `http://localhost:4317` | your instrumented app (via `LangOpsConfig`) |

---

## Local development (without Docker)

Run quality gates and tests per package. See each package's doc for detail:
[backend.md](backend.md), [sdk.md](sdk.md), [dashboard.md](dashboard.md).

```bash
# Backend (Python 3.12)
cd backend && python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest          # 25 tests
alembic upgrade head                    # apply schema to a running Postgres

# SDK
cd sdk && python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest          # 15 tests

# Dashboard (Node 20+)
cd dashboard && npm install
npm run dev                             # http://localhost:3000
```

Aggregate entry points from the repo root (see the [Makefile](../Makefile)):
`make up`, `make lint`, `make test`, `make e2e`, `make retention`.

---

## Verifying the pipeline

The bundled example runs with no API key (uses a fake chat model):

```bash
docker compose up -d
pip install -e ./sdk
python examples/simple-agent/main.py    # emits an execution to the Collector
open http://localhost:3000
```

Or the automated acceptance check — builds the stack, runs the example, verifies
the execution is queryable, and tests Collector-retry resilience by killing the
API mid-run:

```bash
make e2e                                # bash scripts/e2e-smoke.sh
```

Load test (against a running stack):

```bash
python scripts/load-test.py --count 100 --concurrency 20
```

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Execution never appears in the dashboard | Is the Collector reachable at `localhost:4317`? Check `docker compose logs otel-collector`. |
| Cost shows **"Unknown"** | The model isn't in the pricing catalog — add it (see [backend.md](backend.md#pricing) / `infrastructure/pricing/`). This is intended, never `$0`. |
| `413 request_too_large` on ingest | Payload exceeds `INGEST_MAX_PAYLOAD_BYTES`; raise it or lower the SDK's `max_payload_bytes`. |
| Graph runs but nothing exports, no crash | Working as designed — telemetry failures never break your app. Check app logs for a single `langops` warning. |
| `make e2e` fails to start | Docker Desktop / daemon must be running. |
