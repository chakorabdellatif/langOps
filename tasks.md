# LangOps — Build Plan

Production-ready implementation plan, phased to match the milestones in
[docs/architecture.md §8](docs/architecture.md). Each phase ends in a
demonstrable state with explicit acceptance criteria; testing is part of
every phase, not deferred. Work top-to-bottom; within a phase, tasks are
ordered by dependency.

Conventions for this file: `[ ]` todo · `[x]` done. Update statuses as work
lands; keep acceptance criteria checked against reality, not intention.

---

## Phase 0 — Blueprint & scaffold ✅

- [x] Architecture Design Document (`docs/architecture.md`)
- [x] Monorepo skeleton per §2 (sdk/, backend/, dashboard/, collector/, docker/, examples/, docs/)
- [x] `docker-compose.yml` (§7), `collector/otel-collector-config.yaml`, Dockerfiles
- [x] `Makefile`, `.env.example`, `.pre-commit-config.yaml`

> **Scope decision:** LangOps is a local-dev tool — no hosted CI. Quality
> gates (`make lint`, `make test`, pre-commit) run locally; GitHub Actions
> workflows were removed from the plan.
- [x] `docs/semantic-conventions.md` v0.1.0 draft (the SDK↔backend contract)
- [x] SDK package skeleton: `pyproject.toml`, public surface (`instrument`, `LangOpsConfig`), `semconv.py` constants
- [x] Backend package skeleton: `pyproject.toml` with import-linter layer contracts, app factory, `/api/v1/health`, settings
- [x] Dashboard skeleton: Next.js app (standalone output), typed fetch wrapper, query-key factory, feature-module layout
- [x] `docs/adr/adr-0001-otel-as-wire-format.md`

## Phase 1 — Toolchain green (M1)

Goal: a fresh clone passes `make lint && make test` locally for all three
packages.

- [ ] Create and verify local dev environments (Python 3.12 venvs for sdk/ and backend/, `npm install` for dashboard/)
- [ ] Run `next build` once and commit any missing scaffolding it requires
- [ ] Verify `ruff`, `mypy`, and `lint-imports` pass on the skeletons; keep configs pragmatic (no strictness theater)
- [ ] Install pre-commit hooks; verify each hook fires on a sample change
- [ ] Choose and add `LICENSE` (Apache-2.0 is declared in the pyprojects)
- [ ] Review `docs/semantic-conventions.md` draft against real LangGraph/LangChain callback payloads; adjust before backend/SDK build

**Accept when:** fresh clone → `make lint && make test` green locally for sdk, backend, dashboard.

## Phase 2 — Backend foundation (M2)

Goal: posting a fixture OTLP payload to `/v1/traces` produces correct rows
in every table and correct query-API responses.

### 2.1 Domain layer (pure, no I/O)
- [x] Entities: `Project`, `Graph`, `Execution`, `NodeExecution`, `LlmCall`, `ToolCall`, `StateSnapshot`, `LogRecord`, `ModelPricing` (dataclasses)
- [x] Value objects: `TokenUsage`, `ExecutionStatus`, `StateDiff`, `CheckpointRef` (Cost = `Decimal`; `TimeRange` deferred until a query needs it)
- [x] Domain services: `CostCalculator` (pricing as data in), `StateDiffer` — with unit tests (`ExecutionAggregator` folded into repo rollups; add if aggregation grows)
- [x] Repository Protocols (async, intent-revealing methods): Execution, NodeExecution, LlmCall, ToolCall, StateSnapshot, Log, Graph, Project, Pricing

### 2.2 Persistence
- [x] Alembic `env.py` (async, DATABASE_URL from env) + initial migration: full §4 schema (all 9 tables, indexes, FKs, cascades)
- [x] `model_pricing` seed (current OpenAI/Anthropic prices, `effective_from` history model) — canonical list in `infrastructure/db/pricing_seed.py`, used by both migration and dev/test path. **Interim only** — replaced by a JSON catalog in Phase 7 (ADR-0002); `$0`-for-unknown is a known gap fixed there.
- [x] SQLAlchemy ORM models (separate from domain entities, portable JSONB/JSON) + entity↔row mappers
- [x] Postgres repository implementations (upsert on OTel natural keys)
- [x] Default project auto-created lazily on first ingest/query
- [ ] Integration tests via testcontainers against real Postgres (deferred to Phase 8; API suite runs on SQLite for now)

### 2.3 Ingestion
- [x] `infrastructure/otlp/`: OTLP/HTTP parsing (protobuf `application/x-protobuf` + JSON), malformed input → 400 never 500
- [x] `application/mappers/otlp_mapper.py`: spans → domain entities via semconv constants (mirrored from `docs/semantic-conventions.md`)
- [x] `IngestTelemetryService`: group by trace, lazy execution creation from child spans, upsert idempotency (span_id/trace_id natural keys), rollup recomputation (never increments), cost computation, `execution.updated` publish to Redis (best-effort)
- [x] `POST /v1/traces` router; hand-built OTLP/JSON fixture + ingestion tests: happy path, duplicate delivery, out-of-order (child before root), malformed → 400

### 2.4 Query API (first slice)
- [x] Composition root (`composition.py`): settings → engine → repos → domain services → app services → `Depends` providers; lifespan owns engine/Redis
- [x] `ListExecutionsService` + `GET /api/v1/executions` (filters: status/graph/thread/time; pagination)
- [x] `GetExecutionDetailService` + `GET /api/v1/executions/{id}`, `/timeline`, `/logs`
- [x] `GetNodeDetailService` + `GET /api/v1/nodes/{id}`
- [x] Error contract: `LangOpsError` hierarchy, exception handlers → `{code, message, detail}` (404/422/500)
- [x] Health endpoint gains real readiness checks (Postgres ping, Redis ping)
- [ ] Structured logging (structlog, JSON, execution_id/trace_id correlation) — stdlib logging in place; structlog deferred

**Accept when:** fixture OTLP → correct rows in every table + correct API responses; import-linter contracts hold. ✅ (real-Postgres integration + structlog deferred as noted)

## Phase 3 — SDK instrumentation (M3)

Goal: `instrument(graph)` on a real LangGraph app emits spans matching the
conventions doc exactly, and can never break the host app.

- [x] `export/tracer.py`: dedicated TracerProvider (never the global one), resource attrs, OTLP exporter (default localhost:4317), sampling ratio
- [x] `export/processors.py`: BatchSpanProcessor config (payload-limit enforced at capture time, `langops.truncated` marker)
- [x] `capture/state.py`: safe serialization (fallback repr, depth limits, size caps)
- [x] `capture/diff.py`: structural diff {added, modified, removed} — same semantics as backend `StateDiffer`
- [x] `capture/redaction.py`: user hook applied before export (fails closed on hook error)
- [x] `instrumentation/graph.py`: wrap invoke/ainvoke/stream/astream; root span; input/output events; thread/checkpoint extraction; topology capture + hash; fresh-vs-resumed detection; handler injection; re-entrancy guard (invoke→stream); idempotent
- [x] `instrumentation/callbacks.py`: node spans (sequence from `graph:step` tag, retries per node/step), LLM spans (gen_ai.* attrs, usage_metadata tokens, message/params/response events), tool spans; run_id→span-context parent wiring
- [x] `instrumentation/checkpointer.py`: `BaseCheckpointSaver` proxy (composition); feeds authoritative checkpoint lineage into the execution span on `put()`/`aput()` (richer per-put snapshot events → Phase 6)
- [x] Failure policy: every capture path wrapped; one WARNING per failure class; fault-injection test proves a raising redaction hook never reaches the host graph
- [x] Span tests against an in-memory exporter, validated against `docs/semantic-conventions.md` (kinds, sequence, parenting, correlation, payload events)
- [x] `examples/simple-agent/main.py`: 2-node graph, one LLM call, one tool call, instrumented (runs with no API key via a fake chat model)

**Accept when:** span tests pass; fault-injection test passes; the example runs cleanly with and without a reachable collector. ✅

## Phase 4 — Collector & end-to-end pipeline (M4)

Goal: `docker compose up` + running the example on the host = execution
queryable via REST within seconds.

- [x] Collector config verified against the real API ingest path: `otlphttp` → `http://api:8000/v1/traces`, protobuf content-type, retry + sending-queue for kill/restart resilience
- [x] **Real OTLP/protobuf ingest test** (`tests/api/test_ingest_protobuf.py`) — the wire format the Collector actually sends, proven queryable end-to-end through the API (Phase 2 only covered JSON)
- [x] Backend Dockerfile fixed (build ran `pip install` before `src/` was copied → hatchling failure) — migrations run on start via `alembic upgrade head`
- [x] API healthcheck in compose; Collector + dashboard gated on `api: service_healthy`
- [x] Quickstart in the root README (compose up → pip install sdk → run example → dashboard) + `make e2e`
- [x] Acceptance script `scripts/e2e-smoke.sh`: compose up → run example → assert queryable → kill API mid-run → restart → assert Collector replayed (no loss)
- [ ] **Run `make e2e` on a Docker host** — needs the Docker daemon (unavailable in this dev env); the script + configs are ready. This is the one remaining M4 gate.

**Accept when:** `make e2e` passes repeatably on a machine with Docker Desktop running. All code/config is in place and unit-verified; the live compose run is the user's to execute.

## Phase 5 — Dashboard core (M5)

Goal: watch an execution appear live, then inspect every node and LLM call
in the browser.

- [ ] App shell: sidebar + topbar layout, TanStack Query provider, theme
- [ ] shadcn/ui setup; shared data components: `DataTable`, `JsonViewer`, `StatusBadge`, `DurationLabel`, `TokenBadge`, `CostLabel`, `EmptyState`
- [ ] `npm run generate:api` wired to backend OpenAPI; generated types adopted in `lib/api` (no hand-written telemetry types)
- [ ] SSE: backend `GET /api/v1/events` (Redis pub/sub bridge) + `lib/api/sse.ts` + cache-invalidation hook
- [ ] Executions feature: list page (filters, pagination, URL-synced via Zustand filters store, live updates)
- [ ] Execution detail: header (status, duration, tokens, cost, thread/checkpoint, fresh-vs-resumed) + tab navigation
- [ ] Graph tab: React Flow DAG (dagre/elk layout) from `GET /graphs/{id}/topology`, node status overlay, duration/cost badges, click → node inspector
- [ ] Timeline tab: Gantt-style span waterfall from `/executions/{id}/timeline`
- [ ] LLM calls feature: request/response inspector, message-thread rendering
- [ ] Logs tab: log table + stack-trace viewer (`SearchLogsService` + endpoint if not yet built)
- [ ] Backend: `GetGraphTopologyService` + `/graphs` endpoints (prerequisite for the Graph tab)

**Accept when:** run the demo app → execution appears live → every node and LLM call inspectable in the browser. ✅ (built: app shell, SSE live updates, executions list/detail, React Flow graph with status overlay, timeline, LLM inspector, logs; `tsc` + `next build` clean, pages render 200. API types are hand-written mirrors — `npm run generate:api` remains the production path.)

## Phase 6 — State viewer & context observation (M6)

Goal: step through state node-by-node and see exactly what each node changed.

- [ ] Backend `GetStateEvolutionService` + `GET /api/v1/executions/{id}/state` (ordered snapshots, diffs, context-growth series)
- [ ] Server-side diff recomputation/validation (`StateDiffer`) so the dashboard never depends on SDK version
- [ ] State tab: snapshot tree viewer, added/modified/removed diff visualization (`DiffViewer` shared component)
- [ ] Context-growth chart: size_bytes + message_count over node sequence
- [ ] Execution header: thread/checkpoint metadata, resumed-run link to parent checkpoint
- [ ] `examples/multi-agent-rag`: multiple agents, tools, retrieval, checkpointer, retries, a resumed run — the acceptance fixture

**Accept when:** for multi-agent-rag, a developer can step through state node-by-node, see per-node changes, and see a resumed run linked to its parent checkpoint. ✅ backend (`GetStateEvolutionService`, `/executions/{id}/state`, server-recomputed diffs) + dashboard State tab (per-node diff view + context-growth chart) + resumed/checkpoint header. ⬜ Remaining: the `examples/multi-agent-rag` fixture app itself.

## Phase 7 — Cost & token tracking (M7)

Goal: costs shown anywhere in the product match hand-computed values.

> **Pricing design (ADR-0002):** JSON catalog, not a DB table. Prices live in
> per-provider files under `infrastructure/pricing/` (`openai.json`,
> `anthropic.json`, `ollama.json`, …), loaded into an in-memory pricing service
> at startup — editing a price is a JSON edit + restart, no migration. The
> Phase 2 interim (DB `model_pricing` table + Python seed, `$0` for unknown
> models) is replaced here.

- [ ] JSON catalog files per provider + loader; support local models (ollama `0`/`0`) and an optional user custom catalog
- [ ] Replace `PricingRepository` DB lookup with the catalog service; drop the `model_pricing` table, its seed migration, and `infrastructure/db/pricing_seed.py`
- [ ] **Unknown models → `cost_status: "unknown"`, never `$0`** (nullable cost); dashboard renders "Unknown"
- [ ] Split cost into `input_cost` / `output_cost` / `total_cost` on `llm_calls` (schema change)
- [ ] `CostCalculator` wired through ingestion for every LLM call; execution/node rollups verified idempotent
- [ ] `GetCostReportService` + `GET /api/v1/costs/summary` (by model / graph / day), Redis-cached with short TTL
- [ ] `GetMetricsService` + `GET /api/v1/metrics/overview` (latency percentiles, failure rate, throughput), Redis-cached
- [ ] Dashboard Costs screen (Recharts breakdowns) and Metrics screen
- [ ] Overview page: recent executions, failure rate, cost today, latency sparkline
- [ ] Fixture-based verification: hand-computed costs == API == dashboard

**Accept when:** cost figures per call/node/execution/model/day match hand-computed values from the JSON catalog for fixture data; unknown models show "Unknown", not `$0`. ✅ (JSON catalog + cost split + `cost_status`; `/costs/summary`, `/metrics/overview`; dashboard Costs + Metrics + Overview screens; verified in `test_reports.py`. Redis caching of aggregates deferred — recompute is cheap at MVP volume.)

## Phase 8 — Hardening & 0.1.0 release (M8)

Goal: quickstart works on a clean machine in under 10 minutes; the release
is tagged.

- [x] Retention job: delete executions older than N days (single cascade delete per run), off by default — `python -m langops_api.retention --days N` / `make retention`; cascade verified in `test_retention.py`
- [x] Error-path coverage: ingestion edge cases (duplicate, out-of-order, malformed → 400), API error contract (404/400), SDK degradation (fault-injection) — covered across the suites
- [x] Docs: README quickstart, `docs/contributing.md`, ADRs, semantic-conventions; OpenAPI served at `/docs`
- [ ] `make e2e` on a Docker host (the M4 gate) — script ready, needs a daemon
- [ ] Load sanity: 100 concurrent executions ingested without loss; document limits
- [ ] Coverage gate ≥ 90% on backend domain + application layers
- [x] Version bump to 0.1.0 (sdk + backend) and `CHANGELOG.md`
- [ ] Publish `langops` 0.1.0 to PyPI + tag the repo (release step for the user)

**Accept when:** clean-machine quickstart < 10 minutes; `make e2e` passes locally; all §9 conventions are enforced by tooling. (Core hardening done; live E2E, load test, and PyPI/tag remain — infra/release steps for the user.)

---

## Pre-0.1.0 roadmap follow-ups (post-milestone polish)

- [x] **M1** JSON pricing catalog: currency + effective_from arrays, groq/mistral/custom, prefix matching, `reload()`; unknown → `cost_status`, never $0
- [x] **M2** Dashboard polish: richer Overview (tokens/cost/avg latency/success rate), Execution Explorer tabs (Overview/Graph/Timeline/State/LLM Calls/Tool Calls/Logs), graph node badges, JSON viewer copy+collapse, colorized diffs
- [x] **M3** Hardening: structlog JSON logging with correlation IDs, payload size limit (413), no stack-trace leakage, graceful SDK degradation
- [x] **Execution Comparison** (differentiator): `/executions/compare` + dashboard side-by-side (metric deltas, graph paths, final-state diff)
- [x] **M5** README (features, comparison, contributing, license, badges) + `CHANGELOG.md` + version 0.1.0
- [ ] **M4** Live `docker compose up` E2E + 100-execution load test with documented latency/throughput — needs a Docker daemon (`make e2e` ready)

---

## Post-MVP backlog (architecture §10 — do not start before 0.1.0)

Prompt versioning · agent evaluation · execution replay / time travel ·
human-in-the-loop · multi-project · auth/users · Kubernetes deployment ·
partitioned/scale-out storage. Each maps to an existing seam; keep it that
way — new features must be additive.
