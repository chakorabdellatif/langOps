# LangOps Documentation

Start here. LangOps is an observability platform for LangGraph apps — "Chrome
DevTools for LangGraph."

## Getting started

- **[Setup & Usage](setup.md)** — run the stack and instrument your own LangGraph
  app (requirements, quick start, SDK config, env vars, troubleshooting).

## Components (one doc per top-level folder)

| Doc | Folder | What it covers |
|---|---|---|
| [sdk.md](sdk.md) | `sdk/` | The `langops` instrumentation SDK — how `instrument()` works |
| [backend.md](backend.md) | `backend/` | The `langops-api` service — layering, ingestion, query API, pricing |
| [dashboard.md](dashboard.md) | `dashboard/` | The Next.js UI — screens, data flow, live updates |
| [collector.md](collector.md) | `collector/` | The OTel Collector config — the ingestion pipeline |
| [examples.md](examples.md) | `examples/` | Runnable instrumented demo apps |

## Reference & design

- **[architecture.md](architecture.md)** — the full implementation blueprint
  (system, layering, schema, SDK strategy, Docker topology, conventions).
- **[semantic-conventions.md](semantic-conventions.md)** — the SDK ↔ backend
  contract (the `langops.*` / `gen_ai.*` OTel attribute namespace).
- **[database.md](database.md)** — schema reference.
- **[adr/](adr/)** — Architecture Decision Records
  ([0001 OTel wire format](adr/adr-0001-otel-as-wire-format.md),
  [0002 pricing catalog](adr/adr-0002-pricing-catalog.md)).

## Project status

See [`../tasks.md`](../tasks.md) for the phased build plan and current state, and
[`../CHANGELOG.md`](../CHANGELOG.md) for the release history.
