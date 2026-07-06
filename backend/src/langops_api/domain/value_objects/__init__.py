"""Immutable value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class ExecutionStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


@dataclass(frozen=True)
class StateDiff:
    """Structural difference between two JSON-like states."""

    added: dict[str, Any] = field(default_factory=dict)
    modified: dict[str, Any] = field(default_factory=dict)  # key -> {"old": ..., "new": ...}
    removed: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.modified or self.removed)

    def to_dict(self) -> dict[str, Any]:
        return {"added": self.added, "modified": self.modified, "removed": self.removed}


@dataclass(frozen=True)
class CheckpointRef:
    """LangGraph thread/checkpoint linkage for an execution."""

    thread_id: str | None = None
    checkpoint_id: str | None = None
    parent_checkpoint_id: str | None = None
    resumed: bool = False


ZERO_COST = Decimal("0")
