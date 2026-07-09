"""Phase 15 — cached replay: recorded LLM responses served with zero calls."""

from itertools import cycle
from typing import Any, TypedDict

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import langops
from langops import semconv
from langops._replay import ReplayError


class State(TypedDict):
    x: int


class CountingModel(GenericFakeChatModel):
    calls: int = 0

    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        type(self).calls += 1
        return super()._generate(*args, **kwargs)


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _graph(provider: TracerProvider, model: Any):
    def node(state: State) -> dict:
        model.invoke("hello")
        return {"x": state["x"] + 1}

    graph = StateGraph(State)
    graph.add_node("agent", node)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return langops.instrument(graph.compile(), tracer_provider=provider)


def test_stub_llm_serves_recording_with_zero_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    CountingModel.calls = 0
    model = CountingModel(messages=cycle([AIMessage(content="recorded answer")]))
    provider, exporter = _provider()
    graph = _graph(provider, model)

    # First, a real run.
    graph.invoke({"x": 1})
    assert CountingModel.calls == 1

    # The recording the API would return for the replay.
    recorded_llm = [
        {"response": {"content": "recorded answer"}, "input_tokens": 7, "output_tokens": 3}
    ]

    def fake_fetch(api: str, path: str, timeout: float) -> Any:
        if path.endswith("/llm-calls"):
            return recorded_llm
        return {"input": {"x": 1}, "thread_id": None}

    monkeypatch.setattr("langops._replay._fetch_json", fake_fetch)

    CountingModel.calls = 0
    exporter.clear()
    result = langops.replay(graph, "orig", stub_llm=True)

    assert result == {"x": 2}
    assert CountingModel.calls == 0  # zero real model calls — served from cache

    llm_span = next(
        s for s in exporter.get_finished_spans() if s.attributes.get(semconv.KIND) == "llm"
    )
    assert llm_span.attributes.get(semconv.LLM_STUBBED) is True
    # Global cache is restored after replay.
    from langchain_core.globals import get_llm_cache

    assert get_llm_cache() is None


def test_stub_llm_rejects_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, _ = _provider()
    graph = _graph(provider, CountingModel(messages=cycle([AIMessage(content="x")])))
    with pytest.raises(ReplayError, match="contradicts swapping the model"):
        langops.replay(graph, "orig", stub_llm=True, model="gpt-5")


def test_stub_llm_strict_miss_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    CountingModel.calls = 0
    model = CountingModel(messages=cycle([AIMessage(content="a")]))
    provider, exporter = _provider()
    graph = _graph(provider, model)

    def fake_fetch(api: str, path: str, timeout: float) -> Any:
        if path.endswith("/llm-calls"):
            return []  # no recorded responses → miss
        return {"input": {"x": 1}, "thread_id": None}

    monkeypatch.setattr("langops._replay._fetch_json", fake_fetch)
    with pytest.raises(Exception):  # noqa: B017,PT011 — StubMiss surfaces through the graph
        langops.replay(graph, "orig", stub_llm=True, on_miss="fail")
