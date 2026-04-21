import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user_optional
from ..config.plot_defaults import default_plot_xy_columns
from ..run_discovery import load_run_table
from ..schemas import PdbTarRequest
from ..auth_providers.base import AuthUser
from ..cache import get_run_metadata


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs/plots", tags=["plots"])


@router.post("/columns")
async def get_plot_columns_multiple(
    request: Dict[str, Any],
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    try:
        run_ids = request.get("run_ids", [])
        if not run_ids:
            raise HTTPException(status_code=400, detail="No run IDs provided")
        all_dfs: List[pd.DataFrame] = []
        methods = set()
        for run_id in run_ids:
            run_metadata = get_run_metadata(run_id)
            if not run_metadata:
                logger.warning(f"Run not found: {run_id}")
                continue
            df = load_run_table(run_metadata)
            if df is None:
                logger.warning(f"Results table not found for run: {run_id}")
                continue
            all_dfs.append(df)
            methods.add(run_metadata.get("method", ""))
        if not all_dfs:
            raise HTTPException(
                status_code=404,
                detail="No valid data found for any of the specified runs",
            )
        combined_df = pd.concat(all_dfs, ignore_index=True)
        numeric_cols = combined_df.select_dtypes(include=[np.number]).columns.tolist()
        most_common_method = max(methods, key=list(methods).count) if methods else ""
        defaults = default_plot_xy_columns(combined_df, most_common_method)
        return {
            "numeric_columns": numeric_cols,
            "defaults": defaults,
            "total_rows": len(combined_df),
            "run_count": len(run_ids),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_plot_columns_multiple: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scatter")
async def get_scatter_plot_multiple(
    request: Dict[str, Any],
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    try:
        run_ids = request.get("run_ids", [])
        x_col = request.get("x_col")
        y_col = request.get("y_col")
        if not run_ids:
            raise HTTPException(status_code=400, detail="No run IDs provided")
        if not x_col or not y_col:
            raise HTTPException(status_code=400, detail="x_col and y_col are required")
        all_dfs: List[pd.DataFrame] = []
        for run_id in run_ids:
            run_metadata = get_run_metadata(run_id)
            if not run_metadata:
                logger.warning(f"Run not found: {run_id}")
                continue
            df = load_run_table(run_metadata)
            if df is None:
                logger.warning(f"Results table not found for run: {run_id}")
                continue
            all_dfs.append(df)
        if not all_dfs:
            raise HTTPException(
                status_code=404,
                detail="No valid data found for any of the specified runs",
            )
        combined_df = pd.concat(all_dfs, ignore_index=True)
        numeric_cols = combined_df.select_dtypes(include=[np.number]).columns.tolist()
        if x_col not in numeric_cols:
            raise HTTPException(
                status_code=400, detail=f"Column '{x_col}' not found or not numeric"
            )
        if y_col not in numeric_cols:
            raise HTTPException(
                status_code=400, detail=f"Column '{y_col}' not found or not numeric"
            )
        clean_df = (
            combined_df[[x_col, y_col]].replace([np.inf, -np.inf], np.nan).dropna()
        )
        if len(clean_df) == 0:
            raise HTTPException(
                status_code=400, detail="No valid data points for selected columns"
            )
        data_values = [
            {c: row[c] for c in clean_df.columns} for _, row in clean_df.iterrows()
        ]
        return {
            "data": data_values,
            "data_points": len(clean_df),
            "total_rows": len(combined_df),
            "run_count": len(run_ids),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_scatter_plot_multiple: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/histogram")
async def get_histogram_plot_multiple(
    request: Dict[str, Any],
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    try:
        run_ids = request.get("run_ids", [])
        col = request.get("col")
        if not run_ids:
            raise HTTPException(status_code=400, detail="No run IDs provided")
        if not col:
            raise HTTPException(status_code=400, detail="col is required")
        all_dfs: List[pd.DataFrame] = []
        for run_id in run_ids:
            run_metadata = get_run_metadata(run_id)
            if not run_metadata:
                logger.warning(f"Run not found: {run_id}")
                continue
            df = load_run_table(run_metadata)
            if df is None:
                logger.warning(f"Results table not found for run: {run_id}")
                continue
            all_dfs.append(df)
        if not all_dfs:
            raise HTTPException(
                status_code=404,
                detail="No valid data found for any of the specified runs",
            )
        combined_df = pd.concat(all_dfs, ignore_index=True)
        numeric_cols = combined_df.select_dtypes(include=[np.number]).columns.tolist()
        if col not in numeric_cols:
            raise HTTPException(
                status_code=400, detail=f"Column '{col}' not found or not numeric"
            )
        clean_df = combined_df[[col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean_df) == 0:
            raise HTTPException(
                status_code=400, detail="No valid data points for selected column"
            )
        data_values = [
            {c: row[c] for c in clean_df.columns} for _, row in clean_df.iterrows()
        ]
        return {
            "data": data_values,
            "data_points": len(clean_df),
            "total_rows": len(combined_df),
            "run_count": len(run_ids),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_histogram_plot_multiple: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
