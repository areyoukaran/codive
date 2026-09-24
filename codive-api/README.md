# Codive API

The real backend behind the Codive front end: GitHub OAuth, repository
sync, health signals computed from actual data, and an `/ask` endpoint
that answers from what's actually been synced — with a free LLM if you
want AI-written prose, or a plain templated answer if you don't.

Every piece of this runs on a free tier. None of the steps below ask for a
credit card. Where that changes (it might, providers do this), the README
line for that provider will say so — check before you type in a card
number anywhere.

## What's real here vs what I could verify myself

I don't have a way to click through your GitHub account, create OAuth
apps, or provision databases for you — those need your own accounts. So
what you're getting is the complete, working backend code, verified in two
different ways:

- **Syntax-checked and unit-tested for real, right now.** Every one of the
  45 Python files compiles. The pieces with no third-party dependency —
  token encryption, GitHub pagination parsing, the rate limiter, webhook
  HMAC signature verification, health-signal math, embedding generation,
  LLM provider selection — have actual `pytest` tests that ran and passed
  against the real code (41/41). One of those runs caught a genuine bug
  (settings were frozen at import time instead of re-read — fixed, see the
  comment in `app/core/config.py`).
- **Wired to run automatically in CI the moment you push.** The parts that
  need FastAPI, SQLAlchemy, and a live Postgres — the full request/response
  cycle, GitHub OAuth, the database — can't run in a sandboxed environment
  with no network. `.github/workflows/ci.yml` spins up a real Postgres
  container and runs the complete test suite (`tests/test_api_smoke.py`
  included) on every push, for free, using GitHub's own runners. Watch the
  Actions tab after your first push — that's your real test run.

## 1. Get the four free accounts

Five minutes each, no card for any of them.

| Service | What it's for | Where |
|---|---|---|
| **Neon** | Postgres with pgvector, 0.5GB, never expires | https://neon.tech → New Project → copy the connection string |
| **Upstash** | Redis, 256MB — optional but recommended | https://console.upstash.com → Create Database → Redis → copy the `redis://` URL (not the REST URL) |
| **Groq** | Free LLM (Llama 3.3 70B) for AI summaries/chat | https://console.groq.com/keys → Create API Key |
| **GitHub OAuth App** | Lets people connect their GitHub account | https://github.com/settings/developers → New OAuth App |

For the GitHub OAuth App, use:
- **Homepage URL**: your deployed frontend URL (or `http://localhost:5173` while testing)
- **Authorization callback URL**: `{your backend URL}/auth/github/callback` — e.g. `https://codive-api.onrender.com/auth/github/callback`

You'll get a Client ID and a Client Secret. Keep the secret secret.

## 2. Generate your own keys

```bash
python3 scripts/gen-keys.py
```

Prints a `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, and `GITHUB_WEBHOOK_SECRET`.
Paste them into `.env` (copy `.env.example` first) or your host's
environment variables. Don't reuse these across environments, don't commit
them.

## 3. Run it locally

```bash
cp .env.example .env
# fill in DATABASE_URL, SECRET_KEY, TOKEN_ENCRYPTION_KEY, GITHUB_CLIENT_ID,
# GITHUB_CLIENT_SECRET at minimum — see .env.example for what each does

docker compose up --build
```

This starts Postgres (with pgvector), Redis, and the API together — the
API container runs migrations automatically on start. Once it's up:

```bash
curl http://localhost:8000/health
```

should return `{"status": "ok", ...}` with a `warnings` list telling you
anything you haven't configured yet.

No Docker? Run Postgres/Redis however you like and:

```bash
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## 4. Deploy for free

**Backend — Render:**

1. Push this repo to GitHub.
2. On [render.com](https://render.com): New → Blueprint → point at your
   repo. It reads `render.yaml` and creates a free web service.
3. Fill in the environment variables Render prompts for (your Neon URL,
   Upstash URL, the keys from step 2, your GitHub OAuth credentials).
4. After the first deploy, copy the service's `.onrender.com` URL, set it
   as `BACKEND_URL`, and update your GitHub OAuth App's callback URL to
   match. Redeploy.

Free-tier honesty: Render's free web service spins down after 15 minutes
with no traffic and takes ~30-50 seconds to wake back up on the next
request. Fine for a portfolio project and personal use; if that cold start
bothers you, a free external uptime pinger (e.g. UptimeRobot's free tier,
5-minute interval) hitting `/health` keeps it warm — or upgrade the Render
instance later, nothing else about this setup needs to change.

**Frontend:** see `codive-site/README.md` — GitHub Pages or Render
Static Site, both free, both simple for a static site with no build step.
Point `codive-site/assets/config.js` at your Render backend URL.

## 5. Turn on AI (optional, still free)

Without `GROQ_API_KEY` or `GEMINI_API_KEY` set, `/ask` and the daily brief
still work — they answer from real synced data using a plain templated
sentence instead of a model-written one. Add either key and it upgrades
automatically, no code change, no redeploy of anything but the env var.

## 6. Turn on webhooks (optional)

Polling covers you by default (`SYNC_INTERVAL_MINUTES`, default 20). For
near-real-time updates: on each repository → Settings → Webhooks → Add
webhook → Payload URL `{BACKEND_URL}/webhooks/github`, content type
`application/json`, secret = your `GITHUB_WEBHOOK_SECRET`, events: pushes,
pull requests, issues, issue comments, check runs, releases.

## API surface

| Route | What it does |
|---|---|
| `GET /auth/github/login` | Redirects to GitHub's OAuth consent screen |
| `GET /auth/github/callback` | Exchanges the code, creates the session, redirects to the frontend |
| `GET /auth/me` | Current signed-in user |
| `POST /auth/logout` | Clears the session cookie |
| `GET /repos/available` | Live list of the signed-in user's GitHub repos to pick from |
| `POST /repos/select` | `{"full_names": ["owner/repo", ...]}` — starts watching them |
| `GET /repos` | Watched repositories, with synced metadata |
| `POST /sync/start` | Queues a sync for every watched repository |
| `GET /sync/status` | Per-repository sync progress |
| `GET /prs`, `/issues`, `/commits`, `/ci` | Synced activity, optional `?repo=owner/name` |
| `GET /health-signals` | The signal → evidence → action list, computed from real rows |
| `GET /brief` | Today's lede + counters, computed on demand — AI-written if a key is set, templated if not |
| `POST /ask` | `{"question": "...", "scope": "..."}` → `{"answer": "... [pr:412] ..."}` |
| `POST /webhooks/github` | Signature-verified webhook receiver |
| `GET /health`, `GET /ready` | Liveness / readiness |

Interactive docs at `/docs` outside production.

## What Phase 4-5 of the original blueprint still needs

This covers Phases 1-3 (foundation, daily usefulness, AI) plus the
security/reliability basics from §19 (encrypted tokens, webhook
verification, rate limiting, structured logging, tenant isolation via
`owner_user_id` scoping on every query). Not built yet, on purpose, to keep
this a real MVP rather than a half-built everything:

- AI PR review findings are stored (`PullRequest.ai_findings`) but nothing
  populates them yet — `sync_service.py` is the place to call the LLM
  provider per new/updated PR and write the result.
- Full-repository code indexing (currently README + docs only, by design —
  see the comment in `sync_service.py` about not vacuuming proprietary
  source by default).
- Slack/Discord notifications, multi-repo comparison, org/team accounts.

The data model (`app/db/models.py`) has room for all of it without a
redesign — that was intentional.
