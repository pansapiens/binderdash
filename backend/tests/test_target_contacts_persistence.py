CACHE_KEY = {
    "run_id": "run-1",
    "design_id": "design-1",
    "source_path": "",
    "structure_filename": "design_1.pdb",
    "binder_chains": "B",
    "target_chains": "A",
    "params_key": "cut12.0_p1.4_n100",
}

RECORD = {"v": 1, "residues": {"A166": [8.1, 6.4, 3.2, 12.0, 90.0]}}


def _item(**overrides):
    return {**CACHE_KEY, "contacts": RECORD, **overrides}


def test_contacts_cache_round_trip(sqlite_designs_repo) -> None:
    repo = sqlite_designs_repo
    assert repo.get_target_contacts_cache(**CACHE_KEY) is None

    assert repo.upsert_target_contacts_cache_bulk([_item()]) == 1
    assert repo.get_target_contacts_cache(**CACHE_KEY) == RECORD


def test_contacts_cache_upsert_replaces(sqlite_designs_repo) -> None:
    repo = sqlite_designs_repo
    repo.upsert_target_contacts_cache_bulk([_item()])
    updated = {"v": 1, "residues": {"A166": [1.0, 1.0, 1.0, 0.0, 90.0]}}
    repo.upsert_target_contacts_cache_bulk([_item(contacts=updated)])

    assert repo.get_target_contacts_cache(**CACHE_KEY) == updated
    assert repo.count_target_contacts_by_run(["run-1"], CACHE_KEY["params_key"]) == {"run-1": 1}


def test_contacts_cache_key_is_params_specific(sqlite_designs_repo) -> None:
    """A different cutoff or SASA setting yields incomparable numbers, so it must not
    read back a record computed under the previous settings."""
    repo = sqlite_designs_repo
    repo.upsert_target_contacts_cache_bulk([_item()])

    assert repo.get_target_contacts_cache(**{**CACHE_KEY, "params_key": "cut8.0_p1.4_n100"}) is None


def test_contacts_cache_key_is_chain_role_specific(sqlite_designs_repo) -> None:
    repo = sqlite_designs_repo
    repo.upsert_target_contacts_cache_bulk([_item()])

    assert repo.get_target_contacts_cache(**{**CACHE_KEY, "binder_chains": "A"}) is None


def test_list_contacts_for_runs(sqlite_designs_repo) -> None:
    repo = sqlite_designs_repo
    repo.upsert_target_contacts_cache_bulk(
        [
            _item(),
            _item(design_id="design-2"),
            _item(run_id="run-2", design_id="design-3"),
        ]
    )

    rows = repo.list_target_contacts_for_runs(["run-1"], CACHE_KEY["params_key"])
    assert {r["design_id"] for r in rows} == {"design-1", "design-2"}
    assert rows[0]["contacts"] == RECORD

    both = repo.list_target_contacts_for_runs(["run-1", "run-2"], CACHE_KEY["params_key"])
    assert len(both) == 3
    assert repo.count_target_contacts_by_run(
        ["run-1", "run-2"], CACHE_KEY["params_key"]
    ) == {"run-1": 2, "run-2": 1}


def test_list_contacts_empty_run_list(sqlite_designs_repo) -> None:
    repo = sqlite_designs_repo
    assert repo.list_target_contacts_for_runs([], "k") == []
    assert repo.count_target_contacts_by_run([], "k") == {}


def test_target_residues_round_trip(sqlite_designs_repo) -> None:
    repo = sqlite_designs_repo
    key = {
        "run_id": "run-1",
        "params_key": "cut12.0_p1.4_n100",
        "binder_chains": "B",
        "target_chains": "A",
    }
    assert repo.get_target_residues(**key) is None

    residues = [{"label": "A166", "resname": "GLU", "aa1": "E", "sasa_apo": 90.0}]
    repo.upsert_target_residues(**key, target_key="abc123", residues=residues)

    stored = repo.get_target_residues(**key)
    assert stored is not None
    assert stored["residues"] == residues
    assert stored["target_key"] == "abc123"
    assert stored["target_moves"] is False

    repo.upsert_target_residues(**key, target_key="abc123", residues=residues, target_moves=True)
    assert repo.get_target_residues(**key)["target_moves"] is True


def test_delete_run_clears_target_contact_state(sqlite_designs_repo) -> None:
    repo = sqlite_designs_repo
    repo.upsert_target_contacts_cache_bulk([_item()])
    repo.upsert_target_residues(
        run_id="run-1",
        params_key=CACHE_KEY["params_key"],
        binder_chains="B",
        target_chains="A",
        target_key="abc123",
        residues=[{"label": "A166"}],
    )

    repo.delete_run("run-1")

    assert repo.get_target_contacts_cache(**CACHE_KEY) is None
    assert (
        repo.get_target_residues(
            run_id="run-1",
            params_key=CACHE_KEY["params_key"],
            binder_chains="B",
            target_chains="A",
        )
        is None
    )
