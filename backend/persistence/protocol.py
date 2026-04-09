from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class DesignsRepository(Protocol):
    """Swappable persistence for ingested runs and design rows (SQLite supported; Postgres later)."""

    def is_enabled(self) -> bool:
        """False when DATABASE is unset and persistence is disabled."""
        ...

    def init_schema(self) -> None:
        ...

    def get_run_by_group_key(self, run_group_key: str) -> Optional[Dict[str, Any]]:
        """Return row dict with run_id, run_json (parsed dict), or None."""
        ...

    def upsert_run_and_replace_designs(
        self,
        run_group_key: str,
        run_id: str,
        run_dict: Dict[str, Any],
        designs: List[Dict[str, Any]],
    ) -> None:
        """Replace all designs for run_id; upsert runs row."""
        ...

    def list_run_records(self) -> List[Dict[str, Any]]:
        """Rows with run_id, run_group_key, project_id, method, run_name, run_json (str)."""
        ...

    def list_all_design_dicts(self) -> List[Dict[str, Any]]:
        """Flattened design dicts for cache (merged from DB columns + data_json)."""
        ...

    def update_design_tag(
        self,
        run_id: str,
        design_id: str,
        tag: Optional[str],
        source_path: Optional[str] = None,
    ) -> bool:
        """Return True if a row was updated."""
        ...

    def update_design_good(
        self,
        run_id: str,
        design_id: str,
        good: Optional[bool],
        source_path: Optional[str] = None,
    ) -> bool:
        ...

    def delete_run(self, run_id: str) -> bool:
        ...

    def get_tag_metrics_cache(
        self,
        *,
        run_id: str,
        design_id: str,
        source_path: str,
        structure_filename: str,
        binder_chain: str,
        target_chains: str,
        distant_from: str,
        sasa_probe_radius: float,
        sasa_n_points: int,
        sasa_threshold: float,
        more_distant_threshold: float,
    ) -> Optional[Dict[str, Any]]:
        """Return cached metrics fields for TagMetricsRow (no run_id/design_id/pdb_file/error), or None."""
        ...

    def upsert_tag_metrics_cache(
        self,
        *,
        run_id: str,
        design_id: str,
        source_path: str,
        structure_filename: str,
        binder_chain: str,
        target_chains: str,
        distant_from: str,
        sasa_probe_radius: float,
        sasa_n_points: int,
        sasa_threshold: float,
        more_distant_threshold: float,
        metrics: Dict[str, Any],
    ) -> None:
        ...


def design_dedupe_key(design_id: str, source_path: Optional[str]) -> str:
    return f"{design_id}\x1f{source_path or ''}"


def split_design_for_storage(
    design: Dict[str, Any],
) -> tuple[str, str, str, str, Optional[str], Optional[bool], Dict[str, Any]]:
    """Return design_id, project_id, method, source_path_str, tag, good, payload_for_json."""
    design_id = str(design.get("design_id", ""))
    project_id = str(design.get("project_id", ""))
    method = str(design.get("method", ""))
    sp = design.get("source_path")
    source_path_str = str(sp) if sp is not None and str(sp).strip() else ""
    tag_v = design.get("tag")
    if tag_v is None:
        tag = None
    else:
        try:
            if hasattr(tag_v, "item") and callable(tag_v.item):
                tag_v = tag_v.item()
        except (ValueError, AttributeError):
            pass
        s = str(tag_v).strip()
        tag = s if s else None
    raw_good = design.get("good")
    good: Optional[bool]
    if raw_good is None or (isinstance(raw_good, float) and str(raw_good) == "nan"):
        good = None
    elif raw_good is True or raw_good is False:
        good = bool(raw_good)
    elif raw_good in (0, 1):
        good = bool(raw_good)
    elif isinstance(raw_good, str):
        low = raw_good.strip().lower()
        if low in ("true", "1", "yes"):
            good = True
        elif low in ("false", "0", "no"):
            good = False
        else:
            good = None
    else:
        good = None

    skip = {
        "design_id",
        "run_id",
        "project_id",
        "method",
        "tag",
        "good",
        "source_path",
    }
    payload = {k: v for k, v in design.items() if k not in skip}
    return design_id, project_id, method, source_path_str, tag, good, payload


def merge_design_from_storage(
    run_id: str,
    design_id: str,
    project_id: str,
    method: str,
    source_path: str,
    tag: Optional[str],
    good: Optional[bool],
    data: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(data)
    out["design_id"] = design_id
    out["run_id"] = run_id
    out["project_id"] = project_id
    out["method"] = method
    if source_path:
        out["source_path"] = source_path
    if tag is not None:
        out["tag"] = tag
    if good is not None:
        out["good"] = good
    return out


def run_group_key(run: Dict[str, Any]) -> str:
    project_id = run.get("project_id", "unknown")
    run_name = (run.get("metadata") or {}).get("name", "unknown")
    return f"{project_id}/{run_name}"
