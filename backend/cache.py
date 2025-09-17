import logging
from typing import Any, Dict, List, Optional

import numpy as np

from .run_discovery import parse_designs_from_run


logger = logging.getLogger(__name__)


run_cache: Dict[str, Dict[str, Any]] = {}
designs_cache: List[Dict[str, Any]] = []


def get_run_metadata(run_id: str) -> Optional[Dict[str, Any]]:
    return run_cache.get(run_id)


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
            has_score = False
            if design.get("method") == "rfd" and "pae_interaction" in design:
                has_score = True
            elif design.get("method") == "bindcraft" and "Average_i_pTM" in design:
                has_score = True
            if has_score:
                designs_with_score.append(design)
            else:
                designs_without_score.append(design)

        def sort_key(design: Dict[str, Any]):
            if design["method"] == "rfd":
                score = design.get("pae_interaction")
                if score is None:
                    return float("inf")
                return score
            else:
                score = design.get("Average_i_pTM")
                if score is None:
                    return float("inf")
                return -score

        designs_with_score.sort(key=sort_key)
        # Replace contents in-place to preserve references
        designs_cache.clear()
        designs_cache.extend(designs_with_score + designs_without_score)
        logger.info(
            f"Refreshed designs cache: {len(designs_cache)} designs from {len(run_cache)} runs"
        )
    except Exception as e:
        logger.error(f"Error refreshing designs cache: {str(e)}")
        designs_cache.clear()
