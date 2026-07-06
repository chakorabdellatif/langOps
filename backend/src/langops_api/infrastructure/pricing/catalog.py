"""In-memory pricing catalog loaded from per-provider JSON files (ADR-0002).

Implements the domain ``PricingRepository`` protocol. Built-in prices ship in
this package; an optional ``PRICING_CATALOG_DIR`` adds user files (same shape)
that extend or override the built-ins. Supports:

- effective-dating (multiple entries per model, chosen by call time),
- prefix matching for dated model variants (``gpt-4.1-2025-04-14`` → ``gpt-4.1``),
- ``reload()`` to pick up edited JSON without a restart,
- custom/local models via ``custom.json`` or an extra directory.

Unknown models return ``None`` — the caller records ``cost_status: "unknown"``,
never a misleading ``$0``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from langops_api.domain.entities import ModelPricing

logger = logging.getLogger(__name__)

_BUILTIN_DIR = Path(__file__).parent
_MIN_DATE = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class _PriceEntry:
    input_per_1m: Decimal
    output_per_1m: Decimal
    effective_from: datetime


class PricingCatalog:
    """Price lookups from the JSON catalog. Unknown models return ``None``."""

    def __init__(self, extra_dir: str | None = None) -> None:
        self._extra_dir = extra_dir
        # (provider, model_name) -> entries sorted by effective_from ascending.
        self._prices: dict[tuple[str, str], list[_PriceEntry]] = {}
        self.reload()

    # Kept for the previous constructor name used in composition/tests.
    @classmethod
    def load(cls, extra_dir: str | None = None) -> PricingCatalog:
        return cls(extra_dir)

    def reload(self) -> None:
        """Re-read every JSON file (built-ins + optional extra dir)."""
        prices: dict[tuple[str, str], list[_PriceEntry]] = {}
        self._load_dir(_BUILTIN_DIR, prices)
        if self._extra_dir:
            self._load_dir(Path(self._extra_dir), prices)
        for entries in prices.values():
            entries.sort(key=lambda e: e.effective_from)
        self._prices = prices
        logger.info("loaded pricing for %d models", len(prices))

    @staticmethod
    def _load_dir(directory: Path, prices: dict[tuple[str, str], list[_PriceEntry]]) -> None:
        if not directory.is_dir():
            return
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                provider = data["provider"]
                for entry in data["models"]:
                    key = (provider, entry["name"])
                    prices.setdefault(key, []).append(
                        _PriceEntry(
                            input_per_1m=Decimal(str(entry["input"])),
                            output_per_1m=Decimal(str(entry["output"])),
                            effective_from=_parse_date(entry.get("effective_from")),
                        )
                    )
            except (OSError, ValueError, KeyError, TypeError):
                logger.warning("skipping malformed pricing file: %s", path.name)

    async def get_price(
        self, provider: str, model: str, at: datetime | None = None
    ) -> ModelPricing | None:
        entries, matched_name = self._match(provider, model)
        if not entries:
            return None
        entry = self._effective(entries, at or datetime.now(tz=UTC))
        return ModelPricing(
            provider=provider,
            model=matched_name,
            input_price_per_1m=entry.input_per_1m,
            output_price_per_1m=entry.output_per_1m,
        )

    def _match(self, provider: str, model: str) -> tuple[list[_PriceEntry], str]:
        exact = self._prices.get((provider, model))
        if exact:
            return exact, model
        # Longest-prefix match for dated variants (e.g. gpt-4.1-2025-04-14).
        best_name = ""
        for prov, name in self._prices:
            if prov == provider and model.startswith(name) and len(name) > len(best_name):
                best_name = name
        if best_name:
            return self._prices[(provider, best_name)], best_name
        return [], model

    @staticmethod
    def _effective(entries: list[_PriceEntry], at: datetime) -> _PriceEntry:
        # Latest entry effective on or before `at`; fall back to the earliest.
        applicable = [e for e in entries if e.effective_from <= at]
        return applicable[-1] if applicable else entries[0]


def _parse_date(value: str | None) -> datetime:
    if not value:
        return _MIN_DATE
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


# Backwards-compatible alias (previous name).
CatalogPricingRepository = PricingCatalog
