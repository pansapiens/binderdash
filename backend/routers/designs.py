import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user_optional
from ..cache import (
    designs_cache,
    get_run_metadata,
    patch_design_in_cache,
    refresh_designs_cache,
)
from ..routers.files import _resolve_structure_path
from ..run_discovery import (
    update_design_good_flag,
    update_design_sequence_and_binder_chain,
    update_design_tag,
)
from ..util.pdb_to_fasta import get_chain_sequences
from ..schemas import (
    DesignGoodUpdate,
    DesignTagUpdate,
    SequenceExtractRequest,
    SequenceExtractResponse,
    SequenceExtractResultRow,
    ShortNameBulkRequest,
    ShortNameBulkResponse,
    TagMetricsResponse,
    TagMetricsRow,
    TagPlacementRequest,
    TagPlacementResponse,
    TagPlacementResultRow,
)
from ..persistence.factory import get_designs_repository
from ..auth_providers.base import AuthUser
from ..tag_placement import compute_tag_metrics_for_structure_file


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/designs", tags=["designs"])


@router.get("")
async def list_designs(
    run_ids: Optional[str] = Query(
        None,
        description="Comma-separated run_id values to filter designs; omit for all designs.",
    ),
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    try:
        if not designs_cache:
            refresh_designs_cache()
        if not run_ids or not run_ids.strip():
            return {"designs": designs_cache}
        allowed = {rid.strip() for rid in run_ids.split(",") if rid.strip()}
        if not allowed:
            return {"designs": designs_cache}
        filtered = [
            d for d in designs_cache if str(d.get("run_id")) in allowed
        ]
        return {"designs": filtered}
    except Exception as e:
        logger.error(f"Error in list_designs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
async def clear_designs(
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
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
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
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
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
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


@router.post("/short-names")
async def post_short_names(
    body: ShortNameBulkRequest,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    """Bulk-persist Prepare Sequences short names (Twist) without changing design_id."""
    repo = get_designs_repository()
    items = [u.model_dump() for u in body.updates]
    count = 0
    if repo.is_enabled():
        count = repo.update_design_short_names_bulk(items)
        if body.refresh_cache_after:
            refresh_designs_cache()
        else:
            for u in body.updates:
                patch_design_in_cache(
                    u.run_id,
                    u.design_id,
                    u.source_path,
                    {"short_name": u.short_name},
                )
    else:
        for u in body.updates:
            patch_design_in_cache(
                u.run_id,
                u.design_id,
                u.source_path,
                {"short_name": u.short_name},
            )
    return ShortNameBulkResponse(updated=count)


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
        seq_val: Optional[str] = None
        if metrics and isinstance(metrics.get("sequence"), str):
            seq_val = metrics["sequence"]
        try:
            update_design_sequence_and_binder_chain(
                run,
                item.design_id,
                source_path=item.source_path,
                sequence=seq_val,
                binder_chain=binder,
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
        cache_updates: Dict[str, Any] = {"tag": tag}
        if seq_val is not None:
            cache_updates["Sequence"] = seq_val
        cache_updates["binder_chain"] = binder
        patch_design_in_cache(
            item.run_id,
            item.design_id,
            item.source_path,
            cache_updates,
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


def _sequences_extract_sync(body: SequenceExtractRequest) -> SequenceExtractResponse:
    results: list[SequenceExtractResultRow] = []
    repo = get_designs_repository()
    if not repo.is_enabled():
        for item in body.designs:
            results.append(
                SequenceExtractResultRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    error="DATABASE is not configured; cannot persist sequences",
                )
            )
        return SequenceExtractResponse(results=results)

    for item in body.designs:
        run = get_run_metadata(item.run_id)
        if not run:
            results.append(
                SequenceExtractResultRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    error="Run not found",
                )
            )
            continue
        fn_raw = (item.pdb_file or "").strip()
        if not fn_raw:
            results.append(
                SequenceExtractResultRow(
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
                SequenceExtractResultRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    error="Structure file not found on disk",
                )
            )
            continue
        chain = (item.chain or "").strip() or "B"
        try:
            seqs = get_chain_sequences(str(pdb_path), [chain])
        except Exception as e:
            results.append(
                SequenceExtractResultRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    error=str(e),
                )
            )
            continue
        seq = seqs.get(chain)
        if not seq:
            results.append(
                SequenceExtractResultRow(
                    run_id=item.run_id,
                    design_id=item.design_id,
                    error=f"Chain {chain!r} not found or has no residues",
                )
            )
            continue
        try:
            update_design_sequence_and_binder_chain(
                run,
                item.design_id,
                source_path=item.source_path,
                sequence=seq,
                binder_chain=chain,
            )
        except ValueError as e:
            results.append(
                SequenceExtractResultRow(
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
            {"Sequence": seq, "binder_chain": chain},
        )
        results.append(
            SequenceExtractResultRow(
                run_id=item.run_id,
                design_id=item.design_id,
                sequence=seq,
            )
        )
    return SequenceExtractResponse(results=results)


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
            seq_m: Optional[str] = None
            if isinstance(metrics.get("sequence"), str):
                seq_m = metrics["sequence"]
            try:
                update_design_sequence_and_binder_chain(
                    run,
                    item.design_id,
                    source_path=item.source_path,
                    sequence=seq_m,
                    binder_chain=binder,
                )
            except ValueError:
                pass
            else:
                mu: Dict[str, Any] = {"binder_chain": binder}
                if seq_m is not None:
                    mu["Sequence"] = seq_m
                patch_design_in_cache(
                    item.run_id,
                    item.design_id,
                    item.source_path,
                    mu,
                )
    return TagMetricsResponse(results=results)


@router.post("/refresh-cache")
async def post_refresh_designs_cache(
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
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
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    try:
        return await asyncio.to_thread(_tag_metrics_sync, body)
    except Exception as e:
        logger.error("tag-metrics failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/tag-placement", response_model=TagPlacementResponse)
async def post_tag_placement(
    body: TagPlacementRequest,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    try:
        out = await asyncio.to_thread(_tag_placement_sync, body)
        if body.refresh_cache_after:
            refresh_designs_cache()
        return out
    except Exception as e:
        logger.error("tag-placement batch failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/sequences", response_model=SequenceExtractResponse)
async def post_extract_sequences(
    body: SequenceExtractRequest,
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    try:
        out = await asyncio.to_thread(_sequences_extract_sync, body)
        if body.refresh_cache_after:
            refresh_designs_cache()
        return out
    except Exception as e:
        logger.error("sequences extract batch failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
