"""Binder-sequence FASTA export for download bundles.

The field probe order mirrors the frontend's (``onDownloadFasta`` in DesignsView.vue) so
a bundle's binders.fasta and the tab's quick FASTA download never disagree about which
column is "the sequence". Seeded from persistence.protocol.SEQUENCE_EXTRA_KEYS rather
than hardcoding a third copy of that list.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, TextIO, Tuple

from ..persistence.protocol import SEQUENCE_EXTRA_KEYS

# Order matters (first hit wins); SEQUENCE_EXTRA_KEYS is an unordered frozenset, so it
# seeds membership while this tuple fixes precedence.
SEQUENCE_FIELD_CANDIDATES: Tuple[str, ...] = (
    "Sequence",
    "sequence",
    "binder_sequence",
    "binder_seq",
    "seq",
)

_UNSEEDED = tuple(k for k in SEQUENCE_FIELD_CANDIDATES if k not in SEQUENCE_EXTRA_KEYS)

DEFAULT_HEADER_FIELDS: Tuple[str, ...] = ("run_id", "final_rank")


def pick_sequence(row: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """The (field name, sequence) this row's binder sequence comes from, or (None, None)."""
    for field in SEQUENCE_FIELD_CANDIDATES:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return field, value.strip()
    return None, None


def _header(row: Dict[str, Any], header_fields: Iterable[str]) -> str:
    design_id = str(row.get("design_id") or "design")
    extras: List[str] = []
    for field in header_fields:
        value = row.get(field)
        if value is None or value == "":
            continue
        extras.append(f"{field}={value}")
    return design_id if not extras else f"{design_id} {' '.join(extras)}"


def write_binder_fasta(
    fh: TextIO,
    rows: List[Dict[str, Any]],
    *,
    header_fields: Iterable[str] = DEFAULT_HEADER_FIELDS,
    line_width: int = 60,
) -> Tuple[int, int]:
    """Write binder sequences as FASTA. Returns (records written, rows skipped)."""
    fields = tuple(header_fields)
    written = 0
    skipped = 0
    for row in rows:
        _, sequence = pick_sequence(row)
        if not sequence:
            skipped += 1
            continue
        fh.write(f">{_header(row, fields)}\n")
        if line_width and line_width > 0:
            for start in range(0, len(sequence), line_width):
                fh.write(sequence[start : start + line_width] + "\n")
        else:
            fh.write(sequence + "\n")
        written += 1
    return written, skipped


def write_sequence_fasta(
    fh: TextIO,
    records: Iterable[Tuple[str, str]],
    *,
    line_width: int = 60,
) -> int:
    """Write (header, sequence) pairs as FASTA. Used for prepared constructs, where the
    header is a vendor short name rather than a design id."""
    written = 0
    for header, sequence in records:
        seq = (sequence or "").strip()
        if not seq:
            continue
        fh.write(f">{header}\n")
        if line_width and line_width > 0:
            for start in range(0, len(seq), line_width):
                fh.write(seq[start : start + line_width] + "\n")
        else:
            fh.write(seq + "\n")
        written += 1
    return written
