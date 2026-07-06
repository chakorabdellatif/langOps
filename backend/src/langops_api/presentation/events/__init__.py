"""Server-Sent Events endpoint bridging Redis pub/sub to the dashboard.

One-directional live updates: the dashboard opens this stream and invalidates
its TanStack Query caches when an `execution.updated` event arrives.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from langops_api.composition import Container, get_container

router = APIRouter(tags=["events"])


@router.get("/events")
async def events(
    request: Request, container: Container = Depends(get_container)
) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        async for payload in container.subscribe_events():
            if await request.is_disconnected():
                break
            yield ": keep-alive\n\n" if payload is None else f"data: {payload}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
