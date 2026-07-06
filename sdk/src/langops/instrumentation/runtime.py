"""Per-run context shared between the graph wrapper and the checkpointer.

A ``ContextVar`` lets the (instrument-time) checkpointer wrapper find the
current execution's root span without threading it through LangGraph.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
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


current_run: ContextVar[RunContext | None] = ContextVar("langops_current_run", default=None)


def add_payload_event(
    span: Span,
    event_name: str,
    value: Any,
    config: LangOpsConfig,
    *,
    with_message_count: bool = False,
) -> None:
    """Attach a JSON payload to ``span`` as a span event (redacted + size-capped).

    Large payloads ride as events, not attributes, per the semantic
    conventions. Never raises — capture failures must not break the run.
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
        span.add_event(event_name, attributes=attributes)
    except Exception:  # noqa: BLE001 — telemetry must never break the host graph
        return
