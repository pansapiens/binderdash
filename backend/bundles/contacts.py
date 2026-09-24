"""Cached target-contact SASA values, flattened for export.

Read-only by design: a download must never kick off a SASA computation, which is
minutes-scale for a large design set. Designs with no cached record are simply reported
as uncovered in the manifest.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import (
    ContactReferenceResidue,
    ContactReferenceRun,
    TargetContactsReference,
)
from .spec import ContactExport
from ..filtering.target_contacts import (
    DEFAULT_RECORD_CUTOFF,
    ResidueContact,
    delta_sasa_percent,
)
from ..filtering.target_contacts_service import (
    PARAMS_KEY,
    RunContext,
    load_contact_data,
)

logger = logging.getLogger(__name__)

CONTACT_COLUMNS: Tuple[str, ...] = (
    "run_id",
    "design_id",
    "source_path",
    "residue_label",
    "chain",
    "resseq",
    "icode",
    "resname",
    "d_ca",
    "d_cb",
    "d_heavy",
    "sasa_bound",
    "sasa_apo",
    "delta_sasa",
    "delta_sasa_percent",
)


def _design_key(run_id: Any, design_id: Any, source_path: Any = None) -> str:
    sp = str(source_path).strip() if source_path is not None and str(source_path).strip() else ""
    return f"{run_id}\x1f{design_id}\x1f{sp}"


def _resolve_apo(
    contact: ResidueContact, label: str, context: Optional[RunContext]
) -> Optional[float]:
    """Per-design apo SASA wins over the run reference.

    ``ResidueContact.sasa_apo`` is None for the usual fixed-target run, where the
    run-level reference map applies. It is only populated for runs whose target moves
    between designs - exactly the runs where using the shared reference would give the
    wrong delta.
    """
    if contact.sasa_apo is not None:
        return contact.sasa_apo
    if context is None:
        return None
    return context.apo_by_label.get(label)


def _reference_run(context: RunContext) -> ContactReferenceRun:
    return ContactReferenceRun(
        run_id=context.run_id,
        run_name=context.run_name or "",
        method=context.method or "",
        target_key=context.target_key or "",
        binder_chain_ids=list(context.binder_chain_ids),
        target_chain_ids=list(context.target_chain_ids),
        target_moves=bool(context.target_moves),
        error=context.error,
        residues=[
            ContactReferenceResidue(
                label=r.label,
                chain=r.chain,
                resseq=r.resseq,
                icode=r.icode,
                resname=r.resname,
                aa1=r.aa1,
                sasa_apo=r.sasa_apo,
            )
            for r in context.residues
        ],
    )


def build_contact_export(
    run_ids: Iterable[str],
    rows: List[Dict[str, Any]],
) -> Optional[ContactExport]:
    """Flatten cached contacts for the given design rows, or None if nothing is cached."""
    ids = [str(r) for r in dict.fromkeys(run_ids) if str(r)]
    if not ids or not rows:
        return None

    try:
        data = load_contact_data(ids)
    except Exception as e:
        logger.warning("target contacts unavailable for bundle: %s", e)
        return None

    if not data.records:
        return None

    out_rows: List[Dict[str, Any]] = []
    covered = 0
    for row in rows:
        run_id = str(row.get("run_id") or "")
        design_id = str(row.get("design_id") or "")
        source_path = row.get("source_path")
        record = data.records.get(_design_key(run_id, design_id, source_path))
        if not record:
            continue
        covered += 1
        context = data.context_for_run(run_id)
        resname_by_label = context.resname_by_label if context else {}
        residue_by_label = {r.label: r for r in (context.residues if context else [])}
        for label, contact in record.items():
            resname = resname_by_label.get(label, "")
            apo = _resolve_apo(contact, label, context)
            delta = None if apo is None else apo - contact.sasa_bound
            residue = residue_by_label.get(label)
            out_rows.append(
                {
                    "run_id": run_id,
                    "design_id": design_id,
                    "source_path": source_path or "",
                    "residue_label": label,
                    "chain": residue.chain if residue else "",
                    "resseq": residue.resseq if residue else "",
                    "icode": (residue.icode if residue else "").strip(),
                    "resname": resname,
                    "d_ca": contact.d_ca,
                    "d_cb": contact.d_cb,
                    "d_heavy": contact.d_heavy,
                    "sasa_bound": contact.sasa_bound,
                    "sasa_apo": apo,
                    "delta_sasa": delta,
                    "delta_sasa_percent": (
                        None
                        if delta is None or not resname
                        else delta_sasa_percent(resname, delta)
                    ),
                }
            )

    if not out_rows:
        return None

    reference = TargetContactsReference(
        params_key=PARAMS_KEY,
        record_cutoff_angstrom=DEFAULT_RECORD_CUTOFF,
        runs=[
            _reference_run(context)
            for context in data.contexts.values()
            if context is not None
        ],
    )

    return ContactExport(
        rows=out_rows,
        reference=reference,
        designs_with_contacts=covered,
        designs_without_contacts=len(rows) - covered,
        params_key=PARAMS_KEY,
    )
