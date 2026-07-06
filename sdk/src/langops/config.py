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

    # Capture toggles
    capture_state: bool = True
    capture_llm_payloads: bool = True
    capture_tool_payloads: bool = True

    # Limits & privacy
    max_payload_bytes: int = 65_536
    redaction_hook: RedactionHook | None = None
    sampling_ratio: float = 1.0
