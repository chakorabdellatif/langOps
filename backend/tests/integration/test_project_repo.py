"""Default-project creation is idempotent and concurrency-safe.

The UniqueViolation on `projects.slug` happened when concurrent ingests each
missed the SELECT and both INSERTed. The fix inserts inside a savepoint and
re-reads on conflict; here we assert idempotency (the concurrent path is proven
live against Postgres).
"""

import pytest

from langops_api.infrastructure.db.models import Base
from langops_api.infrastructure.db.repositories import PostgresProjectRepository
from langops_api.infrastructure.db.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_get_or_create_default_is_idempotent() -> None:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)

    async with factory() as session, session.begin():
        first = await PostgresProjectRepository(session).get_or_create_default()
    async with factory() as session, session.begin():
        second = await PostgresProjectRepository(session).get_or_create_default()

    assert first.id == second.id
    assert first.slug == "default"
    await engine.dispose()
