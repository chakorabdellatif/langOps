# Visit City — a multi-agent app observed with LangOps

A four-agent LangGraph app that briefs you on any city — and shows how little it
takes to get **full observability** with LangOps: one line.

```
       ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
START ─▶ weather ─▶  history  ─▶  economy  ─▶  summary  ─▶ END
       └─────────┘   └─────────┘   └─────────┘   └─────────┘
        Open-Meteo    gpt-4o-mini   gpt-4o-mini   gpt-4o-mini
         (tool)
```

- **weather** — current conditions from [Open-Meteo](https://open-meteo.com)
  (free, no API key)
- **history / economy / summary** — `gpt-4o-mini` agents
- **Redis cache** — ask about the same city twice; the second answer is instant
  and the agents don't re-run

## The only LangOps line

```python
import langops

graph = build_graph()
graph = langops.instrument(graph)   # 👈 that's it — full tracing, zero code change
```

Every run now shows up in the dashboard with the graph path, per-node state
diffs, every LLM and tool call, tokens, latency, and **cost** (gpt-4o-mini is in
the pricing catalog, so you get real dollars — not "unknown").

## Run it

```bash
# 1. LangOps stack (from the repo root)
docker compose up -d

# 2. Deps
pip install -e ./sdk
pip install -r examples/visit-city/requirements.txt
export OPENAI_API_KEY=sk-...

# 3. Go
python examples/visit-city/main.py Paris Tokyo Cairo
```

Then open **http://localhost:3000**:

- **Executions** — one per city; watch them appear live.
- **Graph** — `weather → history → economy → summary`, nodes colored by status
  with duration badges.
- **LLM Calls** — the exact prompt and response for each agent, with token
  counts and cost.
- **Tool Calls** — the Open-Meteo weather lookup, input and output.
- **State** — how the state grows as each agent adds its slice.
- **Compare** — diff two cities side by side (tokens, cost, latency, final brief).

Re-run a city (or run the same one twice) and the console prints
`[cache hit]` — served from Redis, no execution created. That's the caching the
platform is designed to make observable.
