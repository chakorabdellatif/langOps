"""Token counts + pricing → cost. Pricing comes in as data; no I/O here."""

from decimal import Decimal

from langops_api.domain.entities import ModelPricing
from langops_api.domain.value_objects import ZERO_COST, TokenUsage

ONE_MILLION = Decimal("1000000")


class CostCalculator:
    def calculate(self, usage: TokenUsage, pricing: ModelPricing | None) -> Decimal:
        """Cost in USD for one LLM call; zero when the model is not priced."""
        if pricing is None:
            return ZERO_COST
        input_cost = Decimal(usage.input_tokens) * pricing.input_price_per_1m / ONE_MILLION
        output_cost = Decimal(usage.output_tokens) * pricing.output_price_per_1m / ONE_MILLION
        return (input_cost + output_cost).quantize(Decimal("0.000001"))
