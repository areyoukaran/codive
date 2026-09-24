"""
A free-tier web service is one process, not a web dyno plus a worker
dyno - so background jobs run in-process with APScheduler rather than a
separate Celery worker, matching §18's "background jobs" without needing
infrastructure the free tier doesn't offer.

Trade-off, stated plainly: on Render's free tier the process spins down
after 15 minutes with no inbound HTTP traffic, and an idle scheduler alone
does not count as traffic - so on a totally quiet free instance, scheduled
jobs pause until the next real request wakes it back up. A paid instance,
or a free external cron hitting /health every few minutes, keeps it warm.
This is documented in the README's deployment section, not hidden.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import get_session_factory
from app.db.models import DailyBrief, GithubAccount, Repository, User
from app.services.brief import compute_counters, generate_lede
from app.services.sync_service import run_sync

log = logging.getLogger("codive.scheduler")
_scheduler: AsyncIOScheduler | None = None


async def _incremental_sync_all() -> None:
    from app.core.security import decrypt_secret
    factory = get_session_factory()
    async with factory() as db:
        repos = list(await db.scalars(select(Repository).where(Repository.is_watched.is_(True))))
        log.info("scheduled sync: %d watched repositories", len(repos))
        for repo in repos:
            account = await db.scalar(select(GithubAccount).where(GithubAccount.user_id == repo.owner_user_id))
            if account is None:
                continue
            token = decrypt_secret(account.encrypted_access_token)
            if token is None:
                continue
            await run_sync(db, repo, token)


async def _generate_daily_briefs() -> None:
    from datetime import datetime, timezone
    from app.db.models import Commit, Issue, PullRequest, WorkflowRun

    factory = get_session_factory()
    today = datetime.now(timezone.utc).date().isoformat()
    async with factory() as db:
        users = list(await db.scalars(select(User)))
        for user in users:
            existing = await db.scalar(select(DailyBrief).where(DailyBrief.user_id == user.id, DailyBrief.brief_date == today))
            if existing:
                continue
            repos = list(await db.scalars(select(Repository).where(Repository.owner_user_id == user.id, Repository.is_watched.is_(True))))
            ids = [r.id for r in repos]
            if not ids:
                continue
            prs = (await db.execute(select(PullRequest).where(PullRequest.repo_id.in_(ids)))).scalars().all()
            issues = (await db.execute(select(Issue).where(Issue.repo_id.in_(ids)))).scalars().all()
            runs = (await db.execute(select(WorkflowRun).where(WorkflowRun.repo_id.in_(ids)))).scalars().all()

            pr_dicts = [{"repo": next((r.full_name for r in repos if r.id == p.repo_id), ""), "number": p.number,
                         "state": p.state, "is_draft": p.is_draft, "review_decision": p.review_decision} for p in prs]
            issue_dicts = [{"state": i.state, "age_days": (datetime.now(timezone.utc) - i.opened_at).days} for i in issues]
            run_dicts = [{"status": w.status, "workflow_name": w.workflow_name} for w in runs]

            counters = compute_counters(pulls=pr_dicts, issues=issue_dicts, runs=run_dicts)
            top = [p for p in pr_dicts if p["state"] == "open" and not p["is_draft"]][:3]
            lede, generated_by = await generate_lede(counters=counters, top_items=top)

            db.add(DailyBrief(user_id=user.id, brief_date=today, lede=lede, counters=counters, generated_by=generated_by))
        await db.commit()


def start_scheduler() -> AsyncIOScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.enable_scheduler or not settings.database_url:
        log.info("scheduler disabled (ENABLE_SCHEDULER=false or no DATABASE_URL)")
        return None
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(_incremental_sync_all, "interval", minutes=settings.sync_interval_minutes, id="incremental_sync")
    _scheduler.add_job(_generate_daily_briefs, "cron", hour=settings.brief_hour_utc, minute=0, id="daily_brief")
    _scheduler.start()
    log.info("scheduler started: sync every %sm, brief at %02d:00 UTC", settings.sync_interval_minutes, settings.brief_hour_utc)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
