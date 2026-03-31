"""PDBTM URL parsing for reference fetch."""

from backend.util.superpose import parse_pdbtm_pdb_id_from_url


def test_parse_pdbtm_entry_url() -> None:
    assert parse_pdbtm_pdb_id_from_url("https://pdbtm.unitmp.org/entry/6lfl") == "6LFL"
    assert parse_pdbtm_pdb_id_from_url("http://pdbtm.unitmp.org/entry/1crn/") == "1CRN"


def test_parse_pdbtm_json_url() -> None:
    assert (
        parse_pdbtm_pdb_id_from_url("https://pdbtm.unitmp.org/api/v1/entry/6lfl.json")
        == "6LFL"
    )


def test_parse_pdbtm_non_match() -> None:
    assert parse_pdbtm_pdb_id_from_url("https://files.rcsb.org/download/1crn.cif") is None
    assert parse_pdbtm_pdb_id_from_url("1crn") is None
