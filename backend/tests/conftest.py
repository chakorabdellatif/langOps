"""Shared test fixtures.

Runs the real ASGI app against an in-memory SQLite database (tables created at
startup, no Redis) so API tests exercise the full stack without a server.
"""

from collections.abc import AsyncIterator

import httpx
import pytest_asyncio

from langops_api.infrastructure.settings import Settings
from langops_api.main import create_app


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="",
        db_create_tables=True,
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    # `lifespan_context` builds the DI container + schema before requests run.
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as c,
    ):
        yield c
