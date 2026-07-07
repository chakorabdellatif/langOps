"""per-node category + rollups (v0.2, Phase 9)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-07

Adds node-level category and cost/token rollups. All columns are nullable or
defaulted so pre-0.2 rows backfill lazily (the API renders "utility"/"—" for
NULLs); no data migration required.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("node_executions", sa.Column("category", sa.Text(), nullable=True))
    op.add_column(
        "node_executions",
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "node_executions",
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("node_executions", sa.Column("total_cost", sa.Numeric(12, 6), nullable=True))
    op.add_column(
        "node_executions",
        sa.Column("cost_status", sa.Text(), nullable=False, server_default="unknown"),
    )


def downgrade() -> None:
    for column in ("cost_status", "total_cost", "output_tokens", "input_tokens", "category"):
        op.drop_column("node_executions", column)
