"""Structural metrics computable from a single structure + sequence — no PAE/pLDDT
confidence output and no refolding pass required.

Ports the subset of boltzgen's ``Analyze`` metrics (repos/boltzgen/src/boltzgen/task/
analyze/analyze_utils.py, analyze.py) that are pure functions of coordinates + sequence,
so they can be computed for *any* method's output structure (rfd, rfd3, bindcraft), not
just boltzgen's own pipeline. This closes part of the metric-parity gap described in
the filtering plan's cross-run-type metric table.

Deliberately avoids ``pydssp`` (boltzgen's choice for secondary structure): it pulls in
a full CPU/CUDA torch install for what is, on CPU, a tiny computation. Uses biotite's
built-in ``annotate_sse`` (P-SEA algorithm, CA-coordinates only) instead — the same
alternative the filtering plan's own Q7 answer suggested.

Salt-bridge detection needs per-atom formal charges. Boltzgen's own table
(``boltzgen/data/const.py``, ``formal_charges``) assigns the formal +-1 charge to a
single representative atom per residue — not every chemically-charged atom — since the
charge on a carboxylate/guanidinium group is delocalized, not doubled/tripled across its
oxygens/nitrogens: ``ASP.OD2 = -1``, ``GLU.OE2 = -1``, ``LYS.NZ = +1``, ``ARG.NH2 = +1``
(with an explicit comment there that His is excluded, since it's protonated in the CCD
reference geometry but usually isn't at neutral pH). ``_SALT_BRIDGE_POSITIVE`` /
``_SALT_BRIDGE_NEGATIVE`` below mirror that table exactly (verified against source, not
the general "count every charged oxygen/nitrogen" convention other tools like PLIP use).

Output keys are prefixed ``structural_hbonds``/``structural_saltbridge`` (not plain
``hbonds``/``saltbridge``) to avoid colliding with ``filtering.metrics.METRIC_ALIASES``'s
canonical ``hbonds``/``saltbridge`` entries, which map to *provider-reported* CSV columns
(e.g. boltzgen's own ``plip_hbonds_refolded``) computed by a different method on a
different structure (refolded, not the as-generated one) — a different quantity, not a
duplicate, so it must not share a column name.
"""

from __future__ import annotations

import gzip
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

AMINO_ACIDS = (
    "ALA CYS ASP GLU PHE GLY HIS ILE LYS LEU MET ASN PRO GLN ARG SER THR VAL TRP TYR"
).split()

_THREE_TO_ONE = {
    "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F", "GLY": "G",
    "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L", "MET": "M", "ASN": "N",
    "PRO": "P", "GLN": "Q", "ARG": "R", "SER": "S", "THR": "T", "VAL": "V",
    "TRP": "W", "TYR": "Y",
}

# Kyte & Doolittle (1982) hydropathy scale.
_KYTE_DOOLITTLE = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5,
    "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8,
    "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}

_HYDROPHOBIC_RESIDUES = {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "TRP", "PRO"}

_SALT_BRIDGE_POSITIVE = {("LYS", "NZ"), ("ARG", "NH2")}
_SALT_BRIDGE_NEGATIVE = {("ASP", "OD2"), ("GLU", "OE2")}


def amino_acid_composition_fractions(sequence: str) -> Dict[str, float]:
    """Per-residue-type fraction of ``sequence`` (e.g. ``ALA_fraction``), matching
    boltzgen's ``<AA>_fraction`` filter columns. Sequence-only, no structure needed.
    """
    seq = (sequence or "").upper()
    length = len(seq)
    one_letter_counts = {aa: 0 for aa in _THREE_TO_ONE.values()}
    for ch in seq:
        if ch in one_letter_counts:
            one_letter_counts[ch] += 1
    return {
        f"{three}_fraction": (one_letter_counts[one] / length if length else float("nan"))
        for three, one in _THREE_TO_ONE.items()
    }


def hydrophobicity_score(sequence: str) -> float:
    """Mean Kyte-Doolittle hydropathy across ``sequence``. Sequence-only.

    Not bit-identical to boltzgen's ``design_hydrophobicity`` (which uses a proprietary
    length-weighted penalty table), but the same underlying concept and comparable
    across designs.
    """
    seq = (sequence or "").upper()
    values = [_KYTE_DOOLITTLE[c] for c in seq if c in _KYTE_DOOLITTLE]
    if not values:
        return float("nan")
    return float(np.mean(values))


def _load_atom_array(path: str):
    import biotite.structure.io.pdb as pdb_io
    import biotite.structure.io.pdbx as pdbx_io

    p = Path(path)
    name = p.name.lower()
    is_cif = ".cif" in name
    opener = (lambda: gzip.open(p, "rt")) if name.endswith(".gz") else (lambda: open(p))

    with opener() as fh:
        if is_cif:
            cif_file = pdbx_io.CIFFile.read(fh)
            atoms = pdbx_io.get_structure(cif_file, model=1)
        else:
            pdb_file = pdb_io.PDBFile.read(fh)
            atoms = pdb_io.get_structure(pdb_file, model=1)

    # Strip any pre-existing hydrogens: hydride refuses to add hydrogens to a
    # structure that already has them, and most design-tool outputs are heavy-atom-only
    # anyway.
    return atoms[atoms.element != "H"]


def _residue_first_atom_mask(atom_array) -> np.ndarray:
    """Boolean mask selecting one atom (CA) per residue, for per-residue annotations."""
    return atom_array.atom_name == "CA"


def secondary_structure_fractions(
    structure_path: str, chain_ids: Optional[Sequence[str]] = None
) -> Dict[str, float]:
    """Helix/sheet/loop fraction over ``chain_ids`` (default: all chains) via biotite's
    P-SEA algorithm (CA coordinates + dihedrals only — no DSSP binary, no torch).
    """
    import biotite.structure as struc

    atoms = _load_atom_array(structure_path)
    if chain_ids:
        atoms = atoms[np.isin(atoms.chain_id, list(chain_ids))]
    if len(atoms) == 0:
        return {"helix_fraction": float("nan"), "sheet_fraction": float("nan"), "loop_fraction": float("nan")}

    sse = struc.annotate_sse(atoms)
    total = len(sse)
    if total == 0:
        return {"helix_fraction": float("nan"), "sheet_fraction": float("nan"), "loop_fraction": float("nan")}

    return {
        "helix_fraction": float(np.sum(sse == "a")) / total,
        "sheet_fraction": float(np.sum(sse == "b")) / total,
        "loop_fraction": float(np.sum(sse == "c")) / total,
    }


def delta_sasa(
    structure_path: str, target_chain_ids: Sequence[str], binder_chain_ids: Sequence[str]
) -> Optional[float]:
    """Buried target surface area upon binder complex formation: SASA(target alone) -
    SASA(target within the complex). Positive means the binder occludes target surface.

    Returns ``None`` if either chain set is empty or missing from the structure.
    """
    import biotite.structure as struc

    if not target_chain_ids or not binder_chain_ids:
        return None

    atoms = _load_atom_array(structure_path)
    target_mask = np.isin(atoms.chain_id, list(target_chain_ids))
    binder_mask = np.isin(atoms.chain_id, list(binder_chain_ids))
    if not target_mask.any() or not binder_mask.any():
        return None

    complex_atoms = atoms[target_mask | binder_mask]
    target_only_atoms = atoms[target_mask]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        complex_sasa = struc.sasa(complex_atoms, vdw_radii="Single")
        target_alone_sasa = struc.sasa(target_only_atoms, vdw_radii="Single")

    complex_target_mask = target_mask[target_mask | binder_mask]
    target_area_in_complex = float(np.nansum(complex_sasa[complex_target_mask]))
    target_area_alone = float(np.nansum(target_alone_sasa))

    return target_area_alone - target_area_in_complex


def hydrophobic_patch_area(
    structure_path: str, chain_ids: Optional[Sequence[str]] = None, distance_cutoff: float = 6.0
) -> Optional[float]:
    """Largest contiguous solvent-exposed hydrophobic patch (sum of per-atom SASA within
    a DBSCAN cluster of exposed hydrophobic side-chain carbons), over ``chain_ids``.
    """
    import biotite.structure as struc
    from sklearn.cluster import DBSCAN

    atoms = _load_atom_array(structure_path)
    if chain_ids:
        atoms = atoms[np.isin(atoms.chain_id, list(chain_ids))]
    if len(atoms) == 0:
        return None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        atom_sasa = struc.sasa(atoms, vdw_radii="Single")

    is_hydrophobic = np.isin(atoms.res_name, list(_HYDROPHOBIC_RESIDUES))
    is_carbon = np.char.startswith(atoms.atom_name.astype(str), "C")
    mask = is_hydrophobic & is_carbon & (np.nan_to_num(atom_sasa) > 0)

    coords = atoms.coord[mask]
    sasa_vals = atom_sasa[mask]
    if len(coords) == 0:
        return 0.0

    labels = DBSCAN(eps=distance_cutoff, min_samples=1).fit(coords).labels_
    return float(max(sasa_vals[labels == label].sum() for label in np.unique(labels)))


def hbond_saltbridge_counts(
    structure_path: str, binder_chain_ids: Sequence[str], target_chain_ids: Sequence[str]
) -> Dict[str, int]:
    """Count binder<->target hydrogen bonds and salt bridges at the interface.

    Hydrogen bonds: biotite's geometric H-bond detector (needs explicit hydrogens,
    added via ``hydride`` since most design-tool outputs are heavy-atom-only).
    Salt bridges: distance between oppositely-charged side-chain atoms (Asp/Glu vs
    Lys/Arg, see module docstring), no hydrogens required.
    """
    import biotite.structure as struc
    import hydride

    result = {"structural_hbonds": 0, "structural_saltbridge": 0}
    if not binder_chain_ids or not target_chain_ids:
        return result

    atoms = _load_atom_array(structure_path)
    binder_mask = np.isin(atoms.chain_id, list(binder_chain_ids))
    target_mask = np.isin(atoms.chain_id, list(target_chain_ids))
    if not binder_mask.any() or not target_mask.any():
        return result
    atoms = atoms[binder_mask | target_mask]
    binder_mask = np.isin(atoms.chain_id, list(binder_chain_ids))
    target_mask = np.isin(atoms.chain_id, list(target_chain_ids))

    # --- hydrogen bonds ---
    try:
        h_atoms = atoms.copy()
        h_atoms.bonds = struc.connect_via_residue_names(h_atoms)
        h_atoms.set_annotation("charge", np.zeros(len(h_atoms), dtype=int))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            h_atoms, _ = hydride.add_hydrogen(h_atoms)
            hbonds = struc.hbond(h_atoms)
        donor_chain = h_atoms.chain_id[hbonds[:, 0]]
        acceptor_chain = h_atoms.chain_id[hbonds[:, 2]]
        binder_ids = set(binder_chain_ids)
        target_ids = set(target_chain_ids)
        cross = (
            (np.isin(donor_chain, list(binder_ids)) & np.isin(acceptor_chain, list(target_ids)))
            | (np.isin(donor_chain, list(target_ids)) & np.isin(acceptor_chain, list(binder_ids)))
        )
        result["structural_hbonds"] = int(cross.sum())
    except Exception:
        result["structural_hbonds"] = 0

    # --- salt bridges ---
    charge = np.zeros(len(atoms), dtype=int)
    for i, (res_name, atom_name) in enumerate(zip(atoms.res_name, atoms.atom_name)):
        pair = (str(res_name), str(atom_name))
        if pair in _SALT_BRIDGE_POSITIVE:
            charge[i] = 1
        elif pair in _SALT_BRIDGE_NEGATIVE:
            charge[i] = -1

    pos_idx = np.where(charge > 0)[0]
    neg_idx = np.where(charge < 0)[0]
    if len(pos_idx) and len(neg_idx):
        dists = np.linalg.norm(
            atoms.coord[pos_idx][:, None, :] - atoms.coord[neg_idx][None, :, :], axis=-1
        )
        close_pos, close_neg = np.where((dists > 0.5) & (dists < 5.5))
        pos_chain = atoms.chain_id[pos_idx[close_pos]]
        neg_chain = atoms.chain_id[neg_idx[close_neg]]
        binder_ids = set(binder_chain_ids)
        target_ids = set(target_chain_ids)
        cross = (
            (np.isin(pos_chain, list(binder_ids)) & np.isin(neg_chain, list(target_ids)))
            | (np.isin(pos_chain, list(target_ids)) & np.isin(neg_chain, list(binder_ids)))
        )
        result["structural_saltbridge"] = int(cross.sum())

    return result


def compute_structural_metrics(
    structure_path: str,
    binder_chain_ids: Sequence[str],
    target_chain_ids: Sequence[str],
) -> Dict[str, float]:
    """Convenience wrapper computing every structure-dependent metric in one pass.

    Sequence-only metrics (``amino_acid_composition_fractions``, ``hydrophobicity_score``)
    are intentionally not included here — call them directly against a design's
    ``Sequence`` column without touching the structure file at all.
    """
    metrics: Dict[str, float] = {}
    metrics.update(secondary_structure_fractions(structure_path, binder_chain_ids))
    sasa = delta_sasa(structure_path, target_chain_ids, binder_chain_ids)
    if sasa is not None:
        metrics["delta_sasa"] = sasa
    patch = hydrophobic_patch_area(structure_path, binder_chain_ids)
    if patch is not None:
        metrics["hydrophobic_patch_area"] = patch
    metrics.update(hbond_saltbridge_counts(structure_path, binder_chain_ids, target_chain_ids))
    return metrics
