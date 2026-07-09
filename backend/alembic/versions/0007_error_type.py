"""indexed error_type for failure analytics (v0.1, Phase 18)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-08

Extracts the exception type from the error JSON into an indexed column on
executions and node_executions so "TimeoutError in weather ×12 this week" is a
grouped, indexed query. Backfills existing rows from the stored error JSON.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("executions", "node_executions"):
        op.add_column(table, sa.Column("error_type", sa.Text(), nullable=True))
        op.create_index(f"ix_{table}_error_type", table, ["error_type"])

    # Backfill from the error JSON's "type" field (Postgres JSONB accessor).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("executions", "node_executions"):
            op.execute(
                f"UPDATE {table} SET error_type = error->>'type' "
                f"WHERE error IS NOT NULL AND error->>'type' IS NOT NULL"
            )


def downgrade() -> None:
    for table in ("executions", "node_executions"):
        op.drop_index(f"ix_{table}_error_type", table_name=table)
        op.drop_column(table, "error_type")
