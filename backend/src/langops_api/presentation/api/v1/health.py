"""Liveness/readiness endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    # Phase 2 (tasks.md): add readiness checks for Postgres and Redis.
    return {"status": "ok"}
