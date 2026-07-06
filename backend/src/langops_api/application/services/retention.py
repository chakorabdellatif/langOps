"""Retention: delete executions older than a cutoff (single cascade delete)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from langops_api.domain.repositories import ExecutionRepository


class RetentionService:
    def __init__(self, executions: ExecutionRepository) -> None:
        self._executions = executions

    async def purge_older_than(self, days: int, *, now: datetime | None = None) -> int:
        """Delete executions started more than ``days`` ago; returns the count."""
        cutoff = (now or datetime.now(tz=UTC)) - timedelta(days=days)
        return await self._executions.delete_older_than(cutoff)
