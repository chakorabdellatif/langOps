# ADR-0002: Pricing lives in a JSON catalog, enriched server-side

**Status:** accepted (implementation deferred to Phase 7) · **Date:** 2026-07-06

## Context

Cost is derived from LLM-call facts (provider, model, input/output tokens).
Two questions: *where* does cost get computed, and *where* do prices live.

The MVP already settled the first: the **SDK observes, the backend enriches**.
The SDK emits only `gen_ai.*` telemetry (model, tokens) and never sees a price;
the backend computes cost at ingest. That separation stands.

This ADR settles the second question and supersedes the `model_pricing` **table**
described in `architecture.md` §4.2 (the table + `effective_from` history model).

## Decision

Prices live in **per-provider JSON catalog files** under
`backend/src/langops_api/infrastructure/pricing/` (`openai.json`,
`anthropic.json`, `google.json`, `ollama.json`, …), loaded into an in-memory
pricing service at startup. Editing a price is a JSON edit + restart — no code
change, no database migration. Local models (ollama, cost `0`) and a
user-supplied custom catalog are first-class.

Historical accuracy is preserved by storing the **computed cost on each
`llm_calls` row at ingest** (old rows keep their old cost; only new calls use a
changed price), so the catalog does not need `effective_from` dating for the MVP.

Unknown models are **never priced at `$0`**. Cost is nullable and each call
carries a `cost_status` (`priced` / `unknown`) so the dashboard renders
"Unknown" rather than a misleading zero. Cost is split into
`input_cost` / `output_cost` / `total_cost`.

## Consequences

- Drop the `model_pricing` table and its seed migration; delete
  `infrastructure/db/pricing_seed.py`. `PricingRepository` becomes a catalog
  lookup, not a DB query. `CostCalculator` is unchanged (still pure).
- Contributors add a model by editing one JSON file in a reviewable PR.
- **Interim state (Phases 2–6):** the current implementation seeds a
  `model_pricing` DB table from a Python list and returns `$0` for unknown
  models. This is a known, temporary gap — the JSON catalog, `cost_status`,
  and cost split all land in **Phase 7** (Cost & token tracking). Nothing
  consumes the cost fields until then, so the migration cost is low.
