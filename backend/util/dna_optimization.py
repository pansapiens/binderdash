import io
import sys
import logging
from typing import Any, Dict, List, Optional
from contextlib import redirect_stdout

import dnachisel as dc
# Assuming Bio.Data.CodonTable.standard_dna_table is what we want for simple naive translation initially
# actually dnachisel uses Bio for CodonOptimize, but we can just map the protein sequentially for initialization.
# Or use python_codon_tables? Dnachisel depends on python_codon_tables.
import python_codon_tables as pct

logger = logging.getLogger(__name__)


def _naive_translate_protein(protein_seq: str, table_id: str = "e_coli_316407") -> str:
    """Translates protein to DNA naively by picking the most frequent codon.
    DnaChisel needs a starting DNA seq to optimize."""
    # Resolve the proper dnachisel species taxonomy ID if possible, or just use the table
    # We will pick the most frequent codon per amino acid for the naive start.
    try:
        table = pct.get_codons_table(table_id, replace_U_by_T=True)
    except Exception:
        # fallback to standard e coli if not found
        table = pct.get_codons_table("e_coli_316407", replace_U_by_T=True)
        
    best_codons = {}
    for aa, codons in table.items():
        if aa == "*":
            continue
        if isinstance(codons, dict):
            # Sort codons by frequency descending, then alphabetically
            ordered = sorted(codons.items(), key=lambda x: (-x[1], x[0]))
            if ordered:
                best_codons[aa.upper()] = ordered[0][0].upper()
    
    # Just in case some AAs are missing
    best_codons.setdefault('X', 'NNN')
    
    dna_parts = []
    for aa in protein_seq.upper():
        if aa == '*':
            # find best stop codon
            stop_ordered = sorted(table.get('*', {}).items(), key=lambda x: (-x[1], x[0]))
            dna_parts.append(stop_ordered[0][0].upper() if stop_ordered else 'TAA')
        else:
            dna_parts.append(best_codons.get(aa, 'NNN'))
    return "".join(dna_parts)

def build_dnachisel_constraint(
    constraint_type: str, params: Dict[str, Any], codon_table_id: str = "e_coli_316407"
) -> Optional[Any]:
    try:
        if constraint_type == "EnforceGCContent":
            return dc.EnforceGCContent(**params)
        elif constraint_type == "AvoidHairpins":
            p = {k: v for k, v in params.items() if k != "location"}
            return dc.AvoidHairpins(**p)
        elif constraint_type == "AvoidPattern":
            pattern = params.get("pattern")
            if isinstance(pattern, dict) and pattern.get("type") == "RepeatedKmerPattern":
                rep_params = pattern.get("params", {})
                # API uses k_size/n_repeats, not k/n
                k_size = rep_params.get("k_size") or rep_params.get("k")
                n_repeats = rep_params.get("n_repeats") or rep_params.get("n")
                if k_size is None or n_repeats is None:
                    logger.warning(f"RepeatedKmerPattern missing k_size or n_repeats in {rep_params}")
                    return None
                from dnachisel.SequencePattern import RepeatedKmerPattern
                return dc.AvoidPattern(RepeatedKmerPattern(k_size=int(k_size), n_repeats=int(n_repeats)))
            else:
                return dc.AvoidPattern(pattern)
        elif constraint_type == "AvoidRareCodons":
            # species is required; inject from the optimization context
            merged = {"species": codon_table_id, **params}
            return dc.AvoidRareCodons(**merged)
        elif constraint_type == "UniquifyAllKmers":
            return dc.UniquifyAllKmers(**params)
        else:
            logger.warning(f"Unknown constraint type: {constraint_type}")
            return None
    except Exception as e:
        logger.error(f"Failed to build constraint {constraint_type} with params {params}: {e}")
        return None


def optimize_sequences(
    sequences: Dict[str, str], 
    codon_table_id: str, 
    constraints: List[Dict[str, Any]], 
    method: str = "match_codon_usage"
) -> Dict[str, Dict[str, Optional[str]]]:
    """
    Optimizes a batch of protein sequences.
    Returns: { design_id: {"optimized_dna": str | None, "error": str | None} }
    """
    results = {}
    
    # Extract taxonomy ID from python-codon-tables ID (e.g. 'e_coli_316407' -> '316407')
    # If it's a tax id, get numeric part. Wait, dnachisel CodonOptimize accepts tax id or species name.
    # DnaChisel passes this straight to python_codon_tables internally! So we can just pass codon_table_id.
    
    parsed_constraints = []
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
            initial_dna = _naive_translate_protein(protein_seq, codon_table_id)
            
            # Combine parsed constraints with mandatory constraints
            seq_constraints = [
                *parsed_constraints,
                dc.EnforceTranslation()
            ]
            
            problem = dc.DnaOptimizationProblem(
                sequence=initial_dna,
                constraints=seq_constraints,
                objectives=[dc.CodonOptimize(species=codon_table_id, method=method)]
            )
            
            # Redirect stdout to avoid log pollution from DnaChisel
            f_capture = io.StringIO()
            with redirect_stdout(f_capture):
                problem.resolve_constraints()
                problem.optimize()
            
            results[design_id] = {
                "optimized_dna": problem.sequence,
                "error": None
            }
        except dc.NoSolutionError as e:
            logger.error(f"No solution found for {design_id}: {e}")
            results[design_id] = {"optimized_dna": None, "error": "Constraints could not be resolved (No solution found)."}
        except Exception as e:
            logger.exception(f"Exception during optimization of {design_id}")
            results[design_id] = {"optimized_dna": None, "error": str(e)}

    return results
