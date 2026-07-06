"""In-memory pricing catalog loaded from per-provider JSON files (ADR-0002).

Implements the domain ``PricingRepository`` protocol. Built-in prices ship in
this package; an optional ``PRICING_CATALOG_DIR`` adds user files (same shape)
that extend or override the built-ins. Loaded once at startup.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from pathlib import Path

from langops_api.domain.entities import ModelPricing

logger = logging.getLogger(__name__)

_BUILTIN_DIR = Path(__file__).parent


class CatalogPricingRepository:
    """Price lookups from the JSON catalog. Unknown models return ``None``."""

    def __init__(self, prices: dict[tuple[str, str], ModelPricing]) -> None:
        self._prices = prices

    @classmethod
    def load(cls, extra_dir: str | None = None) -> CatalogPricingRepository:
        prices: dict[tuple[str, str], ModelPricing] = {}
        cls._load_dir(_BUILTIN_DIR, prices)
        if extra_dir:
            cls._load_dir(Path(extra_dir), prices)  # user files override built-ins
        logger.info("loaded pricing for %d models", len(prices))
        return cls(prices)

    @staticmethod
    def _load_dir(directory: Path, prices: dict[tuple[str, str], ModelPricing]) -> None:
        if not directory.is_dir():
            return
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                provider = data["provider"]
                for model, entry in data["models"].items():
                    prices[(provider, model)] = ModelPricing(
                        provider=provider,
                        model=model,
                        input_price_per_1m=Decimal(str(entry["input"])),
                        output_price_per_1m=Decimal(str(entry["output"])),
                    )
            except (OSError, ValueError, KeyError):
                logger.warning("skipping malformed pricing file: %s", path.name)

    async def get_price(self, provider: str, model: str) -> ModelPricing | None:
        return self._prices.get((provider, model))
