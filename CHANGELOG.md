# Changelog

All notable changes to LangOps are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-07-07

First public release — observability for LangGraph applications, end to end.

### SDK (`langops`)

- `instrument(graph)` wraps a compiled LangGraph in place and emits OpenTelemetry
  spans for executions, nodes, LLM calls, and tool calls.
- State capture with safe serialization (depth/size caps, truncation marker),
  structural diffing, and a fail-closed redaction hook.
- Dedicated `TracerProvider` (never the global one); batched OTLP export.
- Fault isolation: telemetry errors never propagate to the host graph.

### Backend (`langops-api`)

- OTLP/HTTP ingestion (`POST /v1/traces`, protobuf + JSON) — idempotent and
  order-independent (lazy execution creation, upsert on OTel natural keys).
- Query REST API: executions (list/detail/timeline/state/logs/llm-calls/
  tool-calls), nodes, graphs + topology, costs, metrics, and an **execution
  comparison** endpoint.
- Live updates over Server-Sent Events (`/events`).
- JSON pricing catalog (per-provider files, effective-dating, prefix matching,
  `reload()`); unknown models report `cost_status: "unknown"`, never `$0`.
- Structured JSON logging (structlog) with trace/execution/thread/checkpoint
  correlation; payload size limits; no stack traces exposed over REST.
- Retention job (`python -m langops_api.retention --days N`).
- Layered architecture enforced by import-linter; Alembic-managed schema.

### Dashboard (`langops-dashboard`)

- Overview, executions list, and an Execution Explorer with Overview, Graph
  (React Flow DAG with status/duration/retry/error badges), Timeline, State
  (per-node diff + context-growth chart), LLM Calls, Tool Calls, and Logs tabs.
- **Execution comparison** — side-by-side metric deltas, graph paths, and a
  final-state diff.
- Costs and Metrics screens (Recharts); live updates via SSE.

### Infrastructure

- Docker Compose stack (api, dashboard, postgres, redis, otel-collector) with
  health checks and Collector retry/queue for delivery resilience.
- `make e2e` acceptance script (compose up → run example → verify → kill/restart
  the API → verify no data loss).

[0.1.0]: https://github.com/chakorabdellatif/langOps/releases/tag/v0.1.0
