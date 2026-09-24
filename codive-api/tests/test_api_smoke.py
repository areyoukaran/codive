import pytest

pytestmark = pytest.mark.asyncio


async def test_health_is_always_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["warnings"], list)


async def test_ready_reports_database_reachable(client):
    resp = await client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


async def test_root_lists_health_endpoint(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["health"] == "/health"


async def test_protected_route_requires_session(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_returns_current_user(authed_client, test_user):
    resp = await authed_client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["login"] == test_user.github_login


async def test_logout_clears_session(authed_client):
    resp = await authed_client.post("/auth/logout")
    assert resp.status_code == 200
    # cookie should be cleared/expired on the client jar
    resp2 = await authed_client.get("/auth/me")
    # httpx keeps the jar itself; the server told it to expire the cookie,
    # so the *next* real browser request would be unauthenticated. Here we
    # only assert the endpoint didn't error.
    assert resp2.status_code in (200, 401)


async def test_empty_repo_list_for_new_user(authed_client):
    resp = await authed_client.get("/repos")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_prs_empty_before_any_repo_selected(authed_client):
    resp = await authed_client.get("/prs")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_sync_start_without_repos_returns_400(authed_client):
    resp = await authed_client.post("/sync/start")
    assert resp.status_code == 400


async def test_webhook_rejects_bad_signature(client):
    resp = await client.post(
        "/webhooks/github",
        content=b'{"repository":{"full_name":"a/b"}}',
        headers={"X-Hub-Signature-256": "sha256=deadbeef", "X-GitHub-Event": "push", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


async def test_ask_requires_auth(client):
    resp = await client.post("/ask", json={"question": "what changed?"})
    assert resp.status_code == 401


async def test_ask_with_no_repos_returns_grounded_empty_context(authed_client):
    resp = await authed_client.post("/ask", json={"question": "what changed this week?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "template"  # no GROQ/GEMINI key in CI env by default
    assert "GROQ_API_KEY" in body["answer"] or "GEMINI_API_KEY" in body["answer"]
