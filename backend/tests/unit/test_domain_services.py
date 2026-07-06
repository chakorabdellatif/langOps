"""Pure domain-service tests — no I/O."""

from decimal import Decimal

from langops_api.domain.entities import ModelPricing
from langops_api.domain.services import CostCalculator, StateDiffer
from langops_api.domain.value_objects import CostStatus, TokenUsage


def _pricing(inp: str, out: str) -> ModelPricing:
    return ModelPricing(
        provider="anthropic",
        model="claude-opus-4-8",
        input_price_per_1m=Decimal(inp),
        output_price_per_1m=Decimal(out),
    )


def test_cost_calculator_splits_and_totals() -> None:
    cost = CostCalculator().calculate(
        TokenUsage(input_tokens=1_000_000, output_tokens=500_000),
        _pricing("5.00", "25.00"),
    )
    # 1M input * $5 = 5, 0.5M output * $25 = 12.5
    assert cost.input_cost == Decimal("5.000000")
    assert cost.output_cost == Decimal("12.500000")
    assert cost.total_cost == Decimal("17.500000")
    assert cost.status is CostStatus.PRICED


def test_cost_calculator_unknown_when_unpriced() -> None:
    # Unknown models are never priced at $0 (ADR-0002).
    cost = CostCalculator().calculate(TokenUsage(100, 100), pricing=None)
    assert cost.status is CostStatus.UNKNOWN
    assert cost.total_cost is None


def test_state_differ_detects_added_modified_removed() -> None:
    diff = StateDiffer().diff(
        {"a": 1, "b": 2, "c": 3},
        {"b": 2, "c": 99, "d": 4},
    )
    assert diff.added == {"d": 4}
    assert diff.removed == ["a"]
    assert diff.modified == {"c": {"old": 3, "new": 99}}


def test_state_differ_empty_when_unchanged() -> None:
    diff = StateDiffer().diff({"a": 1}, {"a": 1})
    assert diff.is_empty
