"""Instrumentation against a real LangGraph run with an in-memory exporter.

Validates the emitted spans against docs/semantic-conventions.md and proves the
failure policy: telemetry errors never reach the host graph.
"""

import json
from typing import TypedDict
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langgraph.graph import END, START, StateGraph
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import langops
from langops import semconv
from langops.config import LangOpsConfig
from langops.instrumentation.callbacks import LangOpsCallbackHandler


class State(TypedDict):
    x: int


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _two_node_graph():
    graph = StateGraph(State)
    graph.add_node("plan", lambda s: {"x": s["x"] + 1})
    graph.add_node("act", lambda s: {"x": s["x"] * 2})
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "act")
    graph.add_edge("act", END)
    return graph.compile()


def _event(span, name):
    return next(e for e in span.events if e.name == name)


def test_execution_and_node_spans() -> None:
    provider, exporter = _provider()
    graph = langops.instrument(_two_node_graph(), tracer_provider=provider)

    result = graph.invoke({"x": 1}, config={"configurable": {"thread_id": "t1"}})
    assert result == {"x": 4}  # graph output unaffected by instrumentation

    spans = exporter.get_finished_spans()
    by_kind = {s.attributes[semconv.KIND]: s for s in spans}
    assert set(by_kind) == {"execution", "node"}
    nodes = sorted(
        (s for s in spans if s.attributes[semconv.KIND] == "node"),
        key=lambda s: s.attributes[semconv.NODE_SEQUENCE],
    )
    assert [s.attributes[semconv.NODE_NAME] for s in nodes] == ["plan", "act"]
    assert [s.attributes[semconv.NODE_SEQUENCE] for s in nodes] == [1, 2]

    execution = by_kind["execution"]
    assert execution.attributes[semconv.THREAD_ID] == "t1"
    assert execution.attributes[semconv.GRAPH_NAME]
    assert execution.attributes[semconv.GRAPH_TOPOLOGY_HASH]

    # Every child span correlates to the execution and shares its trace.
    exec_id = execution.attributes[semconv.EXECUTION_ID]
    for node in nodes:
        assert node.attributes[semconv.EXECUTION_ID] == exec_id
        assert node.context.trace_id == execution.context.trace_id
        assert node.parent.span_id == execution.context.span_id

    # State events carry a JSON payload the backend can decode.
    payload = _event(nodes[0], semconv.EVENT_STATE_INPUT).attributes[semconv.PAYLOAD]
    assert json.loads(payload) == {"x": 1}

    # Topology payload is v2: node objects {id, ...} and edge objects.
    topo = json.loads(_event(execution, semconv.EVENT_GRAPH_TOPOLOGY).attributes[semconv.PAYLOAD])
    assert {n["id"] for n in topo["nodes"]} >= {"plan", "act"}
    assert all("source" in e and "target" in e and "conditional" in e for e in topo["edges"])


def test_conditional_node_gets_category() -> None:
    provider, exporter = _provider()

    def route(state: State) -> str:
        return "act" if state["x"] > 0 else END

    graph = StateGraph(State)
    graph.add_node("plan", lambda s: {"x": s["x"] + 1})
    graph.add_node("act", lambda s: {"x": s["x"] * 2})
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", route, {"act": "act", END: END})
    graph.add_edge("act", END)
    instrumented = langops.instrument(graph.compile(), tracer_provider=provider)

    instrumented.invoke({"x": 1})

    spans = exporter.get_finished_spans()
    plan = next(
        s
        for s in spans
        if s.attributes.get(semconv.KIND) == "node" and s.attributes[semconv.NODE_NAME] == "plan"
    )
    # "plan" is the source of a conditional edge → categorised as conditional.
    assert plan.attributes[semconv.NODE_CATEGORY] == semconv.NodeCategory.CONDITIONAL


def test_llm_and_tool_spans_via_handler() -> None:
    provider, exporter = _provider()
    tracer = provider.get_tracer("test")
    root = tracer.start_span("execution")
    handler = LangOpsCallbackHandler(tracer, "exec-1", root, LangOpsConfig())

    # LLM span with token usage from usage_metadata.
    llm_run = uuid4()
    handler.on_chat_model_start(
        {},
        [[]],
        run_id=llm_run,
        metadata={"ls_provider": "anthropic", "ls_model_name": "claude-opus-4-8"},
        invocation_params={"model": "claude-opus-4-8", "temperature": 0},
    )
    message = AIMessage(
        content="ok",
        usage_metadata={"input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
    )
    handler.on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]]), run_id=llm_run)

    # Tool span.
    tool_run = uuid4()
    handler.on_tool_start({"name": "word_count"}, "hello world", run_id=tool_run)
    handler.on_tool_end("2", run_id=tool_run)
    root.end()

    spans = {s.attributes.get(semconv.KIND): s for s in exporter.get_finished_spans()}
    llm = spans["llm"]
    assert llm.attributes[semconv.GEN_AI_SYSTEM] == "anthropic"
    assert llm.attributes[semconv.GEN_AI_REQUEST_MODEL] == "claude-opus-4-8"
    assert llm.attributes[semconv.GEN_AI_USAGE_INPUT_TOKENS] == 12
    assert llm.attributes[semconv.GEN_AI_USAGE_OUTPUT_TOKENS] == 3

    tool = spans["tool"]
    assert tool.attributes[semconv.TOOL_NAME] == "word_count"


def test_instrumentation_never_breaks_the_graph() -> None:
    provider, exporter = _provider()
    # A redaction hook that raises on every payload must not break the run
    # (it fails closed) and the graph output must be unchanged.
    config = LangOpsConfig(redaction_hook=lambda _: (_ for _ in ()).throw(ValueError("boom")))
    graph = langops.instrument(_two_node_graph(), config, tracer_provider=provider)

    assert graph.invoke({"x": 3}) == {"x": 8}
    # Spans are still emitted; payloads were dropped, not leaked.
    assert any(s.attributes.get(semconv.KIND) == "node" for s in exporter.get_finished_spans())


def test_instrument_is_idempotent() -> None:
    provider, exporter = _provider()
    graph = _two_node_graph()
    graph = langops.instrument(graph, tracer_provider=provider)
    graph = langops.instrument(graph, tracer_provider=provider)  # second call is a no-op

    graph.invoke({"x": 1})
    executions = [
        s for s in exporter.get_finished_spans() if s.attributes.get(semconv.KIND) == "execution"
    ]
    assert len(executions) == 1  # not double-wrapped


@pytest.mark.asyncio
async def test_ainvoke_emits_spans() -> None:
    provider, exporter = _provider()
    graph = langops.instrument(_two_node_graph(), tracer_provider=provider)

    result = await graph.ainvoke({"x": 1})
    assert result == {"x": 4}
    kinds = {s.attributes.get(semconv.KIND) for s in exporter.get_finished_spans()}
    assert kinds == {"execution", "node"}
