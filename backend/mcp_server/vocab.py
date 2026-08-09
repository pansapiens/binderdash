"""Canonical metric vocabulary for the MCP surface: names, directions, presets.

The REST API exposes raw per-method column names and leaves the caller to know that
`pae_interaction` is lower-is-better while `Average_i_pTM` is higher-is-better. Getting
that backwards produces a plausible, confidently wrong ranking, so direction lives here
next to the name and every tool that sorts consults it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..filtering.metrics import METRIC_ALIASES

# canonical metric -> (higher_is_better, one-line meaning).
METRIC_DIRECTIONS: Dict[str, tuple] = {
    "iptm": (True, "Interface pTM: predicted accuracy of the binder-target interface, 0-1."),
    "ptm": (True, "pTM: predicted accuracy of the whole complex, 0-1."),
    "rmsd": (False, "Backbone RMSD of the refolded/predicted binder against the design, Angstrom."),
    "pae_interaction": (False, "Predicted aligned error across the interface, Angstrom."),
    "hbonds": (True, "Hydrogen bonds across the interface."),
    "saltbridge": (True, "Salt bridges across the interface."),
    "delta_sasa": (True, "Interface area buried on complex formation, Angstrom^2."),
}

# Metrics that are identifiers/sequences rather than scores — rankable never.
NON_SCORE_METRICS = {"sequence", "design_id"}

RANKING_PRESETS: Dict[str, Dict[str, Any]] = {
    "iptm": {
        "label": "iptm only (default)",
        "description": "Rank by interface pTM alone. The Filtering tab's fresh-state default.",
        "metrics": [{"column": "iptm", "weight": 1, "higher_is_better": True}],
    },
    # BoltzGen's own Filter task default recipe (design_to_target_iptm 1, design_ptm 1,
    # neg_min_design_to_target_pae 1, plip_hbonds_refolded 2, plip_saltbridge_refolded 2,
    # delta_sasa_refolded 2), expressed in canonical names so it also applies to runs
    # from other methods that have an equivalent metric.
    "boltzgen": {
        "label": "BoltzGen defaults",
        "description": "BoltzGen's own multi-metric recipe, in cross-method canonical names.",
        "metrics": [
            {"column": "iptm", "weight": 1, "higher_is_better": True},
            {"column": "ptm", "weight": 1, "higher_is_better": True},
            {"column": "pae_interaction", "weight": 1, "higher_is_better": False},
            {"column": "hbonds", "weight": 2, "higher_is_better": True},
            {"column": "saltbridge", "weight": 2, "higher_is_better": True},
            {"column": "delta_sasa", "weight": 2, "higher_is_better": True},
        ],
    },
}


def is_canonical(name: str) -> bool:
    return name in METRIC_ALIASES


def higher_is_better(canonical: str) -> Optional[bool]:
    """Known sort direction for a canonical metric, or ``None`` for a raw column."""
    entry = METRIC_DIRECTIONS.get(canonical)
    return entry[0] if entry else None


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
