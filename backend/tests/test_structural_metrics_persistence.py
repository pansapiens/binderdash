from pathlib import Path


def test_structural_metrics_cache_round_trip(sqlite_designs_repo) -> None:
    repo = sqlite_designs_repo
    assert (
        repo.get_structural_metrics_cache(
            run_id="r1",
            design_id="d1",
            source_path="",
            structure_filename="d1.pdb",
            binder_chains="B",
            target_chains="A",
        )
        is None
    )

    metrics = {"helix_fraction": 0.8, "delta_sasa": 900.0, "structural_hbonds": 7}
    repo.upsert_structural_metrics_cache(
        run_id="r1",
        design_id="d1",
        source_path="",
        structure_filename="d1.pdb",
        binder_chains="B",
        target_chains="A",
        metrics=metrics,
    )
    cached = repo.get_structural_metrics_cache(
        run_id="r1",
        design_id="d1",
        source_path="",
        structure_filename="d1.pdb",
        binder_chains="B",
        target_chains="A",
    )
    assert cached == metrics


def test_structural_metrics_cache_key_is_chain_role_specific(sqlite_designs_repo) -> None:
    repo = sqlite_designs_repo
    repo.upsert_structural_metrics_cache(
        run_id="r1",
        design_id="d1",
        source_path="",
        structure_filename="d1.pdb",
        binder_chains="B",
        target_chains="A",
        metrics={"delta_sasa": 900.0},
    )
    # Same design, different chain-role assignment -> different cache entry (miss).
    assert (
        repo.get_structural_metrics_cache(
            run_id="r1",
            design_id="d1",
            source_path="",
            structure_filename="d1.pdb",
            binder_chains="A",
            target_chains="B",
        )
        is None
    )


def test_structural_metrics_cache_upsert_overwrites(sqlite_designs_repo) -> None:
    repo = sqlite_designs_repo
    kwargs = dict(
        run_id="r1",
        design_id="d1",
        source_path="",
        structure_filename="d1.pdb",
        binder_chains="B",
        target_chains="A",
    )
    repo.upsert_structural_metrics_cache(metrics={"delta_sasa": 1.0}, **kwargs)
    repo.upsert_structural_metrics_cache(metrics={"delta_sasa": 2.0}, **kwargs)
    assert repo.get_structural_metrics_cache(**kwargs) == {"delta_sasa": 2.0}


def test_delete_run_clears_structural_metrics_cache(sqlite_designs_repo, tmp_path: Path) -> None:
    repo = sqlite_designs_repo
    run_dict = {
        "run_id": "r1",
        "project_id": "p1",
        "method": "bindcraft",
        "path": str(tmp_path),
        "metadata": {"name": "run1"},
    }
    repo.upsert_run_and_replace_designs("p1/run1", "r1", run_dict, [])
    repo.upsert_structural_metrics_cache(
        run_id="r1",
        design_id="d1",
        source_path="",
        structure_filename="d1.pdb",
        binder_chains="B",
        target_chains="A",
        metrics={"delta_sasa": 1.0},
    )
    assert repo.delete_run("r1") is True
    assert (
        repo.get_structural_metrics_cache(
            run_id="r1",
            design_id="d1",
            source_path="",
            structure_filename="d1.pdb",
            binder_chains="B",
            target_chains="A",
        )
        is None
    )
