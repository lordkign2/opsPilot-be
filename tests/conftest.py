"""
OpsPilot — Test Configuration.

Shared fixtures for the test suite.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ["APP_ENV"] = "testing"

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.billing.models import Invoice, Subscription  # noqa

# Import all models to ensure they are registered with Base.metadata before create_all
from app.modules.feature_flags.models import BusinessFeatureFlag, FeatureFlag, SubscriptionTier  # noqa
from app.modules.metering.models import UsageMeter  # noqa

settings = get_settings()

# Use a separate test database (in-memory SQLite for speed, or test Postgres)
TEST_DATABASE_URL = settings.DATABASE_URL.get_secret_value().replace("opspilot_db", "opspilot_test_db")


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)

    from app.db.session import async_session_factory

    async_session_factory.configure(bind=engine)

    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        from sqlalchemy import text

        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional test database session."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client with DB override."""

    async def override_get_db():
        yield db_session

    from app.db.redis import get_redis

    async def override_get_redis():
        class MockRedis:
            async def get(self, *args, **kwargs):
                return None

            async def set(self, *args, **kwargs):
                return None

            async def setex(self, *args, **kwargs):
                return None

        yield MockRedis()

    from fastapi_cache import FastAPICache
    from fastapi_cache.backends.inmemory import InMemoryBackend

    FastAPICache.init(InMemoryBackend())

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
