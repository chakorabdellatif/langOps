# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LangOps is an open-source observability and evaluation platform for **LangGraph-based AI applications** — "Chrome DevTools for LangGraph." It instruments existing LangGraph projects (via `langops.instrument(graph)`) to capture graph executions, node transitions, LLM calls, state changes/diffs, token usage, costs, latency, tool invocations, and logs, surfaced through a web dashboard and REST API.

Context & state observation is a core feature: for every node, LangOps captures initial/final state, state diffs (added/modified/removed values), context growth (messages, memory, retrieved documents), thread and checkpoint information, and whether the execution started fresh or resumed from a previous checkpoint.

The MVP focuses on **observability, not orchestration**. Features like prompt versioning, execution replay, and evaluation are on the roadmap but out of scope for now.

## Current Status

Phases 1–7 are implemented and Phase 8 is largely done; the product works end-to-end. Local-dev only (no hosted CI). Two documents drive all work:

- `docs/architecture.md` — the implementation blueprint (services, layering, schema, SDK strategy, dashboard, Docker, conventions). Consult before implementing.
- `tasks.md` — the phased build plan with acceptance criteria and current checkbox state. Keep it updated.

What exists and is tested:
- **backend/** — full FastAPI service: OTLP ingest (`POST /v1/traces`, protobuf + JSON, idempotent, out-of-order safe); query API (executions, nodes, graphs/topology, state evolution, costs, metrics, SSE `/events`); layered + import-linter enforced; Alembic schema; retention job (`python -m langops_api.retention --days N`). 19 tests.
- **sdk/** — `langops.instrument(graph)` emits OTel spans (execution/node/LLM/tool) per `docs/semantic-conventions.md`; fault-isolated. 15 tests.
- **dashboard/** — Next.js UI: overview, executions list/detail (React Flow graph, timeline, state diff + context-growth, LLM inspector, logs), costs (Recharts), metrics; SSE live updates. `next build` + `tsc` clean.
- **Pricing** is a JSON catalog (`backend/.../infrastructure/pricing/`, ADR-0002), not a DB table; unknown models → `cost_status: "unknown"`, never $0.

Verify with `make lint` / `make test` per package; `make e2e` runs the full Docker pipeline (needs a Docker daemon). Remaining: the multi-agent-rag example, live `make e2e` run, and the 0.1.0 PyPI release.

`docs/semantic-conventions.md` is the SDK↔backend contract (the `langops.*` / `gen_ai.*` OTel attribute namespace); it is mirrored in `sdk/src/langops/semconv.py` and must never drift. Backend layering (`presentation → application → domain ← infrastructure`) is enforced by import-linter contracts in `backend/pyproject.toml`.

## Architecture

Data flows in one direction through the pipeline:

```
LangGraph App → langops.instrument() → LangOps SDK → OpenTelemetry SDK
  → OTel Collector → FastAPI Backend → PostgreSQL (+ Redis)
  → REST API → Next.js Dashboard
```

Planned top-level layout:

- `sdk/` — Python instrumentation SDK (published as `langops` on pip); wraps LangGraph apps and emits telemetry via OpenTelemetry
- `backend/` — FastAPI server (Python 3.12, SQLAlchemy, Pydantic, AsyncIO); persists to PostgreSQL, uses Redis for cache/messaging, exposes the REST API
- `dashboard/` — Next.js frontend (TypeScript, Tailwind CSS, shadcn/ui, React Flow for graph visualization, Recharts for metrics)
- `collector/` — OpenTelemetry Collector configuration
- `docker/`, `docker-compose.yml` — containerization for all services

## Commands

Run the full stack (services: langops-api, langops-dashboard, postgres, redis, otel-collector):

```bash
docker compose up --build
```

Service URLs: Dashboard http://localhost:3000, API http://localhost:8000, API docs http://localhost:8000/docs, PostgreSQL localhost:5432, Redis localhost:6379.

## Design Principles

- **Simple** — minimal setup with sensible defaults
- **Lightweight** — low runtime overhead; integrates into existing projects rather than replacing LangGraph
- **Developer-first** — built for debugging and understanding agent workflows
- **Framework-aware** — deeply integrated with LangGraph, not generic abstractions
