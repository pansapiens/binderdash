import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user_optional
from ..cache import designs_cache, refresh_designs_cache
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
