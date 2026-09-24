from __future__ import annotations

import time

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.base import get_engine

router = APIRouter(tags=["health"])

_started_at = time.time()


@router.get("/health")
async def health():
    """Always 200 if the process is up — for platform liveness checks.
    Lists missing configuration so a half-set-up deployment says why,
    instead of failing silently on the first real request."""
    settings = get_settings()
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _started_at),
        "warnings": settings.warnings(),
    }


@router.get("/ready")
async def ready():
    """200 only if the database is actually reachable — for a load
    balancer or platform readiness probe, distinct from liveness."""
    settings = get_settings()
    if not settings.database_url:
        return {"status": "not_ready", "reason": "DATABASE_URL not set"}
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        return {"status": "not_ready", "reason": str(exc)[:200]}
    return {"status": "ready"}
