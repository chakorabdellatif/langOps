"""initial schema + model pricing seed

Revision ID: 0001
Revises:
Create Date: 2026-07-06

Full telemetry schema per docs/architecture.md §4. JSONB payloads on Postgres;
typed columns for everything queried/aggregated. Seeds current model pricing.
"""

from decimal import Decimal

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "graphs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("topology", JSONB, nullable=True),
        sa.Column("topology_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name", "topology_hash", name="uq_graphs_topology"),
    )

    op.create_table(
        "executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("graph_id", sa.Uuid(), sa.ForeignKey("graphs.id"), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=False, unique=True),
        sa.Column("thread_id", sa.Text(), nullable=True),
        sa.Column("checkpoint_id", sa.Text(), nullable=True),
        sa.Column("parent_checkpoint_id", sa.Text(), nullable=True),
        sa.Column("resumed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("error", JSONB, nullable=True),
        sa.Column("input", JSONB, nullable=True),
        sa.Column("output", JSONB, nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("total_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("sdk_version", sa.Text(), nullable=True),
    )
    op.create_index("ix_executions_project_started", "executions", ["project_id", "started_at"])
    op.create_index("ix_executions_thread_started", "executions", ["thread_id", "started_at"])
    op.create_index("ix_executions_graph_started", "executions", ["graph_id", "started_at"])
    op.create_index("ix_executions_status", "executions", ["status"])

    op.create_table(
        "node_executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "execution_id",
            sa.Uuid(),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("span_id", sa.Text(), nullable=False, unique=True),
        sa.Column("parent_span_id", sa.Text(), nullable=True),
        sa.Column("node_name", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="succeeded"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", JSONB, nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_node_executions_execution_sequence", "node_executions", ["execution_id", "sequence"]
    )
    op.create_index(
        "ix_node_executions_name_started", "node_executions", ["node_name", "started_at"]
    )

    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "node_execution_id",
            sa.Uuid(),
            sa.ForeignKey("node_executions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "execution_id",
            sa.Uuid(),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("span_id", sa.Text(), nullable=False, unique=True),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("messages", JSONB, nullable=True),
        sa.Column("params", JSONB, nullable=True),
        sa.Column("response", JSONB, nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error", JSONB, nullable=True),
    )
    op.create_index("ix_llm_calls_execution", "llm_calls", ["execution_id"])
    op.create_index("ix_llm_calls_model_started", "llm_calls", ["model", "started_at"])

    op.create_table(
        "tool_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "node_execution_id",
            sa.Uuid(),
            sa.ForeignKey("node_executions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "execution_id",
            sa.Uuid(),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("span_id", sa.Text(), nullable=False, unique=True),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("input", JSONB, nullable=True),
        sa.Column("output", JSONB, nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="succeeded"),
        sa.Column("error", JSONB, nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_tool_calls_execution", "tool_calls", ["execution_id"])

    op.create_table(
        "state_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "execution_id",
            sa.Uuid(),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "node_execution_id",
            sa.Uuid(),
            sa.ForeignKey("node_executions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("state", JSONB, nullable=True),
        sa.Column("diff", JSONB, nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_state_snapshots_execution_created", "state_snapshots", ["execution_id", "created_at"]
    )

    op.create_table(
        "logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "execution_id",
            sa.Uuid(),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "node_execution_id",
            sa.Uuid(),
            sa.ForeignKey("node_executions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("level", sa.Text(), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("attributes", JSONB, nullable=True),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_logs_execution_timestamp", "logs", ["execution_id", "timestamp"])
    op.create_index("ix_logs_level_timestamp", "logs", ["level", "timestamp"])

    op.create_table(
        "model_pricing",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_price_per_1m", sa.Numeric(12, 6), nullable=False),
        sa.Column("output_price_per_1m", sa.Numeric(12, 6), nullable=False),
        sa.Column("effective_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "model", "effective_from", name="uq_model_pricing"),
    )

    _seed_pricing()


def _seed_pricing() -> None:
    from uuid6 import uuid7

    from langops_api.infrastructure.db.pricing_seed import (
        DEFAULT_EFFECTIVE_FROM,
        DEFAULT_PRICING,
    )

    rows = [
        {
            "id": uuid7(),
            "provider": provider,
            "model": model,
            "input_price_per_1m": Decimal(inp),
            "output_price_per_1m": Decimal(out),
            "effective_from": DEFAULT_EFFECTIVE_FROM,
        }
        for provider, model, inp, out in DEFAULT_PRICING
    ]
    op.bulk_insert(
        sa.table(
            "model_pricing",
            sa.column("id", sa.Uuid()),
            sa.column("provider", sa.Text()),
            sa.column("model", sa.Text()),
            sa.column("input_price_per_1m", sa.Numeric(12, 6)),
            sa.column("output_price_per_1m", sa.Numeric(12, 6)),
            sa.column("effective_from", sa.TIMESTAMP(timezone=True)),
        ),
        rows,
    )


def downgrade() -> None:
    for table in (
        "model_pricing",
        "logs",
        "state_snapshots",
        "tool_calls",
        "llm_calls",
        "node_executions",
        "executions",
        "graphs",
        "projects",
    ):
        op.drop_table(table)
