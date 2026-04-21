import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from .config.run_signatures import run_folder_signatures
from .run_discovery import parse_designs_from_run
from .util.profiling import Timer


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


def hydrate_caches_from_repository() -> None:
    global run_cache, designs_cache
    from .persistence.factory import get_designs_repository

    repo = get_designs_repository()
    run_cache.clear()
    designs_cache.clear()
    if not repo.is_enabled():
        logger.info("hydrate_caches_from_repository: persistence disabled, caches empty")
        return
    for row in repo.list_run_records():
        rj = row["run_json"]
        run_dict = json.loads(rj) if isinstance(rj, str) else rj
        rid = run_dict.get("run_id") or row["run_id"]
        run_dict["run_id"] = rid
        run_cache[rid] = run_dict
    refresh_designs_cache()
    logger.info(
        "Hydrated from database: %s runs, %s designs",
        len(run_cache),
        len(designs_cache),
    )


def patch_design_in_cache(
    run_id: str,
    design_id: str,
    source_path: Optional[str],
    updates: Dict[str, Any],
) -> bool:
    sp = (source_path or "").strip()
    for d in designs_cache:
        if str(d.get("run_id")) != str(run_id):
            continue
        if str(d.get("design_id")) != str(design_id):
            continue
        dsp = str(d.get("source_path") or "").strip()
        if dsp != sp:
            continue
        for k, v in updates.items():
            if v is None and k in ("tag", "good", "binder_chain"):
                d.pop(k, None)
            else:
                d[k] = v
        return True
    return False


def refresh_designs_cache():
    global designs_cache
    try:
        _refresh_t = Timer(logger, "refresh_designs_cache").start()
        designs_cache.clear()
        _parse_t = Timer(logger, "refresh_designs_cache.parse").start()
        from .persistence.factory import get_designs_repository

        repo = get_designs_repository()
        rows: List[Dict[str, Any]] = []
        if repo.is_enabled():
            allowed = set(run_cache.keys())
            rows = [
                d
                for d in repo.list_all_design_dicts()
                if str(d.get("run_id")) in allowed
            ]
        else:
            for run in run_cache.values():
                rows.extend(parse_designs_from_run(run))
        _parse_t.log()

        designs_with_score: List[Dict[str, Any]] = []
        designs_without_score: List[Dict[str, Any]] = []

        for design in rows:
            has_score, _ = _get_design_score(design)
            if has_score:
                designs_with_score.append(design)
            else:
                designs_without_score.append(design)

        _sort_t = Timer(logger, "refresh_designs_cache.sort").start()
        designs_with_score.sort(key=lambda d: _get_design_score(d)[1])
        designs_cache.clear()
        designs_cache.extend(designs_with_score + designs_without_score)
        _sort_t.log()

        logger.info(
            f"Refreshed designs cache: {len(designs_cache)} designs from {len(run_cache)} runs"
        )
        _refresh_t.log(runs=len(run_cache), designs=len(designs_cache))
    except Exception as e:
        logger.error(f"Error refreshing designs cache: {str(e)}")
        designs_cache.clear()
