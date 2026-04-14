import shutil
from pathlib import Path

from backend.run_discovery import (
    update_design_sequence_and_binder_chain,
    update_design_tag,
)
from backend.tag_placement import (
    compute_tag_metrics_for_structure_file,
    determine_his_tag_placement,
)


def test_determine_his_tag_only_n_eligible():
    tag = determine_his_tag_placement(
        n_sasa=50.0,
        c_sasa=40.0,
        n_percent_sasa=40.0,
        c_percent_sasa=40.0,
        n_dist_target=10.0,
        c_dist_target=10.0,
        n_target_contacts=False,
        c_target_contacts=True,
        sasa_threshold_percent=30.0,
        more_distant_threshold_angstrom=5.0,
    )
    assert tag == "N"


def test_determine_his_tag_ambiguous_equal_sasa():
    tag = determine_his_tag_placement(
        n_sasa=50.0,
        c_sasa=50.0,
        n_percent_sasa=40.0,
        c_percent_sasa=40.0,
        n_dist_target=10.0,
        c_dist_target=10.0,
        n_target_contacts=False,
        c_target_contacts=False,
        sasa_threshold_percent=30.0,
        more_distant_threshold_angstrom=5.0,
    )
    assert tag is None


def _seed_tag_run(sqlite_designs_repo, tmp_path: Path) -> tuple[str, dict]:
    run_id = "run-tag-1"
    gk = "p1/tagrun"
    run_dict = {
        "run_id": run_id,
        "project_id": "p1",
        "method": "bindcraft",
        "path": str(tmp_path),
        "metadata": {"name": "tagrun"},
    }
    designs = [
        {"design_id": "a", "run_id": run_id, "project_id": "p1", "method": "bindcraft"},
        {
            "design_id": "b",
            "run_id": run_id,
            "project_id": "p1",
            "method": "bindcraft",
            "tag": "C",
        },
    ]
    sqlite_designs_repo.upsert_run_and_replace_designs(gk, run_id, run_dict, designs)
    return run_id, run_dict


def test_update_design_tag_persists_in_db(sqlite_designs_repo, tmp_path: Path) -> None:
    _, run_dict = _seed_tag_run(sqlite_designs_repo, tmp_path)
    update_design_tag(run_dict, "a", "N")
    rows = {d["design_id"]: d for d in sqlite_designs_repo.list_all_design_dicts()}
    assert rows["a"]["tag"] == "N"
    assert rows["b"]["tag"] == "C"


def test_update_design_tag_clear_in_db(sqlite_designs_repo, tmp_path: Path) -> None:
    _, run_dict = _seed_tag_run(sqlite_designs_repo, tmp_path)
    update_design_tag(run_dict, "b", None)
    rows = {d["design_id"]: d for d in sqlite_designs_repo.list_all_design_dicts()}
    assert rows["b"].get("tag") is None


def test_update_design_sequence_and_binder_chain_persists(
    sqlite_designs_repo, tmp_path: Path
) -> None:
    _, run_dict = _seed_tag_run(sqlite_designs_repo, tmp_path)
    update_design_sequence_and_binder_chain(
        run_dict,
        "a",
        sequence="ACDEFGHIK",
        binder_chain="B",
    )
    rows = {d["design_id"]: d for d in sqlite_designs_repo.list_all_design_dicts()}
    assert rows["a"]["Sequence"] == "ACDEFGHIK"
    assert rows["a"]["binder_chain"] == "B"


def test_compute_tag_metrics_returns_buried_and_predicted(tmp_path):
    src = Path(__file__).resolve().parent / "fixtures" / "two_chain_minimal.pdb"
    target = tmp_path / "m.pdb"
    shutil.copy(src, target)
    metrics, err = compute_tag_metrics_for_structure_file(target, binder_chain="B")
    assert err is None
    assert metrics is not None
    assert "n_sasa" in metrics and "c_sasa" in metrics
    assert "n_percent_sasa" in metrics and "c_percent_sasa" in metrics
    assert "n_percent_buried" in metrics and "c_percent_buried" in metrics
    assert "predicted_tag" in metrics
    if metrics["n_percent_sasa"] is not None:
        assert metrics["n_percent_buried"] == round(100.0 - float(metrics["n_percent_sasa"]), 2)


def test_compute_tag_metrics_target_chains_sets_distances(tmp_path):
    src = Path(__file__).resolve().parent / "fixtures" / "two_chain_minimal.pdb"
    target = tmp_path / "m.pdb"
    shutil.copy(src, target)
    metrics, err = compute_tag_metrics_for_structure_file(
        target, binder_chain="B", target_chains="A"
    )
    assert err is None
    assert metrics is not None
    assert metrics["n_dist_target"] is not None
    assert metrics["c_dist_target"] is not None
    assert float(metrics["n_dist_target"]) > 10.0
