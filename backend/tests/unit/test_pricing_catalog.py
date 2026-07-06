"""JSON pricing catalog (ADR-0002): effective-dating, prefix match, reload."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from langops_api.infrastructure.pricing import PricingCatalog


@pytest.mark.asyncio
async def test_prices_known_models() -> None:
    catalog = PricingCatalog()

    opus = await catalog.get_price("anthropic", "claude-opus-4-8")
    assert opus is not None
    assert opus.input_price_per_1m == Decimal("5.0")
    assert opus.output_price_per_1m == Decimal("25.0")

    # Local models are priced at zero, not unknown.
    llama = await catalog.get_price("ollama", "llama3.1")
    assert llama is not None
    assert llama.input_price_per_1m == Decimal("0.0")


@pytest.mark.asyncio
async def test_unknown_model_returns_none() -> None:
    catalog = PricingCatalog()
    assert await catalog.get_price("acme", "my-private-model-v3") is None


@pytest.mark.asyncio
async def test_prefix_match_for_dated_variant() -> None:
    # A dated snapshot resolves to its base model via longest-prefix match.
    catalog = PricingCatalog()
    priced = await catalog.get_price("openai", "gpt-4.1-2025-04-14")
    assert priced is not None
    assert priced.model == "gpt-4.1"
    assert priced.input_price_per_1m == Decimal("2.0")


@pytest.mark.asyncio
async def test_effective_dating_falls_back_to_earliest() -> None:
    # A call before any effective_from still gets priced (earliest entry).
    catalog = PricingCatalog()
    priced = await catalog.get_price("openai", "gpt-4.1", at=datetime(2020, 1, 1, tzinfo=UTC))
    assert priced is not None
    assert priced.input_price_per_1m == Decimal("2.0")


@pytest.mark.asyncio
async def test_reload_is_idempotent() -> None:
    catalog = PricingCatalog()
    before = await catalog.get_price("anthropic", "claude-opus-4-8")
    catalog.reload()
    after = await catalog.get_price("anthropic", "claude-opus-4-8")
    assert before == after
