from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import desktop as desktop_routes
from backend.settings import settings, update_run_base_dirs


@pytest.fixture()
def desktop_client(tmp_path: Path, monkeypatch):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    other_dir = tmp_path / "other"
    other_dir.mkdir()

    cfg_file = tmp_path / "desktop.json"
    monkeypatch.setenv("BINDERDASH_DESKTOP_CONFIG", str(cfg_file))
    monkeypatch.setattr(settings, "binderdash_desktop", True, raising=False)
    update_run_base_dirs([str(runs_dir)])

    app = FastAPI()
    app.include_router(desktop_routes.router)
    with TestClient(app) as client:
        yield client, runs_dir, other_dir


def test_desktop_info(desktop_client):
    client, runs_dir, _ = desktop_client
    resp = client.get("/api/desktop/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["desktop"] is True
    assert body["needs_setup"] is False
    assert str(runs_dir) in body["run_base_dirs"]


def test_put_run_base_dirs(desktop_client):
    client, _, other_dir = desktop_client
    resp = client.put(
        "/api/desktop/run-base-dirs",
        json={"run_base_dirs": [str(other_dir)]},
    )
    assert resp.status_code == 200
    assert resp.json()["run_base_dirs"] == [str(other_dir)]
