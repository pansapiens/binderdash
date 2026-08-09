"""Tests for per-user API keys: generation, caching, and the /api/api-keys router.

Router-level cases (revoke, ownership, admin scoping, key-auth lockout) drive
a full app through TestClient with a real session login, since ownership and
scoping are enforced by the router + repository together. Lower-level cases
(caching, expiry boundaries, plaintext-at-rest) go straight at
``backend.api_keys`` and the repository, which is faster and more precise.
"""

import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api_keys import (
    ApiKeyPrincipal,
    expiry_from_days,
    generate_key,
    resolve_principal,
)
from backend.auth_providers.passwords import get_password_hash
from backend.persistence.factory import set_designs_repository
from backend.settings import LocalUser


class FakeRequest:
    """Minimal stand-in for a Starlette Request: headers + per-request state."""

    def __init__(self, headers: dict | None = None):
        self.headers = headers or {}
        self.state = types.SimpleNamespace()


# --- app_client: full session-capable app -----------------------------------


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import backend.auth as auth_mod
    import backend.auth_providers.local as local_auth_mod
    import backend.main as main_mod
    import backend.routers.auth as auth_routes_mod
    import backend.settings as settings_mod

    url = f"sqlite:///{tmp_path}/app.sqlite"
    local_users = [
        LocalUser(username="alice", password_hash=get_password_hash("alice-pw")),
        LocalUser(username="bob", password_hash=get_password_hash("bob-pw")),
        LocalUser(username="admin", password_hash=get_password_hash("admin-pw")),
    ]
    patched_settings = settings_mod.settings.model_copy(
        update={
            "auth_disabled": False,
            "local_users": local_users,
            "binderdash_admin_users": ["admin"],
        }
    )
    for mod in (settings_mod, main_mod, auth_mod, auth_routes_mod, local_auth_mod):
        monkeypatch.setattr(mod, "settings", patched_settings)
    monkeypatch.setattr(main_mod, "default_sqlite_url", lambda: url)

    app = main_mod.app
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def login(client: TestClient, username: str, password: str) -> str:
    r = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["csrf_token"]


def create_key(client: TestClient, csrf: str, name: str, **extra):
    payload = {"name": name, **extra}
    r = client.post(
        "/api/api-keys", json=payload, headers={"X-CSRF-Token": csrf}
    )
    return r


# --- Router: ownership, admin scoping, revocation ----------------------------


def test_revoked_key_401_immediately(app_client):
    csrf = login(app_client, "alice", "alice-pw")
    created = create_key(app_client, csrf, "mine").json()
    token = created["key"]
    key_id = created["id"]

    r = app_client.get("/api/runs", headers={"X-Binderdash-Api-Key": token})
    assert r.status_code == 200

    r = app_client.delete(f"/api/api-keys/{key_id}", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200

    # Drop the leftover session cookie from the login above -- otherwise a
    # rejected API key would silently fall back to the still-valid session,
    # masking the very thing this test checks.
    app_client.cookies.clear()
    r = app_client.get("/api/runs", headers={"X-Binderdash-Api-Key": token})
    assert r.status_code == 401


def test_user_a_gets_404_for_user_b_key_on_patch_and_delete(app_client):
    csrf_a = login(app_client, "alice", "alice-pw")
    created = create_key(app_client, csrf_a, "alices-key").json()
    key_id = created["id"]

    csrf_b = login(app_client, "bob", "bob-pw")
    r = app_client.patch(
        f"/api/api-keys/{key_id}",
        json={"name": "renamed"},
        headers={"X-CSRF-Token": csrf_b},
    )
    assert r.status_code == 404

    r = app_client.delete(f"/api/api-keys/{key_id}", headers={"X-CSRF-Token": csrf_b})
    assert r.status_code == 404


def test_admin_can_list_all_and_revoke_others_key(app_client):
    csrf_b = login(app_client, "bob", "bob-pw")
    created = create_key(app_client, csrf_b, "bobs-key").json()
    key_id = created["id"]

    csrf_admin = login(app_client, "admin", "admin-pw")
    r = app_client.get("/api/api-keys", params={"all": "true"})
    assert r.status_code == 200
    ids = [k["id"] for k in r.json()["keys"]]
    assert key_id in ids

    r = app_client.delete(f"/api/api-keys/{key_id}", headers={"X-CSRF-Token": csrf_admin})
    assert r.status_code == 200


def test_non_admin_cannot_list_all(app_client):
    csrf = login(app_client, "alice", "alice-pw")
    r = app_client.get("/api/api-keys", params={"all": "true"})
    assert r.status_code == 403


def test_admin_cannot_create_key_on_behalf_of_another_user(app_client):
    """There is no such parameter -- an admin's ``user_id`` in the body is ignored."""
    csrf_b = login(app_client, "bob", "bob-pw")
    bob_key = create_key(app_client, csrf_b, "bobs-own-key").json()

    csrf_admin = login(app_client, "admin", "admin-pw")
    listed = app_client.get("/api/api-keys", params={"all": "true"})
    bob_owned = next(k for k in listed.json()["keys"] if k["id"] == bob_key["id"])
    bob_user_id = bob_owned["user_id"]

    created = create_key(app_client, csrf_admin, "admin-key-with-user-id", user_id=bob_user_id)
    assert created.status_code == 201
    body = created.json()
    assert body["user_id"] != bob_user_id


def test_api_key_auth_gets_403_from_every_api_keys_route(app_client):
    csrf = login(app_client, "alice", "alice-pw")
    created = create_key(app_client, csrf, "alices-key").json()
    token = created["key"]
    key_id = created["id"]
    headers = {"X-Binderdash-Api-Key": token}

    assert app_client.get("/api/api-keys", headers=headers).status_code == 403
    assert (
        app_client.post("/api/api-keys", json={"name": "x"}, headers=headers).status_code
        == 403
    )
    assert (
        app_client.patch(
            f"/api/api-keys/{key_id}", json={"name": "y"}, headers=headers
        ).status_code
        == 403
    )
    assert app_client.delete(f"/api/api-keys/{key_id}", headers=headers).status_code == 403


def test_duplicate_live_key_name_conflicts_then_reusable_after_revoke(app_client):
    csrf = login(app_client, "alice", "alice-pw")
    first = create_key(app_client, csrf, "dupe")
    assert first.status_code == 201

    second = create_key(app_client, csrf, "dupe")
    assert second.status_code == 409

    key_id = first.json()["id"]
    r = app_client.delete(f"/api/api-keys/{key_id}", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200

    third = create_key(app_client, csrf, "dupe")
    assert third.status_code == 201


def test_plaintext_returned_exactly_once(app_client):
    csrf = login(app_client, "alice", "alice-pw")
    created = create_key(app_client, csrf, "once")
    assert created.status_code == 201
    assert "key" in created.json()

    listing = app_client.get("/api/api-keys")
    assert listing.status_code == 200
    for row in listing.json()["keys"]:
        assert "key" not in row
        assert "key_hash" not in row


def test_token_absent_from_raw_sqlite_bytes(app_client, tmp_path):
    csrf = login(app_client, "alice", "alice-pw")
    created = create_key(app_client, csrf, "secret-holder")
    token = created.json()["key"]

    db_dir = tmp_path
    haystacks = list(db_dir.glob("app.sqlite*"))
    assert haystacks, "expected the sqlite file (and/or its WAL) to exist"
    for path in haystacks:
        assert token.encode("utf-8") not in path.read_bytes()


# --- Expiry -------------------------------------------------------------------


def test_expired_key_401(app_client):
    csrf = login(app_client, "alice", "alice-pw")
    created = create_key(app_client, csrf, "already-expired", expires_in_days=0)
    assert created.status_code == 201
    token = created.json()["key"]

    # See test_revoked_key_401_immediately: without this, the leftover
    # session cookie from login() would authenticate the request instead.
    app_client.cookies.clear()
    r = app_client.get("/api/runs", headers={"X-Binderdash-Api-Key": token})
    assert r.status_code == 401


def test_expiry_from_days_zero_is_now_or_earlier():
    from backend.api_keys import _parse_sql_timestamp, utc_now

    exp = expiry_from_days(0)
    assert exp is not None
    parsed = _parse_sql_timestamp(exp)
    assert parsed <= utc_now()


# --- Caching and last_used_at (repository-level, no HTTP) --------------------


def test_two_validations_issue_exactly_one_hash_lookup(
    sqlite_designs_repo, monkeypatch: pytest.MonkeyPatch
):
    user = sqlite_designs_repo.upsert_login_identity(provider="local", identifier="carol")
    token, key_hash, key_prefix = generate_key()
    sqlite_designs_repo.create_api_key(
        user_id=int(user["id"]), name="k", key_hash=key_hash, key_prefix=key_prefix
    )

    calls = {"n": 0}
    real = sqlite_designs_repo.get_api_key_by_hash

    def counting(digest):
        calls["n"] += 1
        return real(digest)

    monkeypatch.setattr(sqlite_designs_repo, "get_api_key_by_hash", counting)

    p1 = resolve_principal(FakeRequest({"X-Binderdash-Api-Key": token}))
    p2 = resolve_principal(FakeRequest({"X-Binderdash-Api-Key": token}))
    assert isinstance(p1, ApiKeyPrincipal)
    assert isinstance(p2, ApiKeyPrincipal)
    assert calls["n"] == 1


def test_last_used_at_written_after_flush(
    sqlite_designs_repo, monkeypatch: pytest.MonkeyPatch
):
    import backend.api_keys as api_keys_mod
    from backend.api_keys import flush_last_used

    # _mark_used schedules its own background flush once every
    # LAST_USED_INTERVAL_SECONDS; disable that here so only the explicit
    # flush_last_used() call below drains the debounce queue, avoiding a race
    # between the two.
    class _NoStartThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(api_keys_mod.threading, "Thread", _NoStartThread)

    user = sqlite_designs_repo.upsert_login_identity(provider="local", identifier="dave")
    token, key_hash, key_prefix = generate_key()
    key_row = sqlite_designs_repo.create_api_key(
        user_id=int(user["id"]), name="k", key_hash=key_hash, key_prefix=key_prefix
    )

    before = sqlite_designs_repo.get_api_key(key_row["id"])
    assert before["last_used_at"] is None

    resolve_principal(FakeRequest({"X-Binderdash-Api-Key": token}))
    flushed = flush_last_used()
    assert flushed == 1

    after = sqlite_designs_repo.get_api_key(key_row["id"])
    assert after["last_used_at"] is not None


# --- Noop repository: zero DB calls, 503 everywhere --------------------------


def test_noop_repo_key_validation_touches_no_db(monkeypatch: pytest.MonkeyPatch):
    from backend.persistence.noop_repo import NoopDesignsRepository

    repo = NoopDesignsRepository()
    calls = {"n": 0}
    real = repo.get_api_key_by_hash

    def counting(digest):
        calls["n"] += 1
        return real(digest)

    monkeypatch.setattr(repo, "get_api_key_by_hash", counting)
    set_designs_repository(repo)

    principal = resolve_principal(FakeRequest({"X-Binderdash-Api-Key": "bd_whatever"}))
    assert principal is None
    assert calls["n"] == 0
