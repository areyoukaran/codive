/* Codive - front-end configuration.
 *
 * Leave apiBase as null and the whole site runs on sample data: nothing
 * to set up, no account needed, every screen works. This is the demo.
 *
 * Set apiBase to your deployed Codive API (see ../../codive-api/README.md
 * for how to stand one up for free) and the site switches to live mode:
 *   - index.html's "Connect GitHub" buttons go straight to the real
 *     GitHub OAuth flow instead of the demo onboarding walkthrough
 *   - onboarding.html fetches your real repositories and polls a real sync
 *   - app.html loads your real synced commits, PRs, issues, CI runs and
 *     health signals, and "Ask Codive" answers from that real data
 *
 * If someone opens the site without being signed in, live mode falls back
 * to the demo data automatically - nothing breaks, they just see the demo
 * until they connect their own account from the landing page.
 *
 * Local dev:   apiBase: "http://localhost:8000"
 * Deployed:    apiBase: "https://your-service.onrender.com"  (no trailing slash)
 */
window.CODIVE = { apiBase: "http://localhost:8001" };