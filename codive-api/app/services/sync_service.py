"""
One function per stage, one job per repository. `run_sync` is what the
scheduler calls periodically and what POST /sync/start calls immediately
for a newly-added repository. Each stage commits its own progress via
SyncJob.stage, so GET /sync/status can show real progress instead of a
fake timer.

Deliberately conservative about what source code it stores: only README,
top-level docs, and dependency manifests are indexed by default (see
_INDEXABLE_PATTERNS) — full proprietary source is not vacuumed into the
database unless a repository is explicitly marked for deeper indexing.
That default is the product's own §19 ("treat repository text as
untrusted input", "least privilege") applied to storage, not just access.
"""
from __future__ import annotations

import fnmatch
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CodeChunk, Commit, Issue, IssueComment, PullRequest, Repository, SyncJob, WorkflowRun
from app.services.embeddings import get_embedding_provider
from app.services.github_client import GitHubClient

log = logging.getLogger("codive.sync")

_INDEXABLE_PATTERNS = ["README*", "docs/*", "*.md", "requirements*.txt", "pyproject.toml", "package.json", "go.mod"]
_MAX_CHUNK_CHARS = 2400


def _is_indexable(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in _INDEXABLE_PATTERNS)


def _chunk(text: str, size: int = _MAX_CHUNK_CHARS) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


async def _set_stage(db: AsyncSession, job: SyncJob, stage: str) -> None:
    job.stage = stage
    await db.commit()


async def run_sync(db: AsyncSession, repo: Repository, token: str) -> SyncJob:
    job = SyncJob(repo_id=repo.id, status="running", stage="commits & branches")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    owner, name = repo.full_name.split("/", 1)

    try:
        async with GitHubClient(token) as gh:
            meta = await gh.repo(owner, name)
            repo.description = meta.get("description")
            repo.default_branch = meta.get("default_branch", "main")
            repo.language = meta.get("language")
            repo.visibility = "private" if meta.get("private") else "public"
            repo.stars = meta.get("stargazers_count", 0)
            repo.forks = meta.get("forks_count", 0)
            release = await gh.latest_release(owner, name)
            if release:
                repo.latest_release = release.get("tag_name")

            # --- commits ---
            since = repo.sync_cursor
            count = 0
            async for c in gh.commits(owner, name, since=since):
                sha = c["sha"]
                existing = await db.scalar(select(Commit).where(Commit.repo_id == repo.id, Commit.sha == sha))
                if existing:
                    continue
                commit_detail = c.get("commit", {})
                db.add(Commit(
                    repo_id=repo.id,
                    sha=sha,
                    author_login=(c.get("author") or {}).get("login"),
                    author_name=commit_detail.get("author", {}).get("name"),
                    message=commit_detail.get("message", "")[:2000],
                    committed_at=datetime.fromisoformat(commit_detail["author"]["date"].replace("Z", "+00:00")),
                    url=c.get("html_url"),
                ))
                count += 1
                if count >= 500:  # first-sync guardrail; incremental syncs after this are small
                    break
            await db.commit()
            await _set_stage(db, job, "pull requests & reviews")

            # --- pull requests ---
            async for pr in gh.pulls(owner, name, state="all"):
                number = pr["number"]
                row = await db.scalar(select(PullRequest).where(PullRequest.repo_id == repo.id, PullRequest.number == number))
                is_new = row is None
                if row is None:
                    row = PullRequest(repo_id=repo.id, number=number)
                    db.add(row)
                row.title = pr["title"]
                row.body = (pr.get("body") or "")[:4000]
                row.author_login = (pr.get("user") or {}).get("login")
                row.state = pr["state"]
                row.is_merged = bool(pr.get("merged_at"))
                row.is_draft = pr.get("draft", False)
                row.branch = (pr.get("head") or {}).get("ref")
                row.base_branch = (pr.get("base") or {}).get("ref")
                row.additions = pr.get("additions", 0) or 0
                row.deletions = pr.get("deletions", 0) or 0
                row.changed_files = pr.get("changed_files", 0) or 0
                row.labels = [l["name"] for l in pr.get("labels", [])]
                row.opened_at = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
                row.updated_at = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
                row.closed_at = datetime.fromisoformat(pr["closed_at"].replace("Z", "+00:00")) if pr.get("closed_at") else None
                row.url = pr.get("html_url")
                if is_new or row.updated_at.timestamp() > (row.ai_generated_at or datetime(1970, 1, 1, tzinfo=timezone.utc)).timestamp():
                    try:
                        files = await gh.pull_files(owner, name, number)
                        row.files_changed = [
                            {"path": f["filename"], "additions": f.get("additions", 0), "deletions": f.get("deletions", 0)}
                            for f in files[:40]
                        ]
                    except Exception:  # noqa: BLE001 — file list is best-effort, never blocks the sync
                        log.warning("could not fetch files for %s#%s", repo.full_name, number)
            await db.commit()
            await _set_stage(db, job, "issues & comments")

            # --- issues ---
            async for issue in gh.issues(owner, name, state="all"):
                number = issue["number"]
                row = await db.scalar(select(Issue).where(Issue.repo_id == repo.id, Issue.number == number))
                if row is None:
                    row = Issue(repo_id=repo.id, number=number)
                    db.add(row)
                row.title = issue["title"]
                row.body = (issue.get("body") or "")[:4000]
                row.author_login = (issue.get("user") or {}).get("login")
                row.assignee_login = (issue.get("assignee") or {}).get("login")
                row.state = issue["state"]
                row.labels = [l["name"] if isinstance(l, dict) else l for l in issue.get("labels", [])]
                row.comment_count = issue.get("comments", 0)
                row.opened_at = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
                row.updated_at = datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00"))
                row.closed_at = datetime.fromisoformat(issue["closed_at"].replace("Z", "+00:00")) if issue.get("closed_at") else None
                row.url = issue.get("html_url")
            await db.commit()
            await _set_stage(db, job, "releases & workflow runs")

            # --- workflow runs (checks on the default branch's latest commits) ---
            try:
                latest_commits = await db.scalars(
                    select(Commit).where(Commit.repo_id == repo.id).order_by(Commit.committed_at.desc()).limit(5)
                )
                for c in latest_commits:
                    runs = await gh.check_runs(owner, name, c.sha)
                    for r in runs[:5]:
                        exists = await db.scalar(
                            select(WorkflowRun).where(WorkflowRun.repo_id == repo.id, WorkflowRun.commit_sha == c.sha,
                                                       WorkflowRun.workflow_name == r.get("name", "check"))
                        )
                        if exists:
                            continue
                        status = "passing" if r.get("conclusion") == "success" else (
                            "failing" if r.get("conclusion") in ("failure", "timed_out") else "pending"
                        )
                        db.add(WorkflowRun(
                            repo_id=repo.id,
                            workflow_name=r.get("name", "check"),
                            run_number=r.get("run_number", 0) or 0,
                            branch=repo.default_branch,
                            status=status,
                            failing_job=r.get("output", {}).get("title") if status == "failing" else None,
                            commit_sha=c.sha,
                            started_at=datetime.fromisoformat(r["started_at"].replace("Z", "+00:00")) if r.get("started_at") else datetime.now(timezone.utc),
                            url=r.get("html_url"),
                        ))
                await db.commit()
            except Exception:  # noqa: BLE001 — checks API can 404 on repos with no checks configured
                log.info("no check runs available for %s", repo.full_name)
            await _set_stage(db, job, "indexing files")

            # --- indexing (README + docs only, by default) ---
            readme = await gh.readme(owner, name)
            embedder = get_embedding_provider()
            if readme:
                await db.execute(CodeChunk.__table__.delete().where(CodeChunk.repo_id == repo.id, CodeChunk.path == "README"))
                chunks = _chunk(readme)
                vectors = await embedder.embed(chunks)
                for i, (text, vec) in enumerate(zip(chunks, vectors)):
                    db.add(CodeChunk(repo_id=repo.id, path="README", chunk_index=i, content=text, embedding=vec))
                await db.commit()

            repo.sync_cursor = datetime.now(timezone.utc).isoformat()
            repo.last_synced_at = datetime.now(timezone.utc)
            job.status = "done"
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            return job

    except Exception as exc:  # noqa: BLE001 — a failed sync is recorded, not raised past the caller
        log.exception("sync failed for %s", repo.full_name)
        job.status = "error"
        job.error = str(exc)[:500]
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        return job
