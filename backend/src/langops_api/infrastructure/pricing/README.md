# Pricing catalog

Per-provider JSON price files (USD per 1M tokens), loaded into an in-memory
pricing service at startup (see `catalog.py` and ADR-0002). To change a price
or add a model, edit the relevant file and restart the API — no migration, no
code change.

```json
{
  "provider": "openai",
  "models": {
    "gpt-4.1": { "input": 2.0, "output": 8.0 }
  }
}
```

- **Add a provider:** drop a new `<provider>.json` here; it's picked up
  automatically.
- **Local models:** `ollama.json` prices everything at `0`.
- **Custom / self-hosted models:** set `PRICING_CATALOG_DIR` to a directory of
  additional `*.json` files (same shape); they extend/override the built-ins.
- **Unknown models** (not in any file) are recorded with `cost_status:
  "unknown"` and shown as "Unknown" in the dashboard — never priced at `$0`.
