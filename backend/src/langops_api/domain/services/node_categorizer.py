"""Deterministic node categorisation — no I/O, no LLM (v0.2, Phase 9).

Structural categories (router/conditional/checkpoint/subgraph) come from the
SDK, which reads them off the graph topology; they always win. Everything else
is inferred from what the node actually did at runtime: a node with LLM child
spans is an ``llm`` agent, one with only tool child spans is a ``tool`` node,
and a node with neither is a plain ``utility`` node.
"""

from __future__ import annotations

LLM = "llm"
TOOL = "tool"
UTILITY = "utility"

STRUCTURAL = frozenset({"router", "conditional", "checkpoint", "subgraph"})


def infer_category(sdk_category: str | None, *, has_llm: bool, has_tool: bool) -> str:
    """Final stored category for a node.

    ``sdk_category`` is whatever the SDK sent (may be ``None``). A structural
    SDK category is authoritative; otherwise the category is inferred from the
    node's child spans, falling back to any non-structural SDK hint, then
    ``utility``.
    """
    if sdk_category in STRUCTURAL:
        return sdk_category  # type: ignore[return-value]
    if has_llm:
        return LLM
    if has_tool:
        return TOOL
    if sdk_category:
        return sdk_category
    return UTILITY
