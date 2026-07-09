"""SDK configuration.

All fields have working defaults; `instrument(graph)` with no config must
work against a local `docker compose up` stack.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Applied to every captured payload before it reaches the exporter;
# secrets must never leave the process.
RedactionHook = Callable[[Any], Any]


@dataclass(frozen=True)
class LangOpsConfig:
    """Configuration for :func:`langops.instrument`."""

    endpoint: str = "http://localhost:4317"
    service_name: str = "langgraph-app"
    graph_name: str | None = None  # defaults to the LangGraph graph name
    project: str = "default"
    # Optional API key sent as an OTLP `authorization: Bearer <key>` header,
    # for a backend/collector protected by LANGOPS_API_KEY. Falls back to the
    # LANGOPS_API_KEY environment variable when unset.
    api_key: str | None = None

    # Capture toggles
    capture_state: bool = True
    capture_llm_payloads: bool = True
    capture_tool_payloads: bool = True
    # Opt-in: bridge stdlib `logging` records into the trace as langops.log
    # events on the active node/execution span (off by default — zero cost).
    capture_logs: bool = False
    # Cap on log events recorded per span before a single truncation marker is
    # emitted (kept under OTel's default 128-event-per-span limit so captured
    # logs are never *silently* dropped).
    max_logs_per_span: int = 100

    # Limits & privacy
    max_payload_bytes: int = 65_536
    redaction_hook: RedactionHook | None = None
    sampling_ratio: float = 1.0
