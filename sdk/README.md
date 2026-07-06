# langops (SDK)

Observability SDK for LangGraph applications.

```python
from langops import instrument

graph = instrument(graph)
graph.invoke(...)
```

Spans are exported via OTLP to the LangOps stack (default
`http://localhost:4317`). See the repository root README and
`docs/architecture.md` §5 for the design.
