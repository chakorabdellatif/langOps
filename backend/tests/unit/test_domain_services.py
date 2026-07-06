"""Pure domain-service tests — no I/O."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from langops_api.domain.entities import ModelPricing
from langops_api.domain.services import CostCalculator, StateDiffer
from langops_api.domain.value_objects import TokenUsage


def _pricing(inp: str, out: str) -> ModelPricing:
    return ModelPricing(
        id=uuid4(),
        provider="anthropic",
        model="claude-opus-4-8",
        input_price_per_1m=Decimal(inp),
        output_price_per_1m=Decimal(out),
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_cost_calculator_multiplies_tokens_by_price() -> None:
    cost = CostCalculator().calculate(
        TokenUsage(input_tokens=1_000_000, output_tokens=500_000),
        _pricing("5.00", "25.00"),
    )
    # 1M input * $5 + 0.5M output * $25 = 5 + 12.5
    assert cost == Decimal("17.500000")


def test_cost_calculator_zero_when_unpriced() -> None:
    cost = CostCalculator().calculate(TokenUsage(100, 100), pricing=None)
    assert cost == Decimal("0")


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
