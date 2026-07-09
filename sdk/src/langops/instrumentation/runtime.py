"""Per-run context shared between the graph wrapper and the checkpointer.

A ``ContextVar`` lets the (instrument-time) checkpointer wrapper find the
current execution's root span without threading it through LangGraph.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from opentelemetry.trace import Span

from langops import semconv
from langops.capture import redaction, state
from langops.config import LangOpsConfig


@dataclass
class RunContext:
    execution_id: str
    root_span: Span
    # Authoritative checkpoint lineage, filled in by the checkpointer wrapper.
    checkpoint_id: str | None = None
    parent_checkpoint_id: str | None = None
    # Stack of currently-executing node spans (for attributing log records to
    # the node that emitted them); empty → logs attach to the execution root.
    node_spans: list[Span] = field(default_factory=list)
    # Per-span log-event counts (keyed by id(span)) for the truncation guard.
    log_counts: dict[int, int] = field(default_factory=dict)

    @property
    def target_span(self) -> Span:
        """The innermost active node span, or the execution root."""
        return self.node_spans[-1] if self.node_spans else self.root_span


current_run: ContextVar[RunContext | None] = ContextVar("langops_current_run", default=None)


@dataclass(frozen=True)
class ReplayInfo:
    """Set by ``langops.replay`` so the graph wrapper stamps replay lineage."""

    replay_of: str
    overrides: dict[str, Any]


replay_context: ContextVar[ReplayInfo | None] = ContextVar("langops_replay", default=None)

# Set by the replay LLM cache when it serves (or misses) a recorded response,
# read by the callback handler to mark the LLM span as stubbed. Task-local, so
# concurrent nodes each see their own value.
llm_stub_served: ContextVar[bool | None] = ContextVar("langops_llm_stub_served", default=None)


def add_payload_event(
    span: Span,
    event_name: str,
    value: Any,
    config: LangOpsConfig,
    *,
    with_message_count: bool = False,
    extra_attributes: dict[str, Any] | None = None,
) -> None:
    """Attach a JSON payload to ``span`` as a span event (redacted + size-capped).

    Large payloads ride as events, not attributes, per the semantic
    conventions. ``extra_attributes`` are merged onto the event (e.g. log
    level/source). Never raises — capture failures must not break the run.
    """
    try:
        redacted = redaction.apply(value, config.redaction_hook)
        jsonable = state.to_jsonable(redacted)
        encoded, truncated, size = state.serialize(jsonable, config.max_payload_bytes)
        attributes: dict[str, Any] = {semconv.PAYLOAD: encoded, semconv.STATE_SIZE_BYTES: size}
        if truncated:
            attributes[semconv.TRUNCATED] = True
        if with_message_count:
            count = state.count_messages(jsonable)
            if count is not None:
                attributes[semconv.STATE_MESSAGE_COUNT] = count
        if extra_attributes:
            attributes.update(extra_attributes)
        span.add_event(event_name, attributes=attributes)
    except Exception:  # noqa: BLE001 — telemetry must never break the host graph
        return
