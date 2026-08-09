"""MCP server: authentication, mounting, and the tool surface.

Drives the mounted sub-app in-process over httpx.ASGITransport, so requests pass
through the real middleware stack (CORS, sessions, CSRF) without opening a socket.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from backend.api_keys import generate_key
from backend.persistence.sqlite_repo import SqliteDesignsRepository

MCP_URL = "http://test/api/mcp/"


@pytest.fixture
def seeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A database URL plus a live API key, with the app pointed at it."""
    import backend.api_keys as api_keys_mod
    import backend.auth as auth_mod
    import backend.main as main_mod
    import backend.settings as settings_mod

    url = f"sqlite:///{tmp_path}/mcp.sqlite"
    repo = SqliteDesignsRepository(url)
    repo.init_schema()
    user = repo.upsert_login_identity(provider="local", identifier="alice")
    assert user is not None
    token, key_hash, key_prefix = generate_key()
    key = repo.create_api_key(
        user_id=int(user["id"]), name="mcp", key_hash=key_hash, key_prefix=key_prefix
    )

    patched = settings_mod.settings.model_copy(update={"auth_disabled": False})
    for mod in (settings_mod, main_mod, auth_mod):
        monkeypatch.setattr(mod, "settings", patched)
    # main.app is a module-level singleton; without this its lifespan would initialise
    # the real database (see test_api_key_auth.py, which does the same).
    monkeypatch.setattr(main_mod, "default_sqlite_url", lambda: url)
    api_keys_mod.reset_cache()

    yield {"url": url, "token": token, "repo": repo, "key_id": int(key["id"])}
    api_keys_mod.reset_cache()


@pytest_asyncio.fixture
async def app(seeded):
    import backend.main as main_mod

    application = main_mod.app
    application.dependency_overrides.clear()
    started, stop = asyncio.Event(), asyncio.Event()

    # The streamable-HTTP session manager opens anyio cancel scopes, which must be
    # exited by the task that entered them. pytest-asyncio runs async-fixture setup and
    # teardown on *different* tasks, so entering the lifespan inline makes the suite
    # error at teardown, attributed to the wrong test.
    async def run_lifespan() -> None:
        async with application.router.lifespan_context(application):
            started.set()
            await stop.wait()

    task = asyncio.create_task(run_lifespan())
    await started.wait()
    yield application
    stop.set()
    await task


def http_client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def mcp_client(app, token: str | None, header: str = "Authorization") -> Client:
    def factory(headers=None, timeout=None, auth=None, **kwargs) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers=headers,
            timeout=timeout,
            auth=auth,
            **kwargs,
        )

    headers = {}
    if token is not None:
        headers[header] = f"Bearer {token}" if header == "Authorization" else token
    return Client(
        StreamableHttpTransport(url=MCP_URL, headers=headers, httpx_client_factory=factory)
    )


class TestAuth:
    async def test_missing_key_is_401_not_a_csrf_403(self, app):
        """The regression test for the CSRF exemption.

        Without it the middleware answers first with text/plain "CSRF token missing",
        which no MCP client can interpret as an auth failure.
        """
        async with http_client(app) as http:
            resp = await http.post(
                "/api/mcp/",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                headers={"Accept": "application/json, text/event-stream"},
            )
        assert resp.status_code == 401
        assert "CSRF" not in resp.text
        assert "www-authenticate" in {k.lower() for k in resp.headers}

    async def test_slashless_path_redirects_rather_than_404(self, app):
        async with http_client(app) as http:
            resp = await http.post("/api/mcp", json={}, follow_redirects=False)
        assert resp.status_code == 307

    async def test_valid_key_lists_tools(self, app, seeded):
        async with mcp_client(app, seeded["token"]) as client:
            names = {tool.name for tool in await client.list_tools()}
        assert {"list_runs", "describe_methods", "describe_columns"} <= names

    async def test_binderdash_header_is_accepted(self, app, seeded):
        async with mcp_client(app, seeded["token"], header="X-Binderdash-Api-Key") as client:
            assert await client.list_tools()

    async def test_wrong_key_rejected(self, app):
        with pytest.raises(Exception):
            async with mcp_client(app, "bd_definitely-not-a-key") as client:
                await client.list_tools()

    async def test_revoked_key_rejected_immediately(self, app, seeded):
        """MCP and REST share one key cache, so revocation takes effect at once."""
        async with mcp_client(app, seeded["token"]) as client:
            assert await client.list_tools()

        seeded["repo"].revoke_api_key(seeded["key_id"])
        import backend.api_keys as api_keys_mod

        api_keys_mod.reset_cache()

        with pytest.raises(Exception):
            async with mcp_client(app, seeded["token"]) as client:
                await client.list_tools()


class TestDiscoveryTools:
    async def test_describe_methods_states_sort_directions(self, app, seeded):
        async with mcp_client(app, seeded["token"]) as client:
            result = await client.call_tool("describe_methods", {})
        by_name = {m["canonical"]: m for m in result.data["metrics"]}
        assert by_name["iptm"]["higher_is_better"] is True
        assert by_name["pae_interaction"]["higher_is_better"] is False
        assert "iptm" in result.data["ranking_presets"]

    async def test_list_runs_reads_the_shared_cache(self, app, seeded):
        import backend.cache as cache_mod

        cache_mod.run_cache.clear()
        cache_mod.run_cache["run-1"] = {
            "run_id": "run-1",
            "project_id": "proj",
            "method": "bindcraft",
            "metadata": {"name": "campaign-a"},
            "pdb_files": ["/data/runs/a/x.pdb"],
        }
        try:
            async with mcp_client(app, seeded["token"]) as client:
                result = await client.call_tool("list_runs", {})
        finally:
            cache_mod.run_cache.clear()

        assert result.data["total_runs"] == 1
        run = result.data["runs"][0]
        assert run["run_id"] == "run-1"
        assert run["method"] == "bindcraft"
        assert run["structure_count"] == 1
