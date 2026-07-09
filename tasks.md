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

# Milestone v0.2 — Developer Experience

Goal: transform LangOps from an execution viewer into an **interactive
debugging platform** — understand, compare, and re-run LangGraph executions.
Everything in this milestone is **deterministic** (no LLM calls, no recurring
inference cost) and **additive** (no breaking semconv or API changes; old
SDKs keep working against the new backend and vice versa).

Ordering rationale: Phase 9 (graph inspection) is the highest-value UX win
and creates the per-node data (tokens/cost/category) that Phases 10 and 12
present; Phase 10 (comparison engine) is pure backend + presentation on top
of data that already exists; Phase 11 (logs) requires an SDK release, so its
SDK work ships together with Phase 12's SDK work in one `langops` 0.2.0.

> **Contract changes (semconv 0.1.0 → 0.2.0, all additive — no `!` commit):**
> - `langops.node.category` node-span attribute: `llm | tool | utility |
>   router | conditional | checkpoint | subgraph` (SDK best-effort; backend
>   infers a deterministic fallback when absent, so old SDKs still work)
> - Topology payload v2: `nodes` entries may be objects
>   `{id, category, metadata}` instead of bare strings; backend accepts both
> - `langops.log` span event: `{level, logger, message, source}` +
>   `langops.payload` for structured extras (source: `app | sdk | llm | tool`)
> - `langops.execution.replay_of` execution-span attribute (UUID of the
>   execution being replayed) + `langops.execution.overrides` event (JSON of
>   replay modifications, redacted/truncated like any payload)
> Update `docs/semantic-conventions.md` to 0.2.0 **first**, then mirror in
> `sdk/src/langops/semconv.py` and the backend mapper constants — same
> workflow as 0.1.0. Unknown attributes are already ignored by ingestion, so
> mixed SDK/backend versions stay safe.

## Phase 9 — Rich graph node inspection (M9) — highest priority

Goal: the graph becomes the primary debugging surface — per-node status,
duration, tokens, cost, retries at a glance; full inspector on click.

### 9.1 Data foundation (backend + SDK)
- [x] Migration (`0002_node_rollups`): `node_executions` gains
      `input_tokens`, `output_tokens`, `total_cost` (nullable), `cost_status`,
      and `category` (nullable); old rows render "utility"/"—" via API fallback
- [x] Ingestion: per-node rollups recomputed idempotently from child
      `llm_calls` across the whole execution (`_recompute_node_rollups`, same
      never-increment pattern as execution rollups); `cost_status` aggregates
      per node (any unknown child → `unknown`, never $0 — ADR-0002)
- [x] Deterministic category inference (`domain/services/node_categorizer.py`,
      pure + unit-tested): LLM child → `llm`; tool child (no LLM) → `tool`;
      else `utility`; structural SDK categories always win
- [x] SDK: `_topology` captures conditional-edge metadata from
      `graph.get_graph()`, emits topology-v2 node/edge objects, and stamps
      `langops.node.category` on conditional routers via the callback handler
- [x] Extended `NodeView` DTO + `NodeSummaryResponse` (and dashboard types):
      `category`, tokens, `total_cost`, `cost_status`, `models`, `tool_names`,
      `state_changes` — enriched in `GetExecutionDetailService` via 3 batch
      queries per execution, **no N+1 on hover**
- [x] Tests: rollup idempotency, out-of-order LLM rollup, category-inference
      matrix (API + pure unit), state-change surfacing

### 9.2 Dashboard — graph as debugging surface
- [x] Custom React Flow node (`GraphNode`): status color, duration, tokens,
      cost, retry badge (`↻n`), category glyph + label
- [x] Hover tooltip (CSS `group-hover`, data from `ExecutionDetail.nodes` —
      no fetch on hover): status, duration, tokens, cost, model(s), category,
      tools, state-change summary; non-LLM → "—"; failed → exception + retries
- [x] Click → `NodeInspector` drawer fed by existing `GET /api/v1/nodes/{id}`
- [x] Edge styling: conditional edges dashed + labeled from topology-v2
- [x] Live updates reuse existing SSE cache invalidation (unchanged)
- [x] `tsc` + `next lint` clean; topology normaliser accepts v1 (bare
      strings/tuples) so 0.1.0-SDK executions still render

**Accept when:** every node shows status, duration, tokens, cost, and category
on the graph; hover shows the full tooltip without a network request; click
opens the inspector; a failed node shows exception + retry info; old-SDK
executions render without errors. ✅ (unit/API/tsc/lint verified; live
browser render verified in the visit-city run at the end)

## Phase 10 — Deterministic comparison engine (M10)

Goal: comparing two executions answers "what changed and did it get better
or worse" — state, structure, performance, and plain-language insights.
Entirely rule-based; **never an LLM**. (Merges wishlist items 2 and 4 — the
"better state diff" sections *are* the richer comparison.)

- [x] Domain service `ExecutionComparator` (pure, no I/O — unit-tested like
      `StateDiffer`), composing four sections: **State** (reuse `StateDiffer`),
      **Execution** (nodes added/removed, order change, retries add/remove,
      topology change), **Performance** (duration/cost/tokens/context-size +
      per-node latency as `{a, b, delta, delta_pct, comparable}`; unknown cost
      → incomparable, never 0), **LLM** (model/temperature/prompt-size/
      response-length/tool-call-count)
- [x] Rule-based insight generator: threshold-driven (`Thresholds` constants),
      each insight cites its metric + severity (info/good/bad); deterministic
      and snapshot-tested
- [x] Extended `CompareExecutionsService` + `/executions/compare` additively
      (kept `a`/`b`/`final_state_diff`; added `result` with the four sections
      + `insights`)
- [x] Dashboard compare page: Insights / Performance / Execution / LLM cards
      with ▲/▼ delta chips (lower latency/cost = green), per-node latency table
- [x] "Compare with…" entry point from execution detail → `/compare?a=<id>`
      (Suspense-wrapped `useSearchParams`)
- [x] Tests: comparator unit matrix (identical → empty; each change class),
      insight snapshot, API contract (model swap + token increase),
      unknown-cost incomparability

**Accept when:** comparing two fixture runs with a known injected difference
surfaces exactly the expected execution changes, performance deltas, and
insights — reproducibly, no LLM. ✅ (7 unit + 1 API test; `next build` clean)

## Phase 11 — Logs experience (M11)

Goal: logs become a first-class debugging channel — today only exception
events reach the `logs` table (always level `error`).

- [x] SDK: opt-in `LangOpsConfig(capture_logs=True)` installs a
      `LangOpsLogHandler` on the root logger that emits `langops.log` events
      onto the active node span (via a `node_spans` stack on `RunContext`),
      falling back to the execution root; source `sdk` for `langops.*`
      loggers else `app`; redaction + payload cap reused; fault-isolated
- [x] Ingestion: `_map_structured_logs` maps `langops.log` events →
      `LogRecord`; migration `0003_log_source` adds `logs.source`/`logger`;
      exception rows classified `exception`
- [x] `SearchLogsService` + `GET /api/v1/logs`: filters `execution_id`
      (optional), `node_execution_id`, `level`, `source`, `q` (ILIKE), time
      range; limit/offset pagination; `ix_logs_source` index added
- [x] Dashboard Logs tab rebuilt: search box, level chips (All/Errors/
      Warnings), source chips (App/SDK/LLM/Tool/Exception), timestamp +
      level color + source + message + stack trace, total count
- [x] Log-count badges: error/warning totals on the execution header
- [x] Tests: SDK node-attribution capture, log-event ingestion + node
      attribution, search filters (level/source/text), exception-source
      classification

**Accept when:** an app using stdlib `logging` shows its log lines in the
dashboard attributed to the right node, filterable by level/source and
searchable by text; capture off by default costs nothing. ✅ (SDK 17 +
backend 45 tests; verified end-to-end in the visit-city run)

## Phase 12 — Execution replay, phases R1–R2 (M12)

Goal: re-run a captured execution from the dashboard's data — exactly (R1)
or with modifications (R2). Replay runs **in the user's environment via the
SDK** (the backend never executes user code); the platform's job is
supplying the recorded inputs/config and linking lineage. R3 (from
checkpoint) and R4 (from arbitrary node) stay in the post-v0.2 backlog —
per the design decision, replay ships *with* modifications or not at all.

### R1 — exact replay
- [x] SDK `langops.replay(graph, execution_id, api_url=...)` (impl in
      `_replay.py` to dodge the module/function name clash) + CLI
      (`python -m langops replay <id> --app module:graph`): fetches recorded
      input/config via stdlib urllib (no new dep), fresh thread unless
      `--same-thread`, re-invokes the local instrumented graph
- [x] Replay lineage: root span carries `langops.execution.replay_of` (via a
      `replay_context` set in `_replay`); migration `0004_replay_lineage`
      adds `executions.replay_of_execution_id` (+ `replay_overrides`, indexed);
      summary/detail responses expose it, detail lists `replays`
- [x] Dashboard `ReplayPanel`: copyable CLI command (UI states the dashboard
      can't run user code), lineage links (original ⇄ replays), "Compare with
      original" (reuses Phase 10)
- [x] Guard: truncated recorded input (`langops.truncated`) fails fast with
      `ReplayError` unless an explicit `--input` is supplied

### R2 — replay with modifications
- [x] Overrides: `--input file.json`, `--model`, `--temperature` — recorded
      and passed via `config["configurable"]` (`langops_replay_model` /
      `langops_replay_temperature`) for apps that honour them. Documented
      limit: LangOps can't rewrite prompt templates embedded in user code
- [x] Overrides recorded on the new execution (`langops.execution.overrides`
      event, redacted/capped); replay panel + compare view surface them
- [x] Tests: SDK replay round-trip (exact output for a deterministic graph),
      override recording, truncated-input guard; backend lineage ingestion +
      both-direction API exposure
- [x] Docs: replay guide in `docs/sdk.md` (capabilities *and* limits)

**Accept when:** `langops replay <id>` yields a new execution linked to the
original, and `--model`/`--input` overrides produce a modified run whose
differences are visible in the Phase 10 comparison view — closing the loop:
inspect → compare → replay → compare. ✅ (SDK 20 + backend 47 tests; verified
in the visit-city run)

## Phase 13 — v0.2 hardening & release

- [ ] `docs/semantic-conventions.md` 0.2.0 finalized; SDK/backend constants
      verified mirror-identical; mixed-version compatibility test (0.1 SDK →
      0.2 backend, and the reverse ingest-ignores-unknown path)
- [ ] Per-component docs updated (sdk.md, backend.md, dashboard.md,
      database.md schema changes); CHANGELOG for sdk 0.2.0 + backend 0.2.0
- [ ] `make lint` / `make test` green on all packages; coverage holds on
      backend domain + application (comparator + inference are pure and
      cheap to cover)
- [ ] `make e2e` extended: instrumented run with logs → inspect node badges
      via API → compare two runs → replay via CLI → assert lineage
- [ ] ~~Version bump + tag `v0.2.0`~~ — **superseded by Milestone 3**: the
      tool has never shipped, so there is no 0.2 release; everything lands in
      one first public `0.1.0` (Phase 19). Package versions realign to 0.1.0
      in Phase 14.

**Accept when:** clean machine: quickstart → run example twice → graph shows
rich nodes → compare shows deterministic insights → replay with a model
override produces a linked, comparable execution. No feature added a
recurring LLM cost.

---

# Milestone 3 — Production Efficiency & Insight (ships as v0.1)

Goal: close the gap between the data the platform already captures and what
it surfaces — cached (zero-token) replay, thread-level observability,
per-node cost attribution, global search, failure analytics — then harden
for the **first public release**. Everything stays deterministic (no LLM
calls) and additive.

> **Versioning decision:** the tool has never been published, so there is no
> v0.2 — Milestones 2 and 3 fold into one first release, **`0.1.0`**.
> Package versions (sdk `__version__`, backend) realign to `0.1.0` in
> Phase 14. The *semconv document* stays at 0.2.x — attribute-schema
> versioning is independent of package versioning, and its 0.1→0.2 history
> is real. No `v0.2.0` tag is ever created (supersedes the Phase 13 release
> line).

Priorities driving the order (from the v0.2 review): **P1** cached replay ·
**P2** thread/session view · **P3** per-node cost breakdown · **P4** search
everywhere · **P5** failure analytics · **P6** production hardening. Phase 14
comes first because it fixes known defects and the one ingestion hotspot —
cheap now, expensive after more features stack on top.

## Phase 14 — Correctness & performance debt (pre-feature gate)

Known defects and the ingest hotspot found in the v0.2 review; fix before
building on top of them.

- [x] **Rollup batching**: replaced the per-node loop with
      `NodeExecutionRepository.recompute_rollups(execution_id)` — one UPDATE
      using correlated aggregate subqueries (works on Postgres *and* SQLite,
      so no dialect branch needed); category CASE mirrors domain
      `infer_category`. Idempotency + out-of-order tests pass unchanged; dead
      helpers (`aggregate_by_node`, `node_ids_with_calls`, per-node
      `update_rollups`) removed
- [x] **Comparator $0-cost bug**: `_build_input` now derives `cost_known`
      from child `cost_status` (all priced ⇒ known, incl. genuine $0) and
      passes `total_cost=None` only when truly unknown; `_delta` fixed so
      `0 → 0` is 0% (not None). $0 vs $0 compares as 0%
- [x] **`prompt_changed` upgrade**: `LlmStat.message_sigs` (role:content-hash
      per message) → deterministic sequence diff; `prompt_first_divergence`
      reports the first differing message index. Same-length edits detected
- [x] **Log-capture overflow guard**: `RunContext.log_counts` per span;
      `LangOpsLogHandler` stops at `max_logs_per_span` (config, default 100)
      and emits exactly one visible `langops.log` marker (source `sdk`);
      re-instrument refreshes the handler config
- [x] **Version realignment**: sdk `__version__` 0.2.0 → `0.1.0` (pyprojects
      were already 0.1.0; nothing keys behavior off the version string)

**Accept when:** full suites green with no test edits except new cases;
ingesting a 25-node execution issues exactly one rollup UPDATE (asserted via
SQLAlchemy `before_cursor_execute` counting); `$0 vs $0` compare shows 0%;
a chatty node shows a visible truncation marker. ✅ (backend 51 + SDK 21)

## Phase 15 — Cached replay: zero-token debugging (P1)

The highest-ROI item: replay becomes deterministic and free by serving
recorded tool outputs / LLM responses from the trace instead of re-executing.
All required data (tool input/output, LLM messages/response per call) is
already stored — `GET /executions/{id}/tool-calls` and `/llm-calls` exist,
so this is **SDK + dashboard work only; zero backend changes**.

- [x] SDK `replay(..., stub_llm=True, stub_tools=[tool, …], on_miss=…)` + CLI
      (`--stub-llm`, `--stub-tool module:attr` repeatable, `--on-miss`); fetches
      the recorded LLM/tool calls via the existing endpoints
- [x] **LLM stubbing is generic** (`_stubs.ReplayLLMCache`, a LangChain
      `BaseCache`): chat models consult the process-global cache before every
      call, so recorded generations are replayed **in order** (FIFO) without
      touching the user's graph — more robust than key-matching. Served calls
      set a task-local flag; the callback handler stamps `langops.llm.stubbed`;
      recorded `usage_metadata` preserved so token counts still show
- [x] **Tool stubbing is explicit** (`ToolStub` wrapping passed tool objects,
      matched by name + canonical input with FIFO fallback) — there is no
      global tool cache, and tools called inside node functions can't be
      discovered from a compiled graph; documented honestly
- [x] Guards: `on_miss` `execute`/`fail`; truncated recorded response →
      `ReplayError`; `stub_llm` + `model` rejected; global cache + wrapped
      tools always restored (try/finally)
- [x] Backend (one additive column, `0005_llm_stubbed`): mapper reads
      `langops.llm.stubbed`; stubbed calls priced `Cost.free()` ($0) so they
      drop out of node/execution rollups without special-casing
- [x] Overrides record `stubbed: {llm, tools}`; dashboard LLM-calls tab shows a
      "cached" badge; replay panel shows a "cached" badge + `--stub-llm` hint
- [x] Tests: SDK zero-call round trip (spy-counted) + stubbed marking + cache
      restored + model-override rejection + strict-miss; backend stubbed-cost
      exclusion; semconv doc + both mirrors updated

**Accept when:** `langops replay <id> --stub-llm` on visit-city makes **zero
LLM invocations**, reproduces the recorded output, and the new execution is
badged cached with $0 marginal cost. ✅ (verified end-to-end: real run 3 model
calls → cached replay 0; all 3 replay LLM calls stubbed at $0)

## Phase 16 — Thread view & per-node cost breakdown (P2 + P3)

Both are aggregation + presentation over data already captured.

### 16.1 Thread / session view
- [x] `GET /api/v1/threads`: `ExecutionRepository.list_threads` groups by
      `thread_id` (run count, first/last, status rollup, tokens/cost), most
      recent first, paginated; null-thread executions excluded
- [x] `GET /api/v1/threads/{thread_id}`: `list_by_thread` (oldest first) →
      `ThreadRun`s with running cumulative tokens/cost across the conversation;
      404 on an unknown thread
- [x] Dashboard Threads page (sidebar entry) + thread detail (conversation
      timeline with per-run + cumulative totals); execution header thread id
      links into it
- [x] Tests: grouping/rollup, cumulative totals, 404, null-thread exclusion

### 16.2 Per-node cost breakdown
- [x] Per-execution: `NodeCostBreakdown` share bar on the execution Overview
      (data already in `ExecutionDetail.nodes` — frontend only). Rules
      enforced: unknown-cost nodes badged "unknown" (never 0%); any unknown ⇒
      whole bar falls back to token-share with a caption; no-LLM nodes omitted
- [x] Aggregate: `LlmCallRepository.cost_by_node` (join `llm_calls →
      node_executions`, group by `node_name`, unknown counted separately) +
      `by_node` in `GET /costs/summary` (optional `graph_id`)
- [x] Costs screen: "By node" table with per-node share (unknown → "—")
- [x] Tests: cost-by-node in summary (tokens/calls), unknown exclusion in UI

**Accept when:** the threads page shows separate conversations with their runs;
the costs screen shows node shares; an uncataloged-model node shows "unknown",
never 0%. ✅ (verified e2e on visit-city: 2 threads, cumulative 156→312 across
2 turns, cost-by-node = history/economy/summary ×3 calls each)

## Phase 17 — Search everywhere (P4)

Postgres is sufficient at this scale (500 → 50k executions); this is one
extracted column, one index, one endpoint, one ⌘K palette — **not** a search
cluster.

- [x] Migration `0006_llm_text_search`: `llm_calls.text_content` (prompt +
      response text extracted at ingest, size-capped 8 KB) + a `pg_trgm` GIN
      index on Postgres (`CREATE EXTENSION IF NOT EXISTS pg_trgm`); SQLite
      falls back to a plain LIKE scan for the test suite
- [x] `GET /api/v1/search?q=&per_group=`: `PostgresSearchRepository` runs one
      indexed query per kind — executions (thread/trace ILIKE), graphs (name),
      nodes (name), tools (name), logs (message), LLM content (`text_content`
      with snippet); typed groups, each count-annotated
- [x] Dashboard ⌘K command palette (global, mounted in the layout): grouped
      results, deep-links to the execution; keyboard open/close
- [x] Executions list facets: `model` (EXISTS over llm_calls) + `has_retries`
      (EXISTS over node_executions retry_count) — backend + UI controls
- [x] Tests: LLM-content search finds a phrase only in a response, grouping,
      empty query → 422, model + has_retries facets

**Accept when:** typing a phrase that only appears inside an LLM response finds
its execution from any page in one search. ✅ (verified in-browser: searching
"highlights" surfaced the "LLM RESPONSES · 9" group with snippets; Postgres
serves it via the pg_trgm GIN index)

## Phase 18 — Failure analytics (P5)

What on-call debugging actually needs: *"TimeoutError in weather ×12 this
week"* — a GROUP BY away from data already stored.

- [x] Migration `0007_error_type`: indexed `error_type` on `executions` and
      `node_executions`, extracted from the error JSON at ingest; migration
      backfills existing rows (Postgres `error->>'type'`)
- [x] `GET /api/v1/errors/summary?since=`: `PostgresErrorRepository` groups by
      `error_type` × `node_name` (count, first/last seen, sample execution) +
      a daily trend
- [x] Dashboard Errors screen: grouped table + inline-SVG trend sparkline,
      sample links + "view all →" click-through to filtered executions;
      Overview "Top failures" card
- [x] Executions facet: `error_type` (URL param honoured, removable chip)
- [x] Tests: grouping (TimeoutError×3 in weather, ValueError in planner),
      daily trend total, error_type facet

**Accept when:** injected TimeoutErrors in one node group as a single row with
the right count and working drill-down; the overview card shows it. ✅
(verified in-browser: TimeoutError/weather ×5, ValueError/planner ×3,
KeyError/summary ×2 with trend + sample links + "view all")

## Phase 19 — Production hardening & the 0.1.0 release (P6)

The unglamorous work that makes "production-ready" true beyond localhost.
Subsumes the still-open Phase 8/13 gates (live e2e, load sanity, PyPI).

- [x] **API-key auth (optional, off by default)**: `API_KEY`/`LANGOPS_API_KEY`
      — when set, ingest + `/api/v1/*` require `Authorization: Bearer`
      (constant-time `secrets.compare_digest`); health + `/docs` stay open;
      SDK `LangOpsConfig(api_key=…)`/env adds the OTLP header; dashboard
      `/backend` proxy route attaches the key server-side (never to the
      browser). Single-tenant; multi-user auth stays in the backlog
- [x] **Payload lifecycle**: retention on by default in compose
      (`RETENTION_DAYS=30`, `0`=off) via a periodic in-process lifespan task
      (no cron); `RETENTION_PRUNE_PAYLOADS_DAYS` nulls messages/response/state
      while keeping rollup rows (`prune_payloads_older_than`)
- [x] **Load sanity**: `scripts/loadtest.py` fires N concurrent executions,
      reports ingest p50/p95 + throughput, asserts no loss (user-run)
- [ ] **Live `make e2e`** on a Docker host — the user's to run (this sandbox
      has no Docker and `api.openai.com` is DNS-blocked); every feature was
      verified via the in-process visit-city harness + browser instead
- [x] Docs: `setup.md` production section, `.env.example` +
      `docker-compose.yml` env, consolidated `CHANGELOG.md` for 0.1.0
- [ ] Tag `v0.1.0`; publish `langops` 0.1.0 to PyPI (release steps for the
      user — package versions are already `0.1.0`)

**Accept when:** clean-machine quickstart < 10 min; with the key set,
unauthenticated ingest/query return 401 and the instrumented example still
works; retention prunes on schedule. ✅ (auth/retention/prune unit+API tested,
backend 68 + SDK 25; live Docker e2e + PyPI tag remain the user's release
steps)

---

## Post-MVP backlog (architecture §10 — do not start before 0.1.0)

Prompt versioning · agent evaluation (batch replay + comparator as the
seam) · **replay R3/R4** (from checkpoint / from arbitrary node — requires
checkpoint state rehydration; R1/R2 landed in Phase 12, cached replay in
Phase 15) · human-in-the-loop · multi-project · **multi-user auth/SSO**
(single API key lands in Phase 19) · Kubernetes deployment ·
partitioned/scale-out storage. Each maps to an existing seam; keep it that
way — new features must be additive.
