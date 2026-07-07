# SDK — `sdk/`

The Python instrumentation SDK, published as **`langops`** on PyPI. It wraps a
compiled LangGraph app in-process and emits OpenTelemetry spans; it does not
talk to the LangOps backend directly — it speaks standard OTLP, so any OTel
backend can receive it.

> Design reference: [architecture.md §5](architecture.md#5-sdk-architecture-langops-sdk).
> Wire contract: [semantic-conventions.md](semantic-conventions.md).

---

## What it does

For every graph run it captures — with **zero code change** beyond
`instrument(graph)` and **zero risk** to the host app:

- the **execution** (root span): graph topology, thread/checkpoint ids,
  fresh-vs-resumed, input/output;
- each **node**: name, sequence, retries, status, input/output state;
- each **LLM call**: provider, model, messages, params, response, token usage;
- each **tool call**: name, input, output.

Cost is **not** computed here — the SDK only observes facts. Pricing lives in the
backend (see [backend.md](backend.md#pricing)).

---

## Layout

```
sdk/src/langops/
├── __init__.py            # public surface: instrument(), LangOpsConfig, __version__
├── config.py              # LangOpsConfig (endpoint, capture toggles, redaction, …)
├── semconv.py             # langops.* / gen_ai.* attribute constants (mirrors docs/)
├── instrumentation/
│   ├── graph.py           # wraps invoke/ainvoke/stream/astream → execution root span
│   ├── callbacks.py       # LangChain BaseCallbackHandler → node / LLM / tool spans
│   ├── checkpointer.py    # checkpointer proxy → authoritative checkpoint lineage
│   └── runtime.py         # per-run context (ContextVar) + payload event helper
├── capture/
│   ├── state.py           # safe serialization: depth/size caps, truncation marker
│   ├── diff.py            # structural diff {added, modified, removed}
│   └── redaction.py       # user hook, applied before export (fail-closed)
└── export/
    ├── tracer.py          # dedicated TracerProvider + resource attributes
    └── processors.py      # BatchSpanProcessor over the OTLP exporter
```

---

## How it works

`instrument(graph)` uses the three **supported** LangGraph seams — it
monkeypatches nothing beyond the graph's own entrypoints:

1. **Graph wrapper** (`graph.py`) — replaces `invoke`/`ainvoke`/`stream`/`astream`
   on the compiled graph instance. Each call opens the **execution root span**,
   captures topology once (`graph.get_graph()` + hash), extracts
   `thread_id`/`checkpoint_id` from the run config, detects fresh-vs-resumed, and
   injects the callback handler. A re-entrancy guard means the internal
   `invoke → stream` delegation doesn't double-count.
2. **Callback handler** (`callbacks.py`) — a `BaseCallbackHandler` that turns
   `on_chain_*` into node spans (sequence from the `graph:step` tag, retry
   detection), `on_chat_model_start` / `on_llm_end` into LLM spans (`gen_ai.*`
   attributes + `usage_metadata` tokens), and `on_tool_*` into tool spans.
   `run_id` / `parent_run_id` map onto OTel span context.
3. **Checkpointer wrapper** (`checkpointer.py`) — a composition proxy over
   `BaseCheckpointSaver` that records authoritative checkpoint lineage on each
   `put()`.

**Export** (`export/`) builds a **dedicated** `TracerProvider` — never the global
one — so LangOps coexists with any OTel instrumentation you already run, and
batches spans out over OTLP.

**Failure policy:** every capture path is wrapped; an internal error logs one
warning per failure class and drops that datum. Your graph run is never failed or
slowed by LangOps.

---

## Usage

See [setup.md → Instrument your own LangGraph app](setup.md#instrument-your-own-langgraph-app)
for the full guide. Minimal:

```python
from langops import instrument
graph = instrument(graph)
graph.invoke(..., config={"configurable": {"thread_id": "s1"}})
```

### Structured logs (v0.2, opt-in)

```python
graph = instrument(graph, LangOpsConfig(capture_logs=True))
```

Bridges stdlib `logging` records into the trace as `langops.log` events on the
node that emitted them (falling back to the execution root). Off by default —
when disabled it costs nothing. Records pass the same redaction hook and
payload cap as every other capture path.

### Replay (v0.2)

Re-run a captured execution on your local instrumented graph — exactly, or with
modifications:

```bash
# exact replay
python -m langops replay <execution-id> --app your_module:graph

# with overrides (experimentation)
python -m langops replay <execution-id> --app your_module:graph \
    --model gpt-5 --temperature 0.2 --input new_input.json
```

or programmatically:

```python
import langops
langops.replay(graph, "<execution-id>", model="gpt-5")
```

**What replay is — and isn't.** Replay fetches the recorded input/config from
the API and re-invokes your *local* graph, so it runs in your environment:
external APIs and tools re-execute for real, and results need not match the
original. Replay is for **experimentation** (swap a model, edit the input,
adjust temperature), not deterministic time travel.

- `--model` / `--temperature` are recorded on the new execution and passed via
  `config["configurable"]` (`langops_replay_model` / `langops_replay_temperature`)
  — apps that read those keys honour them; LangOps cannot rewrite prompt
  templates embedded in your code.
- A fresh thread is used unless `--same-thread`.
- Replaying an execution whose input was truncated at capture time fails fast
  (pass `--input` to supply one explicitly).
- Every replay links back to its original (`replay_of`) so the dashboard shows
  the lineage and a one-click comparison. Replaying from a checkpoint or an
  arbitrary node (R3/R4) is future work.

---

## Develop & test

```bash
cd sdk
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/ruff check src tests
.venv/Scripts/mypy src
.venv/Scripts/python -m pytest            # 15 tests
```

Tests use an in-memory OTel exporter and a real 2-node LangGraph run to validate
spans field-by-field against the semantic conventions, plus fault-injection
(a raising redaction hook must not break the graph). `instrument()` accepts a
`tracer_provider=` override for this.
