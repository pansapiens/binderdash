"""Tests for GET /api/designs run_ids filtering."""

import backend.cache as cache_mod


def _seed_cache(rows: list) -> None:
    cache_mod.designs_cache.clear()
    cache_mod.designs_by_run_id.clear()
    cache_mod.designs_cache.extend(rows)
    for row in rows:
        rid = str(row["run_id"])
        cache_mod.designs_by_run_id.setdefault(rid, []).append(row)


def test_list_designs_no_param_returns_all(api_client) -> None:
    _seed_cache(
        [
            {"run_id": "run-a", "design_id": "d1"},
            {"run_id": "run-b", "design_id": "d2"},
        ]
    )
    r = api_client.get("/api/designs")
    assert r.status_code == 200
    assert len(r.json()["designs"]) == 2


def test_list_designs_run_ids_filters_single(api_client) -> None:
    _seed_cache(
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
    _seed_cache(
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
    _seed_cache([{"run_id": "run-a", "design_id": "d1"}])
    r = api_client.get("/api/designs", params={"run_ids": "nonexistent"})
    assert r.status_code == 200
    assert r.json()["designs"] == []


def test_list_designs_format_tsv(api_client) -> None:
    _seed_cache(
        [
            {"run_id": "run-a", "design_id": "d1", "iptm": 0.9},
            {"run_id": "run-a", "design_id": "d2", "iptm": 0.5},
        ]
    )
    r = api_client.get("/api/designs", params={"run_ids": "run-a", "format": "tsv"})
    assert r.status_code == 200
    assert "text/tab-separated-values" in r.headers["content-type"]
    assert "designs_run-a.tsv" in r.headers.get("content-disposition", "")
    lines = r.text.strip().split("\n")
    assert lines[0].startswith("run_id")
    assert "design_id" in lines[0]
    assert len(lines) == 3  # header + 2 rows
    assert "d1" in r.text and "d2" in r.text


def test_list_designs_format_json_is_default(api_client) -> None:
    _seed_cache([{"run_id": "run-a", "design_id": "d1"}])
    r = api_client.get("/api/designs", params={"run_ids": "run-a", "format": "json"})
    assert r.status_code == 200
    assert "designs" in r.json()
