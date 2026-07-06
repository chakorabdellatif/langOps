"""LangOps SDK — observability for LangGraph applications.

Public surface (everything else is private):

    from langops import instrument, LangOpsConfig

    graph = instrument(compiled_graph)          # defaults
    graph = instrument(compiled_graph, config=LangOpsConfig(...))
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from langops.config import LangOpsConfig

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider

__version__ = "0.1.0.dev0"

__all__ = ["LangOpsConfig", "instrument", "__version__"]

_INSTRUMENTED = "__langops_instrumented__"


def instrument(
    graph: Any,
    config: LangOpsConfig | None = None,
    *,
    tracer_provider: TracerProvider | None = None,
) -> Any:
    """Instrument a compiled LangGraph graph and return it.

    Wraps the graph's entrypoints (invoke/ainvoke/stream/astream), injects the
    LangOps callback handler, and wraps the checkpointer if one is attached.
    Telemetry failures never propagate to the caller — a graph is always
    returned, instrumented if possible, untouched otherwise.

    ``tracer_provider`` overrides the default OTLP provider (used by tests to
    capture spans with an in-memory exporter).
    """
    config = config or LangOpsConfig()

    if getattr(graph, _INSTRUMENTED, False):
        return graph  # idempotent — never double-wrap

    try:
        from langops.instrumentation.graph import instrument_graph

        if tracer_provider is None:
            from langops.export.tracer import build_tracer_provider

            tracer_provider = build_tracer_provider(config)

        instrument_graph(graph, config, tracer_provider)
        with contextlib.suppress(Exception):  # guard flag is best-effort
            setattr(graph, _INSTRUMENTED, True)
    except Exception:  # noqa: BLE001 — instrumentation must never break adoption
        import logging

        logging.getLogger("langops").warning(
            "langops: instrumentation unavailable; returning the graph unmodified"
        )

    return graph
