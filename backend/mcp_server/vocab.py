"""Canonical metric vocabulary for the MCP surface: names, directions, presets.

Direction knowledge lives in ``filtering.metrics`` (next to ``METRIC_ALIASES``) so
REST ColumnInfo and the Filtering UI share the same source. This module re-exports
that vocabulary and holds MCP ranking presets / catalogue helpers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..filtering.metrics import (
    METRIC_ALIASES,
    METRIC_DIRECTIONS,
    NON_SCORE_METRICS,
    higher_is_better,
)


def _preset_metric(column: str, weight: float = 1) -> Dict[str, Any]:
    direction = higher_is_better(column)
    if direction is None:
        raise ValueError(f"Ranking preset metric {column!r} has no known direction")
    return {"column": column, "weight": weight, "higher_is_better": direction}


RANKING_PRESETS: Dict[str, Dict[str, Any]] = {
    "iptm_plddt_rmsd": {
        "label": "ipTM + Binder pLDDT + Binder RMSD",
        "description": (
            "Simple ranking: ipTM primary, binder pLDDT secondary, binder RMSD tertiary. "
            "The Filtering tab's fresh-state default (ranking_mode=simple)."
        ),
        "ranking_mode": "simple",
        "metrics": [
            _preset_metric("iptm"),
            _preset_metric("binder_plddt"),
            _preset_metric("rmsd"),
        ],
    },
    "ipsae_plddt_rmsd": {
        "label": "ipSAE + Binder pLDDT + Binder RMSD",
        "description": (
            "Simple ranking: ipSAE primary, binder pLDDT secondary, binder RMSD tertiary. "
            "ipSAE resolves to BoltzGen design_ipsae_min and RFdiffusion3 rf3_ipsae_min; "
            "BindCraft and plain RFdiffusion have no equivalent."
        ),
        "ranking_mode": "simple",
        "metrics": [
            _preset_metric("ipsae"),
            _preset_metric("binder_plddt"),
            _preset_metric("rmsd"),
        ],
    },
    "iptm": {
        "label": "iptm only",
        "description": "Rank by interface pTM alone.",
        "ranking_mode": "simple",
        "metrics": [_preset_metric("iptm")],
    },
    # BoltzGen's own Filter task default recipe (design_to_target_iptm 1, design_ptm 1,
    # neg_min_design_to_target_pae 1, plip_hbonds_refolded 2, plip_saltbridge_refolded 2,
    # delta_sasa_refolded 2), expressed in canonical names so it also applies to runs
    # from other methods that have an equivalent metric.
    "boltzgen": {
        "label": "BoltzGen defaults",
        "description": (
            "BoltzGen's own multi-metric recipe, in cross-method canonical names. "
            "Uses ranking_mode=worst_rank (inverse-importance weights)."
        ),
        "ranking_mode": "worst_rank",
        "metrics": [
            _preset_metric("iptm"),
            _preset_metric("ptm"),
            _preset_metric("pae_interaction"),
            _preset_metric("hbonds", weight=2),
            _preset_metric("saltbridge", weight=2),
            _preset_metric("delta_sasa", weight=2),
        ],
    },
}


def is_canonical(name: str) -> bool:
    return name in METRIC_ALIASES


def metric_catalogue() -> List[Dict[str, Any]]:
    """Every canonical metric with its direction, meaning, and per-method raw columns."""
    out: List[Dict[str, Any]] = []
    for canonical, per_method in METRIC_ALIASES.items():
        if canonical in NON_SCORE_METRICS:
            continue
        direction, meaning = METRIC_DIRECTIONS.get(canonical, (None, ""))
        out.append(
            {
                "canonical": canonical,
                "higher_is_better": direction,
                "meaning": meaning,
                "raw_columns": {
                    method: raw for method, raw in per_method.items() if raw is not None
                },
            }
        )
    return out


def primary_score_for_method(method: str) -> Optional[Dict[str, Any]]:
    """The method's own default sort column and direction, from its run signature.

    This is the same configuration the Designs table sorts by, so "sort by primary
    score" over MCP and the default order in the web UI agree.
    """
    from ..cache import _method_score_config

    config = _method_score_config.get(method)
    if not config:
        return None
    columns, sort_ascending = config
    if not columns:
        return None
    return {
        "columns": list(columns),
        "higher_is_better": not sort_ascending,
    }
