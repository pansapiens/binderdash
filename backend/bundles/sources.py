"""Build a BundleSpec from either a live table selection or a saved set.

Everything except row production is shared. Structure resolution in particular lives here
once, so both paths get the same arcname namespacing and the same per-miss warnings -
the previous saved-set zip builder skipped missing files silently, which made a short
download indistinguishable from a complete one.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .contacts import build_contact_export
from .models import (
    BundleDesignsRequest,
    BundleProvenance,
    PrepareSequencesBundleRequest,
)
from .spec import BundleSpec, StructureRef
from ..cache import get_designs_for_run_ids, get_run_metadata
from ..filtering import service as filtering_service
from ..session_state import SessionState, uncaptured_session_state
from ..util.structure_paths import resolve_structure_path

logger = logging.getLogger(__name__)

NO_CLIENT_STATE_NOTE = (
    "The client did not send UI state with this download request, so the table layout, "
    "filters and ranking configuration of the session that produced it are not recorded."
)

LEGACY_SET_NOTE = (
    "This saved set was created before Binderdash recorded UI state, so the table "
    "layout and plot settings of the session that produced it are not available. The "
    "filter and ranking recipe is in manifest.json under provenance.filter_params."
)

_SAFE_LABEL = re.compile(r"[^A-Za-z0-9._-]+")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_label(label: str, fallback: str = "binderdash_bundle") -> str:
    cleaned = _SAFE_LABEL.sub("_", (label or "").strip()).strip("._-")
    return cleaned[:96] or fallback


def design_key_str(run_id: Any, design_id: Any, source_path: Any = None) -> str:
    sp = str(source_path).strip() if source_path is not None and str(source_path).strip() else ""
    return f"{run_id}\x1f{design_id}\x1f{sp}"


def _structure_filename(row: Dict[str, Any]) -> Optional[str]:
    value = row.get("pdb_file") or row.get("structure_file") or row.get("cif_file")
    if not value:
        return None
    return Path(str(value)).name


def _run_short(run_id: str, run: Optional[Dict[str, Any]]) -> str:
    if run:
        name = (run.get("metadata") or {}).get("name") or run.get("run_name")
        if name:
            return safe_label(str(name), run_id)
    return safe_label(run_id, "run")


def resolve_structures(
    rows: List[Dict[str, Any]],
    *,
    rank_of: Optional[Dict[str, int]] = None,
) -> Tuple[List[StructureRef], int, List[str]]:
    """Resolve each row's structure file. Returns (refs, requested, warnings).

    Arcnames are namespaced by run because two runs can hold the same structure
    basename; without that, zipfile drops the second with only a UserWarning.
    """
    refs: List[StructureRef] = []
    warnings: List[str] = []
    requested = 0
    seen: set[str] = set()

    for index, row in enumerate(rows, start=1):
        filename = _structure_filename(row)
        if not filename:
            continue
        requested += 1
        run_id = str(row.get("run_id") or "")
        design_id = str(row.get("design_id") or "")
        run = get_run_metadata(run_id)
        if not run:
            warnings.append(f"Run {run_id} is no longer known, so {filename} was omitted")
            continue
        path = resolve_structure_path(run.get("pdb_files", []), filename, run.get("method"))
        if path is None or not path.is_file():
            warnings.append(f"Structure file {filename} was not found on disk for run {run_id}")
            continue
        try:
            size = path.stat().st_size
        except OSError as e:
            warnings.append(f"Could not read {filename}: {e}")
            continue

        rank = (rank_of or {}).get(design_key_str(run_id, design_id, row.get("source_path")), index)
        arcname = f"structures/rank{rank:04d}_{_run_short(run_id, run)}_{path.name}"
        if arcname in seen:
            suffix = 2
            while f"{arcname}_{suffix}" in seen:
                suffix += 1
            arcname = f"{arcname}_{suffix}"
        seen.add(arcname)
        refs.append(
            StructureRef(
                arcname=arcname,
                path=path,
                size_bytes=size,
                run_id=run_id,
                design_id=design_id,
            )
        )

    return refs, requested, warnings


def _dedupe_keys(keys: Iterable[Any]) -> List[Tuple[str, str, str]]:
    """First-seen order, deduped. A duplicated key would otherwise duplicate both a table
    row and a structure file."""
    out: List[Tuple[str, str, str]] = []
    seen: set[Tuple[str, str, str]] = set()
    for key in keys:
        triple = (
            str(getattr(key, "run_id", "") or ""),
            str(getattr(key, "design_id", "") or ""),
            str(getattr(key, "source_path", "") or ""),
        )
        if not triple[0] or not triple[1] or triple in seen:
            continue
        seen.add(triple)
        out.append(triple)
    return out


def _rows_for_keys(
    keys: List[Tuple[str, str, str]],
    run_ids: List[str],
    client_columns: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Design dicts from the cache, in the order the client asked for them."""
    warnings: List[str] = []
    available = get_designs_for_run_ids(run_ids)
    by_key: Dict[str, Dict[str, Any]] = {}
    by_loose: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in available:
        run_id = str(row.get("run_id") or "")
        design_id = str(row.get("design_id") or "")
        by_key[design_key_str(run_id, design_id, row.get("source_path"))] = row
        by_loose.setdefault((run_id, design_id), row)

    rows: List[Dict[str, Any]] = []
    missing = 0
    for run_id, design_id, source_path in keys:
        exact = design_key_str(run_id, design_id, source_path)
        row = by_key.get(exact) or by_loose.get((run_id, design_id))
        if row is None:
            missing += 1
            continue
        merged = dict(row)
        extra = client_columns.get(exact) or client_columns.get(f"{run_id}\x1f{design_id}\x1f")
        if extra:
            merged.update(extra)
        rows.append(merged)

    if missing:
        warnings.append(
            f"{missing} requested design(s) are no longer in the design cache and were omitted"
        )
    return rows, warnings


def spec_from_live_request(
    request: BundleDesignsRequest,
    *,
    kind: str = "designs",
) -> BundleSpec:
    keys = _dedupe_keys(request.keys)
    run_ids = [str(r).strip() for r in dict.fromkeys(request.run_ids) if str(r).strip()]
    if not run_ids:
        run_ids = list(dict.fromkeys(run_id for run_id, _design, _source in keys))

    rows, warnings = _rows_for_keys(keys, run_ids, request.client_columns)

    rank_of = {design_key_str(*k): i for i, k in enumerate(keys, start=1)}
    structures: List[StructureRef] = []
    requested = 0
    if request.include.structures:
        structures, requested, structure_warnings = resolve_structures(rows, rank_of=rank_of)
        warnings.extend(structure_warnings)

    contacts = (
        build_contact_export(run_ids, rows) if request.include.target_contacts else None
    )

    prepared = getattr(request, "prepared", None)
    # Always emit a session member when session capture is on, even if the client sent
    # nothing: the bundle's member list must not depend on which source produced it.
    session = None
    if request.include.session:
        session = request.session or uncaptured_session_state(NO_CLIENT_STATE_NOTE)

    return BundleSpec(
        kind="prepare_sequences" if prepared is not None else "designs",
        bundle_id=str(uuid.uuid4()),
        created_at=_now_iso(),
        label=safe_label(request.label),
        provenance=BundleProvenance(source="live_selection", run_ids=run_ids),
        rows=rows,
        structures=structures,
        structures_requested=requested,
        contacts=contacts,
        session=session,
        prepared=prepared,
        warnings=warnings,
    )


def spec_from_prepare_request(request: PrepareSequencesBundleRequest) -> BundleSpec:
    return spec_from_live_request(request, kind="prepare_sequences")


def spec_from_saved_set(saved_set_id: str) -> Optional[BundleSpec]:
    saved_set = filtering_service.get_saved_set(saved_set_id)
    if saved_set is None:
        return None
    designs_response = filtering_service.get_saved_set_designs(saved_set_id)
    frozen = designs_response.designs if designs_response else []

    # The frozen metrics snapshot, deliberately not re-read from the design cache: a
    # saved set is an immutable record of what it contained when it was made.
    rows: List[Dict[str, Any]] = []
    rank_of: Dict[str, int] = {}
    for index, row in enumerate(frozen, start=1):
        merged: Dict[str, Any] = {
            "design_id": row.design_id,
            "run_id": row.run_id,
            "source_path": row.source_path,
            "final_rank": row.final_rank,
            "quality_score": row.quality_score,
            "in_diverse_set": row.in_diverse_set,
        }
        merged.update(row.metrics or {})
        rows.append(merged)
        rank_of[design_key_str(row.run_id, row.design_id, row.source_path)] = (
            row.final_rank or index
        )

    structures, requested, warnings = resolve_structures(rows, rank_of=rank_of)
    run_ids = list(saved_set.source_run_ids or [])
    contacts = build_contact_export(run_ids, rows)

    filter_params = dict(saved_set.filter_params or {})
    raw_ui_state = filter_params.pop("ui_state", None)
    if raw_ui_state:
        try:
            session = SessionState.model_validate(raw_ui_state)
        except Exception as e:
            logger.warning("saved set %s has unreadable ui_state: %s", saved_set_id, e)
            session = uncaptured_session_state(
                "The stored UI state for this saved set could not be read."
            )
    else:
        session = uncaptured_session_state(LEGACY_SET_NOTE)

    return BundleSpec(
        kind="designs",
        bundle_id=str(uuid.uuid4()),
        created_at=_now_iso(),
        label=safe_label(f"saved_set_{saved_set.name}", f"saved_set_{saved_set_id}"),
        provenance=BundleProvenance(
            source="saved_set",
            run_ids=run_ids,
            saved_set_id=saved_set.id,
            saved_set_name=saved_set.name,
            saved_set_created_at=saved_set.created_at,
            filter_params=filter_params,
        ),
        rows=rows,
        structures=structures,
        structures_requested=requested,
        contacts=contacts,
        session=session,
        warnings=warnings,
    )
