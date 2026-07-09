"""SQLAlchemy ORM models — persistence shape only, separate from domain entities.

Types are portable: JSONB/typed columns on Postgres, plain JSON on SQLite so
the API test suite can run without a database server. Alembic migrations
target Postgres only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


class Base(DeclarativeBase):
    type_annotation_map = {
        dict[str, Any]: JSONType,
        Any: JSONType,
    }


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(sa.Text)
    slug: Mapped[str] = mapped_column(sa.Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True))


class GraphModel(Base):
    __tablename__ = "graphs"
    __table_args__ = (
        sa.UniqueConstraint("project_id", "name", "topology_hash", name="uq_graphs_topology"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(sa.Text)
    topology: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    topology_hash: Mapped[str] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True))


class ExecutionModel(Base):
    __tablename__ = "executions"
    __table_args__ = (
        sa.Index("ix_executions_project_started", "project_id", "started_at"),
        sa.Index("ix_executions_thread_started", "thread_id", "started_at"),
        sa.Index("ix_executions_graph_started", "graph_id", "started_at"),
        sa.Index("ix_executions_replay_of", "replay_of_execution_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("projects.id"))
    graph_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("graphs.id"), nullable=True)
    trace_id: Mapped[str] = mapped_column(sa.Text, unique=True)
    thread_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    checkpoint_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    parent_checkpoint_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    resumed: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    status: Mapped[str] = mapped_column(sa.Text, default="running", index=True)
    error: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    input: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    output: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    total_input_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    total_cost: Mapped[Decimal] = mapped_column(sa.Numeric(12, 6), default=Decimal("0"))
    sdk_version: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # v0.2 replay lineage (plain UUID, no FK — see migration 0004).
    replay_of_execution_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, nullable=True)
    replay_overrides: Mapped[Any | None] = mapped_column(JSONType, nullable=True)


class NodeExecutionModel(Base):
    __tablename__ = "node_executions"
    __table_args__ = (
        sa.Index("ix_node_executions_execution_sequence", "execution_id", "sequence"),
        sa.Index("ix_node_executions_name_started", "node_name", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("executions.id", ondelete="CASCADE")
    )
    span_id: Mapped[str] = mapped_column(sa.Text, unique=True)
    parent_span_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    node_name: Mapped[str] = mapped_column(sa.Text)
    sequence: Mapped[int] = mapped_column(sa.Integer, default=0)
    status: Mapped[str] = mapped_column(sa.Text, default="succeeded")
    retry_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    error: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    # v0.2: category + per-node rollups (recomputed from child llm_calls).
    category: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    input_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    # NULL when any child LLM call is unpriced (ADR-0002 — never $0).
    total_cost: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 6), nullable=True)
    cost_status: Mapped[str] = mapped_column(sa.Text, default="unknown")


class LlmCallModel(Base):
    __tablename__ = "llm_calls"
    __table_args__ = (
        sa.Index("ix_llm_calls_execution", "execution_id"),
        sa.Index("ix_llm_calls_model_started", "model", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    node_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("node_executions.id", ondelete="CASCADE"), nullable=True
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("executions.id", ondelete="CASCADE")
    )
    span_id: Mapped[str] = mapped_column(sa.Text, unique=True)
    provider: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    model: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    messages: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    params: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    response: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    input_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    # Cost split by direction; NULL when the model is unpriced (ADR-0002).
    input_cost: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 6), nullable=True)
    output_cost: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 6), nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 6), nullable=True)
    cost_status: Mapped[str] = mapped_column(sa.Text, default="unknown")
    latency_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    error: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    # v0.1 cached replay: served from a recording (excluded from cost).
    stubbed: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    # Flattened prompt+response text for full-text search (pg_trgm on Postgres).
    text_content: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class ToolCallModel(Base):
    __tablename__ = "tool_calls"
    __table_args__ = (sa.Index("ix_tool_calls_execution", "execution_id"),)

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    node_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("node_executions.id", ondelete="CASCADE"), nullable=True
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("executions.id", ondelete="CASCADE")
    )
    span_id: Mapped[str] = mapped_column(sa.Text, unique=True)
    tool_name: Mapped[str] = mapped_column(sa.Text)
    input: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    output: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    status: Mapped[str] = mapped_column(sa.Text, default="succeeded")
    error: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)


class StateSnapshotModel(Base):
    __tablename__ = "state_snapshots"
    __table_args__ = (
        sa.Index("ix_state_snapshots_execution_created", "execution_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("executions.id", ondelete="CASCADE")
    )
    node_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("node_executions.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(sa.Text)
    state: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    diff: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    size_bytes: Mapped[int] = mapped_column(sa.Integer, default=0)
    message_count: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)


class LogModel(Base):
    __tablename__ = "logs"
    __table_args__ = (
        sa.Index("ix_logs_execution_timestamp", "execution_id", "timestamp"),
        sa.Index("ix_logs_level_timestamp", "level", "timestamp"),
        sa.Index("ix_logs_source", "source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("executions.id", ondelete="CASCADE")
    )
    node_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("node_executions.id", ondelete="CASCADE"), nullable=True
    )
    level: Mapped[str] = mapped_column(sa.Text, default="info")
    # v0.2: origin channel (app | sdk | llm | tool | exception).
    source: Mapped[str] = mapped_column(sa.Text, default="app")
    logger: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    message: Mapped[str] = mapped_column(sa.Text)
    stack_trace: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    attributes: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)


# Model pricing lives in the JSON catalog (infrastructure/pricing/), not the DB
# (ADR-0002) — there is no model_pricing table.
