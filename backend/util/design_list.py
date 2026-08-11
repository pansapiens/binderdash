"""Helpers for GET /api/designs list responses (trim, pagination, run_ids parsing)."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, FrozenSet, List, Optional

# Omitted from default list payloads to reduce JSON size; use include_heavy=true to restore.
LIST_DESIGN_OMIT_FIELDS: FrozenSet[str] = frozenset(
    {"params", "target_sequence", "run_path"}
)


def parse_run_ids_param(run_ids: Optional[str]) -> Optional[List[str]]:
    """Parse comma-separated run_ids query value; None means no run filter."""
    if not run_ids or not run_ids.strip():
        return None
    parsed = [rid.strip() for rid in run_ids.split(",") if rid.strip()]
    return parsed if parsed else None


def trim_design_for_list(design: Dict[str, Any]) -> Dict[str, Any]:
    """Drop heavy fields from one design dict for the default list response."""
    return {k: v for k, v in design.items() if k not in LIST_DESIGN_OMIT_FIELDS}


def trim_designs_for_list(
    designs: List[Dict[str, Any]], *, include_heavy: bool
) -> List[Dict[str, Any]]:
    """Apply trim_design_for_list to each row unless include_heavy is true."""
    if include_heavy:
        return designs
    return [trim_design_for_list(d) for d in designs]


def paginate_designs(
    designs: List[Dict[str, Any]],
    page: Optional[int],
    page_size: Optional[int],
) -> tuple[List[Dict[str, Any]], Optional[Dict[str, int]]]:
    """Slice designs when page is set; otherwise return the full list with no meta."""
    if page is None:
        return designs, None
    size = page_size if page_size is not None else 50
    if size < 1:
        size = 50
    start = page * size
    end = start + size
    meta = {
        "total": len(designs),
        "page": page,
        "page_size": size,
    }
    return designs[start:end], meta


def _tsv_cell(value: Any) -> str:
    """Flat string for one TSV cell; nested values are JSON-encoded."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    return json.dumps(value, default=str, separators=(",", ":"))


def designs_to_tsv(designs: List[Dict[str, Any]]) -> str:
    """Serialise design dicts as TSV (union of keys, stable column order)."""
    columns: List[str] = []
    seen = set()
    for design in designs:
        for key in design.keys():
            if key not in seen:
                seen.add(key)
                columns.append(key)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(columns)
    for design in designs:
        writer.writerow([_tsv_cell(design.get(col)) for col in columns])
    return buf.getvalue()
