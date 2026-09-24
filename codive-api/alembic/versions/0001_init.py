"""initial schema

Revision ID: 0001_init
Revises:
Create Date: 2026-09-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

_EMBED_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("github_id", sa.Integer, unique=True, index=True, nullable=False),
        sa.Column("github_login", sa.String(255), index=True, nullable=False),
        sa.Column("avatar_url", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "github_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("encrypted_access_token", sa.Text, nullable=False),
        sa.Column("scope", sa.String(255)),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "repositories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("github_repo_id", sa.Integer, index=True, nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("default_branch", sa.String(255), nullable=False, server_default="main"),
        sa.Column("language", sa.String(64)),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="public"),
        sa.Column("stars", sa.Integer, nullable=False, server_default="0"),
        sa.Column("forks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latest_release", sa.String(255)),
        sa.Column("is_watched", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("sync_cursor", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_user_id", "full_name", name="uq_repo_owner_fullname"),
    )

    op.create_table(
        "commits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repo_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("sha", sa.String(40), index=True, nullable=False),
        sa.Column("author_login", sa.String(255)),
        sa.Column("author_name", sa.String(255)),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("additions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("deletions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("committed_at", sa.DateTime(timezone=True), index=True, nullable=False),
        sa.Column("pull_request_number", sa.Integer),
        sa.Column("url", sa.String(512)),
        sa.UniqueConstraint("repo_id", "sha", name="uq_commit_repo_sha"),
    )

    op.create_table(
        "pull_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repo_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("number", sa.Integer, index=True, nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("author_login", sa.String(255)),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("is_merged", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_draft", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("branch", sa.String(255)),
        sa.Column("base_branch", sa.String(255)),
        sa.Column("additions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("deletions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("changed_files", sa.Integer, nullable=False, server_default="0"),
        sa.Column("review_decision", sa.String(32)),
        sa.Column("ci_state", sa.String(16)),
        sa.Column("labels", JSONB, nullable=False, server_default="[]"),
        sa.Column("files_changed", JSONB, nullable=False, server_default="[]"),
        sa.Column("ai_summary", sa.Text),
        sa.Column("ai_findings", JSONB, nullable=False, server_default="[]"),
        sa.Column("ai_generated_at", sa.DateTime(timezone=True)),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("url", sa.String(512)),
        sa.UniqueConstraint("repo_id", "number", name="uq_pr_repo_number"),
    )

    op.create_table(
        "issues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repo_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("number", sa.Integer, index=True, nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("author_login", sa.String(255)),
        sa.Column("assignee_login", sa.String(255)),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("labels", JSONB, nullable=False, server_default="[]"),
        sa.Column("comment_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ai_summary", sa.Text),
        sa.Column("ai_decisions", JSONB, nullable=False, server_default="[]"),
        sa.Column("ai_open_questions", JSONB, nullable=False, server_default="[]"),
        sa.Column("ai_generated_at", sa.DateTime(timezone=True)),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("url", sa.String(512)),
        sa.UniqueConstraint("repo_id", "number", name="uq_issue_repo_number"),
    )

    op.create_table(
        "issue_comments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issue_id", sa.String(36), sa.ForeignKey("issues.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("author_login", sa.String(255)),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repo_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("workflow_name", sa.String(255), nullable=False),
        sa.Column("run_number", sa.Integer, nullable=False),
        sa.Column("branch", sa.String(255)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("failing_job", sa.String(512)),
        sa.Column("commit_sha", sa.String(40)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("url", sa.String(512)),
    )

    op.create_table(
        "code_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repo_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("path", sa.String(1024), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("commit_sha", sa.String(40)),
        sa.Column("embedding", Vector(_EMBED_DIM) if Vector is not None else JSONB),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_code_chunks_repo_path", "code_chunks", ["repo_id", "path"])

    op.create_table(
        "daily_briefs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("brief_date", sa.String(10), nullable=False),
        sa.Column("lede", sa.Text, nullable=False),
        sa.Column("counters", JSONB, nullable=False, server_default="{}"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_by", sa.String(16), nullable=False, server_default="template"),
        sa.UniqueConstraint("user_id", "brief_date", name="uq_brief_user_date"),
    )

    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repo_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(64)),
        sa.Column("error", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )

    # HNSW index for approximate nearest-neighbor search over code_chunks.
    # Built CONCURRENTLY-equivalent isn't available inside a transactional
    # migration on every provider, so this stays a plain index - fine at
    # MVP scale (a few thousand chunks), and documented in the README for
    # anyone who later needs to rebuild it CONCURRENTLY outside a migration.
    if Vector is not None:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_code_chunks_embedding "
            "ON code_chunks USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    op.drop_table("sync_jobs")
    op.drop_table("daily_briefs")
    op.drop_index("ix_code_chunks_embedding", table_name="code_chunks")
    op.drop_index("ix_code_chunks_repo_path", table_name="code_chunks")
    op.drop_table("code_chunks")
    op.drop_table("workflow_runs")
    op.drop_table("issue_comments")
    op.drop_table("issues")
    op.drop_table("pull_requests")
    op.drop_table("commits")
    op.drop_table("repositories")
    op.drop_table("github_accounts")
    op.drop_table("users")
