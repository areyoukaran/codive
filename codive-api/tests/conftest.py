"""
Fixtures for the FastAPI-integration tests (test_api_smoke.py). These need
a real Postgres reachable via DATABASE_URL - provided by the `postgres`
service container in .github/workflows/ci.yml, or by `docker compose up db`
locally. They are not run as part of the pure-logic test files, which have
no such requirement and run anywhere Python does.
"""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS1mb3ItcHl0ZXN0LSE=")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("ENABLE_SCHEDULER", "false")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://codive:codive@localhost:5432/codive_test",
)

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import create_session_token
from app.db.base import Base, get_engine
from app.db.models import User


@pytest_asyncio.fixture(scope="session")
async def _schema():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(_schema):
    from app.db.base import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_user(db_session):
    user = User(github_id=999001, github_login="octocat-test", avatar_url=None)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def client(_schema):
    from app.main import create_app
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def authed_client(client, test_user):
    token = create_session_token(test_user.id, test_user.github_login)
    client.cookies.set("codive_session", token)
    return client
