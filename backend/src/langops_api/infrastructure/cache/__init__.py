"""Redis adapters: execution-update pub/sub (dashboard live updates).

Telemetry must never fail because Redis is down — publishing is best-effort
and degrades to a logged warning.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

EVENTS_CHANNEL = "langops:events"


class RedisEventPublisher:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._warned = False

    async def publish(self, event: dict[str, Any]) -> None:
        try:
            await self._redis.publish(EVENTS_CHANNEL, json.dumps(event, default=str))
        except Exception:  # noqa: BLE001 — best-effort by design
            if not self._warned:
                logger.warning("Redis unavailable; execution events will not be published")
                self._warned = True


class NullEventPublisher:
    """Used when Redis is not configured (tests)."""

    async def publish(self, event: dict[str, Any]) -> None:
        return None
