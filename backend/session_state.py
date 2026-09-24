"""The UI state a client captures into a download bundle.

A leaf module on purpose: ``filtering.schemas`` needs ``SessionState`` (saved sets store
it in ``filter_params``) and ``bundles`` imports from ``filtering.schemas``, so defining
it in either would create a cycle.

``extra="allow"`` throughout. These models mirror Pinia stores that change far more often
than the backend, and a download must never fail with a 422 because the frontend grew a
field. The fields pinned below are the ones that carry reproducibility meaning, or that
the backend itself reads; everything else rides along untyped and is preserved verbatim
in the emitted JSON.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

SESSION_SCHEMA_VERSION = "1.0"


class SessionSort(BaseModel):
    """One entry of PrimeVue's DataTable multiSortMeta."""

    model_config = ConfigDict(extra="allow")

    field: str
    order: int = 1


class SessionRunRef(BaseModel):
    """Enough per-run identity to find the run again, or to say what is missing."""

    model_config = ConfigDict(extra="allow")

    run_id: str
    run_name: Optional[str] = None
    project_id: Optional[str] = None
    method: Optional[str] = None
    run_path: Optional[str] = None


class SessionState(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = SESSION_SCHEMA_VERSION
    captured: bool = True
    note: Optional[str] = None
    captured_at: Optional[str] = None
    active_view: Optional[str] = None

    runs: List[SessionRunRef] = Field(default_factory=list)
    run_ids: List[str] = Field(default_factory=list)

    selection_mode: str = "explicit"
    selected_design_count: Optional[int] = None

    visible_columns: List[str] = Field(default_factory=list)
    sort: List[SessionSort] = Field(default_factory=list)
    best_mpnn_only: Optional[bool] = None
    saved_set_ids: List[str] = Field(default_factory=list)

    # Snapshots of stores/filtering.ts and stores/plots.ts. Kept as permissive dicts
    # rather than typed models: the authoritative typed shapes already exist on the
    # request side (FilterSpec, RankingMetric, TargetContactGroup, SizeBucket), and
    # re-declaring them here would mean two places to update.
    filtering: Dict[str, Any] = Field(default_factory=dict)
    plots: Dict[str, Any] = Field(default_factory=dict)

    saved_set_id: Optional[str] = None


def uncaptured_session_state(note: str) -> SessionState:
    """Placeholder for a source that has no UI state - e.g. a saved set created before
    ui_state existed. Emitted rather than omitted so the bundle's member list stays the
    same whatever produced it.
    """
    return SessionState(captured=False, note=note)
