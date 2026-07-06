"""Token counts + catalog price → cost. Pricing comes in as data; no I/O here."""

from decimal import Decimal

from langops_api.domain.entities import ModelPricing
from langops_api.domain.value_objects import Cost, CostStatus, TokenUsage

ONE_MILLION = Decimal("1000000")
_CENTS = Decimal("0.000001")


class CostCalculator:
    def calculate(self, usage: TokenUsage, pricing: ModelPricing | None) -> Cost:
        """Cost of one LLM call, split by direction.

        Returns an ``UNKNOWN`` cost (amounts ``None``) when the model is not in
        the catalog — never a misleading ``$0`` (ADR-0002).
        """
        if pricing is None:
            return Cost.unknown()
        input_cost = (
            Decimal(usage.input_tokens) * pricing.input_price_per_1m / ONE_MILLION
        ).quantize(_CENTS)
        output_cost = (
            Decimal(usage.output_tokens) * pricing.output_price_per_1m / ONE_MILLION
        ).quantize(_CENTS)
        return Cost(
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=input_cost + output_cost,
            status=CostStatus.PRICED,
        )
