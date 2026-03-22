import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user_optional
from ..cache import designs_cache, get_run_metadata, refresh_designs_cache
from ..run_discovery import update_design_good_flag
from ..schemas import DesignGoodUpdate
from ..settings import LocalUser


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/designs", tags=["designs"])


@router.get("")
async def list_designs(
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    try:
        if not designs_cache:
            refresh_designs_cache()
        return {"designs": designs_cache}
    except Exception as e:
        logger.error(f"Error in list_designs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
async def clear_designs(
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    try:
        designs_cache.clear()
        return {"message": "All designs cleared from cache"}
    except Exception as e:
        logger.error(f"Error in clear_designs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/good")
async def patch_design_good(
    body: DesignGoodUpdate,
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    run = get_run_metadata(body.run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        update_design_good_flag(
            run,
            body.design_id,
            body.good,
            source_path=body.source_path,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower() or "no results" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except OSError as e:
        logger.error("Error writing design good flag: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    refresh_designs_cache()
    return {"ok": True, "run_id": body.run_id, "design_id": body.design_id, "good": body.good}
