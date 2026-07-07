"""Pure ExecutionComparator tests — deterministic, no I/O, no LLM."""

from decimal import Decimal

from langops_api.domain.services import ExecutionComparator
from langops_api.domain.services.execution_comparator import (
    ComparisonInput,
    LlmStat,
    NodeStat,
)


def _input(**overrides: object) -> ComparisonInput:
    base = dict(
        status="succeeded",
        duration_ms=1000,
        total_tokens=100,
        total_cost=Decimal("0.001"),
        topology_hash="h1",
        context_size_bytes=1000,
        nodes=[NodeStat("plan", 1, 0, 100, "llm"), NodeStat("act", 2, 0, 200, "tool")],
        llm_calls=[LlmStat("gpt-4o-mini", 0.3, 100, 50)],
        tool_call_count=2,
    )
    base.update(overrides)
    return ComparisonInput(**base)  # type: ignore[arg-type]


def test_identical_runs_have_no_changes() -> None:
    result = ExecutionComparator().compare(_input(), _input())
    ec = result.execution_changes
    assert not ec.nodes_added and not ec.nodes_removed
    assert not ec.order_changed and not ec.topology_changed
    assert not ec.retries_added
    assert result.insights == []


def test_detects_added_node_and_topology_change() -> None:
    b = _input(
        topology_hash="h2",
        nodes=[
            NodeStat("plan", 1, 0, 100, "llm"),
            NodeStat("act", 2, 0, 200, "tool"),
            NodeStat("review", 3, 0, 50, "llm"),
        ],
    )
    result = ExecutionComparator().compare(_input(), b)
    assert result.execution_changes.nodes_added == ["review"]
    assert result.execution_changes.topology_changed
    metrics = {i.metric for i in result.insights}
    assert "topology" in metrics and "nodes" in metrics


def test_detects_retry_added() -> None:
    b = _input(nodes=[NodeStat("plan", 1, 2, 100, "llm"), NodeStat("act", 2, 0, 200, "tool")])
    result = ExecutionComparator().compare(_input(), b)
    assert result.execution_changes.retries_added == ["plan"]
    assert any(i.metric == "retries" and i.severity == "bad" for i in result.insights)


def test_detects_slower_execution() -> None:
    result = ExecutionComparator().compare(_input(duration_ms=1000), _input(duration_ms=2000))
    assert result.performance.duration.delta_pct == 100.0
    assert any(i.metric == "duration" and i.severity == "bad" for i in result.insights)


def test_unknown_cost_is_incomparable_not_zero() -> None:
    result = ExecutionComparator().compare(
        _input(total_cost=Decimal("0.01")), _input(total_cost=None)
    )
    assert result.performance.cost.comparable is False
    # No misleading cost insight when one side is unpriced.
    assert not any(i.metric == "cost" for i in result.insights)


def test_detects_model_and_tool_call_changes() -> None:
    a = _input(llm_calls=[LlmStat("gpt-4o-mini", 0.3, 100, 50)], tool_call_count=2)
    b = _input(llm_calls=[LlmStat("gpt-5", 0.3, 100, 50)], tool_call_count=5)
    result = ExecutionComparator().compare(a, b)
    assert result.llm_changes.model_changed
    assert result.llm_changes.tool_calls.delta == 3.0
    metrics = {i.metric for i in result.insights}
    assert "model" in metrics and "tool_calls" in metrics


def test_node_latency_spike_insight() -> None:
    a = _input(nodes=[NodeStat("summary", 1, 0, 100, "llm")])
    b = _input(nodes=[NodeStat("summary", 1, 0, 171, "llm")])
    result = ExecutionComparator().compare(a, b)
    spike = next(i for i in result.insights if i.metric == "node_latency")
    assert "summary" in spike.text and "71%" in spike.text
