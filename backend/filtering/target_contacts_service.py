"""Orchestration for target-contact filters: resolve chain roles and target identity per
run, compute and cache per-design contact records, evaluate contact conditions into
boolean columns, and aggregate records into the per-residue profile the structure viewer
colours by.

The filter evaluation deliberately produces *virtual columns* rather than extending the
filtering engine. Each condition becomes a ``__tc_<group>_<index>`` boolean column on
the designs DataFrame plus an ordinary ``FilterSpec`` against it, so cascade counts,
ranking, diversity selection and Saved Sets all work unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import polars as pl

from ..cache import get_designs_for_run_ids, get_run_metadata
from ..persistence.factory import get_designs_repository
from ..routers.files import _resolve_structure_path
from ..util.sasa_constants import TIEN_2023_THEORETICAL
from .chain_roles import resolve_chain_roles_cached
from .schemas import (
    FilterSpec,
    TargetContactCoverage,
    TargetContactFilterSpec,
    TargetContactGroup,
    TargetContactProfileRequest,
    TargetContactProfileResponse,
    TargetContactProfileRow,
    TargetContactsComputeRequest,
    TargetContactsComputeResponse,
    TargetInfo,
    TargetResidueDto,
    TargetResiduesResponse,
)
from .target_contacts import (
    DEFAULT_N_POINTS,
    DEFAULT_PROBE_RADIUS,
    DEFAULT_RECORD_CUTOFF,
    FAR,
    ResidueContact,
    compute_many,
    compute_reference_residues,
    deserialise_record,
    target_backbone_signature,
    target_sequence_key,
)

logger = logging.getLogger(__name__)

# How many structures to sample when checking whether the target moves between designs.
TARGET_MOTION_SAMPLE = 3


def params_key(
    record_cutoff: float = DEFAULT_RECORD_CUTOFF,
    probe_radius: float = DEFAULT_PROBE_RADIUS,
    n_points: int = DEFAULT_N_POINTS,
) -> str:
    return f"cut{record_cutoff}_p{probe_radius}_n{n_points}"


PARAMS_KEY = params_key()


def _design_key(run_id: Any, design_id: Any, source_path: Any = None) -> str:
    """Matches the frontend's buildDesignKey and persistence.design_dedupe_key."""
    sp = str(source_path).strip() if source_path is not None and str(source_path).strip() else ""
    return f"{run_id}\x1f{design_id}\x1f{sp}"


@dataclass
class RunContext:
    run_id: str
    run_name: str
    method: str
    binder_chain_ids: List[str]
    target_chain_ids: List[str]
    target_key: str
    residues: List[TargetResidueDto]
    target_moves: bool = False
    error: Optional[str] = None

    @property
    def binder_key(self) -> str:
        return ",".join(sorted(self.binder_chain_ids))

    @property
    def target_chain_key(self) -> str:
        return ",".join(sorted(self.target_chain_ids))

    @property
    def apo_by_label(self) -> Dict[str, float]:
        return {r.label: r.sasa_apo for r in self.residues}

    @property
    def resname_by_label(self) -> Dict[str, str]:
        return {r.label: r.resname for r in self.residues}


def _structure_paths_for_run(run: Dict[str, Any]) -> List[str]:
    return list(run.get("pdb_files", []) or [])


def _design_structure_path(run: Dict[str, Any], design: Dict[str, Any]) -> Optional[Path]:
    filename = str(design.get("pdb_file") or "").strip()
    if not filename:
        return None
    path = _resolve_structure_path(
        _structure_paths_for_run(run), Path(filename).name, run.get("method")
    )
    if path is None or not path.is_file():
        return None
    return path


def _detect_target_motion(structure_paths: Sequence[str], binder_chains: Sequence[str]) -> bool:
    """True when sampled structures disagree on the target's CA coordinates, in which
    case the run-level apo-SASA reference does not apply and apo values must be computed
    per design.
    """
    sample = list(structure_paths)[:TARGET_MOTION_SAMPLE]
    signatures = set()
    for path in sample:
        try:
            signatures.add(target_backbone_signature(path, binder_chains))
        except Exception:
            continue
    return len(signatures) > 1


def get_run_context(run_id: str, *, refresh: bool = False) -> RunContext:
    """Chain roles, target identity and residue catalogue for a run, cached in the
    repository so the (multi-second) reference SASA pass happens once per run.
    """
    run = get_run_metadata(run_id)
    if not run:
        return RunContext(
            run_id=run_id, run_name=run_id, method="", binder_chain_ids=[],
            target_chain_ids=[], target_key="", residues=[], error="Run not found",
        )

    run_name = str((run.get("metadata") or {}).get("name") or run_id)
    method = str(run.get("method") or "")
    structure_paths = _structure_paths_for_run(run)
    roles = resolve_chain_roles_cached(run_id, method, structure_paths)
    binder_ids, target_ids = roles.binder_chain_ids, roles.target_chain_ids
    if not binder_ids or not target_ids or not structure_paths:
        return RunContext(
            run_id=run_id, run_name=run_name, method=method,
            binder_chain_ids=binder_ids, target_chain_ids=target_ids,
            target_key="", residues=[],
            error="Could not resolve binder/target chain roles for this run",
        )

    binder_key = ",".join(sorted(binder_ids))
    target_chain_key = ",".join(sorted(target_ids))
    repo = get_designs_repository()

    if not refresh and repo.is_enabled():
        cached = repo.get_target_residues(
            run_id=run_id,
            params_key=PARAMS_KEY,
            binder_chains=binder_key,
            target_chains=target_chain_key,
        )
        if cached is not None:
            return RunContext(
                run_id=run_id, run_name=run_name, method=method,
                binder_chain_ids=binder_ids, target_chain_ids=target_ids,
                target_key=cached["target_key"],
                residues=[TargetResidueDto(**r) for r in cached["residues"]],
                target_moves=cached["target_moves"],
            )

    try:
        reference = compute_reference_residues(structure_paths[0], binder_ids)
        target_key = target_sequence_key(structure_paths[0], binder_ids)
    except Exception as e:
        logger.warning("target residue catalogue failed for run %s: %s", run_id, e)
        return RunContext(
            run_id=run_id, run_name=run_name, method=method,
            binder_chain_ids=binder_ids, target_chain_ids=target_ids,
            target_key="", residues=[], error=str(e),
        )

    residues = [
        TargetResidueDto(
            label=r.label, chain=r.chain, resseq=r.resseq, icode=r.icode,
            resname=r.resname, aa1=r.aa1, sasa_apo=r.sasa_apo,
        )
        for r in reference
    ]
    target_moves = _detect_target_motion(structure_paths, binder_ids)

    if repo.is_enabled():
        repo.upsert_target_residues(
            run_id=run_id,
            params_key=PARAMS_KEY,
            binder_chains=binder_key,
            target_chains=target_chain_key,
            target_key=target_key,
            residues=[r.model_dump() for r in residues],
            target_moves=target_moves,
        )

    return RunContext(
        run_id=run_id, run_name=run_name, method=method,
        binder_chain_ids=binder_ids, target_chain_ids=target_ids,
        target_key=target_key, residues=residues, target_moves=target_moves,
    )


def _coverage_rows(contexts: Sequence[RunContext]) -> List[TargetContactCoverage]:
    repo = get_designs_repository()
    run_ids = [c.run_id for c in contexts]
    computed = repo.count_target_contacts_by_run(run_ids, PARAMS_KEY) if run_ids else {}
    totals: Dict[str, int] = {}
    for design in get_designs_for_run_ids(run_ids):
        rid = str(design.get("run_id"))
        totals[rid] = totals.get(rid, 0) + 1
    return [
        TargetContactCoverage(
            run_id=c.run_id,
            run_name=c.run_name,
            target_key=c.target_key,
            total_designs=totals.get(c.run_id, 0),
            computed_designs=computed.get(c.run_id, 0),
            target_moves=c.target_moves,
        )
        for c in contexts
    ]


def get_targets(run_ids: List[str]) -> TargetResiduesResponse:
    """Targets present in the run scope, their residue catalogues, and compute coverage.

    Runs are grouped by ``target_key`` (a hash of the target chain sequences), so runs
    against the same target share one entry and one residue list.
    """
    contexts = [get_run_context(run_id) for run_id in run_ids]
    warnings = [f"{c.run_name}: {c.error}" for c in contexts if c.error]

    by_target: Dict[str, List[RunContext]] = {}
    for context in contexts:
        if context.error or not context.target_key:
            continue
        by_target.setdefault(context.target_key, []).append(context)

    targets: List[TargetInfo] = []
    for target_key, group in sorted(by_target.items()):
        first = group[0]
        chain_ids = first.target_chain_ids
        label = f"{'/'.join(chain_ids)} · {len(first.residues)} aa"
        targets.append(
            TargetInfo(
                target_key=target_key,
                label=label,
                run_ids=[c.run_id for c in group],
                chain_ids=chain_ids,
                length=len(first.residues),
                residues=first.residues,
            )
        )

    return TargetResiduesResponse(
        targets=targets, coverage=_coverage_rows(contexts), warnings=warnings
    )


def compute_contacts(request: TargetContactsComputeRequest) -> TargetContactsComputeResponse:
    """Compute and cache per-design contact records, skipping designs already cached."""
    repo = get_designs_repository()
    contexts = {run_id: get_run_context(run_id) for run_id in request.run_ids}
    errors = [f"{c.run_name}: {c.error}" for c in contexts.values() if c.error]

    wanted: Optional[set] = None
    if request.design_keys:
        wanted = {_design_key(k.run_id, k.design_id, k.source_path) for k in request.design_keys}

    cached_hits = 0
    tasks: List[Tuple[str, str, Sequence[str], Optional[Dict[str, float]]]] = []
    task_meta: Dict[str, Dict[str, Any]] = {}

    for design in get_designs_for_run_ids(request.run_ids):
        run_id = str(design.get("run_id"))
        context = contexts.get(run_id)
        if context is None or context.error:
            continue
        design_id = str(design.get("design_id"))
        source_path = design.get("source_path") or ""
        key = _design_key(run_id, design_id, source_path)
        if wanted is not None and key not in wanted:
            continue

        run = get_run_metadata(run_id)
        structure_path = _design_structure_path(run or {}, design)
        if structure_path is None:
            errors.append(f"{design_id}: structure file not found")
            continue
        filename = structure_path.name

        if not request.ignore_cache and repo.is_enabled():
            hit = repo.get_target_contacts_cache(
                run_id=run_id,
                design_id=design_id,
                source_path=str(source_path),
                structure_filename=filename,
                binder_chains=context.binder_key,
                target_chains=context.target_chain_key,
                params_key=PARAMS_KEY,
            )
            if hit is not None:
                cached_hits += 1
                continue

        apo = None if context.target_moves else context.apo_by_label
        tasks.append((key, str(structure_path), context.binder_chain_ids, apo))
        task_meta[key] = {
            "run_id": run_id,
            "design_id": design_id,
            "source_path": str(source_path),
            "structure_filename": filename,
            "binder_chains": context.binder_key,
            "target_chains": context.target_chain_key,
        }

    results = compute_many(tasks, max_workers=request.max_workers)

    to_write: List[Dict[str, Any]] = []
    failed = 0
    for key, (record, error) in results.items():
        if error or record is None:
            failed += 1
            if len(errors) < 20:
                errors.append(f"{task_meta[key]['design_id']}: {error}")
            continue
        to_write.append({**task_meta[key], "params_key": PARAMS_KEY, "contacts": record})

    if to_write and repo.is_enabled():
        repo.upsert_target_contacts_cache_bulk(to_write)

    return TargetContactsComputeResponse(
        computed=len(to_write),
        cached=cached_hits,
        failed=failed,
        errors=errors,
        coverage=_coverage_rows(list(contexts.values())),
    )


@dataclass
class ContactData:
    """Everything the filter and profile evaluators need for a run scope."""

    records: Dict[str, Dict[str, ResidueContact]] = field(default_factory=dict)
    contexts: Dict[str, RunContext] = field(default_factory=dict)

    def context_for_run(self, run_id: str) -> Optional[RunContext]:
        return self.contexts.get(run_id)


def load_contact_data(run_ids: List[str]) -> ContactData:
    repo = get_designs_repository()
    contexts = {run_id: get_run_context(run_id) for run_id in run_ids}
    records: Dict[str, Dict[str, ResidueContact]] = {}
    for row in repo.list_target_contacts_for_runs(run_ids, PARAMS_KEY):
        key = _design_key(row["run_id"], row["design_id"], row.get("source_path"))
        records[key] = deserialise_record(row["contacts"]).contacts
    return ContactData(records=records, contexts=contexts)


def _metric_value(
    contact: Optional[ResidueContact],
    spec_metric: str,
    distance_type: str,
    unit: str,
    resname: Optional[str],
    apo_sasa: Optional[float],
) -> Optional[float]:
    """The requested metric for one residue of one design.

    ``contact`` is None for a residue outside the record cutoff, which is not missing
    data: such a residue is far from the binder, so its distance exceeds the cutoff and
    its bound SASA equals its apo SASA with no change on binding (see the module
    docstring of target_contacts).
    """
    if spec_metric == "distance":
        if contact is None:
            return FAR
        return {"ca": contact.d_ca, "cb": contact.d_cb, "heavy": contact.d_heavy}[distance_type]

    if apo_sasa is None:
        return None

    if spec_metric == "sasa_bound":
        value = apo_sasa if contact is None else contact.sasa_bound
    elif spec_metric == "delta_sasa":
        if contact is None:
            value = 0.0
        else:
            reference = contact.sasa_apo if contact.sasa_apo is not None else apo_sasa
            value = reference - contact.sasa_bound
    else:
        return None

    if unit == "percent":
        max_sasa = TIEN_2023_THEORETICAL.get((resname or "").upper())
        if not max_sasa:
            return None
        return 100.0 * value / max_sasa
    return value


_OPERATORS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


def evaluate_contact_filter(
    spec: TargetContactFilterSpec,
    contacts: Optional[Dict[str, ResidueContact]],
    context: RunContext,
) -> bool:
    """Whether one design satisfies one condition.

    Residues the run does not have at all are skipped (the condition does not apply to
    them). A design with no computed record at all fails, rather than silently passing:
    the UI surfaces that as missing coverage with a Compute button.
    """
    apo_by_label = context.apo_by_label
    resname_by_label = context.resname_by_label

    known = [label for label in spec.residues if label in apo_by_label]
    if not known:
        return True
    if contacts is None:
        return False

    compare = _OPERATORS[spec.operator]

    if spec.scope == "site_percent":
        total = 0.0
        max_total = 0.0
        for label in known:
            resname = resname_by_label.get(label)
            max_sasa = TIEN_2023_THEORETICAL.get((resname or "").upper())
            value = _metric_value(
                contacts.get(label), spec.metric, spec.distance_type, "angstrom",
                resname, apo_by_label.get(label),
            )
            if value is None or not max_sasa:
                continue
            total += value
            max_total += max_sasa
        if max_total <= 0:
            return True
        return compare(100.0 * total / max_total, spec.value)

    passes = 0
    evaluated = 0
    for label in known:
        value = _metric_value(
            contacts.get(label), spec.metric, spec.distance_type, spec.unit,
            resname_by_label.get(label), apo_by_label.get(label),
        )
        if value is None:
            continue
        evaluated += 1
        if compare(value, spec.value):
            passes += 1

    if evaluated == 0:
        return True
    if spec.scope == "all":
        return passes == evaluated
    if spec.scope == "count":
        return passes >= (spec.min_count or 1)
    return passes > 0


def describe_contact_filter(spec: TargetContactFilterSpec, group_label: Optional[str]) -> str:
    residues = ",".join(spec.residues[:4]) + ("…" if len(spec.residues) > 4 else "")
    scope = {
        "any": "any of",
        "all": "all of",
        "count": f"≥{spec.min_count or 1} of",
        "site_percent": "site total over",
    }[spec.scope]
    unit = "Å" if spec.metric == "distance" else ("%" if spec.unit == "percent" else "Å²")
    metric = {
        "distance": f"{spec.distance_type} distance",
        "sasa_bound": "SASA when bound",
        "delta_sasa": "ΔSASA on binding",
    }[spec.metric]
    body = f"{scope} {residues}: {metric} {spec.operator} {spec.value}{unit}"
    return f"{group_label}: {body}" if group_label else body


@dataclass
class FilterInputs:
    df: pl.DataFrame
    specs: List[FilterSpec]
    labels: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


def augment_with_target_contacts(
    df: pl.DataFrame, groups: Sequence[TargetContactGroup], run_ids: List[str]
) -> Tuple[pl.DataFrame, List[FilterSpec], Dict[str, str], List[str]]:
    """Append one boolean column per contact condition, plus the FilterSpecs selecting
    on them. Designs outside a group's run scope are set True (the group does not apply
    to them).
    """
    active = [g for g in groups if g.filters]
    if not active or df.is_empty():
        return df, [], {}, []

    data = load_contact_data(run_ids)
    warnings: List[str] = []
    specs: List[FilterSpec] = []
    labels: Dict[str, str] = {}
    columns: List[pl.Series] = []

    design_keys = [
        _design_key(row["run_id"], row["design_id"], row.get("source_path"))
        for row in df.select(
            [c for c in ("run_id", "design_id", "source_path") if c in df.columns]
        ).iter_rows(named=True)
    ]
    run_id_col = df["run_id"].cast(pl.Utf8).to_list() if "run_id" in df.columns else []

    for g_index, group in enumerate(active):
        scope_run_ids = set(group.run_ids) if group.run_ids else {
            rid for rid, ctx in data.contexts.items() if ctx.target_key == group.target_key
        }
        missing = [
            rid for rid in scope_run_ids
            if (ctx := data.contexts.get(rid)) is not None and ctx.error
        ]
        for rid in missing:
            warnings.append(f"{data.contexts[rid].run_name}: {data.contexts[rid].error}")

        for f_index, spec in enumerate(group.filters):
            column = f"__tc_{g_index}_{f_index}"
            values: List[bool] = []
            for row_index, key in enumerate(design_keys):
                run_id = run_id_col[row_index] if row_index < len(run_id_col) else ""
                if run_id not in scope_run_ids:
                    values.append(True)
                    continue
                context = data.contexts.get(run_id)
                if context is None or context.error:
                    values.append(False)
                    continue
                values.append(
                    evaluate_contact_filter(spec, data.records.get(key), context)
                )
            columns.append(pl.Series(column, values, dtype=pl.Boolean))
            specs.append(FilterSpec(column=column, operator="equals", text_value="true"))
            labels[column] = describe_contact_filter(spec, group.label)

    return df.with_columns(columns), specs, labels, warnings


def contact_filter_columns(df: pl.DataFrame) -> List[str]:
    return [c for c in df.columns if c.startswith("__tc_")]


def compute_profile(request: TargetContactProfileRequest) -> TargetContactProfileResponse:
    """Per-residue aggregate across a design set, for the viewer's colour map."""
    data = load_contact_data(request.run_ids)
    contexts = [
        c for c in data.contexts.values()
        if not c.error and (not request.target_key or c.target_key == request.target_key)
    ]
    if not contexts:
        return TargetContactProfileResponse(
            target_key=request.target_key or "",
            warnings=["No run in scope has a resolved target for this target_key."],
        )

    scope_run_ids = {c.run_id for c in contexts}
    reference = contexts[0]
    apo_by_label = reference.apo_by_label
    resname_by_label = reference.resname_by_label

    wanted: Optional[set] = None
    if request.design_keys:
        wanted = {_design_key(k.run_id, k.design_id, k.source_path) for k in request.design_keys}

    selected: List[Dict[str, ResidueContact]] = []
    for design in get_designs_for_run_ids(sorted(scope_run_ids)):
        run_id = str(design.get("run_id"))
        if run_id not in scope_run_ids:
            continue
        key = _design_key(run_id, design.get("design_id"), design.get("source_path"))
        if wanted is not None and key not in wanted:
            continue
        record = data.records.get(key)
        if record is None:
            continue
        selected.append(record)

    warnings: List[str] = []
    if not selected:
        warnings.append(
            "No design in the selection has computed target contacts yet. "
            "Use Compute target contacts first."
        )

    rows: List[TargetContactProfileRow] = []
    for residue in reference.residues:
        label = residue.label
        values: List[float] = []
        contacted = 0
        for record in selected:
            contact = record.get(label)
            if request.metric == "contact_frequency":
                metric_value = _metric_value(
                    contact,
                    "distance" if request.contact_metric == "distance" else "delta_sasa",
                    request.distance_type,
                    "angstrom",
                    resname_by_label.get(label),
                    apo_by_label.get(label),
                )
                if metric_value is None:
                    continue
                is_contact = (
                    metric_value <= request.contact_threshold
                    if request.contact_metric == "distance"
                    else metric_value >= request.contact_threshold
                )
                values.append(1.0 if is_contact else 0.0)
                contacted += 1 if is_contact else 0
                continue

            metric_value = _metric_value(
                contact,
                "delta_sasa" if request.metric == "delta_sasa" else "distance",
                request.distance_type,
                request.unit if request.metric == "delta_sasa" else "angstrom",
                resname_by_label.get(label),
                apo_by_label.get(label),
            )
            if metric_value is None:
                continue
            values.append(metric_value)
            if contact is not None:
                contacted += 1

        if not values:
            rows.append(
                TargetContactProfileRow(
                    label=label, chain=residue.chain, resseq=residue.resseq,
                    resname=residue.resname, aa1=residue.aa1, n=0,
                )
            )
            continue

        ordered = sorted(values)
        midpoint = len(ordered) // 2
        median = (
            ordered[midpoint]
            if len(ordered) % 2
            else (ordered[midpoint - 1] + ordered[midpoint]) / 2
        )
        rows.append(
            TargetContactProfileRow(
                label=label,
                chain=residue.chain,
                resseq=residue.resseq,
                resname=residue.resname,
                aa1=residue.aa1,
                mean=round(sum(values) / len(values), 3),
                median=round(median, 3),
                min=round(ordered[0], 3),
                max=round(ordered[-1], 3),
                contact_fraction=round(contacted / len(selected), 4) if selected else 0.0,
                n=len(values),
            )
        )

    return TargetContactProfileResponse(
        target_key=reference.target_key,
        residues=rows,
        n_designs=len(selected),
        warnings=warnings,
    )
