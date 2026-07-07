# Examples — `examples/`

Runnable, instrumented LangGraph apps. They double as living documentation and
end-to-end smoke tests.

| Example | What it shows |
|---|---|
| `simple-agent/` | A minimal 2-node graph (`plan → act`) with one LLM call and one tool call, wrapped by `langops.instrument`. Runs with **no API key** (uses a deterministic fake chat model) — swap in `ChatOpenAI(...)` for the real thing. |
| `multi-agent-rag/` | Placeholder for the richer demo (multiple agents, tools, retrieval, checkpoints, retries) used to exercise the state viewer and comparison. |

## Run `simple-agent`

```bash
docker compose up -d          # in the repo root: full stack
pip install -e ./sdk
python examples/simple-agent/main.py
open http://localhost:3000    # the execution appears in the dashboard
```

Without the stack running, the graph still executes cleanly — telemetry export
just fails quietly in the background (the SDK never breaks the host app). This is
the pattern to copy into your own app; see
[setup.md](setup.md#instrument-your-own-langgraph-app).
