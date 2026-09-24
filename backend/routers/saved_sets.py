import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user_optional
from ..auth_providers.base import AuthUser
from ..bundles import BundleCapsError, check_caps, spec_from_saved_set, write_bundle
from ..filtering import service
from ..filtering.schemas import (
    SavedSet,
    SavedSetDesignsResponse,
    SavedSetListResponse,
    SavedSetRenameRequest,
)
from ..routers.bundles import bundle_response, current_caps

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/saved-sets", tags=["saved-sets"])


@router.get("", response_model=SavedSetListResponse)
async def list_saved_sets(
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    try:
        return await asyncio.to_thread(service.list_saved_sets)
    except Exception as e:
        logger.error("list saved sets failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{saved_set_id}", response_model=SavedSet)
async def get_saved_set(
    saved_set_id: str,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    result = await asyncio.to_thread(service.get_saved_set, saved_set_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Saved set not found")
    return result


@router.get("/{saved_set_id}/designs", response_model=SavedSetDesignsResponse)
async def get_saved_set_designs(
    saved_set_id: str,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    result = await asyncio.to_thread(service.get_saved_set_designs, saved_set_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Saved set not found")
    return result


@router.delete("/{saved_set_id}")
async def delete_saved_set(
    saved_set_id: str,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    deleted = await asyncio.to_thread(service.delete_saved_set, saved_set_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved set not found")
    return {"ok": True}


@router.patch("/{saved_set_id}", response_model=SavedSet)
async def rename_saved_set(
    saved_set_id: str,
    body: SavedSetRenameRequest,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    """Sets are immutable snapshots otherwise (see plan §7A.4) — rename is the only
    allowed mutation. "Reapply filters" (frontend) builds a new Set instead of
    re-running this one in place.
    """
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name must not be empty")
    renamed = await asyncio.to_thread(service.rename_saved_set, saved_set_id, name)
    if not renamed:
        raise HTTPException(status_code=404, detail="Saved set not found")
    result = await asyncio.to_thread(service.get_saved_set, saved_set_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Saved set not found")
    return result


def _build_bundle_sync(saved_set_id: str):
    """Build the saved set's bundle, or None if the set is gone.

    Deliberately the same builder the live Designs download uses, so the two cannot
    drift: only row production differs (a set exports its frozen metrics snapshot rather
    than re-reading the design cache).
    """
    spec = spec_from_saved_set(saved_set_id)
    if spec is None:
        return None
    check_caps(spec, current_caps())
    return write_bundle(spec)


@router.get("/{saved_set_id}/download")
async def download_saved_set(
    saved_set_id: str,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    try:
        built = await asyncio.to_thread(_build_bundle_sync, saved_set_id)
    except BundleCapsError as e:
        raise HTTPException(
            status_code=413, detail={"message": str(e), "estimate": e.estimate.model_dump()}
        ) from e
    if built is None:
        raise HTTPException(status_code=404, detail="Saved set not found")
    return bundle_response(built)
