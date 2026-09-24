# Codive

### AI-Powered Developer Repository Intelligence

Codive is a developer-focused intelligence layer for GitHub repositories.

It connects to your repositories, synchronizes GitHub activity, identifies work that needs attention, analyzes repository health, and provides repository-aware AI assistance grounded in actual repository data.

> **What changed? What matters? What needs my attention? What should I do next?**

---

## Overview

Developers already have GitHub for commits, pull requests, issues, CI, and repository information.

The problem is that the important information is scattered across all of those surfaces.

Codive brings that information together into a single developer workflow:

```text
Connect GitHub
      ↓
Select repositories
      ↓
Initial synchronization
      ↓
Codive builds repository intelligence
      ↓
Daily developer dashboard
      ↓
Understand changes & identify attention items
      ↓
Ask Codive questions about your repositories
```

Codive is designed to be something a developer can open every morning to quickly understand the current state of their repositories.

---

## Features

### GitHub Integration

Connect your GitHub account through OAuth and select the repositories Codive should monitor.

Codive synchronizes:

* Commits
* Branches
* Pull requests
* Reviews
* Issues
* Issue comments
* Releases
* CI / workflow runs
* Repository metadata
* Contributors
* Repository documentation

Synchronization supports pagination, incremental updates, rate-limit handling, retries, and webhook events.

---

### Repository Dashboard

Get a consolidated view of repository activity and health.

Each repository can surface:

* Repository metadata
* Recent commits
* Open pull requests
* Open issues
* CI status
* Recent activity
* Health signals
* Contributors
* Releases
* Codive insights

Quick actions include:

* Summarize changes
* Review a pull request
* Explain the repository
* Find risky areas
* Ask questions about the codebase

---

### Daily Developer Brief

The daily brief is Codive's primary intelligence feature.

Instead of manually checking GitHub, Codive summarizes what changed since your previous visit and highlights work that deserves attention.

It can surface:

* Important commits
* Pull requests waiting for review
* CI failures
* Stale pull requests
* Stale issues
* Significant releases
* Potentially risky changes
* Blocked or unresolved work
* Suggested next actions

Example:

```text
TODAY'S REPO BRIEF

3   Important changes
2   PRs need review
1   CI failure
4   Stale issues
1   Potentially risky change
```

---

### Pull Request Intelligence

Codive provides repository-aware context around pull requests.

PR views can include:

* Author
* State
* Age
* Changed files
* Additions / deletions
* Reviews
* Comments
* CI status
* Linked issues
* Timeline

AI-assisted workflows can summarize changes and identify potential concerns using repository context.

The intended review pipeline is:

```text
PR metadata + diff
        ↓
Relevant repository context
        ↓
AI analysis
        ↓
Potential issues / risks
        ↓
Evidence & supporting context
```

AI findings are designed to remain evidence-backed rather than being treated as authoritative conclusions.

---

### Issue Intelligence

Codive analyzes issue activity to surface work that may require attention.

It tracks:

* Labels
* Assignees
* Age
* Activity
* Linked pull requests
* Comments
* Priority signals

It can identify:

* Stale issues
* Blocked work
* Rapidly changing issues
* Long periods of inactivity
* Unresolved questions

AI can also summarize long issue discussions and extract decisions.

---

### Repository Health

Codive uses measurable repository signals instead of reducing repository health to an arbitrary AI-generated score.

Signals can include:

* Stale PRs
* Stale issues
* CI failure frequency
* Dependency age
* Large or complex changes
* Test coverage when available
* Documentation gaps
* Release cadence
* Unresolved review comments

Each signal follows:

```text
Signal
  ↓
Evidence
  ↓
Suggested action
```

Example:

```text
3 PRs older than 14 days
        ↓
Show affected PRs
        ↓
Review or close stale PRs
```

---

### Repository-Aware AI

Codive includes an AI interface that understands the repository context instead of operating as a generic chatbot.

Questions can be scoped to:

* Repository
* Files
* Pull requests
* Issues
* Commits
* Branches
* Time ranges

Example questions:

```text
What changed in authentication this week?

Why was this function introduced?

Which PR introduced this dependency?

What could break if I change this module?

Summarize the last 20 commits.
```

Responses can reference the underlying repository sources so developers can trace the information back to GitHub data.

---

### Unified Search

Search across the repository's indexed information.

Supported sources include:

* Repositories
* Files
* Commits
* Pull requests
* Issues
* Documentation

Search is designed to support both exact and semantic retrieval while retaining source information such as repository, path, timestamp, and GitHub link.

---

### Webhooks & Background Synchronization

Codive supports GitHub webhooks for near-real-time repository events alongside scheduled synchronization.

The backend handles:

* Pagination
* Rate limits
* Retries
* Backoff
* Timeouts
* Duplicate events
* Webhook verification
* Partial failures
* Incremental synchronization

Background jobs handle tasks such as synchronization, indexing, embeddings, daily briefs, health analysis, and notifications.

---

## Architecture

```text
                         ┌─────────────────────┐
                         │       GitHub        │
                         │ OAuth / API / Hooks │
                         └──────────┬──────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────┐
│                    Codive API                           │
│                                                         │
│  Auth       Repository       Activity       Webhooks   │
│                                                         │
│  Sync       Health Signals   AI / LLM       Search     │
└───────────────┬─────────────────────────┬───────────────┘
                │                         │
                ▼                         ▼
        ┌───────────────┐         ┌───────────────┐
        │  PostgreSQL   │         │     Redis     │
        │   + pgvector  │         │ Cache / Jobs  │
        └───────────────┘         └───────────────┘
                │                         │
                └────────────┬────────────┘
                             ▼
                    ┌─────────────────┐
                    │ Background Jobs │
                    │ Sync / AI / RAG  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Codive Frontend │
                    │ HTML / CSS / JS │
                    └─────────────────┘
```

The product architecture follows a FastAPI API layer with GitHub integration, repository/activity services, AI and search services, PostgreSQL/pgvector, Redis, and background workers.

---

## Tech Stack

### Frontend

* HTML5
* CSS3
* Vanilla JavaScript
* Responsive UI
* Light / dark theme
* GitHub OAuth integration
* Unified search
* Repository dashboard

The frontend intentionally has **no build step or npm dependency requirement**.

### Backend

* Python
* FastAPI
* SQLAlchemy
* Pydantic
* AsyncIO
* HTTPX
* JWT
* Cryptography
* APScheduler

### Data

* PostgreSQL
* pgvector
* Redis
* AsyncPG
* Alembic

### AI

* LLM provider integration
* Embeddings
* Retrieval-augmented generation
* Repository-aware context
* Evidence-backed responses

### Infrastructure

* Docker
* Docker Compose
* GitHub Actions
* Render
* Neon
* Upstash

---

## Project Structure

```text
codive/
│
├── codive-site/
│   ├── index.html
│   ├── onboarding.html
│   ├── app.html
│   │
│   └── assets/
│       ├── app.js
│       ├── app.css
│       ├── site.css
│       ├── config.js
│       └── favicon.svg
│
├── codive-api/
│   ├── app/
│   │   ├── api/
│   │   │   └── routers/
│   │   ├── core/
│   │   ├── db/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── workers/
│   │
│   ├── alembic/
│   ├── tests/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── render.yaml
│   ├── requirements.txt
│   └── pyproject.toml
│
└── README.md
```

---

## API

The backend currently exposes endpoints covering authentication, repositories, synchronization, activity, health signals, daily briefs, AI questions, webhooks, and service health.

| Endpoint                    | Purpose                          |
| --------------------------- | -------------------------------- |
| `GET /auth/github/login`    | Start GitHub OAuth               |
| `GET /auth/github/callback` | OAuth callback                   |
| `GET /auth/me`              | Current authenticated user       |
| `POST /auth/logout`         | End session                      |
| `GET /repos/available`      | Available GitHub repositories    |
| `POST /repos/select`        | Select repositories to monitor   |
| `GET /repos`                | Watched repositories             |
| `POST /sync/start`          | Start repository synchronization |
| `GET /sync/status`          | Synchronization status           |
| `GET /prs`                  | Pull request activity            |
| `GET /issues`               | Issue activity                   |
| `GET /commits`              | Commit activity                  |
| `GET /ci`                   | CI / workflow activity           |
| `GET /health-signals`       | Repository health signals        |
| `GET /brief`                | Daily developer brief            |
| `POST /ask`                 | Repository-aware AI questions    |
| `POST /webhooks/github`     | GitHub webhook receiver          |
| `GET /health`               | Health check                     |
| `GET /ready`                | Readiness check                  |

Interactive API documentation is available through FastAPI's `/docs` endpoint during development.

---

## Running Locally

### Backend

```bash
cd codive-api
```

Create your environment file:

```bash
cp .env.example .env
```

Generate application secrets:

```bash
python3 scripts/gen-keys.py
```

Then start the backend infrastructure:

```bash
docker compose up --build
```

This starts:

* PostgreSQL + pgvector
* Redis
* Codive API

The API is exposed locally on:

```text
http://localhost:8001
```

Health check:

```bash
curl http://localhost:8001/health
```

---

### Frontend

```bash
cd codive-site
python3 -m http.server 5173
```

Open:

```text
http://localhost:5173
```

The frontend can run in demo mode without a backend.

---

## Demo Mode

Codive includes a standalone demo mode so the frontend can be explored without configuring GitHub OAuth, PostgreSQL, Redis, or an LLM provider.

When no API is configured:

```text
Frontend
   ↓
Demo data
   ↓
Dashboard
```

When the API is configured:

```text
Frontend
   ↓
Codive API
   ↓
GitHub
   ↓
Real repository data
```

The frontend automatically falls back to demo data when a user is not authenticated.

---

## Live Mode

Set the API URL in:

```text
codive-site/assets/config.js
```

```javascript
window.CODIVE = {
  apiBase: "https://your-api.onrender.com"
};
```

The same frontend then supports:

* GitHub OAuth
* Repository selection
* Real synchronization
* Real commits
* Real pull requests
* Real issues
* Real CI data
* Repository health signals
* Daily briefs
* Repository-aware AI questions

---

## Environment Variables

The backend supports configuration for:

```text
DATABASE_URL
REDIS_URL

SECRET_KEY
TOKEN_ENCRYPTION_KEY

GITHUB_CLIENT_ID
GITHUB_CLIENT_SECRET
GITHUB_WEBHOOK_SECRET

GROQ_API_KEY
GEMINI_API_KEY

FRONTEND_URL
BACKEND_URL
CORS_ORIGINS
```

LLM API keys are optional. Without an LLM provider configured, Codive can still generate data-driven responses using its existing repository information.

---

## Security

Codive treats repository data and GitHub content as untrusted input.

Security considerations include:

* GitHub OAuth
* Encrypted GitHub token storage
* Least-privilege permissions
* Webhook signature verification
* Rate limiting
* Tenant-aware repository access
* Secret management
* No secret logging
* Input validation
* CORS configuration
* Prompt-injection defenses
* Separation of untrusted repository content from system instructions

These requirements are part of the product architecture rather than being added as an afterthought.

---

## Testing

The backend includes tests covering core application logic such as:

* API smoke tests
* Encryption
* Embeddings
* Health signals
* LLM provider selection
* GitHub pagination
* Rate limiting
* Webhook verification

CI is configured through GitHub Actions.

Run the test suite with:

```bash
pytest
```

---

## Current MVP Scope

The current implementation covers the foundation, daily usefulness, and core AI phases of the product.

### Implemented

* GitHub OAuth
* Repository selection
* Repository synchronization
* GitHub activity
* Pull requests
* Issues
* Commits
* CI information
* Repository health signals
* Daily developer brief
* Repository-aware `/ask`
* Semantic search infrastructure
* PostgreSQL + pgvector
* Redis
* Webhooks
* Background scheduling
* Rate limiting
* Docker
* CI

### Planned

Some capabilities remain intentionally outside the current MVP:

* AI-generated PR review findings
* Full source-code repository indexing
* Slack notifications
* Email notifications
* Discord integration
* Multi-repository comparison
* Organization/team workspaces
* Cross-repository intelligence

The MVP deliberately avoids becoming a full IDE, generic project-management suite, generic chatbot, or oversized analytics dashboard.

---

## Roadmap

```text
Phase 1
Foundation
├── GitHub OAuth
├── Repository selection
├── Initial synchronization
├── Repository dashboard
└── Core GitHub activity

Phase 2
Daily Usefulness
├── Activity intelligence
├── Daily developer brief
├── Stale work detection
├── Notifications
├── Redis caching
└── Background synchronization

Phase 3
AI
├── Repository indexing
├── Embeddings
├── RAG
├── Repository summaries
├── PR summaries
└── Issue summaries

Phase 4
Intelligence
├── AI PR review
├── Risk signals
├── Codebase navigation
├── Historical analysis
└── Personalized recommendations

Phase 5
Scale & Polish
├── Webhooks
├── Incremental synchronization
├── Observability
├── Expanded testing
├── Deployment optimization
└── Additional integrations
```

The phased roadmap follows the product blueprint's progression from GitHub synchronization and daily usefulness into RAG, repository intelligence, risk analysis, and scaling.

---

## Design Philosophy

Codive intentionally avoids turning developer tooling into a wall of dashboards and charts.

The interface prioritizes:

* Fast scanning
* Clear information hierarchy
* Whitespace
* Timelines
* Compact tables
* Subtle status indicators
* Evidence-backed AI
* Minimal clicks
* Actionable output

Every screen should answer a concrete developer question or lead to a useful action.

---

## Product Positioning

**Codive - AI-Powered Developer Repository Intelligence**

A repository intelligence platform that synchronizes GitHub activity, analyzes repository health and developer workflow, and provides evidence-backed AI summaries, codebase search, PR/issue intelligence, and personalized daily developer briefs.

---

## License

This project is currently intended as a portfolio and development project.

License information can be added here when the repository license is finalized.
