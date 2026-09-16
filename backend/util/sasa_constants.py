"""Reference solvent-accessible surface areas, shared by every SASA consumer in the
backend (``tag_placement``, ``filtering.target_contacts``).

The name is historical: the values are Tien et al. 2013's *theoretical* per-residue
maxima (https://doi.org/10.1371/journal.pone.0080635), and the same table (under the
same name) is used by nf-binder-design's ``bin/complex_sasa.py``, so percentages
computed here are directly comparable with that pipeline's TSV output.
"""

from typing import Dict, Optional

TIEN_2023_THEORETICAL: Dict[str, float] = {
    "ALA": 129.0,
    "ARG": 274.0,
    "ASN": 195.0,
    "ASP": 193.0,
    "CYS": 167.0,
    "GLU": 223.0,
    "GLN": 225.0,
    "GLY": 104.0,
    "HIS": 224.0,
    "ILE": 197.0,
    "LEU": 201.0,
    "LYS": 236.0,
    "MET": 224.0,
    "PHE": 240.0,
    "PRO": 159.0,
    "SER": 155.0,
    "THR": 172.0,
    "TRP": 285.0,
    "TYR": 263.0,
    "VAL": 174.0,
}


def percent_of_max_sasa(resname: str, sasa: float) -> Optional[float]:
    """``sasa`` as a percentage of ``resname``'s theoretical maximum, or None for a
    residue type with no reference value (non-standard residues).
    """
    max_sasa = TIEN_2023_THEORETICAL.get(resname.upper())
    if not max_sasa or max_sasa <= 0:
        return None
    return round((sasa / max_sasa) * 100.0, 2)
