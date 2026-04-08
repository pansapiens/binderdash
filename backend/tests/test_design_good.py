from pathlib import Path

import pytest

from backend.run_discovery import update_design_good_flag


def _seed_run(sqlite_designs_repo, tmp_path: Path) -> tuple[str, dict]:
    run_id = "run-1"
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
        {
            "design_id": "b",
            "run_id": run_id,
            "project_id": "p1",
            "method": "bindcraft",
            "good": False,
        },
    ]
    sqlite_designs_repo.upsert_run_and_replace_designs(gk, run_id, run_dict, designs)
    return run_id, run_dict


def test_update_design_good_persists(sqlite_designs_repo, tmp_path: Path) -> None:
    _, run_dict = _seed_run(sqlite_designs_repo, tmp_path)
    update_design_good_flag(run_dict, "a", True)
    rows = {d["design_id"]: d for d in sqlite_designs_repo.list_all_design_dicts()}
    assert rows["a"]["good"] is True
    assert rows["b"]["good"] is False


def test_update_design_good_clears(sqlite_designs_repo, tmp_path: Path) -> None:
    _, run_dict = _seed_run(sqlite_designs_repo, tmp_path)
    update_design_good_flag(run_dict, "b", None)
    rows = {d["design_id"]: d for d in sqlite_designs_repo.list_all_design_dicts()}
    assert rows["b"].get("good") is None


def test_update_design_good_flag_not_found(sqlite_designs_repo, tmp_path: Path) -> None:
    _, run_dict = _seed_run(sqlite_designs_repo, tmp_path)
    with pytest.raises(ValueError, match="not found"):
        update_design_good_flag(run_dict, "missing", True)
