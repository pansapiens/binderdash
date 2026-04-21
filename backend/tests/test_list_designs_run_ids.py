"""Tests for GET /api/designs run_ids filtering."""

import backend.cache as cache_mod


def test_list_designs_no_param_returns_all(api_client) -> None:
    cache_mod.designs_cache.clear()
    cache_mod.designs_cache.extend(
        [
            {"run_id": "run-a", "design_id": "d1"},
            {"run_id": "run-b", "design_id": "d2"},
        ]
    )
    r = api_client.get("/api/designs")
    assert r.status_code == 200
    body = r.json()
    assert len(body["designs"]) == 2
    assert body["total"] == 2


def test_list_designs_run_ids_filters_single(api_client) -> None:
    cache_mod.designs_cache.clear()
    cache_mod.designs_cache.extend(
        [
            {"run_id": "run-a", "design_id": "d1"},
            {"run_id": "run-b", "design_id": "d2"},
        ]
    )
    r = api_client.get("/api/designs", params={"run_ids": "run-a"})
    assert r.status_code == 200
    data = r.json()["designs"]
    assert len(data) == 1
    assert data[0]["design_id"] == "d1"


def test_list_designs_run_ids_comma_separated(api_client) -> None:
    cache_mod.designs_cache.clear()
    cache_mod.designs_cache.extend(
        [
            {"run_id": "run-a", "design_id": "d1"},
            {"run_id": "run-b", "design_id": "d2"},
            {"run_id": "run-c", "design_id": "d3"},
        ]
    )
    r = api_client.get("/api/designs", params={"run_ids": "run-a,run-b"})
    assert r.status_code == 200
    ids = {d["design_id"] for d in r.json()["designs"]}
    assert ids == {"d1", "d2"}


def test_list_designs_run_ids_unknown_returns_empty(api_client) -> None:
    cache_mod.designs_cache.clear()
    cache_mod.designs_cache.append({"run_id": "run-a", "design_id": "d1"})
    r = api_client.get("/api/designs", params={"run_ids": "nonexistent"})
    assert r.status_code == 200
    assert r.json()["designs"] == []
