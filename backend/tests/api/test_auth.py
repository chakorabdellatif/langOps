"""Phase 19 — optional API-key auth."""

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from langops_api.infrastructure.settings import Settings
from langops_api.main import create_app

KEY = "s3cr3t-key"


@pytest_asyncio.fixture
async def auth_client() -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="",
        db_create_tables=True,
        api_key=KEY,
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as c,
    ):
        yield c


@pytest.mark.asyncio
async def test_health_is_open_without_key(auth_client: httpx.AsyncClient) -> None:
    assert (await auth_client.get("/api/v1/health")).status_code == 200


@pytest.mark.asyncio
async def test_query_requires_key(auth_client: httpx.AsyncClient) -> None:
    unauth = await auth_client.get("/api/v1/executions")
    assert unauth.status_code == 401
    assert unauth.json()["code"] == "unauthorized"

    ok = await auth_client.get("/api/v1/executions", headers={"authorization": f"Bearer {KEY}"})
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_ingest_requires_key(auth_client: httpx.AsyncClient) -> None:
    body = '{"resourceSpans": []}'
    unauth = await auth_client.post(
        "/v1/traces", content=body, headers={"content-type": "application/json"}
    )
    assert unauth.status_code == 401

    ok = await auth_client.post(
        "/v1/traces",
        content=body,
        headers={"content-type": "application/json", "authorization": f"Bearer {KEY}"},
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_wrong_key_rejected(auth_client: httpx.AsyncClient) -> None:
    resp = await auth_client.get("/api/v1/executions", headers={"authorization": "Bearer wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_off_by_default(client: httpx.AsyncClient) -> None:
    # The default fixture sets no api_key — no Authorization needed.
    assert (await client.get("/api/v1/executions")).status_code == 200
