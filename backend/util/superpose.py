"""Fetch reference structures and TM-align them onto a design structure (server-side)."""

from __future__ import annotations

import gzip
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Tuple

import numpy as np
import requests
from Bio.PDB import MMCIFParser, PDBParser, Structure
from Bio.PDB.mmcifio import MMCIFIO
from Bio.PDB.Polypeptide import is_aa
from tmtools import tm_align
from tmtools.io import get_residue_data

PDB_ID_PATTERN = re.compile(r"^[0-9][A-Za-z0-9]{3}$")
_MAX_FETCH_BYTES = 50 * 1024 * 1024
_REQUEST_TIMEOUT = 120


def _load_structure_from_path(path: Path) -> Structure.Structure:
    lower = path.name.lower()
    if lower.endswith(".cif.gz"):
        with gzip.open(str(path), "rb") as gz_f:
            data = gz_f.read()
        with tempfile.NamedTemporaryFile(suffix=".cif", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            parser = MMCIFParser(QUIET=True)
            return parser.get_structure("s", tmp_path)
        finally:
            os.unlink(tmp_path)
    if lower.endswith(".pdb.gz"):
        with gzip.open(str(path), "rb") as gz_f:
            data = gz_f.read()
        with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            parser = PDBParser(QUIET=True)
            return parser.get_structure("s", tmp_path)
        finally:
            os.unlink(tmp_path)
    if lower.endswith(".cif"):
        parser = MMCIFParser(QUIET=True)
        return parser.get_structure("s", str(path))
    parser = PDBParser(QUIET=True)
    return parser.get_structure("s", str(path))


def _load_structure_from_bytes(data: bytes, fmt: str) -> Structure.Structure:
    fmt_l = fmt.lower()
    if fmt_l == "mmcif":
        suffix = ".cif"
        parser_f = lambda p: MMCIFParser(QUIET=True).get_structure("s", p)
    else:
        suffix = ".pdb"
        parser_f = lambda p: PDBParser(QUIET=True).get_structure("s", p)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        return parser_f(tmp_path)
    finally:
        os.unlink(tmp_path)


def _longest_protein_chain(structure: Structure.Structure) -> Any:
    best_chain = None
    best_len = 0
    for model in structure:
        for chain in model:
            n = 0
            for residue in chain:
                if residue.id[0] != " ":
                    continue
                if not is_aa(residue, standard=True):
                    continue
                if "CA" in residue.child_dict:
                    n += 1
            if n > best_len:
                best_len = n
                best_chain = chain
    return best_chain


def _chain_coords_and_seq(chain: Any) -> Tuple[np.ndarray, str]:
    if chain is None:
        return np.zeros((0, 3), dtype=np.float64), ""
    return get_residue_data(chain, ignore_hetero=True)


def _apply_tm_to_structure(
    structure: Structure.Structure, u: np.ndarray, t: np.ndarray
) -> None:
    r = np.asarray(u, dtype=np.float64)
    tr = np.asarray(t, dtype=np.float64).reshape(3)
    for model in structure:
        for chain in model:
            for residue in chain:
                for atom in residue:
                    c = atom.coord
                    atom.set_coord(r @ c + tr)


def fetch_reference_structure(source: str) -> Tuple[bytes, str]:
    """Return decompressed structure bytes and format hint ``pdb`` or ``mmcif``."""
    s = source.strip()
    if not s:
        raise ValueError("Empty reference source")

    if PDB_ID_PATTERN.match(s):
        url = f"https://files.rcsb.org/download/{s.upper()}.cif"
        r = requests.get(url, timeout=_REQUEST_TIMEOUT)
        r.raise_for_status()
        if len(r.content) > _MAX_FETCH_BYTES:
            raise ValueError("Downloaded structure exceeds size limit")
        return r.content, "mmcif"

    if s.lower().startswith(("http://", "https://")):
        r = requests.get(s, timeout=_REQUEST_TIMEOUT)
        r.raise_for_status()
        if len(r.content) > _MAX_FETCH_BYTES:
            raise ValueError("Downloaded structure exceeds size limit")
        data = r.content
        lower = s.lower()
        if lower.endswith(".gz"):
            data = gzip.decompress(data)
            lower = lower[:-3]
        if lower.endswith(".cif"):
            return data, "mmcif"
        return data, "pdb"

    raise ValueError(
        "Source must be a 4-character PDB ID or an http(s) URL to a structure file"
    )


def superpose_reference_onto_design(
    ref_bytes: bytes,
    ref_format: str,
    design_path: Path,
) -> Tuple[bytes, dict[str, Any]]:
    """TM-align reference (first structure) onto design; return mmCIF bytes and metrics."""
    design_structure = _load_structure_from_path(design_path)
    ref_structure = _load_structure_from_bytes(ref_bytes, ref_format)

    d_chain = _longest_protein_chain(design_structure)
    r_chain = _longest_protein_chain(ref_structure)
    if d_chain is None or r_chain is None:
        raise ValueError("Could not find protein chains with Cα atoms for alignment")

    coords_d, seq_d = _chain_coords_and_seq(d_chain)
    coords_r, seq_r = _chain_coords_and_seq(r_chain)
    if len(seq_d) < 3 or len(seq_r) < 3:
        raise ValueError("Insufficient residues for TM-align")

    coords_d = np.asarray(coords_d, dtype=np.float64)
    coords_r = np.asarray(coords_r, dtype=np.float64)

    result = tm_align(coords_r, coords_d, seq_r, seq_d)
    u = np.array(result.u, dtype=np.float64)
    t = np.array(result.t, dtype=np.float64)

    ref_copy = ref_structure.copy()
    ref_copy.id = "ref_aligned"
    _apply_tm_to_structure(ref_copy, u, t)

    io = MMCIFIO()
    io.set_structure(ref_copy)
    with tempfile.NamedTemporaryFile(
        suffix=".cif", delete=False, mode="w", encoding="utf-8"
    ) as tmp:
        tmp_path = tmp.name
    try:
        io.save(tmp_path)
        with open(tmp_path, "rb") as f:
            out = f.read()
    finally:
        os.unlink(tmp_path)

    metrics = {
        "tm_score_norm_design": float(result.tm_norm_chain2),
        "tm_score_norm_reference": float(result.tm_norm_chain1),
        "rmsd": float(result.rmsd),
        "aligned_length": sum(1 for c in result.seqM if c == ":"),
    }
    return out, metrics


def superpose_reference_path_onto_design(
    ref_path: Path,
    design_path: Path,
) -> Tuple[bytes, dict[str, Any]]:
    """Load reference from disk (same formats as design) and TM-align onto design."""
    lower = ref_path.name.lower()
    if lower.endswith(".gz"):
        inner = Path(ref_path.stem).suffix.lower()
        fmt = "mmcif" if inner == ".cif" else "pdb"
        with gzip.open(str(ref_path), "rb") as gz_f:
            data = gz_f.read()
    else:
        fmt = "mmcif" if lower.endswith(".cif") else "pdb"
        data = ref_path.read_bytes()
    return superpose_reference_onto_design(data, fmt, design_path)
