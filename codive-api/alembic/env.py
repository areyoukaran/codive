from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401 — registers models on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _db_url() -> str:
    settings = get_settings()
    url = settings.database_url or "postgresql+asyncpg://codive:codive@localhost:5432/codive"
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


def run_migrations_offline() -> None:
    context.configure(url=_db_url(), target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _db_url()
    connectable = async_engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
