"""One writer per bundle member. Each streams into the open zip and returns its digest."""

from __future__ import annotations

import csv
import json
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from .contacts import CONTACT_COLUMNS
from .hashing import MemberDigest, text_member
from .models import PrepareSequencesPayload
from .spec import ContactExport
from ..util.design_fasta import write_binder_fasta, write_sequence_fasta
from ..util.design_list import design_columns, write_designs_tsv

# Presentational fields from the frontend's PreparedRow: coloured segment spans and
# duplicate display strings. Accepted on input (extra="allow") but kept out of the
# archive, which should be data rather than a snapshot of one UI's rendering.
PREPARED_ROW_EXCLUDE = {
    "segments_aa",
    "segments_aa_display",
    "segments_dna",
    "prepared_aa_display",
    "design_filter_text",
}

CONSTRUCT_COLUMNS: Tuple[str, ...] = (
    "short_name",
    "design_id",
    "run_id",
    "run_name",
    "project_id",
    "tag",
    "original_sequence",
    "prepared_aa",
    "prepared_dna",
    "aa_length",
    "dna_length",
    "extinction_coeff_reduced",
    "extinction_coeff_oxidized",
    "isoelectric_point",
    "warnings",
)


def write_designs_table(
    zf: zipfile.ZipFile, arcname: str, rows: List[Dict[str, Any]]
) -> MemberDigest:
    columns = design_columns(rows)
    with text_member(zf, arcname) as (fh, digest):
        write_designs_tsv(fh, rows, columns=columns)
    return digest


def write_binders_fasta(
    zf: zipfile.ZipFile, arcname: str, rows: List[Dict[str, Any]]
) -> Tuple[MemberDigest, int, int]:
    with text_member(zf, arcname) as (fh, digest):
        written, skipped = write_binder_fasta(fh, rows)
    return digest, written, skipped


def write_contacts_table(
    zf: zipfile.ZipFile, arcname: str, contacts: ContactExport
) -> MemberDigest:
    with text_member(zf, arcname) as (fh, digest):
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(CONTACT_COLUMNS)
        for row in contacts.rows:
            writer.writerow(
                ["" if row.get(col) is None else row.get(col) for col in CONTACT_COLUMNS]
            )
    return digest


def _construct_cell(row: Dict[str, Any], column: str) -> Any:
    if column == "aa_length":
        return len(str(row.get("prepared_aa") or ""))
    if column == "dna_length":
        dna = row.get("prepared_dna")
        return len(str(dna)) if dna else ""
    if column == "warnings":
        warnings = row.get("warnings") or []
        return "; ".join(str(w) for w in warnings) if isinstance(warnings, list) else str(warnings)
    value = row.get(column)
    return "" if value is None else value


def write_constructs_table(
    zf: zipfile.ZipFile, arcname: str, prepared: PrepareSequencesPayload
) -> MemberDigest:
    rows = [r.model_dump(exclude=PREPARED_ROW_EXCLUDE) for r in prepared.rows]
    with text_member(zf, arcname) as (fh, digest):
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(CONSTRUCT_COLUMNS)
        for row in rows:
            writer.writerow([_construct_cell(row, col) for col in CONSTRUCT_COLUMNS])
    return digest


def _construct_header(row: Dict[str, Any]) -> str:
    name = str(row.get("short_name") or "").strip()
    design_id = str(row.get("design_id") or "").strip()
    if name and design_id and name != design_id:
        return f"{name} design_id={design_id}"
    return name or design_id or "construct"


def write_construct_fastas(
    zf: zipfile.ZipFile,
    aa_arcname: str,
    dna_arcname: Optional[str],
    prepared: PrepareSequencesPayload,
) -> Tuple[MemberDigest, Optional[MemberDigest], int]:
    rows = [r.model_dump(exclude=PREPARED_ROW_EXCLUDE) for r in prepared.rows]
    with text_member(zf, aa_arcname) as (fh, aa_digest):
        written = write_sequence_fasta(
            fh, ((_construct_header(r), str(r.get("prepared_aa") or "")) for r in rows)
        )

    dna_digest: Optional[MemberDigest] = None
    has_dna = any(r.get("prepared_dna") for r in rows)
    if dna_arcname and has_dna:
        with text_member(zf, dna_arcname) as (fh, dna_digest_inner):
            write_sequence_fasta(
                fh,
                (
                    (_construct_header(r), str(r.get("prepared_dna") or ""))
                    for r in rows
                    if r.get("prepared_dna")
                ),
            )
        dna_digest = dna_digest_inner
    return aa_digest, dna_digest, written


def write_constructs_twist_csv(
    zf: zipfile.ZipFile, arcname: str, prepared: PrepareSequencesPayload
) -> Tuple[MemberDigest, int]:
    """The vendor upload format: name, sequence, original_name. CSV because that is what
    the vendor accepts, not because the bundle prefers CSV anywhere else.

    Returns (digest, rows skipped). A row lacking the chosen sequence type is omitted
    rather than written with an empty sequence cell: an order file that silently carries
    a blank sequence is worse than one that is visibly short, and the count surfaces as a
    manifest warning.
    """
    rows = [r.model_dump(exclude=PREPARED_ROW_EXCLUDE) for r in prepared.rows]
    sequence_key = "prepared_dna" if any(r.get("prepared_dna") for r in rows) else "prepared_aa"
    skipped = 0
    with text_member(zf, arcname) as (fh, digest):
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["name", "sequence", "original_name"])
        for row in rows:
            sequence = str(row.get(sequence_key) or "").strip()
            if not sequence:
                skipped += 1
                continue
            writer.writerow(
                [
                    row.get("short_name") or row.get("design_id") or "",
                    sequence,
                    row.get("design_id") or "",
                ]
            )
    return digest, skipped


def write_json_member(
    zf: zipfile.ZipFile, arcname: str, model: BaseModel, *, exclude: Any = None
) -> MemberDigest:
    payload = model.model_dump(mode="json", exclude=exclude)
    with text_member(zf, arcname) as (fh, digest):
        json.dump(payload, fh, indent=2, sort_keys=False, default=str)
        fh.write("\n")
    return digest


def write_text_member(zf: zipfile.ZipFile, arcname: str, text: str) -> MemberDigest:
    with text_member(zf, arcname) as (fh, digest):
        fh.write(text)
    return digest
