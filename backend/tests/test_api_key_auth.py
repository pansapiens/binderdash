from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api_keys import generate_key
from backend.persistence.sqlite_repo import SqliteDesignsRepository


@pytest.fixture
def api_key_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A running app with one seeded user holding one live API key.

    Seeding goes straight through the repository rather than the CLI or a
    login round trip, since this fixture only cares about request-time
    validation, not user creation itself.
    """
    import backend.auth as auth_mod
    import backend.main as main_mod
    import backend.routers.auth as auth_routes_mod
    import backend.settings as settings_mod

    url = f"sqlite:///{tmp_path}/api.sqlite"
    seed_repo = SqliteDesignsRepository(url)
    seed_repo.init_schema()
    user = seed_repo.upsert_login_identity(provider="local", identifier="alice")
    assert user is not None
    token, key_hash, key_prefix = generate_key()
    seed_repo.create_api_key(
        user_id=int(user["id"]), name="ci", key_hash=key_hash, key_prefix=key_prefix
    )

    patched_settings = settings_mod.settings.model_copy(update={"auth_disabled": False})
    for mod in (settings_mod, main_mod, auth_mod, auth_routes_mod):
        monkeypatch.setattr(mod, "settings", patched_settings)
    monkeypatch.setattr(main_mod, "default_sqlite_url", lambda: url)

    app = main_mod.app
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        yield client, token
    app.dependency_overrides.clear()


def test_api_key_bearer_allows_get(api_key_client):
    client, token = api_key_client
    r = client.get(
        "/api/runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


def test_api_key_header_allows_get(api_key_client):
    client, token = api_key_client
    r = client.get(
        "/api/runs",
        headers={"X-Binderdash-Api-Key": token},
    )
    assert r.status_code == 200


def test_api_key_wrong_key_rejected(api_key_client):
    client, _ = api_key_client
    r = client.get(
        "/api/runs",
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert r.status_code == 401


def test_api_key_post_without_csrf(api_key_client):
    client, token = api_key_client
    r = client.post(
        "/api/designs/refresh-cache",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_session_post_without_csrf_rejected(api_key_client):
    client, _ = api_key_client
    r = client.post("/api/designs/refresh-cache")
    assert r.status_code == 403
    assert "CSRF" in r.text


def test_auth_status_reports_api_key_enabled(api_key_client):
    client, _ = api_key_client
    r = client.get("/api/auth/status")
    assert r.status_code == 200
    # api_keys.enabled reflects the per-user key mechanism (persistence
    # configured and auth not disabled), not the deprecated global env key.
    assert r.json()["api_keys"]["enabled"] is True
