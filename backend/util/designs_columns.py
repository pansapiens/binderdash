"""Build column metadata from design rows (aligned with frontend ``buildColumnsFromData``)."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Sequence, Set

from ..config.pipeline_display import (
    SCORE_COLUMN_HEADERS,
    design_build_column_static_keys,
    score_fields_for_range_filter,
)


def _title_case_field(key: str) -> str:
    return key.replace("_", " ").title()


def build_columns_from_data(designs: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    if not designs:
        return []

    base_columns: List[MutableMapping[str, Any]] = [
        {
            "field": "design_id",
            "header": "Design ID",
            "sortable": True,
            "filter": True,
            "filterType": "text",
            "showFilterMenu": False,
            "style": "min-width: 150px",
        },
        {
            "field": "project_id",
            "header": "Project ID",
            "sortable": True,
            "filter": True,
            "filterType": "text",
            "showFilterMenu": False,
            "style": "min-width: 120px",
        },
        {
            "field": "run_name",
            "header": "Run Name",
            "sortable": True,
            "filter": True,
            "filterType": "text",
            "showFilterMenu": False,
            "style": "min-width: 120px",
        },
        {
            "field": "method",
            "header": "Method",
            "sortable": True,
            "filter": True,
            "filterType": "text",
            "showFilterMenu": False,
            "style": "min-width: 100px",
        },
    ]

    if any("good" in d for d in designs):
        base_columns.append(
            {
                "field": "good",
                "header": "Good",
                "sortable": True,
                "filter": True,
                "filterType": "boolean",
                "showFilterMenu": False,
                "style": "min-width: 90px",
            }
        )

    if any("tag" in d for d in designs):
        base_columns.append(
            {
                "field": "tag",
                "header": "Tag",
                "sortable": True,
                "filter": True,
                "filterType": "text",
                "showFilterMenu": False,
                "style": "min-width: 72px",
            }
        )

    known_score_fields = list(score_fields_for_range_filter())
    score_columns: List[MutableMapping[str, Any]] = []
    for sf in known_score_fields:
        if any(sf in d and d.get(sf) is not None for d in designs):
            score_columns.append(
                {
                    "field": sf,
                    "header": SCORE_COLUMN_HEADERS.get(sf, _title_case_field(sf)),
                    "sortable": True,
                    "filter": True,
                    "filterType": "numeric",
                    "showFilterMenu": False,
                    "style": "min-width: 120px",
                }
            )

    metadata_columns: List[MutableMapping[str, Any]] = [
        {
            "field": "target_sequence",
            "header": "Target Sequence",
            "sortable": False,
            "filter": False,
            "style": "min-width: 200px",
        },
        {
            "field": "pdb_file",
            "header": "PDB File",
            "sortable": False,
            "filter": False,
            "style": "min-width: 200px",
        },
        {
            "field": "run_path",
            "header": "Run Path",
            "sortable": False,
            "filter": False,
            "style": "min-width: 200px",
        },
    ]

    existing = set(design_build_column_static_keys())
    dynamic_keys: Set[str] = set()
    for design in designs:
        for key in design.keys():
            if key not in existing:
                dynamic_keys.add(key)

    other_columns: List[MutableMapping[str, Any]] = []
    for key in sorted(dynamic_keys):
        sample: Any = None
        for design in designs:
            v = design.get(key)
            if v is not None and v != "":
                sample = v
                break
        filter_type = "text"
        sortable = False
        if sample is None:
            filter_type = "text"
        elif isinstance(sample, bool):
            filter_type = "boolean"
            sortable = True
        elif isinstance(sample, (int, float)) and not isinstance(sample, bool):
            filter_type = "numeric"
            sortable = True
        elif hasattr(sample, "year"):  # datetime-like
            filter_type = "date"
            sortable = True
        elif isinstance(sample, str) and sample.strip() and _looks_numeric_string(sample):
            filter_type = "numeric"
            sortable = True

        other_columns.append(
            {
                "field": key,
                "header": _title_case_field(key),
                "sortable": sortable,
                "filter": True,
                "filterType": filter_type,
                "showFilterMenu": False,
                "style": "min-width: 120px",
            }
        )

    return list(base_columns) + score_columns + metadata_columns + other_columns


def _looks_numeric_string(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False
