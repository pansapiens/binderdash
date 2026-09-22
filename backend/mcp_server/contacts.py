"""Target-contact filtering, shared by every tool that takes hard filters.

A contact condition ("A166 within 5 A of the binder", "the epitope buries at least 30%
on binding") cannot be expressed as a threshold on a design-table column, because it is
derived from the design's structure rather than its results table. The filtering service
evaluates each condition into a boolean ``__tc_*`` column and hands back a FilterSpec
selecting on it, so the tools here treat contact conditions as ordinary hard filters and
only have to strip the virtual columns before returning rows.

Computing the underlying per-residue records is deliberately not exposed as a tool: it
parses every structure in the selection and takes minutes, so it belongs behind the web
UI's Compute button. When records are missing, tools say so rather than reporting the
resulting empty selection as a real answer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import polars as pl

from . import errors

VIRTUAL_PREFIX = "__tc_"

NOT_COMPUTED_HINT = (
    "Target contacts have not been computed for these runs. Open the Filtering tab in "
    "the Binderdash web UI and press 'Compute target contacts' for the runs in scope; "
    "it parses every structure, so it is not available as a tool call."
)


def build_inputs(
    run_ids: Sequence[str],
    filters: Sequence[Dict[str, Any]],
    target_contact_groups: Optional[Sequence[Dict[str, Any]]] = None,
) -> Tuple[Any, List[Dict[str, Any]]]:
    """(FilterInputs, warnings) for a selection, with contact conditions already
    evaluated into ``__tc_*`` columns."""
    from ..filtering.schemas import FilterSpec, TargetContactGroup
    from ..filtering.service import build_filter_inputs

    specs = [FilterSpec(**f) for f in filters]
    try:
        groups = [TargetContactGroup(**g) for g in (target_contact_groups or [])]
    except Exception as exc:  # pydantic validation
        errors.fail(
            errors.INVALID_TARGET_CONTACT_FILTER,
            f"target_contact_groups is malformed: {exc}. Call list_target_residues for "
            "the target_key and the residue labels to write conditions against.",
        )

    inputs = build_filter_inputs(list(run_ids), specs, groups or None)
    warnings = [
        errors.warning(errors.TARGET_CONTACTS_UNAVAILABLE, message)
        for message in inputs.warnings
    ]
    return inputs, warnings


def strip_virtual(df: pl.DataFrame) -> pl.DataFrame:
    """Drop the internal boolean columns so they never reach the caller."""
    virtual = [c for c in df.columns if c.startswith(VIRTUAL_PREFIX)]
    return df.drop(virtual, strict=False) if virtual else df


def empty_selection_hint(
    target_contact_groups: Optional[Sequence[Dict[str, Any]]],
    warnings: Sequence[Dict[str, Any]],
) -> str:
    """Extra sentence for an EMPTY_SELECTION message when contact filters were in play.

    A design whose contacts were never computed fails every contact condition, so an
    uncomputed run looks exactly like a threshold nobody meets.
    """
    if not target_contact_groups:
        return ""
    if any(w.get("code") == errors.TARGET_CONTACTS_UNAVAILABLE for w in warnings):
        return " " + NOT_COMPUTED_HINT
    return (
        " Contact conditions were applied; check them against list_target_residues "
        "and target_contact_profile, which shows what the binders actually touch."
    )

