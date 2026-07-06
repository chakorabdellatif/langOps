"""CompiledGraph wrapper — execution root spans.

Wraps invoke/ainvoke/stream/astream to: open the execution root span, record
graph input/output, extract thread/checkpoint ids from
``config["configurable"]``, capture topology once via ``graph.get_graph()``,
determine fresh-vs-resumed via the (wrapped) checkpointer, and inject the
callback handler into the run config.

Implemented in Phase 3 — see tasks.md and architecture.md §5.3(1).
"""
