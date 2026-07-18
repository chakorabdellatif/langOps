# LangOps

> **A lightweight observability and evaluation platform for LangGraph applications.**

![status: v0.1.0](https://img.shields.io/badge/status-v0.1.0-0ea5e9) ![license: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue) ![stack: FastAPI · Next.js · OTel](https://img.shields.io/badge/stack-FastAPI%20·%20Next.js%20·%20OpenTelemetry-111)

LangOps is an open-source developer platform that provides deep observability, debugging, and evaluation capabilities for **LangGraph-based AI applications**.

Instead of replacing LangGraph, LangOps integrates seamlessly into existing projects to help developers understand what happens inside their agent workflows. It automatically captures graph executions, node transitions, LLM calls, state changes, token usage, costs, latency, tool invocations, and execution logs, all accessible through a modern web dashboard.

The goal of LangOps is to become the equivalent of **Chrome DevTools for LangGraph**, allowing developers to monitor, debug, replay, and optimize complex multi-agent systems.

---
⚠️ LangOps is currently in active development,APIs and features may change as the project evolves. Feedback and contributions are welcome.



# Documentation

Full docs live in [`docs/`](docs/README.md):

- **[Setup & Usage](docs/setup.md)** — run the stack and instrument your own app
- Per-component guides: **[SDK](docs/sdk.md)** · **[Backend](docs/backend.md)** · **[Dashboard](docs/dashboard.md)** · **[Collector](docs/collector.md)** · **[Examples](docs/examples.md)**
- Reference: **[Architecture](docs/architecture.md)** · **[Semantic Conventions](docs/semantic-conventions.md)** · **[Database](docs/database.md)** · **[ADRs](docs/adr/)**

---

# Getting Started

## Clone the repository

```bash
git clone https://github.com/yourusername/langops.git

cd langops
```

---

## Start all services

```bash
docker compose up --build
```

---

## Services

| Service | URL |
|----------|-----|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

# Instrumenting a LangGraph Application

Install the SDK (from source during development):

```bash
pip install -e ./sdk        # published as `langops` on PyPI at 0.1.0
```

Wrap your compiled graph — one line, no other changes:

```python
from langops import instrument

graph = instrument(graph)   # wraps invoke/ainvoke/stream/astream in place
graph.invoke(..., config={"configurable": {"thread_id": "abc"}})
```

Spans export via OpenTelemetry to the Collector (default `http://localhost:4317`;
override with `LangOpsConfig(endpoint=...)`). Every execution — node transitions,
LLM calls, tokens, state diffs — is captured and appears in the dashboard.
Instrumentation is fault-isolated: if telemetry ever errors, your graph still
runs unaffected.

---

# Try it end-to-end

With the stack running, run the bundled example on the host and watch it appear:

```bash
docker compose up --build            # terminal 1: the full stack
pip install -e ./sdk                 # terminal 2
python examples/simple-agent/main.py # emits an execution to the Collector
open http://localhost:3000           # the run shows up in the dashboard
```

Or run the automated acceptance check (builds the stack, runs the example,
verifies the execution is queryable, and tests Collector-retry resilience by
killing the API mid-run):

```bash
make e2e        # bash scripts/e2e-smoke.sh
```

---

# Design Principles

LangOps follows four core principles:

- **Simple** — minimal setup with sensible defaults.
- **Lightweight** — low runtime overhead and easy integration.
- **Developer-first** — built for debugging and understanding agent workflows.
- **Framework-aware** — deeply integrated with LangGraph instead of providing generic abstractions.

---

# Vision

LangOps aims to become the observability layer for LangGraph applications by providing developers with the tools needed to inspect, monitor, debug, and optimize AI agent workflows from local development to production.

---

# Contributing

Contributions are welcome. Start with the [Architecture Design Document](docs/architecture.md)
(the implementation blueprint) and [`docs/contributing.md`](docs/contributing.md).

```bash
cp .env.example .env
make lint      # ruff + mypy + import-linter (backend) + eslint/tsc (dashboard)
make test      # unit + API tests for sdk, backend, dashboard
make e2e       # full Docker pipeline smoke test (needs Docker running)
```

Ground rules: keep the backend layering (`presentation → application → domain ← infrastructure`,
enforced by import-linter); never invent an OTel attribute without adding it to
[`docs/semantic-conventions.md`](docs/semantic-conventions.md) first; significant
decisions get an ADR in [`docs/adr/`](docs/adr/); Conventional Commits.

# License

[Apache-2.0](LICENSE).
