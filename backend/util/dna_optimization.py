import io
import logging
from contextlib import redirect_stdout
from typing import Any, Dict, List, Optional, Sequence, Tuple

import dnachisel as dc
import python_codon_tables as pct

logger = logging.getLogger(__name__)

FIXED_STOP_DNA = "TAA"
FIXED_START_DNA = "ATG"
# DnaChisel's random search can miss a sequence that satisfies the constraints.
# Re-run a design that fails with NoSolutionError this many times before reporting it.
OPTIMIZATION_ATTEMPTS = 5
_NO_SOLUTION_MESSAGE = "Constraints could not be resolved (No solution found)."


def _naive_translate_protein(protein_seq: str, table_id: str = "e_coli_316407") -> str:
    """Translates protein to DNA naively by picking the most frequent codon.
    DnaChisel needs a starting DNA seq to optimize."""
    try:
        table = pct.get_codons_table(table_id, replace_U_by_T=True)
    except Exception:
        table = pct.get_codons_table("e_coli_316407", replace_U_by_T=True)

    best_codons: Dict[str, str] = {}
    for aa, codons in table.items():
        if aa == "*":
            continue
        if isinstance(codons, dict):
            ordered = sorted(codons.items(), key=lambda x: (-x[1], x[0]))
            if ordered:
                best_codons[aa.upper()] = ordered[0][0].upper()

    best_codons.setdefault("X", "NNN")

    dna_parts: List[str] = []
    for aa in protein_seq.upper():
        if aa == "*":
            stop_ordered = sorted(table.get("*", {}).items(), key=lambda x: (-x[1], x[0]))
            dna_parts.append(stop_ordered[0][0].upper() if stop_ordered else FIXED_STOP_DNA)
        else:
            dna_parts.append(best_codons.get(aa, "NNN"))
    return "".join(dna_parts)


def build_dnachisel_constraint(
    constraint_type: str, params: Dict[str, Any], codon_table_id: str = "e_coli_316407"
) -> Optional[Any]:
    try:
        # Strip caller-supplied location; free-interval locations are applied later.
        clean = {k: v for k, v in params.items() if k != "location"}
        if constraint_type == "EnforceGCContent":
            return dc.EnforceGCContent(**clean)
        elif constraint_type == "AvoidHairpins":
            return dc.AvoidHairpins(**clean)
        elif constraint_type == "AvoidPattern":
            pattern = clean.get("pattern")
            if isinstance(pattern, dict) and pattern.get("type") == "RepeatedKmerPattern":
                rep_params = pattern.get("params", {})
                k_size = rep_params.get("k_size") or rep_params.get("k")
                n_repeats = rep_params.get("n_repeats") or rep_params.get("n")
                if k_size is None or n_repeats is None:
                    logger.warning(
                        f"RepeatedKmerPattern missing k_size or n_repeats in {rep_params}"
                    )
                    return None
                from dnachisel.SequencePattern import RepeatedKmerPattern

                return dc.AvoidPattern(
                    RepeatedKmerPattern(k_size=int(k_size), n_repeats=int(n_repeats))
                )
            else:
                return dc.AvoidPattern(pattern)
        elif constraint_type == "AvoidRareCodons":
            merged = {"species": codon_table_id, **clean}
            return dc.AvoidRareCodons(**merged)
        elif constraint_type == "UniquifyAllKmers":
            return dc.UniquifyAllKmers(**clean)
        else:
            logger.warning(f"Unknown constraint type: {constraint_type}")
            return None
    except Exception as e:
        logger.error(f"Failed to build constraint {constraint_type} with params {params}: {e}")
        return None


def resolve_fixed_mask(
    protein_seq: str, fixed: Optional[Sequence[bool]]
) -> List[bool]:
    """Return a per-residue fixed mask.

    When ``fixed`` is omitted, every stop (``*``) is frozen as TAA.
    When present, it is the complete mask and must match the protein length;
    only stop residues, or a leading Met (M), may be marked fixed.
    """
    if fixed is None:
        return [aa == "*" for aa in protein_seq]
    if len(fixed) != len(protein_seq):
        raise ValueError(
            f"fixed mask length {len(fixed)} does not match protein length {len(protein_seq)}"
        )
    mask = [bool(v) for v in fixed]
    for i, (aa, is_fixed) in enumerate(zip(protein_seq, mask)):
        if not is_fixed:
            continue
        if aa == "*":
            continue
        if aa == "M" and i == 0:
            continue
        raise ValueError(
            f"Residue {i} is marked fixed but is '{aa}'; "
            "only stop (*) or a leading Met (M) can be fixed"
        )
    return mask


def fixed_codon_dna(aa: str) -> str:
    """Exact DNA written for a fixed residue."""
    if aa == "*":
        return FIXED_STOP_DNA
    if aa == "M":
        return FIXED_START_DNA
    raise ValueError(f"No fixed codon defined for amino acid '{aa}'")


def fixed_nt_indices(fixed_mask: Sequence[bool]) -> List[int]:
    """Expand per-residue fixed flags to nucleotide indexes (codon = 3 nt)."""
    indices: List[int] = []
    for i, is_fixed in enumerate(fixed_mask):
        if is_fixed:
            base = 3 * i
            indices.extend([base, base + 1, base + 2])
    return indices


def free_intervals(seq_len: int, fixed_indices: Sequence[int]) -> List[Tuple[int, int]]:
    """Inclusive-start, exclusive-end nucleotide intervals that are not fixed."""
    fixed_set = set(fixed_indices)
    intervals: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for i in range(seq_len):
        if i in fixed_set:
            if start is not None:
                intervals.append((start, i))
                start = None
        elif start is None:
            start = i
    if start is not None:
        intervals.append((start, seq_len))
    return intervals


def _constraint_min_span(constraint: Any) -> int:
    """Minimum interval length for a constraint to be meaningful."""
    window = getattr(constraint, "window", None)
    if window is not None:
        try:
            return max(1, int(window))
        except (TypeError, ValueError):
            pass
    hairpin_window = getattr(constraint, "hairpin_window", None)
    if hairpin_window is not None:
        try:
            return max(1, int(hairpin_window))
        except (TypeError, ValueError):
            pass
    k = getattr(constraint, "k", None)
    if k is not None:
        try:
            return max(1, int(k))
        except (TypeError, ValueError):
            pass
    pattern = getattr(constraint, "pattern", None)
    if pattern is not None:
        size = getattr(pattern, "size", None)
        if size is not None:
            try:
                return max(1, int(size))
            except (TypeError, ValueError):
                pass
        if isinstance(pattern, str):
            return max(1, len(pattern))
    return 3


def _apply_fixed_dna(dna: str, protein: str, fixed_mask: Sequence[bool]) -> str:
    """Overwrite each fixed codon with its frozen DNA (TAA for stop, ATG for start Met)."""
    chars = list(dna)
    for i, is_fixed in enumerate(fixed_mask):
        if not is_fixed:
            continue
        start = 3 * i
        codon = fixed_codon_dna(protein[i])
        chars[start : start + 3] = list(codon)
    return "".join(chars)


def _localize_constraints(
    base_constraints: List[Any], intervals: List[Tuple[int, int]]
) -> List[Any]:
    localized: List[Any] = []
    for constraint in base_constraints:
        min_span = _constraint_min_span(constraint)
        for start, end in intervals:
            if end - start < min_span:
                continue
            localized.append(
                constraint.copy_with_changes(location=dc.Location(start, end))
            )
    return localized


def _codon_optimize_objectives(
    codon_table_id: str, method: str, intervals: List[Tuple[int, int]]
) -> List[Any]:
    objectives: List[Any] = []
    for start, end in intervals:
        if (end - start) < 3 or (end - start) % 3 != 0:
            continue
        objectives.append(
            dc.CodonOptimize(
                species=codon_table_id,
                method=method,
                location=dc.Location(start, end),
            )
        )
    return objectives


def _solve_once(
    initial_dna: str,
    seq_constraints: List[Any],
    objectives: List[Any],
) -> str:
    problem = dc.DnaOptimizationProblem(
        sequence=initial_dna,
        constraints=seq_constraints,
        objectives=objectives,
    )
    captured = io.StringIO()
    with redirect_stdout(captured):
        problem.resolve_constraints()
        problem.optimize()
    return problem.sequence


def _optimize_with_retries(
    design_id: str,
    initial_dna: str,
    seq_constraints: List[Any],
    objectives: List[Any],
) -> Dict[str, Optional[str]]:
    """Solve one design, retrying stochastic "no solution" failures."""
    for attempt in range(1, OPTIMIZATION_ATTEMPTS + 1):
        try:
            return {
                "optimized_dna": _solve_once(initial_dna, seq_constraints, objectives),
                "error": None,
            }
        except dc.NoSolutionError as e:
            if attempt < OPTIMIZATION_ATTEMPTS:
                logger.warning(
                    f"No solution found for {design_id} "
                    f"(attempt {attempt}/{OPTIMIZATION_ATTEMPTS}); retrying: {e}"
                )
                continue
            logger.error(
                f"No solution found for {design_id} after {OPTIMIZATION_ATTEMPTS} attempts: {e}"
            )
            return {"optimized_dna": None, "error": _NO_SOLUTION_MESSAGE}
        except Exception as e:
            logger.exception(f"Exception during optimization of {design_id}")
            return {"optimized_dna": None, "error": str(e)}
    return {"optimized_dna": None, "error": _NO_SOLUTION_MESSAGE}


def optimize_sequences(
    sequences: Dict[str, str],
    codon_table_id: str,
    constraints: List[Dict[str, Any]],
    method: str = "match_codon_usage",
    fixed: Optional[Dict[str, List[bool]]] = None,
) -> Dict[str, Dict[str, Optional[str]]]:
    """
    Optimizes a batch of protein sequences.
    Returns: { design_id: {"optimized_dna": str | None, "error": str | None} }

    ``fixed`` maps design_id -> per-residue booleans. Residues marked true must be
    stops and are frozen as TAA, excluded from codon optimisation and user
    constraints. When a design_id is absent from ``fixed``, every ``*`` in that
    protein is treated as fixed.

    A design that fails with ``NoSolutionError`` is solved again from the same
    starting sequence, up to ``OPTIMIZATION_ATTEMPTS`` times, before that error
    is returned. Other errors are returned on the first failure.
    """
    results: Dict[str, Dict[str, Optional[str]]] = {}
    fixed = fixed or {}

    parsed_constraints: List[Any] = []
    for c in constraints:
        if not c.get("enabled", True):
            continue
        dc_c = build_dnachisel_constraint(c["type"], c.get("params", {}), codon_table_id)
        if dc_c:
            parsed_constraints.append(dc_c)

    for design_id, protein_seq in sequences.items():
        if not protein_seq:
            results[design_id] = {"optimized_dna": None, "error": "Empty sequence"}
            continue

        try:
            protein = protein_seq.upper()
            design_fixed = fixed.get(design_id) if design_id in fixed else None
            fixed_mask = resolve_fixed_mask(protein, design_fixed)
            initial_dna = _apply_fixed_dna(
                _naive_translate_protein(protein, codon_table_id),
                protein,
                fixed_mask,
            )
            fixed_indices = fixed_nt_indices(fixed_mask)
            intervals = free_intervals(len(initial_dna), fixed_indices)

            if not intervals:
                results[design_id] = {"optimized_dna": initial_dna, "error": None}
                continue

            if fixed_indices:
                seq_constraints = [
                    *_localize_constraints(parsed_constraints, intervals),
                    dc.AvoidChanges(indices=fixed_indices),
                    dc.EnforceTranslation(),
                ]
                objectives = _codon_optimize_objectives(
                    codon_table_id, method, intervals
                )
            else:
                seq_constraints = [
                    *parsed_constraints,
                    dc.EnforceTranslation(),
                ]
                objectives = [
                    dc.CodonOptimize(species=codon_table_id, method=method)
                ]

            if not objectives:
                results[design_id] = {"optimized_dna": initial_dna, "error": None}
                continue
        except ValueError as e:
            results[design_id] = {"optimized_dna": None, "error": str(e)}
            continue
        except Exception as e:
            logger.exception(f"Exception preparing optimization of {design_id}")
            results[design_id] = {"optimized_dna": None, "error": str(e)}
            continue

        results[design_id] = _optimize_with_retries(
            design_id, initial_dna, seq_constraints, objectives
        )

    return results
