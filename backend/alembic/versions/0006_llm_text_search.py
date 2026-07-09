"""searchable LLM text content + trigram index (v0.1, Phase 17)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-08

Adds a flattened prompt+response text column on llm_calls with a pg_trgm GIN
index so "find the run where the model said X" is an indexed ILIKE. Postgres
only for the index (SQLite falls back to a plain LIKE scan in tests).
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_calls", sa.Column("text_content", sa.Text(), nullable=True))
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            "CREATE INDEX ix_llm_calls_text_content_trgm "
            "ON llm_calls USING gin (text_content gin_trgm_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_llm_calls_text_content_trgm")
    op.drop_column("llm_calls", "text_content")
