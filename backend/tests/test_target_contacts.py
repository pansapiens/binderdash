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


class TestSasaConventions:
    """Pin what the areas mean, since the filter thresholds are calibrated against them.

    See ``backend/util/sasa.py``: biotite's ProtOr radii over heavy atoms only. These
    assert the convention rather than snapshotting areas, so a future change of kernel
    or radii set has to be a deliberate one.
    """

    def test_matches_biotite_native_protor(self, contact_complex_pdb):
        """Our own radii lookup must equal ``vdw_radii="ProtOr"`` on ordinary residues.

        We look the radii up ourselves only so an unrecognised ligand falls back instead
        of failing the whole structure; it must not otherwise change the answer.
        """
        from pathlib import Path

        import biotite.structure as struc
        import biotite.structure.io.pdb as pdb_io

        from backend.tag_placement import load_structure
        from backend.util.sasa import flatten_structure, residue_sasa

        array = pdb_io.PDBFile.read(contact_complex_pdb).get_structure(model=1)
        native = struc.sasa(array, probe_radius=1.4, point_number=100, vdw_radii="ProtOr")
        heavy = struc.filter_heavy(array)
        expected: dict = {}
        for chain_id, res_id, area in zip(
            array.chain_id[heavy], array.res_id[heavy], np.asarray(native)[heavy]
        ):
            if np.isfinite(area):
                key = (str(chain_id), int(res_id))
                expected[key] = expected.get(key, 0.0) + float(area)

        atoms = flatten_structure(load_structure(Path(contact_complex_pdb)))
        areas = residue_sasa(atoms)
        got = {
            (residue.get_parent().get_id(), int(residue.get_id()[1])): float(area)
            for residue, area in zip(atoms.residues, areas)
            if np.isfinite(area)
        }

        assert got.keys() == expected.keys()
        for key, area in expected.items():
            assert got[key] == pytest.approx(area, abs=1e-6)

    def test_hydrogens_do_not_change_the_areas(self, tmp_path):
        """Heavy-atom convention: modelled hydrogens must not move the numbers.

        Predicted structures differ in whether and where they place hydrogens, so if
        those counted, the same design would score differently per folding method.
        """
        from pathlib import Path

        import biotite.structure.info as info

        from backend.tag_placement import load_structure
        from backend.util.sasa import flatten_structure, residue_sasa

        with_h = info.residue("TYR")
        with_h.chain_id = np.full(len(with_h), "A")
        with_h.res_id = np.full(len(with_h), 1)
        without_h = with_h[with_h.element != "H"]
        assert len(with_h) > len(without_h), "fixture needs hydrogens to be meaningful"

        areas = []
        for name, residues in (("with_h", with_h), ("without_h", without_h)):
            path = _write_pdb([residues], tmp_path / f"{name}.pdb")
            atoms = flatten_structure(load_structure(Path(path)))
            areas.append(residue_sasa(atoms))

        np.testing.assert_allclose(areas[0], areas[1], atol=1e-6)

    def test_unknown_residue_falls_back_instead_of_raising(self):
        """A ligand biotite has no ProtOr entry for must not fail the whole structure."""
        import biotite.structure as struc
        import biotite.structure.info as info

        from backend.util.sasa import _FALLBACK_RADIUS, _protor_radii

        with pytest.raises((KeyError, ValueError)):
            info.vdw_radius_protor("ZZZ", "X1")

        array = struc.AtomArray(2)
        array.coord = np.zeros((2, 3), dtype=np.float32)
        array.element = np.array(["C", "C"])
        array.atom_name = np.array(["CA", "X1"])
        array.res_name = np.array(["GLY", "ZZZ"])

        radii = _protor_radii(array)
        assert radii[0] == pytest.approx(info.vdw_radius_protor("GLY", "CA"))
        assert radii[1] == pytest.approx(_FALLBACK_RADIUS)

    def test_apo_pass_matches_deleting_the_binder_chain(self, contact_complex_pdb):
        """Dropping binder atoms from the occluder set must equal removing the chain."""
        import copy
        from pathlib import Path

        from backend.filtering.target_contacts import (
            binder_atom_mask,
            target_residue_indices,
        )
        from backend.tag_placement import load_structure
        from backend.util.sasa import flatten_structure, residue_sasa

        apo_structure = copy.deepcopy(load_structure(Path(contact_complex_pdb)))
        apo_structure[0].detach_child("B")
        apo_atoms = flatten_structure(apo_structure)
        expected = {
            (r.get_parent().get_id(), int(r.get_id()[1])): float(a)
            for r, a in zip(apo_atoms.residues, residue_sasa(apo_atoms))
            if np.isfinite(a)
        }

        atoms = flatten_structure(load_structure(Path(contact_complex_pdb)))
        indices = target_residue_indices(atoms, {"B"})
        areas = residue_sasa(
            atoms,
            residue_indices=list(indices.values()),
            occluders=~binder_atom_mask(atoms, {"B"}),
        )
        got = {
            (key[0], key[1]): float(areas[index])
            for key, index in indices.items()
            if np.isfinite(areas[index])
        }

        assert got.keys() == expected.keys()
        for key, area in expected.items():
            assert got[key] == pytest.approx(area, abs=1e-6)

    def test_contacted_residue_buries_area_but_the_distant_one_does_not(
        self, contact_complex_pdb
    ):
        """The filter's whole premise: ΔSASA separates contacted from distant residues."""
        record = compute_target_contacts(contact_complex_pdb, ["B"])
        contacted = record.contacts["A1"]
        assert contacted.sasa_apo is not None
        assert contacted.sasa_apo - contacted.sasa_bound > 1.0
        # TRP 2 sits 40 A away, so it never earns a record at all.
        assert "A2" not in record.contacts
