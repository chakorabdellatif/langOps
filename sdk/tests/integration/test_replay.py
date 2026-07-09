"""Phase 12 — execution replay (R1 exact + R2 overrides)."""

from typing import TypedDict

import pytest
from langgraph.graph import END, START, StateGraph
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import langops
from langops import semconv
from langops._replay import ReplayError


class State(TypedDict):
    x: int


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _graph(provider: TracerProvider):
    graph = StateGraph(State)
    graph.add_node("double", lambda s: {"x": s["x"] * 2})
    graph.add_edge(START, "double")
    graph.add_edge("double", END)
    return langops.instrument(graph.compile(), tracer_provider=provider)


def _root(exporter: InMemorySpanExporter):
    return next(
        s for s in exporter.get_finished_spans() if s.attributes.get(semconv.KIND) == "execution"
    )


def test_exact_replay_reruns_recorded_input(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, exporter = _provider()
    graph = _graph(provider)

    monkeypatch.setattr(
        "langops._replay._fetch_execution",
        lambda *a, **k: {"input": {"x": 5}, "thread_id": None},
    )
    result = langops.replay(graph, "orig-123")

    assert result == {"x": 10}  # replayed the recorded input {x:5}
    root = _root(exporter)
    assert root.attributes[semconv.EXECUTION_REPLAY_OF] == "orig-123"


def test_replay_with_overrides_records_them(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, exporter = _provider()
    graph = _graph(provider)

    monkeypatch.setattr(
        "langops._replay._fetch_execution",
        lambda *a, **k: {"input": {"x": 1}, "thread_id": None},
    )
    result = langops.replay(graph, "orig-9", input={"x": 100}, model="gpt-5", temperature=0.2)

    assert result == {"x": 200}  # ran the override input {x:100}
    root = _root(exporter)
    overrides_event = next(e for e in root.events if e.name == semconv.EVENT_EXECUTION_OVERRIDES)
    import json

    overrides = json.loads(overrides_event.attributes[semconv.PAYLOAD])
    assert overrides["model"] == "gpt-5"
    assert overrides["temperature"] == 0.2
    assert overrides["input"] == "custom"


def test_truncated_input_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, _ = _provider()
    graph = _graph(provider)
    monkeypatch.setattr(
        "langops._replay._fetch_execution",
        lambda *a, **k: {"input": {"langops.truncated": True}, "thread_id": None},
    )
    with pytest.raises(ReplayError, match="truncated"):
        langops.replay(graph, "orig-x")
