import asyncio
import csv
import io
import logging
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..auth import get_current_user_optional
from ..auth_providers.base import AuthUser
from ..cache import get_run_metadata
from ..filtering import service
from ..filtering.schemas import (
    SavedSet,
    SavedSetDesignsResponse,
    SavedSetListResponse,
    SavedSetRenameRequest,
)
from ..routers.files import _resolve_structure_path

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


def _build_download_zip_sync(saved_set_id: str) -> Optional[bytes]:
    saved_set = service.get_saved_set(saved_set_id)
    if saved_set is None:
        return None
    designs_resp = service.get_saved_set_designs(saved_set_id)
    rows = designs_resp.designs if designs_resp else []

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        csv_buf = io.StringIO()
        fieldnames = ["design_id", "run_id", "final_rank", "quality_score", "in_diverse_set"]
        extra_metric_keys: List[str] = []
        seen = set(fieldnames)
        for row in rows:
            for k in row.metrics.keys():
                if k not in seen:
                    seen.add(k)
                    extra_metric_keys.append(k)
        writer = csv.DictWriter(csv_buf, fieldnames=fieldnames + extra_metric_keys)
        writer.writeheader()
        for row in rows:
            record: Dict[str, Any] = {
                "design_id": row.design_id,
                "run_id": row.run_id,
                "final_rank": row.final_rank,
                "quality_score": row.quality_score,
                "in_diverse_set": row.in_diverse_set,
            }
            record.update(row.metrics)
            writer.writerow(record)
        zf.writestr("designs.csv", csv_buf.getvalue())

        # Structure files: read directly from each design's original path (no
        # intermediate copy/symlink directory — same lightweight-reference intent as
        # the plan's "use symlinks" answer, just without the extra filesystem step).
        for row in rows:
            pdb_file = row.metrics.get("pdb_file")
            if not pdb_file:
                continue
            run = get_run_metadata(row.run_id)
            if not run:
                continue
            structure_path = _resolve_structure_path(
                run.get("pdb_files", []), Path(str(pdb_file)).name, run.get("method")
            )
            if structure_path is None or not structure_path.is_file():
                continue
            arcname = f"structures/rank{row.final_rank or 0:04d}_{structure_path.name}"
            zf.write(structure_path, arcname=arcname)

    return buf.getvalue()


@router.get("/{saved_set_id}/download")
async def download_saved_set(
    saved_set_id: str,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    data = await asyncio.to_thread(_build_download_zip_sync, saved_set_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Saved set not found")
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="saved_set_{saved_set_id}.zip"'
        },
    )
