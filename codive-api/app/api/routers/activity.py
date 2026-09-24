from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_user_token
from app.db.base import get_db
from app.db.models import Commit, Issue, PullRequest, Repository, User, WorkflowRun
from app.services.brief import compute_counters, generate_lede
from app.services.github_client import GitHubClient, GitHubAPIError
from app.services.health_signals import compute_all

router = APIRouter(tags=["activity"])


async def _owned_repo_ids(user: User, db: AsyncSession, repo: str | None) -> list[str]:
    q = select(Repository.id, Repository.full_name).where(Repository.owner_user_id == user.id, Repository.is_watched.is_(True))
    rows = (await db.execute(q)).all()
    if repo and repo != "all":
        rows = [r for r in rows if r.full_name == repo]
    return [r.id for r in rows]


def _pr_out(p: PullRequest, repo_name: str) -> dict:
    return {
        "n": p.number, "repo": repo_name, "title": p.title, "author": p.author_login,
        "state": "merged" if p.is_merged else p.state, "draft": p.is_draft,
        "opened_at": p.opened_at.isoformat(), "updated_at": p.updated_at.isoformat(),
        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
        "files": p.changed_files, "add": p.additions, "del": p.deletions,
        "ci": p.ci_state or "unknown", "review_decision": p.review_decision,
        "branch": p.branch, "labels": p.labels or [], "url": p.url,
        "summary": p.ai_summary, "findings": p.ai_findings or [],
        "changed": [f"{f['path']} - +{f.get('additions',0)}/-{f.get('deletions',0)}" for f in (p.files_changed or [])],
    }


def _issue_out(i: Issue, repo_name: str) -> dict:
    return {
        "n": i.number, "repo": repo_name, "title": i.title, "author": i.author_login,
        "state": i.state, "assignee": i.assignee_login or "-", "labels": i.labels or [],
        "comments": i.comment_count, "opened_at": i.opened_at.isoformat(), "url": i.url,
        "summary": i.ai_summary, "decisions": i.ai_decisions or [], "open": i.ai_open_questions or [],
    }


@router.get("/prs")
async def list_prs(repo: str | None = Query(default=None), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ids = await _owned_repo_ids(user, db, repo)
    if not ids:
        return []
    rows = (await db.execute(
        select(PullRequest, Repository.full_name)
        .join(Repository, Repository.id == PullRequest.repo_id)
        .where(PullRequest.repo_id.in_(ids))
        .order_by(PullRequest.updated_at.desc())
        .limit(200)
    )).all()
    return [_pr_out(p, name) for p, name in rows]


@router.get("/issues")
async def list_issues(repo: str | None = Query(default=None), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ids = await _owned_repo_ids(user, db, repo)
    if not ids:
        return []
    rows = (await db.execute(
        select(Issue, Repository.full_name)
        .join(Repository, Repository.id == Issue.repo_id)
        .where(Issue.repo_id.in_(ids), Issue.state == "open")
        .order_by(Issue.updated_at.desc())
        .limit(200)
    )).all()
    return [_issue_out(i, name) for i, name in rows]


@router.get("/commits")
async def list_commits(repo: str | None = Query(default=None), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ids = await _owned_repo_ids(user, db, repo)
    if not ids:
        return []
    rows = (await db.execute(
        select(Commit, Repository.full_name)
        .join(Repository, Repository.id == Commit.repo_id)
        .where(Commit.repo_id.in_(ids))
        .order_by(Commit.committed_at.desc())
        .limit(100)
    )).all()
    return [
        {"sha": c.sha, "repo": name, "author": c.author_login or c.author_name or "unknown",
         "msg": c.message.splitlines()[0][:200], "committed_at": c.committed_at.isoformat(),
         "add": c.additions, "del": c.deletions, "pr": c.pull_request_number, "url": c.url}
        for c, name in rows
    ]


@router.get("/commit-detail")
async def commit_detail(
    repo: str = Query(..., min_length=3),
    sha: str = Query(..., min_length=7, max_length=40),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch one commit and its real GitHub file patches on demand.

    Commit history is stored locally for fast dashboards, but the full patch
    is deliberately fetched from GitHub only when a developer opens a
    commit. That keeps normal synchronization light while making commit
    inspection evidence-backed and current.
    """
    repository = await db.scalar(
        select(Repository).where(
            Repository.owner_user_id == user.id,
            Repository.full_name == repo,
            Repository.is_watched.is_(True),
        )
    )
    if repository is None:
        raise HTTPException(404, "Repository is not in your watched repositories")

    try:
        token = await get_user_token(user, db)
        owner, name = repo.split("/", 1)
        async with GitHubClient(token) as gh:
            detail = await gh.commit_detail(owner, name, sha)
    except ValueError as exc:
        raise HTTPException(400, "repo must be in owner/name format") from exc
    except GitHubAPIError as exc:
        status = exc.status if exc.status in {400, 404, 409, 403, 429} else 502
        raise HTTPException(status, str(exc)) from exc

    return {"repo": repo, **detail}


@router.get("/ci")
async def list_ci(repo: str | None = Query(default=None), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ids = await _owned_repo_ids(user, db, repo)
    if not ids:
        return []
    rows = (await db.execute(
        select(WorkflowRun, Repository.full_name)
        .join(Repository, Repository.id == WorkflowRun.repo_id)
        .where(WorkflowRun.repo_id.in_(ids))
        .order_by(WorkflowRun.started_at.desc())
        .limit(50)
    )).all()
    return [
        {"repo": name, "wf": w.workflow_name, "branch": w.branch, "state": w.status,
         "job": w.failing_job, "run": f"#{w.run_number}", "started_at": w.started_at.isoformat(), "url": w.url}
        for w, name in rows
    ]


@router.get("/health-signals")
async def health_signals(repo: str | None = Query(default=None), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ids = await _owned_repo_ids(user, db, repo)
    if not ids:
        return []
    pr_rows = (await db.execute(
        select(PullRequest, Repository.full_name).join(Repository, Repository.id == PullRequest.repo_id)
        .where(PullRequest.repo_id.in_(ids))
    )).all()
    issue_rows = (await db.execute(
        select(Issue, Repository.full_name).join(Repository, Repository.id == Issue.repo_id)
        .where(Issue.repo_id.in_(ids))
    )).all()
    run_rows = (await db.execute(
        select(WorkflowRun, Repository.full_name).join(Repository, Repository.id == WorkflowRun.repo_id)
        .where(WorkflowRun.repo_id.in_(ids)).order_by(WorkflowRun.started_at.desc()).limit(100)
    )).all()

    pulls = [{"repo": name, "number": p.number, "state": p.state, "is_merged": p.is_merged,
              "opened_at": p.opened_at.isoformat(), "closed_at": p.closed_at.isoformat() if p.closed_at else None}
             for p, name in pr_rows]
    issues = [{"repo": name, "number": i.number, "state": i.state, "comment_count": i.comment_count, "title": i.title}
              for i, name in issue_rows]
    runs = [{"workflow_name": w.workflow_name, "branch": w.branch, "status": w.status,
              "failing_job": w.failing_job, "run_label": f"{name} {w.run_number}"} for w, name in run_rows]

    signals = compute_all(pulls=pulls, issues=issues, runs=runs)
    return [
        {"mark": s.mark, "cls": {"mute": "g-mute", "warn": "g-warn", "del": "g-del", "iris": "g-iris"}[s.severity],
         "t": s.title, "evidence": s.evidence, "action": s.action, "actionNote": s.action_note, "trend": s.trend}
        for s in signals
    ]


@router.get("/brief")
async def daily_brief(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Computed on demand rather than only read from the scheduler's cached
    DailyBrief row - a freshly onboarded user (or one on a free-tier
    instance that just cold-started, see workers/scheduler.py) shouldn't
    see an empty brief just because a cron job hasn't fired yet. Real
    counters always; the lede is AI-written if a key is configured, a
    plain templated sentence built from the same real numbers if not -
    see app/services/brief.py.
    """
    from datetime import datetime, timezone

    ids = await _owned_repo_ids(user, db, None)
    if not ids:
        return {"lede": "Connect a repository to get your first brief.", "counters": {
            "open_prs": 0, "waiting_on_you": 0, "ci_failures": 0, "stale_issues": 0,
        }, "generated_by": "template"}

    pr_rows = (await db.execute(
        select(PullRequest, Repository.full_name).join(Repository, Repository.id == PullRequest.repo_id)
        .where(PullRequest.repo_id.in_(ids))
    )).all()
    issue_rows = (await db.execute(
        select(Issue, Repository.full_name).join(Repository, Repository.id == Issue.repo_id)
        .where(Issue.repo_id.in_(ids), Issue.state == "open")
    )).all()
    run_rows = (await db.execute(
        select(WorkflowRun, Repository.full_name).join(Repository, Repository.id == WorkflowRun.repo_id)
        .where(WorkflowRun.repo_id.in_(ids)).order_by(WorkflowRun.started_at.desc()).limit(10)
    )).all()

    now = datetime.now(timezone.utc)
    pull_dicts = [
        {"repo": name, "number": p.number, "state": p.state, "is_draft": p.is_draft,
         "is_merged": p.is_merged, "review_decision": p.review_decision}
        for p, name in pr_rows
    ]
    issue_dicts = [
        {"state": i.state, "age_days": (now - i.opened_at).days}
        for i, _ in issue_rows
    ]
    run_dicts = [{"status": w.status, "workflow_name": w.workflow_name} for w, _ in run_rows]

    counters = compute_counters(pulls=pull_dicts, issues=issue_dicts, runs=run_dicts)
    top_items = [
        {"repo": name, "number": p.number}
        for p, name in pr_rows
        if p.state == "open" and not p.is_draft and p.review_decision in (None, "none", "changes_requested")
    ][:3]
    lede, generated_by = await generate_lede(counters=counters, top_items=top_items)
    return {"lede": lede, "counters": counters, "generated_by": generated_by}
