# ADR-0001: OpenTelemetry as the SDK wire format

**Status:** accepted · **Date:** 2026-07-06

## Context

The SDK must ship telemetry (spans for executions, nodes, LLM calls, tools;
state snapshots) from the user's process to the LangOps backend. Options:
a custom HTTP/JSON protocol, or standard OTLP with a documented attribute
namespace.

## Decision

The SDK emits plain OpenTelemetry spans over OTLP, with LangOps meaning
carried by semantic conventions (`docs/semantic-conventions.md`): `gen_ai.*`
where official conventions exist, `langops.*` for LangGraph-specific
concepts. An OTel Collector sits between SDK and backend.

## Consequences

- Batching, retry, back-pressure, sampling, and context propagation are
  inherited from OTel instead of reimplemented.
- Users can tee LangOps telemetry into existing OTel stacks (Jaeger,
  Datadog, Grafana) for free.
- OTLP attribute/event size norms constrain giant payloads — handled with
  explicit payload limits and span events; a side-channel for oversized
  artifacts is a documented future extension (architecture §10).
- The backend must be a standards-compliant OTLP receiver
  (`POST /v1/traces`, protobuf + JSON).
