import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user_optional
from ..auth_providers.base import AuthUser
from ..filtering.schemas import (
    FilteringApplyRequest,
    FilteringApplyResponse,
    FilteringColumnsRequest,
    FilteringColumnsResponse,
    FilteringDiversityRequest,
    FilteringDiversityResponse,
    FilteringPreviewRequest,
    FilteringPreviewResponse,
    FilteringRankRequest,
    FilteringRankResponse,
    FilteringRunRequest,
    FilteringRunResponse,
)
from ..filtering.service import (
    compute_apply,
    compute_available_columns,
    compute_diversity_preview,
    compute_preview,
    compute_rank,
    run_filtering_and_save,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/filtering", tags=["filtering"])


@router.post("/preview", response_model=FilteringPreviewResponse)
async def post_filtering_preview(
    body: FilteringPreviewRequest,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    try:
        return await asyncio.to_thread(compute_preview, body)
    except Exception as e:
        logger.error("filtering preview failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/columns", response_model=FilteringColumnsResponse)
async def post_filtering_columns(
    body: FilteringColumnsRequest,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    try:
        columns = await asyncio.to_thread(compute_available_columns, body.run_ids)
        return FilteringColumnsResponse(columns=columns)
    except Exception as e:
        logger.error("filtering columns failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/apply", response_model=FilteringApplyResponse)
async def post_filtering_apply(
    body: FilteringApplyRequest,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    """Hard filters only, returning the actual matching design keys — for live-narrowing
    the Designs table. Cheap (no ranking/diversity), meant to be called on a debounce
    from the frontend as filters are edited. See plan §7A.2.
    """
    try:
        return await asyncio.to_thread(compute_apply, body)
    except Exception as e:
        logger.error("filtering apply failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/rank", response_model=FilteringRankResponse)
async def post_filtering_rank(
    body: FilteringRankRequest,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    """Hard filters + ranking, no diversity selection, no Saved Set persistence — backs
    the Filtering tab's explicit "Apply Ranking" button (not debounced/live). See plan
    §7A.2.
    """
    try:
        return await asyncio.to_thread(compute_rank, body)
    except Exception as e:
        logger.error("filtering rank failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/diversity", response_model=FilteringDiversityResponse)
async def post_filtering_diversity(
    body: FilteringDiversityRequest,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    """Full filter+rank+diversity pipeline without persisting a Saved Set — backs the
    Filtering tab's explicit "Apply Diversity Filter" button. See plan §7A.2.
    """
    try:
        return await asyncio.to_thread(compute_diversity_preview, body)
    except Exception as e:
        logger.error("filtering diversity failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/run", response_model=FilteringRunResponse)
async def post_filtering_run(
    body: FilteringRunRequest,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    try:
        return await asyncio.to_thread(run_filtering_and_save, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("filtering run failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
