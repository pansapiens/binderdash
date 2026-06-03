from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from .persistence.factory import get_designs_repository
from .persistence.protocol import RESERVED_TOP_LEVEL_KEYS, design_dedupe_key
from .run_discovery import resolve_design_id_column

logger = logging.getLogger(__name__)


def read_uploaded_table(content: bytes, filename: str) -> pd.DataFrame:
    name = (filename or "").lower()
    buf = io.BytesIO(content)
    if name.endswith(".csv"):
        return pd.read_csv(buf)
    if name.endswith(".tsv") or name.endswith(".txt"):
        return pd.read_csv(buf, sep="\t")
    try:
        return pd.read_csv(buf, sep="\t")
    except Exception:
        buf.seek(0)
        return pd.read_csv(buf)


def resolve_upload_design_id_column(
    df: pd.DataFrame, design_id_column: Optional[str] = None
) -> str:
    if design_id_column and design_id_column in df.columns:
        return design_id_column
    if "design_id" in df.columns:
        return "design_id"
    for col in df.columns:
        if str(col).lower() in ("design", "description", "name", "id"):
            return col
    raise ValueError(
        "Could not find a design id column; include design_id or pass design_id_column"
    )


def _row_fields(row: pd.Series, skip_cols: Set[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for col in row.index:
        if col in skip_cols:
            continue
        val = row[col]
        if pd.isna(val):
            continue
        out[str(col)] = val.item() if hasattr(val, "item") else val
    return out


def build_merge_items_for_runs(
    df: pd.DataFrame,
    design_id_col: str,
    run_ids: List[str],
    designs_by_run: Dict[str, List[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return (items for merge_design_extra_data_bulk per run_id batching), summary)."""
    upload_has_source = "source_path" in df.columns
    skip_cols = {design_id_col}
    if upload_has_source:
        skip_cols.add("source_path")

    new_columns = [
        c
        for c in df.columns
        if c not in skip_cols and str(c) not in RESERVED_TOP_LEVEL_KEYS
    ]

    items: List[Dict[str, Any]] = []
    matched_design_ids: Set[str] = set()
    upload_rows_by_id: Dict[str, List[pd.Series]] = {}
    for _, row in df.iterrows():
        did = str(row.get(design_id_col, "")).strip()
        if not did:
            continue
        upload_rows_by_id.setdefault(did, []).append(row)

    all_design_ids_in_runs: Set[str] = set()
    for run_id in run_ids:
        for design in designs_by_run.get(run_id, []):
            did = str(design.get("design_id", "")).strip()
            if did:
                all_design_ids_in_runs.add(did)

    unknown_in_upload = set(upload_rows_by_id.keys()) - all_design_ids_in_runs

    for run_id in run_ids:
        for design in designs_by_run.get(run_id, []):
            did = str(design.get("design_id", "")).strip()
            if not did:
                continue
            upload_rows = upload_rows_by_id.get(did)
            if not upload_rows:
                continue
            sp_design = str(design.get("source_path") or "").strip()
            row_to_use: Optional[pd.Series] = None
            if upload_has_source:
                for urow in upload_rows:
                    sp_up = str(urow.get("source_path") or "").strip()
                    if sp_up == sp_design:
                        row_to_use = urow
                        break
            else:
                row_to_use = upload_rows[0]
            if row_to_use is None:
                continue
            matched_design_ids.add(did)
            fields = _row_fields(row_to_use, skip_cols)
            if not fields:
                continue
            items.append(
                {
                    "run_id": run_id,
                    "design_id": did,
                    "source_path": sp_design or None,
                    "fields": fields,
                }
            )

    summary = {
        "upload_row_count": len(df),
        "new_columns": new_columns,
        "matched_design_count": len(matched_design_ids),
        "unknown_design_id_count": len(unknown_in_upload),
        "skipped_columns": [],
    }
    return items, summary


def apply_merge_table_upload(
    content: bytes,
    filename: str,
    run_ids: List[str],
    *,
    design_id_column: Optional[str] = None,
    preview: bool = False,
) -> Dict[str, Any]:
    repo = get_designs_repository()
    if not repo.is_enabled():
        raise ValueError(
            "DATABASE is not configured or persistence is disabled; set DATABASE in .env"
        )
    if not run_ids:
        raise ValueError("At least one run_id is required")

    df = read_uploaded_table(content, filename)
    if df.empty:
        raise ValueError("Uploaded table is empty")

    design_id_col = resolve_upload_design_id_column(df, design_id_column)

    all_designs = repo.list_all_design_dicts()
    allowed = set(run_ids)
    designs_by_run: Dict[str, List[Dict[str, Any]]] = {rid: [] for rid in run_ids}
    for d in all_designs:
        rid = str(d.get("run_id", ""))
        if rid in allowed:
            designs_by_run.setdefault(rid, []).append(d)

    flat_items, summary = build_merge_items_for_runs(
        df, design_id_col, run_ids, designs_by_run
    )

    pipeline_keys = set(repo.list_data_json_keys_for_runs(run_ids))
    new_cols = summary.get("new_columns") or []
    summary["pipeline_collision_columns"] = sorted(
        c for c in new_cols if c in pipeline_keys
    )

    if preview:
        would_update = len(flat_items)
        return {
            "preview": True,
            "design_id_column": design_id_col,
            **summary,
            "would_update_rows": would_update,
        }

    totals = {
        "matched": 0,
        "updated": 0,
        "skipped_keys": 0,
        "unknown_design_ids": 0,
    }
    by_run: Dict[str, List[Dict[str, Any]]] = {}
    for it in flat_items:
        rid = str(it["run_id"])
        by_run.setdefault(rid, []).append(
            {
                "design_id": it["design_id"],
                "source_path": it.get("source_path"),
                "fields": it["fields"],
            }
        )
    for rid, batch in by_run.items():
        stats = repo.merge_design_extra_data_bulk(rid, batch)
        for k in totals:
            totals[k] += stats.get(k, 0)

    return {
        "preview": False,
        "design_id_column": design_id_col,
        **summary,
        **totals,
    }
