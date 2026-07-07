# Backend — `backend/`

The **`langops-api`** FastAPI service. It ingests OpenTelemetry telemetry
(OTLP), maps it to a domain model, persists to PostgreSQL, and exposes the query
REST API + live SSE that the dashboard consumes.

> Design reference: [architecture.md §3–4](architecture.md#3-backend-architecture-langops-api).
> Schema reference: [database.md](database.md).

---

## Layering (DDD)

Dependencies point inward; the domain imports nothing framework-y. Enforced in
CI by **import-linter** contracts in `pyproject.toml`.

```
presentation  →  application  →  domain  ←  infrastructure
```

```
backend/src/langops_api/
├── main.py                 # app factory, lifespan, error handlers, router mounting
├── composition.py          # DI composition root (the only place the graph is wired)
├── presentation/           # ── HTTP only ──
│   ├── api/v1/              #   query routers: executions, nodes, graphs, costs,
│   │                        #   metrics, health
│   ├── ingest/              #   OTLP receiver: POST /v1/traces
│   ├── events/              #   SSE endpoint: GET /api/v1/events
│   └── schemas/             #   Pydantic request/response models (wire format only)
├── application/            # ── use cases ──
│   ├── services/            #   IngestTelemetry, queries, reports, retention
│   ├── mappers/             #   OTLP spans → domain entities (+ semconv constants)
│   └── dto/                 #   inter-layer data carriers
├── domain/                 # ── pure, no frameworks ──
│   ├── entities/            #   Execution, NodeExecution, LlmCall, ToolCall, …
│   ├── value_objects/       #   TokenUsage, Cost, ExecutionStatus, StateDiff, …
│   ├── repositories/        #   repository Protocols (interfaces)
│   ├── services/            #   CostCalculator, StateDiffer (pure logic)
│   └── errors.py            #   LangOpsError hierarchy
└── infrastructure/         # ── implements domain interfaces ──
    ├── db/                  #   SQLAlchemy models, Postgres repos, async session
    ├── pricing/             #   JSON pricing catalog (see below)
    ├── cache/               #   Redis event publisher
    ├── otlp/                #   OTLP protobuf/JSON parsing
    ├── logging_config.py    #   structlog JSON logging + correlation
    └── settings.py          #   pydantic-settings (env-driven)
```

Three separate model families on purpose — **domain entities** (business
meaning), **ORM models** (persistence), **API schemas** (wire) — mapped
explicitly, so schema migrations, API versioning, and domain refactors stay
independent.

---

## Ingestion

`POST /v1/traces` accepts OTLP over HTTP in **protobuf** (what the Collector
sends) and **JSON**. `IngestTelemetryService` groups spans by trace, maps them
to domain entities via the [semantic conventions](semantic-conventions.md), and
persists **idempotently**:

- keyed by OTel `trace_id` / `span_id` (upsert on conflict) — redelivery is
  harmless;
- **order-independent** — a child span arriving before its execution root
  lazily creates the row; the root enriches it later;
- rollups (tokens, cost) are **recomputed** from child rows, never incremented.

Malformed payloads → **400**; oversized payloads → **413**; internal errors →
**500** with a generic body (never a stack trace).

---

## Query API

All under `/api/v1` (OpenAPI docs at `/docs`):

```
GET  /executions                     list + filters (status/graph/thread/time) + pagination
GET  /executions/compare?a=&b=       side-by-side comparison + final-state diff
GET  /executions/{id}                detail + node summaries
GET  /executions/{id}/timeline       ordered spans for the waterfall
GET  /executions/{id}/state          snapshots + diffs + context-growth series
GET  /executions/{id}/llm-calls      all LLM calls for the run
GET  /executions/{id}/tool-calls     all tool calls for the run
GET  /executions/{id}/logs
GET  /nodes/{id}                     node detail (llm calls, tools, state, logs)
GET  /graphs                         known graph topologies
GET  /graphs/{id}/topology           DAG (nodes + edges)
GET  /costs/summary                  by model / by day
GET  /metrics/overview               counts, failure rate, avg + p50/p95/p99 latency
GET  /events                         SSE stream (execution.updated)
GET  /health                         liveness/readiness (Postgres + Redis)
POST /v1/traces                      OTLP ingestion (OTLP-spec path, not under /api)
```

---

## Pricing

Cost is computed server-side (the SDK never sees prices). Prices live in a
**JSON catalog** under `infrastructure/pricing/` — one file per provider
(`openai.json`, `anthropic.json`, `google.json`, `groq.json`, `mistral.json`,
`ollama.json`, `custom.json`) loaded into memory at startup. See
[ADR-0002](adr/adr-0002-pricing-catalog.md).

- Editing a price = edit JSON + restart. No migration, no code change.
- Effective-dating (multiple entries per model), longest-prefix matching for
  dated variants, `reload()`, and `PRICING_CATALOG_DIR` for custom/local models.
- **Unknown models → `cost_status: "unknown"` with `cost = null`**, shown as
  "Unknown" in the dashboard — never a misleading `$0`.

---

## Cross-cutting

- **Logging** — structured JSON via structlog; ingestion binds
  `trace_id` / `execution_id` / `thread_id` / `checkpoint_id` so every log during
  a trace is correlated.
- **Migrations** — Alembic (`alembic upgrade head`), run on container start.
- **Retention** — `python -m langops_api.retention --days N` (single cascade
  delete; off by default).

---

## Develop & test

```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/ruff check src tests alembic
.venv/Scripts/mypy src
.venv/Scripts/lint-imports                # layering contracts
.venv/Scripts/python -m pytest            # 25 tests
```

Tests run the real ASGI app against in-memory SQLite (no server needed) and
cover ingestion (protobuf + JSON, duplicate, out-of-order), the query API,
pricing, comparison, metrics, and retention.
