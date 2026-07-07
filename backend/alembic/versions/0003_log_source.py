"""log source + logger name (v0.2, Phase 11)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-07

Classifies each log row by origin channel and records the logger name. Existing
exception-derived rows are backfilled to source ``exception``.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "logs", sa.Column("source", sa.Text(), nullable=False, server_default="app")
    )
    op.add_column("logs", sa.Column("logger", sa.Text(), nullable=True))
    # Existing rows are all exception-derived (the only prior log source).
    op.execute("UPDATE logs SET source = 'exception'")
    op.create_index("ix_logs_source", "logs", ["source"])


def downgrade() -> None:
    op.drop_index("ix_logs_source", table_name="logs")
    op.drop_column("logs", "logger")
    op.drop_column("logs", "source")
