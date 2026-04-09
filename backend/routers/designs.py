import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user_optional
from ..cache import (
    designs_cache,
    get_run_metadata,
    patch_design_in_cache,
    refresh_designs_cache,
)
from ..routers.files import _resolve_structure_path
from ..run_discovery import update_design_good_flag, update_design_tag
from ..schemas import (
    DesignGoodUpdate,
    DesignTagUpdate,
    TagMetricsResponse,
    TagMetricsRow,
    TagPlacementRequest,
    TagPlacementResponse,
    TagPlacementResultRow,
)
from ..persistence.factory import get_designs_repository
from ..settings import LocalUser
from ..tag_placement import compute_tag_metrics_for_structure_file


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

    updates: Dict[str, Any] = {"good": body.good}
    if not patch_design_in_cache(
        body.run_id, body.design_id, body.source_path, updates
    ):
        refresh_designs_cache()
    return {"ok": True, "run_id": body.run_id, "design_id": body.design_id, "good": body.good}


@router.patch("/tag")
async def patch_design_tag(
    body: DesignTagUpdate,
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    run = get_run_metadata(body.run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    tag = body.tag
    if tag is not None:
        u = tag.strip().upper()
        if u not in ("N", "C"):
            raise HTTPException(
                status_code=400,
                detail="tag must be 'N', 'C', or omitted to clear",
            )
        tag = u

    try:
        update_design_tag(
            run,
            body.design_id,
            tag,
            source_path=body.source_path,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower() or "no results" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e

    updates: Dict[str, Any] = {"tag": tag}
    if not patch_design_in_cache(
        body.run_id, body.design_id, body.source_path, updates
    ):
        refresh_designs_cache()
    return {"ok": True, "run_id": body.run_id, "design_id": body.design_id, "tag": tag}


def _tag_placement_sync(body: TagPlacementRequest) -> TagPlacementResponse:
    results: list[TagPlacementResultRow] = []
    repo = get_designs_repository()
    tc = (body.target_chains or "").strip()
    df = (body.distant_from or "").strip()
    binder = body.binder_chain.strip() or "B"
    for item in body.designs:
        run = get_run_metadata(item.run_id)
        if not run:
            results.append(
                TagPlacementResultRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    error="Run not found",
                )
            )
            continue
        fn_raw = (item.pdb_file or "").strip()
        if not fn_raw:
            results.append(
                TagPlacementResultRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    error="No structure file for design",
                )
            )
            continue
        fn = Path(fn_raw).name
        pdb_path = _resolve_structure_path(
            run.get("pdb_files", []), fn, run.get("method")
        )
        if pdb_path is None or not pdb_path.is_file():
            results.append(
                TagPlacementResultRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    error="Structure file not found on disk",
                )
            )
            continue
        metrics, err = compute_tag_metrics_for_structure_file(
            Path(pdb_path),
            binder_chain=binder,
            distant_from=body.distant_from,
            target_chains=body.target_chains,
            sasa_probe_radius=body.sasa_probe_radius,
            sasa_n_points=body.sasa_n_points,
            sasa_threshold=body.sasa_threshold,
            more_distant_threshold=body.more_distant_threshold,
        )
        if err:
            results.append(
                TagPlacementResultRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    error=err,
                )
            )
            continue
        tag = metrics.get("predicted_tag") if metrics else None
        try:
            update_design_tag(
                run,
                item.design_id,
                tag,
                source_path=item.source_path,
            )
        except ValueError as e:
            results.append(
                TagPlacementResultRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    error=str(e),
                )
            )
            continue
        patch_design_in_cache(
            item.run_id,
            item.design_id,
            item.source_path,
            {"tag": tag},
        )
        if repo.is_enabled():
            sp = (item.source_path or "").strip()
            if metrics:
                repo.upsert_tag_metrics_cache(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    source_path=sp,
                    structure_filename=fn,
                    binder_chain=binder,
                    target_chains=tc,
                    distant_from=df,
                    sasa_probe_radius=body.sasa_probe_radius,
                    sasa_n_points=body.sasa_n_points,
                    sasa_threshold=body.sasa_threshold,
                    more_distant_threshold=body.more_distant_threshold,
                    metrics=metrics,
                )
        results.append(
            TagPlacementResultRow(
                run_id=item.run_id,
                design_id=item.design_id,
                tag=tag,
            )
        )
    return TagPlacementResponse(results=results)


def _tag_metrics_sync(body: TagPlacementRequest) -> TagMetricsResponse:
    repo = get_designs_repository()
    results: list[TagMetricsRow] = []
    binder = body.binder_chain.strip() or "B"
    tc = (body.target_chains or "").strip()
    df = (body.distant_from or "").strip()
    allow_compute = bool(body.ignore_cache or not body.cache_only)
    use_cache_read = bool(not body.ignore_cache and repo.is_enabled())

    for item in body.designs:
        run = get_run_metadata(item.run_id)
        if not run:
            results.append(
                TagMetricsRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    error="Run not found",
                )
            )
            continue
        fn_raw = (item.pdb_file or "").strip()
        if not fn_raw:
            results.append(
                TagMetricsRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    error="No structure file for design",
                )
            )
            continue
        fn = Path(fn_raw).name
        sp = (item.source_path or "").strip()
        pdb_path = _resolve_structure_path(
            run.get("pdb_files", []), fn, run.get("method")
        )
        if pdb_path is None or not pdb_path.is_file():
            results.append(
                TagMetricsRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    pdb_file=fn,
                    error="Structure file not found on disk",
                )
            )
            continue
        if use_cache_read:
            cached = repo.get_tag_metrics_cache(
                run_id=item.run_id,
                design_id=item.design_id,
                source_path=sp,
                structure_filename=fn,
                binder_chain=binder,
                target_chains=tc,
                distant_from=df,
                sasa_probe_radius=body.sasa_probe_radius,
                sasa_n_points=body.sasa_n_points,
                sasa_threshold=body.sasa_threshold,
                more_distant_threshold=body.more_distant_threshold,
            )
            if cached is not None:
                results.append(
                    TagMetricsRow(
                        run_id=item.run_id,
                        design_id=item.design_id,
                        pdb_file=fn,
                        **cached,
                    )
                )
                continue

        if not allow_compute:
            results.append(
                TagMetricsRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    pdb_file=fn,
                )
            )
            continue

        metrics, err = compute_tag_metrics_for_structure_file(
            Path(pdb_path),
            binder_chain=binder,
            distant_from=body.distant_from,
            target_chains=body.target_chains,
            sasa_probe_radius=body.sasa_probe_radius,
            sasa_n_points=body.sasa_n_points,
            sasa_threshold=body.sasa_threshold,
            more_distant_threshold=body.more_distant_threshold,
        )
        if err:
            results.append(
                TagMetricsRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    pdb_file=fn,
                    error=err,
                )
            )
            continue
        results.append(
            TagMetricsRow(
                run_id=item.run_id,
                design_id=item.design_id,
                pdb_file=fn,
                **metrics,
            )
        )
        if repo.is_enabled():
            repo.upsert_tag_metrics_cache(
                run_id=item.run_id,
                design_id=item.design_id,
                source_path=sp,
                structure_filename=fn,
                binder_chain=binder,
                target_chains=tc,
                distant_from=df,
                sasa_probe_radius=body.sasa_probe_radius,
                sasa_n_points=body.sasa_n_points,
                sasa_threshold=body.sasa_threshold,
                more_distant_threshold=body.more_distant_threshold,
                metrics=metrics,
            )
    return TagMetricsResponse(results=results)


@router.post("/refresh-cache")
async def post_refresh_designs_cache(
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    try:
        refresh_designs_cache()
        return {"ok": True}
    except Exception as e:
        logger.error("refresh-designs-cache failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/tag-metrics", response_model=TagMetricsResponse)
async def post_tag_metrics(
    body: TagPlacementRequest,
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    try:
        return await asyncio.to_thread(_tag_metrics_sync, body)
    except Exception as e:
        logger.error("tag-metrics failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/tag-placement", response_model=TagPlacementResponse)
async def post_tag_placement(
    body: TagPlacementRequest,
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    try:
        out = await asyncio.to_thread(_tag_placement_sync, body)
        if body.refresh_cache_after:
            refresh_designs_cache()
        return out
    except Exception as e:
        logger.error("tag-placement batch failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
