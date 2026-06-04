"""Load-path performance behaviour for GET /api/designs?run_ids=."""

from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import patch

import backend.cache as cache_mod
from backend.persistence.noop_repo import NoopDesignsRepository


def _design(run_id: str, design_id: str, **extra: Any) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "run_id": run_id,
        "design_id": design_id,
        "project_id": "p",
        "method": "boltzgen",
        "params": {"n": 1},
        "target_sequence": "ACDE",
        "run_path": "/nfs/runs/x",
    }
    row.update(extra)
    return row


def _seed_two_runs(n_a: int, n_b: int) -> tuple[str, str]:
    cache_mod.run_cache.clear()
    cache_mod.designs_cache.clear()
    cache_mod.designs_by_run_id.clear()
    run_a, run_b = "run-a", "run-b"
    cache_mod.run_cache[run_a] = {"run_id": run_a, "method": "boltzgen", "path": "/a"}
    cache_mod.run_cache[run_b] = {"run_id": run_b, "method": "boltzgen", "path": "/b"}
    rows_a = [_design(run_a, f"a{i}") for i in range(n_a)]
    rows_b = [_design(run_b, f"b{i}") for i in range(n_b)]
    cache_mod.designs_by_run_id[run_a] = rows_a
    cache_mod.designs_by_run_id[run_b] = rows_b
    cache_mod.designs_cache.extend(rows_a + rows_b)
    return run_a, run_b


def test_list_designs_run_scoped_returns_only_selected_run(api_client) -> None:
    run_a, run_b = _seed_two_runs(5, 5000)
    r = api_client.get("/api/designs", params={"run_ids": run_a})
    assert r.status_code == 200
    data = r.json()["designs"]
    assert len(data) == 5
    assert all(d["run_id"] == run_a for d in data)
    assert run_b not in {d["run_id"] for d in data}


def test_list_designs_empty_cache_run_scoped_no_full_refresh(
    api_client, sqlite_designs_repo
) -> None:
    cache_mod.run_cache.clear()
    cache_mod.designs_cache.clear()
    cache_mod.designs_by_run_id.clear()
    run_id = "run-only"
    cache_mod.run_cache[run_id] = {
        "run_id": run_id,
        "method": "boltzgen",
        "path": "/tmp/run",
        "project_id": "proj",
        "metadata": {"name": "test-run"},
    }
    designs = [_design(run_id, f"d{i}", score=float(i)) for i in range(3)]
    sqlite_designs_repo.upsert_run_and_replace_designs(
        "proj/test-run",
        run_id,
        cache_mod.run_cache[run_id],
        designs,
    )
    with patch.object(cache_mod, "refresh_designs_cache") as mock_refresh:
        r = api_client.get("/api/designs", params={"run_ids": run_id})
    assert r.status_code == 200
    assert len(r.json()["designs"]) == 3
    mock_refresh.assert_not_called()
    assert run_id in cache_mod.designs_by_run_id


def test_list_designs_run_ids_queries_db_slice(sqlite_designs_repo) -> None:
    run_id = "rid-1"
    designs = [_design(run_id, "d1")]
    sqlite_designs_repo.upsert_run_and_replace_designs(
        "p/r",
        run_id,
        {"run_id": run_id, "method": "boltzgen"},
        designs,
    )
    with patch.object(
        sqlite_designs_repo,
        "list_all_design_dicts",
        wraps=sqlite_designs_repo.list_all_design_dicts,
    ) as mock_all:
        out = sqlite_designs_repo.list_design_dicts_for_run_ids([run_id])
    assert len(out) == 1
    mock_all.assert_not_called()


def test_list_designs_trims_heavy_fields_by_default(api_client) -> None:
    run_a, _ = _seed_two_runs(1, 0)
    r = api_client.get("/api/designs", params={"run_ids": run_a})
    assert r.status_code == 200
    row = r.json()["designs"][0]
    assert "params" not in row
    assert "target_sequence" not in row
    assert "run_path" not in row


def test_list_designs_include_heavy(api_client) -> None:
    run_a, _ = _seed_two_runs(1, 0)
    r = api_client.get(
        "/api/designs", params={"run_ids": run_a, "include_heavy": "true"}
    )
    row = r.json()["designs"][0]
    assert "params" in row
    assert "target_sequence" in row


def test_list_designs_pagination(api_client) -> None:
    run_a, _ = _seed_two_runs(10, 0)
    r = api_client.get(
        "/api/designs",
        params={"run_ids": run_a, "page": 1, "page_size": 3},
    )
    data = r.json()
    assert len(data["designs"]) == 3
    assert data["total"] == 10
    assert data["page"] == 1
    assert data["page_size"] == 3


def test_ensure_designs_loaded_scales_by_run_not_total(sqlite_designs_repo) -> None:
    cache_mod.run_cache.clear()
    cache_mod.designs_cache.clear()
    cache_mod.designs_by_run_id.clear()
    run_a, run_b = "ra", "rb"
    for rid, n in ((run_a, 100), (run_b, 5000)):
        cache_mod.run_cache[rid] = {
            "run_id": rid,
            "method": "boltzgen",
            "project_id": "p",
            "metadata": {"name": rid},
            "path": f"/{rid}",
        }
        sqlite_designs_repo.upsert_run_and_replace_designs(
            f"p/{rid}",
            rid,
            cache_mod.run_cache[rid],
            [_design(rid, f"{rid}-{i}") for i in range(n)],
        )
    cache_mod.ensure_designs_loaded_for_run_ids([run_a])
    assert run_a in cache_mod.designs_by_run_id
    assert len(cache_mod.designs_by_run_id[run_a]) == 100
    assert run_b not in cache_mod.designs_by_run_id
