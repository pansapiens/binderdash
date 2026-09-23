"""Google sign-in must round-trip the URL fragment the login page was opened on.

Fragments are not sent to the server, so the client encodes ``/#filtering`` as
the ``next`` query parameter. The callback has to put that fragment back on
the redirect, including when sign-in fails.
"""

from pathlib import Path

import pytest
from authlib.integrations.base_client import OAuthError
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from backend.routers.auth import safe_next_url
from backend.settings import settings as app_settings


def test_safe_next_url_keeps_fragment_and_query():
    assert safe_next_url(None) == "/"
    assert safe_next_url("  /#filtering  ") == "/#filtering"
    assert safe_next_url("/?keep=1#seq-prep") == "/?keep=1#seq-prep"
    assert safe_next_url("https://evil.example/phish") == "/"
    assert safe_next_url("//evil.example") == "/"
    assert safe_next_url("/\\evil.example") == "/"
    assert safe_next_url("/ok\r\nLocation: https://evil.example") == "/"


class _FakeGoogle:
    def __init__(self, userinfo=None, error: Exception | None = None):
        self.userinfo = userinfo
        self.error = error
        self.stored_next: str | None = None

    async def authorize_redirect(self, request, redirect_uri):
        self.stored_next = request.session.get("post_oauth_next")
        return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth", status_code=302)

    async def authorize_access_token(self, request):
        if self.error is not None:
            raise self.error
        return {"userinfo": self.userinfo or {}}


class _FakeOAuth:
    def __init__(self, google: _FakeGoogle):
        self.google = google


@pytest.fixture
def google_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import backend.auth as auth_mod
    import backend.auth_providers.google as google_mod
    import backend.main as main_mod
    import backend.routers.auth as auth_routes
    import backend.settings as settings_mod

    patched = app_settings.model_copy(
        update={
            "auth_disabled": False,
            "google_auth_enabled": True,
            "google_auth_client_id": "test-client",
            "google_auth_client_secret": "test-secret",
            "google_auth_redirect_uri": "http://testserver/api/auth/google/callback",
            "google_auth_allowed_users": ["user@example.com"],
        }
    )
    for mod in (settings_mod, main_mod, auth_mod, auth_routes, google_mod):
        monkeypatch.setattr(mod, "settings", patched)
    monkeypatch.setattr(
        main_mod, "default_sqlite_url", lambda: f"sqlite:///{tmp_path}/google.sqlite"
    )

    google = _FakeGoogle(userinfo={"email": "user@example.com", "name": "User"})
    monkeypatch.setattr(auth_routes, "get_oauth", lambda: _FakeOAuth(google))

    app = main_mod.app
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        yield client, google
    app.dependency_overrides.clear()


def _start(client: TestClient, google: _FakeGoogle, next_url: str):
    response = client.get(
        "/api/auth/google/login",
        params={"next": next_url},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert google.stored_next == safe_next_url(next_url)
    return response


def test_callback_redirect_keeps_fragment(google_client):
    client, google = google_client
    _start(client, google, "/#filtering")
    response = client.get("/api/auth/google/callback", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/#filtering"


def test_callback_redirect_keeps_query_and_fragment(google_client):
    client, google = google_client
    _start(client, google, "/?keep=1#plots")
    response = client.get("/api/auth/google/callback", follow_redirects=False)
    assert response.headers["location"] == "/?keep=1#plots"


def test_disallowed_google_user_keeps_fragment(google_client):
    client, google = google_client
    google.userinfo = {"email": "other@example.com"}
    _start(client, google, "/#designs")
    response = client.get("/api/auth/google/callback", follow_redirects=False)
    assert response.headers["location"] == "/?auth_error=not_allowed#designs"


def test_oauth_error_keeps_fragment(google_client):
    client, google = google_client
    google.error = OAuthError(error="access_denied")
    _start(client, google, "/#saved-sets")
    response = client.get("/api/auth/google/callback", follow_redirects=False)
    assert response.headers["location"] == "/?auth_error=oauth_failed#saved-sets"


def test_open_redirect_is_dropped(google_client):
    client, google = google_client
    _start(client, google, "https://evil.example/#filtering")
    response = client.get("/api/auth/google/callback", follow_redirects=False)
    assert response.headers["location"] == "/"
