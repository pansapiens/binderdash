"""Tests for python -m backend.cli: the bootstrap path for a fresh deployment,
proven here end to end -- mint a key with no browser session, then use it.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.cli import main


@pytest.fixture
def cli_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point both the CLI and a fresh app instance at the same tmp sqlite file.

    `_init_repo` resolves the URL from `raw_settings.database` exactly as
    `main.py` does, so patching that in place keeps the two in sync.
    """
    import backend.settings as settings_mod
    from backend.persistence.factory import set_designs_repository
    from backend.persistence.noop_repo import NoopDesignsRepository

    url = f"sqlite:///{tmp_path}/cli.sqlite"
    monkeypatch.setattr(settings_mod.raw_settings, "database", url)
    yield url
    set_designs_repository(NoopDesignsRepository())


def test_cli_user_create_then_key_create_authenticates(
    cli_db: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    exit_code = main(
        ["user", "create", "--email", "bootstrap@example.org", "--admin"]
    )
    assert exit_code == 0
    create_out = capsys.readouterr().out
    assert "bootstrap@example.org" in create_out

    exit_code = main(
        ["key", "create", "bootstrap@example.org", "--name", "bootstrap-key"]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    token = captured.out.strip()
    assert token.startswith("bd_")
    assert "bootstrap-key" in captured.err

    import backend.auth as auth_mod
    import backend.main as main_mod
    import backend.routers.auth as auth_routes_mod
    import backend.settings as settings_mod

    patched_settings = settings_mod.settings.model_copy(update={"auth_disabled": False})
    for mod in (settings_mod, main_mod, auth_mod, auth_routes_mod):
        monkeypatch.setattr(mod, "settings", patched_settings)
    # This test only exercises the API-key path (not password login), so
    # backend.auth_providers.local need not be patched here.
    monkeypatch.setattr(main_mod, "default_sqlite_url", lambda: cli_db)

    app = main_mod.app
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        r = client.get("/api/runs", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
    app.dependency_overrides.clear()


def test_cli_key_create_without_user_or_all_errors(cli_db: str):
    exit_code = main(["key", "list"])
    assert exit_code == 1
