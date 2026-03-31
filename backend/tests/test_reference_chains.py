"""Reference chain filter for TM-align and mmCIF output."""

import os
import tempfile
from pathlib import Path

import pytest
from Bio.PDB import MMCIFParser

from backend.util.superpose import (
    parse_reference_chain_list,
    superpose_reference_onto_design,
)

FIXTURE_PDB = Path(__file__).resolve().parent / "fixtures" / "two_chain_minimal.pdb"


def _chain_ids_from_mmcif(data: bytes) -> set[str]:
    parser = MMCIFParser(QUIET=True)
    with tempfile.NamedTemporaryFile(suffix=".cif", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        s = parser.get_structure("x", path)
        m = next(s.get_models())
        return {str(c.id).strip() for c in m}
    finally:
        os.unlink(path)


def test_parse_reference_chain_list() -> None:
    assert parse_reference_chain_list(None) is None
    assert parse_reference_chain_list("") is None
    assert parse_reference_chain_list("  ") is None
    assert parse_reference_chain_list("A") == ["A"]
    assert parse_reference_chain_list("A,B") == ["A", "B"]
    assert parse_reference_chain_list("A B") == ["A", "B"]
    assert parse_reference_chain_list("A, B  C") == ["A", "B", "C"]
    assert parse_reference_chain_list("A A B") == ["A", "B"]


def test_superpose_reference_subset_chains() -> None:
    pdb_bytes = FIXTURE_PDB.read_bytes()
    out, metrics = superpose_reference_onto_design(
        pdb_bytes, "pdb", FIXTURE_PDB, None, ["B"]
    )
    assert "tm_score_norm_design" in metrics
    ids = _chain_ids_from_mmcif(out)
    assert ids == {"B"}


def test_superpose_reference_all_chains_when_unfiltered() -> None:
    pdb_bytes = FIXTURE_PDB.read_bytes()
    out, _ = superpose_reference_onto_design(pdb_bytes, "pdb", FIXTURE_PDB, None, None)
    ids = _chain_ids_from_mmcif(out)
    assert ids == {"A", "B"}


def test_superpose_unknown_chain_raises() -> None:
    pdb_bytes = FIXTURE_PDB.read_bytes()
    with pytest.raises(ValueError, match="not found"):
        superpose_reference_onto_design(
            pdb_bytes, "pdb", FIXTURE_PDB, None, ["Z"]
        )


def test_design_same_file_longest_chain_aligns() -> None:
    pdb_bytes = FIXTURE_PDB.read_bytes()
    out_b, m_b = superpose_reference_onto_design(
        pdb_bytes, "pdb", FIXTURE_PDB, None, ["B"]
    )
    out_full, m_full = superpose_reference_onto_design(
        pdb_bytes, "pdb", FIXTURE_PDB, None, None
    )
    assert m_b["aligned_length"] == m_full["aligned_length"]
