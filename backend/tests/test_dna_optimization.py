import pytest


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
