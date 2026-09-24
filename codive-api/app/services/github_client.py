"""
A thin async wrapper over the GitHub REST API — every call goes through
`_get`, which handles pagination, ETag-based conditional requests, primary
rate-limit backoff, and secondary (Retry-After) backoff in one place. The
sync service never touches httpx directly.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

import httpx

from app.services.github_pagination import (
    next_page_url,
    parse_rate_limit_headers,
    retry_after_seconds,
)

log = logging.getLogger("codive.github")

GITHUB_API = "https://api.github.com"
GITHUB_OAUTH_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_TOKEN = "https://github.com/login/oauth/access_token"


class GitHubAPIError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status


class GitHubClient:
    def __init__(self, token: str | None = None, *, timeout: float = 20.0):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Codive (+https://github.com)",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        # Sync clients hit large repositories on first sync and legitimately
        # take minutes, not seconds — this was the actual bug in the
        # product's own sample data (httpx 0.26 changed what timeout=None
        # means), so the timeout here is explicit on every leg, not implied.
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API,
            headers=headers,
            timeout=httpx.Timeout(connect=5.0, read=timeout, write=10.0, pool=5.0),
        )
        self._etags: dict[str, tuple[str, Any]] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    # ----------------------------------------------------------- internals --

    async def _get(self, url: str, *, params: dict | None = None, use_etag: bool = False) -> httpx.Response:
        headers = {}
        cache_key = url if not params else f"{url}?{sorted(params.items())}"
        if use_etag and cache_key in self._etags:
            headers["If-None-Match"] = self._etags[cache_key][0]

        for attempt in range(6):
            resp = await self._client.get(url, params=params, headers=headers)

            if resp.status_code == 304:
                return resp  # caller reads the cached body via self._etags

            if resp.status_code == 403 or resp.status_code == 429:
                retry = retry_after_seconds(resp.headers)
                if retry is not None:
                    log.warning("secondary rate limit hit, backing off %ss", retry)
                    await asyncio.sleep(min(retry, 60) + 1)
                    continue
                rl = parse_rate_limit_headers(resp.headers)
                if rl is not None and rl.exhausted:
                    import time
                    wait = rl.seconds_until_reset(time.time())
                    log.warning("primary rate limit exhausted, sleeping %ss", wait)
                    await asyncio.sleep(min(wait, 300) + 1)
                    continue
                # 403 that isn't a rate limit (e.g. missing scope) — don't retry
                raise GitHubAPIError(resp.status_code, resp.text[:300])

            if resp.status_code >= 500:
                backoff = min(2 ** attempt, 30)
                log.warning("GitHub 5xx, retrying in %ss (attempt %s)", backoff, attempt + 1)
                await asyncio.sleep(backoff)
                continue

            if resp.status_code >= 400:
                raise GitHubAPIError(resp.status_code, resp.text[:300])

            if use_etag and "etag" in resp.headers:
                self._etags[cache_key] = (resp.headers["etag"], resp.json())
            return resp

        raise GitHubAPIError(0, "exhausted retries against GitHub API")

    async def _paginated(self, path: str, *, params: dict | None = None) -> AsyncIterator[dict]:
        params = dict(params or {})
        params.setdefault("per_page", 100)
        url: str | None = path
        first = True
        while url:
            resp = await self._get(url, params=params if first else None)
            first = False
            for item in resp.json():
                yield item
            url = next_page_url(resp.headers.get("Link"))

    # -------------------------------------------------------------- oauth --

    @staticmethod
    def authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
        from urllib.parse import urlencode
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user repo:status public_repo",
            "state": state,
            "allow_signup": "true",
        }
        return f"{GITHUB_OAUTH_AUTHORIZE}?{urlencode(params)}"

    @staticmethod
    async def exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as c:
            resp = await c.post(
                GITHUB_OAUTH_TOKEN,
                headers={"Accept": "application/json"},
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise GitHubAPIError(400, data.get("error_description", data["error"]))
            return data

    # ------------------------------------------------------------- reads --

    async def me(self) -> dict:
        resp = await self._get("/user")
        return resp.json()

    async def list_installation_repos(self) -> list[dict]:
        """Repositories the authenticated user can grant Codive read access to."""
        out = []
        async for repo in self._paginated("/user/repos", params={"sort": "pushed", "affiliation": "owner,collaborator"}):
            out.append(repo)
        return out

    async def repo(self, owner: str, name: str) -> dict:
        resp = await self._get(f"/repos/{owner}/{name}")
        return resp.json()

    async def commits(self, owner: str, name: str, *, since: str | None = None) -> AsyncIterator[dict]:
        params = {"since": since} if since else {}
        async for c in self._paginated(f"/repos/{owner}/{name}/commits", params=params):
            yield c

    async def pulls(self, owner: str, name: str, *, state: str = "all") -> AsyncIterator[dict]:
        async for pr in self._paginated(f"/repos/{owner}/{name}/pulls", params={"state": state, "sort": "updated", "direction": "desc"}):
            yield pr

    async def pull_files(self, owner: str, name: str, number: int) -> list[dict]:
        out = []
        async for f in self._paginated(f"/repos/{owner}/{name}/pulls/{number}/files"):
            out.append(f)
        return out

    async def issues(self, owner: str, name: str, *, state: str = "all", since: str | None = None) -> AsyncIterator[dict]:
        params = {"state": state}
        if since:
            params["since"] = since
        async for item in self._paginated(f"/repos/{owner}/{name}/issues", params=params):
            if "pull_request" in item:
                continue  # GitHub lists PRs under /issues too; the sync service handles those separately
            yield item

    async def issue_comments(self, owner: str, name: str, number: int) -> list[dict]:
        out = []
        async for c in self._paginated(f"/repos/{owner}/{name}/issues/{number}/comments"):
            out.append(c)
        return out

    async def check_runs(self, owner: str, name: str, ref: str) -> list[dict]:
        resp = await self._get(f"/repos/{owner}/{name}/commits/{ref}/check-runs")
        return resp.json().get("check_runs", [])

    async def latest_release(self, owner: str, name: str) -> dict | None:
        resp = await self._client.get(f"/repos/{owner}/{name}/releases/latest")
        return resp.json() if resp.status_code == 200 else None

    async def readme(self, owner: str, name: str) -> str | None:
        resp = await self._client.get(
            f"/repos/{owner}/{name}/readme",
            headers={"Accept": "application/vnd.github.raw+json"},
        )
        return resp.text if resp.status_code == 200 else None
