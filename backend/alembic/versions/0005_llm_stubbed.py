"""cached-replay stubbed flag on llm_calls (v0.1, Phase 15)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-08

Marks LLM calls whose response was served from a recording during a cached
replay; these cost nothing and are excluded from cost rollups.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "llm_calls", sa.Column("stubbed", sa.Boolean(), nullable=False, server_default=sa.false())
    )


def downgrade() -> None:
    op.drop_column("llm_calls", "stubbed")
