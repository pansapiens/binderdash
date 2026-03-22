import pandas as pd

from backend.run_discovery import update_design_good_flag


def test_update_design_good_flag_adds_column(tmp_path):
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
    update_design_good_flag(run_metadata, "a", True)
    df = pd.read_csv(table, sep="\t")
    assert "good" in df.columns
    assert bool(df.loc[df["Design"] == "a", "good"].iloc[0])
    assert not bool(df.loc[df["Design"] == "b", "good"].iloc[0])


def test_update_design_good_flag_clear(tmp_path):
    run_dir = tmp_path / "run3"
    run_dir.mkdir()
    table = run_dir / "stats.tsv"
    pd.DataFrame({"Design": ["a", "b"], "good": [True, False]}).to_csv(
        table, sep="\t", index=False
    )
    run_metadata = {
        "path": str(run_dir),
        "results_table": "stats.tsv",
        "signature": {"design_id_columns": ["Design"]},
    }
    update_design_good_flag(run_metadata, "a", None)
    df = pd.read_csv(table, sep="\t")
    assert pd.isna(df.loc[df["Design"] == "a", "good"].iloc[0])
    assert df.loc[df["Design"] == "b", "good"].iloc[0] is False


def test_update_design_good_flag_not_found(tmp_path):
    run_dir = tmp_path / "run2"
    run_dir.mkdir()
    table = run_dir / "stats.tsv"
    pd.DataFrame({"Design": ["x"], "score": [1.0]}).to_csv(table, sep="\t", index=False)
    run_metadata = {
        "path": str(run_dir),
        "results_table": "stats.tsv",
        "signature": {"design_id_columns": ["Design"]},
    }
    try:
        update_design_good_flag(run_metadata, "missing", True)
    except ValueError as e:
        assert "not found" in str(e).lower()
    else:
        raise AssertionError("expected ValueError")
