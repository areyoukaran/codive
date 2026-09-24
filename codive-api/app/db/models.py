"""
Schema follows §15 of the product blueprint, trimmed to what Phase 1-3
(foundation, daily usefulness, AI) actually needs. Every synced row keeps
its GitHub source id and a `repo_id` foreign key, so nothing is stored
without a traceable origin, and every query that lists a user's data is
scoped through `repo_id -> Repository.owner_user_id` — there is no
cross-tenant table to forget to filter.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # keeps `alembic revision --autogenerate` importable
    Vector = None      # even before pgvector-python is installed locally


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    github_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    github_login: Mapped[str] = mapped_column(String(255), index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    account: Mapped["GithubAccount"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    repositories: Mapped[list["Repository"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class GithubAccount(Base):
    """One row per user. The GitHub access token is stored encrypted (see
    app.core.security) — never in plaintext, never logged."""
    __tablename__ = "github_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    encrypted_access_token: Mapped[str] = mapped_column(Text)
    scope: Mapped[str | None] = mapped_column(String(255))
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="account")


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("owner_user_id", "full_name", name="uq_repo_owner_fullname"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    github_repo_id: Mapped[int] = mapped_column(Integer, index=True)
    full_name: Mapped[str] = mapped_column(String(255))          # "owner/name"
    description: Mapped[str | None] = mapped_column(Text)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    language: Mapped[str | None] = mapped_column(String(64))
    visibility: Mapped[str] = mapped_column(String(16), default="public")
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    latest_release: Mapped[str | None] = mapped_column(String(255))
    is_watched: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_cursor: Mapped[str | None] = mapped_column(String(64))  # last commit SHA / ISO timestamp walked to
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    owner: Mapped["User"] = relationship(back_populates="repositories")
    commits: Mapped[list["Commit"]] = relationship(back_populates="repo", cascade="all, delete-orphan")
    pull_requests: Mapped[list["PullRequest"]] = relationship(back_populates="repo", cascade="all, delete-orphan")
    issues: Mapped[list["Issue"]] = relationship(back_populates="repo", cascade="all, delete-orphan")
    workflow_runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="repo", cascade="all, delete-orphan")
    code_chunks: Mapped[list["CodeChunk"]] = relationship(back_populates="repo", cascade="all, delete-orphan")


class Commit(Base):
    __tablename__ = "commits"
    __table_args__ = (UniqueConstraint("repo_id", "sha", name="uq_commit_repo_sha"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    sha: Mapped[str] = mapped_column(String(40), index=True)
    author_login: Mapped[str | None] = mapped_column(String(255))
    author_name: Mapped[str | None] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    pull_request_number: Mapped[int | None] = mapped_column(Integer)
    url: Mapped[str | None] = mapped_column(String(512))

    repo: Mapped["Repository"] = relationship(back_populates="commits")


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (UniqueConstraint("repo_id", "number", name="uq_pr_repo_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(512))
    body: Mapped[str | None] = mapped_column(Text)
    author_login: Mapped[str | None] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(16))          # open | closed
    is_merged: Mapped[bool] = mapped_column(Boolean, default=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    branch: Mapped[str | None] = mapped_column(String(255))
    base_branch: Mapped[str | None] = mapped_column(String(255))
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    changed_files: Mapped[int] = mapped_column(Integer, default=0)
    review_decision: Mapped[str | None] = mapped_column(String(32))  # approved | changes_requested | none
    ci_state: Mapped[str | None] = mapped_column(String(16))          # passing | failing | pending | none
    labels: Mapped[list] = mapped_column(JSONB, default=list)
    files_changed: Mapped[list] = mapped_column(JSONB, default=list)  # [{path, additions, deletions, patch_excerpt}]
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_findings: Mapped[list] = mapped_column(JSONB, default=list)    # [{severity, title, location, body, fix, confidence}]
    ai_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    url: Mapped[str | None] = mapped_column(String(512))

    repo: Mapped["Repository"] = relationship(back_populates="pull_requests")


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("repo_id", "number", name="uq_issue_repo_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(512))
    body: Mapped[str | None] = mapped_column(Text)
    author_login: Mapped[str | None] = mapped_column(String(255))
    assignee_login: Mapped[str | None] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(16))
    labels: Mapped[list] = mapped_column(JSONB, default=list)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_decisions: Mapped[list] = mapped_column(JSONB, default=list)
    ai_open_questions: Mapped[list] = mapped_column(JSONB, default=list)
    ai_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    url: Mapped[str | None] = mapped_column(String(512))

    repo: Mapped["Repository"] = relationship(back_populates="issues")
    comments: Mapped[list["IssueComment"]] = relationship(back_populates="issue", cascade="all, delete-orphan")


class IssueComment(Base):
    __tablename__ = "issue_comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    author_login: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    issue: Mapped["Issue"] = relationship(back_populates="comments")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    workflow_name: Mapped[str] = mapped_column(String(255))
    run_number: Mapped[int] = mapped_column(Integer)
    branch: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16))          # passing | failing | pending
    failing_job: Mapped[str | None] = mapped_column(String(512))
    commit_sha: Mapped[str | None] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    url: Mapped[str | None] = mapped_column(String(512))

    repo: Mapped["Repository"] = relationship(back_populates="workflow_runs")


_EMBED_DIM = 384  # matches the default local + Gemini-compatible dimension used in app/services/embeddings.py


class CodeChunk(Base):
    """Indexed source: README, docs, config, and selected file excerpts —
    never full proprietary source dumps by default (see sync_service)."""
    __tablename__ = "code_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(1024))
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    commit_sha: Mapped[str | None] = mapped_column(String(40))
    if Vector is not None:
        embedding = mapped_column(Vector(_EMBED_DIM), nullable=True)
    else:  # pragma: no cover — only hit if pgvector-python truly isn't installed
        embedding = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    repo: Mapped["Repository"] = relationship(back_populates="code_chunks")

    __table_args__ = (Index("ix_code_chunks_repo_path", "repo_id", "path"),)


class DailyBrief(Base):
    __tablename__ = "daily_briefs"
    __table_args__ = (UniqueConstraint("user_id", "brief_date", name="uq_brief_user_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    brief_date: Mapped[str] = mapped_column(String(10))   # ISO date, one per user per day
    lede: Mapped[str] = mapped_column(Text)
    counters: Mapped[dict] = mapped_column(JSONB, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    generated_by: Mapped[str] = mapped_column(String(16), default="template")  # template | groq | gemini


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued | running | done | error
    stage: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
