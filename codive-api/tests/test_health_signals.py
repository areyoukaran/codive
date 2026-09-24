from datetime import datetime, timedelta, timezone

from app.services.health_signals import (
    compute_all,
    failing_ci_rate,
    review_turnaround,
    stale_pull_requests,
    unresolved_long_thread,
)

NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def test_stale_pull_requests_flags_old_open_prs():
    pulls = [
        {"repo": "atlas/api", "number": 401, "state": "open", "opened_at": _iso(16)},
        {"repo": "atlas/api", "number": 402, "state": "open", "opened_at": _iso(2)},   # too new
        {"repo": "atlas/api", "number": 403, "state": "closed", "opened_at": _iso(30)},  # not open
    ]
    signal = stale_pull_requests(pulls, now=NOW)
    assert signal is not None
    assert "1 pull request" in signal.title
    assert signal.evidence[0][0] == "atlas/api#401"


def test_stale_pull_requests_none_when_nothing_qualifies():
    pulls = [{"repo": "atlas/api", "number": 1, "state": "open", "opened_at": _iso(1)}]
    assert stale_pull_requests(pulls, now=NOW) is None


def test_failing_ci_rate_detects_streak_on_same_workflow():
    runs = [
        {"workflow_name": "api-ci", "branch": "main", "status": "failing", "failing_job": "test_no_timeout", "run_label": "run #3"},
        {"workflow_name": "api-ci", "branch": "main", "status": "failing", "failing_job": "test_no_timeout", "run_label": "run #2"},
        {"workflow_name": "api-ci", "branch": "main", "status": "failing", "failing_job": "test_no_timeout", "run_label": "run #1"},
        {"workflow_name": "web-ci", "branch": "main", "status": "passing", "failing_job": None, "run_label": "run #9"},
    ]
    signal = failing_ci_rate(runs)
    assert signal is not None
    assert "3 in a row" in signal.title
    assert signal.severity == "del"


def test_failing_ci_rate_none_when_all_passing():
    runs = [{"workflow_name": "api-ci", "branch": "main", "status": "passing", "run_label": "run #1"}]
    assert failing_ci_rate(runs) is None


def test_review_turnaround_needs_minimum_sample():
    prs = [
        {"is_merged": True, "opened_at": _iso(3), "closed_at": _iso(1)},
        {"is_merged": True, "opened_at": _iso(3), "closed_at": _iso(1)},
    ]
    assert review_turnaround(prs) is None, "fewer than 3 merged PRs should not produce a signal"


def test_review_turnaround_flags_slow_median():
    prs = [
        {"is_merged": True, "opened_at": _iso(5), "closed_at": _iso(2)},   # 3 days = 72h
        {"is_merged": True, "opened_at": _iso(4), "closed_at": _iso(1.5)},  # 60h
        {"is_merged": True, "opened_at": _iso(3), "closed_at": _iso(2.5)},  # 12h
    ]
    signal = review_turnaround(prs)
    assert signal is not None
    assert "hours" in signal.title


def test_unresolved_long_thread():
    issues = [
        {"repo": "atlas/api", "number": 287, "state": "open", "comment_count": 41, "title": "Initial sync stalls"},
        {"repo": "atlas/api", "number": 244, "state": "open", "comment_count": 6, "title": "Rate limit drops events"},
    ]
    signal = unresolved_long_thread(issues, comment_threshold=25)
    assert signal is not None
    assert "287" in signal.title
    assert signal.mark == "?"


def test_compute_all_skips_empty_signals():
    result = compute_all(pulls=[], issues=[], runs=[])
    assert result == []
