"""LangChain BaseCallbackHandler — node, LLM, and tool spans.

Maps runtime events to spans: on_chain_start/end/error → node spans (with
retry detection), on_chat_model_start/on_llm_end/error → LLM spans,
on_tool_start/end/error → tool spans. Parent-child wiring maps
run_id/parent_run_id onto OTel span context so the span tree mirrors the
execution tree (including subgraphs).

Implemented in Phase 3 — see tasks.md and architecture.md §5.3(2).
"""
