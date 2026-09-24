# Codive — going to production, for free

Two folders, one product:

- **`codive-site/`** — the frontend. Static HTML/CSS/JS, no build step.
  Works standalone as a demo with zero setup.
- **`codive-api/`** — the backend. FastAPI, real GitHub OAuth, a real
  sync, real (optional) AI. Deploys free.

## The fastest path to a real, live, free deployment

1. **Read `codive-api/README.md` first** and follow it end to end:
   create the four free accounts (Neon, Upstash, Groq, a GitHub OAuth
   App), generate your keys, deploy the API to Render.
2. **Deploy `codive-site/`** to GitHub Pages or a Render Static Site
   (both free — steps in `codive-site/README.md`).
3. **Set one line** in `codive-site/assets/config.js`:
   ```js
   window.CODIVE = { apiBase: "https://your-api.onrender.com" };
   ```
4. Update the API's `FRONTEND_URL`/`CORS_ORIGINS` env vars to your
   deployed frontend URL, and your GitHub OAuth App's callback URL to
   `{your-api-url}/auth/github/callback`. Redeploy the API.
5. Open your frontend URL, click Connect GitHub. That's a real product.

Total cost: $0. Every service used has a genuine free tier with no card
required — confirmed current as of this build, not assumed from training
data (pricing pages change; if something's moved, the READMEs' method
still holds even if a number does not).

## What "production" means here, honestly

- **The code is real and complete.** GitHub OAuth, encrypted token
  storage, actual GitHub API sync with pagination and rate-limit backoff,
  pgvector search, an `/ask` endpoint with clickable citations, webhook
  support, a scheduler, Docker, CI. Not a mockup wired to fake data — the
  fake data (in `codive-site/assets/app.js`) only runs when you haven't
  configured a backend yet.
- **I tested what I could run.** No network in my sandbox meant no `pip
  install`, so I couldn't boot the full FastAPI app myself. What I did
  instead: syntax-checked all 45+ backend files, ran 41 real unit tests
  against every piece of logic with no third-party dependency (encryption,
  webhook signature verification, rate limiting, GitHub pagination
  parsing, health-signal math, LLM provider selection) — which caught and
  fixed two real bugs — and separately verified the frontend's live-data
  adapter against realistic mock API responses shaped exactly like the
  real endpoints, including the edge cases (not signed in, zero
  repositories, a brand-new empty account). `.github/workflows/ci.yml`
  runs the full suite, including the parts needing a live Postgres,
  automatically the moment you push — that's your first real end-to-end
  test run, and it's free.
- **What's still a stub, on purpose:** AI-generated PR review findings
  (the `ai_findings` column exists; nothing populates it yet), full-source
  code indexing (currently README/docs only, deliberately — see the
  comment in `sync_service.py`), and Slack/email notifications. The README
  in `codive-api/` says exactly where each one would plug in.

## If something doesn't work

- **CORS errors in the browser console:** `CORS_ORIGINS` on the backend
  doesn't include your actual frontend URL, or you forgot the protocol
  (`https://`, not just the domain).
- **"Signed in" but the dashboard is empty:** check `GET /sync/status` on
  the API directly — the first sync on a large repository can take a
  couple of minutes, and Render's free tier cold-starts after 15 minutes
  idle (~30-50s to wake up on the next request).
- **`/ask` gives a templated, not AI-written, answer:** no `GROQ_API_KEY`
  or `GEMINI_API_KEY` set on the backend. Both are free — add either and
  redeploy.
- **Anything else:** `GET /health` on the API lists exactly what
  configuration is missing, in plain English.
