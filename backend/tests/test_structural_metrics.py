import numpy as np
import pytest

from backend.filtering.structural_metrics import (
    amino_acid_composition_fractions,
    compute_structural_metrics,
    delta_sasa,
    hbond_saltbridge_counts,
    hydrophobic_patch_area,
    hydrophobicity_score,
    secondary_structure_fractions,
)


def _place_residue(res_name: str, chain_id: str, res_id: int, offset):
    """One CCD-ideal-geometry residue (heavy atoms only), translated into place.

    Uses biotite's bundled Chemical Component Dictionary reference geometry (no
    network access, no external files) so the synthetic complex has chemically
    plausible bond lengths/angles for connect_via_residue_names/hydride/hbond/sasa
    to operate on meaningfully.
    """
    import biotite.structure.info as info

    residue = info.residue(res_name)
    residue = residue[residue.element != "H"]
    residue.coord = residue.coord + np.array(offset)
    residue.chain_id = np.full(len(residue), chain_id)
    residue.res_id = np.full(len(residue), res_id)
    return residue


@pytest.fixture(scope="module")
def synthetic_complex_pdb(tmp_path_factory) -> str:
    """A minimal but chemically real two-chain complex: an ASP on chain A (target)
    positioned near a LYS on chain B (binder) — close enough to form a salt bridge —
    plus an ALA on chain B for hydrophobic-composition coverage.
    """
    import biotite.structure as struc
    import biotite.structure.io.pdb as pdb_io

    asp = _place_residue("ASP", "A", 1, [0, 0, 0])
    lys = _place_residue("LYS", "B", 1, [3.0, 0.5, 0.0])
    ala = _place_residue("ALA", "B", 2, [8, 0, 0])

    combined = asp + lys + ala
    combined.bonds = struc.connect_via_residue_names(combined)

    out_dir = tmp_path_factory.mktemp("structural_metrics_fixtures")
    out_path = out_dir / "synthetic_complex.pdb"
    pdb_file = pdb_io.PDBFile()
    pdb_io.set_structure(pdb_file, combined)
    pdb_file.write(str(out_path))
    return str(out_path)


class TestAminoAcidComposition:
    def test_fractions_sum_to_one(self):
        fractions = amino_acid_composition_fractions("MAAGVKQL")
        assert fractions["ALA_fraction"] == pytest.approx(2 / 8)
        assert fractions["GLY_fraction"] == pytest.approx(1 / 8)
        assert sum(fractions.values()) == pytest.approx(1.0)

    def test_empty_sequence_is_nan(self):
        fractions = amino_acid_composition_fractions("")
        assert all(np.isnan(v) for v in fractions.values())

    def test_lowercase_input_normalised(self):
        assert amino_acid_composition_fractions("aaaa")["ALA_fraction"] == 1.0


class TestHydrophobicity:
    def test_all_hydrophobic_positive(self):
        # I, L, V are among the most hydrophobic residues on the Kyte-Doolittle scale.
        assert hydrophobicity_score("ILVILVILV") > 2.0

    def test_all_charged_negative(self):
        # R, D, E, K are among the most hydrophilic.
        assert hydrophobicity_score("RDEKRDEK") < -2.0

    def test_empty_sequence_is_nan(self):
        assert np.isnan(hydrophobicity_score(""))


class TestSecondaryStructureFractions:
    def test_fractions_sum_to_one(self, synthetic_complex_pdb):
        fractions = secondary_structure_fractions(synthetic_complex_pdb, chain_ids=["B"])
        total = sum(fractions.values())
        assert total == pytest.approx(1.0)

    def test_missing_chain_returns_nan(self, synthetic_complex_pdb):
        fractions = secondary_structure_fractions(synthetic_complex_pdb, chain_ids=["Z"])
        assert all(np.isnan(v) for v in fractions.values())


class TestDeltaSasa:
    def test_positive_when_chains_are_in_contact(self, synthetic_complex_pdb):
        # The ASP/LYS pair are positioned close enough to bury some target surface.
        value = delta_sasa(synthetic_complex_pdb, target_chain_ids=["A"], binder_chain_ids=["B"])
        assert value is not None
        assert value > 0

    def test_none_when_chain_set_empty(self, synthetic_complex_pdb):
        assert delta_sasa(synthetic_complex_pdb, target_chain_ids=[], binder_chain_ids=["B"]) is None

    def test_none_when_chain_missing_from_structure(self, synthetic_complex_pdb):
        assert (
            delta_sasa(synthetic_complex_pdb, target_chain_ids=["A"], binder_chain_ids=["Z"])
            is None
        )


class TestHydrophobicPatchArea:
    def test_positive_for_hydrophobic_chain(self, synthetic_complex_pdb):
        # Chain B has an ALA (hydrophobic, solvent-exposed in this synthetic complex).
        area = hydrophobic_patch_area(synthetic_complex_pdb, chain_ids=["B"])
        assert area is not None
        assert area > 0

    def test_zero_for_non_hydrophobic_chain(self, synthetic_complex_pdb):
        # Chain A is a lone ASP — not in the hydrophobic residue set.
        area = hydrophobic_patch_area(synthetic_complex_pdb, chain_ids=["A"])
        assert area == 0.0


class TestHbondSaltbridgeCounts:
    def test_detects_saltbridge(self, synthetic_complex_pdb):
        result = hbond_saltbridge_counts(
            synthetic_complex_pdb, binder_chain_ids=["B"], target_chain_ids=["A"]
        )
        assert result["structural_saltbridge"] > 0
        assert result["structural_hbonds"] >= 0

    def test_empty_chain_ids_returns_zeros(self, synthetic_complex_pdb):
        result = hbond_saltbridge_counts(synthetic_complex_pdb, binder_chain_ids=[], target_chain_ids=["A"])
        assert result == {"structural_hbonds": 0, "structural_saltbridge": 0}


class TestComputeStructuralMetrics:
    def test_returns_combined_dict(self, synthetic_complex_pdb):
        metrics = compute_structural_metrics(
            synthetic_complex_pdb, binder_chain_ids=["B"], target_chain_ids=["A"]
        )
        for key in (
            "helix_fraction",
            "sheet_fraction",
            "loop_fraction",
            "delta_sasa",
            "hydrophobic_patch_area",
            "structural_hbonds",
            "structural_saltbridge",
        ):
            assert key in metrics
