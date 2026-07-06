# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LangOps is an open-source observability and evaluation platform for **LangGraph-based AI applications** — "Chrome DevTools for LangGraph." It instruments existing LangGraph projects (via `langops.instrument(graph)`) to capture graph executions, node transitions, LLM calls, state changes/diffs, token usage, costs, latency, tool invocations, and logs, surfaced through a web dashboard and REST API.

Context & state observation is a core feature: for every node, LangOps captures initial/final state, state diffs (added/modified/removed values), context growth (messages, memory, retrieved documents), thread and checkpoint information, and whether the execution started fresh or resumed from a previous checkpoint.

The MVP focuses on **observability, not orchestration**. Features like prompt versioning, execution replay, and evaluation are on the roadmap but out of scope for now.

## Current Status

The monorepo skeleton is scaffolded (packages, configs, CI, Docker/Compose, docs), but feature code is not yet implemented — most Python modules are docstring stubs. Two documents drive all work:

- `docs/architecture.md` — the implementation blueprint (services, monorepo layout, backend layering, database schema, SDK instrumentation strategy, dashboard architecture, Docker topology, conventions). Consult it before implementing anything.
- `tasks.md` — the phased build plan (Phase 1–8, mapped to the architecture milestones) with acceptance criteria. Work phases in order and keep checkbox statuses current.

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
