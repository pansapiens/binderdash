import shutil
from pathlib import Path

import pandas as pd

from backend.run_discovery import update_design_tag
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


def test_update_design_tag_writes_column(tmp_path):
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    table = run_dir / "stats.tsv"
    pd.DataFrame({"Design": ["a", "b"], "score": [1.0, 2.0]}).to_csv(
        table, sep="\t", index=False
    )
    run_metadata = {
        "path": str(run_dir),
        "results_table": "stats.tsv",
        "signature": {"design_id_columns": ["Design"]},
    }
    update_design_tag(run_metadata, "a", "N")
    df = pd.read_csv(table, sep="\t")
    assert "tag" in df.columns
    assert str(df.loc[df["Design"] == "a", "tag"].iloc[0]) == "N"
    assert pd.isna(df.loc[df["Design"] == "b", "tag"].iloc[0])


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


def test_update_design_tag_clear(tmp_path):
    run_dir = tmp_path / "run2"
    run_dir.mkdir()
    table = run_dir / "stats.tsv"
    pd.DataFrame(
        {"Design": ["a", "b"], "tag": ["N", "C"]}
    ).to_csv(table, sep="\t", index=False)
    run_metadata = {
        "path": str(run_dir),
        "results_table": "stats.tsv",
        "signature": {"design_id_columns": ["Design"]},
    }
    update_design_tag(run_metadata, "a", None)
    df = pd.read_csv(table, sep="\t")
    assert pd.isna(df.loc[df["Design"] == "a", "tag"].iloc[0])
    assert str(df.loc[df["Design"] == "b", "tag"].iloc[0]) == "C"
