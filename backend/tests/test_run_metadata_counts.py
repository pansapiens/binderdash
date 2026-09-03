"""Run-level attempt counts and primary-score stats (Bindcraft / Boltzgen example_runs)."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BINDCRAFT_RUN = REPO_ROOT / "example_runs/ccl7_8fk6_5-70_hs5_11_13_20_47_default4stage.m3"
BOLTZGEN_RUN = REPO_ROOT / "example_runs/boltzgen-nanobody"
MULTI_PDB_BINDCRAFT = REPO_ROOT / "example_runs/multi-pdb-bindcraft"


@pytest.mark.skipif(not BINDCRAFT_RUN.is_dir(), reason="example bindcraft run not present")
def test_bindcraft_resolve_trajectory_count() -> None:
    from backend.run_discovery import detect_run_type, resolve_trajectory_count

    sig = detect_run_type(BINDCRAFT_RUN)
    assert sig is not None
    assert resolve_trajectory_count(BINDCRAFT_RUN, sig) == 700


@pytest.mark.skipif(not BOLTZGEN_RUN.is_dir(), reason="example boltzgen run not present")
def test_boltzgen_resolve_trajectory_count() -> None:
    from backend.run_discovery import detect_run_type, resolve_trajectory_count

    sig = detect_run_type(BOLTZGEN_RUN)
    assert sig is not None
    assert resolve_trajectory_count(BOLTZGEN_RUN, sig) == 4


def test_bindcraft_multi_target_trajectory_count_from_params(tmp_path: Path) -> None:
    """``bindcraft_n_traj`` is per input PDB — total must be n_traj × n_targets."""
    from backend.run_discovery import (
        detect_run_type,
        resolve_target_count,
        resolve_trajectory_count,
    )

    run = tmp_path / "multi_bindcraft"
    (run / "input").mkdir(parents=True)
    (run / "input" / "A.pdb").write_text("ATOM\n")
    (run / "input" / "B.pdb").write_text("ATOM\n")
    (run / "results" / "bindcraft" / "accepted").mkdir(parents=True)
    (run / "results" / "bindcraft" / "final_design_stats.csv").write_text(
        "Target,Design,Average_i_pTM\nA.pdb,d1,0.8\nB.pdb,d2,0.7\n"
    )
    (run / "results" / "params.json").write_text(
        json.dumps(
            {
                "params": {
                    "input_pdb": "input/*.pdb",
                    "bindcraft_n_traj": 100,
                },
                "workflow": {},
            }
        )
    )

    sig = detect_run_type(run)
    assert sig is not None
    assert sig.get("trajectory_count_per_target") is True
    assert resolve_target_count(run, sig) == 2
    assert resolve_trajectory_count(run, sig) == 200


def test_count_csv_data_rows_cr_only(tmp_path: Path) -> None:
    from backend.run_discovery import count_csv_data_rows

    path = tmp_path / "traj.csv"
    # Classic Mac CR-only separators (seen in some BindCraft merges)
    path.write_bytes(b"Target,Design\rA.pdb,d1\rB.pdb,d2\r")
    assert count_csv_data_rows(path) == 2


@pytest.mark.skipif(
    not (MULTI_PDB_BINDCRAFT / "results" / "bindcraft" / "final_design_stats.csv").is_file(),
    reason="nf-binder-design multi-pdb-bindcraft example not present",
)
def test_bindcraft_multi_pdb_example_trajectory_count() -> None:
    from backend.run_discovery import (
        _bindcraft_target_count_from_trajectory_stats,
        detect_run_type,
        find_runs_recursive,
        resolve_target_count,
        resolve_trajectory_count,
    )

    sig = detect_run_type(MULTI_PDB_BINDCRAFT)
    assert sig is not None
    # params: bindcraft_n_traj=4, two input PDBs → 8 total
    assert _bindcraft_target_count_from_trajectory_stats(MULTI_PDB_BINDCRAFT) == 2
    assert resolve_target_count(MULTI_PDB_BINDCRAFT, sig) == 2
    assert resolve_trajectory_count(MULTI_PDB_BINDCRAFT, sig) == 8

    runs = find_runs_recursive(MULTI_PDB_BINDCRAFT)
    assert len(runs) == 1
    assert runs[0]["metadata"]["target_count"] == 2


def test_bindcraft_target_count_prefers_trajectory_stats_over_input_folder(
    tmp_path: Path,
) -> None:
    from backend.run_discovery import resolve_target_count

    run = tmp_path / "bindcraft"
    (run / "input").mkdir(parents=True)
    for name in ("A.pdb", "B.pdb", "C.pdb"):
        (run / "input" / name).write_text("ATOM\n")
    (run / "results" / "bindcraft").mkdir(parents=True)
    (run / "results" / "bindcraft" / "trajectory_stats.csv").write_text(
        "Target,Design\nA.pdb,d1\nB.pdb,d2\n"
    )
    (run / "results" / "params.json").write_text(
        json.dumps({"params": {"input_pdb": "input/*.pdb", "bindcraft_n_traj": 10}})
    )
    sig = {"trajectory_count_per_target": True}
    assert resolve_target_count(run, sig) == 2


def test_bindcraft_target_count_ignores_final_design_stats_without_trajectory_stats(
    tmp_path: Path,
) -> None:
    from backend.run_discovery import resolve_target_count

    run = tmp_path / "bindcraft"
    (run / "input").mkdir(parents=True)
    (run / "input" / "only.pdb").write_text("ATOM\n")
    (run / "results" / "bindcraft").mkdir(parents=True)
    (run / "results" / "bindcraft" / "final_design_stats.csv").write_text(
        "Target,Design\nA.pdb,d1\nB.pdb,d2\n"
    )
    sig = {"trajectory_count_per_target": True}
    assert resolve_target_count(run, sig) == 1


@pytest.mark.skipif(not BINDCRAFT_RUN.is_dir(), reason="example bindcraft run not present")
def test_bindcraft_primary_score_stats() -> None:
    from backend.run_discovery import compute_primary_score_stats, detect_run_type, load_run_table

    sig = detect_run_type(BINDCRAFT_RUN)
    assert sig is not None
    run_meta = {
        "path": str(BINDCRAFT_RUN),
        "results_table": sig["results_table"],
        "signature": sig,
        "method": sig["method"],
        "merged_paths": [str(BINDCRAFT_RUN)],
    }
    df = load_run_table(run_meta)
    assert df is not None and not df.empty
    stats = compute_primary_score_stats(df, sig)
    assert stats is not None
    assert stats["column"] == "Average_i_pTM"
    assert stats["count"] == len(df)
    assert stats["min"] <= stats["median"] <= stats["max"]


@pytest.mark.skipif(not BOLTZGEN_RUN.is_dir(), reason="example boltzgen run not present")
def test_boltzgen_primary_score_stats() -> None:
    from backend.run_discovery import compute_primary_score_stats, detect_run_type, load_run_table

    sig = detect_run_type(BOLTZGEN_RUN)
    assert sig is not None
    run_meta = {
        "path": str(BOLTZGEN_RUN),
        "results_table": sig["results_table"],
        "signature": sig,
        "method": sig["method"],
        "merged_paths": [str(BOLTZGEN_RUN)],
    }
    df = load_run_table(run_meta)
    assert df is not None and not df.empty
    stats = compute_primary_score_stats(df, sig)
    assert stats is not None
    assert stats["column"] == "design_to_target_iptm"
    assert stats["min"] <= stats["median"] <= stats["max"]
