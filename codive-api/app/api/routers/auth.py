from __future__ import annotations

import secrets
import time

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_configured
from app.core.config import get_settings
from app.core.security import create_session_token, encrypt_secret
from app.db.base import get_db
from app.db.models import GithubAccount, User
from app.services.github_client import GitHubClient

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory OAuth `state` store, one process. Good enough for the CSRF check
# it exists for; a multi-instance deployment would move this to Redis, same
# as the rate limiter - the interface is small on purpose so that's a
# one-file change later, not a rewrite.
_pending_states: dict[str, float] = {}
_STATE_TTL_SECONDS = 600


def _issue_state() -> str:
    now = time.time()
    for k in list(_pending_states):
        if _pending_states[k] < now:
            del _pending_states[k]
    state = secrets.token_urlsafe(24)
    _pending_states[state] = now + _STATE_TTL_SECONDS
    return state


def _consume_state(state: str) -> bool:
    expiry = _pending_states.pop(state, None)
    return expiry is not None and expiry >= time.time()


@router.get("/github/login")
async def github_login():
    require_configured("github_client_id", "github_client_secret", "secret_key")
    settings = get_settings()
    state = _issue_state()
    redirect_uri = f"{settings.backend_url}/auth/github/callback"
    url = GitHubClient.authorize_url(settings.github_client_id, redirect_uri, state)
    return RedirectResponse(url)


@router.get("/github/callback")
async def github_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if not _consume_state(state):
        raise HTTPException(400, "OAuth state is invalid or expired - start over from the login button")

    redirect_uri = f"{settings.backend_url}/auth/github/callback"
    token_data = await GitHubClient.exchange_code(
        settings.github_client_id, settings.github_client_secret, code, redirect_uri
    )
    access_token = token_data["access_token"]
    scope = token_data.get("scope", "")

    async with GitHubClient(access_token) as gh:
        profile = await gh.me()

    user = await db.scalar(select(User).where(User.github_id == profile["id"]))
    if user is None:
        user = User(github_id=profile["id"], github_login=profile["login"], avatar_url=profile.get("avatar_url"))
        db.add(user)
        await db.flush()
    else:
        user.github_login = profile["login"]
        user.avatar_url = profile.get("avatar_url")

    account = await db.scalar(select(GithubAccount).where(GithubAccount.user_id == user.id))
    encrypted = encrypt_secret(access_token)
    if account is None:
        account = GithubAccount(user_id=user.id, encrypted_access_token=encrypted, scope=scope)
        db.add(account)
    else:
        account.encrypted_access_token = encrypted
        account.scope = scope
    await db.commit()

    session_token = create_session_token(user.id, user.github_login)
    resp = RedirectResponse(f"{settings.frontend_url}/onboarding.html?connected=1")
    resp.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    return resp


@router.post("/logout")
async def logout(response: Response):
    settings = get_settings()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "login": user.github_login, "avatar_url": user.avatar_url}
