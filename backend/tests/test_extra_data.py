"""Tests for extra_data column, ingest preservation, and merge-table."""

from pathlib import Path

import pytest

from backend.design_merge import apply_merge_table_upload
from backend.persistence.protocol import merge_design_from_storage, split_design_for_storage
from backend.run_discovery import update_design_sequence_and_binder_chain


def _seed_run(sqlite_designs_repo, tmp_path: Path, extra: dict | None = None) -> tuple[str, dict]:
    run_id = "run-extra"
    gk = "p1/extra-run"
    run_dict = {
        "run_id": run_id,
        "project_id": "p1",
        "method": "bindcraft",
        "path": str(tmp_path),
        "metadata": {"name": "extra-run"},
    }
    designs = [
        {
            "design_id": "d1",
            "run_id": run_id,
            "project_id": "p1",
            "method": "bindcraft",
            "Average_i_pTM": 0.5,
            **(extra or {}),
        },
        {
            "design_id": "d2",
            "run_id": run_id,
            "project_id": "p1",
            "method": "bindcraft",
            "Average_i_pTM": 0.6,
        },
    ]
    sqlite_designs_repo.upsert_run_and_replace_designs(gk, run_id, run_dict, designs)
    return run_id, run_dict


def test_merge_design_from_storage_extra_overrides() -> None:
    out = merge_design_from_storage(
        "r1",
        "d1",
        "p1",
        "bindcraft",
        "",
        None,
        None,
        {"Average_i_pTM": 0.5},
        extra={"custom_col": "yes", "Average_i_pTM": 0.99},
    )
    assert out["Average_i_pTM"] == 0.99
    assert out["custom_col"] == "yes"


def test_sequence_persisted_in_extra_data(sqlite_designs_repo, tmp_path: Path) -> None:
    run_id, run_dict = _seed_run(sqlite_designs_repo, tmp_path)
    update_design_sequence_and_binder_chain(
        run_dict,
        "d1",
        sequence="ACDEFG",
        binder_chain="B",
    )
    by_id = {d["design_id"]: d for d in sqlite_designs_repo.list_all_design_dicts()}
    assert by_id["d1"].get("Sequence") == "ACDEFG"
    assert by_id["d1"].get("binder_chain") == "B"


def test_reingest_preserves_extra_data(sqlite_designs_repo, tmp_path: Path) -> None:
    run_id, run_dict = _seed_run(sqlite_designs_repo, tmp_path)
    sqlite_designs_repo.merge_design_extra_data_bulk(
        run_id,
        [{"design_id": "d1", "fields": {"lab_note": "keep me"}}],
    )
    sqlite_designs_repo.update_design_good(run_id, "d1", True)
    designs_v2 = [
        {
            "design_id": "d1",
            "run_id": run_id,
            "project_id": "p1",
            "method": "bindcraft",
            "Average_i_pTM": 0.99,
        },
        {
            "design_id": "d2",
            "run_id": run_id,
            "project_id": "p1",
            "method": "bindcraft",
            "Average_i_pTM": 0.1,
        },
    ]
    sqlite_designs_repo.upsert_run_and_replace_designs(
        "p1/extra-run", run_id, run_dict, designs_v2
    )
    by_id = {d["design_id"]: d for d in sqlite_designs_repo.list_all_design_dicts()}
    assert by_id["d1"].get("lab_note") == "keep me"
    assert by_id["d1"].get("good") is True
    assert by_id["d1"].get("Average_i_pTM") == 0.99


def test_merge_extra_data_bulk_skips_pipeline_keys(sqlite_designs_repo, tmp_path: Path) -> None:
    run_id, _ = _seed_run(sqlite_designs_repo, tmp_path)
    stats = sqlite_designs_repo.merge_design_extra_data_bulk(
        run_id,
        [
            {
                "design_id": "d1",
                "fields": {"Average_i_pTM": 9.9, "new_metric": 1},
            }
        ],
    )
    assert stats["updated"] == 1
    assert stats["skipped_keys"] >= 1
    by_id = {d["design_id"]: d for d in sqlite_designs_repo.list_all_design_dicts()}
    assert by_id["d1"].get("new_metric") == 1
    assert by_id["d1"].get("Average_i_pTM") == 0.5


def test_apply_merge_table_upload(sqlite_designs_repo, tmp_path: Path) -> None:
    run_id, _ = _seed_run(sqlite_designs_repo, tmp_path)
    tsv = "design_id\tbatch\n d1\tB1\n d3\tB3\n"
    preview = apply_merge_table_upload(
        tsv.encode(),
        "extra.tsv",
        [run_id],
        preview=True,
    )
    assert preview["preview"] is True
    assert preview["matched_design_count"] == 1
    assert preview["unknown_design_id_count"] == 1
    assert "batch" in preview["new_columns"]

    result = apply_merge_table_upload(
        tsv.encode(),
        "extra.tsv",
        [run_id],
        preview=False,
    )
    assert result["updated"] >= 1
    by_id = {d["design_id"]: d for d in sqlite_designs_repo.list_all_design_dicts()}
    assert by_id["d1"].get("batch") == "B1"
