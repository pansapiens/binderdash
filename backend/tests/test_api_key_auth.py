from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_key_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import backend.auth as auth_mod
    import backend.main as main_mod
    import backend.routers.auth as auth_routes_mod
    import backend.settings as settings_mod

    api_key = "test-secret-api-key-abc123"
    patched_settings = settings_mod.settings.model_copy(
        update={"auth_disabled": False, "binderdash_api_key": api_key}
    )
    for mod in (settings_mod, main_mod, auth_mod, auth_routes_mod):
        monkeypatch.setattr(mod, "settings", patched_settings)
    monkeypatch.setattr(
        main_mod,
        "default_sqlite_url",
        lambda: f"sqlite:///{tmp_path}/api.sqlite",
    )

    app = main_mod.app
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        yield client, api_key
    app.dependency_overrides.clear()


def test_api_key_bearer_allows_get(api_key_client):
    client, api_key = api_key_client
    r = client.get(
        "/api/runs",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert r.status_code == 200


def test_api_key_header_allows_get(api_key_client):
    client, api_key = api_key_client
    r = client.get(
        "/api/runs",
        headers={"X-Binderdash-Api-Key": api_key},
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
    client, api_key = api_key_client
    r = client.post(
        "/api/designs/refresh-cache",
        headers={"Authorization": f"Bearer {api_key}"},
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
    assert r.json()["providers"]["api_key"]["enabled"] is True
