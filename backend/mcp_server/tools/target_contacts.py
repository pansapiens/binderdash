"""Target-contact tools: what the target offers, and what the binders touch.

These are the read side of the feature. Computing the per-residue records is not a tool
- it parses every structure in the selection - so it stays behind the web UI's Compute
button; see contacts.NOT_COMPUTED_HINT.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import Field

from .. import contacts, errors, refs, tables
from ..descriptions import LIST_TARGET_RESIDUES, TARGET_CONTACT_PROFILE
from ..server import run_blocking

# A target is typically 100-300 residues; the catalogue is the point of the tool, but a
# multi-target selection of long chains would otherwise blow the budget in one call.
RESIDUE_FIELDS = 5


def _targets(run_ids: List[str], include_residues: bool) -> Dict[str, Any]:
    from ...filtering.target_contacts_service import get_targets

    refs.validate_run_ids(run_ids)
    response = get_targets(run_ids)
    if not response.targets:
        errors.fail(
            errors.EMPTY_SELECTION,
            f"No target chain could be resolved for {run_ids}. "
            + (
                "; ".join(response.warnings)
                or "These runs may have no target chain in their structures."
            ),
        )

    if include_residues:
        total = sum(len(t.residues) for t in response.targets)
        tables.enforce_cell_budget(
            total, RESIDUE_FIELDS, "Re-call with include_residues=false, or fewer run_ids."
        )

    targets = []
    for target in response.targets:
        entry: Dict[str, Any] = {
            "target_key": target.target_key,
            "label": target.label,
            "run_ids": target.run_ids,
            "chain_ids": target.chain_ids,
            "length": target.length,
            "sequence": "".join(r.aa1 for r in target.residues),
        }
        if include_residues:
            entry["residue_columns"] = ["label", "chain", "resseq", "resname", "sasa_apo"]
            entry["residues"] = [
                [
                    r.label,
                    r.chain,
                    r.resseq,
                    r.resname,
                    tables.clean_cell(r.sasa_apo),
                ]
                for r in target.residues
            ]
        targets.append(entry)

    coverage = [c.model_dump() for c in response.coverage]
    warnings = [
        errors.warning(errors.TARGET_CONTACTS_UNAVAILABLE, message)
        for message in response.warnings
    ]
    uncomputed = [c for c in coverage if c["computed_designs"] < c["total_designs"]]
    if uncomputed:
        warnings.append(
            errors.warning(
                errors.TARGET_CONTACTS_UNAVAILABLE,
                "Some designs have no computed contacts and will fail every contact "
                "condition. " + contacts.NOT_COMPUTED_HINT,
                {
                    c["run_id"]: f"{c['computed_designs']}/{c['total_designs']}"
                    for c in uncomputed
                },
            )
        )

    return {"targets": targets, "coverage": coverage, "warnings": warnings}


def _profile(
    run_ids: List[str],
    target_key: Optional[str],
    metric: str,
    unit: str,
    distance_type: str,
    contact_metric: str,
    contact_threshold: float,
    design_keys: Optional[List[Dict[str, Any]]],
    include_all: bool,
    limit: int,
) -> Dict[str, Any]:
    from ...filtering.schemas import DesignKey, TargetContactProfileRequest
    from ...filtering.target_contacts_service import compute_profile

    refs.validate_run_ids(run_ids)
    request = TargetContactProfileRequest(
        run_ids=run_ids,
        design_keys=[DesignKey(**k) for k in (design_keys or [])],
        target_key=target_key,
        metric=metric,  # type: ignore[arg-type]
        unit=unit,  # type: ignore[arg-type]
        distance_type=distance_type,  # type: ignore[arg-type]
        contact_metric=contact_metric,  # type: ignore[arg-type]
        contact_threshold=contact_threshold,
    )
    response = compute_profile(request)
    if response.n_designs == 0:
        errors.fail(
            errors.EMPTY_SELECTION,
            "No design in this selection has computed target contacts, so there is "
            "nothing to profile. " + contacts.NOT_COMPUTED_HINT,
        )

    rows = list(response.residues)
    if not include_all:
        # Contacts are only recorded within 12 A of the binder, so contact_fraction > 0
        # means "some design came near this residue at all". On a 300-residue target the
        # rest is most of the response and carries no information.
        rows = [r for r in rows if r.n and r.contact_fraction > 0]
    # Most interesting first: the residues the binders bury hardest, or approach closest.
    ascending = metric == "distance"
    rows.sort(
        key=lambda r: (r.mean if r.mean is not None else (float("inf") if ascending else -1.0)),
        reverse=not ascending,
    )
    truncated = len(rows) > limit
    rows = rows[:limit]

    columns = ["label", "chain", "resseq", "resname", "mean", "median", "min", "max",
               "contact_fraction", "n"]
    warnings = [
        errors.warning(errors.TARGET_CONTACTS_UNAVAILABLE, message)
        for message in response.warnings
    ]
    if truncated:
        warnings.append(
            errors.warning(
                errors.TRUNCATED,
                f"Showing the top {limit} residues by {metric}; raise limit for more.",
            )
        )
    return tables.build_table(
        [r.model_dump() for r in rows],
        columns,
        total_matching=len(response.residues),
        warnings=warnings,
        extra={
            "target_key": response.target_key,
            "n_designs": response.n_designs,
            "metric": metric,
            "unit": unit,
            "distance_type": distance_type,
        },
    )


def register(mcp: Any) -> None:
    @mcp.tool(description=LIST_TARGET_RESIDUES)
    async def list_target_residues(
        run_ids: Annotated[List[str], Field(description="Runs to resolve targets for.")],
        include_residues: Annotated[
            bool, Field(description="Include the per-residue catalogue, not just the summary.")
        ] = True,
    ) -> Dict[str, Any]:
        return await run_blocking(_targets, run_ids, include_residues, heavy=True)

    @mcp.tool(description=TARGET_CONTACT_PROFILE)
    async def target_contact_profile(
        run_ids: Annotated[List[str], Field(description="Runs to profile.")],
        target_key: Annotated[
            Optional[str],
            Field(description="From list_target_residues; required when runs use several targets."),
        ] = None,
        metric: Annotated[
            Literal["delta_sasa", "contact_frequency", "distance"],
            Field(description="What to summarise per residue."),
        ] = "delta_sasa",
        unit: Annotated[
            Literal["angstrom", "percent"],
            Field(description="A^2/A, or percent of the residue's theoretical maximum SASA."),
        ] = "angstrom",
        distance_type: Annotated[
            Literal["ca", "cb", "heavy"], Field(description="Which atoms distances are measured between.")
        ] = "heavy",
        contact_metric: Annotated[
            Literal["distance", "delta_sasa"],
            Field(description="What counts as a contact, for metric='contact_frequency'."),
        ] = "distance",
        contact_threshold: Annotated[
            float, Field(description="Contact cutoff: <= for distance, >= for delta_sasa.")
        ] = 5.0,
        design_keys: Annotated[
            Optional[List[Dict[str, Any]]],
            Field(description="Restrict to specific designs, each {run_id, design_id, source_path?}."),
        ] = None,
        include_all: Annotated[
            bool, Field(description="Include residues no binder ever contacts.")
        ] = False,
        limit: Annotated[int, Field(ge=1, le=400, description="Residues to return.")] = 60,
    ) -> Dict[str, Any]:
        return await run_blocking(
            _profile,
            run_ids,
            target_key,
            metric,
            unit,
            distance_type,
            contact_metric,
            contact_threshold,
            design_keys,
            include_all,
            limit,
            heavy=True,
        )
