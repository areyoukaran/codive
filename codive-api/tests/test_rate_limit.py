import time

from app.core.rate_limit import InMemoryLimiter


def test_allows_up_to_the_limit():
    limiter = InMemoryLimiter()
    for i in range(5):
        result = limiter.allow("user-1", limit=5, window_seconds=60)
        assert result.allowed, f"request {i} should be allowed"
        assert result.remaining == 5 - (i + 1)


def test_blocks_after_the_limit():
    limiter = InMemoryLimiter()
    for _ in range(3):
        limiter.allow("user-1", limit=3, window_seconds=60)
    result = limiter.allow("user-1", limit=3, window_seconds=60)
    assert not result.allowed
    assert result.remaining == 0
    assert result.retry_after_seconds > 0


def test_keys_are_independent():
    limiter = InMemoryLimiter()
    for _ in range(3):
        limiter.allow("user-1", limit=3, window_seconds=60)
    result = limiter.allow("user-2", limit=3, window_seconds=60)
    assert result.allowed, "a different key must not be blocked by user-1's usage"


def test_window_expires_old_hits():
    limiter = InMemoryLimiter()
    limiter.allow("user-1", limit=1, window_seconds=1)
    blocked = limiter.allow("user-1", limit=1, window_seconds=1)
    assert not blocked.allowed
    time.sleep(1.05)
    result = limiter.allow("user-1", limit=1, window_seconds=1)
    assert result.allowed, "hits older than the window should have expired"
