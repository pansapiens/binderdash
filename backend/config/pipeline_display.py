"""Mirror of frontend ``config/pipelineDisplay`` for server-side designs queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Sequence, Set, Tuple


@dataclass(frozen=True)
class MethodBestScoreConfig:
    primary: str
    secondary: Tuple[str, ...]
    higher_is_better: bool


# Must stay aligned with ``frontend/src/config/pipelineDisplay.ts`` METHOD_BEST_SCORE.
METHOD_BEST_SCORE: Dict[str, MethodBestScoreConfig] = {
    "bindcraft": MethodBestScoreConfig(
        primary="Average_i_pTM",
        secondary=("Average_Binder_pLDDT",),
        higher_is_better=True,
    ),
    "rfd": MethodBestScoreConfig(
        primary="pae_interaction",
        secondary=("plddt_binder",),
        higher_is_better=False,
    ),
    "boltzgen": MethodBestScoreConfig(
        primary="design_to_target_iptm",
        secondary=("design_ptm",),
        higher_is_better=True,
    ),
    "rfd3": MethodBestScoreConfig(
        primary="iptm",
        secondary=("rf3_ipsae_min",),
        higher_is_better=True,
    ),
}

# SCORE_FIELD_DEFS order + flags (scoreRangeFilter / globalFilterScore).
_SCORE_RANGE = [
    "pae_interaction",
    "Average_i_pTM",
    "design_to_target_iptm",
    "quality_score",
    "i_pTM",
    "ipTM",
    "iptm",
    "pair_pae",
    "rf3_ipsae_min",
    "rf3_rmsd_target_aligned_binder_rmsd_all",
]

_SCORE_GLOBAL = [
    "pae_interaction",
    "Average_i_pTM",
    "i_pTM",
    "ipTM",
    "Average_Binder_pLDDT",
    "plddt_binder",
]


def score_fields_for_range_filter() -> List[str]:
    return list(_SCORE_RANGE)


def score_fields_for_global_filter() -> List[str]:
    return list(_SCORE_GLOBAL)


DESIGN_TABLE_STATIC_FIELD_KEYS: FrozenSet[str] = frozenset(
    {
        "design_id",
        "project_id",
        "run_name",
        "method",
        "good",
        "tag",
        *_SCORE_RANGE,
        "pLDDT",
        "interaction_pae",
        "min_interation_pae",
        "design_ipsae_min",
        "Average_Binder_pLDDT",
        "plddt_binder",
        "Average_Binder_RMSD",
        "Average_Target_RMSD",
        "binder_aligned_rmsd",
        "pdb_file",
        "run_path",
        "run_id",
        "target_sequence",
    }
)

DESIGN_BUILD_COLUMN_EXTRA_KEYS: Sequence[str] = (
    "Length",
    "length",
    "file_name",
    "source_path",
    "backbone_id",
    "params",
    "min_interaction_pae",
    "design_ptm",
)


def design_build_column_static_keys() -> FrozenSet[str]:
    return frozenset(
        set(DESIGN_TABLE_STATIC_FIELD_KEYS)
        | set(DESIGN_BUILD_COLUMN_EXTRA_KEYS)
        | {x for x in score_fields_for_range_filter()}
    )


# Table headers for known score columns (aligned with SCORE_FIELD_DEFS tableHeader).
SCORE_COLUMN_HEADERS: Dict[str, str] = {
    "pae_interaction": "PAE Interaction",
    "Average_i_pTM": "Average i_pTM",
    "design_to_target_iptm": "Design→Target ipTM",
    "quality_score": "Quality Score",
    "pLDDT": "pLDDT",
    "i_pTM": "i_pTM",
    "ipTM": "ipTM",
    "iptm": "ipTM",
    "pair_pae": "Pair PAE",
    "rf3_ipsae_min": "RF3 ipSAE Min",
    "rf3_rmsd_target_aligned_binder_rmsd_all": "RF3 RMSD (Target-aligned Binder)",
    "interaction_pae": "Interaction PAE",
    "min_interation_pae": "Min interaction PAE",
    "design_ipsae_min": "Design ipSAE min",
    "Average_Binder_pLDDT": "Average Binder pLDDT",
    "plddt_binder": "Binder pLDDT",
    "Average_Binder_RMSD": "Average Binder RMSD",
    "Average_Target_RMSD": "Average Target RMSD",
    "binder_aligned_rmsd": "Binder Aligned RMSD",
}
