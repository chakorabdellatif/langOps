"""Liveness/readiness endpoint."""

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Response

from langops_api.composition import Container, get_container

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(response: Response, container: Container = Depends(get_container)) -> dict:
    checks: dict[str, str] = {}

    try:
        async with container.engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        checks["database"] = "unavailable"
        response.status_code = 503

    if container.redis is not None:
        try:
            await container.redis.ping()
            checks["redis"] = "ok"
        except Exception:  # noqa: BLE001 — Redis is optional (cache/pub-sub only)
            checks["redis"] = "unavailable"

    return {"status": "ok" if checks["database"] == "ok" else "degraded", "checks": checks}
