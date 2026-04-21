"""Run-level attempt counts and primary-score stats (Bindcraft / Boltzgen example_runs)."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BINDCRAFT_RUN = REPO_ROOT / "example_runs/ccl7_8fk6_5-70_hs5_11_13_20_47_default4stage.m3"
BOLTZGEN_RUN = REPO_ROOT / "example_runs/boltzgen-nanobody"


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
