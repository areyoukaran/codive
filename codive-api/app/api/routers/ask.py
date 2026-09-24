from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_user_token
from app.core.config import get_settings
from app.core.rate_limit import get_limiter
from app.db.base import get_db
from app.db.models import Commit, Issue, PullRequest, Repository, User, WorkflowRun
from app.services.github_client import GitHubClient, GitHubAPIError
from app.services.llm import ASK_SYSTEM_PROMPT, LLMError, get_llm_provider

router = APIRouter(tags=["ask"])


class AskRequest(BaseModel):
    question: str
    scope: str | None = "all"
    view: dict | None = None
    commit_repo: str | None = None
    commit_sha: str | None = None


async def _build_context(
    user: User,
    db: AsyncSession,
    scope: str | None,
    *,
    commit_repo: str | None = None,
    commit_sha: str | None = None,
) -> dict:
    repo_q = select(Repository).where(Repository.owner_user_id == user.id, Repository.is_watched.is_(True))
    effective_scope = commit_repo or scope
    if effective_scope and effective_scope != "all":
        repo_q = repo_q.where(Repository.full_name == effective_scope)
    repos = list(await db.scalars(repo_q))
    ids = [r.id for r in repos]
    if not ids:
        return {"repositories": [], "pull_requests": [], "issues": [], "commits": [], "workflow_runs": []}

    prs = (await db.execute(
        select(PullRequest, Repository.full_name).join(Repository, Repository.id == PullRequest.repo_id)
        .where(PullRequest.repo_id.in_(ids)).order_by(PullRequest.updated_at.desc()).limit(30)
    )).all()
    issues = (await db.execute(
        select(Issue, Repository.full_name).join(Repository, Repository.id == Issue.repo_id)
        .where(Issue.repo_id.in_(ids), Issue.state == "open").order_by(Issue.updated_at.desc()).limit(30)
    )).all()
    commits = (await db.execute(
        select(Commit, Repository.full_name).join(Repository, Repository.id == Commit.repo_id)
        .where(Commit.repo_id.in_(ids)).order_by(Commit.committed_at.desc()).limit(20)
    )).all()
    runs = (await db.execute(
        select(WorkflowRun, Repository.full_name).join(Repository, Repository.id == WorkflowRun.repo_id)
        .where(WorkflowRun.repo_id.in_(ids)).order_by(WorkflowRun.started_at.desc()).limit(10)
    )).all()

    context = {
        "repositories": [{"full_name": r.full_name, "language": r.language, "ci": None, "description": r.description} for r in repos],
        "pull_requests": [
            {"repo": name, "number": p.number, "title": p.title, "author": p.author_login, "state": "merged" if p.is_merged else p.state,
             "ci": p.ci_state, "additions": p.additions, "deletions": p.deletions, "summary": p.ai_summary,
             "findings": p.ai_findings or []}
            for p, name in prs
        ],
        "issues": [
            {"repo": name, "number": i.number, "title": i.title, "comments": i.comment_count,
             "summary": i.ai_summary, "decisions": i.ai_decisions or [], "open_questions": i.ai_open_questions or []}
            for i, name in issues
        ],
        "commits": [
            {"sha": c.sha[:7], "repo": name, "author": c.author_login, "message": c.message.splitlines()[0][:200]}
            for c, name in commits
        ],
        "workflow_runs": [
            {"repo": name, "workflow": w.workflow_name, "status": w.status, "failing_job": w.failing_job}
            for w, name in runs
        ],
    }

    if commit_repo and commit_sha:
        repository = next((r for r in repos if r.full_name == commit_repo), None)
        if repository is not None:
            try:
                token = await get_user_token(user, db)
                owner, name = commit_repo.split("/", 1)
                async with GitHubClient(token) as gh:
                    detail = await gh.commit_detail(owner, name, commit_sha)
                context["commit"] = {
                    "repo": commit_repo,
                    "sha": detail.get("sha"),
                    "message": detail.get("message"),
                    "stats": detail.get("stats"),
                    "files": [
                        {
                            "path": f.get("filename"),
                            "status": f.get("status"),
                            "additions": f.get("additions", 0),
                            "deletions": f.get("deletions", 0),
                            "patch": (f.get("patch") or "")[:12000],
                        }
                        for f in detail.get("files", [])[:40]
                    ],
                }
            except (GitHubAPIError, ValueError):
                # The normal repository context remains usable even if the
                # live patch cannot be fetched. The commit page reports the
                # fetch error separately.
                context["commit"] = {
                    "repo": commit_repo,
                    "sha": commit_sha,
                    "diff_unavailable": True,
                }

    return context


@router.post("/ask")
async def ask(body: AskRequest, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    limiter = get_limiter(getattr(request.app.state, "redis", None))
    result = limiter.allow(f"ask:{user.id}", settings.ask_rate_limit_per_minute, 60)
    if hasattr(result, "__await__"):
        result = await result
    if not result.allowed:
        raise HTTPException(429, f"Slow down a little - try again in {result.retry_after_seconds}s", headers={"Retry-After": str(result.retry_after_seconds)})

    if not body.question or not body.question.strip():
        raise HTTPException(400, "question is required")

    context = await _build_context(
        user,
        db,
        body.scope,
        commit_repo=body.commit_repo,
        commit_sha=body.commit_sha,
    )
    provider = get_llm_provider()

    # Keep commit diffs intact when a user is investigating a specific commit.
    # The old global 12k-character slice could cut the JSON in the middle of a
    # patch, leaving the model with commit metadata but not the actual change.
    context_json = json.dumps(context, ensure_ascii=False)
    if len(context_json) > 30000:
        if context.get("commit"):
            base_context = {k: v for k, v in context.items() if k != "commit"}
            base_json = json.dumps(base_context, ensure_ascii=False)
            remaining = max(8000, 30000 - len(base_json) - 2000)
            commit = dict(context["commit"])
            files = []
            used = 0
            for file in commit.get("files", []):
                patch = file.get("patch") or ""
                budget = max(0, remaining - used)
                if len(patch) > budget:
                    file = dict(file)
                    file["patch"] = patch[:budget]
                files.append(file)
                used += len(file.get("patch") or "")
                if used >= remaining:
                    break
            commit["files"] = files
            context = {**base_context, "commit": commit}
            context_json = json.dumps(context, ensure_ascii=False)
        else:
            context_json = context_json[:30000]

    user_prompt = (
        "REPOSITORY STATE (JSON):\n"
        + context_json
        + "\n\nQUESTION: "
        + body.question.strip()
    )

    try:
        answer = await provider.complete(ASK_SYSTEM_PROMPT, user_prompt, max_tokens=400)
    except LLMError as exc:
        raise HTTPException(503, str(exc)) from exc

    if not isinstance(answer, str) or not answer.strip():
        raise HTTPException(502, f"{provider.name} returned an empty answer")

    return {"answer": answer.strip(), "provider": provider.name}
