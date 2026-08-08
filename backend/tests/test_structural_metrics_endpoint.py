"""Integration tests for POST /api/designs/structural-metrics."""

from __future__ import annotations

from pathlib import Path

import backend.cache as cache_mod
from backend.filtering.chain_roles import clear_chain_role_cache

FIXTURE_PDB = Path(__file__).resolve().parent / "fixtures" / "two_chain_minimal.pdb"


def _seed_bindcraft_run(run_id: str = "run-struct-1") -> None:
    cache_mod.run_cache.clear()
    cache_mod.designs_cache.clear()
    cache_mod.designs_by_run_id.clear()
    clear_chain_role_cache()
    cache_mod.run_cache[run_id] = {
        "run_id": run_id,
        "method": "bindcraft",
        "path": "/fake",
        "pdb_files": [str(FIXTURE_PDB)],
    }


def test_structural_metrics_computes_and_returns_result(api_client, sqlite_designs_repo) -> None:
    _seed_bindcraft_run()
    resp = api_client.post(
        "/api/designs/structural-metrics",
        json={
            "designs": [
                {
                    "run_id": "run-struct-1",
                    "design_id": "d1",
                    "pdb_file": FIXTURE_PDB.name,
                    "source_path": "",
                }
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    row = resp.json()["results"][0]
    assert row["error"] is None
    # bindcraft convention: target=A, binder=B
    assert row["binder_chain_ids"] == ["B"]
    assert row["target_chain_ids"] == ["A"]
    assert row["metrics"] is not None
    assert "helix_fraction" in row["metrics"]
    assert "ALA_fraction" in row["metrics"]


def test_structural_metrics_second_call_hits_cache(api_client, sqlite_designs_repo) -> None:
    _seed_bindcraft_run()
    body = {
        "designs": [
            {
                "run_id": "run-struct-1",
                "design_id": "d1",
                "pdb_file": FIXTURE_PDB.name,
                "source_path": "",
            }
        ]
    }
    first = api_client.post("/api/designs/structural-metrics", json=body)
    assert first.status_code == 200, first.text

    cached = sqlite_designs_repo.get_structural_metrics_cache(
        run_id="run-struct-1",
        design_id="d1",
        source_path="",
        structure_filename=FIXTURE_PDB.name,
        binder_chains="B",
        target_chains="A",
    )
    assert cached is not None

    second = api_client.post("/api/designs/structural-metrics", json=body)
    assert second.status_code == 200, second.text
    assert second.json()["results"][0]["metrics"] == cached


def test_structural_metrics_cache_only_miss_returns_empty_row(api_client, sqlite_designs_repo) -> None:
    _seed_bindcraft_run()
    resp = api_client.post(
        "/api/designs/structural-metrics",
        json={
            "designs": [
                {
                    "run_id": "run-struct-1",
                    "design_id": "d1",
                    "pdb_file": FIXTURE_PDB.name,
                    "source_path": "",
                }
            ],
            "cache_only": True,
        },
    )
    assert resp.status_code == 200, resp.text
    row = resp.json()["results"][0]
    assert row["metrics"] is None
    assert row["error"] is None


def test_structural_metrics_explicit_chain_override(api_client, sqlite_designs_repo) -> None:
    _seed_bindcraft_run()
    resp = api_client.post(
        "/api/designs/structural-metrics",
        json={
            "designs": [
                {
                    "run_id": "run-struct-1",
                    "design_id": "d1",
                    "pdb_file": FIXTURE_PDB.name,
                    "source_path": "",
                }
            ],
            "binder_chain_ids": ["A"],
            "target_chain_ids": ["B"],
        },
    )
    assert resp.status_code == 200, resp.text
    row = resp.json()["results"][0]
    assert row["binder_chain_ids"] == ["A"]
    assert row["target_chain_ids"] == ["B"]


def test_structural_metrics_run_not_found(api_client, sqlite_designs_repo) -> None:
    cache_mod.run_cache.clear()
    resp = api_client.post(
        "/api/designs/structural-metrics",
        json={"designs": [{"run_id": "missing-run", "design_id": "d1", "pdb_file": "x.pdb"}]},
    )
    assert resp.status_code == 200, resp.text
    row = resp.json()["results"][0]
    assert row["error"] == "Run not found"


def test_structural_metrics_structure_file_not_found(api_client, sqlite_designs_repo) -> None:
    _seed_bindcraft_run()
    resp = api_client.post(
        "/api/designs/structural-metrics",
        json={
            "designs": [
                {
                    "run_id": "run-struct-1",
                    "design_id": "d1",
                    "pdb_file": "does_not_exist.pdb",
                }
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    row = resp.json()["results"][0]
    assert row["error"] == "Structure file not found on disk"
