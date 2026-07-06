"""Canonical model-pricing seed data (single source of truth).

Both the Alembic migration and the dev/test `create_all` path seed from this
list, so the two never drift. USD per 1M tokens. Update prices by appending a
new row with a later ``effective_from`` (history is preserved; queries pick the
latest row <= call time).
"""

from datetime import UTC, datetime
from decimal import Decimal

# (provider, model, input_per_1m, output_per_1m)
DEFAULT_PRICING: list[tuple[str, str, str, str]] = [
    ("anthropic", "claude-opus-4-8", "5.00", "25.00"),
    ("anthropic", "claude-opus-4-7", "5.00", "25.00"),
    ("anthropic", "claude-sonnet-5", "3.00", "15.00"),
    ("anthropic", "claude-sonnet-4-6", "3.00", "15.00"),
    ("anthropic", "claude-haiku-4-5", "1.00", "5.00"),
    ("openai", "gpt-4o", "2.50", "10.00"),
    ("openai", "gpt-4o-mini", "0.15", "0.60"),
    ("openai", "gpt-4.1", "2.00", "8.00"),
    ("openai", "gpt-4.1-mini", "0.40", "1.60"),
    ("openai", "o3", "2.00", "8.00"),
    ("openai", "o4-mini", "1.10", "4.40"),
]

# Baseline date — early enough to price any observed call; newer prices are
# added as rows with a later effective_from.
DEFAULT_EFFECTIVE_FROM = datetime(2020, 1, 1, tzinfo=UTC)


async def seed_pricing(session) -> None:  # type: ignore[no-untyped-def]
    """Insert default pricing rows that are not already present.

    Used only by the dev/test `db_create_tables` path; production seeds the same
    data through the initial Alembic migration.
    """
    import sqlalchemy as sa
    from uuid6 import uuid7

    from langops_api.infrastructure.db.models import ModelPricingModel

    for provider, model, inp, out in DEFAULT_PRICING:
        exists = await session.scalar(
            sa.select(ModelPricingModel.id).where(
                ModelPricingModel.provider == provider,
                ModelPricingModel.model == model,
                ModelPricingModel.effective_from == DEFAULT_EFFECTIVE_FROM,
            )
        )
        if exists is None:
            session.add(
                ModelPricingModel(
                    id=uuid7(),
                    provider=provider,
                    model=model,
                    input_price_per_1m=Decimal(inp),
                    output_price_per_1m=Decimal(out),
                    effective_from=DEFAULT_EFFECTIVE_FROM,
                )
            )
    await session.commit()
