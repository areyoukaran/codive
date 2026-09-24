(function(){
"use strict";

/* ============================ DATA ============================ */
let ME = "rkulkarni";
const REPOS = [
  {id:"atlas/api", lang:"Python", color:"#3572A5", vis:"private", branch:"main", desc:"FastAPI service behind the Atlas dashboard - auth, sync and the public API.", stars:184, forks:21, prs:5, issues:23, ci:"failing", synced:"2 min ago", release:"v2.14.0 · 6 days ago", contributors:9},
  {id:"atlas/web", lang:"TypeScript", color:"#3178C6", vis:"private", branch:"main", desc:"React front end. Talks to atlas/api over the v2 API.", stars:96, forks:8, prs:3, issues:11, ci:"passing", synced:"2 min ago", release:"v2.14.0 · 6 days ago", contributors:6},
  {id:"atlas/workers", lang:"Python", color:"#3572A5", vis:"private", branch:"main", desc:"Background sync, indexing and embedding jobs. Celery + Redis.", stars:41, forks:3, prs:2, issues:8, ci:"passing", synced:"4 min ago", release:"v0.9.3 · 3 weeks ago", contributors:4},
  {id:"atlas/infra", lang:"HCL", color:"#7B42BC", vis:"private", branch:"main", desc:"Terraform for staging and production. RDS, ElastiCache, ECS.", stars:12, forks:1, prs:1, issues:4, ci:"passing", synced:"11 min ago", release:"-", contributors:3}
];

const PRS = [
  {n:412, repo:"atlas/api", title:"Replace session cookies with rotating refresh tokens", author:"dpark", state:"open", age:"3 days", opened:"16 Sep", files:24, add:1204, del:689, ci:"passing", reviews:"1 approved · 1 changes requested", branch:"auth/rotating-tokens", waiting:true, draft:false,
   linked:[287], labels:["auth","breaking"],
   summary:"Swaps server-side session cookies for short-lived access tokens plus a rotating refresh token stored in an httpOnly cookie. Adds a token family table so a reused refresh token invalidates the whole family, and moves logout to a revocation list in Redis. Front-end changes are in atlas/web#188, which is not merged yet.",
   changed:["app/auth/tokens.py - new, rotation and family tracking","app/auth/service.py - login, logout, refresh","app/models/token_family.py - new table","app/api/deps.py - bearer parsing replaces cookie session","alembic/versions/9f21_token_families.py","tests/auth/ - 11 new tests"],
   findings:[
     {sev:"high", t:"Concurrent refresh can revoke a valid session", loc:"app/auth/tokens.py:88", conf:.82,
      body:"Two requests refreshing the same token at once both read the family as active, then both write a new head. The second write marks the first successor as reused, which trips the reuse detector and revokes the family - a user with two tabs open gets logged out.",
      code:"  84  family = await repo.get_family(token.family_id)\n  85  if family.revoked:\n  86      raise TokenReuse()\n  87\n  88  new = await repo.rotate(family, token)   ← no lock between read and write\n  89  await repo.mark_used(token)",
      fix:"Take a row lock on the family (SELECT … FOR UPDATE) or key a short Redis lease on family_id for the read-rotate-write window."},
     {sev:"high", t:"Password change does not revoke existing token families", loc:"app/auth/service.py:203", conf:.74,
      body:"change_password updates the hash and returns. The old flow destroyed every session server-side; the new flow has no equivalent, so tokens issued before a password change keep working until they expire (30 days).",
      code:" 201  await repo.set_password(user.id, hash_pw(new))\n 202  await audit.log(\"password.changed\", user.id)\n 203  return Ok()                              ← families never revoked",
      fix:"Call revoke_all_families(user.id) before returning, and add a test that a pre-change refresh token is rejected."},
     {sev:"med", t:"SameSite=None set without Secure in the dev config", loc:"app/config/dev.py:31", conf:.66,
      body:"Browsers drop a SameSite=None cookie that is not marked Secure. This only affects local development, but the same block is copied into staging.py, where it does matter.",
      code:"  31  REFRESH_COOKIE = {\"samesite\": \"none\", \"secure\": False}",
      fix:"Derive the flag from the environment rather than repeating the dict per config file."},
     {sev:"low", t:"Migration is not reversible", loc:"alembic/versions/9f21_token_families.py:44", conf:.58,
      body:"downgrade() is left as pass. Every other migration in the repository implements it, and the deploy runbook assumes a rollback path exists.",
      code:"  44  def downgrade():\n  45      pass",
      fix:"Drop the token_families table and restore the sessions index."}],
   checklist:["Rotation is covered by a concurrency test, not just a happy-path test","Revocation runs on password change, email change and admin disable","atlas/web#188 ships in the same release or the API accepts both schemes","Rollback path verified against a staging snapshot","30-day refresh lifetime signed off - it was 7 days with sessions"],
   timeline:[["16 Sep 09:14","dpark opened the pull request"],["16 Sep 11:02","CI passed on 3 checks"],["17 Sep 14:40","mchen requested changes - “token lifetime needs a second pair of eyes”"],["18 Sep 08:21","dpark pushed 4 commits"],["18 Sep 16:55","jlee approved"],["19 Sep 07:30","rkulkarni requested as reviewer"]]},

  {n:418, repo:"atlas/api", title:"Bump httpx 0.25 → 0.27 and pin anyio", author:"dependabot", state:"open", age:"19 hours", opened:"18 Sep", files:2, add:8, del:8, ci:"failing", reviews:"no reviews", branch:"deps/httpx-027", waiting:true, draft:false,
   linked:[], labels:["dependencies"],
   summary:"Routine dependency bump. CI has failed three times on the same test - tests/clients/test_timeouts.py::test_no_timeout - since the bump landed on the branch.",
   changed:["pyproject.toml","poetry.lock"],
   findings:[
     {sev:"high", t:"timeout=None no longer means “no timeout”", loc:"app/clients/github.py:52", conf:.79,
      body:"httpx 0.26 changed the default timeout handling so an explicit None on the client falls back to the transport default rather than disabling timeouts. The GitHub client passes timeout=None on the initial-sync path, which is exactly where requests legitimately run long. That is the failing test.",
      code:"  52  self._c = httpx.AsyncClient(timeout=None)   ← now inherits a 5s default\n  53  # initial sync of a 10k-commit repo takes minutes",
      fix:"Pass an explicit httpx.Timeout(connect=5, read=300, write=30, pool=5) for sync clients and keep the short default everywhere else."}],
   checklist:["Timeouts set explicitly per client, not globally disabled","Initial sync re-run against a large repository","Changelog for 0.26 and 0.27 read for other behaviour changes"],
   timeline:[["18 Sep 12:04","dependabot opened the pull request"],["18 Sep 12:22","CI failed - test_timeouts"],["18 Sep 22:10","CI failed - test_timeouts"],["19 Sep 06:48","CI failed - test_timeouts"]]},

  {n:401, repo:"atlas/api", title:"Add pgvector HNSW index for code_chunks", author:"mchen", state:"open", age:"16 days", opened:"3 Sep", files:6, add:212, del:34, ci:"passing", reviews:"awaiting review from rkulkarni", branch:"search/hnsw-index", waiting:true, draft:false, stale:true,
   linked:[], labels:["search","performance"],
   summary:"Replaces the IVFFlat index on code_chunks.embedding with HNSW and adds a migration plus a benchmark script. Opened 16 days ago and has had no review activity for 13 of them.",
   changed:["alembic/versions/7c04_hnsw.py","app/search/index.py","scripts/bench_search.py","docs/search.md"],
   findings:[
     {sev:"med", t:"Index build will lock the table on a production-sized dataset", loc:"alembic/versions/7c04_hnsw.py:18", conf:.71,
      body:"CREATE INDEX without CONCURRENTLY blocks writes on code_chunks for the duration of the build. On the staging dataset that was 40 seconds; production has roughly 14× the rows.",
      code:"  18  op.execute(\"CREATE INDEX idx_chunks_hnsw ON code_chunks …\")",
      fix:"Use CONCURRENTLY outside a transaction, and gate the migration behind a maintenance window flag."}],
   checklist:["Benchmark numbers included in the description","Index build strategy agreed for production","Old IVFFlat index dropped in a follow-up, not this one"],
   timeline:[["3 Sep 16:30","mchen opened the pull request"],["4 Sep 10:12","CI passed"],["6 Sep 09:40","mchen commented - “benchmarks in the description now”"],["19 Sep","no activity for 13 days"]]},

  {n:419, repo:"atlas/workers", title:"Stop the retry storm when GitHub returns 403", author:"jlee", state:"merged", age:"merged yesterday", opened:"17 Sep", files:5, add:97, del:41, ci:"passing", reviews:"2 approved", branch:"fix/retry-storm", waiting:false, draft:false,
   linked:[244], labels:["reliability"],
   summary:"Secondary rate-limit 403s were being retried immediately by the generic error handler, which burned the remaining quota in seconds. Adds respect for Retry-After, exponential backoff with jitter, and a circuit breaker per installation.",
   changed:["workers/github/retry.py","workers/github/client.py","workers/sync/jobs.py","tests/github/test_retry.py","docs/runbook.md"],
   findings:[],
   checklist:[],
   timeline:[["17 Sep 10:05","jlee opened the pull request"],["17 Sep 15:44","mchen approved"],["18 Sep 09:02","rkulkarni approved"],["18 Sep 09:15","merged into main"]]},

  {n:188, repo:"atlas/web", title:"Refresh-token client and silent re-auth", author:"dpark", state:"open", age:"3 days", opened:"16 Sep", files:14, add:486, del:302, ci:"passing", reviews:"1 approved", branch:"auth/refresh-client", waiting:false, draft:false,
   linked:[], labels:["auth"],
   summary:"Front-end half of the auth change. Adds a refresh interceptor, a single-flight queue so parallel 401s trigger one refresh, and a sign-out broadcast across tabs.",
   changed:["src/auth/refresh.ts","src/auth/queue.ts","src/api/client.ts","src/hooks/useSession.ts"],
   findings:[
     {sev:"med", t:"Single-flight queue has no timeout", loc:"src/auth/queue.ts:34", conf:.69,
      body:"If the refresh request never settles, queued requests wait forever and the app shows a blank authenticated shell rather than sending the user to sign-in.",
      code:"  34  if (inFlight) return inFlight;   ← no timeout, no rejection path",
      fix:"Race the in-flight promise against a 10s timeout and fall through to sign-out."}],
   checklist:["Merged together with atlas/api#412 or behind a flag","Cross-tab sign-out verified in Safari"],
   timeline:[["16 Sep 09:40","dpark opened the pull request"],["17 Sep 12:00","jlee approved"]]},

  {n:421, repo:"atlas/api", title:"Incremental sync cursors", author:"rkulkarni", state:"draft", age:"5 hours", opened:"19 Sep", files:9, add:341, del:12, ci:"pending", reviews:"draft", branch:"sync/cursors", waiting:false, draft:true,
   linked:[287], labels:["sync"],
   summary:"Your draft. Stores a per-repository cursor (last event id plus ETag) so a scheduled sync fetches only what changed instead of walking the full history.",
   changed:["app/sync/cursor.py","app/sync/scheduler.py","app/models/sync_job.py"],
   findings:[], checklist:[],
   timeline:[["19 Sep 04:12","rkulkarni opened a draft"]]}
];

const ISSUES = [
  {n:287, repo:"atlas/api", title:"Initial sync stalls on repositories with more than 10k commits", state:"open", author:"mchen", age:"12 days", comments:41, labels:["bug","sync","P1"], assignee:"rkulkarni", hot:true, blocked:true,
   summary:"Initial sync reliably stalls somewhere past 10,000 commits. The thread has narrowed it to a single worker holding one connection for the whole walk, so the job neither finishes nor fails - it just stops making progress while the connection sits idle.",
   decisions:["Paginate by commit date, not by page number - page numbers drift as new commits land mid-sync","Checkpoint every 500 commits so a restart resumes instead of starting over","Full history is not required for the first brief; the last 90 days is enough to be useful"],
   open:["Do we backfill older history lazily, or leave it out until someone asks for it?","Who owns the cursor format - this issue or #412's follow-up?"],
   activity:[["7 Sep","mchen opened the issue with a stack trace from staging"],["9 Sep","jlee reproduced it on a 34k-commit repository"],["12 Sep","thread agrees on date-based pagination"],["15 Sep","dpark posts a checkpointing sketch"],["17 Sep","blocked - waiting on a decision about backfill"]]},
  {n:244, repo:"atlas/api", title:"Rate-limit handling drops webhook events silently", state:"open", author:"jlee", age:"22 days", comments:6, labels:["bug","reliability"], assignee:"-", stale:true,
   summary:"When the client hits a secondary rate limit, the event handler catches the exception, logs at debug level and returns 200. GitHub sees a success and never redelivers, so the event is gone.",
   decisions:["Return 503 so GitHub retries the delivery","Log rate-limit hits at warning, not debug"],
   open:["Is there a backlog of already-lost events worth replaying?"],
   activity:[["28 Aug","jlee opened the issue"],["29 Aug","mchen linked it to the retry work in atlas/workers"],["18 Sep","partly addressed by atlas/workers#419 - the webhook path is still open"]]},
  {n:301, repo:"atlas/api", title:"Webhook signature verification fails on redelivery", state:"open", author:"dpark", age:"4 days", comments:9, labels:["security","webhooks"], assignee:"dpark",
   summary:"Redelivered webhooks arrive with the original timestamp. The verifier rejects anything older than five minutes, so a redelivery after a brief outage is dropped as a replay attempt - which defeats the point of redelivery.",
   decisions:["Keep the replay window, but key deduplication on the delivery id instead of the timestamp"],
   open:["What window do we accept for redeliveries - 24 hours?"],
   activity:[["15 Sep","dpark opened the issue after a staging outage"],["16 Sep","mchen confirms the same behaviour in production logs"],["18 Sep","dpark proposes delivery-id deduplication"]]},
  {n:265, repo:"atlas/web", title:"Dashboard flashes empty state while the first sync runs", state:"open", author:"rkulkarni", age:"9 days", comments:3, labels:["ux"], assignee:"-",
   summary:"During the first sync the dashboard renders the empty state for about a second before data arrives, which reads as “nothing here” at exactly the moment a new user is deciding whether the product works.",
   decisions:["Show sync progress instead of the empty state until the first sync completes"],
   open:["Do we hold the whole dashboard, or fill sections as each finishes?"],
   activity:[["10 Sep","rkulkarni opened the issue"],["11 Sep","dpark suggests per-section progress"]]},
  {n:198, repo:"atlas/workers", title:"Embedding job retries the whole batch when one chunk fails", state:"open", author:"mchen", age:"34 days", comments:2, labels:["performance"], assignee:"-", stale:true,
   summary:"One oversized chunk fails the embedding call and the entire batch of 256 is retried, including the 255 chunks that embedded fine. On a large repository this triples the indexing cost.",
   decisions:[],
   open:["Split on failure, or validate chunk size before the call?"],
   activity:[["16 Aug","mchen opened the issue"],["17 Aug","jlee notes the same pattern in the summarization job"]]}
];

const COMMITS = [
  {sha:"a91f3c2", repo:"atlas/api", author:"dpark", msg:"Track refresh-token families and detect reuse", when:"2 hours ago", add:318, del:96, pr:412},
  {sha:"4d02b71", repo:"atlas/api", author:"dpark", msg:"Move bearer parsing out of the cookie session dependency", when:"3 hours ago", add:74, del:141, pr:412},
  {sha:"c7e5a90", repo:"atlas/workers", author:"jlee", msg:"Respect Retry-After on secondary rate limits", when:"yesterday", add:61, del:23, pr:419},
  {sha:"2b88fd4", repo:"atlas/workers", author:"jlee", msg:"Add a per-installation circuit breaker", when:"yesterday", add:36, del:18, pr:419},
  {sha:"81ac6de", repo:"atlas/api", author:"dependabot", msg:"Bump httpx from 0.25.2 to 0.27.0", when:"yesterday", add:8, del:8, pr:418},
  {sha:"fe30b12", repo:"atlas/web", author:"dpark", msg:"Single-flight refresh queue", when:"2 days ago", add:128, del:44, pr:188},
  {sha:"6cc1904", repo:"atlas/api", author:"rkulkarni", msg:"Sketch per-repository sync cursors", when:"5 hours ago", add:341, del:12, pr:421},
  {sha:"9ab7255", repo:"atlas/infra", author:"mchen", msg:"Raise RDS max_connections to 400", when:"3 days ago", add:4, del:4, pr:null},
  {sha:"d14e8f0", repo:"atlas/api", author:"mchen", msg:"Benchmark script for HNSW vs IVFFlat", when:"13 days ago", add:96, del:0, pr:401}
];

const CI = [
  {repo:"atlas/api", wf:"api-ci", branch:"main", state:"failing", when:"41 minutes ago", job:"pytest · tests/clients/test_timeouts.py::test_no_timeout", run:"#2841", streak:3},
  {repo:"atlas/web", wf:"web-ci", branch:"main", state:"passing", when:"2 hours ago", job:"-", run:"#1907", streak:0},
  {repo:"atlas/workers", wf:"workers-ci", branch:"main", state:"passing", when:"yesterday", job:"-", run:"#612", streak:0}
];

const SIGNALS = [
  {mark:"·", cls:"g-mute", t:"3 pull requests older than 14 days", trend:"up", trendTxt:"+1 this week",
   evidence:[["atlas/api#401","16 days · awaiting your review"],["atlas/web#173","21 days · no reviewer assigned"],["atlas/infra#44","29 days · author left the team"]],
   action:"Review or close", actionNote:"Three PRs, about 40 minutes", go:{v:"prs"}},
  {mark:"×", cls:"g-del", t:"CI on atlas/api fails 18% of runs, up from 6% a month ago", trend:"up", trendTxt:"3× on the same test",
   evidence:[["run #2841","test_no_timeout · 41 minutes ago"],["run #2836","test_no_timeout · yesterday"],["run #2829","test_no_timeout · yesterday"]],
   action:"Open PR #418", actionNote:"One test, one cause", go:{v:"pr", n:418}},
  {mark:"!", cls:"g-warn", t:"Two dependencies are more than a year behind", trend:"flat", trendTxt:"unchanged",
   evidence:[["celery 5.2.7","released Dec 2022 · 5.4.0 available"],["redis-py 4.5.1","released Feb 2023 · 5.0.8 available"]],
   action:"Schedule an upgrade", actionNote:"Both used by atlas/workers", go:{v:"repo", id:"atlas/workers"}},
  {mark:"·", cls:"g-mute", t:"Median review turnaround slipped from 9 hours to 31 hours", trend:"up", trendTxt:"over 4 weeks",
   evidence:[["atlas/api","9h → 34h"],["atlas/web","8h → 19h"],["reviewers","3 of 9 did 78% of reviews"]],
   action:"Spread review load", actionNote:"Suggested in the weekly digest", go:{v:"activity"}},
  {mark:"?", cls:"g-iris", t:"One issue has run 41 comments without a decision", trend:"flat", trendTxt:"12 days open",
   evidence:[["atlas/api#287","blocked on the backfill question"]],
   action:"Read the summary", actionNote:"Decisions and open questions extracted", go:{v:"issue", n:287}},
  {mark:"!", cls:"g-warn", t:"atlas/workers has no documented runbook for a failed sync", trend:"flat", trendTxt:"gap",
   evidence:[["docs/runbook.md","covers retries, not stuck jobs"],["issue #287","asks for one"]],
   action:"Draft a runbook section", actionNote:"Codive can start from the thread", go:{v:"issue", n:287}}
];

const FILES = [
  {path:"app/auth/tokens.py", repo:"atlas/api", kw:"token rotation refresh family reuse detection"},
  {path:"app/auth/service.py", repo:"atlas/api", kw:"login logout password change session"},
  {path:"app/clients/github.py", repo:"atlas/api", kw:"github api client timeout pagination rate limit"},
  {path:"app/sync/cursor.py", repo:"atlas/api", kw:"incremental sync cursor etag checkpoint"},
  {path:"app/search/index.py", repo:"atlas/api", kw:"pgvector embedding index similarity hnsw"},
  {path:"workers/github/retry.py", repo:"atlas/workers", kw:"backoff jitter retry-after circuit breaker"},
  {path:"src/auth/refresh.ts", repo:"atlas/web", kw:"interceptor silent reauth 401 queue"},
  {path:"docs/runbook.md", repo:"atlas/workers", kw:"operations oncall stuck job recovery"}
];

const BRIEF = {
  date:"Saturday, 19 September",
  since:"since you last looked, Thursday 17:40",
  lede:[
    "The auth rewrite is nearly through - ",
    {hl:"two pull requests are waiting on you"},
    ", and atlas/api has failed CI three times on the same test since yesterday's httpx bump. Nothing else moved much."
  ]
};

/* --- repositories chosen during onboarding, passed as ?repos=a,b --- */
(function applySelection(){
  var q;
  try { q = new URLSearchParams(location.search).get("repos"); } catch(e){ return; }
  if(!q) return;
  var keep = q.split(",").map(function(s){return s.trim();}).filter(Boolean);
  if(!keep.length) return;
  function prune(list, key){
    for(var i=list.length-1;i>=0;i--){ if(keep.indexOf(list[i][key])<0) list.splice(i,1); }
  }
  if(!REPOS.some(function(r){ return keep.indexOf(r.id) >= 0; })) return;  // nothing known selected
  prune(REPOS,"id"); prune(PRS,"repo"); prune(ISSUES,"repo");
  prune(COMMITS,"repo"); prune(CI,"repo"); prune(FILES,"repo");
})();

/* ============================ LIVE DATA ============================
   Demo mode (default, zero config) never reaches any of this - every
   function below is only called from boot() at the bottom of the file,
   and only once backendConfigured() is true. The sample arrays above
   stay exactly as they are; this section mutates them IN PLACE (via
   .length=0 + .push, never reassignment) once real data arrives, which
   is what lets every render() function below keep reading the same
   REPOS/PRS/ISSUES/COMMITS/CI/SIGNALS bindings whether they hold sample
   data or a real sync. */
let IS_LIVE = false;

function apiBase(){
  return (window.CODIVE && window.CODIVE.apiBase || "").replace(/\/$/, "");
}
async function apiGet(path){
  const resp = await fetch(apiBase() + path, {credentials: "include"});
  if(resp.status === 401) { const e = new Error("unauthenticated"); e.code = 401; throw e; }
  if(!resp.ok){ const e = new Error("http_"+resp.status); e.code = resp.status; throw e; }
  return resp.json();
}

function relativeDay(iso){
  if(!iso) return "";
  const d = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 86400000));
  if(d === 0) return "today";
  if(d === 1) return "yesterday";
  if(d < 14) return d + " days";
  if(d < 60) return Math.round(d/7) + " weeks";
  return Math.round(d/30) + " months";
}
function relativeShort(iso){
  if(!iso) return "";
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if(mins < 1) return "just now";
  if(mins < 60) return mins + "m ago";
  const hrs = Math.round(mins/60);
  if(hrs < 24) return hrs + "h ago";
  return relativeDay(iso) + " ago";
}

/* Maps one backend PR record (see app/api/routers/activity.py:_pr_out) to
   the shape prRow()/vPR() already know how to render. Fields the backend
   hasn't populated yet (AI findings/checklist/timeline - see the API
   README's "what Phase 4-5 still needs") come through as empty arrays,
   which the existing empty-state UI already handles correctly. */
function adaptPR(p){
  return {
    n: p.n, repo: p.repo, title: p.title, author: p.author || "unknown",
    state: p.state, age: relativeDay(p.opened_at), opened: relativeDay(p.opened_at),
    files: p.files, add: p.add, del: p.del, ci: p.ci || "unknown",
    reviews: p.review_decision ? p.review_decision.replace(/_/g," ") : "no reviews yet",
    branch: p.branch || "", waiting: p.state === "open" && !p.draft &&
      (p.review_decision === null || p.review_decision === "none" || p.review_decision === "changes_requested"),
    draft: !!p.draft, linked: [], labels: p.labels || [],
    summary: p.summary || "Codive hasn't written a summary for this pull request yet.",
    changed: p.changed || [], findings: p.findings || [], checklist: [], timeline: [],
    stale: p.state === "open" && relativeDay(p.opened_at).indexOf("week") >= 0,
  };
}
function adaptIssue(i){
  const ageDays = i.opened_at ? Math.round((Date.now() - new Date(i.opened_at).getTime()) / 86400000) : 0;
  return {
    n: i.n, repo: i.repo, title: i.title, state: i.state, author: i.author || "unknown",
    age: relativeDay(i.opened_at), comments: i.comments, labels: i.labels || [],
    assignee: i.assignee || "-", hot: i.comments >= 25, blocked: (i.open || []).length > 0,
    stale: i.state === "open" && ageDays >= 21,  // mirrors STALE_ISSUE_DAYS in the backend's health_signals.py
    summary: i.summary || "Codive hasn't summarized this thread yet.",
    decisions: i.decisions || [], open: i.open || [], activity: [],
  };
}
function adaptCommit(c){
  return {sha: c.sha, repo: c.repo, author: c.author || "unknown", msg: c.msg,
          when: relativeShort(c.committed_at), add: c.add, del: c.del, pr: c.pr};
}
function adaptCI(c){
  return {repo: c.repo, wf: c.wf, branch: c.branch, state: c.state, when: relativeShort(c.started_at),
          job: c.job, run: c.run, streak: 0};
}
function adaptRepo(r){
  const known = REPOS.find(x => x.id === r.full_name) || {};
  return {
    id: r.full_name, lang: r.language || "-", color: known.color || "#8B938B",
    vis: r.visibility, branch: r.default_branch, desc: r.description || "No description yet.",
    stars: r.stars, forks: r.forks, ci: "passing", synced: r.last_synced_at ? relativeShort(r.last_synced_at) : "never",
    release: r.latest_release || "-", contributors: known.contributors || 0,
  };
}
function adaptSignal(s){
  return {mark: s.mark, cls: s.cls, t: s.t, trend: s.trend || "flat",
          trendTxt: s.trend === "up" ? "rising" : s.trend === "down" ? "improving" : "unchanged",
          evidence: s.evidence || [], action: s.action, actionNote: s.actionNote,
          go: {v: "prs"}};
}

async function tryLoadLiveData(){
  if(!backendConfigured()) return false;
  let me;
  try{ me = await apiGet("/auth/me"); }
  catch(e){ return false; }  // not signed in - demo data stands, index.html's Connect GitHub button is the way in

  let repos;
  try{ repos = await apiGet("/repos"); }
  catch(e){ return false; }

  if(!repos.length){
    location.href = "onboarding.html?connected=1";
    return "redirecting";
  }

  const [prs, issues, commits, ci, signals] = await Promise.all([
    apiGet("/prs").catch(()=>[]), apiGet("/issues").catch(()=>[]),
    apiGet("/commits").catch(()=>[]), apiGet("/ci").catch(()=>[]),
    apiGet("/health-signals").catch(()=>[]),
  ]);

  REPOS.length = 0; REPOS.push(...repos.map(adaptRepo));
  PRS.length = 0; PRS.push(...prs.map(adaptPR));
  ISSUES.length = 0; ISSUES.push(...issues.map(adaptIssue));
  COMMITS.length = 0; COMMITS.push(...commits.map(adaptCommit));
  CI.length = 0; CI.push(...ci.map(adaptCI));
  SIGNALS.length = 0; SIGNALS.push(...signals.map(adaptSignal));
  FILES.length = 0;  // README/docs indexing has no stable "file browser" shape yet - search still works over synced PRs/issues/commits

  IS_LIVE = true;
  ME = me.login;

  try{
    const brief = await apiGet("/brief");
    BRIEF.date = new Date().toLocaleDateString(undefined, {weekday:"long", day:"numeric", month:"long"});
    BRIEF.since = brief.generated_by === "template" ? "computed from synced data" : "written by " + brief.generated_by;
    BRIEF.lede = [brief.lede];
    BRIEF.counters = brief.counters;
  }catch(e){ /* brief is best-effort - the rest of the dashboard still renders */ }

  return true;
}

/* ============================ HELPERS ============================ */
const $ = (s,r)=> (r||document).querySelector(s);
const el = (t,c,x)=>{const n=document.createElement(t); if(c)n.className=c; if(x!=null)n.textContent=x; return n;};
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const initials = n => n.slice(0,2).toUpperCase();
let scope = "all";
const inScope = r => scope === "all" || r === scope;

function toast(msg){
  const t = $("#toast"); t.textContent = msg; t.classList.add("on");
  clearTimeout(toast._t); toast._t = setTimeout(()=>t.classList.remove("on"), 2100);
}
function avatar(name){
  const a = el("span","avatar",initials(name)); return a;
}
function whoChip(name){
  const w = el("span","who-chip"); w.appendChild(avatar(name)); w.appendChild(el("span",null,name)); return w;
}
function sec(title, meta){
  const s = el("section","sec");
  const h = el("div","sec-head");
  h.appendChild(el("h2","sec-title",title));
  h.appendChild(el("div","sec-line"));
  if(meta) h.appendChild(el("div","sec-meta",meta));
  s.appendChild(h);
  return s;
}
function row(mark, markCls, build, side, onClick){
  const r = el(onClick ? "button" : "div","row");
  if(onClick){ r.type="button"; r.addEventListener("click", onClick); }
  const g = el("div","gut "+markCls, mark);
  const b = el("div","row-body");
  build(b);
  r.appendChild(g); r.appendChild(b);
  const s = el("div","row-side");
  if(side) s.appendChild(typeof side === "string" ? el("span","stamp",side) : side);
  r.appendChild(s);
  return r;
}
function metaLine(parts){
  const m = el("div","row-m");
  parts.forEach(p=>{ if(p) m.appendChild(typeof p === "string" ? el("span",null,p) : p); });
  return m;
}
function diffNum(a,d){
  const s = el("span","diffnum");
  s.innerHTML = '<span class="p">+'+a.toLocaleString()+'</span> <span class="m">−'+d.toLocaleString()+'</span>';
  return s;
}
function tag(text, kind){ return el("span","tag"+(kind?" "+kind:""), text); }
function ledger(rows){
  const l = el("div","ledger");
  rows.forEach(r=>l.appendChild(r));
  return l;
}
function emptyState(title, body){
  const e = el("div","empty");
  e.appendChild(el("b",null,title));
  e.appendChild(el("span",null,body));
  const w = el("div","ledger"); w.appendChild(e); return w;
}
const prBy = n => PRS.find(p=>p.n===n);
const issueBy = n => ISSUES.find(i=>i.n===n);
const repoBy = id => REPOS.find(r=>r.id===id);

/* ============================ ROUTER ============================ */
const NAV = [
  {v:"overview", label:"Overview", icon:'<path d="M4 13h6V4H4v9zm0 7h6v-5H4v5zm10 0h6V11h-6v9zm0-16v5h6V4h-6z" fill="currentColor"/>'},
  {v:"repos", label:"Repositories", icon:'<path d="M5 3h11a2 2 0 012 2v16l-6-3-6 3V5a2 2 0 012-2z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>'},
  {v:"activity", label:"Activity", icon:'<path d="M3 12h4l3-8 4 16 3-8h4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>'},
  {v:"prs", label:"Pull requests", icon:'<circle cx="6" cy="6" r="2.4" stroke="currentColor" stroke-width="1.8"/><circle cx="6" cy="18" r="2.4" stroke="currentColor" stroke-width="1.8"/><circle cx="18" cy="18" r="2.4" stroke="currentColor" stroke-width="1.8"/><path d="M6 8.4v7.2M18 15.6V10a3 3 0 00-3-3h-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'},
  {v:"issues", label:"Issues", icon:'<circle cx="12" cy="12" r="8.4" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="2.4" fill="currentColor"/>'},
  {v:"health", label:"Code health", icon:'<path d="M4 18V9m5 9V5m5 13v-6m5 6V8" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>'}
];

let view = {v:"overview"};

function counts(){
  const prs = PRS.filter(p=>inScope(p.repo) && p.state==="open" && !p.draft);
  return {
    prs: prs.length,
    issues: ISSUES.filter(i=>inScope(i.repo) && i.state==="open").length,
    ci: CI.filter(c=>inScope(c.repo) && c.state==="failing").length
  };
}

function renderNav(){
  const nav = $("#nav"); nav.innerHTML = "";
  const c = counts();
  NAV.forEach(item=>{
    const b = el("button","nav-item");
    b.type = "button";
    b.setAttribute("aria-current", view.v === item.v || (item.v==="prs" && view.v==="pr") || (item.v==="issues" && view.v==="issue") || (item.v==="repos" && view.v==="repo") ? "true":"false");
    b.innerHTML = '<svg class="ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">'+item.icon+'</svg><span>'+item.label+'</span>';
    if(item.v === "prs") b.insertAdjacentHTML("beforeend", '<span class="nav-count">'+c.prs+'</span>');
    if(item.v === "issues") b.insertAdjacentHTML("beforeend", '<span class="nav-count">'+c.issues+'</span>');
    if(item.v === "health" && c.ci) b.insertAdjacentHTML("beforeend", '<span class="nav-count alarm">'+c.ci+'</span>');
    b.addEventListener("click", ()=>go({v:item.v}));
    nav.appendChild(b);
  });
}

function go(v){
  view = v;
  render();
  $("#page").scrollIntoView({block:"start"});
  window.scrollTo({top:0, behavior:"instant"});
  updateAskContext();
}

function render(){
  renderNav();
  const p = $("#page"); p.innerHTML = "";
  const fn = {overview:vOverview, repos:vRepos, repo:vRepo, activity:vActivity, prs:vPRs, pr:vPR, issues:vIssues, issue:vIssue, health:vHealth}[view.v];
  (fn || vOverview)(p);
}

/* ============================ OVERVIEW ============================ */
function vOverview(p){
  const c = counts();
  const brief = el("div","brief");
  const top = el("div","brief-top");
  top.appendChild(el("span","brief-date",BRIEF.date));
  top.appendChild(el("span","brief-since",BRIEF.since));
  brief.appendChild(top);

  const lede = el("div","lede");
  const para = el("p");
  BRIEF.lede.forEach(part=>{
    if(typeof part === "string") para.appendChild(document.createTextNode(part));
    else para.appendChild(el("span","hl",part.hl));
  });
  lede.appendChild(para);
  const foot = el("div","lede-foot");
  const by = el("div","lede-by");
  const commitCount = COMMITS.filter(x=>inScope(x.repo)).length;
  const prCount = PRS.filter(x=>inScope(x.repo)).length;
  const ciCount = CI.filter(x=>inScope(x.repo)).length;
  by.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M1 12.5h4.2l2.3-6.8 3.6 13.6 3-9.4 1.9 2.6H23" stroke="var(--iris)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Written by Codive from '+commitCount+' commits, '+prCount+' pull requests and '+ciCount+' workflow runs</span>';
  foot.appendChild(by);
  const rew = el("button","btn sm","Rewrite this brief");
  rew.id = "rewriteBrief";
  foot.appendChild(rew);
  lede.appendChild(foot);
  brief.appendChild(lede);

  // Every number below is computed straight from PRS/ISSUES/CI at render
  // time - in both demo and live mode. This used to be a hand-authored
  // set of numbers that matched only the demo dataset, which meant live
  // mode would render the demo's fake counts on top of a user's real
  // repositories. Computing it generically fixes that, and demo mode
  // still comes out the same because the demo arrays are shaped to match.
  const openPRsScoped = PRS.filter(x=>inScope(x.repo) && x.state==="open" && !x.draft);
  const waitingCount = openPRsScoped.filter(x=>x.waiting).length;
  const staleIssueCount = ISSUES.filter(x=>inScope(x.repo) && x.state==="open" && x.stale).length;
  const mergedRecent = PRS.filter(x=>inScope(x.repo) && x.state==="merged").slice(0,2);
  const recentCommits = COMMITS.filter(x=>inScope(x.repo)).slice(0,2);
  const changedCount = Math.min(4, mergedRecent.length + recentCommits.length) || Math.min(4, commitCount);

  const counters = el("div","counters");
  [[String(changedCount || commitCount),"changes worth reading","is-iris",{v:"activity"}],
   [String(c.prs),"pull requests open","",{v:"prs"}],
   [String(waitingCount),"waiting on your review","is-warn",{v:"prs"}],
   [String(c.ci),"CI failure"+(c.ci===1?"":"s")+" on main","is-del",{v:"health"}],
   [String(staleIssueCount),"stale issues","",{v:"issues"}]].forEach(([n,l,cls,dest])=>{
    const b = el("button","counter "+cls); b.type="button";
    b.appendChild(el("div","n",n)); b.appendChild(el("div","l",l));
    b.addEventListener("click",()=>go(dest));
    counters.appendChild(b);
  });
  brief.appendChild(counters);
  p.appendChild(brief);

  rew.addEventListener("click", ()=>rewriteBrief(para, rew));

  /* --- needs you: worst-first from real PR/issue state, same logic for
     demo and live data. No hardcoded PR numbers or names here anymore -
     see the note above the counters. */
  const needsPRs = [];
  const seenPR = new Set();
  const addPR = list => list.forEach(x=>{ const k=x.repo+"#"+x.n; if(!seenPR.has(k)){ seenPR.add(k); needsPRs.push(x); } });
  addPR(openPRsScoped.filter(x=>x.ci==="failing"));
  addPR(openPRsScoped.filter(x=>(x.findings||[]).some(f=>f.sev==="high")));
  addPR(openPRsScoped.filter(x=>x.waiting));
  addPR(openPRsScoped.filter(x=>x.stale));
  const needsIssues = ISSUES.filter(x=>inScope(x.repo) && x.state==="open" && x.blocked);

  const needRows = [...needsPRs.slice(0,3).map(prRow), ...needsIssues.slice(0,2).map(issueRow)].slice(0,4);
  const s1 = sec("Needs you", needRows.length+" item"+(needRows.length===1?"":"s"));
  s1.appendChild(needRows.length ? ledger(needRows) : emptyState("Nothing needs you right now","No open reviews, failing checks or blocked threads in scope."));
  p.appendChild(s1);

  /* --- what changed: most recently merged PRs + most recent commits --- */
  const changeRows = [...mergedRecent.map(prRow), ...recentCommits.map(commitRow)];
  const s2 = sec("What changed", changeRows.length+" item"+(changeRows.length===1?"":"s"));
  s2.appendChild(changeRows.length ? ledger(changeRows) : emptyState("Nothing merged yet","Once a pull request merges or a commit lands, it shows up here."));
  p.appendChild(s2);

  /* --- health digest --- */
  const s3 = sec("Health signals", "6 tracked");
  const hl = el("div","ledger");
  SIGNALS.slice(0,3).forEach(sig=>hl.appendChild(signalRow(sig)));
  s3.appendChild(hl);
  const more = el("button","btn sm","See all health signals");
  more.style.marginTop = "10px";
  more.addEventListener("click",()=>go({v:"health"}));
  s3.appendChild(more);
  p.appendChild(s3);
}

function rowTitle(numTxt, title){
  const t = el("div","row-t");
  t.appendChild(el("span","num mono",numTxt));
  t.appendChild(document.createTextNode(title));
  return t;
}

function rewriteBrief(para, btn){
  withSample(async (sample)=>{
    btn.disabled = true; const prev = btn.textContent; btn.textContent = "Writing…";
    para.style.opacity = ".45";
    const prompt = "You are Codive, a repository intelligence tool. Using ONLY the state below, write the opening line of a developer's morning brief.\n\n"
      + "Rules: two sentences maximum, under 45 words, plain declarative prose, no greeting, no bullet points, no markdown, no emoji. Name the specific repository, PR number or test where it matters. Lead with whatever the developer must act on today. Do not invent anything not in the state.\n\nSTATE:\n"
      + contextBlob();
    try{
      let out = "";
      await sample(prompt, {modelTier:"quick", onText:({text})=>{ out = text; para.textContent = text; para.style.opacity="1"; }});
      para.textContent = out.trim();
      para.style.opacity = "1";
    }catch(e){
      para.style.opacity = "1";
      if(e && e.text){ para.textContent = e.text; }
      else { restoreLede(para); toast(sampleMsg(e && e.code)); }
    }finally{ btn.disabled = false; btn.textContent = prev; }
  }, ()=>{ restoreLede(para); toast("Live rewriting needs Claude access in this view."); });
}
function restoreLede(para){
  para.innerHTML = "";
  BRIEF.lede.forEach(part=>{
    if(typeof part === "string") para.appendChild(document.createTextNode(part));
    else para.appendChild(el("span","hl",part.hl));
  });
}

/* ============================ REPOSITORIES ============================ */
function vRepos(p){
  p.appendChild(pageHead("Repositories","4 connected · GitHub App installed on the atlas organization"));
  const wrap = el("div","ledger");
  const t = el("table","rtable");
  t.innerHTML = "<thead><tr><th>Repository</th><th>Language</th><th>Open PRs</th><th>Open issues</th><th>CI</th><th>Last sync</th></tr></thead>";
  const tb = el("tbody");
  REPOS.filter(r=>inScope(r.id)).forEach(r=>{
    const tr = el("tr");
    tr.tabIndex = 0;
    const c1 = el("td");
    const nm = el("div","mono"); nm.style.fontSize="13px"; nm.style.fontWeight="500"; nm.textContent = r.id;
    const d = el("div"); d.style.cssText="font-size:12.2px;color:var(--ink2);margin-top:2px;max-width:46ch"; d.textContent = r.desc;
    c1.appendChild(nm); c1.appendChild(d);
    const c2 = el("td");
    const lg = el("span","lang"); const dot = el("i"); dot.style.background = r.color;
    lg.appendChild(dot); lg.appendChild(el("span",null,r.lang)); c2.appendChild(lg);
    const c3 = el("td"); c3.className="mono"; c3.style.fontSize="12.5px"; c3.textContent = r.prs;
    const c4 = el("td"); c4.className="mono"; c4.style.fontSize="12.5px"; c4.textContent = r.issues;
    const c5 = el("td"); c5.appendChild(tag(r.ci, r.ci==="failing"?"del":"add"));
    const c6 = el("td"); c6.className="stamp"; c6.textContent = r.synced;
    [c1,c2,c3,c4,c5,c6].forEach(c=>tr.appendChild(c));
    tr.addEventListener("click",()=>go({v:"repo",id:r.id}));
    tr.addEventListener("keydown",e=>{ if(e.key==="Enter") go({v:"repo",id:r.id}); });
    tb.appendChild(tr);
  });
  t.appendChild(tb); wrap.appendChild(t); p.appendChild(wrap);
}

function vRepo(p){
  const r = repoBy(view.id); if(!r) return vRepos(p);
  p.appendChild(backLink("All repositories",{v:"repos"}));
  const h = el("div","detail-head");
  const t = el("h1","detail-title"); t.className="detail-title mono"; t.textContent = r.id;
  h.appendChild(t);
  const d = el("p"); d.style.cssText="margin:0 0 9px;color:var(--ink2);font-size:13.5px;max-width:70ch"; d.textContent = r.desc;
  h.appendChild(d);
  const m = el("div","detail-meta");
  [tag(r.vis), el("span","mono","default: "+r.branch), r.lang, r.stars+" stars", r.contributors+" contributors", "synced "+r.synced].forEach(x=>{
    m.appendChild(typeof x === "string" ? el("span",null,x) : x);
  });
  h.appendChild(m);
  p.appendChild(h);

  const acts = el("div","filters"); acts.style.marginTop="14px";
  [["Summarize changes","Summarize what changed in "+r.id+" over the last week"],
   ["Explain this repository","Explain what "+r.id+" does and how it is structured"],
   ["Find risky areas","Which areas of "+r.id+" look riskiest right now, and why?"],
   ["Ask about the code","What changed in "+r.id+" recently?"]].forEach(([label,q])=>{
    const b = el("button","chip",label);
    b.addEventListener("click",()=>{ openAsk(); askAsk(q); });
    acts.appendChild(b);
  });
  p.appendChild(acts);

  const cols = el("div","cols"); cols.style.marginTop="18px";
  const left = el("div");

  const prs = PRS.filter(x=>x.repo===r.id);
  const s1 = sec("Open pull requests", prs.filter(x=>x.state==="open").length+" open");
  s1.style.marginTop = "0";
  s1.appendChild(ledger(prs.filter(x=>x.state==="open").map(prRow)));
  left.appendChild(s1);

  const s2 = sec("Recent commits");
  const cs = COMMITS.filter(c=>c.repo===r.id);
  s2.appendChild(ledger(cs.map(commitRow)));
  left.appendChild(s2);

  const s3 = sec("Open issues");
  const is = ISSUES.filter(i=>i.repo===r.id);
  s3.appendChild(is.length ? ledger(is.map(issueRow)) : emptyState("No open issues","Nothing filed against this repository.") );
  left.appendChild(s3);

  const right = el("div");
  const pan = el("div","panel");
  pan.appendChild(el("h3","panel-t","At a glance"));
  const dl = el("dl"); dl.style.margin="0";
  [["Visibility",r.vis],["Default branch",r.branch],["Latest release",r.release],["CI",r.ci],["Stars",String(r.stars)],["Forks",String(r.forks)],["Contributors",String(r.contributors)]].forEach(([k,v])=>{
    const kv = el("div","kv"); kv.appendChild(el("dt",null,k)); kv.appendChild(el("dd",null,v)); dl.appendChild(kv);
  });
  pan.appendChild(dl); right.appendChild(pan);

  const ciRun = CI.find(c=>c.repo===r.id);
  if(ciRun){
    const p2 = el("div","panel");
    p2.appendChild(el("h3","panel-t","Latest workflow run"));
    const st = el("div"); st.style.cssText="display:flex;align-items:center;gap:8px;margin-bottom:7px";
    const dot = el("span","dot"+(ciRun.state==="failing"?" bad":"")); st.appendChild(dot);
    st.appendChild(el("span",null,ciRun.wf+" "+ciRun.run));
    p2.appendChild(st);
    const sub = el("div"); sub.style.cssText="font-size:12.3px;color:var(--ink2)";
    sub.textContent = ciRun.state==="failing" ? ciRun.job : "All checks passed · "+ciRun.when;
    p2.appendChild(sub);
    if(ciRun.streak>1){
      const w = el("div"); w.style.cssText="font-size:12.2px;color:var(--del);margin-top:6px";
      w.textContent = "Failed "+ciRun.streak+" runs in a row on the same test.";
      p2.appendChild(w);
    }
    right.appendChild(p2);
  }
  cols.appendChild(left); cols.appendChild(right);
  p.appendChild(cols);
}

/* ============================ ACTIVITY ============================ */
let actFilter = {type:"all", author:"all"};
function vActivity(p){
  p.appendChild(pageHead("Activity","Commits, pull requests, issues and workflow runs, normalized across repositories"));
  const f = el("div","filters");
  [["all","Everything"],["commit","Commits"],["pr","Pull requests"],["issue","Issues"],["ci","Workflow runs"]].forEach(([v,l])=>{
    const c = el("button","chip",l);
    c.setAttribute("aria-pressed", actFilter.type===v ? "true":"false");
    c.addEventListener("click",()=>{ actFilter.type=v; render(); });
    f.appendChild(c);
  });
  f.appendChild(el("div","filter-sep"));
  ["all","dpark","jlee","mchen","rkulkarni"].forEach(a=>{
    const c = el("button","chip", a==="all"?"Anyone":a);
    c.setAttribute("aria-pressed", actFilter.author===a ? "true":"false");
    c.addEventListener("click",()=>{ actFilter.author=a; render(); });
    f.appendChild(c);
  });
  p.appendChild(f);

  const items = [];
  if(actFilter.type==="all"||actFilter.type==="commit")
    COMMITS.filter(c=>inScope(c.repo)).forEach(c=>items.push({kind:"commit", author:c.author, node:commitRow(c)}));
  if(actFilter.type==="all"||actFilter.type==="pr")
    PRS.filter(x=>inScope(x.repo)).forEach(x=>items.push({kind:"pr", author:x.author, node:prRow(x)}));
  if(actFilter.type==="all"||actFilter.type==="issue")
    ISSUES.filter(i=>inScope(i.repo)).forEach(i=>items.push({kind:"issue", author:i.author, node:issueRow(i)}));
  if(actFilter.type==="all"||actFilter.type==="ci")
    CI.filter(c=>inScope(c.repo)).forEach(c=>items.push({kind:"ci", author:"-", node:ciRow(c)}));

  const shown = items.filter(i=>actFilter.author==="all" || i.author===actFilter.author);
  const s = sec("Timeline", shown.length+" events");
  s.style.marginTop="4px";
  s.appendChild(shown.length ? ledger(shown.map(i=>i.node)) : emptyState("Nothing matches those filters","Try a different author or event type."));
  p.appendChild(s);

  const s2 = sec("Trends", "last 6 weeks");
  const g = el("div"); g.style.cssText="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px";
  [["Merged pull requests",[4,6,5,9,7,8],"8 this week","down"],
   ["Median review turnaround",[9,11,14,22,27,31],"31 hours","up"],
   ["Failed workflow runs",[1,2,1,3,4,6],"6 this week","up"]].forEach(([label,data,val,dir])=>{
    const pan = el("div","panel");
    pan.appendChild(el("h3","panel-t",label));
    const sp = el("div","spark");
    const max = Math.max.apply(null,data);
    data.forEach((d,i)=>{ const b = el("i"); b.style.height = Math.max(3, Math.round(d/max*22))+"px"; if(i===data.length-1) b.className="on"; sp.appendChild(b); });
    const rowx = el("div"); rowx.style.cssText="display:flex;align-items:flex-end;justify-content:space-between;gap:10px";
    rowx.appendChild(sp);
    const tr = el("span","trend "+dir, (dir==="up"?"▲ ":"▼ ")+val);
    rowx.appendChild(tr);
    pan.appendChild(rowx);
    g.appendChild(pan);
  });
  s2.appendChild(g);
  p.appendChild(s2);
}

/* ============================ PULL REQUESTS ============================ */
let prFilter = "needs";
function vPRs(p){
  p.appendChild(pageHead("Pull requests","Aged, ranked and reviewed - not just mirrored"));
  const f = el("div","filters");
  [["needs","Needs attention"],["open","Open"],["mine","Opened by me"],["all","Everything"]].forEach(([v,l])=>{
    const c = el("button","chip",l);
    c.setAttribute("aria-pressed", prFilter===v?"true":"false");
    c.addEventListener("click",()=>{ prFilter=v; render(); });
    f.appendChild(c);
  });
  p.appendChild(f);

  let list = PRS.filter(x=>inScope(x.repo));
  if(prFilter==="needs") list = list.filter(x=>x.waiting);
  if(prFilter==="open") list = list.filter(x=>x.state==="open");
  if(prFilter==="mine") list = list.filter(x=>x.author===ME);

  const s = sec(prFilter==="needs" ? "Waiting on someone" : "Pull requests", list.length+" shown");
  s.style.marginTop="4px";
  s.appendChild(list.length ? ledger(list.map(prRow)) : emptyState("Nothing here","No pull requests match this filter in the current scope."));
  p.appendChild(s);
}

function prMark(x){
  if(x.state==="merged") return ["+","g-add"];
  if(x.ci==="failing") return ["×","g-del"];
  if(x.stale) return ["·","g-mute"];
  if(x.draft) return ["○","g-mute"];
  if(x.waiting) return ["→","g-warn"];
  return ["·","g-mute"];
}
function prRow(x){
  const [m,c] = prMark(x);
  const high = (x.findings||[]).filter(f=>f.sev==="high").length;
  return row(m,c, b=>{
    b.appendChild(rowTitle(x.repo+" #"+x.n, x.title));
    const parts = [whoChip(x.author), x.state==="merged" ? x.age : "opened "+x.age+" ago", diffNum(x.add,x.del), el("span","mono",x.files+" files")];
    if(x.ci==="failing") parts.push(tag("CI failing","del"));
    if(x.draft) parts.push(tag("draft"));
    if(x.stale) parts.push(tag("stale"));
    if(high) parts.push(tag(high+" high-severity finding"+(high>1?"s":""),"warn"));
    b.appendChild(metaLine(parts));
  }, x.state==="merged"?"merged":x.reviews.split("·")[0].trim(), ()=>go({v:"pr",n:x.n}));
}

function vPR(p){
  const x = prBy(view.n); if(!x) return vPRs(p);
  p.appendChild(backLink("Pull requests",{v:"prs"}));
  const h = el("div","detail-head");
  const t = el("h1","detail-title");
  t.appendChild(el("span","num",x.repo+" #"+x.n+"  "));
  t.appendChild(document.createTextNode(x.title));
  h.appendChild(t);
  const m = el("div","detail-meta");
  m.appendChild(tag(x.state==="merged"?"merged":x.draft?"draft":"open", x.state==="merged"?"iris":x.draft?"":"add"));
  m.appendChild(whoChip(x.author));
  m.appendChild(el("span",null,"opened "+x.opened));
  m.appendChild(el("span","mono",x.branch));
  m.appendChild(diffNum(x.add,x.del));
  m.appendChild(el("span",null,x.files+" files"));
  if(x.ci==="failing") m.appendChild(tag("CI failing","del")); else if(x.ci==="passing") m.appendChild(tag("CI passing","add"));
  x.labels.forEach(l=>m.appendChild(tag(l)));
  h.appendChild(m);
  p.appendChild(h);

  const cols = el("div","cols"); cols.style.marginTop="18px";
  const left = el("div");

  const s0 = sec("What this changes");
  s0.style.marginTop="0";
  const sum = el("div","panel");
  const sp = el("p"); sp.style.cssText="margin:0;font-size:13.6px;line-height:1.62;color:var(--ink);max-width:72ch";
  sp.textContent = x.summary;
  sum.appendChild(sp);
  const byline = el("div","lede-by"); byline.style.marginTop="11px";
  byline.innerHTML = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none"><path d="M1 12.5h4.2l2.3-6.8 3.6 13.6 3-9.4 1.9 2.6H23" stroke="var(--iris)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Summarized from the diff and '+x.timeline.length+' timeline events · a suggestion, not a verdict</span>';
  sum.appendChild(byline);
  s0.appendChild(sum);
  left.appendChild(s0);

  const s1 = sec("Possible problems", x.findings.length ? x.findings.length+" findings" : "none found");
  if(x.findings.length){
    x.findings.forEach((f,i)=>left_append(s1,f,i));
  } else {
    s1.appendChild(emptyState("Nothing flagged","Codive read the diff and the linked issue and found nothing worth raising. That is not the same as “no bugs”."));
  }
  const rerun = el("button","btn sm","Re-run review with the latest commits");
  rerun.style.marginTop="10px";
  rerun.addEventListener("click", ()=>rerunReview(x, rerun));
  s1.appendChild(rerun);
  left.appendChild(s1);

  const s2 = sec("Files affected", x.files+" files");
  const fl = el("div","ledger");
  x.changed.forEach(c=>{
    const [path, note] = c.split(" - ");
    fl.appendChild(row("~","g-mute", b=>{
      const t2 = el("div","row-t mono"); t2.style.fontSize="12.8px"; t2.textContent = path;
      b.appendChild(t2);
      if(note) b.appendChild(metaLine([note]));
    }, null, null));
  });
  s2.appendChild(fl);
  left.appendChild(s2);

  if(x.checklist.length){
    const s3 = sec("Review checklist","generated from the diff");
    const pan = el("div","panel");
    x.checklist.forEach((c,i)=>{
      const lab = el("label","check");
      const inp = document.createElement("input"); inp.type="checkbox"; inp.id="chk"+x.n+"-"+i;
      lab.appendChild(inp); lab.appendChild(el("span",null,c));
      pan.appendChild(lab);
    });
    s3.appendChild(pan);
    left.appendChild(s3);
  }

  const s4 = sec("Timeline");
  const tl = el("div","ledger");
  x.timeline.forEach(([when,what])=>{
    tl.appendChild(row("·","g-mute", b=>{
      b.appendChild(el("div","row-t",what));
    }, when, null));
  });
  s4.appendChild(tl);
  left.appendChild(s4);

  const right = el("div");
  const pan = el("div","panel");
  pan.appendChild(el("h3","panel-t","Ask about this pull request"));
  const qs = ["What could break if this ships today?","Why was the refresh lifetime set to 30 days?","Which other files touch token rotation?","Summarize the review discussion"];
  const sg = el("div","sugg");
  qs.forEach(q=>{
    const b = el("button",null,q);
    b.addEventListener("click",()=>{ openAsk(); askAsk(q+" (atlas PR #"+x.n+")"); });
    sg.appendChild(b);
  });
  pan.appendChild(sg);
  right.appendChild(pan);

  const p2 = el("div","panel");
  p2.appendChild(el("h3","panel-t","Review state"));
  const dl = el("dl"); dl.style.margin="0";
  const rows2 = [["Reviews",x.reviews],["CI",x.ci],["Age",x.age],["Files",String(x.files)],["Branch",x.branch]];
  if(x.linked.length) rows2.push(["Linked issue","#"+x.linked.join(", #")]);
  rows2.forEach(([k,v])=>{ const kv = el("div","kv"); kv.appendChild(el("dt",null,k)); kv.appendChild(el("dd",null,v)); dl.appendChild(kv); });
  p2.appendChild(dl);
  if(x.linked.length){
    const lb = el("button","btn sm","Open issue #"+x.linked[0]);
    lb.style.marginTop="10px";
    lb.addEventListener("click",()=>go({v:"issue",n:x.linked[0]}));
    p2.appendChild(lb);
  }
  right.appendChild(p2);

  cols.appendChild(left); cols.appendChild(right);
  p.appendChild(cols);
}

function left_append(s1, f, i){
  const card = el("div","finding");
  const head = el("button","finding-h"); head.type="button";
  head.setAttribute("aria-expanded", i===0 ? "true":"false");
  const sev = el("span","sev "+f.sev, f.sev);
  const mid = el("div"); mid.style.minWidth="0"; mid.style.flex="1";
  mid.appendChild(el("div","finding-t",f.t));
  const sub = el("div","finding-sub");
  const ev = el("button","evidence", f.loc);
  ev.addEventListener("click",e=>{ e.stopPropagation(); toast("Would open "+f.loc+" at the referenced line"); });
  sub.appendChild(ev);
  mid.appendChild(sub);
  const conf = el("div","conf");
  conf.innerHTML = '<span>'+Math.round(f.conf*100)+'%</span><span class="conf-bar"><i style="width:'+Math.round(f.conf*100)+'%"></i></span>';
  head.appendChild(sev); head.appendChild(mid); head.appendChild(conf);
  card.appendChild(head);

  const body = el("div","finding-body");
  body.style.display = i===0 ? "block":"none";
  const pp = el("p"); pp.textContent = f.body; body.appendChild(pp);
  const code = el("pre","code mono"); code.textContent = f.code; body.appendChild(code);
  const fix = el("p"); fix.innerHTML = "<b style='color:var(--ink)'>Suggested fix.</b> "+esc(f.fix); body.appendChild(fix);
  card.appendChild(body);
  head.addEventListener("click",()=>{
    const open = body.style.display === "block";
    body.style.display = open ? "none":"block";
    head.setAttribute("aria-expanded", open ? "false":"true");
  });
  s1.appendChild(card);
}

function rerunReview(x, btn){
  withSample(async (sample)=>{
    btn.disabled = true; const prev = btn.textContent; btn.textContent = "Reviewing…";
    const prompt = "You are Codive reviewing a pull request. Use ONLY the facts below.\n\nPULL REQUEST:\n"
      + JSON.stringify({repo:x.repo, number:x.n, title:x.title, summary:x.summary, files:x.changed, ci:x.ci, known_findings:x.findings.map(f=>({severity:f.sev, title:f.t, at:f.loc, detail:f.body}))})
      + "\n\nWIDER REPOSITORY STATE:\n" + contextBlob()
      + "\n\nWrite a short reviewer's note, under 90 words, plain prose, no markdown, no bullets. Say what you would check first and why, referencing a specific file, line or test. Do not repeat the pull request title back.";
    try{
      const {text} = await sample(prompt, {modelTier:"default"});
      const note = el("div","panel");
      note.style.marginTop = "10px";
      note.appendChild(el("h3","panel-t","Reviewer's note · just now"));
      const pz = el("p"); pz.style.cssText="margin:0;font-size:13.3px;line-height:1.6;color:var(--ink2)";
      pz.textContent = text.trim();
      note.appendChild(pz);
      btn.after(note);
      btn.style.display = "none";
    }catch(e){ toast(sampleMsg(e && e.code)); }
    finally{ btn.disabled = false; btn.textContent = prev; }
  }, ()=>toast("Live review needs Claude access in this view."));
}

/* ============================ ISSUES ============================ */
let issueFilter = "all";
function vIssues(p){
  p.appendChild(pageHead("Issues","Ageing, stalling and unresolved discussion - surfaced, not just listed"));
  const f = el("div","filters");
  [["all","All open"],["hot","Active discussion"],["stale","Stale"],["mine","Assigned to me"]].forEach(([v,l])=>{
    const c = el("button","chip",l);
    c.setAttribute("aria-pressed", issueFilter===v?"true":"false");
    c.addEventListener("click",()=>{ issueFilter=v; render(); });
    f.appendChild(c);
  });
  p.appendChild(f);
  let list = ISSUES.filter(i=>inScope(i.repo));
  if(issueFilter==="hot") list = list.filter(i=>i.hot);
  if(issueFilter==="stale") list = list.filter(i=>i.stale);
  if(issueFilter==="mine") list = list.filter(i=>i.assignee===ME);
  const s = sec("Issues", list.length+" shown");
  s.style.marginTop="4px";
  s.appendChild(list.length ? ledger(list.map(issueRow)) : emptyState("Nothing here","No issues match this filter in the current scope."));
  p.appendChild(s);
}
function issueRow(i){
  const mark = i.blocked ? ["?","g-iris"] : i.stale ? ["·","g-mute"] : i.hot ? ["!","g-warn"] : ["·","g-mute"];
  return row(mark[0], mark[1], b=>{
    b.appendChild(rowTitle(i.repo+" #"+i.n, i.title));
    const parts = [whoChip(i.author), i.age+" old", el("span","mono",i.comments+" comments")];
    if(i.blocked) parts.push(tag("blocked","warn"));
    if(i.stale) parts.push(tag("stale"));
    i.labels.forEach(l=>parts.push(tag(l)));
    b.appendChild(metaLine(parts));
  }, i.assignee===ME ? "yours" : i.assignee==="-" ? "unassigned" : i.assignee, ()=>go({v:"issue",n:i.n}));
}

function vIssue(p){
  const i = issueBy(view.n); if(!i) return vIssues(p);
  p.appendChild(backLink("Issues",{v:"issues"}));
  const h = el("div","detail-head");
  const t = el("h1","detail-title");
  t.appendChild(el("span","num",i.repo+" #"+i.n+"  "));
  t.appendChild(document.createTextNode(i.title));
  h.appendChild(t);
  const m = el("div","detail-meta");
  m.appendChild(tag("open","add")); m.appendChild(whoChip(i.author));
  m.appendChild(el("span",null,i.age+" old"));
  m.appendChild(el("span","mono",i.comments+" comments"));
  m.appendChild(el("span",null,"assigned to "+i.assignee));
  i.labels.forEach(l=>m.appendChild(tag(l)));
  h.appendChild(m);
  p.appendChild(h);

  const cols = el("div","cols"); cols.style.marginTop="18px";
  const left = el("div");

  const s0 = sec(i.comments>15 ? "The thread in one paragraph" : "Summary");
  s0.style.marginTop="0";
  const pan = el("div","panel");
  const pp = el("p"); pp.style.cssText="margin:0;font-size:13.6px;line-height:1.62;max-width:72ch"; pp.textContent = i.summary;
  pan.appendChild(pp);
  const bl = el("div","lede-by"); bl.style.marginTop="11px";
  bl.innerHTML = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none"><path d="M1 12.5h4.2l2.3-6.8 3.6 13.6 3-9.4 1.9 2.6H23" stroke="var(--iris)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Summarized from '+i.comments+' comments</span>';
  pan.appendChild(bl);
  s0.appendChild(pan);
  left.appendChild(s0);

  if(i.decisions.length){
    const s1 = sec("Decisions the thread reached", i.decisions.length+"");
    const l1 = el("div","ledger");
    i.decisions.forEach(d=>l1.appendChild(row("+","g-add", b=>{ b.appendChild(el("div","row-t",d)); }, null, null)));
    s1.appendChild(l1);
    left.appendChild(s1);
  }
  if(i.open.length){
    const s2 = sec("Still unresolved", i.open.length+"");
    const l2 = el("div","ledger");
    i.open.forEach(d=>l2.appendChild(row("?","g-iris", b=>{ b.appendChild(el("div","row-t",d)); }, null, null)));
    s2.appendChild(l2);
    left.appendChild(s2);
  }
  const s3 = sec("Activity");
  const l3 = el("div","ledger");
  i.activity.forEach(([when,what])=>l3.appendChild(row("·","g-mute", b=>{ b.appendChild(el("div","row-t",what)); }, when, null)));
  s3.appendChild(l3);
  left.appendChild(s3);

  const right = el("div");
  const rp = el("div","panel");
  rp.appendChild(el("h3","panel-t","Ask about this issue"));
  const sg = el("div","sugg");
  ["What is actually blocking this?","Which pull requests touch this code?","Draft a comment proposing a decision","Has this happened before?"].forEach(q=>{
    const b = el("button",null,q);
    b.addEventListener("click",()=>{ openAsk(); askAsk(q+" (issue #"+i.n+")"); });
    sg.appendChild(b);
  });
  rp.appendChild(sg);
  right.appendChild(rp);

  const linked = PRS.filter(x=>x.linked.indexOf(i.n)>=0);
  if(linked.length){
    const lp = el("div","panel");
    lp.appendChild(el("h3","panel-t","Linked pull requests"));
    linked.forEach(x=>{
      const b = el("button","btn sm",x.repo+" #"+x.n);
      b.style.cssText = "margin:0 6px 6px 0;font-family:'IBM Plex Mono',monospace";
      b.addEventListener("click",()=>go({v:"pr",n:x.n}));
      lp.appendChild(b);
    });
    right.appendChild(lp);
  }
  cols.appendChild(left); cols.appendChild(right);
  p.appendChild(cols);
}

/* ============================ HEALTH ============================ */
function signalRow(sig){
  const r = el("div","signal");
  r.appendChild(el("div","gut "+sig.cls, sig.mark));
  const b = el("div","signal-b");
  const top = el("div"); top.style.cssText="display:flex;gap:12px;align-items:baseline;justify-content:space-between";
  top.appendChild(el("div","signal-t",sig.t));
  top.appendChild(el("span","trend "+sig.trend, (sig.trend==="up"?"▲ ":sig.trend==="down"?"▼ ":"- ")+sig.trendTxt));
  b.appendChild(top);
  const ul = el("ul","signal-e");
  sig.evidence.forEach(([k,v])=>{
    const li = el("li");
    li.appendChild(el("span","mono",k));
    li.appendChild(el("span",null,v));
    ul.appendChild(li);
  });
  b.appendChild(ul);
  const act = el("div","action");
  const btn = el("button","btn sm",sig.action);
  btn.addEventListener("click",()=>go(sig.go));
  act.appendChild(btn);
  act.appendChild(el("span","action-label",sig.actionNote));
  act.querySelector(".action-label").style.color = "var(--ink3)";
  act.querySelector(".action-label").style.fontWeight = "400";
  b.appendChild(act);
  r.appendChild(b);
  return r;
}
function vHealth(p){
  p.appendChild(pageHead("Code health","Measured signals with the evidence behind them. No score out of a hundred."));
  const s = sec("Signals", SIGNALS.length+" tracked");
  s.style.marginTop="4px";
  const l = el("div","ledger");
  SIGNALS.forEach(sig=>l.appendChild(signalRow(sig)));
  s.appendChild(l);
  p.appendChild(s);

  const s2 = sec("Workflow runs");
  const l2 = el("div","ledger");
  CI.filter(c=>inScope(c.repo)).forEach(c=>l2.appendChild(ciRow(c)));
  s2.appendChild(l2);
  p.appendChild(s2);

  const note = el("p");
  note.style.cssText = "margin-top:18px;font-size:12.6px;color:var(--ink3);max-width:66ch;line-height:1.6";
  note.textContent = "Every signal here is counted from synchronized GitHub data, not inferred by a model. Codive only writes the suggested action - and you can disagree with it.";
  p.appendChild(note);
}
function ciRow(c){
  const bad = c.state === "failing";
  return row(bad?"×":"+", bad?"g-del":"g-add", b=>{
    b.appendChild(rowTitle(c.repo+" "+c.run, c.wf+" on "+c.branch));
    const parts = [c.state, c.when];
    if(bad){ parts.push(el("span","mono",c.job)); if(c.streak>1) parts.push(tag(c.streak+" in a row","del")); }
    b.appendChild(metaLine(parts));
  }, c.when, bad ? ()=>go({v:"pr",n:418}) : null);
}
function commitRow(c){
  return row("+","g-add", b=>{
    const t = el("div","row-t");
    t.appendChild(el("span","num mono",c.sha));
    t.appendChild(document.createTextNode(c.msg));
    b.appendChild(t);
    const parts = [whoChip(c.author), el("span","mono",c.repo), c.when, diffNum(c.add,c.del)];
    if(c.pr) parts.push(tag("#"+c.pr,"iris"));
    b.appendChild(metaLine(parts));
  }, c.when, c.pr ? ()=>go({v:"pr",n:c.pr}) : null);
}

function pageHead(title, sub){
  const h = el("div","page-head");
  h.appendChild(el("h1","page-title",title));
  if(sub) h.appendChild(el("p","page-sub",sub));
  return h;
}
function backLink(label, dest){
  const b = el("button","back");
  b.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M15 5l-7 7 7 7" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg><span>'+esc(label)+'</span>';
  b.addEventListener("click",()=>go(dest));
  return b;
}

/* ============================ SEARCH ============================ */
const INDEX = [];
REPOS.forEach(r=>INDEX.push({type:"repo", t:r.id, sub:r.desc, r:r.id, kw:r.desc+" "+r.lang, go:{v:"repo",id:r.id}}));
PRS.forEach(x=>INDEX.push({type:"pull", t:"#"+x.n+" "+x.title, sub:x.repo+" · "+x.author, r:x.repo, kw:x.summary+" "+x.labels.join(" ")+" "+x.branch, go:{v:"pr",n:x.n}}));
ISSUES.forEach(i=>INDEX.push({type:"issue", t:"#"+i.n+" "+i.title, sub:i.repo+" · "+i.comments+" comments", r:i.repo, kw:i.summary+" "+i.labels.join(" "), go:{v:"issue",n:i.n}}));
COMMITS.forEach(c=>INDEX.push({type:"commit", t:c.msg, sub:c.repo+" · "+c.sha+" · "+c.when, r:c.repo, kw:c.sha+" "+c.author, go:c.pr?{v:"pr",n:c.pr}:{v:"repo",id:c.repo}}));
FILES.forEach(f=>INDEX.push({type:"file", t:f.path, sub:f.repo, r:f.repo, kw:f.kw, go:{v:"repo",id:f.repo}}));

let cmdkMode = "exact", cmdkSel = 0, cmdkHits = [];
function cmdkSearch(q){
  const s = q.trim().toLowerCase();
  if(!s) return INDEX.filter(i=>inScope(i.r)).slice(0,9);
  const words = s.split(/\s+/);
  return INDEX.filter(i=>inScope(i.r)).map(i=>{
    const hay = (i.t+" "+i.sub).toLowerCase();
    const deep = (hay+" "+i.kw).toLowerCase();
    let score = 0;
    words.forEach(w=>{
      if(hay.indexOf(w)>=0) score += 3;
      else if(cmdkMode==="semantic" && deep.indexOf(w)>=0) score += 1.4;
    });
    if(hay.indexOf(s)>=0) score += 2;
    return {i, score};
  }).filter(x=>x.score>0).sort((a,b)=>b.score-a.score).slice(0,10).map(x=>x.i);
}
function renderCmdk(){
  const list = $("#cmdkList"); list.innerHTML = "";
  cmdkHits = cmdkSearch($("#cmdkIn").value);
  if(!cmdkHits.length){
    const e = el("div","empty");
    e.appendChild(el("b",null,"No matches"));
    e.appendChild(el("span",null, cmdkMode==="exact" ? "Try semantic search - it looks at meaning, not just the literal string." : "Nothing in the indexed repositories matches that."));
    list.appendChild(e); return;
  }
  cmdkHits.forEach((h,idx)=>{
    const b = el("button","cmdk-i"+(idx===cmdkSel?" sel":"")); b.type="button";
    b.appendChild(el("span","type",h.type));
    b.appendChild(el("span","t",h.t));
    b.appendChild(el("span","r",h.r));
    b.addEventListener("click",()=>{ closeCmdk(); go(h.go); });
    list.appendChild(b);
  });
}
function openCmdk(){ $("#cmdk").classList.add("open"); $("#cmdkIn").value=""; cmdkSel=0; renderCmdk(); $("#cmdkIn").focus(); }
function closeCmdk(){ $("#cmdk").classList.remove("open"); }

/* ============================ ASK ============================ */
let sampleFn = null, sampleResolved = false, turns = [], askCtl = null;
const CTX_RULES =
"You are Codive, a repository intelligence assistant. Answer only from the repository state given below. "+
"If the state does not contain the answer, say so plainly and name what you would need - never guess. "+
"Be brief: 2-4 sentences or up to 4 short bullet lines. Plain prose, no markdown headings, no bold. "+
"Cite every factual claim with an inline marker in square brackets, placed right after the claim: "+
"[pr:412] for a pull request, [issue:287] for an issue, [commit:a91f3c2] for a commit, [file:app/auth/tokens.py:88] for a file, [repo:atlas/api] for a repository. "+
"Use only identifiers that appear in the state. Do not add a sources list at the end; the markers are the citation.";

function contextBlob(){
  const o = {
    today:"2026-09-19", viewer:ME,
    repositories: REPOS.map(r=>({id:r.id, language:r.lang, default_branch:r.branch, open_prs:r.prs, open_issues:r.issues, ci:r.ci, latest_release:r.release, description:r.desc})),
    pull_requests: PRS.map(x=>({repo:x.repo, number:x.n, title:x.title, author:x.author, state:x.state, age:x.age, ci:x.ci, reviews:x.reviews, additions:x.add, deletions:x.del, files:x.changed, summary:x.summary,
      findings:(x.findings||[]).map(f=>({severity:f.sev, title:f.t, location:f.loc, detail:f.body, suggested_fix:f.fix}))})),
    issues: ISSUES.map(i=>({repo:i.repo, number:i.n, title:i.title, author:i.author, age:i.age, comments:i.comments, assignee:i.assignee, summary:i.summary, decisions:i.decisions, open_questions:i.open})),
    commits: COMMITS.map(c=>({sha:c.sha, repo:c.repo, author:c.author, message:c.msg, when:c.when, pr:c.pr})),
    workflow_runs: CI,
    health_signals: SIGNALS.map(s=>({signal:s.t, evidence:s.evidence, suggested_action:s.action})),
    indexed_files: FILES.map(f=>({path:f.path, repo:f.repo, topics:f.kw}))
  };
  return JSON.stringify(o);
}
function useSample(){
  if(sampleResolved) return Promise.resolve(sampleFn);
  const w = window.claude;
  if(!w || typeof w.use !== "function"){ sampleResolved = true; return Promise.resolve(null); }
  return w.use("sample").then(f=>{ sampleFn = f; sampleResolved = true; return f; })
    .catch(()=>{ sampleResolved = true; return null; });
}
function withSample(run, fallback){
  useSample().then(f=>{ if(f) run(f); else fallback(); });
}
/* ---- optional: talk to your own backend instead of the in-page fallback ----
   Set window.CODIVE.apiBase in assets/config.js and this posts to
   POST {apiBase}/ask  ->  { "answer": "... [pr:412] ..." }                   */
function backendConfigured(){
  return !!(window.CODIVE && window.CODIVE.apiBase);
}
function backendAsk(q, body, log){
  var base = window.CODIVE.apiBase.replace(/\/$/,"");
  fetch(base + "/ask", {
    method:"POST",
    credentials:"include",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({question:q, scope:scope, view:view})
  })
  .then(function(r){
    if(r.status === 401){ var e = new Error("unauthenticated"); e.code = 401; throw e; }
    if(r.status === 429){ var e2 = new Error("rate_limited"); e2.code = 429; throw e2; }
    if(!r.ok){
      // Reached the server, but it returned an error - surface what it
      // actually said instead of collapsing every non-2xx into the same
      // "could not reach" message, which made a real 500/422/503 look
      // identical to a genuine network/CORS failure and impossible to
      // tell apart from a screenshot.
      return r.text().then(function(txt){
        var detail = txt;
        try{ var j = JSON.parse(txt); detail = j.detail || j.message || txt; }catch(e){}
        var e3 = new Error("http_"+r.status); e3.code = r.status; e3.detail = detail; throw e3;
      });
    }
    return r.json();
  })
  .then(function(d){ linkifyCitations(d.answer || d.text || "(empty response)", body); log.scrollTop = log.scrollHeight; })
  .catch(function(err){
    if(err && err.code === 401){ body.textContent = "Signed out - reconnect GitHub to keep asking questions."; }
    else if(err && err.code === 429){ body.textContent = "Slow down a little - try again in a few seconds."; }
    else if(err && err.code){ body.textContent = "Backend responded with " + err.code + ": " + (err.detail || "no further detail") + " (POST " + base + "/ask)"; }
    else { body.textContent = "Could not reach " + base + "/ask at all - this is a network/CORS failure, not a server error. Check the backend is running and its CORS_ORIGINS includes " + location.origin + "."; }
    body.style.color = "var(--ink2)";
  });
}
function sampleMsg(code){
  switch(code){
    case "not_granted": case "sampling_disabled": case "not_declared": case "capability_disabled": return "Claude access is not available in this view.";
    case "rate_limited": return "Too many requests just now - try again in a minute.";
    case "session_expired": return "Sign in to Claude again to continue.";
    case "cancelled": return "Stopped.";
    case "refused": return "Claude declined to answer that one.";
    case "prompt_too_large": return "That was too much context to send at once.";
    default: return "Something went wrong reaching Claude. Try again.";
  }
}
function updateAskContext(){
  const c = $("#askCtx"); c.innerHTML = "";
  const chips = [];
  chips.push(scope === "all" ? "all repositories" : scope);
  if(view.v === "pr") chips.push("PR #"+view.n);
  if(view.v === "issue") chips.push("issue #"+view.n);
  if(view.v === "repo") chips.push(view.id);
  chips.forEach(t=>c.appendChild(tag(t,"iris")));
}
function openAsk(){
  $("#ask").classList.add("open");
  $("#ask").setAttribute("aria-hidden","false");
  $("#scrim").classList.add("on");
  updateAskContext();
  setTimeout(()=>$("#askIn").focus(),120);
}
function closeAsk(){
  $("#ask").classList.remove("open");
  $("#ask").setAttribute("aria-hidden","true");
  $("#scrim").classList.remove("on");
}
function askEmpty(){
  const log = $("#askLog"); log.innerHTML = "";
  const e = el("div","ask-empty");
  e.textContent = "Ask about anything Codive has synchronized - commits, pull requests, issues, workflow runs or indexed files. Answers point back at the source.";
  log.appendChild(e);
  const sg = el("div","sugg");
  ["What changed in authentication this week?",
   "What could break if PR #412 ships today?",
   "Why does CI keep failing on atlas/api?",
   "What is blocking issue #287?",
   "Summarize the last 9 commits"].forEach(q=>{
    const b = el("button",null,q);
    b.addEventListener("click",()=>askAsk(q));
    sg.appendChild(b);
  });
  log.appendChild(sg);
  turns = [];
}
function linkifyCitations(text, host){
  host.innerHTML = "";
  const parts = String(text).split(/(\[(?:pr|issue|commit|file|repo):[^\]]+\])/g);
  let para = el("p");
  parts.forEach(part=>{
    const m = /^\[(pr|issue|commit|file|repo):([^\]]+)\]$/.exec(part);
    if(m){
      const kind = m[1], id = m[2];
      const b = el("button","evidence", kind==="file" ? id : kind+" "+id);
      b.addEventListener("click",()=>{
        if(kind==="pr" && prBy(+id)) { closeAsk(); go({v:"pr",n:+id}); }
        else if(kind==="issue" && issueBy(+id)) { closeAsk(); go({v:"issue",n:+id}); }
        else if(kind==="repo" && repoBy(id)) { closeAsk(); go({v:"repo",id:id}); }
        else toast("Would open "+id);
      });
      para.appendChild(document.createTextNode(" "));
      para.appendChild(b);
    } else {
      part.split(/\n{2,}/).forEach((chunk,i)=>{
        if(i>0){ host.appendChild(para); para = el("p"); }
        para.appendChild(document.createTextNode(chunk));
      });
    }
  });
  host.appendChild(para);
}
const CANNED = {
  "what changed in authentication this week?":
    "Two commits landed on the auth branch two hours ago: token families with reuse detection [commit:a91f3c2], and bearer parsing moved out of the cookie session dependency [commit:4d02b71]. Both belong to the refresh-token rewrite [pr:412], which is open and waiting on your review. The front-end half is separate and not merged [file:src/auth/refresh.ts].",
  "what could break if pr #412 ships today?":
    "Two things. Concurrent refreshes have no lock between reading and rotating a token family, so a user with two tabs can be logged out [file:app/auth/tokens.py:88]. And changing a password no longer revokes existing token families, so old tokens stay valid for 30 days [file:app/auth/service.py:203]. There is also a coupling risk: the API change needs the front-end client to ship with it [pr:188].",
  "why does ci keep failing on atlas/api?":
    "The same test has failed three runs in a row - test_no_timeout, after the httpx bump [pr:418]. httpx 0.26 changed what timeout=None means, so the GitHub client that deliberately disabled timeouts for initial sync now inherits a short default [file:app/clients/github.py:52]. Setting an explicit long read timeout for the sync client fixes it.",
  "what is blocking issue #287?":
    "One open question: whether older history is backfilled lazily or left out until someone asks [issue:287]. The thread already settled the rest - paginate by commit date, checkpoint every 500 commits, and treat 90 days as enough for a first useful brief. Your draft on sync cursors overlaps with it [pr:421].",
  "summarize the last 9 commits":
    "Most of the movement is auth: two commits on the rotating-token work [commit:a91f3c2], and the retry-storm fix that merged in workers [commit:c7e5a90]. One dependency bump is the source of the current CI failure [pr:418]. Your own sync-cursor sketch is the newest thing in the list [commit:6cc1904], and the oldest is the HNSW benchmark script from thirteen days ago [pr:401]."
};
function askAsk(q){
  const log = $("#askLog");
  if(!turns.length) log.innerHTML = "";
  log.appendChild(el("div","msg-u",q));
  const a = el("div","msg-a");
  const who = el("div","who-a");
  who.innerHTML = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none"><path d="M1 12.5h4.2l2.3-6.8 3.6 13.6 3-9.4 1.9 2.6H23" stroke="var(--iris)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Codive</span>';
  a.appendChild(who);
  const body = el("div");
  const think = el("span","thinking"); think.innerHTML = "<i></i><i></i><i></i>";
  body.appendChild(think);
  a.appendChild(body);
  log.appendChild(a);
  log.scrollTop = log.scrollHeight;

  const canned = CANNED[q.trim().toLowerCase()];
  withSample(async (sample)=>{
    askCtl = new AbortController();
    turns.push({role:"user", content:q});
    const input = [{role:"user", content: CTX_RULES + "\n\nREPOSITORY STATE (JSON):\n" + contextBlob() + "\n\nAcknowledge with: Ready."},
                   {role:"assistant", content:"Ready."}].concat(turns);
    try{
      const {text} = await sample(input, {cache:false, signal:askCtl.signal, modelTier:"default",
        onText:({text})=>{ linkifyCitations(text, body); log.scrollTop = log.scrollHeight; }});
      linkifyCitations(text, body);
      turns.push({role:"assistant", content:text});
    }catch(e){
      if(e && e.text){ linkifyCitations(e.text, body); }
      else if(canned){ linkifyCitations(canned, body); }
      else { body.textContent = sampleMsg(e && e.code); body.style.color = "var(--ink2)"; }
      turns.pop();
    }
    log.scrollTop = log.scrollHeight;
  }, ()=>{
    if(backendConfigured()){ backendAsk(q, body, log); return; }
    setTimeout(()=>{
      if(canned) linkifyCitations(canned, body);
      else {
        body.textContent = "Live answers need Claude access in this view. The suggested questions still work - they run against the same synchronized repository state.";
        body.style.color = "var(--ink2)";
      }
      log.scrollTop = log.scrollHeight;
    }, 420);
  });
}

/* ============================ WIRING ============================ */
function initScope(){
  const s = $("#scope");
  REPOS.forEach(r=>{
    const o = document.createElement("option"); o.value = r.id; o.textContent = r.id; s.appendChild(o);
  });
  s.addEventListener("change",()=>{
    scope = s.value;
    if(view.v==="pr" || view.v==="issue" || view.v==="repo") view = {v:"overview"};
    render(); updateAskContext();
    const n = scope==="all" ? REPOS.length : 1;
    $("#syncText").textContent = n+" repositor"+(n===1?"y":"ies")+" · synced 2 minutes ago";
  });
}
function initTheme(){
  const b = $("#themeBtn");
  b.addEventListener("click",()=>{
    const cur = document.documentElement.getAttribute("data-theme");
    const dark = cur ? cur==="dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.setAttribute("data-theme", dark ? "light":"dark");
  });
}
document.addEventListener("keydown", e=>{
  if((e.metaKey||e.ctrlKey) && e.key.toLowerCase()==="k"){ e.preventDefault(); openCmdk(); return; }
  if(e.key === "Escape"){
    if($("#cmdk").classList.contains("open")) closeCmdk();
    else if($("#ask").classList.contains("open")) closeAsk();
    return;
  }
  if($("#cmdk").classList.contains("open")){
    if(e.key==="ArrowDown"){ e.preventDefault(); cmdkSel = Math.min(cmdkSel+1, cmdkHits.length-1); renderCmdk(); }
    if(e.key==="ArrowUp"){ e.preventDefault(); cmdkSel = Math.max(cmdkSel-1, 0); renderCmdk(); }
    if(e.key==="Enter" && cmdkHits[cmdkSel]){ e.preventDefault(); const h = cmdkHits[cmdkSel]; closeCmdk(); go(h.go); }
    return;
  }
  const tagN = (e.target.tagName||"").toLowerCase();
  if(tagN==="input"||tagN==="textarea"||tagN==="select") return;
  if(e.key === "/"){ e.preventDefault(); openAsk(); }
});
$("#searchBtn").addEventListener("click", openCmdk);
$("#cmdkIn").addEventListener("input",()=>{ cmdkSel=0; renderCmdk(); });
$("#cmdk").addEventListener("mousedown", e=>{ if(e.target.id==="cmdk") closeCmdk(); });
document.querySelectorAll(".cmdk-mode button").forEach(b=>{
  b.addEventListener("click",()=>{
    cmdkMode = b.dataset.mode;
    document.querySelectorAll(".cmdk-mode button").forEach(x=>x.setAttribute("aria-pressed", x===b ? "true":"false"));
    cmdkSel=0; renderCmdk(); $("#cmdkIn").focus();
  });
});
$("#askBtn").addEventListener("click", openAsk);
$("#askClose").addEventListener("click", closeAsk);
$("#scrim").addEventListener("click", closeAsk);
$("#askNew").addEventListener("click", ()=>{ if(askCtl) askCtl.abort(); askEmpty(); $("#askIn").focus(); });
$("#askSend").addEventListener("click", ()=>{
  const v = $("#askIn").value.trim(); if(!v) return;
  $("#askIn").value = ""; $("#askIn").style.height = "auto";
  askAsk(v);
});
$("#askIn").addEventListener("keydown", e=>{
  if(e.key==="Enter" && !e.shiftKey){ e.preventDefault(); $("#askSend").click(); }
});
$("#askIn").addEventListener("input", e=>{
  e.target.style.height = "auto";
  e.target.style.height = Math.min(e.target.scrollHeight, 110)+"px";
});

initTheme();
if(backendConfigured()){
  $("#page").innerHTML = '<div style="padding:60px 0;text-align:center;color:var(--ink3);font-size:13.5px">Connecting to your synced data…</div>';
}
boot();
async function boot(){
  const result = await tryLoadLiveData().catch(()=>false);
  if(result === "redirecting") return;  // onboarding.html takes over

  initScope();
  askEmpty();
  render();
  updateAskContext();

  if(CI.some(function(c){return c.state==="failing";})) $("#syncDot").classList.add("bad");
  $("#syncText").textContent = IS_LIVE
    ? REPOS.length + " repositor" + (REPOS.length===1?"y":"ies") + " · live · synced " +
      (REPOS[0] && REPOS[0].synced ? REPOS[0].synced : "recently") +
      (CI.some(c=>c.state==="failing") ? " · 1 workflow failing" : "")
    : REPOS.length + " repositor" + (REPOS.length===1?"y":"ies") + " · demo data · synced 2 minutes ago" +
      (CI.some(c=>c.state==="failing") ? " · 1 workflow failing" : "");

  useSample().then(f=>{
    $("#askNote").textContent = f
      ? "Answers cite the commit, pull request, issue or file they came from. Click a citation to open it."
      : backendConfigured() && IS_LIVE
        ? "Answers come from your synced data. Citations are clickable."
        : backendConfigured()
          ? "Signed out - connect GitHub from the landing page for live answers."
          : "Running on sample repository data. Point assets/config.js at your API for live answers.";
  });
}
})();
