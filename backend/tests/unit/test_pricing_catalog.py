"""JSON pricing catalog (ADR-0002)."""

from decimal import Decimal

import pytest

from langops_api.infrastructure.pricing import CatalogPricingRepository


@pytest.mark.asyncio
async def test_catalog_prices_known_models() -> None:
    catalog = CatalogPricingRepository.load()

    opus = await catalog.get_price("anthropic", "claude-opus-4-8")
    assert opus is not None
    assert opus.input_price_per_1m == Decimal("5.0")
    assert opus.output_price_per_1m == Decimal("25.0")

    # Local models are priced at zero, not unknown.
    llama = await catalog.get_price("ollama", "llama3.1")
    assert llama is not None
    assert llama.input_price_per_1m == Decimal("0.0")


@pytest.mark.asyncio
async def test_catalog_returns_none_for_unknown_model() -> None:
    catalog = CatalogPricingRepository.load()
    assert await catalog.get_price("acme", "my-private-model-v3") is None
