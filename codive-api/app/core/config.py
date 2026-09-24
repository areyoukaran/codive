"""
Centralized settings, read fresh every time Settings() is constructed -
which in normal operation is exactly once per process, via the
lru_cache'd get_settings() below.

Every value with a default is optional; the app boots and serves the
health check without any of them. Features that need a value you have not
set turn themselves off (see Settings.warnings()) rather than crashing -
so a half-configured deployment still comes up and tells you what's missing
instead of 500ing.

Note for anyone extending this: values are read inside __init__, not as
class-body assignments. `secret_key: str | None = _get("SECRET_KEY")` at
class scope would only evaluate once, at import time - os.environ changes
after that point (exactly what tests do between cases, and what a process
manager occasionally does before the app's first real request) would
silently not take effect even after get_settings.cache_clear(). Reading in
__init__ makes "clear the cache, get fresh env" actually true. (This was a
real bug caught by tests/test_llm_provider_selection.py during development
- see the git history if you're curious what it looked like broken.)
"""
from __future__ import annotations

import os
from functools import lru_cache


def _get(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def _get_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_list(name: str, default: list[str]) -> list[str]:
    val = os.environ.get(name)
    if not val:
        return list(default)
    return [x.strip() for x in val.split(",") if x.strip()]


class Settings:
    app_name = "Codive API"

    def __init__(self) -> None:
        self.env: str = _get("ENV", "development")

        # required for real auth + encryption; app still boots without
        # them, but /auth/github/* and token storage will 503 with a
        # clear message rather than crash
        self.secret_key: str | None = _get("SECRET_KEY")
        self.token_encryption_key: str | None = _get("TOKEN_ENCRYPTION_KEY")
        self.github_client_id: str | None = _get("GITHUB_CLIENT_ID")
        self.github_client_secret: str | None = _get("GITHUB_CLIENT_SECRET")
        self.github_webhook_secret: str | None = _get("GITHUB_WEBHOOK_SECRET")

        # where things live
        self.database_url: str | None = _get("DATABASE_URL")
        self.redis_url: str | None = _get("REDIS_URL")
        self.frontend_url: str = _get("FRONTEND_URL", "http://localhost:5173")
        self.backend_url: str = _get("BACKEND_URL", "http://localhost:8000")
        self.cors_origins: list[str] = _get_list("CORS_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"])

        # optional AI providers; without a key, summaries/chat fall back to
        # a deterministic templated answer built straight from synced data
        self.groq_api_key: str | None = _get("GROQ_API_KEY")
        self.groq_model: str = _get("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.gemini_api_key: str | None = _get("GEMINI_API_KEY")
        self.gemini_model: str = _get("GEMINI_MODEL", "gemini-2.0-flash")
        self.llm_provider: str = _get("LLM_PROVIDER", "auto")
        self.embedding_provider: str = _get("EMBEDDING_PROVIDER", "auto")

        # sync / scheduling
        self.sync_interval_minutes: int = int(_get("SYNC_INTERVAL_MINUTES", "20"))
        self.brief_hour_utc: int = int(_get("BRIEF_HOUR_UTC", "5"))
        self.max_repos_per_account: int = int(_get("MAX_REPOS_PER_ACCOUNT", "8"))
        self.enable_scheduler: bool = _get_bool("ENABLE_SCHEDULER", True)

        # rate limiting (per authenticated user)
        self.rate_limit_per_minute: int = int(_get("RATE_LIMIT_PER_MINUTE", "60"))
        self.ask_rate_limit_per_minute: int = int(_get("ASK_RATE_LIMIT_PER_MINUTE", "6"))

        # cookies
        self.session_cookie_name: str = "codive_session"
        self.session_max_age_seconds: int = 60 * 60 * 24 * 14  # 14 days
        self.cookie_secure: bool = _get_bool("COOKIE_SECURE", self.env != "development")
        # SameSite=Lax survives the OAuth redirect (a top-level navigation)
        # but is NOT sent on the fetch()/XHR calls the frontend makes for
        # every other route once it's a different domain from the API -
        # which it is in the real deployment (GitHub Pages vs Render).
        # Cross-site cookies require SameSite=None, and browsers only honor
        # None when Secure is also set - which cookie_secure already is
        # outside local dev, so this falls out of that one flag rather than
        # needing its own env var.
        self.cookie_samesite: str = "none" if self.cookie_secure else "lax"

    def warnings(self) -> list[str]:
        """Human-readable list of missing configuration, surfaced at /health."""
        out = []
        if not self.secret_key:
            out.append("SECRET_KEY not set - sessions cannot be issued")
        if not self.token_encryption_key:
            out.append("TOKEN_ENCRYPTION_KEY not set - GitHub tokens cannot be stored")
        if not self.database_url:
            out.append("DATABASE_URL not set - nothing can be persisted")
        if not self.github_client_id or not self.github_client_secret:
            out.append("GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET not set - GitHub OAuth is disabled")
        if not self.redis_url:
            out.append("REDIS_URL not set - rate limiting and caching fall back to in-process memory (fine for one instance, not for several)")
        if not self.groq_api_key and not self.gemini_api_key:
            out.append("No GROQ_API_KEY or GEMINI_API_KEY set - AI summaries and chat use a templated fallback, not a model")
        if not self.github_webhook_secret:
            out.append("GITHUB_WEBHOOK_SECRET not set - webhook delivery is disabled, sync falls back to polling only")
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
