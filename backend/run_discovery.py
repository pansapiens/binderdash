import logging
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import json

from .util.pdb_to_fasta import get_chain_sequences
from .util.profiling import Timer

# Import will be done inside the function to avoid linting issues


logger = logging.getLogger(__name__)


def _ensure_original_results_table_backup(table_path: Path) -> None:
    """Create a hidden one-time backup: .{name}.orig.{ext} alongside the table."""
    backup_path = table_path.with_name(f".{table_path.stem}.orig{table_path.suffix}")
    if backup_path.exists():
        return
    shutil.copy2(table_path, backup_path)


def get_target_sequence(
    pdb_file: str, method: str, binder_sequence: Optional[str] = None
) -> Optional[str]:
    """Extract the target sequence from a PDB file based on the method.

    Args:
        pdb_file: Path to the PDB file
        method: The method type ("bindcraft", "rfd", or other)
        binder_sequence: The binder sequence (used for methods other than bindcraft/rfd)

    Returns:
        The target sequence as a string, or None if not found
    """

    if not pdb_file or not os.path.exists(pdb_file):
        return None

    try:
        # Get sequences for all chains
        chain_sequences = get_chain_sequences(pdb_file)

        if not chain_sequences:
            logger.warning(f"No sequences found in PDB file: {pdb_file}")
            return None

        if method == "bindcraft":
            # Target sequence is from chain A
            return chain_sequences.get("A")

        elif method == "rfd":
            # Target sequence is from chain B
            return chain_sequences.get("B")

        else:
            # For other methods, find the target by excluding the binder sequence
            if not binder_sequence:
                logger.warning(f"No binder sequence provided for method {method}")
                return None

            # Remove any non-amino acid characters and convert to uppercase for comparison
            clean_binder = "".join(c.upper() for c in binder_sequence if c.isalpha())

            # Find the chain that doesn't match the binder sequence
            for chain_id, sequence in chain_sequences.items():
                clean_chain_seq = "".join(c.upper() for c in sequence if c.isalpha())
                if clean_chain_seq != clean_binder:
                    return sequence

            logger.warning(
                f"Could not find target sequence in {pdb_file} - all chains match binder"
            )
            return None

    except Exception as e:
        logger.error(f"Error extracting target sequence from {pdb_file}: {str(e)}")
        return None


def extract_backbone_id(design_id: str, method: str) -> str:
    """Extract backbone_id from design_id by removing MPNN variant suffixes.

    For bindcraft: removes _mpnn{n} suffix
    For rfd: removes _mpnn{n} suffix and _af2pred suffix

    Args:
        design_id: The design identifier
        method: The method type ("bindcraft" or "rfd")

    Returns:
        The backbone_id with MPNN variant suffixes removed
    """
    if not design_id:
        return design_id

    # bindcraft_design_111_l93_s308700_mpnn10 -> bindcraft_design_111_l93_s308700
    # design_ppi_1Ty4GSo_6_dldesign_0_cycle1_mpnn1_af2pred -> design_ppi_1Ty4GSo_6_dldesign_0_cycle1

    # Remove _mpnn{n} pattern, optionally followed by _af2pred
    # This handles both bindcraft (_mpnn{n}) and RFD (_mpnn{n}_af2pred) patterns
    backbone_id = re.sub(r"_mpnn\d+(?:_af2pred)?$", "", design_id)

    return backbone_id


# Directories to skip during recursive walk (common to all signatures)
DEFAULT_SKIP_DIRS = [".nextflow", "work"]

# Run folder signatures for declarative run detection
# Each signature defines the structure required to identify a run type
run_folder_signatures = [
    {
        "method": "bindcraft",
        "submethod": "nf-binder-design",
        "priority": 1,  # Higher priority = checked first
        "required_files": ["results/bindcraft/final_design_stats.csv"],
        "required_dirs": ["results/bindcraft/accepted"],
        "results_table": "results/bindcraft/final_design_stats.csv",
        "pdb_pattern": "results/bindcraft/accepted/*.pdb",
        "params_files": ["results/params.json"],
        "skip_dirs": DEFAULT_SKIP_DIRS,
        # Design parsing configuration
        "design_id_columns": ["Design"],
        "primary_score_columns": ["Average_i_pTM"],
        "sort_ascending": False,
        "structure_file_column": None,
        "structure_search_patterns": [
            "{design_id}.pdb",
            "{design_id}_*.pdb",
            "{design_id}*.pdb",
        ],
    },
    {
        "method": "rfd",
        "submethod": "nf-binder-design",
        "priority": 2,
        "required_files": ["results/combined_scores.tsv"],
        "required_dirs": [
            "results/af2_initial_guess",
            "results/proteinmpnn",
            "results/rfdiffusion",
        ],
        "results_table": "results/combined_scores.tsv",
        "pdb_pattern": "results/af2_initial_guess/pdbs/*.pdb",
        "params_files": ["results/params.json"],
        "skip_dirs": DEFAULT_SKIP_DIRS,
        # Design parsing configuration
        "design_id_columns": ["description"],
        "primary_score_columns": ["pae_interaction"],
        "sort_ascending": True,
        "structure_file_column": None,
        "structure_search_patterns": ["{design_id}.pdb"],
    },
    {
        "method": "bindcraft",
        "submethod": "regular",
        "priority": 3,
        "required_files": ["final_design_stats.csv"],
        "required_dirs": ["Accepted"],
        "results_table": "final_design_stats.csv",
        "pdb_pattern": "Accepted/*.pdb",
        "params_files": ["../settings.json"],
        "skip_dirs": DEFAULT_SKIP_DIRS,
        # Design parsing configuration
        "design_id_columns": ["Design"],
        "primary_score_columns": ["Average_i_pTM"],
        "sort_ascending": False,
        "structure_file_column": None,
        "structure_search_patterns": [
            "{design_id}.pdb",
            "{design_id}_*.pdb",
            "{design_id}*.pdb",
        ],
    },
    {
        "method": "rfd",
        "submethod": "regular",
        "priority": 4,
        "required_dirs": ["af2_initial_guess"],
        "results_table": "combined_scores.tsv",
        "pdb_pattern": "af2_initial_guess/pdbs/*.pdb",
        "skip_dirs": DEFAULT_SKIP_DIRS,
        # Design parsing configuration
        "design_id_columns": ["description"],
        "primary_score_columns": ["pae_interaction"],
        "sort_ascending": True,
        "structure_file_column": None,
        "structure_search_patterns": ["{design_id}.pdb"],
    },
    {
        "method": "boltzgen",
        "submethod": "nf-binder-design",
        "priority": 5,
        # results/boltzgen/filtered/final_ranked_designs must exist
        "required_dirs": ["results/boltzgen/filtered/final_ranked_designs"],
        # final_designs_metrics_*.csv may have varying numeric suffixes
        "required_patterns": [
            "results/boltzgen/filtered/final_ranked_designs/final_designs_metrics_*.csv"
        ],
        # Pattern for resolving the concrete results table at detection time
        "results_table_pattern": "results/boltzgen/filtered/final_ranked_designs/final_designs_metrics_*.csv",
        # Pattern for locating structure files (mmCIF) across possible final_*_designs dirs
        "structure_pattern": "results/boltzgen/filtered/final_ranked_designs/final_*_designs/*.cif",
        "structure_format": "cif",
        "params_files": ["results/params.json"],
        "skip_dirs": DEFAULT_SKIP_DIRS,
        # Design parsing configuration
        "design_id_columns": ["id"],
        "primary_score_columns": ["design_to_target_iptm"],
        "sort_ascending": False,
        # Use the CSV file_name (if available) when searching; otherwise fall back to id
        "structure_file_column": "file_name",
        "structure_search_patterns": [
            "{file_name}",
            "rank*_{file_name}",
        ],
    },
    {
        "method": "rfd3",
        "submethod": "nf-binder-design",
        "priority": 6,
        "required_files": ["results/rfd3/combined_scores.tsv"],
        "required_dirs": [
            "results/rfd3/rosettafold3",
            "results/rfd3/rfdiffusion3",
        ],
        "results_table": "results/rfd3/combined_scores.tsv",
        "structure_pattern": "results/rfd3/rosettafold3/output/*/*.cif",
        "additional_pdb_patterns": [
            "results/rfd3/rosettafold3/output/*/*.cif.gz",
            "results/rfd3/rosettafold3/output/*/*.pdb",
            "results/rfd3/rosettafold3/output/*/*.pdb.gz",
        ],
        "structure_format": "cif",
        "params_files": ["results/params.json"],
        "skip_dirs": DEFAULT_SKIP_DIRS,
        "design_id_columns": ["id"],
        "primary_score_columns": [
            "iptm",
            "pair_pae",
            "rf3_ipsae_min",
            "rf3_rmsd_target_aligned_binder_rmsd_all",
        ],
        "sort_ascending": False,
        "structure_file_column": None,
        "structure_base_dir": "results/rfd3/rosettafold3/output/{design_id}",
        "structure_search_patterns": [
            "{design_id}_model.cif",
            "{design_id}_model.cif.gz",
            "{design_id}_model.pdb",
            "{design_id}_model.pdb.gz",
        ],
    },
]


def guess_project_id(path: Path) -> str:
    run_name = guess_run_name(path)
    disallowed_patterns = [
        r"^runs$",
        r"^results.*$",
        r"^batch.*$",
        r"^bindcraft$",
        r"^rfd$",
        r"^boltzgen$",
        r"^rfd3$",
        r"^\d+$",
    ]

    current_path = path
    found_run_name = False
    while current_path != current_path.parent:
        name = current_path.name
        if name == run_name:
            found_run_name = True
            current_path = current_path.parent
            continue
        if found_run_name:
            is_disallowed = any(
                re.match(pattern, name) for pattern in disallowed_patterns
            )
            if not is_disallowed:
                return name
        current_path = current_path.parent
    return ""


def guess_run_name(path: Path) -> str:
    disallowed_patterns = [
        r"^results.*$",
        r"^bindcraft$",
        r"^rfd$",
        r"^boltzgen$",
        r"^rfd3$",
        r"^batches$",
        r"^\d+$",
    ]
    current_path = path
    while current_path != current_path.parent:
        name = current_path.name
        is_disallowed = any(re.match(pattern, name) for pattern in disallowed_patterns)
        if not is_disallowed:
            return name
        current_path = current_path.parent
    return path.name


def _check_required_files(path: Path, required_files: List[str]) -> bool:
    """Check if all required files exist for the given run signature."""
    for file_path_str in required_files:
        file_path = path / file_path_str
        if not file_path.is_file():
            return False
    return True


def _check_required_dirs(path: Path, required_dirs: List[str]) -> bool:
    """Check if all required directories exist for the given run signature."""
    for dir_path_str in required_dirs:
        dir_path = path / dir_path_str
        if not dir_path.is_dir():
            return False
    return True


def _pick_latest_numeric_suffix_match(matches: List[Path]) -> Path:
    """Prefer the file with the largest trailing _{digits} in the stem (e.g. metrics_10 over metrics_2)."""

    def sort_key(p: Path) -> tuple:
        m = re.search(r"_(\d+)$", p.stem)
        if m:
            return (0, int(m.group(1)))
        return (1, p.name)

    return max(matches, key=sort_key)


def _check_required_patterns(path: Path, required_patterns: List[str]) -> bool:
    """Check if any files match the required patterns for the given run signature."""
    for pattern in required_patterns:
        matches = list(path.glob(pattern))
        if matches:
            return True
    return False


def _find_structure_file_for_design(
    run_path: Path,
    search_value: str,
    search_patterns: List[str],
    structure_base_dir: str,
    design_id: Optional[str] = None,
) -> Optional[str]:
    """Find the structure file for a design using the search patterns."""
    resolved_base = structure_base_dir
    if structure_base_dir and ("{design_id}" in structure_base_dir or "{file_name}" in structure_base_dir):
        did = design_id if design_id is not None else search_value
        try:
            resolved_base = structure_base_dir.format(
                design_id=did, file_name=search_value
            )
        except KeyError:
            resolved_base = structure_base_dir

    search_dirs: List[Path] = []
    if "*" in resolved_base:
        for d in run_path.glob(resolved_base):
            if d.is_dir():
                search_dirs.append(d)
    elif resolved_base:
        base_dir = run_path / resolved_base
        if base_dir.is_dir():
            search_dirs.append(base_dir)

    for base_dir in search_dirs:
        for pattern in search_patterns:
            try:
                search_pattern = pattern.format(design_id=search_value, file_name=search_value)
            except KeyError:
                search_pattern = pattern.format(design_id=search_value)
            matches = list(base_dir.glob(search_pattern))
            if matches:
                return str(matches[0])
    return None


def detect_run_type(path: Path) -> Optional[Dict[str, Any]]:
    """Detect the run type using declarative signatures.

    Returns the matching signature with run_name extracted, or None if no match.
    """
    if not path.is_dir():
        return None

    # Sort signatures by priority (lower number = checked first)
    sorted_signatures = sorted(run_folder_signatures, key=lambda x: x["priority"])

    for signature in sorted_signatures:
        # The current directory is the run_name
        run_name = path.name

        # Check required files
        if "required_files" in signature:
            if not _check_required_files(path, signature["required_files"]):
                continue

        # Check required directories
        if "required_dirs" in signature:
            if not _check_required_dirs(path, signature["required_dirs"]):
                continue

        # Check required patterns (alternative to required_files for some cases)
        if "required_patterns" in signature:
            if not _check_required_patterns(path, signature["required_patterns"]):
                continue

        # Special case for regular RFD: check if combined_scores.tsv exists OR .cs files exist
        if signature["method"] == "rfd" and signature["submethod"] == "regular":
            combined_file = path / "combined_scores.tsv"
            cs_files_scores = list((path / "af2_initial_guess" / "scores").glob("*.cs"))
            cs_files_root = list((path / "af2_initial_guess").glob("*.cs"))

            if not (combined_file.is_file() or cs_files_scores or cs_files_root):
                continue

        # Resolve any dynamic patterns to concrete values for this path
        resolved_signature = dict(signature)

        # Resolve results table from pattern, if provided
        results_table_pattern = resolved_signature.get("results_table_pattern")
        if results_table_pattern and not resolved_signature.get("results_table"):
            matches = list(path.glob(results_table_pattern))
            if not matches:
                # No concrete table found for this signature
                continue
            selected = _pick_latest_numeric_suffix_match(matches)
            try:
                rel_table = selected.relative_to(path)
            except ValueError:
                rel_table = selected
            resolved_signature["results_table"] = str(rel_table)

        # Resolve structure pattern to a concrete glob pattern for this run (used for listing files)
        structure_pattern = resolved_signature.get("structure_pattern")
        if structure_pattern and not resolved_signature.get("pdb_pattern"):
            # Keep the relative glob pattern; find_runs_recursive will use it directly
            resolved_signature["pdb_pattern"] = structure_pattern

        # If we get here, this signature matches
        return {**resolved_signature, "run_name": run_name, "detected_path": str(path)}

    return None


def find_runs_recursive(root_path: Path) -> List[Dict[str, Any]]:
    # Build combined set of directories to skip from all signatures
    skip_dirs_set = set()
    for sig in run_folder_signatures:
        skip_dirs_set.update(sig.get("skip_dirs", []))

    walk_dirs = 0

    runs: List[Dict[str, Any]] = []
    _walk_t = Timer(logger, "find_runs_recursive", root=root_path).start()
    for dirpath, dirnames, filenames in os.walk(root_path, followlinks=True):
        walk_dirs += 1
        current_dir = Path(dirpath)
        if current_dir.name in skip_dirs_set:
            dirnames[:] = []
            continue

        path_parts = current_dir.parts
        if "batches" in path_parts:
            try:
                batches_index = path_parts.index("batches")
                if (
                    batches_index >= 2
                    and path_parts[batches_index - 1] == "bindcraft"
                    and path_parts[batches_index - 2] == "results"
                ):
                    dirnames[:] = []
                    continue
            except ValueError:
                pass

        _det_t = Timer(logger, "detect_run_type", path=str(current_dir)).start()
        detected_run = detect_run_type(current_dir)
        _det_t.log(min_ms=100)

        if detected_run:
            run_id = str(uuid.uuid4())
            guessed_project_id = guess_project_id(current_dir)
            run_name = detected_run["run_name"]

            results_table = detected_run["results_table"]
            pdb_pattern = detected_run["pdb_pattern"]
            extra_pats = detected_run.get("additional_pdb_patterns", [])

            _glob_t = Timer(
                logger,
                "run_glob",
                method=detected_run.get("method"),
                path=str(current_dir),
                primary_pattern=pdb_pattern,
                extra_patterns=len(extra_pats),
            ).start()
            pdb_paths = list(current_dir.glob(pdb_pattern))
            for extra_pat in extra_pats:
                pdb_paths.extend(current_dir.glob(extra_pat))
            pdb_files = sorted({str(p) for p in pdb_paths})
            _glob_t.log(pdb_files=len(pdb_files))

            is_nf_binder_design = detected_run["submethod"] == "nf-binder-design"

            runs.append(
                {
                    "run_id": run_id,
                    "project_id": guessed_project_id,
                    "path": str(current_dir),
                    "method": detected_run["method"],
                    "submethod": detected_run["submethod"],
                    "results_table": results_table,
                    "pdb_files": pdb_files,
                    "is_nf_binder_design": is_nf_binder_design,
                    "signature": detected_run,
                    "metadata": {
                        "name": run_name,
                        "original_name": current_dir.name,
                        "parent_path": str(current_dir.parent),
                        "pdb_count": len(pdb_files),
                    },
                }
            )

            dirnames[:] = []

    _walk_t.log(walk_dirs=walk_dirs, runs_found=len(runs))
    return runs


def resolve_design_id_column(df: pd.DataFrame, signature: Dict[str, Any]) -> Optional[str]:
    design_id_columns = signature.get("design_id_columns", [])
    for col_name in design_id_columns:
        if col_name in df.columns:
            return col_name
    for col in df.columns:
        if col.lower() in ["design", "description", "name", "id"]:
            return col
    return None


def update_design_good_flag(
    run_metadata: Dict[str, Any],
    design_id: str,
    good: Optional[bool],
    source_path: Optional[str] = None,
) -> None:
    """Write the ``good`` flag for one row in the run's results table on disk.

    Pass ``good=None`` to clear the cell (empty / missing in the exported table).

    For merged runs, pass ``source_path`` from the design row so the correct
    fragment table is updated.
    """
    results_table = run_metadata.get("results_table")
    if not results_table:
        raise ValueError("Run has no results_table path configured")

    signature = run_metadata.get("signature", {})
    merged_paths = list(run_metadata.get("merged_paths") or [run_metadata["path"]])

    ordered_bases = list(merged_paths)
    if source_path and source_path in merged_paths:
        ordered_bases = [source_path] + [p for p in merged_paths if p != source_path]

    saw_table = False
    for base in ordered_bases:
        table_path = Path(base) / results_table
        if not table_path.is_file():
            continue

        saw_table = True
        sep = "\t" if table_path.suffix.lower() == ".tsv" else ","
        df = pd.read_csv(table_path, sep=sep)
        id_col = resolve_design_id_column(df, signature)
        if not id_col:
            raise ValueError("Could not resolve design id column in results table")

        mask = df[id_col].astype(str) == str(design_id)
        if not mask.any():
            continue

        if good is None:
            if "good" not in df.columns:
                return
            df["good"] = df["good"].astype(object)
            df.loc[mask, "good"] = np.nan
        else:
            if "good" not in df.columns:
                df["good"] = False
            df.loc[mask, "good"] = bool(good)
        _ensure_original_results_table_backup(table_path)
        df.to_csv(table_path, sep=sep, index=False, na_rep="")
        return

    if not saw_table:
        raise ValueError(
            f"Results table not found at {results_table!r} under run path(s)"
        )
    raise ValueError(f"Design {design_id!r} not found in results table")


def update_design_tag(
    run_metadata: Dict[str, Any],
    design_id: str,
    tag: Optional[str],
    source_path: Optional[str] = None,
) -> None:
    """Write the ``tag`` column (N / C / cleared) for one row in the run's results table."""
    results_table = run_metadata.get("results_table")
    if not results_table:
        raise ValueError("Run has no results_table path configured")

    signature = run_metadata.get("signature", {})
    merged_paths = list(run_metadata.get("merged_paths") or [run_metadata["path"]])

    ordered_bases = list(merged_paths)
    if source_path and source_path in merged_paths:
        ordered_bases = [source_path] + [p for p in merged_paths if p != source_path]

    saw_table = False
    for base in ordered_bases:
        table_path = Path(base) / results_table
        if not table_path.is_file():
            continue

        saw_table = True
        sep = "\t" if table_path.suffix.lower() == ".tsv" else ","
        df = pd.read_csv(table_path, sep=sep)
        id_col = resolve_design_id_column(df, signature)
        if not id_col:
            raise ValueError("Could not resolve design id column in results table")

        mask = df[id_col].astype(str) == str(design_id)
        if not mask.any():
            continue

        if "tag" not in df.columns:
            df["tag"] = np.nan

        df["tag"] = df["tag"].astype(object)
        if tag is None:
            df.loc[mask, "tag"] = np.nan
        else:
            df.loc[mask, "tag"] = str(tag)

        _ensure_original_results_table_backup(table_path)
        df.to_csv(table_path, sep=sep, index=False, na_rep="")
        return

    if not saw_table:
        raise ValueError(
            f"Results table not found at {results_table!r} under run path(s)"
        )
    raise ValueError(f"Design {design_id!r} not found in results table")


def load_run_table(run_metadata: Dict[str, Any]) -> Optional[pd.DataFrame]:
    _t = Timer(logger, "load_run_table", path=run_metadata.get("path")).start()
    try:
        merged_paths = run_metadata.get("merged_paths", [run_metadata["path"]])
        results_table = run_metadata.get("results_table")
        if not results_table:
            _t.log()
            return None
        all_dfs: List[pd.DataFrame] = []
        for run_path in merged_paths:
            path = Path(run_path)
            table_path = path / results_table
            if not table_path.exists():
                logger.warning(f"Results table not found: {table_path}")
                continue
            try:
                if table_path.suffix.lower() == ".csv":
                    df = pd.read_csv(table_path)
                elif table_path.suffix.lower() == ".tsv":
                    df = pd.read_csv(table_path, sep="\t")
                else:
                    logger.warning(f"Unsupported table format: {table_path}")
                    continue
                for col in df.columns:
                    if df[col].dtype == object:
                        df[col] = pd.to_numeric(df[col], errors="ignore")
                df = _standardise_dataframe_columns(
                    df, run_metadata.get("method", "")
                )
                df["source_path"] = str(path)
                all_dfs.append(df)
            except Exception as e:
                logger.error(f"Error loading table from {table_path}: {str(e)}")
                continue
        if not all_dfs:
            logger.warning(
                f"No valid tables found for run: {run_metadata.get('path', 'unknown')}"
            )
            _t.log(table=results_table)
            return None
        if len(all_dfs) == 1:
            out = all_dfs[0]
        else:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            logger.info(
                f"Combined {len(all_dfs)} tables for merged run, total rows: {len(combined_df)}"
            )
            out = combined_df
        _t.log(table=results_table, rows=len(out))
        return out
    except Exception as e:
        logger.error(f"Error loading run table: {str(e)}")
        _t.log()
        return None


def _standardise_dataframe_columns(df: pd.DataFrame, method: str) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    canonical_groups: Dict[str, List[str]] = {
        "Sequence": [
            "Sequence",
            "sequence",
            "binder_sequence",
            "binder_seq",
            "seq",
        ],
        "Length": ["Length", "length", "len", "binder_length"],
    }
    lower_to_original: Dict[str, str] = {col.lower(): col for col in df.columns}
    result_df = df.copy()
    for target, variants in canonical_groups.items():
        source_cols: List[str] = []
        for v in variants:
            original = lower_to_original.get(v.lower())
            if original and original not in source_cols:
                source_cols.append(original)
        if not source_cols:
            continue
        if target in result_df.columns:
            for src in source_cols:
                if src == target:
                    continue
                result_df[target] = result_df[target].fillna(result_df[src])
        else:
            series = None
            for idx, src in enumerate(source_cols):
                if idx == 0:
                    series = result_df[src]
                else:
                    series = series.where(series.notna(), result_df[src])  # type: ignore
            if series is not None:
                result_df[target] = series
        for src in source_cols:
            if src != target and src in result_df.columns:
                result_df = result_df.drop(columns=[src])
    return result_df


def parse_run_params(run_metadata: Dict[str, Any]) -> Optional[Any]:
    """Parse parameter/settings file for a run and return the raw JSON content.

    - Parse the first existing file in signature["params_files"], if provided.

    Returns the parsed JSON (dict/list/primitive) or None if not found or error.
    """
    try:
        run_path_str = run_metadata.get("path", "")
        if not run_path_str:
            return None
        run_path = Path(run_path_str)

        signature: Dict[str, Any] = run_metadata.get("signature", {})
        submethod = signature.get("submethod", run_metadata.get("submethod", ""))

        json_path: Optional[Path] = None

        params_files: List[str] = signature.get("params_files", [])
        for rel in params_files:
            candidate = run_path / rel
            if candidate.is_file():
                json_path = candidate
                break

        if not json_path:
            return None

        logger.info(f"Parsing run params from {json_path}")
        with open(json_path, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Error parsing run params: {str(e)}")
        return None


def parse_designs_from_run(run_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    _t = Timer(
        logger,
        "parse_designs",
        run_id=run_metadata.get("run_id"),
        method=run_metadata.get("method"),
        run_name=run_metadata.get("metadata", {}).get("name", ""),
    ).start()
    try:
        df = load_run_table(run_metadata)
        if df is None or df.empty:
            _t.log()
            return []

        designs: List[Dict[str, Any]] = []
        run_path = run_metadata["path"]
        run_name = run_metadata["metadata"]["name"]
        signature = run_metadata.get("signature", {})

        primary_score_columns = signature.get("primary_score_columns", [])
        sort_ascending = signature.get("sort_ascending", True)
        structure_search_patterns = signature.get(
            "structure_search_patterns", ["{design_id}.pdb"]
        )

        design_id_col = resolve_design_id_column(df, signature)

        primary_score_col = None
        for col_name in primary_score_columns:
            if col_name in df.columns:
                primary_score_col = col_name
                break

        if not primary_score_col:
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if numeric_cols:
                primary_score_col = numeric_cols[0]

        if primary_score_col and primary_score_col in df.columns:
            df = df.sort_values(
                primary_score_col, ascending=sort_ascending
            ).reset_index(drop=True)

        structure_base_dir = signature.get("structure_base_dir", "")
        if not structure_base_dir:
            pdb_pattern = signature.get("pdb_pattern", "")
            if "/*.pdb" in pdb_pattern:
                structure_base_dir = pdb_pattern.split("/*.pdb")[0]
            elif "/*.cif" in pdb_pattern:
                structure_base_dir = pdb_pattern.split("/*.cif")[0]

        _params_t = Timer(
            logger,
            "parse_designs.parse_run_params",
            run_id=run_metadata.get("run_id"),
        ).start()
        run_params: Optional[Any] = parse_run_params(run_metadata)
        _params_t.log()

        # Target protein is the same for every design in a run; parsing each mmCIF
        # only to extract it costs ~O(rows) full structure reads (DEBUG timing logs).
        target_sequence_cache: Dict[str, Optional[str]] = {}

        for index, row in df.iterrows():
            design_id = (
                str(row.get(design_id_col, f"design_{index}"))
                if design_id_col
                else f"design_{index}"
            )

            structure_file_column = signature.get("structure_file_column")
            search_value = design_id
            file_name_val = None
            if structure_file_column and structure_file_column in df.columns:
                file_name_val = row.get(structure_file_column)
                if file_name_val is not None and str(file_name_val).strip():
                    search_value = str(file_name_val)

            pdb_file = _find_structure_file_for_design(
                Path(run_path),
                search_value,
                structure_search_patterns,
                structure_base_dir,
                design_id=design_id,
            )
            if (
                pdb_file is None
                and run_metadata.get("method") == "boltzgen"
                and structure_file_column == "file_name"
                and file_name_val is not None
                and str(file_name_val).strip()
            ):
                pdb_file = str(file_name_val)

            backbone_id = extract_backbone_id(design_id, run_metadata["method"])

            binder_sequence = None
            for seq_col in ["Sequence", "sequence", "binder_sequence"]:
                if seq_col in df.columns:
                    try:
                        val = row[seq_col]
                        if val is not None and str(val).strip():
                            binder_sequence = str(val)
                            break
                    except (KeyError, AttributeError):
                        continue

            cache_key = (
                str(row["source_path"])
                if "source_path" in df.columns
                and row.get("source_path") is not None
                and str(row.get("source_path")).strip()
                else str(run_path)
            )
            if cache_key in target_sequence_cache:
                target_sequence = target_sequence_cache[cache_key]
            elif pdb_file:
                target_sequence = get_target_sequence(
                    pdb_file, run_metadata["method"], binder_sequence
                )
                if target_sequence is not None:
                    target_sequence_cache[cache_key] = target_sequence
            else:
                target_sequence = None

            design: Dict[str, Any] = {
                "design_id": design_id,
                "backbone_id": backbone_id,
                "run_id": run_metadata["run_id"],
                "project_id": run_metadata.get("project_id", ""),
                "run_name": run_name,
                "method": run_metadata["method"],
                "run_path": run_path,
                "pdb_file": pdb_file,
                "target_sequence": target_sequence,
                **{
                    col: row[col]
                    for col in df.columns
                    if col != design_id_col
                    and not bool(
                        (
                            pd.isna(row[col])
                            if hasattr(pd, "isna")
                            else (row[col] is None)
                        )
                    )
                },
            }
            if run_params is not None:
                design["params"] = run_params
            designs.append(design)

        _t.log(rows=len(designs))
        return designs
    except Exception as e:
        logger.error(
            f"Error parsing designs from run {run_metadata['run_id']}: {str(e)}"
        )
        _t.log()
        return []
