"""Tests for GET /api/designs server-side query and GET /api/designs/columns."""

import json

import backend.cache as cache_mod


def _designs_payload():
    return [
        {
            "run_id": "run-a",
            "design_id": "d1",
            "method": "bindcraft",
            "Average_i_pTM": 0.5,
            "Length": 100,
            "project_id": "p1",
            "run_name": "R1",
        },
        {
            "run_id": "run-a",
            "design_id": "d2",
            "method": "bindcraft",
            "Average_i_pTM": 0.9,
            "Length": 120,
            "project_id": "p1",
            "run_name": "R1",
        },
        {
            "run_id": "run-b",
            "design_id": "d3",
            "method": "bindcraft",
            "Average_i_pTM": 0.7,
            "Length": 110,
            "project_id": "p2",
            "run_name": "R2",
        },
    ]


def test_list_designs_response_includes_total(api_client) -> None:
    cache_mod.designs_cache.clear()
    cache_mod.designs_cache.extend(_designs_payload())
    r = api_client.get("/api/designs")
    assert r.status_code == 200
    j = r.json()
    assert len(j["designs"]) == 3
    assert j["total"] == 3
    assert j["page"] is None
    assert j["page_size"] is None


def test_list_designs_pagination(api_client) -> None:
    cache_mod.designs_cache.clear()
    cache_mod.designs_cache.extend(_designs_payload())
    r = api_client.get(
        "/api/designs",
        params={"run_ids": "run-a", "page": 0, "page_size": 1, "sort_field": "design_id", "sort_order": 1},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 2
    assert j["page"] == 0
    assert j["page_size"] == 1
    assert len(j["designs"]) == 1
    assert j["designs"][0]["design_id"] == "d1"


def test_list_designs_global_filter(api_client) -> None:
    cache_mod.designs_cache.clear()
    cache_mod.designs_cache.extend(_designs_payload())
    r = api_client.get(
        "/api/designs",
        params={"global": "d3", "global_score_fields": "Average_i_pTM"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 1
    assert j["designs"][0]["design_id"] == "d3"


def test_list_designs_columns(api_client) -> None:
    cache_mod.designs_cache.clear()
    cache_mod.designs_cache.extend(_designs_payload())
    r = api_client.get("/api/designs/columns", params={"run_ids": "run-a,run-b"})
    assert r.status_code == 200
    cols = r.json()["columns"]
    fields = {c["field"] for c in cols}
    assert "design_id" in fields
    assert "Average_i_pTM" in fields


def test_list_designs_custom_filter_numeric(api_client) -> None:
    cache_mod.designs_cache.clear()
    cache_mod.designs_cache.extend(_designs_payload())
    cf = json.dumps(
        [
            {
                "column": "Average_i_pTM",
                "operator": "gte",
                "value": 0.65,
                "enabled": True,
            }
        ]
    )
    r = api_client.get("/api/designs", params={"custom_filters": cf})
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 2
    ids = {d["design_id"] for d in j["designs"]}
    assert ids == {"d2", "d3"}
