"""replay lineage (v0.2, Phase 12)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-07

Links a replayed execution to the original it re-ran, and records the overrides
that were applied. Plain indexed UUID (no FK) so deleting an original never
blocks or cascades into its replays.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "executions", sa.Column("replay_of_execution_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "executions", sa.Column("replay_overrides", postgresql.JSONB(), nullable=True)
    )
    op.create_index(
        "ix_executions_replay_of", "executions", ["replay_of_execution_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_executions_replay_of", table_name="executions")
    op.drop_column("executions", "replay_overrides")
    op.drop_column("executions", "replay_of_execution_id")
