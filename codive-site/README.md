# Codive - front end

A complete static site: landing page, onboarding flow, and the dashboard.
No build step, no dependencies, no npm install. Works two ways from the
same files:

- **Demo mode** (default, zero config): every screen runs on realistic
  sample data. Nothing to set up, nothing to sign into.
- **Live mode** (one line in `assets/config.js`): real GitHub OAuth, a
  real sync, and a real dashboard backed by
  [`codive-api`](../codive-api/README.md), the FastAPI backend that
  ships alongside this. Demo mode keeps working even after you configure
  this - anyone not signed in just sees the demo.

## Run it

```bash
cd codive-site
python3 -m http.server 5173
```

Then open <http://localhost:5173>. Any static server works the same -
`npx serve`, `php -S localhost:5173`, GitHub Pages, a Render Static Site.

## Turn on live mode

1. Deploy `codive-api` - see its README for the exact free-tier steps
   (Neon, Upstash, Groq, Render, all no-card free tiers).
2. Edit `assets/config.js`:
   ```js
   window.CODIVE = { apiBase: "https://your-api.onrender.com" };
   ```
3. Reload. "Connect GitHub" on the landing page now goes to the real OAuth
   flow, onboarding fetches your real repositories and polls a real sync,
   and the dashboard loads real commits/PRs/issues/CI/health signals.

That's the entire integration surface - one variable. Everything else
(the adapter that maps API JSON into the shapes the UI already renders,
the auth redirect handling, the live sync-progress polling) is already
wired into `assets/app.js` and `onboarding.html`.

## Deploying the front end itself, for free

**GitHub Pages:** push this folder to a repo, Settings → Pages → Deploy
from branch → `/` (root). Free, no card, `https://<user>.github.io/<repo>/`.

**Render Static Site:** New → Static Site → point at this folder, publish
directory `.`. Free, no card.

Either way, once deployed, update `FRONTEND_URL` and `CORS_ORIGINS` in the
backend's environment to match your actual frontend URL - the backend
only accepts cross-origin requests from origins it's told about.

## What's in it

| File | What it is |
| --- | --- |
| `index.html` | Landing page - value proposition, what it answers, evidence, how it works, data handling |
| `onboarding.html` | Setup flow: authorize → select repositories → first sync. Demo (simulated) or live (real API calls), same file |
| `app.html` | The dashboard: nine views, ⌘K search, the Ask panel |
| `assets/app.css` | Design tokens and every component. Light and dark |
| `assets/app.js` | Sample data, the live-data loader and adapters, views, router, search, Ask panel |
| `assets/site.css` | Landing page and onboarding only |
| `assets/config.js` | The one setting - `apiBase` |

## How the live-data loader works

On `app.html`, `boot()` calls `tryLoadLiveData()` before the first render:

1. If `apiBase` isn't set → demo data, unchanged, instantly.
2. If it's set, `GET /auth/me` checks for a session. Not signed in → falls
   back to demo data (no error shown; the landing page's Connect GitHub
   button is the way in).
3. Signed in, zero repositories selected yet → redirects to
   `onboarding.html?connected=1`.
4. Signed in with repositories → fetches `/repos`, `/prs`, `/issues`,
   `/commits`, `/ci`, `/health-signals`, `/brief` in parallel, adapts each
   response into the exact shape the existing render functions expect
   (`adaptPR`, `adaptIssue`, `adaptCommit`, `adaptCI`, `adaptRepo`,
   `adaptSignal` in `app.js`), and mutates the sample arrays in place -
   every view function downstream is unaware anything changed.

The Overview page's "Needs you" and "What changed" sections are computed
generically from that same data (worst PRs first: failing CI, then
flagged findings, then awaiting review, then stale) rather than hand-
written - this matters because it's what makes the page correct in live
mode instead of showing demo content next to your real data.

## Keyboard

- `⌘K` / `Ctrl+K` - unified search, with an exact/semantic toggle
- `/` - open Ask Codive
- `↑` `↓` `↵` - move and open in search
- `Esc` - close whatever is open

## Notes

- Fonts load from Google Fonts. Offline, the fallback stack takes over and
  nothing breaks.
- Theme follows your OS by default; the moon button in the sidebar overrides it.
- The gutter marks are the load-bearing idea: `+` landed, `→` waiting on you,
  `×` failing, `·` stale, `?` unresolved, `○` draft, `~` touched. Keep them
  consistent if you add screens - that consistency is what makes a dense
  list scannable.
- The session cookie is cross-site by design (the frontend and API live on
  different domains once deployed), so every live-mode `fetch()` call uses
  `credentials: "include"`. If you fork this to put frontend and backend on
  the same domain, that still works unchanged.
