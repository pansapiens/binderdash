"""
Pipeline and score configuration (declarative data). See submodules for topics.

- ``run_signatures``: folder detection, results tables, primary score columns
- ``plot_defaults``: default scatter X/Y per method
- ``method_paths``: method IDs, run/project path heuristics, params keys, structure basename rules
- ``score_labels``: metric column names (same as source TSV/CSV headers)
"""

from .method_paths import (
    METHODS_STRUCTURE_BASENAME_STRIP_FIRST_UNDERSCORE,
    PIPELINE_METHOD_IDS,
    PIPELINE_METHOD_IDS_SET,
    STRUCTURE_PARAM_KEYS_BY_METHOD,
    is_disallowed_project_id_segment,
    is_disallowed_run_name_segment,
    should_prune_walk_bindcraft_batches,
    structure_resolve_uses_strip_after_first_underscore,
)
from .plot_defaults import PLOT_DEFAULT_XY_BY_METHOD, default_plot_xy_columns
from .run_signatures import DEFAULT_SKIP_DIRS, run_folder_signatures
from .score_labels import SCORE_FIELD_LABELS

__all__ = [
    "DEFAULT_SKIP_DIRS",
    "METHODS_STRUCTURE_BASENAME_STRIP_FIRST_UNDERSCORE",
    "PIPELINE_METHOD_IDS",
    "PIPELINE_METHOD_IDS_SET",
    "PLOT_DEFAULT_XY_BY_METHOD",
    "SCORE_FIELD_LABELS",
    "STRUCTURE_PARAM_KEYS_BY_METHOD",
    "default_plot_xy_columns",
    "is_disallowed_project_id_segment",
    "is_disallowed_run_name_segment",
    "run_folder_signatures",
    "should_prune_walk_bindcraft_batches",
    "structure_resolve_uses_strip_after_first_underscore",
]
