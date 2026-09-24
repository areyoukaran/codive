from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.middleware import RequestContextMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("codive")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Redis is optional: connect if REDIS_URL is set, otherwise every
    # feature that would use it (rate limiting) falls back to an in-memory
    # implementation with the same interface. See app/core/rate_limit.py.
    app.state.redis = None
    if settings.redis_url:
        try:
            import redis.asyncio as redis
            app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
            await app.state.redis.ping()
            log.info("connected to Redis")
        except Exception:  # noqa: BLE001
            log.exception("could not connect to REDIS_URL — falling back to in-memory rate limiting")
            app.state.redis = None

    scheduler = None
    if settings.enable_scheduler:
        from app.workers.scheduler import start_scheduler
        scheduler = start_scheduler()

    for warning in settings.warnings():
        log.warning("startup: %s", warning)

    yield

    if scheduler is not None:
        from app.workers.scheduler import stop_scheduler
        stop_scheduler()
    if app.state.redis is not None:
        await app.state.redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Codive API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.env != "production" else None,
        redoc_url=None,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    from app.api.routers import activity, ask, auth, health, repos, sync, webhooks
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(repos.router)
    app.include_router(sync.router)
    app.include_router(activity.router)
    app.include_router(ask.router)
    app.include_router(webhooks.router)

    @app.get("/")
    async def root():
        return {"service": "Codive API", "docs": "/docs" if settings.env != "production" else None, "health": "/health"}

    return app


app = create_app()
