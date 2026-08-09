"""Tests for the user/identity model: linking, merging, admin sync, and backfill.

These operate directly on SqliteDesignsRepository, since the login-time link
algorithm (``upsert_login_identity``) is a repository method by design -- the
plan deliberately keeps ``is_admin`` resolution in settings and passes it in,
so the repository itself needs no monkeypatching to exercise here.
"""

import sqlite3
from pathlib import Path

from backend.api_keys import generate_key
from backend.persistence.sqlite_repo import SqliteDesignsRepository


def test_local_and_pam_logins_with_no_email_are_separate_users(sqlite_designs_repo):
    local_user = sqlite_designs_repo.upsert_login_identity(
        provider="local", identifier="alice"
    )
    pam_user = sqlite_designs_repo.upsert_login_identity(
        provider="pam", identifier="alice"
    )
    assert local_user["id"] != pam_user["id"]
    assert len(sqlite_designs_repo.list_users()) == 2


def test_two_logins_same_identity_do_not_duplicate(sqlite_designs_repo):
    first = sqlite_designs_repo.upsert_login_identity(provider="local", identifier="alice")
    second = sqlite_designs_repo.upsert_login_identity(provider="local", identifier="alice")
    assert first["id"] == second["id"]
    assert len(sqlite_designs_repo.list_users()) == 1
    assert len(sqlite_designs_repo.list_user_identities(int(first["id"]))) == 1


def test_verified_email_shared_by_two_providers_merges_to_one_user(sqlite_designs_repo):
    u1 = sqlite_designs_repo.upsert_login_identity(
        provider="google", identifier="g-sub-1", email="shared@example.com"
    )
    token, key_hash, key_prefix = generate_key()
    sqlite_designs_repo.create_api_key(
        user_id=int(u1["id"]), name="bootstrap", key_hash=key_hash, key_prefix=key_prefix
    )

    u2 = sqlite_designs_repo.upsert_login_identity(
        provider="pam", identifier="carolp", email="shared@example.com"
    )

    assert u2["id"] == u1["id"]
    identities = sqlite_designs_repo.list_user_identities(int(u1["id"]))
    providers = {i["provider"] for i in identities}
    assert providers == {"google", "pam"}
    keys = sqlite_designs_repo.list_api_keys(int(u1["id"]))
    assert len(keys) == 1
    assert len(sqlite_designs_repo.list_users()) == 1


def test_legacy_google_email_identity_upgrades_to_sub_and_keeps_keys(sqlite_designs_repo):
    # Google identities used to be keyed by email itself.
    legacy = sqlite_designs_repo.upsert_login_identity(
        provider="google", identifier="alice@example.com", email="alice@example.com"
    )
    token, key_hash, key_prefix = generate_key()
    sqlite_designs_repo.create_api_key(
        user_id=int(legacy["id"]), name="old-key", key_hash=key_hash, key_prefix=key_prefix
    )

    upgraded = sqlite_designs_repo.upsert_login_identity(
        provider="google", identifier="107961038429795926728", email="alice@example.com"
    )

    assert upgraded["id"] == legacy["id"]
    identities = sqlite_designs_repo.list_user_identities(int(legacy["id"]))
    google_identities = [i for i in identities if i["provider"] == "google"]
    assert len(google_identities) == 1
    assert google_identities[0]["identifier"] == "107961038429795926728"
    keys = sqlite_designs_repo.list_api_keys(int(legacy["id"]))
    assert len(keys) == 1


def test_is_admin_resynced_on_login(sqlite_designs_repo):
    row = sqlite_designs_repo.upsert_login_identity(
        provider="local", identifier="alice", is_admin=True
    )
    assert row["is_admin"] is True

    row = sqlite_designs_repo.upsert_login_identity(
        provider="local", identifier="alice", is_admin=False
    )
    assert row["is_admin"] is False


def test_sync_admin_flags_demotes(sqlite_designs_repo):
    admin_row = sqlite_designs_repo.upsert_login_identity(
        provider="local", identifier="admin", is_admin=True
    )
    other_row = sqlite_designs_repo.upsert_login_identity(
        provider="local", identifier="someone", is_admin=False
    )

    sqlite_designs_repo.sync_admin_flags([int(admin_row["id"])])
    assert sqlite_designs_repo.get_user_by_id(int(admin_row["id"]))["is_admin"] is True
    assert sqlite_designs_repo.get_user_by_id(int(other_row["id"]))["is_admin"] is False

    changed = sqlite_designs_repo.sync_admin_flags([])
    assert changed > 0
    assert sqlite_designs_repo.get_user_by_id(int(admin_row["id"]))["is_admin"] is False


# --- Backfill from the legacy audit table -----------------------------------


def _seed_legacy_auth_users_only(path: Path) -> None:
    """Create a sqlite file containing only the legacy binderdash_auth_users
    table, mimicking a database that predates the user model.
    """
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE binderdash_auth_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            identifier TEXT NOT NULL,
            email TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_login_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(provider, identifier)
        );
        """
    )
    rows = [
        ("local", "alice", None),
        ("pam", "carol", None),
        ("google", "dave@example.com", "dave@example.com"),
        ("google", "eve@example.com", None),
    ]
    conn.executemany(
        "INSERT INTO binderdash_auth_users (provider, identifier, email) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def test_backfill_from_legacy_auth_users_table(tmp_path: Path):
    db_path = tmp_path / "legacy.sqlite"
    _seed_legacy_auth_users_only(db_path)

    repo = SqliteDesignsRepository(f"sqlite:///{db_path}")
    repo.init_schema()

    users = repo.list_users()
    assert len(users) == 4
    emails = {u["email"] for u in users}
    assert emails == {None, "dave@example.com", "eve@example.com"}

    dave = repo.get_user_by_email("dave@example.com")
    assert dave is not None
    assert repo.get_user_by_identity("google", "dave@example.com")["id"] == dave["id"]

    eve = repo.get_user_by_email("eve@example.com")
    assert eve is not None
    # No explicit email column for eve's row -- backfilled from her google identifier.
    assert repo.get_user_by_identity("google", "eve@example.com")["id"] == eve["id"]

    alice = repo.get_user_by_identity("local", "alice")
    carol = repo.get_user_by_identity("pam", "carol")
    assert alice is not None and carol is not None
    assert alice["email"] is None
    assert carol["email"] is None
    assert alice["id"] != carol["id"]


def test_backfill_is_idempotent_across_repeated_init_schema(tmp_path: Path):
    db_path = tmp_path / "legacy2.sqlite"
    _seed_legacy_auth_users_only(db_path)

    repo = SqliteDesignsRepository(f"sqlite:///{db_path}")
    repo.init_schema()
    repo.init_schema()

    assert len(repo.list_users()) == 4
    total_identities = sum(
        len(repo.list_user_identities(int(u["id"]))) for u in repo.list_users()
    )
    assert total_identities == 4


# --- Noop repository degradation --------------------------------------------


def test_noop_repo_api_keys_endpoint_returns_503(monkeypatch):
    import backend.auth as auth_mod
    import backend.main as main_mod
    import backend.settings as settings_mod
    from fastapi.testclient import TestClient
    from backend.persistence.factory import set_designs_repository
    from backend.persistence.noop_repo import NoopDesignsRepository

    patched_settings = main_mod.settings.model_copy(update={"auth_disabled": False})
    for mod in (settings_mod, main_mod, auth_mod):
        monkeypatch.setattr(mod, "settings", patched_settings)
    # The real lifespan would otherwise resolve a real (default) sqlite path
    # and clobber the noop repo we are about to install; pin it to noop.
    monkeypatch.setattr(
        main_mod,
        "init_designs_repository_from_url",
        lambda url: set_designs_repository(NoopDesignsRepository()),
    )
    set_designs_repository(NoopDesignsRepository())

    from backend.auth_providers.base import AuthUser
    from backend.auth import get_current_user_optional

    async def _fake_user():
        return AuthUser(
            username="alice", provider="local", user_id=1, auth_method="session"
        )

    app = main_mod.app
    app.dependency_overrides[get_current_user_optional] = _fake_user
    try:
        with TestClient(app) as client:
            r = client.get("/api/api-keys")
            assert r.status_code == 503
    finally:
        app.dependency_overrides.clear()
        set_designs_repository(NoopDesignsRepository())
