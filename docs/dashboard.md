# Dashboard — `dashboard/`

The **`langops-dashboard`** — a Next.js (App Router) web UI that turns captured
telemetry into "Chrome DevTools for LangGraph": graph, state, LLM/tool traces,
costs, metrics, live updates, and side-by-side execution comparison.

> Design reference: [architecture.md §6](architecture.md#6-frontend-architecture-langops-dashboard).

---

## Stack

- **Next.js 14** (App Router, standalone output) + **React** + **TypeScript**
- **TanStack Query** for server state (caching, polling, dedupe)
- **React Flow** for the graph DAG; **Recharts** for cost/metrics charts
- **Tailwind CSS** for styling
- Client-side data fetching against the API (`NEXT_PUBLIC_API_URL`)

---

## Layout

```
dashboard/src/
├── app/                          # routes (thin — compose feature modules)
│   ├── layout.tsx                # shell: sidebar, Query provider, live updates
│   ├── page.tsx                  # Overview
│   ├── executions/page.tsx       # execution list (filter, paginate, live)
│   ├── executions/[id]/page.tsx  # Execution Explorer (tabbed)
│   ├── compare/page.tsx          # execution comparison
│   ├── costs/page.tsx            # Recharts cost breakdowns
│   └── metrics/page.tsx          # latency percentiles, failure rate
├── features/                     # one module per domain feature
│   ├── graph/                    #   React Flow DAG + status/duration/retry badges
│   ├── timeline/                 #   Gantt-style span waterfall
│   └── state/                    #   diff view + context-growth chart
├── components/
│   ├── layout/                   #   sidebar, live-updates mount
│   └── data/                     #   StatusBadge, Duration, Cost, Tokens, JsonViewer, …
└── lib/
    ├── api/                      #   client.ts, hooks.ts, sse.ts, types.ts, generated/
    └── query-keys.ts             #   centralized TanStack Query key factory
```

---

## Screens

- **Overview** — total/running/failed executions, success rate, total tokens,
  total cost, avg + p95 latency, and recent executions (live).
- **Executions** — filterable, paginated, live-updating list.
- **Execution Explorer** (`/executions/[id]`) — header (status, duration,
  tokens, cost, thread/checkpoint, resumed) + tabs:
  **Overview** (input/output/error) · **Graph** (React Flow DAG, nodes colored by
  status with duration/retry/error badges) · **Timeline** · **State** (per-node
  diff + context-growth chart) · **LLM Calls** · **Tool Calls** · **Logs**.
- **Compare** (`/compare`) — pick two executions; side-by-side metric deltas
  (duration, tokens, cost, nodes, retries), graph paths, and a colorized
  final-state diff.
- **Costs** — by-model Recharts breakdown (unknown-priced models flagged) + table.
- **Metrics** — status counts, failure rate, latency p50/p95/p99.

---

## Data & live updates

- **Types** — `lib/api/types.ts` mirrors the backend schemas. The production
  path is `npm run generate:api`, which regenerates types from the live OpenAPI
  schema into `lib/api/generated/`.
- **Hooks** — `lib/api/hooks.ts` wraps every endpoint in a typed TanStack Query
  hook keyed by `lib/query-keys.ts`.
- **Live updates** — `lib/api/sse.ts` subscribes to the backend SSE stream and
  invalidates execution/metrics queries on each `execution.updated` event, so
  lists and detail views refresh without polling.

---

## Develop & build

```bash
cd dashboard
npm install
npm run dev              # http://localhost:3000
npm run typecheck        # tsc --noEmit
npm run lint             # eslint (next)
npm run build            # production build (standalone)
npm run generate:api     # regenerate API types from a running backend's OpenAPI
```

Point the dashboard at a non-default API with `NEXT_PUBLIC_API_URL` (baked at
build time). In Docker it's set on the `dashboard` service.
