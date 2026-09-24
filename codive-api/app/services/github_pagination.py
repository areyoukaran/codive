"""
Pure-stdlib parsing for two things the GitHub REST API hands back on every
response: the `Link` header (pagination) and the `X-RateLimit-*` headers
(how much quota is left). No third-party imports, so this module is unit
tested directly with nothing but the standard library.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_LINK_RE = re.compile(r'<([^>]+)>;\s*rel="([^"]+)"')


def parse_link_header(header_value: str | None) -> dict[str, str]:
    """
    'Link: <https://api.github.com/x?page=2>; rel="next", <...>; rel="last"'
    ->    {"next": "https://api.github.com/x?page=2", "last": "..."}
    Returns {} for a missing or malformed header - callers treat that as
    "no more pages" rather than raising.
    """
    if not header_value:
        return {}
    return {rel: url for url, rel in _LINK_RE.findall(header_value)}


def next_page_url(link_header_value: str | None) -> str | None:
    return parse_link_header(link_header_value).get("next")


@dataclass(frozen=True)
class RateLimitStatus:
    limit: int
    remaining: int
    reset_epoch: int
    used: int

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0

    def seconds_until_reset(self, now_epoch: float) -> int:
        return max(0, int(self.reset_epoch - now_epoch))


def parse_rate_limit_headers(headers: dict[str, str]) -> RateLimitStatus | None:
    """Case-insensitive lookup, because header dict casing varies by client."""
    lower = {k.lower(): v for k, v in headers.items()}
    try:
        return RateLimitStatus(
            limit=int(lower["x-ratelimit-limit"]),
            remaining=int(lower["x-ratelimit-remaining"]),
            reset_epoch=int(lower["x-ratelimit-reset"]),
            used=int(lower.get("x-ratelimit-used", 0)),
        )
    except (KeyError, ValueError):
        return None


def retry_after_seconds(headers: dict[str, str]) -> int | None:
    """
    GitHub sends a plain `Retry-After` (seconds) on secondary rate limits -
    the "you're going too fast, not out of quota" case, distinct from the
    primary limit above. Respecting this was the actual fix behind the
    "retry storm" scenario in the product's sample data.
    """
    lower = {k.lower(): v for k, v in headers.items()}
    val = lower.get("retry-after")
    if val is None:
        return None
    try:
        return max(0, int(val))
    except ValueError:
        return None
