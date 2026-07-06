# Pricing catalog

Per-provider JSON price files (USD per 1M tokens), loaded into an in-memory
pricing service at startup (see `catalog.py` and ADR-0002). To change a price
or add a model, edit the relevant file and restart the API — no migration, no
code change.

```json
{
  "provider": "openai",
  "currency": "USD",
  "models": [
    { "name": "gpt-4.1", "input": 2.0, "output": 8.0, "effective_from": "2025-01-01" }
  ]
}
```

- **Add a provider:** drop a new `<provider>.json` here; it's picked up
  automatically.
- **Effective-dating:** list a model multiple times with different
  `effective_from` dates; the price in effect at the call's timestamp is used.
- **Dated variants:** `gpt-4.1-2025-04-14` resolves to `gpt-4.1` by
  longest-prefix match — no need to list every snapshot.
- **Local models:** `ollama.json` prices everything at `0`.
- **Custom / self-hosted models:** add them to `custom.json`, or set
  `PRICING_CATALOG_DIR` to a directory of additional `*.json` files (same
  shape); they extend/override the built-ins.
- **Reload without a restart:** `PricingCatalog.reload()` re-reads the files.
- **Unknown models** (not in any file) are recorded with `cost_status:
  "unknown"` and shown as "Unknown" in the dashboard — never priced at `$0`.
