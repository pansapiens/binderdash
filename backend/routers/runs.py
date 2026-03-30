import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user_optional
from ..cache import get_run_metadata, refresh_designs_cache, run_cache
from ..path_policy import is_allowed_path
from ..run_discovery import find_runs_recursive, load_run_table
from ..schemas import ScanRequest
from ..settings import LocalUser, settings
from ..util.profiling import Timer


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("/scan")
async def scan_runs(
    request: ScanRequest,
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    try:
        _scan_t = Timer(
            logger, "POST /scan", folders=len(request.folders)
        ).start()
        runs: List[Dict[str, Any]] = []
        for folder_path in request.folders:
            if settings.run_base_dirs and not is_allowed_path(
                folder_path, settings.run_base_dirs
            ):
                logger.warning(
                    "Skipping path not within allowed base directories: %s (bases=%s)",
                    folder_path,
                    settings.run_base_dirs,
                )
                continue
            path = Path(folder_path)
            if not path.exists() or not path.is_dir():
                logger.warning(
                    f"Skipping non-existent or non-directory path: {folder_path}"
                )
                continue
            _folder_t = Timer(
                logger, "POST /scan.folder", folder=folder_path
            ).start()
            folder_runs = find_runs_recursive(path)
            _folder_t.log(runs_found=len(folder_runs))
            runs.extend(folder_runs)
            logger.info(f"Found {len(folder_runs)} runs in {folder_path}")

        _pop_t = Timer(logger, "POST /scan.run_cache_populate").start()
        for run in runs:
            run_cache[run["run_id"]] = run
        _pop_t.log()

        _ref_t = Timer(logger, "POST /scan.refresh_designs_cache").start()
        refresh_designs_cache()
        _ref_t.log()

        _scan_t.log(runs=len(runs))
        return {"runs": runs}
    except Exception as e:
        logger.error(f"Error in scan_runs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def merge_runs(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged_runs: Dict[str, Dict[str, Any]] = {}
    for run in runs:
        project_id = run.get("project_id", "unknown")
        run_name = run.get("metadata", {}).get("name", "unknown")
        group_key = f"{project_id}/{run_name}"
        if group_key not in merged_runs:
            merged_runs[group_key] = run.copy()
            merged_runs[group_key]["merged_paths"] = [run["path"]]
            merged_runs[group_key]["merged_pdb_files"] = run.get("pdb_files", []).copy()
        else:
            existing = merged_runs[group_key]
            existing["merged_paths"].append(run["path"])
            existing["merged_pdb_files"].extend(run.get("pdb_files", []))
            existing["metadata"]["merged_count"] = len(existing["merged_paths"])
            existing["metadata"]["total_pdb_count"] = len(existing["merged_pdb_files"])
    result: List[Dict[str, Any]] = []
    for run in merged_runs.values():
        run.pop("merged_pdb_files", None)
        result.append(run)
    return result


@router.get("")
async def list_runs(
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    try:
        all_runs = list(run_cache.values())
        merged = merge_runs(all_runs)
        return {"runs": merged}
    except Exception as e:
        logger.error(f"Error in list_runs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{run_id}")
async def delete_run(
    run_id: str, current_user: Optional[LocalUser] = Depends(get_current_user_optional)
):
    if run_id in run_cache:
        del run_cache[run_id]
        return {"message": "Run removed from cache"}
    else:
        raise HTTPException(status_code=404, detail="Run not found")


@router.delete("")
async def clear_runs(
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    run_cache.clear()
    return {"message": "All runs cleared from cache"}


@router.get("/{run_id}/table")
async def get_run_table(
    run_id: str, current_user: Optional[LocalUser] = Depends(get_current_user_optional)
):
    try:
        run_metadata = get_run_metadata(run_id)
        if not run_metadata:
            raise HTTPException(status_code=404, detail="Run not found")
        df = load_run_table(run_metadata)
        if df is None:
            raise HTTPException(
                status_code=404, detail="Results table not found or could not be loaded"
            )
        df_clean = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        data_records = [
            {col: row[col] for col in df_clean.columns}
            for _, row in df_clean.iterrows()
        ]
        return {
            "columns": df.columns.tolist(),
            "data": data_records,
            "total_rows": len(df),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_run_table: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
