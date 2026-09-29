import pytest

from backend.util.dna_optimization import (
    FIXED_STOP_DNA,
    fixed_nt_indices,
    free_intervals,
    resolve_fixed_mask,
)


def test_optimize_dna_basic(api_client) -> None:
    payload = {
        "sequences": {
            "d1": "MGS",
            "d2": "MYQ",
        },
        "codon_table_id": "e_coli",
        "method": "match_codon_usage",
        "constraints": [
            {"type": "EnforceGCContent", "enabled": True, "params": {"mini": 0.25, "maxi": 0.75}}
        ],
    }
    resp = api_client.post("/api/sequences/optimize-dna", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "elapsed_seconds" in data
    results = data["results"]
    assert len(results) == 2

    dict_res = {r["design_id"]: r for r in results}
    assert "d1" in dict_res
    assert "d2" in dict_res

    assert dict_res["d1"]["optimized_dna"] is not None
    assert dict_res["d2"]["optimized_dna"] is not None
    assert dict_res["d1"]["error"] is None
    assert len(dict_res["d1"]["optimized_dna"]) == 9
    assert len(dict_res["d2"]["optimized_dna"]) == 9


def test_optimize_dna_invalid_constraint(api_client) -> None:
    payload = {
        "sequences": {"d1": "MGS"},
        "codon_table_id": "e_coli",
        "method": "match_codon_usage",
        "constraints": [
            {"type": "UnknownConstraint", "enabled": True, "params": {}}
        ],
    }
    resp = api_client.post("/api/sequences/optimize-dna", json=payload)
    assert resp.status_code == 200
    res = resp.json()["results"][0]
    assert res["error"] is None
    assert res["optimized_dna"] is not None


@pytest.mark.timeout(10)
def test_optimize_dna_no_solution(api_client) -> None:
    payload = {
        "sequences": {"d1": "MGS"},
        "codon_table_id": "e_coli",
        "method": "match_codon_usage",
        "constraints": [
            {"type": "EnforceGCContent", "enabled": True, "params": {"mini": 1.0, "maxi": 1.0}},
            {"type": "EnforceGCContent", "enabled": True, "params": {"mini": 0.0, "maxi": 0.0}},
        ],
    }
    resp = api_client.post("/api/sequences/optimize-dna", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    res = data["results"][0]
    assert res["error"] is not None


def test_optimize_dna_disabled_constraint(api_client) -> None:
    payload = {
        "sequences": {"d1": "MGS"},
        "codon_table_id": "e_coli",
        "method": "match_codon_usage",
        "constraints": [
            {"type": "EnforceGCContent", "enabled": False, "params": {"mini": 1.0, "maxi": 1.0}},
            {"type": "EnforceGCContent", "enabled": False, "params": {"mini": 0.0, "maxi": 0.0}},
        ],
    }
    resp = api_client.post("/api/sequences/optimize-dna", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    res = data["results"][0]
    assert res["error"] is None


def test_resolve_fixed_mask_defaults_and_shift() -> None:
    assert resolve_fixed_mask("MGS*", None) == [False, False, False, True]
    assert resolve_fixed_mask("MA*M", [False, False, True, False]) == [
        False,
        False,
        True,
        False,
    ]
    # 5' insert moves which residue index is fixed (rescan, not stored coordinates).
    assert fixed_nt_indices(resolve_fixed_mask("MA*M", None)) == [6, 7, 8]
    assert fixed_nt_indices(resolve_fixed_mask("GMA*M", None)) == [9, 10, 11]
    assert free_intervals(12, [6, 7, 8]) == [(0, 6), (9, 12)]
    # Removing the stop drops the span.
    assert fixed_nt_indices(resolve_fixed_mask("MAM", None)) == []


def test_resolve_fixed_mask_rejects_bad_masks() -> None:
    with pytest.raises(ValueError, match="length"):
        resolve_fixed_mask("MGS", [False, False])
    # Leading Met may be fixed; an internal non-stop may not.
    assert resolve_fixed_mask("MGS", [True, False, False]) == [True, False, False]
    with pytest.raises(ValueError, match="leading Met|only stop"):
        resolve_fixed_mask("MGS", [False, True, False])


def test_optimize_dna_leading_met_stays_atg(api_client) -> None:
    from backend.util.dna_optimization import FIXED_START_DNA

    payload = {
        "sequences": {"d1": "MGS*"},
        "fixed": {"d1": [True, False, False, True]},
        "codon_table_id": "e_coli",
        "method": "match_codon_usage",
        "constraints": [
            {"type": "EnforceGCContent", "enabled": True, "params": {"mini": 0.25, "maxi": 0.75}}
        ],
    }
    resp = api_client.post("/api/sequences/optimize-dna", json=payload)
    assert resp.status_code == 200, resp.text
    res = resp.json()["results"][0]
    assert res["error"] is None
    dna = res["optimized_dna"]
    assert dna is not None
    assert dna.startswith(FIXED_START_DNA)
    assert dna.endswith(FIXED_STOP_DNA)
    assert len(dna) == 12


def test_optimize_dna_terminal_stop_stays_taa(api_client) -> None:
    payload = {
        "sequences": {"d1": "MGS*"},
        "fixed": {"d1": [False, False, False, True]},
        "codon_table_id": "e_coli",
        "method": "match_codon_usage",
        "constraints": [
            {"type": "EnforceGCContent", "enabled": True, "params": {"mini": 0.25, "maxi": 0.75}}
        ],
    }
    resp = api_client.post("/api/sequences/optimize-dna", json=payload)
    assert resp.status_code == 200, resp.text
    res = resp.json()["results"][0]
    assert res["error"] is None
    dna = res["optimized_dna"]
    assert dna is not None
    assert dna.endswith(FIXED_STOP_DNA)
    assert len(dna) == 12


def test_optimize_dna_internal_stop_stays_taa(api_client) -> None:
    payload = {
        "sequences": {"d1": "MA*M"},
        "fixed": {"d1": [False, False, True, False]},
        "codon_table_id": "e_coli",
        "method": "match_codon_usage",
        "constraints": [
            {"type": "EnforceGCContent", "enabled": True, "params": {"mini": 0.25, "maxi": 0.75}}
        ],
    }
    resp = api_client.post("/api/sequences/optimize-dna", json=payload)
    assert resp.status_code == 200, resp.text
    res = resp.json()["results"][0]
    assert res["error"] is None
    dna = res["optimized_dna"]
    assert dna is not None
    assert dna[6:9] == FIXED_STOP_DNA
    assert len(dna) == 12


def test_optimize_dna_fixed_shift_after_5prime_insert(api_client) -> None:
    payload = {
        "sequences": {"d1": "GMA*M"},
        "fixed": {"d1": [False, False, False, True, False]},
        "codon_table_id": "e_coli",
        "method": "match_codon_usage",
        "constraints": [
            {"type": "EnforceGCContent", "enabled": True, "params": {"mini": 0.2, "maxi": 0.8}}
        ],
    }
    resp = api_client.post("/api/sequences/optimize-dna", json=payload)
    assert resp.status_code == 200, resp.text
    res = resp.json()["results"][0]
    assert res["error"] is None
    dna = res["optimized_dna"]
    assert dna is not None
    assert dna[9:12] == FIXED_STOP_DNA
    assert len(dna) == 15


def test_optimize_dna_omitted_fixed_freezes_stops(api_client) -> None:
    payload = {
        "sequences": {"d1": "MGS*"},
        "codon_table_id": "e_coli",
        "method": "match_codon_usage",
        "constraints": [],
    }
    resp = api_client.post("/api/sequences/optimize-dna", json=payload)
    assert resp.status_code == 200, resp.text
    res = resp.json()["results"][0]
    assert res["error"] is None
    assert res["optimized_dna"].endswith(FIXED_STOP_DNA)


def test_optimize_dna_fixed_length_mismatch(api_client) -> None:
    payload = {
        "sequences": {"d1": "MGS"},
        "fixed": {"d1": [False, False]},
        "codon_table_id": "e_coli",
        "method": "match_codon_usage",
        "constraints": [],
    }
    resp = api_client.post("/api/sequences/optimize-dna", json=payload)
    assert resp.status_code == 200, resp.text
    res = resp.json()["results"][0]
    assert res["optimized_dna"] is None
    assert res["error"] is not None
    assert "length" in res["error"]


def test_optimize_dna_fixed_non_stop_residue(api_client) -> None:
    payload = {
        "sequences": {"d1": "MGS"},
        "fixed": {"d1": [False, True, False]},
        "codon_table_id": "e_coli",
        "method": "match_codon_usage",
        "constraints": [],
    }
    resp = api_client.post("/api/sequences/optimize-dna", json=payload)
    assert resp.status_code == 200, resp.text
    res = resp.json()["results"][0]
    assert res["optimized_dna"] is None
    assert res["error"] is not None
    assert "stop" in res["error"].lower() or "met" in res["error"].lower()
