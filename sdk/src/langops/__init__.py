"""LangOps SDK — observability for LangGraph applications.

Public surface (everything else is private):

    from langops import instrument, LangOpsConfig

    graph = instrument(compiled_graph)          # defaults
    graph = instrument(compiled_graph, config=LangOpsConfig(...))
"""

from langops.config import LangOpsConfig

__version__ = "0.1.0.dev0"

__all__ = ["LangOpsConfig", "instrument", "__version__"]


def instrument(graph, config: LangOpsConfig | None = None):  # type: ignore[no-untyped-def]
    """Instrument a compiled LangGraph graph and return it.

    Wraps the graph's entrypoints (invoke/ainvoke/stream/astream), injects the
    LangOps callback handler, and wraps the checkpointer if one is attached.
    Telemetry failures never propagate to the caller.

    Implementation: Phase 3 (tasks.md) — instrumentation/graph.py.
    """
    raise NotImplementedError("langops.instrument() is implemented in Phase 3 — see tasks.md")
