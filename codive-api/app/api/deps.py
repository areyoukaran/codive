from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import ConfigurationError, verify_session_token
from app.db.base import get_db
from app.db.models import GithubAccount, User


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias="codive_session"),
) -> User:
    if not session_cookie:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    try:
        claims = verify_session_token(session_cookie)
    except ConfigurationError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if claims is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid - sign in again")
    user = await db.scalar(select(User).where(User.id == claims.user_id))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account no longer exists")
    return user


async def get_user_token(user: User, db: AsyncSession) -> str:
    from app.core.security import decrypt_secret
    account = await db.scalar(select(GithubAccount).where(GithubAccount.user_id == user.id))
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No GitHub account connected")
    token = decrypt_secret(account.encrypted_access_token)
    if token is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Stored GitHub token could not be decrypted - reconnect GitHub")
    return token


def require_configured(*names: str) -> None:
    """Call at the top of a route that needs specific env vars. Returns a
    clean 503 with exactly what's missing, instead of a stack trace three
    layers deep the first time someone deploys without a secret set."""
    settings = get_settings()
    missing = [n for n in names if getattr(settings, n, None) in (None, "")]
    if missing:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Server is missing configuration: {', '.join(missing)}",
        )
