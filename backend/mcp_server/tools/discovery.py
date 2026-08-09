"""Discovery tools: what runs exist, what the metrics mean, what columns are available."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional

from pydantic import Field

from .. import errors, refs, vocab
from ..descriptions import DESCRIBE_COLUMNS, DESCRIBE_METHODS, LIST_RUNS
from ..server import run_blocking


def _summarise_runs(run_ids: Optional[List[str]]) -> Dict[str, Any]:
    from ...cache import designs_by_run_id, ensure_designs_loaded_for_run_ids, run_cache

    if run_ids:
        refs.validate_run_ids(run_ids)
        ensure_designs_loaded_for_run_ids(run_ids)

    # Runs sharing a project/name pair are separate folders of one campaign; the REST
    # API silently merges them, which is where duplicate design_ids come from.
    groups: Dict[str, List[str]] = {}
    for rid, meta in run_cache.items():
        name = (meta.get("metadata") or {}).get("name") or meta.get("run_name") or "unknown"
        groups.setdefault(f"{meta.get('project_id', 'unknown')}/{name}", []).append(rid)

    rows: List[Dict[str, Any]] = []
    for rid, meta in run_cache.items():
        metadata = meta.get("metadata") or {}
        name = metadata.get("name") or meta.get("run_name") or "unknown"
        group = f"{meta.get('project_id', 'unknown')}/{name}"
        cached = designs_by_run_id.get(rid)
        rows.append(
            {
                "run_id": rid,
                "project_id": meta.get("project_id"),
                "run_name": name,
                "method": meta.get("method"),
                "submethod": meta.get("submethod"),
                "target": metadata.get("target") or metadata.get("target_name"),
                "structure_count": len(meta.get("pdb_files") or []),
                "design_count": len(cached) if cached is not None else None,
                "merge_group": group if len(groups[group]) > 1 else None,
            }
        )
    rows.sort(key=lambda r: (str(r["project_id"]), str(r["run_name"])))
    return {
        "runs": rows,
        "total_runs": len(rows),
        "methods": sorted({str(r["method"]) for r in rows if r["method"]}),
    }


def _columns_for(run_ids: List[str], include_raw: bool) -> Dict[str, Any]:
    from ...filtering.service import compute_available_columns

    refs.validate_run_ids(run_ids)
    columns = compute_available_columns(run_ids)
    entries: List[Dict[str, Any]] = []
    for info in columns:
        payload = info.model_dump() if hasattr(info, "model_dump") else dict(info)
        name = payload.get("name") or payload.get("column")
        canonical = vocab.is_canonical(str(name))
        if not include_raw and not canonical:
            continue
        payload["is_canonical"] = canonical
        payload["higher_is_better"] = vocab.higher_is_better(str(name))
        entries.append(payload)
    return {
        "run_ids": run_ids,
        "columns": entries,
        "returned": len(entries),
        "total_available": len(columns),
        "include_raw": include_raw,
        "warnings": []
        if include_raw
        else [
            errors.warning(
                errors.TRUNCATED,
                "Canonical metrics only. Call again with include_raw=true for every "
                f"raw column ({len(columns)} in total).",
            )
        ],
    }


def register(mcp: Any) -> None:
    @mcp.tool(description=LIST_RUNS)
    async def list_runs(
        run_ids: Annotated[
            Optional[List[str]],
            Field(description="Load and count designs for these runs. Omit for metadata only."),
        ] = None,
    ) -> Dict[str, Any]:
        return await run_blocking(_summarise_runs, run_ids)

    @mcp.tool(description=DESCRIBE_METHODS)
    async def describe_methods() -> Dict[str, Any]:
        from ...cache import run_cache

        methods = sorted({str(m.get("method")) for m in run_cache.values() if m.get("method")})
        return {
            "metrics": vocab.metric_catalogue(),
            "methods": {
                method: {
                    "primary_score": vocab.primary_score_for_method(method),
                }
                for method in methods
            },
            "ranking_presets": vocab.RANKING_PRESETS,
            "note": (
                "higher_is_better is per metric, not global: iptm/ptm are higher-is-better, "
                "pae_interaction/rmsd are lower-is-better."
            ),
        }

    @mcp.tool(description=DESCRIBE_COLUMNS)
    async def describe_columns(
        run_ids: Annotated[List[str], Field(description="Runs to describe, from list_runs.")],
        include_raw: Annotated[
            bool,
            Field(description="Include every raw per-method column, not just canonical metrics."),
        ] = False,
    ) -> Dict[str, Any]:
        return await run_blocking(_columns_for, run_ids, include_raw)
