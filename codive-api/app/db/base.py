from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not set")
        url = settings.database_url
        # Accept the common `postgresql://` / `postgres://` forms people copy
        # from a provider dashboard and normalize to the async driver.
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        _engine = create_async_engine(
            url,
            pool_pre_ping=True,   # Neon (and most free-tier PG) can drop idle
            pool_size=5,          # connections; ping-before-use avoids a
            max_overflow=5,       # confusing error on the free tier's first
            pool_recycle=1800,    # query after a while.
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
