"""The shared table envelope every data-returning tool uses.

Rows are arrays, not objects: repeating a dozen column names on every row costs roughly
40-55% of the payload on a wide design table, and an agent reads
``{"columns": [...], "rows": [[...]]}`` just as well. Floats are rounded to four
significant figures, which is a further ~30% on raw pipeline output without changing any
decision an agent would make from them.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

from . import errors

# Never returned, whatever the caller asks for.
#   pdb_file  - an absolute server path; the agent gets structure_filename/_url instead
#   params    - the run's parameters duplicated onto every single design row
#   run_path  - server filesystem layout, useless and leaky to a remote agent
SUPPRESSED_COLUMNS = {"pdb_file", "params", "run_path", "target_sequence"}

# A crude but effective response-size guard. 4000 cells of typical design metrics lands
# around 12-20k tokens; beyond that a tool result stops being usable context and starts
# being a denial of the agent's own budget.
MAX_CELLS = 4000

SIGNIFICANT_FIGURES = 4


def round_significant(value: float, figures: int = SIGNIFICANT_FIGURES) -> float:
    if value == 0 or not math.isfinite(value):
        return value
    return round(value, -int(math.floor(math.log10(abs(value)))) + (figures - 1))


def clean_cell(value: Any) -> Any:
    """JSON-safe scalar. NaN/Inf become null rather than invalid JSON."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round_significant(value)
    if isinstance(value, (int, str)):
        return value
    return str(value)


def visible_columns(columns: Iterable[str]) -> List[str]:
    from ..filtering.metrics import is_excluded_metric_column

    return [c for c in columns if c not in SUPPRESSED_COLUMNS and not is_excluded_metric_column(c)]


def enforce_cell_budget(n_rows: int, n_cols: int, suggestion: str) -> None:
    """Refuse an oversized response instead of silently truncating it.

    Silent truncation is worse than an error: the agent draws conclusions from what
    looks like the complete result set.
    """
    cells = n_rows * n_cols
    if cells > MAX_CELLS:
        errors.fail(
            errors.RESPONSE_TOO_LARGE,
            f"This would return {n_rows} rows x {n_cols} columns = {cells} cells, over "
            f"the {MAX_CELLS}-cell limit. {suggestion}",
        )


def build_table(
    rows: Sequence[Dict[str, Any]],
    columns: Sequence[str],
    *,
    total_matching: int,
    offset: int = 0,
    methods: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[Dict[str, Any]]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    columns = list(columns)
    table: Dict[str, Any] = {
        "columns": columns,
        "rows": [[clean_cell(row.get(c)) for c in columns] for row in rows],
        "total_matching": total_matching,
        "returned": len(rows),
        "offset": offset,
        "truncated": offset + len(rows) < total_matching,
    }
    if methods:
        table["methods"] = methods
    table["warnings"] = warnings or []
    if extra:
        table.update(extra)
    return table
