"""Per-target-residue contact and SASA metrics for a binder/target complex.

Answers, for one design, "how close is the binder to target residue A166, and how much
of that residue's surface does it bury". The Filtering tab's Target Contacts section
turns those numbers into hard filters, and the Designs tab's structure viewer colours
the target by their aggregate across a design set.

Follows nf-binder-design's ``bin/complex_sasa.py`` (holo SASA minus apo SASA per target
residue, percentages against the Tien 2013 maxima) so the numbers are directly
comparable with that pipeline's TSV output. That means BioPython's Shrake-Rupley
conventions: its ``ATOMIC_RADII`` and its golden-spiral point mesh, which
``tag_placement`` also establishes here.

Those conventions are kept, but the kernel that applies them is biotite's rather than
BioPython's, which is ~25x faster on the same inputs. ``Bio.PDB.SASA`` builds a fresh
KDTree of the point mesh for *every atom* and does Python set arithmetic over point
indices; biotite takes the radii and the mesh as parameters, so feeding it
``ATOMIC_RADII`` and ``_sasa_sphere`` reproduces the previous numbers (agreement is to
1e-5 A^2, far inside the 0.01 A^2 the records are rounded to) while also accepting an
``atom_filter``. That filter is most of the win: only residues inside ``record_cutoff``
are ever stored, so only their atoms need an ASA, though every atom still has to be
present to occlude them.

Distinct from ``structural_metrics.delta_sasa``, which answers a different question: a
single whole-interface burial total per design, via biotite. Neither supersedes the
other.

Only residues within ``record_cutoff`` (heavy atom to heavy atom) of the binder get a
per-design record. A residue further away has identical holo and apo SASA, so its
ΔSASA is 0 and its bound SASA is its apo SASA, both recoverable from the run's apo
reference map without storing anything per design.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import biotite.structure as struc
import numpy as np
from Bio.PDB import Structure
from Bio.PDB.Polypeptide import is_aa
from Bio.PDB.SASA import ATOMIC_RADII

from ..tag_placement import load_structure
from ..util.sasa_constants import TIEN_2023_THEORETICAL

logger = logging.getLogger(__name__)

ResidueKey = Tuple[str, int, str]

DEFAULT_RECORD_CUTOFF = 12.0
DEFAULT_PROBE_RADIUS = 1.4
DEFAULT_N_POINTS = 100

# Sentinel for "no binder atom anywhere near this residue". Chosen above any distance
# the record cutoff can admit so comparisons against it behave monotonically.
FAR = 999.0


@dataclass(frozen=True)
class TargetResidueInfo:
    """One target residue in a run's catalogue, with its apo (binder-removed) SASA."""

    chain: str
    resseq: int
    icode: str
    resname: str
    aa1: str
    label: str
    sasa_apo: float


@dataclass
class ResidueContact:
    d_ca: float
    d_cb: float
    d_heavy: float
    sasa_bound: float
    # None when the run-level apo reference applies (the usual case); set per design
    # only for runs whose target moves between designs.
    sasa_apo: Optional[float] = None


@dataclass
class TargetContactRecord:
    contacts: Dict[str, ResidueContact] = field(default_factory=dict)
    target_chain_ids: List[str] = field(default_factory=list)
    binder_chain_ids: List[str] = field(default_factory=list)


_THREE_TO_ONE = {
    "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F", "GLY": "G",
    "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L", "MET": "M", "ASN": "N",
    "PRO": "P", "GLN": "Q", "ARG": "R", "SER": "S", "THR": "T", "VAL": "V",
    "TRP": "W", "TYR": "Y",
}


def one_letter(resname: str) -> str:
    return _THREE_TO_ONE.get(resname.upper(), "X")


def residue_label(chain: str, resseq: int, icode: str = " ") -> str:
    """``A166``, or ``A166B`` with an insertion code. Matches complex_sasa.py's
    ``default_residue_label`` for the (overwhelmingly common) blank-icode case.
    """
    suffix = icode.strip()
    return f"{chain}{resseq}{suffix}"


def parse_residue_label(label: str, chain_ids: Set[str]) -> Optional[ResidueKey]:
    """Inverse of ``residue_label``. Chain IDs are matched longest-first, so a
    multi-character chain ID is not mistaken for a shorter one plus digits.
    """
    for chain_id in sorted(chain_ids, key=len, reverse=True):
        if not label.startswith(chain_id):
            continue
        rest = label[len(chain_id):]
        if not rest:
            continue
        icode = " "
        if rest[-1].isalpha():
            icode = rest[-1]
            rest = rest[:-1]
        try:
            return (chain_id, int(rest), icode)
        except ValueError:
            continue
    return None


def residue_key_sort_key(key: ResidueKey) -> Tuple[str, int, str]:
    return (key[0], key[1], key[2])


def structure_chain_ids(structure: Structure.Structure) -> Set[str]:
    return {chain.get_id() for chain in structure[0]}


def iter_target_residues(
    structure: Structure.Structure, binder_chains: Set[str]
) -> Iterable[Tuple[ResidueKey, str]]:
    for chain in structure[0]:
        chain_id = chain.get_id()
        if chain_id in binder_chains:
            continue
        for residue in chain.get_residues():
            if not is_aa(residue, standard=True):
                continue
            hetflag, resseq, icode = residue.get_id()
            if hetflag != " ":
                continue
            yield (chain_id, int(resseq), icode), residue.get_resname().upper()


def target_chain_ids_in_structure(
    structure: Structure.Structure, binder_chains: Set[str]
) -> List[str]:
    chain_ids: List[str] = []
    for chain in structure[0]:
        chain_id = chain.get_id()
        if chain_id in binder_chains:
            continue
        if any(is_aa(residue, standard=True) for residue in chain.get_residues()):
            chain_ids.append(chain_id)
    return sorted(chain_ids)


def _sasa_sphere(n_points: int) -> np.ndarray:
    """The unit-sphere point mesh ``Bio.PDB.SASA.ShrakeRupley`` uses (golden spiral).

    Handed to biotite so its kernel samples exactly the points BioPython's did; with
    ``ATOMIC_RADII`` for the radii, the resulting areas match the previous
    implementation.
    """
    dl = np.pi * (3 - 5 ** 0.5)
    dz = 2.0 / n_points
    k = np.arange(n_points)
    z = (1 - dz / 2) - k * dz
    radius = np.sqrt(np.maximum(0.0, 1 - z * z))
    return np.stack(
        [np.cos(k * dl) * radius, np.sin(k * dl) * radius, z], axis=1
    ).astype(np.float32)


@dataclass
class _AtomTable:
    """A parsed structure flattened into the arrays biotite's SASA kernel wants.

    ``residue_of_atom`` indexes into ``residue_keys``, whose entries are ``None`` for
    anything that is not a standard amino acid residue: those atoms still occlude, but
    never get an ASA of their own.
    """

    array: "struc.AtomArray"
    radii: np.ndarray
    residue_of_atom: np.ndarray
    residue_keys: List[Optional[ResidueKey]]
    is_binder_atom: np.ndarray

    def atoms_in(self, residues: Iterable[ResidueKey]) -> np.ndarray:
        """Boolean mask over atoms belonging to any of ``residues``."""
        wanted = set(residues)
        indices = [
            i for i, key in enumerate(self.residue_keys) if key is not None and key in wanted
        ]
        if not indices:
            return np.zeros(len(self.residue_of_atom), dtype=bool)
        return np.isin(self.residue_of_atom, np.asarray(indices, dtype=np.int64))

    def residue_sasa(
        self,
        wanted: np.ndarray,
        *,
        occluders: Optional[np.ndarray],
        probe_radius: float,
        n_points: int,
    ) -> Dict[ResidueKey, float]:
        """Per-residue ASA for the residues covered by ``wanted``.

        ``occluders`` restricts which atoms are present to block the probe (the apo
        pass drops the binder); ``None`` keeps every atom, which is the holo pass.
        """
        if not wanted.any():
            return {}
        keep = np.ones(len(self.radii), dtype=bool) if occluders is None else occluders
        # `wanted` is expressed over every atom, so narrow it to the retained ones.
        sub_wanted = wanted[keep]
        if not sub_wanted.any():
            return {}
        per_atom = struc.sasa(
            self.array[keep],
            probe_radius=probe_radius,
            atom_filter=sub_wanted,
            ignore_ions=False,
            point_number=n_points,
            point_distr=_sasa_sphere,
            vdw_radii=self.radii[keep],
        )
        totals: Dict[ResidueKey, float] = {}
        for residue_index, area in zip(self.residue_of_atom[keep][sub_wanted], per_atom[sub_wanted]):
            key = self.residue_keys[residue_index]
            if key is not None:
                totals[key] = totals.get(key, 0.0) + float(area)
        return totals


def build_atom_table(
    structure: Structure.Structure, binder_chains: Set[str]
) -> _AtomTable:
    """Flatten ``structure`` once, reusing the atoms BioPython already parsed."""
    coords: List[np.ndarray] = []
    elements: List[str] = []
    radii: List[float] = []
    residue_of_atom: List[int] = []
    is_binder_atom: List[bool] = []
    residue_keys: List[Optional[ResidueKey]] = []

    for chain in structure[0]:
        chain_id = chain.get_id()
        binder = chain_id in binder_chains
        for residue in chain.get_residues():
            hetflag, resseq, icode = residue.get_id()
            standard = is_aa(residue, standard=True) and hetflag == " "
            index = len(residue_keys)
            residue_keys.append((chain_id, int(resseq), icode) if standard else None)
            for atom in residue:
                coords.append(atom.coord)
                elements.append(atom.element)
                # Indexed rather than defaulted: an element BioPython has no radius for
                # used to raise here, and silently guessing one would change results.
                radii.append(ATOMIC_RADII[atom.element])
                residue_of_atom.append(index)
                is_binder_atom.append(binder)

    array = struc.AtomArray(len(coords))
    array.coord = np.asarray(coords, dtype=np.float32).reshape(len(coords), 3)
    array.element = np.asarray(elements)
    return _AtomTable(
        array=array,
        radii=np.asarray(radii, dtype=float),
        residue_of_atom=np.asarray(residue_of_atom, dtype=np.int64),
        residue_keys=residue_keys,
        is_binder_atom=np.asarray(is_binder_atom, dtype=bool),
    )


def residue_min_distances(
    structure: Structure.Structure, binder_chains: Set[str]
) -> Dict[ResidueKey, Tuple[float, float, float]]:
    """Per target residue: (CA-CA, CB-CB, heavy-heavy) minimum distance to the binder.

    CB falls back to CA for glycine and for any residue with no CB atom. Residues with
    no binder atom of the relevant kind get ``FAR``.
    """
    from scipy.spatial import KDTree

    binder_heavy: List[np.ndarray] = []
    binder_ca: List[np.ndarray] = []
    binder_cb: List[np.ndarray] = []
    for chain in structure[0]:
        if chain.get_id() not in binder_chains:
            continue
        for residue in chain.get_residues():
            if not is_aa(residue, standard=True):
                continue
            for atom in residue:
                if atom.element == "H":
                    continue
                binder_heavy.append(atom.coord)
            ca = residue["CA"].coord if "CA" in residue else None
            if ca is not None:
                binder_ca.append(ca)
            cb = residue["CB"].coord if "CB" in residue else ca
            if cb is not None:
                binder_cb.append(cb)

    trees = {}
    for name, coords in (("heavy", binder_heavy), ("ca", binder_ca), ("cb", binder_cb)):
        trees[name] = KDTree(np.asarray(coords, dtype=float)) if coords else None

    def nearest(tree, coord: Optional[np.ndarray]) -> float:
        if tree is None or coord is None:
            return FAR
        return float(tree.query(np.asarray(coord, dtype=float))[0])

    out: Dict[ResidueKey, Tuple[float, float, float]] = {}
    for chain in structure[0]:
        chain_id = chain.get_id()
        if chain_id in binder_chains:
            continue
        for residue in chain.get_residues():
            if not is_aa(residue, standard=True):
                continue
            hetflag, resseq, icode = residue.get_id()
            if hetflag != " ":
                continue
            ca = residue["CA"].coord if "CA" in residue else None
            cb = residue["CB"].coord if "CB" in residue else ca
            heavy = np.asarray(
                [a.coord for a in residue if a.element != "H"], dtype=float
            )
            d_heavy = FAR
            if trees["heavy"] is not None and len(heavy):
                d_heavy = float(trees["heavy"].query(heavy)[0].min())
            out[(chain_id, int(resseq), icode)] = (
                nearest(trees["ca"], ca),
                nearest(trees["cb"], cb),
                d_heavy,
            )
    return out


def compute_reference_residues(
    structure_path: str,
    binder_chain_ids: Sequence[str],
    *,
    probe_radius: float = DEFAULT_PROBE_RADIUS,
    n_points: int = DEFAULT_N_POINTS,
) -> List[TargetResidueInfo]:
    """The run's target residue catalogue plus each residue's apo SASA, from one
    representative structure. Backs the residue picker and fills in residues that fall
    outside a design's record cutoff.
    """
    binder_chains = set(binder_chain_ids)
    structure = load_structure(Path(structure_path))
    resnames = dict(iter_target_residues(structure, binder_chains))
    # Every target residue is catalogued here, not just the ones near the binder, since
    # this map is what fills in residues outside a design's record cutoff.
    table = build_atom_table(structure, binder_chains)
    apo_sasa = table.residue_sasa(
        table.atoms_in(resnames),
        occluders=~table.is_binder_atom,
        probe_radius=probe_radius,
        n_points=n_points,
    )

    out: List[TargetResidueInfo] = []
    for key in sorted(resnames, key=residue_key_sort_key):
        chain, resseq, icode = key
        resname = resnames[key]
        out.append(
            TargetResidueInfo(
                chain=chain,
                resseq=resseq,
                icode=icode,
                resname=resname,
                aa1=one_letter(resname),
                label=residue_label(chain, resseq, icode),
                sasa_apo=round(apo_sasa.get(key, 0.0), 2),
            )
        )
    return out


def target_backbone_signature(
    structure_path: str, binder_chain_ids: Sequence[str]
) -> str:
    """Hash of the target's CA coordinates, for detecting a target that moves between
    designs (which invalidates the shared apo-SASA reference).
    """
    import hashlib

    binder_chains = set(binder_chain_ids)
    structure = load_structure(Path(structure_path))
    coords: List[np.ndarray] = []
    for chain in structure[0]:
        if chain.get_id() in binder_chains:
            continue
        for residue in chain.get_residues():
            if is_aa(residue, standard=True) and "CA" in residue:
                coords.append(residue["CA"].coord)
    if not coords:
        return ""
    arr = np.round(np.asarray(coords, dtype=float), 2)
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def target_sequence_key(structure_path: str, binder_chain_ids: Sequence[str]) -> str:
    """Stable identity for "which target is this", from the target chains' sequences.

    Runs against the same target share a key (and so a residue catalogue) regardless of
    run name or method; two constructs differing by a tag or truncation do not, which is
    what we want, since their residue numbering differs too.

    Chain IDs are deliberately excluded from the hash: the same target is routinely
    chain A in one pipeline's output and chain B in another's (BindCraft vs RFdiffusion
    in the bundled PD-L1 example), and treating those as different targets would force
    the user to write the same conditions twice. Residue labels are reconciled across
    the differing chain letters at filter time — see RunContext.resolve_label.
    """
    import hashlib

    binder_chains = set(binder_chain_ids)
    structure = load_structure(Path(structure_path))
    by_chain: Dict[str, List[str]] = {}
    for key, resname in iter_target_residues(structure, binder_chains):
        by_chain.setdefault(key[0], []).append(one_letter(resname))
    if not by_chain:
        return ""
    joined = "|".join("".join(by_chain[c]) for c in sorted(by_chain))
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


def compute_target_contacts(
    structure_path: str,
    binder_chain_ids: Sequence[str],
    *,
    record_cutoff: float = DEFAULT_RECORD_CUTOFF,
    probe_radius: float = DEFAULT_PROBE_RADIUS,
    n_points: int = DEFAULT_N_POINTS,
    apo_sasa_by_label: Optional[Dict[str, float]] = None,
) -> TargetContactRecord:
    """Per-residue contacts for one design.

    ``apo_sasa_by_label`` supplies the run's shared apo reference; when given, the apo
    SASA pass is skipped (roughly halving the cost) and the stored records carry no
    per-design apo value.
    """
    binder_chains = set(binder_chain_ids)
    structure = load_structure(Path(structure_path))
    present_chains = structure_chain_ids(structure)
    binder_present = sorted(binder_chains & present_chains)
    if not binder_present:
        raise ValueError(
            f"None of the binder chains {sorted(binder_chains)} are present in "
            f"{Path(structure_path).name}"
        )

    resnames = dict(iter_target_residues(structure, binder_chains))
    distances = residue_min_distances(structure, binder_chains)

    # Only these residues are stored, so only these need an ASA. Everything else in the
    # structure still occludes them, it just never gets an area of its own.
    recorded = [
        key
        for key in sorted(resnames, key=residue_key_sort_key)
        if distances.get(key, (FAR, FAR, FAR))[2] <= record_cutoff
    ]

    holo_sasa: Dict[ResidueKey, float] = {}
    apo_sasa: Optional[Dict[ResidueKey, float]] = None
    if recorded:
        table = build_atom_table(structure, binder_chains)
        wanted = table.atoms_in(recorded)
        holo_sasa = table.residue_sasa(
            wanted, occluders=None, probe_radius=probe_radius, n_points=n_points
        )
        if apo_sasa_by_label is None:
            apo_sasa = table.residue_sasa(
                wanted,
                occluders=~table.is_binder_atom,
                probe_radius=probe_radius,
                n_points=n_points,
            )

    contacts: Dict[str, ResidueContact] = {}
    for key in recorded:
        d_ca, d_cb, d_heavy = distances.get(key, (FAR, FAR, FAR))
        label = residue_label(*key)
        contacts[label] = ResidueContact(
            d_ca=round(d_ca, 2),
            d_cb=round(d_cb, 2),
            d_heavy=round(d_heavy, 2),
            sasa_bound=round(holo_sasa.get(key, 0.0), 2),
            sasa_apo=(round(apo_sasa[key], 2) if apo_sasa is not None and key in apo_sasa else None),
        )

    return TargetContactRecord(
        contacts=contacts,
        target_chain_ids=target_chain_ids_in_structure(structure, binder_chains),
        binder_chain_ids=binder_present,
    )


def delta_sasa_percent(resname: str, delta_angstrom: float) -> Optional[float]:
    """ΔSASA as a percentage of the residue's theoretical maximum, matching
    complex_sasa.py's ``delta_percent``. The maximum, rather than the apo value, keeps
    the number comparable across residues and identical to that pipeline's column.
    """
    max_sasa = TIEN_2023_THEORETICAL.get(resname.upper())
    if not max_sasa or max_sasa <= 0:
        return None
    return round((delta_angstrom / max_sasa) * 100.0, 2)


def _compute_one(args: Tuple) -> Tuple[str, Optional[Dict], Optional[str]]:
    """ProcessPoolExecutor worker. Returns (task_id, serialised record, error)."""
    task_id, structure_path, binder_chain_ids, record_cutoff, probe_radius, n_points, apo = args
    try:
        record = compute_target_contacts(
            structure_path,
            binder_chain_ids,
            record_cutoff=record_cutoff,
            probe_radius=probe_radius,
            n_points=n_points,
            apo_sasa_by_label=apo,
        )
    except Exception as e:  # noqa: BLE001 - reported per design, not fatal to the batch
        return task_id, None, str(e)
    return task_id, serialise_record(record), None


def serialise_record(record: TargetContactRecord) -> Dict:
    """Compact JSON form: positional arrays per residue rather than named fields, since
    this is stored once per design and the field names would dominate the payload.
    """
    return {
        "v": 1,
        "target_chains": record.target_chain_ids,
        "binder_chains": record.binder_chain_ids,
        "residues": {
            label: [c.d_ca, c.d_cb, c.d_heavy, c.sasa_bound, c.sasa_apo]
            for label, c in record.contacts.items()
        },
    }


def deserialise_record(payload: Dict) -> TargetContactRecord:
    contacts = {
        label: ResidueContact(
            d_ca=values[0],
            d_cb=values[1],
            d_heavy=values[2],
            sasa_bound=values[3],
            sasa_apo=values[4] if len(values) > 4 else None,
        )
        for label, values in (payload.get("residues") or {}).items()
    }
    return TargetContactRecord(
        contacts=contacts,
        target_chain_ids=payload.get("target_chains") or [],
        binder_chain_ids=payload.get("binder_chains") or [],
    )


def compute_many(
    tasks: Sequence[Tuple[str, str, Sequence[str], Optional[Dict[str, float]]]],
    *,
    record_cutoff: float = DEFAULT_RECORD_CUTOFF,
    probe_radius: float = DEFAULT_PROBE_RADIUS,
    n_points: int = DEFAULT_N_POINTS,
    max_workers: Optional[int] = None,
) -> Dict[str, Tuple[Optional[Dict], Optional[str]]]:
    """Compute records for many designs in parallel.

    ``tasks`` are ``(task_id, structure_path, binder_chain_ids, apo_sasa_by_label)``.
    Returns ``{task_id: (serialised record | None, error | None)}``.
    """
    if not tasks:
        return {}

    payloads = [
        (task_id, path, list(binder), record_cutoff, probe_radius, n_points, apo)
        for task_id, path, binder, apo in tasks
    ]
    workers = max_workers if max_workers is not None else (os.cpu_count() or 1)
    workers = max(1, min(workers, len(payloads)))

    results: Dict[str, Tuple[Optional[Dict], Optional[str]]] = {}
    if workers == 1:
        for payload in payloads:
            task_id, record, error = _compute_one(payload)
            results[task_id] = (record, error)
        return results

    with ProcessPoolExecutor(max_workers=workers) as executor:
        for task_id, record, error in executor.map(_compute_one, payloads):
            results[task_id] = (record, error)
    return results
