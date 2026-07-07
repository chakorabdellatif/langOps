# Collector — `collector/`

The OpenTelemetry Collector configuration (`otel-collector-config.yaml`). It sits
between instrumented apps and the backend: it receives OTLP from the SDK,
batches and retries, and forwards to the API's ingestion endpoint.

> It runs as the `otel-collector` service in `docker-compose.yml` using the
> `otel/opentelemetry-collector-contrib` image — LangOps ships **config only**,
> no custom collector build.

---

## Why it's there

The SDK speaks standard OTLP, not a proprietary protocol. The Collector gives us
batching, retry, back-pressure, and memory limiting for free, and decouples SDK
release cadence from backend cadence. In local dev it's one container; in a
future cloud deployment it becomes a scalable ingestion tier with zero SDK
changes.

---

## Pipeline

```
instrumented app  ──OTLP/gRPC :4317  ──▶  Collector  ──OTLP/HTTP──▶  api:8000/v1/traces
                    OTLP/HTTP :4318                (protobuf)
```

- **receivers.otlp** — listens on `:4317` (gRPC) and `:4318` (HTTP). Both ports
  are published to the host so an app running outside Compose can reach them at
  `localhost`.
- **processors** — `memory_limiter` (guards against OOM) then `batch` (groups
  spans to reduce request volume).
- **exporters.otlphttp/langops** — POSTs to `http://api:8000` (the exporter
  appends `/v1/traces`) as `application/x-protobuf`, which the backend receiver
  accepts. `retry_on_failure` + `sending_queue` are what make the
  **kill/restart resilience** work: if the API is down, spans are queued and
  retried for up to 5 minutes, so no data is lost.

---

## Editing the config

The config is a read-only bind mount, so you can edit
`collector/otel-collector-config.yaml` and `docker compose restart
otel-collector` without rebuilding an image. To send LangOps telemetry into an
existing OTel stack (Jaeger, Datadog, Grafana) as well, add a second exporter and
list it in the `traces` pipeline — the LangOps-specific meaning lives in the
`langops.*` attributes, so any OTLP backend can also receive the spans.

Validate the config indirectly with `docker compose config` (compose syntax) or
by watching `docker compose logs otel-collector` on startup.
