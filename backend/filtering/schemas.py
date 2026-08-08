from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


NUMERIC_OPERATORS = ("<", "<=", ">", ">=")
STRING_OPERATORS = (
    "contains",
    "not_contains",
    "starts_with",
    "ends_with",
    "equals",
    "not_equals",
    "regex",
)
EMPTY_OPERATORS = ("is_empty", "is_not_empty")


class FilterSpec(BaseModel):
    """A single hard filter — a strict superset of the operators the pre-existing
    client-side Designs-tab custom-filter system supported (see plan §7A.1), so this
    engine can be the single source of truth for both the REST API and the UI.

    ``column`` may be a canonical metric name (see ``filtering.metrics``) or a raw
    DataFrame column name.

    Numeric operators (``<``, ``<=``, ``>``, ``>=``) follow the boltzgen convention:
    lower-is-better metrics use "<" (or "<="), higher-is-better metrics use ">" (or
    ">="); use ``threshold``.

    String operators (``contains``, ``not_contains``, ``starts_with``, ``ends_with``,
    ``equals``, ``not_equals``, ``regex``) compare against ``text_value``.
    ``contains``/``starts_with``/``ends_with`` are case-insensitive (matching the prior
    client-side filters' UX); ``equals``/``not_equals``/``regex`` are case-sensitive.

    ``is_empty``/``is_not_empty`` need neither ``threshold`` nor ``text_value``.
    """

    column: str
    operator: Literal[
        "<", "<=", ">", ">=",
        "contains", "not_contains", "starts_with", "ends_with",
        "equals", "not_equals", "regex",
        "is_empty", "is_not_empty",
    ]
    threshold: Optional[float] = None
    text_value: Optional[str] = None


class RankingMetric(BaseModel):
    """A metric used in the worst-case rank quality score (boltzgen Algorithm 2).

    ``weight`` is the *inverse-importance* weight: a design's rank on this metric is
    divided by ``weight`` before taking the max across metrics, so a larger weight
    de-emphasises the metric's influence on the final rank.
    """

    column: str
    weight: float = 1.0
    higher_is_better: bool = True


class SizeBucket(BaseModel):
    """Caps the number of diverse-set selections whose sequence length falls in [min, max)."""

    min: int
    max: int
    num_designs: int


class ColumnInfo(BaseModel):
    name: str
    canonical_name: Optional[str] = None
    present_in_runs: List[str] = Field(default_factory=list)
    dtype: str
    sample_values: Optional[Dict[str, float]] = None  # {"min":..., "max":..., "mean":...}
    # For a canonical (merged) entry: {method: raw_column_name} showing which raw
    # per-method column this concept resolves to, e.g. {"rfd": "pae_interaction",
    # "bindcraft": "Average_i_pAE"}. Empty/absent for standalone raw columns.
    raw_columns: Dict[str, str] = Field(default_factory=dict)


class FilterCascadeStage(BaseModel):
    column: str
    operator: str
    threshold: Optional[float] = None
    text_value: Optional[str] = None
    # Designs remaining after this stage — filters cascade sequentially (each stage's
    # input is the prior stage's output), so this is also "how many passed this
    # stage"; there's no separate independent count to report.
    remaining: int


class FilteringPreviewRequest(BaseModel):
    run_ids: List[str]
    filters: List[FilterSpec] = Field(default_factory=list)
    metrics: List[RankingMetric] = Field(default_factory=list)


class FilteringPreviewResponse(BaseModel):
    total_designs: int
    per_filter_counts: List[FilterCascadeStage]
    final_passing: int
    available_columns: List[ColumnInfo]


class FilteringRunRequest(BaseModel):
    name: str
    run_ids: List[str]
    filters: List[FilterSpec] = Field(default_factory=list)
    metrics: List[RankingMetric] = Field(default_factory=list)
    budget: int = 30
    alpha: float = 0.1
    size_buckets: List[SizeBucket] = Field(default_factory=list)
    random_state: int = 0


class FilteringRunResponse(BaseModel):
    saved_set_id: str
    name: str
    total_input: int
    passing_filters: int
    top_set_count: int
    diverse_set_count: int


class FilteringColumnsRequest(BaseModel):
    run_ids: List[str]


class FilteringColumnsResponse(BaseModel):
    columns: List[ColumnInfo]


class DesignKey(BaseModel):
    run_id: str
    design_id: str
    source_path: Optional[str] = None


class FilteringApplyRequest(BaseModel):
    """Hard filters only (no ranking/diversity) — for live-narrowing the Designs table.
    Cheap: a single polars filter pass, no ranking computation. See plan §7A.2.
    """

    run_ids: List[str]
    filters: List[FilterSpec] = Field(default_factory=list)


class FilteringApplyResponse(BaseModel):
    total_designs: int
    passing_keys: List[DesignKey]
    final_passing: int


class SavedSet(BaseModel):
    id: str
    name: str
    created_at: str
    source_run_ids: List[str]
    filter_params: Dict
    design_count: int
    total_input: int


class SavedSetListResponse(BaseModel):
    saved_sets: List[SavedSet]


class SavedSetDesignRow(BaseModel):
    design_id: str
    run_id: str
    source_path: Optional[str] = None
    final_rank: Optional[int] = None
    quality_score: Optional[float] = None
    in_diverse_set: bool = False
    metrics: Dict = Field(default_factory=dict)


class SavedSetDesignsResponse(BaseModel):
    designs: List[SavedSetDesignRow]


class SavedSetRenameRequest(BaseModel):
    name: str


class FilteringRankRequest(BaseModel):
    """Hard filters + ranking, no diversity selection and no Saved Set persistence —
    for the Filtering tab's explicit "Apply Ranking" action (see plan §7A.2).
    """

    run_ids: List[str]
    filters: List[FilterSpec] = Field(default_factory=list)
    metrics: List[RankingMetric] = Field(default_factory=list)


class RankedDesignRow(BaseModel):
    run_id: str
    design_id: str
    source_path: Optional[str] = None
    final_rank: Optional[int] = None
    quality_score: Optional[float] = None


class FilteringRankResponse(BaseModel):
    designs: List[RankedDesignRow]
    total_designs: int


class FilteringDiversityRequest(BaseModel):
    """Same shape as ``FilteringRunRequest`` minus ``name`` — runs the full
    filter+rank+diversity pipeline without persisting a Saved Set, for the Filtering
    tab's explicit "Apply Diversity Filter" action (see plan §7A.2).
    """

    run_ids: List[str]
    filters: List[FilterSpec] = Field(default_factory=list)
    metrics: List[RankingMetric] = Field(default_factory=list)
    budget: int = 30
    alpha: float = 0.1
    size_buckets: List[SizeBucket] = Field(default_factory=list)
    random_state: int = 0


class DiverseDesignRow(BaseModel):
    run_id: str
    design_id: str
    source_path: Optional[str] = None
    final_rank: Optional[int] = None
    quality_score: Optional[float] = None
    in_diverse_set: bool = False


class FilteringDiversityResponse(BaseModel):
    designs: List[DiverseDesignRow]
    total_designs: int
    passing_filters: int
    diverse_set_count: int
