"""
Turns synced rows into the signal -> evidence -> action shape from §11 of
the blueprint: measured thresholds, not a model's opinion. Every function
here takes plain dicts/lists (not ORM objects) and returns plain dicts, on
purpose — it has no framework or database import, so it's testable with
nothing but the standard library, and the same functions can run against
either real synced rows or the sample front-end data with no adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _parse(ts: str | datetime) -> datetime:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _age_days(opened_at: str | datetime, now: datetime) -> float:
    return (now - _parse(opened_at)).total_seconds() / 86400


@dataclass
class Signal:
    mark: str
    severity: str          # mute | warn | del | iris
    title: str
    evidence: list[tuple[str, str]] = field(default_factory=list)
    action: str = ""
    action_note: str = ""
    trend: str = "flat"


STALE_PR_DAYS = 14
STALE_ISSUE_DAYS = 21


def stale_pull_requests(pulls: list[dict], now: datetime | None = None) -> Signal | None:
    now = now or datetime.now(timezone.utc)
    stale = [p for p in pulls if p.get("state") == "open" and _age_days(p["opened_at"], now) >= STALE_PR_DAYS]
    if not stale:
        return None
    stale.sort(key=lambda p: _age_days(p["opened_at"], now), reverse=True)
    evidence = [
        (f"{p['repo']}#{p['number']}", f"{int(_age_days(p['opened_at'], now))} days old")
        for p in stale[:5]
    ]
    return Signal(
        mark="·", severity="mute",
        title=f"{len(stale)} pull request{'s' if len(stale) != 1 else ''} older than {STALE_PR_DAYS} days",
        evidence=evidence,
        action="Review or close",
        action_note=f"{len(stale)} pull request{'s' if len(stale) != 1 else ''} waiting",
    )


def failing_ci_rate(runs: list[dict], *, window: int = 20) -> Signal | None:
    recent = runs[:window]
    if not recent:
        return None
    failing = [r for r in recent if r.get("status") == "failing"]
    if not failing:
        return None
    rate = round(len(failing) / len(recent) * 100)
    # a streak on the *same* workflow+branch is the interesting case (one
    # broken thing repeating), separate from scattered unrelated failures
    streak_key = (failing[0].get("workflow_name"), failing[0].get("branch"))
    streak = 0
    for r in recent:
        if (r.get("workflow_name"), r.get("branch")) == streak_key and r.get("status") == "failing":
            streak += 1
        else:
            break
    evidence = [(r.get("run_label", "run"), r.get("failing_job") or "failed") for r in failing[:3]]
    title = f"CI fails {rate}% of the last {len(recent)} runs"
    if streak >= 2:
        title += f", {streak} in a row on the same workflow"
    return Signal(
        mark="×", severity="del", title=title, evidence=evidence,
        action="Open the failing pull request", action_note="Same root cause likely",
        trend="up" if rate >= 15 else "flat",
    )


def review_turnaround(prs: list[dict]) -> Signal | None:
    """Median hours from opened_at to first review/merge, for merged PRs only."""
    merged = [p for p in prs if p.get("is_merged") and p.get("closed_at")]
    if len(merged) < 3:
        return None
    hours = sorted((_parse(p["closed_at"]) - _parse(p["opened_at"])).total_seconds() / 3600 for p in merged)
    median = hours[len(hours) // 2]
    if median < 24:
        return None
    return Signal(
        mark="·", severity="mute",
        title=f"Median time to merge is {median:.0f} hours across {len(merged)} recent pull requests",
        evidence=[("median", f"{median:.0f}h"), ("sample", f"{len(merged)} merged PRs")],
        action="Spread review load", action_note="Computed from merge timestamps",
        trend="up" if median > 48 else "flat",
    )


def unresolved_long_thread(issues: list[dict], *, comment_threshold: int = 25) -> Signal | None:
    hot = [i for i in issues if i.get("state") == "open" and i.get("comment_count", 0) >= comment_threshold]
    if not hot:
        return None
    hot.sort(key=lambda i: i["comment_count"], reverse=True)
    top = hot[0]
    return Signal(
        mark="?", severity="iris",
        title=f"{top['repo']}#{top['number']} has run {top['comment_count']} comments without a decision",
        evidence=[(f"{top['repo']}#{top['number']}", top.get("title", ""))],
        action="Read the summary", action_note="Decisions and open questions extracted",
    )


def compute_all(*, pulls: list[dict], issues: list[dict], runs: list[dict]) -> list[Signal]:
    checks = [stale_pull_requests(pulls), failing_ci_rate(runs), review_turnaround(pulls), unresolved_long_thread(issues)]
    return [s for s in checks if s is not None]
