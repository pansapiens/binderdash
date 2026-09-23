"""Solvent-accessible surface area over BioPython structures, via biotite's kernel.

One place so ``tag_placement`` (terminal-residue exposure) and
``filtering.target_contacts`` (per-target-residue burial) cannot drift apart: both
express exposure as a percentage of the same Tien et al. 2013 maxima, so they have to
agree on what the numerator means.

Conventions are biotite's own:

* **ProtOr radii** (Tsai et al. 1999), looked up per residue and atom name rather than
  per element, and **heavy atoms only** - hydrogens are dropped from the calculation
  entirely rather than given a radius. Predicted structures carry modelled hydrogens
  whose positions are an artefact of the folding method, so including them would make
  the areas depend on which model wrote the file.
* **Fibonacci** (golden-spiral) sphere points, the default distribution.

Parsing stays with BioPython, so callers keep working with ``Bio.PDB`` residues; only
the areas come from biotite, which is ~20x faster than ``Bio.PDB.SASA`` (that builds a
fresh KDTree of the point mesh for every atom).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

import biotite.structure as struc
import biotite.structure.info as struc_info
import numpy as np
from Bio.PDB import Residue, Structure

logger = logging.getLogger(__name__)

DEFAULT_PROBE_RADIUS = 1.4
DEFAULT_N_POINTS = 100

#: Names the radii set and atom selection in cache keys, so records computed under a
#: different convention can never be mistaken for these.
RADII_SET = "protor-heavy"

#: biotite's own fallback for an atom the ProtOr table does not cover.
_FALLBACK_RADIUS = 1.8


@dataclass
class StructureAtoms:
    """A BioPython structure flattened into the arrays biotite's SASA kernel wants.

    Hydrogens are already gone (see the module docstring). ``residue_of_atom`` indexes
    into ``residues``, which is in parse order, so callers can map areas back onto
    whatever residue identity they use without agreeing on a key format.
    """

    array: "struc.AtomArray"
    radii: np.ndarray
    residue_of_atom: np.ndarray
    residues: List[Residue.Residue]
    #: Chain of each residue, recorded while walking the structure so callers do not
    #: have to walk back up to the parent entity.
    residue_chain_ids: List[str]

    @property
    def residue_count(self) -> int:
        return len(self.residues)

    def atom_mask(self, residue_indices: Iterable[int]) -> np.ndarray:
        """Boolean mask over atoms belonging to any of ``residue_indices``."""
        indices = np.fromiter(set(residue_indices), dtype=np.int64)
        if not indices.size:
            return np.zeros(len(self.residue_of_atom), dtype=bool)
        return np.isin(self.residue_of_atom, indices)


def _protor_radii(array: "struc.AtomArray") -> np.ndarray:
    """ProtOr radius per atom, falling back to 1.8 A where the table has no entry.

    biotite already substitutes 1.8 for atoms it looks up successfully but has no radius
    for; it raises for residues or atom names absent from the Chemical Component
    Dictionary. Ligands and modified residues do occur in uploaded structures, and one
    of them should not fail the whole file, so those raises become the same fallback.
    """
    res_names = np.asarray(array.res_name)
    atom_names = np.asarray(array.atom_name)
    radii = np.empty(array.array_length(), dtype=np.float64)
    unknown = 0
    for i in range(array.array_length()):
        try:
            radius = struc_info.vdw_radius_protor(str(res_names[i]), str(atom_names[i]))
        except (KeyError, ValueError):
            radius = None
        if radius is None:
            unknown += 1
        radii[i] = _FALLBACK_RADIUS if radius is None else radius
    if unknown:
        logger.debug("ProtOr radius unavailable for %d atom(s); used %.1f A",
                     unknown, _FALLBACK_RADIUS)
    return radii


def flatten_structure(
    structure: Structure.Structure, model: int = 0
) -> StructureAtoms:
    """Flatten one model of a parsed structure, reusing the atoms BioPython gave us.

    Re-reading the file with biotite would risk the two parsers disagreeing about which
    atoms exist; this way the residue list is exactly what the caller iterates.
    """
    coords: List[np.ndarray] = []
    elements: List[str] = []
    atom_names: List[str] = []
    res_names: List[str] = []
    chain_ids: List[str] = []
    res_ids: List[int] = []
    residue_of_atom: List[int] = []
    residues: List[Residue.Residue] = []
    residue_chain_ids: List[str] = []

    for chain in structure[model]:
        chain_id = chain.get_id()
        for residue in chain.get_residues():
            index = len(residues)
            residues.append(residue)
            residue_chain_ids.append(chain_id)
            res_name = residue.get_resname().upper()
            for atom in residue:
                element = (atom.element or "").upper()
                if element in ("H", "D"):
                    continue
                coords.append(atom.coord)
                elements.append(element)
                atom_names.append(atom.get_id())
                res_names.append(res_name)
                chain_ids.append(chain_id)
                res_ids.append(int(residue.get_id()[1]))
                residue_of_atom.append(index)

    count = len(coords)
    array = struc.AtomArray(count)
    array.coord = np.asarray(coords, dtype=np.float32).reshape(count, 3)
    array.element = np.asarray(elements)
    array.atom_name = np.asarray(atom_names)
    array.res_name = np.asarray(res_names)
    array.chain_id = np.asarray(chain_ids)
    array.res_id = np.asarray(res_ids, dtype=int)

    return StructureAtoms(
        array=array,
        radii=_protor_radii(array),
        residue_of_atom=np.asarray(residue_of_atom, dtype=np.int64),
        residues=residues,
        residue_chain_ids=residue_chain_ids,
    )


def residue_sasa(
    atoms: StructureAtoms,
    *,
    residue_indices: Optional[Sequence[int]] = None,
    occluders: Optional[np.ndarray] = None,
    probe_radius: float = DEFAULT_PROBE_RADIUS,
    n_points: int = DEFAULT_N_POINTS,
) -> np.ndarray:
    """Per-residue SASA, indexed like ``atoms.residues``; NaN where not requested.

    ``residue_indices`` limits which residues get an area - the atoms of every other
    residue still occlude, they just cost nothing to skip. ``occluders`` is an atom mask
    that removes atoms from the structure altogether, which is how the apo pass drops a
    binder chain without copying anything.
    """
    totals = np.full(atoms.residue_count, np.nan)
    if not atoms.residue_count or not len(atoms.residue_of_atom):
        return totals

    if residue_indices is None:
        wanted = np.ones(len(atoms.residue_of_atom), dtype=bool)
        requested = np.arange(atoms.residue_count)
    else:
        requested = np.unique(np.asarray(list(residue_indices), dtype=np.int64))
        if not requested.size:
            return totals
        wanted = np.isin(atoms.residue_of_atom, requested)

    keep = np.ones(len(atoms.residue_of_atom), dtype=bool) if occluders is None else occluders
    # `wanted` spans every atom, so narrow it to the ones still present.
    sub_wanted = wanted[keep]
    if not sub_wanted.any():
        return totals

    per_atom = struc.sasa(
        atoms.array[keep],
        probe_radius=probe_radius,
        atom_filter=sub_wanted,
        point_number=n_points,
        vdw_radii=atoms.radii[keep],
    )

    summed = np.zeros(atoms.residue_count)
    owners = atoms.residue_of_atom[keep][sub_wanted]
    values = np.asarray(per_atom)[sub_wanted]
    finite = np.isfinite(values)
    np.add.at(summed, owners[finite], values[finite])

    # Only residues that actually kept an atom get a number; the rest stay NaN so a
    # caller cannot mistake "excluded from this pass" for "buried to zero".
    present = np.unique(owners)
    scored = np.intersect1d(requested, present, assume_unique=False)
    totals[scored] = summed[scored]
    return totals


def annotate_residue_sasa(
    structure: Structure.Structure,
    *,
    probe_radius: float = DEFAULT_PROBE_RADIUS,
    n_points: int = DEFAULT_N_POINTS,
    model: int = 0,
) -> None:
    """Set ``.sasa`` on every residue, as ``Bio.PDB.SASA.compute(level="R")`` did.

    Residues left out of the calculation (solvent, or all-hydrogen) get 0.0 rather than
    NaN, matching what the BioPython call used to leave behind.
    """
    atoms = flatten_structure(structure, model=model)
    areas = residue_sasa(atoms, probe_radius=probe_radius, n_points=n_points)
    for residue, area in zip(atoms.residues, areas):
        # Same duck-typed attribute Bio.PDB.SASA sets; callers read `residue.sasa`.
        residue.sasa = 0.0 if not np.isfinite(area) else float(area)  # type: ignore[attr-defined]
