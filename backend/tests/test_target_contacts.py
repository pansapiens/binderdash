import numpy as np
import pytest

from backend.filtering.target_contacts import (
    FAR,
    compute_reference_residues,
    compute_target_contacts,
    delta_sasa_percent,
    deserialise_record,
    parse_residue_label,
    residue_label,
    serialise_record,
    target_sequence_key,
)


def _place_residue(res_name: str, chain_id: str, res_id: int, offset):
    """One CCD-ideal-geometry residue (heavy atoms only), translated into place.

    Same approach as test_structural_metrics.py: biotite's bundled Chemical Component
    Dictionary geometry, so SASA has chemically plausible input without network access.
    """
    import biotite.structure.info as info

    residue = info.residue(res_name)
    residue = residue[residue.element != "H"]
    residue.coord = residue.coord + np.array(offset)
    residue.chain_id = np.full(len(residue), chain_id)
    residue.res_id = np.full(len(residue), res_id)
    return residue


def _write_pdb(residues, path):
    import biotite.structure as struc
    import biotite.structure.io.pdb as pdb_io

    combined = residues[0]
    for extra in residues[1:]:
        combined = combined + extra
    combined.bonds = struc.connect_via_residue_names(combined)
    pdb_file = pdb_io.PDBFile()
    pdb_io.set_structure(pdb_file, combined)
    pdb_file.write(str(path))
    return str(path)


@pytest.fixture(scope="module")
def contact_complex_pdb(tmp_path_factory) -> str:
    """Target chain A with a contacted residue (ASP 1, next to the binder) and a distant
    one (TRP 2, 40 Å away); binder chain B is a single LYS.
    """
    out_dir = tmp_path_factory.mktemp("target_contacts_fixtures")
    return _write_pdb(
        [
            _place_residue("ASP", "A", 1, [0, 0, 0]),
            _place_residue("TRP", "A", 2, [40, 0, 0]),
            _place_residue("LYS", "B", 1, [6.0, 0.5, 0.0]),
        ],
        out_dir / "contact_complex.pdb",
    )


class TestResidueLabels:
    def test_round_trip(self):
        assert residue_label("A", 166) == "A166"
        assert parse_residue_label("A166", {"A", "B"}) == ("A", 166, " ")

    def test_insertion_code(self):
        assert residue_label("A", 166, "B") == "A166B"
        assert parse_residue_label("A166B", {"A"}) == ("A", 166, "B")

    def test_multi_character_chain_id_wins_over_shorter_prefix(self):
        assert parse_residue_label("AB12", {"A", "AB"}) == ("AB", 12, " ")

    def test_unparseable_returns_none(self):
        assert parse_residue_label("Z99", {"A", "B"}) is None


class TestComputeTargetContacts:
    def test_only_residues_within_cutoff_are_recorded(self, contact_complex_pdb):
        record = compute_target_contacts(contact_complex_pdb, ["B"], record_cutoff=12.0)
        assert "A1" in record.contacts
        assert "A2" not in record.contacts

    def test_cutoff_boundary(self, contact_complex_pdb):
        d_heavy = compute_target_contacts(contact_complex_pdb, ["B"]).contacts["A1"].d_heavy
        inside = compute_target_contacts(
            contact_complex_pdb, ["B"], record_cutoff=d_heavy + 0.1
        )
        outside = compute_target_contacts(
            contact_complex_pdb, ["B"], record_cutoff=d_heavy - 0.1
        )
        assert "A1" in inside.contacts
        assert "A1" not in outside.contacts

    def test_wide_cutoff_admits_the_distant_residue(self, contact_complex_pdb):
        record = compute_target_contacts(contact_complex_pdb, ["B"], record_cutoff=60.0)
        assert set(record.contacts) == {"A1", "A2"}

    def test_distances_ordered_ca_cb_heavy(self, contact_complex_pdb):
        contact = compute_target_contacts(contact_complex_pdb, ["B"]).contacts["A1"]
        assert contact.d_heavy <= contact.d_cb
        assert contact.d_heavy <= contact.d_ca
        assert contact.d_heavy < FAR

    def test_binder_buries_target_surface(self, contact_complex_pdb):
        record = compute_target_contacts(contact_complex_pdb, ["B"])
        contact = record.contacts["A1"]
        assert contact.sasa_apo is not None
        assert contact.sasa_apo > contact.sasa_bound

    def test_chain_roles_reported(self, contact_complex_pdb):
        record = compute_target_contacts(contact_complex_pdb, ["B"])
        assert record.target_chain_ids == ["A"]
        assert record.binder_chain_ids == ["B"]

    def test_supplied_apo_reference_skips_the_apo_pass(self, contact_complex_pdb):
        record = compute_target_contacts(
            contact_complex_pdb, ["B"], apo_sasa_by_label={"A1": 100.0}
        )
        assert record.contacts["A1"].sasa_apo is None

    def test_missing_binder_chain_raises(self, contact_complex_pdb):
        with pytest.raises(ValueError, match="binder chains"):
            compute_target_contacts(contact_complex_pdb, ["Z"])


class TestReferenceResidues:
    def test_catalogue_covers_every_target_residue(self, contact_complex_pdb):
        residues = compute_reference_residues(contact_complex_pdb, ["B"])
        assert [r.label for r in residues] == ["A1", "A2"]
        assert [r.aa1 for r in residues] == ["D", "W"]
        assert all(r.sasa_apo > 0 for r in residues)

    def test_apo_sasa_ignores_the_binder(self, contact_complex_pdb):
        reference = {r.label: r.sasa_apo for r in compute_reference_residues(contact_complex_pdb, ["B"])}
        bound = compute_target_contacts(contact_complex_pdb, ["B"]).contacts["A1"]
        assert reference["A1"] == pytest.approx(bound.sasa_apo, abs=0.01)


class TestTargetSequenceKey:
    def test_same_target_same_key(self, contact_complex_pdb):
        assert target_sequence_key(contact_complex_pdb, ["B"]) == target_sequence_key(
            contact_complex_pdb, ["B"]
        )

    def test_different_chain_roles_give_different_keys(self, contact_complex_pdb):
        assert target_sequence_key(contact_complex_pdb, ["B"]) != target_sequence_key(
            contact_complex_pdb, ["A"]
        )


class TestSerialisation:
    def test_round_trip(self, contact_complex_pdb):
        record = compute_target_contacts(contact_complex_pdb, ["B"])
        restored = deserialise_record(serialise_record(record))
        assert restored.target_chain_ids == record.target_chain_ids
        assert restored.contacts.keys() == record.contacts.keys()
        assert restored.contacts["A1"].d_heavy == record.contacts["A1"].d_heavy
        assert restored.contacts["A1"].sasa_apo == record.contacts["A1"].sasa_apo


class TestDeltaSasaPercent:
    def test_against_tien_maximum(self):
        # ASP's theoretical maximum is 193 Å².
        assert delta_sasa_percent("ASP", 96.5) == pytest.approx(50.0)

    def test_unknown_residue_returns_none(self):
        assert delta_sasa_percent("XYZ", 10.0) is None
