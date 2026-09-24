"""BundleSpec: a resolved, source-agnostic description of a bundle's contents.

Resolution and serialisation are separate phases. Both sources (a live table selection
and a saved set) produce one of these, holding plain design dicts and already-validated
filesystem paths, so the writer never touches the database and never needs to know where
the rows came from. That is what keeps the three download entry points on one code path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    BundleCoverage,
    BundleEstimate,
    BundleKind,
    BundleProvenance,
    PrepareSequencesPayload,
    TargetContactsReference,
)
from ..session_state import SessionState


@dataclass(frozen=True)
class StructureRef:
    arcname: str
    path: Path
    size_bytes: int
    run_id: str
    design_id: str


@dataclass
class ContactExport:
    """Cached target-contact values for the bundled designs. Never computed on demand."""

    rows: List[Dict[str, Any]] = field(default_factory=list)
    reference: Optional[TargetContactsReference] = None
    designs_with_contacts: int = 0
    designs_without_contacts: int = 0
    params_key: Optional[str] = None

    def __bool__(self) -> bool:
        return bool(self.rows) or bool(self.reference and self.reference.runs)


@dataclass
class BundleCaps:
    max_structure_files: int
    max_structure_bytes: int
    max_total_bytes: int


@dataclass
class BundleSpec:
    kind: BundleKind
    bundle_id: str
    created_at: str
    label: str
    provenance: BundleProvenance
    rows: List[Dict[str, Any]] = field(default_factory=list)
    structures: List[StructureRef] = field(default_factory=list)
    structures_requested: int = 0
    contacts: Optional[ContactExport] = None
    session: Optional[SessionState] = None
    prepared: Optional[PrepareSequencesPayload] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def structure_bytes(self) -> int:
        return sum(s.size_bytes for s in self.structures)

    @property
    def structures_missing(self) -> int:
        return max(0, self.structures_requested - len(self.structures))

    def coverage(self) -> BundleCoverage:
        from ..util.design_fasta import pick_sequence

        with_seq = sum(1 for row in self.rows if pick_sequence(row)[1])
        contacts = self.contacts
        return BundleCoverage(
            designs=len(self.rows),
            designs_with_sequence=with_seq,
            designs_without_sequence=len(self.rows) - with_seq,
            structures_requested=self.structures_requested,
            structures_included=len(self.structures),
            structures_missing=self.structures_missing,
            designs_with_contacts=contacts.designs_with_contacts if contacts else 0,
            designs_without_contacts=(
                contacts.designs_without_contacts if contacts else len(self.rows)
            ),
            contact_params_key=contacts.params_key if contacts else None,
            constructs=len(self.prepared.rows) if self.prepared else 0,
        )


class BundleCapsError(Exception):
    """A request whose structure payload exceeds a configured cap.

    Carries the estimate so the caller can report the measured size rather than just
    "too big".
    """

    def __init__(self, estimate: BundleEstimate) -> None:
        super().__init__("; ".join(estimate.cap_messages) or "Bundle exceeds size limits")
        self.estimate = estimate


def _human_bytes(value: int) -> str:
    step = 1024.0
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < step or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= step
    return f"{size:.1f} TB"


# Rough deflate ratio for PDB/CIF text, used only for the pre-flight estimate the UI
# shows. The archive's real size is measured after the build.
_STRUCTURE_COMPRESSION_RATIO = 0.35
_BYTES_PER_TABLE_CELL = 12
_BYTES_PER_CONTACT_ROW = 120


def estimate(spec: BundleSpec, caps: BundleCaps) -> BundleEstimate:
    structure_bytes = spec.structure_bytes
    column_guess = max(1, len(spec.rows[0]) if spec.rows else 1)
    tables_bytes = len(spec.rows) * column_guess * _BYTES_PER_TABLE_CELL
    contacts_rows = len(spec.contacts.rows) if spec.contacts else 0
    tables_bytes += contacts_rows * _BYTES_PER_CONTACT_ROW

    result = BundleEstimate(
        design_count=len(spec.rows),
        structure_count=len(spec.structures),
        structures_missing=spec.structures_missing,
        structure_bytes=structure_bytes,
        tables_bytes_estimate=tables_bytes,
        estimated_zip_bytes=int(structure_bytes * _STRUCTURE_COMPRESSION_RATIO)
        + int(tables_bytes * 0.3),
        contacts_rows=contacts_rows,
        designs_with_contacts=(
            spec.contacts.designs_with_contacts if spec.contacts else 0
        ),
        max_structure_files=caps.max_structure_files,
        max_structure_bytes=caps.max_structure_bytes,
        max_total_bytes=caps.max_total_bytes,
        warnings=list(spec.warnings),
    )

    messages: List[str] = []
    if caps.max_structure_files and len(spec.structures) > caps.max_structure_files:
        messages.append(
            f"{len(spec.structures)} structure files exceeds the limit of "
            f"{caps.max_structure_files}"
        )
    if caps.max_structure_bytes and structure_bytes > caps.max_structure_bytes:
        messages.append(
            f"{_human_bytes(structure_bytes)} of structure files exceeds the limit of "
            f"{_human_bytes(caps.max_structure_bytes)}"
        )
    if caps.max_total_bytes and result.estimated_zip_bytes > caps.max_total_bytes:
        messages.append(
            f"estimated bundle size {_human_bytes(result.estimated_zip_bytes)} exceeds "
            f"the limit of {_human_bytes(caps.max_total_bytes)}"
        )
    result.cap_messages = messages
    result.exceeds_cap = bool(messages)
    return result


def check_caps(spec: BundleSpec, caps: BundleCaps) -> BundleEstimate:
    result = estimate(spec, caps)
    if result.exceeds_cap:
        raise BundleCapsError(result)
    return result
