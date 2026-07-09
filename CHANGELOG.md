# Changelog

All notable changes to LangOps are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-07-09

First public release — an interactive debugging platform for LangGraph
applications. Everything is deterministic (no LLM calls, no recurring inference
cost) and the SDK↔backend wire contract is versioned
(`docs/semantic-conventions.md`, schema 0.2.x — attribute-schema versioning is
independent of the 0.1.0 package release).

### SDK (`langops`)

- `instrument(graph)` wraps a compiled LangGraph in place and emits OpenTelemetry
  spans for executions, nodes, LLM calls, and tool calls; fault-isolated
  (telemetry errors never reach the host graph); dedicated `TracerProvider`.
- State capture with safe serialization (depth/size caps, truncation marker),
  structural diffing, and a fail-closed redaction hook.
- **Node categories** — conditional-router detection from the graph topology;
  the backend infers llm/tool/utility from runtime spans.
- **Structured log capture** (opt-in `capture_logs`) — bridges stdlib `logging`
  onto the active node span, with a per-span cap + visible truncation marker.
- **Execution replay** — `langops.replay(...)` / `python -m langops replay`:
  exact, or with `--model` / `--temperature` / `--input` overrides.
- **Cached replay** (`--stub-llm` / `--stub-tool`) — serves recorded LLM/tool
  outputs, so replay is deterministic and costs **zero tokens**.
- Optional `api_key` → OTLP `Authorization: Bearer` header.

### Backend (`langops-api`)

- OTLP/HTTP ingestion (protobuf + JSON) — idempotent, order-independent.
- Per-node token/cost rollups (single batched UPDATE) + category, with
  `cost_status: "unknown"` (never `$0`) from a JSON pricing catalog (ADR-0002).
- **Deterministic comparison engine** — state / execution / performance / LLM
  changes + rule-based, threshold-driven insights.
- **Thread (conversation) view**, **per-node cost breakdown**, **global search**
  (incl. LLM-response text via a `pg_trgm` index), and **failure analytics**
  (group by exception type × node with a trend).
- Cached-replay cost exclusion; structured-log ingestion (source classification).
- **Optional single-tenant API-key auth** (`API_KEY`) and **retention** —
  periodic in-process delete + payload-only pruning that keeps rollups.
- Live updates over SSE; layered architecture enforced by import-linter;
  Alembic-managed schema (migrations 0001–0007).

### Dashboard (`langops-dashboard`)

- Execution Explorer: rich React Flow graph (per-node status/tokens/cost/retry
  badges, category, hover tooltip, click-through node inspector), Timeline,
  State, LLM/Tool Calls, and a searchable/filterable Logs tab.
- **Threads**, **Errors**, per-node **cost breakdown**, a **⌘K global search**
  palette, and the **comparison** and **replay** panels.
- Server-side proxy route so an API key never ships to the browser.

### Infrastructure

- Docker Compose stack (api, dashboard, postgres, redis, otel-collector) with
  health checks, Collector retry/queue, retention on by default.
- `make e2e` acceptance script; `scripts/loadtest.py` concurrency generator.

[0.1.0]: https://github.com/chakorabdellatif/langOps/releases/tag/v0.1.0
