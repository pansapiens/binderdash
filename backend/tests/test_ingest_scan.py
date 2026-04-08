def test_scan_empty_does_not_change_listed_runs(api_client) -> None:
    before = api_client.get("/api/runs").json()
    scan = api_client.post("/api/runs/scan", json={"folders": []})
    assert scan.status_code == 200
    assert scan.json() == {"runs": []}
    assert api_client.get("/api/runs").json() == before


def test_ingest_empty_ok(api_client) -> None:
    r = api_client.post("/api/runs/ingest", json={"runs": []})
    assert r.status_code == 200
    assert r.json() == {"runs": []}


def test_scan_accepts_force_rescan_of_ingested(api_client) -> None:
    r = api_client.post(
        "/api/runs/scan",
        json={"folders": [], "force_rescan_of_ingested": True},
    )
    assert r.status_code == 200
    assert r.json() == {"runs": []}


def test_ingest_preview_empty(api_client) -> None:
    r = api_client.post("/api/runs/ingest-preview", json={"runs": []})
    assert r.status_code == 200
    assert r.json() == {"reingest": []}
