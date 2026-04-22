"""Tests for short_name persistence (Prepare Sequences / Twist)."""

from pathlib import Path

from backend.persistence.protocol import merge_design_from_storage, split_design_for_storage


def test_split_merge_promotes_short_name() -> None:
    d = {
        "design_id": "d1",
        "run_id": "r1",
        "project_id": "p1",
        "method": "bindcraft",
        "short_name": "Tw_ab12",
        "extra": 1,
    }
    did, pid, meth, sp, tag, good, bc, sn, payload = split_design_for_storage(d)
    assert did == "d1"
    assert sn == "Tw_ab12"
    assert "short_name" not in payload
    assert payload.get("extra") == 1
    out = merge_design_from_storage(
        "r1", "d1", "p1", "bindcraft", "", None, None, payload, short_name=sn
    )
    assert out["short_name"] == "Tw_ab12"


def test_sqlite_short_name_bulk(sqlite_designs_repo, tmp_path: Path) -> None:
    run_id = "run-sn"
    gk = "p1/n1"
    run_dict = {
        "run_id": run_id,
        "project_id": "p1",
        "method": "bindcraft",
        "path": str(tmp_path),
        "metadata": {"name": "n1"},
    }
    designs = [
        {"design_id": "a", "run_id": run_id, "project_id": "p1", "method": "bindcraft"},
        {"design_id": "b", "run_id": run_id, "project_id": "p1", "method": "bindcraft"},
    ]
    sqlite_designs_repo.upsert_run_and_replace_designs(gk, run_id, run_dict, designs)
    n = sqlite_designs_repo.update_design_short_names_bulk(
        [
            {"run_id": run_id, "design_id": "a", "short_name": "short_a"},
            {"run_id": run_id, "design_id": "b", "short_name": "short_b"},
        ]
    )
    assert n == 2
    by_id = {d["design_id"]: d for d in sqlite_designs_repo.list_all_design_dicts()}
    assert by_id["a"].get("short_name") == "short_a"
    assert by_id["b"].get("short_name") == "short_b"

    sqlite_designs_repo.update_design_short_names_bulk(
        [{"run_id": run_id, "design_id": "a", "short_name": None}]
    )
    by_id = {d["design_id"]: d for d in sqlite_designs_repo.list_all_design_dicts()}
    assert by_id["a"].get("short_name") is None


def test_sqlite_ingest_round_trips_short_name(sqlite_designs_repo, tmp_path: Path) -> None:
    run_id = "run-sn2"
    gk = "p2/n2"
    run_dict = {
        "run_id": run_id,
        "project_id": "p2",
        "method": "bindcraft",
        "path": str(tmp_path),
        "metadata": {"name": "n2"},
    }
    designs = [
        {
            "design_id": "z",
            "run_id": run_id,
            "project_id": "p2",
            "method": "bindcraft",
            "short_name": "Z9",
        },
    ]
    sqlite_designs_repo.upsert_run_and_replace_designs(gk, run_id, run_dict, designs)
    by_id = {d["design_id"]: d for d in sqlite_designs_repo.list_all_design_dicts()}
    assert by_id["z"].get("short_name") == "Z9"
