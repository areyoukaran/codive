from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_user_token
from app.core.config import get_settings
from app.db.base import get_db
from app.db.models import Repository, User
from app.services.github_client import GitHubClient

router = APIRouter(prefix="/repos", tags=["repositories"])


@router.get("/available")
async def available_repos(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Repositories on GitHub the signed-in user can pick from - live call,
    not stored, so it always reflects what's actually on their account."""
    token = await get_user_token(user, db)
    async with GitHubClient(token) as gh:
        repos = await gh.list_installation_repos()
    return [
        {
            "full_name": r["full_name"],
            "description": r.get("description"),
            "language": r.get("language"),
            "private": r.get("private", False),
            "stars": r.get("stargazers_count", 0),
            "pushed_at": r.get("pushed_at"),
        }
        for r in repos
    ]


class SelectRepos(BaseModel):
    full_names: list[str]


@router.post("/select")
async def select_repos(body: SelectRepos, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if len(body.full_names) > settings.max_repos_per_account:
        raise HTTPException(400, f"Pick at most {settings.max_repos_per_account} repositories - fewer makes a sharper brief anyway")

    token = await get_user_token(user, db)
    created = []
    async with GitHubClient(token) as gh:
        for full_name in body.full_names:
            existing = await db.scalar(
                select(Repository).where(Repository.owner_user_id == user.id, Repository.full_name == full_name)
            )
            if existing:
                existing.is_watched = True
                created.append(existing)
                continue
            owner, name = full_name.split("/", 1)
            meta = await gh.repo(owner, name)
            repo = Repository(
                owner_user_id=user.id,
                github_repo_id=meta["id"],
                full_name=full_name,
                description=meta.get("description"),
                default_branch=meta.get("default_branch", "main"),
                language=meta.get("language"),
                visibility="private" if meta.get("private") else "public",
                stars=meta.get("stargazers_count", 0),
                forks=meta.get("forks_count", 0),
            )
            db.add(repo)
            created.append(repo)
    await db.commit()
    for r in created:
        await db.refresh(r)
    return {"repositories": [r.id for r in created]}


@router.get("")
async def list_repos(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(Repository).where(Repository.owner_user_id == user.id, Repository.is_watched.is_(True))
        .order_by(Repository.full_name)
    )
    return [_repo_out(r) for r in rows]


@router.get("/{repo_id}")
async def get_repo(repo_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repo = await db.scalar(select(Repository).where(Repository.id == repo_id, Repository.owner_user_id == user.id))
    if repo is None:
        raise HTTPException(404, "Repository not found")
    return _repo_out(repo)


def _repo_out(r: Repository) -> dict:
    return {
        "id": r.id,
        "full_name": r.full_name,
        "description": r.description,
        "default_branch": r.default_branch,
        "language": r.language,
        "visibility": r.visibility,
        "stars": r.stars,
        "forks": r.forks,
        "latest_release": r.latest_release,
        "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
    }
