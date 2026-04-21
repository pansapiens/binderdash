"""Server-side filtering, sorting, and Best MPNN for design rows.

Mirrors logic in ``frontend/src/stores/designs.ts`` for consistent results.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple, Union

from ..config.pipeline_display import (
    METHOD_BEST_SCORE,
    MethodBestScoreConfig,
    score_fields_for_global_filter,
    score_fields_for_range_filter,
)

JsonValue = Union[str, int, float, bool, None]

SCORE_RANGE_FILTER_FIELDS: Tuple[str, ...] = tuple(score_fields_for_range_filter())
GLOBAL_FILTER_SCORE_FIELDS = frozenset(score_fields_for_global_filter())


@dataclass
class CustomFilterRow:
    column: str = ""
    operator: str = "eq"
    value: Any = None
    enabled: bool = True


@dataclass
class ColumnFilterEntry:
    value: Any = None
    match_mode: str = "contains"


@dataclass
class RangeFilters:
    score_min: Optional[float] = None
    score_max: Optional[float] = None
    length_min: Optional[float] = None
    length_max: Optional[float] = None
    target_sequence: Optional[str] = None


@dataclass
class DesignsQuery:
    run_ids: Optional[Sequence[str]] = None
    global_search: Optional[str] = None
    global_score_fields: Tuple[str, ...] = ()
    column_filters: Mapping[str, ColumnFilterEntry] = field(default_factory=dict)
    range_filters: RangeFilters = field(default_factory=RangeFilters)
    custom_filters: Tuple[CustomFilterRow, ...] = ()
    best_mpnn_only: bool = False
    sort_field: Optional[str] = None
    sort_order: int = 0  # -1 desc, 1 asc, 0 unsorted


def _design_has_any_score_for_range(d: Mapping[str, Any]) -> bool:
    for f in SCORE_RANGE_FILTER_FIELDS:
        v = d.get(f)
        if v is not None and v != "":
            return True
    return False


def _cell_is_empty(raw: Any) -> bool:
    return raw is None or raw == ""


def _to_numeric(raw: Any) -> Optional[float]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if isinstance(raw, float) and (raw != raw):  # NaN
            return None
        return float(raw)
    try:
        n = float(raw)
        if n != n:
            return None
        return n
    except (TypeError, ValueError):
        return None


def _normalize_boolean_cell(raw: Any) -> str:
    if _cell_is_empty(raw):
        return "empty"
    if raw is True or raw == 1 or raw == "1":
        return "true"
    if isinstance(raw, str) and raw.lower() == "true":
        return "true"
    if raw is False or raw == 0 or raw == "0":
        return "false"
    if isinstance(raw, str) and raw.lower() == "false":
        return "false"
    return "empty"


def _column_type_for_field(
    field_name: str, known_numeric: frozenset, known_boolean: frozenset
) -> str:
    if field_name in known_boolean:
        return "boolean"
    if field_name in known_numeric:
        return "numeric"
    return "text"


def passes_custom_filter(
    design: Mapping[str, Any],
    cf: CustomFilterRow,
    col_type: str,
) -> bool:
    if not cf.column:
        return True
    op = cf.operator
    raw = design.get(cf.column)

    if op == "is_empty":
        return _cell_is_empty(raw)
    if op == "is_not_empty":
        return not _cell_is_empty(raw)

    if col_type == "boolean":
        if op != "eq":
            return True
        cell = _normalize_boolean_cell(raw)
        if cf.value is None:
            return cell == "empty"
        if cf.value is True:
            return cell == "true"
        if cf.value is False:
            return cell == "false"
        return True

    if col_type == "numeric":
        n_row = _to_numeric(raw)
        if n_row is None:
            return False
        if cf.value is None:
            return True
        n_filter = _to_numeric(cf.value)
        if n_filter is None:
            return True
        if op == "eq":
            return n_row == n_filter
        if op == "ne":
            return n_row != n_filter
        if op == "gt":
            return n_row > n_filter
        if op == "gte":
            return n_row >= n_filter
        if op == "lt":
            return n_row < n_filter
        if op == "lte":
            return n_row <= n_filter
        return True

    row_str = "" if raw is None else str(raw)
    if op == "eq":
        if cf.value is None:
            return True
        return row_str == str(cf.value)
    if op == "ne":
        if cf.value is None:
            return True
        return row_str != str(cf.value)
    if _cell_is_empty(raw):
        return False
    if cf.value is None:
        return True
    fv = str(cf.value).lower()
    rs = row_str.lower()
    if op == "contains":
        return fv in rs
    if op == "not_contains":
        return fv not in rs
    if op == "starts_with":
        return rs.startswith(fv)
    if op == "ends_with":
        return rs.endswith(fv)
    return True


def _filter_column_value(
    design: Mapping[str, Any], fkey: str, entry: ColumnFilterEntry
) -> bool:
    val = entry.value
    if val is None or val == "":
        return True
    raw = design.get(fkey)
    mm = (entry.match_mode or "contains").lower()
    if fkey == "method":
        return str(raw) == str(val)
    s_val = str(val).lower()
    s_raw = ("" if raw is None else str(raw)).lower()
    if mm == "equals":
        return s_raw == s_val
    return s_val in s_raw


def _apply_global_search(
    design: Mapping[str, Any], needle_lower: str, global_score_fields: Sequence[str]
) -> bool:
    base = ["design_id", "project_id", "run_name", "method", "Length"]
    score_fields: List[str] = [f for f in global_score_fields if f in GLOBAL_FILTER_SCORE_FIELDS]
    check_fields = base + score_fields
    for fname in check_fields:
        v = design.get(fname)
        if v is not None and needle_lower in str(v).lower():
            return True
    return False


def _apply_range_and_builtin_filters(
    rows: List[MutableMapping[str, Any]],
    q: DesignsQuery,
) -> List[MutableMapping[str, Any]]:
    out: List[MutableMapping[str, Any]] = []
    cf = q.column_filters
    rf = q.range_filters
    for d in rows:
        skip = False
        for fkey in ("design_id", "project_id", "run_name", "method"):
            e = cf.get(fkey)
            if e and e.value not in (None, ""):
                if not _filter_column_value(d, fkey, e):
                    skip = True
                    break
        if skip:
            continue
        if rf.score_min is not None:
            if _design_has_any_score_for_range(d):
                ok = False
                smin = float(rf.score_min)
                for fname in SCORE_RANGE_FILTER_FIELDS:
                    v = d.get(fname)
                    if v is None or v == "":
                        continue
                    try:
                        if float(v) >= smin:
                            ok = True
                            break
                    except (TypeError, ValueError):
                        continue
                if not ok:
                    continue
        if rf.score_max is not None:
            if _design_has_any_score_for_range(d):
                ok = False
                smax = float(rf.score_max)
                for fname in SCORE_RANGE_FILTER_FIELDS:
                    v = d.get(fname)
                    if v is None or v == "":
                        continue
                    try:
                        if float(v) <= smax:
                            ok = True
                            break
                    except (TypeError, ValueError):
                        continue
                if not ok:
                    continue
        if rf.length_min is not None:
            length = d.get("Length", d.get("length"))
            if length is not None and length != "":
                try:
                    if float(length) < float(rf.length_min):
                        continue
                except (TypeError, ValueError):
                    pass
        if rf.length_max is not None:
            length = d.get("Length", d.get("length"))
            if length is not None and length != "":
                try:
                    if float(length) > float(rf.length_max):
                        continue
                except (TypeError, ValueError):
                    pass
        if rf.target_sequence:
            pat = rf.target_sequence
            ts = d.get("target_sequence")
            if not ts:
                continue
            try:
                if not re.search(pat, str(ts), re.IGNORECASE):
                    continue
            except re.error:
                if pat.lower() not in str(ts).lower():
                    continue

        out.append(d)
    return out


def _compare_secondary_scores(
    d1: Mapping[str, Any],
    d2: Mapping[str, Any],
    secondary_fields: Sequence[str],
    higher_is_better: bool,
) -> bool:
    for fname in secondary_fields:
        try:
            s1 = d1.get(fname)
            s2 = d2.get(fname)
        except Exception:
            continue
        if s1 is None or s2 is None:
            continue
        try:
            v1 = float(s1)
            v2 = float(s2)
        except (TypeError, ValueError):
            continue
        if higher_is_better:
            if v1 > v2:
                return True
            if v1 < v2:
                return False
        else:
            if v1 < v2:
                return True
            if v1 > v2:
                return False
    return False


def _select_best_design(group: List[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Matches ``_selectBestDesign`` in the designs store (per-row method config)."""
    if not group:
        raise ValueError("empty group")
    if len(group) == 1:
        return group[0]
    best_design = group[0]
    best_score: Optional[float] = None
    for design in group:
        method = str(design.get("method") or "")
        cfg = METHOD_BEST_SCORE.get(method)
        if not cfg:
            continue
        primary_score = _to_numeric(design.get(cfg.primary))
        if primary_score is None:
            continue
        is_better = False
        if best_score is None:
            is_better = True
        elif cfg.higher_is_better:
            if primary_score > best_score:
                is_better = True
            elif primary_score == best_score:
                is_better = _compare_secondary_scores(
                    design, best_design, cfg.secondary, True
                )
        else:
            if primary_score < best_score:
                is_better = True
            elif primary_score == best_score:
                is_better = _compare_secondary_scores(
                    design, best_design, cfg.secondary, False
                )
        if is_better:
            best_design = design
            best_score = primary_score
    return best_design


def filter_best_mpnn_only(rows: List[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    backbone_groups: Dict[str, List[Mapping[str, Any]]] = {}
    no_backbone: List[Mapping[str, Any]] = []
    for design in rows:
        bid = design.get("backbone_id")
        if not bid:
            no_backbone.append(design)
            continue
        key = str(bid)
        backbone_groups.setdefault(key, []).append(design)
    out: List[Mapping[str, Any]] = []
    out.extend(no_backbone)
    for group in backbone_groups.values():
        if len(group) == 1:
            out.append(group[0])
        else:
            out.append(_select_best_design(list(group)))
    return out


def _infer_column_types(
    sample_rows: Sequence[Mapping[str, Any]], custom_cols: Sequence[str]
) -> Tuple[frozenset, frozenset]:
    numeric: set = set()
    boolean: set = set()
    for fname in custom_cols:
        sample: Any = None
        for d in sample_rows:
            v = d.get(fname)
            if v is not None and v != "":
                sample = v
                break
        if sample is None:
            continue
        if isinstance(sample, bool):
            boolean.add(fname)
        elif isinstance(sample, (int, float)) and not isinstance(sample, bool):
            numeric.add(fname)
        elif isinstance(sample, str) and sample.strip() != "":
            try:
                float(sample)
                numeric.add(fname)
            except ValueError:
                pass
    return frozenset(numeric), frozenset(boolean)


def apply_query(
    rows: Sequence[Mapping[str, Any]],
    q: DesignsQuery,
) -> List[Dict[str, Any]]:
    """Filter and sort *rows* (mutates none; returns new list of dict copies as needed)."""
    work: List[MutableMapping[str, Any]] = [dict(r) for r in rows]

    if q.run_ids:
        allowed = {str(x) for x in q.run_ids}
        work = [d for d in work if str(d.get("run_id")) in allowed]

    if q.global_search and q.global_search.strip():
        needle = q.global_search.strip().lower()
        work = [
            d
            for d in work
            if _apply_global_search(d, needle, q.global_score_fields)
        ]

    work = _apply_range_and_builtin_filters(work, q)

    # Custom filters — need types; infer from current work set per column
    active_custom = tuple(c for c in q.custom_filters if c.enabled is not False)
    if active_custom:
        cols = [c.column.strip() for c in active_custom if c.column]
        num_t, bool_t = _infer_column_types(work, cols)

        def passes_all_custom(d: Mapping[str, Any]) -> bool:
            for cf in active_custom:
                col = (cf.column or "").strip()
                if not col:
                    continue
                ct = _column_type_for_field(col, num_t, bool_t)
                if not passes_custom_filter(d, cf, ct):
                    return False
            return True

        work = [d for d in work if passes_all_custom(d)]

    if q.best_mpnn_only:
        work = filter_best_mpnn_only([dict(x) for x in work])
        work = [dict(x) for x in work]

    if q.sort_field and q.sort_order in (-1, 1):
        field_name = q.sort_field
        reverse = q.sort_order == -1

        def sort_key(item: Mapping[str, Any]) -> Tuple[int, Any]:
            v = item.get(field_name)
            if v is None:
                return (1, "")
            if isinstance(v, bool):
                return (0, (1 if v else 0))
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return (0, float(v))
            try:
                fn = float(v)
                return (0, fn)
            except (TypeError, ValueError):
                pass
            return (0, str(v).lower())

        work_sorted = sorted(work, key=sort_key, reverse=reverse)
        return [dict(x) for x in work_sorted]

    return [dict(x) for x in work]


def parse_filters_json(raw: Optional[str]) -> Dict[str, ColumnFilterEntry]:
    if not raw or not str(raw).strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    column_keys = {"design_id", "project_id", "run_name", "method"}
    out: Dict[str, ColumnFilterEntry] = {}
    for k, v in data.items():
        if str(k) not in column_keys:
            continue
        if not isinstance(v, dict):
            continue
        val = v.get("value")
        mm = v.get("matchMode") or v.get("match_mode") or "contains"
        out[str(k)] = ColumnFilterEntry(value=val, match_mode=str(mm))
    return out


def parse_custom_filters_json(raw: Optional[str]) -> Tuple[CustomFilterRow, ...]:
    if not raw or not str(raw).strip():
        return ()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(data, list):
        return ()
    out: List[CustomFilterRow] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        out.append(
            CustomFilterRow(
                column=str(item.get("column") or ""),
                operator=str(item.get("operator") or "eq"),
                value=item.get("value"),
                enabled=item.get("enabled", True) is not False,
            )
        )
    return tuple(out)


def parse_range_json(raw: Optional[str]) -> RangeFilters:
    if not raw or not str(raw).strip():
        return RangeFilters()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return RangeFilters()
    if not isinstance(data, dict):
        return RangeFilters()

    def _f(key: str) -> Optional[float]:
        x = data.get(key)
        if x is None or x == "":
            return None
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    ts = data.get("target_sequence")
    ts_str = None if ts is None or ts == "" else str(ts)
    return RangeFilters(
        score_min=_f("score_min"),
        score_max=_f("score_max"),
        length_min=_f("length_min"),
        length_max=_f("length_max"),
        target_sequence=ts_str,
    )


def parse_global_score_fields(raw: Optional[str]) -> Tuple[str, ...]:
    if not raw or not str(raw).strip():
        return ()
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    return tuple(parts)


def build_designs_query_from_params(
    *,
    global_search: Optional[str],
    global_score_fields_raw: Optional[str],
    filters_json: Optional[str],
    custom_filters_json: Optional[str],
    range_json: Optional[str],
    sort_field: Optional[str],
    sort_order: int,
    best_mpnn_only: bool,
) -> DesignsQuery:
    cf = parse_filters_json(filters_json)
    # Map filter_state keys to column filter entries with _filter_column_value logic
    # The store uses filters.value.design_id etc. — already in parse_filters_json
    return DesignsQuery(
        global_search=global_search,
        global_score_fields=parse_global_score_fields(global_score_fields_raw),
        column_filters=cf,
        range_filters=parse_range_json(range_json),
        custom_filters=parse_custom_filters_json(custom_filters_json),
        best_mpnn_only=best_mpnn_only,
        sort_field=(sort_field.strip() if sort_field and str(sort_field).strip() else None),
        sort_order=int(sort_order) if sort_order is not None else 0,
    )
