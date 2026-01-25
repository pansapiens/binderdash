import logging
from typing import Any, Dict, List, Optional, Tuple

from .run_discovery import parse_designs_from_run, run_folder_signatures


logger = logging.getLogger(__name__)


run_cache: Dict[str, Dict[str, Any]] = {}
designs_cache: List[Dict[str, Any]] = []


# Build a lookup of method -> (primary_score_columns, sort_ascending) from signatures
# Uses the first signature found for each method (highest priority)
_method_score_config: Dict[str, Tuple[List[str], bool]] = {}
for sig in sorted(run_folder_signatures, key=lambda s: s.get("priority", 999)):
    method = sig.get("method")
    if method and method not in _method_score_config:
        score_cols = sig.get("primary_score_columns", [])
        sort_asc = sig.get("sort_ascending", True)
        _method_score_config[method] = (score_cols, sort_asc)


def get_run_metadata(run_id: str) -> Optional[Dict[str, Any]]:
    return run_cache.get(run_id)


def _get_design_score(design: Dict[str, Any]) -> Tuple[bool, float]:
    """Get the primary score for a design based on its method's signature config.

    Returns:
        (has_score, sort_value) where sort_value is adjusted for sort direction
    """
    method = design.get("method")
    if not method or method not in _method_score_config:
        return (False, float("inf"))

    score_cols, sort_ascending = _method_score_config[method]

    for col in score_cols:
        score = design.get(col)
        if score is not None:
            try:
                score_val = float(score)
                # For ascending sort, lower is better - return as-is
                # For descending sort, higher is better - negate for sorting
                sort_value = score_val if sort_ascending else -score_val
                return (True, sort_value)
            except (TypeError, ValueError):
                continue

    return (False, float("inf"))


def refresh_designs_cache():
    global designs_cache
    try:
        designs_cache.clear()
        for run in run_cache.values():
            run_designs = parse_designs_from_run(run)
            designs_cache.extend(run_designs)

        designs_with_score: List[Dict[str, Any]] = []
        designs_without_score: List[Dict[str, Any]] = []

        for design in designs_cache:
            has_score, _ = _get_design_score(design)
            if has_score:
                designs_with_score.append(design)
            else:
                designs_without_score.append(design)

        designs_with_score.sort(key=lambda d: _get_design_score(d)[1])

        designs_cache.clear()
        designs_cache.extend(designs_with_score + designs_without_score)
        logger.info(
            f"Refreshed designs cache: {len(designs_cache)} designs from {len(run_cache)} runs"
        )
    except Exception as e:
        logger.error(f"Error refreshing designs cache: {str(e)}")
        designs_cache.clear()
