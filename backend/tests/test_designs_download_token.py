"""GET /api/designs download_token auth and ingest timestamp persistence."""

from pathlib import Path

import backend.cache as cache_mod
from backend.download_tokens import mint_designs_download_token
from backend.routers.designs import _authorize_list_designs


def _seed_cache(rows: list) -> None:
    cache_mod.designs_cache.clear()
    cache_mod.designs_by_run_id.clear()
    cache_mod.designs_cache.extend(rows)
    for row in rows:
        rid = str(row["run_id"])
        cache_mod.designs_by_run_id.setdefault(rid, []).append(row)


def _enable_auth(api_client, monkeypatch) -> None:
    import backend.auth as auth_mod
    import backend.main as main_mod
    import backend.settings as settings_mod

    patched = settings_mod.settings.model_copy(update={"auth_disabled": False})
    for mod in (settings_mod, main_mod, auth_mod):
        monkeypatch.setattr(mod, "settings", patched)
    # Exercise the real download_token path instead of the fixture's auth bypass.
    api_client.app.dependency_overrides.pop(_authorize_list_designs, None)


def test_download_token_allows_unauthenticated_get(api_client, monkeypatch) -> None:
    _enable_auth(api_client, monkeypatch)
    _seed_cache(
        [
            {"run_id": "run-a", "design_id": "d1", "iptm": 0.9},
            {"run_id": "run-a", "design_id": "d2", "iptm": 0.5},
        ]
    )
    token = mint_designs_download_token("run-a", "tsv")
    r = api_client.get(
        "/api/designs",
        params={"run_ids": "run-a", "format": "tsv", "download_token": token},
    )
    assert r.status_code == 200
    assert "d1" in r.text and "d2" in r.text


def test_download_token_wrong_run_is_403(api_client, monkeypatch) -> None:
    _enable_auth(api_client, monkeypatch)
    _seed_cache([{"run_id": "run-a", "design_id": "d1"}])
    token = mint_designs_download_token("run-a", "tsv")
    r = api_client.get(
        "/api/designs",
        params={"run_ids": "run-b", "format": "tsv", "download_token": token},
    )
    assert r.status_code == 403


def test_download_token_wrong_format_is_403(api_client, monkeypatch) -> None:
    _enable_auth(api_client, monkeypatch)
    _seed_cache([{"run_id": "run-a", "design_id": "d1"}])
    token = mint_designs_download_token("run-a", "tsv")
    r = api_client.get(
        "/api/designs",
        params={"run_ids": "run-a", "format": "json", "download_token": token},
    )
    assert r.status_code == 403


def test_without_token_requires_auth_when_enabled(api_client, monkeypatch) -> None:
    _enable_auth(api_client, monkeypatch)
    _seed_cache([{"run_id": "run-a", "design_id": "d1"}])
    r = api_client.get("/api/designs", params={"run_ids": "run-a"})
    assert r.status_code == 401


def test_reingest_preserves_ingested_at_and_refreshes_folder_mtime(
    sqlite_designs_repo, tmp_path: Path
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    run_id = "run-1"
    gk = "p1/n1"
    run_dict = {
        "run_id": run_id,
        "project_id": "p1",
        "method": "bindcraft",
        "path": str(run_dir),
        "metadata": {"name": "n1"},
    }
    designs = [
        {"design_id": "a", "run_id": run_id, "project_id": "p1", "method": "bindcraft"},
    ]
    sqlite_designs_repo.upsert_run_and_replace_designs(gk, run_id, run_dict, designs)
    first = sqlite_designs_repo.get_run_by_group_key(gk)
    assert first is not None
    assert first["ingested_at"]
    assert run_dict.get("folder_mtime") is not None
    first_mtime = run_dict["folder_mtime"]
    first_ingested = first["ingested_at"]

    # Touch the folder so mtime changes, then re-ingest.
    (run_dir / "marker").write_text("x")
    run_dict2 = {
        "run_id": run_id,
        "project_id": "p1",
        "method": "bindcraft",
        "path": str(run_dir),
        "metadata": {"name": "n1"},
    }
    sqlite_designs_repo.upsert_run_and_replace_designs(gk, run_id, run_dict2, designs)
    second = sqlite_designs_repo.get_run_by_group_key(gk)
    assert second is not None
    assert second["ingested_at"] == first_ingested
    assert run_dict2.get("folder_mtime") is not None
    assert run_dict2["folder_mtime"] >= first_mtime
    assert second["run_json"].get("folder_mtime") == run_dict2["folder_mtime"]
