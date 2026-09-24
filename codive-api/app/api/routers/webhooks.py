from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from sqlalchemy import select

from app.core.config import get_settings
from app.core.webhook_verify import verify_signature
from app.db.base import get_session_factory
from app.db.models import Repository
from app.services.sync_service import run_sync

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger("codive.webhooks")


@router.post("/github")
async def github_webhook(
    request: Request,
    background: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
):
    settings = get_settings()
    if not settings.github_webhook_secret:
        raise HTTPException(503, "Webhooks are not configured on this server (GITHUB_WEBHOOK_SECRET unset) — sync still runs on a schedule")

    raw = await request.body()
    if not verify_signature(settings.github_webhook_secret, raw, x_hub_signature_256):
        raise HTTPException(401, "Invalid webhook signature")

    payload = await request.json()
    repo_full_name = (payload.get("repository") or {}).get("full_name")
    if not repo_full_name:
        return {"ok": True, "ignored": "no repository in payload"}

    if x_github_event in ("push", "pull_request", "issues", "issue_comment", "check_run", "check_suite", "release"):
        background.add_task(_resync_by_name, repo_full_name)

    return {"ok": True, "event": x_github_event}


async def _resync_by_name(full_name: str) -> None:
    from app.api.deps import get_user_token  # local import avoids a circular import at module load time
    factory = get_session_factory()
    async with factory() as db:
        repos = list(await db.scalars(select(Repository).where(Repository.full_name == full_name, Repository.is_watched.is_(True))))
        for repo in repos:
            try:
                from app.db.models import User
                owner = await db.get(User, repo.owner_user_id)
                if owner is None:
                    continue
                token = await get_user_token(owner, db)
                await run_sync(db, repo, token)
            except Exception:  # noqa: BLE001 — a webhook-triggered resync failing must never crash the handler
                log.exception("webhook-triggered resync failed for %s", full_name)
