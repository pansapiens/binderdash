from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# Authentication models
class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class ScanRequest(BaseModel):
    folders: List[str]
    force_rescan_of_ingested: bool = False


class IngestRequest(BaseModel):
    runs: List[Dict[str, Any]]


class IngestPreviewRequest(BaseModel):
    runs: List[Dict[str, Any]]


class IngestPreviewReingestItem(BaseModel):
    run_group_key: str
    display_name: str


class IngestPreviewResponse(BaseModel):
    reingest: List[IngestPreviewReingestItem]


class RunMetadata(BaseModel):
    run_id: str
    project_id: str
    path: str
    method: str  # e.g. bindcraft, rfd, boltzgen, rfd3
    results_table: Optional[str] = None
    pdb_files: List[str] = []
    metadata: Dict[str, Any] = {}


class PdbTarItem(BaseModel):
    run_id: str
    filename: str


class PdbTarRequest(BaseModel):
    items: List[PdbTarItem]


class DesignGoodUpdate(BaseModel):
    run_id: str
    design_id: str
    good: Optional[bool]
    source_path: Optional[str] = None


class DesignTagUpdate(BaseModel):
    run_id: str
    design_id: str
    tag: Optional[str] = None  # N, C, or None to clear
    source_path: Optional[str] = None


class SequenceExtractItem(BaseModel):
    run_id: str
    design_id: str
    pdb_file: str
    chain: str = "B"
    source_path: Optional[str] = None


class SequenceExtractRequest(BaseModel):
    designs: List[SequenceExtractItem]
    refresh_cache_after: bool = Field(
        default=True,
        description="When false, skip rebuilding the in-memory designs cache until a later refresh.",
    )


class SequenceExtractResultRow(BaseModel):
    run_id: str
    design_id: str
    sequence: Optional[str] = None
    error: Optional[str] = None


class SequenceExtractResponse(BaseModel):
    results: List[SequenceExtractResultRow]


class TagPlacementItem(BaseModel):
    run_id: str
    design_id: str
    pdb_file: Optional[str] = None
    source_path: Optional[str] = None


class TagPlacementRequest(BaseModel):
    designs: List[TagPlacementItem]
    binder_chain: str = "B"
    target_chains: Optional[str] = None
    distant_from: Optional[str] = None
    sasa_probe_radius: float = 1.4
    sasa_n_points: int = 100
    sasa_threshold: float = 30.0
    more_distant_threshold: float = 5.0
    refresh_cache_after: bool = Field(
        default=True,
        description="When false, skip rebuilding the in-memory designs cache until a later refresh.",
    )
    cache_only: bool = Field(
        default=False,
        description="When true, return cached tag metrics only (no compute); misses are empty rows.",
    )
    ignore_cache: bool = Field(
        default=False,
        description="When true, skip cache reads; recompute and refresh stored cache entries.",
    )


class TagPlacementResultRow(BaseModel):
    run_id: str
    design_id: str
    tag: Optional[str] = None
    error: Optional[str] = None


class TagPlacementResponse(BaseModel):
    results: List[TagPlacementResultRow]


class TagMetricsRow(BaseModel):
    run_id: str
    design_id: str
    pdb_file: Optional[str] = None
    sequence: Optional[str] = None
    n_aa_type: Optional[str] = None
    c_aa_type: Optional[str] = None
    n_sasa: Optional[float] = None
    c_sasa: Optional[float] = None
    n_percent_sasa: Optional[float] = None
    c_percent_sasa: Optional[float] = None
    n_percent_buried: Optional[float] = None
    c_percent_buried: Optional[float] = None
    n_c_dist: Optional[float] = None
    n_dist_target: Optional[float] = None
    c_dist_target: Optional[float] = None
    n_target_contacts: Optional[bool] = None
    c_target_contacts: Optional[bool] = None
    predicted_tag: Optional[str] = None
    error: Optional[str] = None


class TagMetricsResponse(BaseModel):
    results: List[TagMetricsRow]


class InputTargetItem(BaseModel):
    id: str
    label: str


class InputTargetsResponse(BaseModel):
    targets: List[InputTargetItem]


class CodonTableOption(BaseModel):
    value: str
    label: str


class CodonTableListResponse(BaseModel):
    items: List[CodonTableOption]


class CodonTableDetailResponse(BaseModel):
    value: str
    label: str
    stop_codons: List[str]
    codons_by_aa: Dict[str, Dict[str, float]]
