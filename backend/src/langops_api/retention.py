"""Retention job entry point (off by default; run on a schedule if desired).

    python -m langops_api.retention --days 30

Deletes executions (and their cascaded children) older than N days.
"""

from __future__ import annotations

import argparse
import asyncio

from langops_api.application.services.retention import RetentionService
from langops_api.infrastructure.db.repositories import PostgresExecutionRepository
from langops_api.infrastructure.db.session import create_engine, create_session_factory
from langops_api.infrastructure.settings import Settings


async def _run(days: int) -> int:
    settings = Settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session, session.begin():
            service = RetentionService(PostgresExecutionRepository(session))
            return await service.purge_older_than(days)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete executions older than N days.")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    deleted = asyncio.run(_run(args.days))
    print(f"deleted {deleted} executions older than {args.days} days")


if __name__ == "__main__":
    main()
