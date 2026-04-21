"""Score / metric column names as in source TSV/CSV headers (API and logs)."""

from __future__ import annotations

from typing import Dict

SCORE_FIELD_LABELS: Dict[str, str] = {
    "Average_i_pTM": "Average i-pTM",
    "Average_pLDDT": "Average pLDDT",
    "Average_Binder_pLDDT": "Average binder pLDDT",
    "pae_interaction": "PAE interaction",
    "design_to_target_iptm": "Design→Target ipTM",
    "iptm": "ipTM",
    "ipTM": "ipTM",
    "pair_pae": "Pair PAE",
    "rf3_ipsae_min": "RF3 ipSAE min",
    "rf3_rmsd_target_aligned_binder_rmsd_all": "RF3 RMSD (target-aligned binder)",
    "mean_plddt": "Mean pLDDT",
    "plddt": "pLDDT",
    "plddt_binder": "Binder pLDDT",
    "pae_binder": "PAE binder",
}