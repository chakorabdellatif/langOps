# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LangOps is an open-source observability and evaluation platform for **LangGraph-based AI applications** — "Chrome DevTools for LangGraph." It instruments existing LangGraph projects (via `langops.instrument(graph)`) to capture graph executions, node transitions, LLM calls, state changes/diffs, token usage, costs, latency, tool invocations, and logs, surfaced through a web dashboard and REST API.

Context & state observation is a core feature: for every node, LangOps captures initial/final state, state diffs (added/modified/removed values), context growth (messages, memory, retrieved documents), thread and checkpoint information, and whether the execution started fresh or resumed from a previous checkpoint.

The MVP focuses on **observability, not orchestration**. Features like prompt versioning, execution replay, and evaluation are on the roadmap but out of scope for now.

## Current Status

No source code has been committed yet. The full Architecture Design Document lives at `docs/architecture.md` — it is the implementation blueprint (services, monorepo layout, backend layering, database schema, SDK instrumentation strategy, dashboard architecture, Docker topology, milestones, conventions). Consult it before implementing anything, and update this file as components are actually implemented.

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
