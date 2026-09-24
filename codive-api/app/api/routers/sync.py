from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_user_token
from app.db.base import get_db, get_session_factory
from app.db.models import Repository, SyncJob, User
from app.services.sync_service import run_sync

router = APIRouter(prefix="/sync", tags=["sync"])


async def _sync_one_in_background(repo_id: str, token: str) -> None:
    """Runs after the HTTP response has already gone out, in its own DB
    session — FastAPI's BackgroundTasks, which is what makes free-tier
    hosting work without a second worker process the free plan doesn't
    give you."""
    factory = get_session_factory()
    async with factory() as db:
        repo = await db.get(Repository, repo_id)
        if repo is not None:
            await run_sync(db, repo, token)


@router.post("/start")
async def start_sync(
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token = await get_user_token(user, db)
    repos = list(await db.scalars(
        select(Repository).where(Repository.owner_user_id == user.id, Repository.is_watched.is_(True))
    ))
    if not repos:
        raise HTTPException(400, "No repositories selected yet — call /repos/select first")
    for repo in repos:
        background.add_task(_sync_one_in_background, repo.id, token)
    return {"queued": [r.full_name for r in repos]}


@router.post("/start/{repo_id}")
async def start_sync_one(
    repo_id: str,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token = await get_user_token(user, db)
    repo = await db.scalar(select(Repository).where(Repository.id == repo_id, Repository.owner_user_id == user.id))
    if repo is None:
        raise HTTPException(404, "Repository not found")
    background.add_task(_sync_one_in_background, repo.id, token)
    return {"queued": [repo.full_name]}


@router.get("/status")
async def sync_status(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repos = list(await db.scalars(
        select(Repository).where(Repository.owner_user_id == user.id, Repository.is_watched.is_(True))
    ))
    out = []
    for repo in repos:
        job = await db.scalar(
            select(SyncJob).where(SyncJob.repo_id == repo.id).order_by(SyncJob.started_at.desc()).limit(1)
        )
        out.append({
            "repo": repo.full_name,
            "status": job.status if job else "never synced",
            "stage": job.stage if job else None,
            "error": job.error if job else None,
            "last_synced_at": repo.last_synced_at.isoformat() if repo.last_synced_at else None,
        })
    all_done = all(r["status"] in ("done", "error") for r in out) if out else False
    return {"repositories": out, "complete": all_done}
