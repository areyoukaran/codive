"""
Fixed-window rate limiting, keyed per user per route group.

Two backends behind one interface:
  - InMemoryLimiter: a dict of deques, correct for a single process. This is
    what runs when REDIS_URL is unset, which is exactly the free-tier case
    of one Render web service with no Redis configured yet.
  - RedisLimiter: same algorithm, shared across processes/instances via
    Redis INCR + EXPIRE, for when REDIS_URL (Upstash) is set.

Both expose the same `allow(key, limit, window_seconds) -> RateLimitResult`,
so callers never know which one they're talking to. InMemoryLimiter has no
third-party imports and is unit-tested directly.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class InMemoryLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.monotonic()
        bucket = self._hits[key]
        cutoff = now - window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(window_seconds - (now - bucket[0])))
            return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=retry_after)
        bucket.append(now)
        return RateLimitResult(allowed=True, remaining=limit - len(bucket), retry_after_seconds=0)


class RedisLimiter:
    """Same sliding-window semantics, backed by a Redis sorted set per key."""

    def __init__(self, client) -> None:
        self._r = client

    async def allow(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.time()
        cutoff = now - window_seconds
        pipe = self._r.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.zcard(key)
        pipe.zadd(key, {f"{now}:{id(pipe)}": now})
        pipe.expire(key, window_seconds + 1)
        _, count_before, *_ = await pipe.execute()
        if count_before >= limit:
            await self._r.zrem(key, f"{now}:{id(pipe)}")
            oldest = await self._r.zrange(key, 0, 0, withscores=True)
            retry_after = int(window_seconds - (now - oldest[0][1])) if oldest else window_seconds
            return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=max(1, retry_after))
        return RateLimitResult(allowed=True, remaining=max(0, limit - count_before - 1), retry_after_seconds=0)


_in_memory_singleton = InMemoryLimiter()


def get_limiter(redis_client=None):
    """redis_client is an already-connected redis.asyncio.Redis, or None."""
    if redis_client is not None:
        return RedisLimiter(redis_client)
    return _in_memory_singleton
