def test_list_codon_tables(api_client) -> None:
    res = api_client.get("/api/sequences/codon-tables")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) > 0
    values = {item["value"] for item in data["items"]}
    assert "e_coli_316407" in values
    for item in data["items"]:
        assert "label" in item and "value" in item


def test_get_codon_table_ecoli(api_client) -> None:
    res = api_client.get("/api/sequences/codon-tables/e_coli_316407")
    assert res.status_code == 200
    data = res.json()
    assert data["value"] == "e_coli_316407"
    assert "coli" in data["label"].lower()
    assert data["codons_by_aa"]["M"] == {"ATG": 1.0}
    assert set(data["stop_codons"]) >= {"TAA", "TAG", "TGA"}


def test_get_codon_table_invalid(api_client) -> None:
    res = api_client.get("/api/sequences/codon-tables/___invalid___")
    assert res.status_code == 404
