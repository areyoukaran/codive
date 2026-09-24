from app.services.github_pagination import (
    next_page_url,
    parse_link_header,
    parse_rate_limit_headers,
    retry_after_seconds,
)


def test_parse_link_header_multiple_rels():
    header = (
        '<https://api.github.com/repos/x/y/commits?page=2>; rel="next", '
        '<https://api.github.com/repos/x/y/commits?page=5>; rel="last"'
    )
    parsed = parse_link_header(header)
    assert parsed["next"] == "https://api.github.com/repos/x/y/commits?page=2"
    assert parsed["last"] == "https://api.github.com/repos/x/y/commits?page=5"


def test_parse_link_header_missing():
    assert parse_link_header(None) == {}
    assert parse_link_header("") == {}
    assert parse_link_header("garbage, not a link header") == {}


def test_next_page_url_last_page_has_no_next():
    header = '<https://api.github.com/x?page=1>; rel="prev", <https://api.github.com/x?page=3>; rel="first"'
    assert next_page_url(header) is None


def test_rate_limit_headers_case_insensitive():
    headers = {"X-RateLimit-Limit": "5000", "X-RateLimit-Remaining": "12", "X-RateLimit-Reset": "1700000000"}
    status = parse_rate_limit_headers(headers)
    assert status is not None
    assert status.limit == 5000
    assert status.remaining == 12
    assert not status.exhausted

    lower = {k.lower(): v for k, v in headers.items()}
    status2 = parse_rate_limit_headers(lower)
    assert status2 == status


def test_rate_limit_exhausted():
    headers = {"x-ratelimit-limit": "60", "x-ratelimit-remaining": "0", "x-ratelimit-reset": "1700000000"}
    status = parse_rate_limit_headers(headers)
    assert status.exhausted
    assert status.seconds_until_reset(1699999990) == 10
    assert status.seconds_until_reset(1700000100) == 0  # never negative


def test_rate_limit_headers_missing_returns_none():
    assert parse_rate_limit_headers({"content-type": "application/json"}) is None


def test_retry_after_seconds():
    assert retry_after_seconds({"Retry-After": "30"}) == 30
    assert retry_after_seconds({"retry-after": "0"}) == 0
    assert retry_after_seconds({}) is None
    assert retry_after_seconds({"Retry-After": "not-a-number"}) is None
