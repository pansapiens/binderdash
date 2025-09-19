import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


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
        "skip_dirs": ["results/bindcraft/batches"],  # Skip walking into batches
        # Design parsing configuration
        "design_id_columns": ["Design"],
        "primary_score_columns": ["Average_i_pTM"],
        "sort_ascending": False,
        "pdb_search_patterns": [
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
        "skip_dirs": [],
        # Design parsing configuration
        "design_id_columns": ["description"],
        "primary_score_columns": ["pae_interaction"],
        "sort_ascending": True,
        "pdb_search_patterns": ["{design_id}.pdb"],
    },
    {
        "method": "bindcraft",
        "submethod": "regular",
        "priority": 3,
        "required_files": ["final_design_stats.csv"],
        "required_dirs": ["Accepted"],
        "results_table": "final_design_stats.csv",
        "pdb_pattern": "Accepted/*.pdb",
        "skip_dirs": [],
        # Design parsing configuration
        "design_id_columns": ["Design"],
        "primary_score_columns": ["Average_i_pTM"],
        "sort_ascending": False,
        "pdb_search_patterns": [
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
        "skip_dirs": [],
        # Design parsing configuration
        "design_id_columns": ["description"],
        "primary_score_columns": ["pae_interaction"],
        "sort_ascending": True,
        "pdb_search_patterns": ["{design_id}.pdb"],
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
    disallowed_patterns = [r"^results.*$", r"^bindcraft$", r"^batches$", r"^\d+$"]
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


def _check_required_patterns(path: Path, required_patterns: List[str]) -> bool:
    """Check if any files match the required patterns for the given run signature."""
    for pattern in required_patterns:
        matches = list(path.glob(pattern))
        if matches:
            return True
    return False


def _find_pdb_file_for_design(
    run_path: Path, design_id: str, pdb_search_patterns: List[str], pdb_base_dir: str
) -> Optional[str]:
    """Find the PDB file for a design using the search patterns."""
    pdb_dir = run_path / pdb_base_dir
    if not pdb_dir.exists():
        return None

    for pattern in pdb_search_patterns:
        search_pattern = pattern.format(design_id=design_id)
        matches = list(pdb_dir.glob(search_pattern))
        if matches:
            return str(matches[0])
    return None


def detect_run_type(path: Path) -> Optional[Dict[str, Any]]:
    """Detect the run type using declarative signatures.

    Returns the matching signature with run_name extracted, or None if no match.
    """
    if not path.is_dir():
        return None

    # Sort signatures by priority (higher priority first)
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

        # If we get here, this signature matches
        return {**signature, "run_name": run_name, "detected_path": str(path)}

    return None


def find_runs_recursive(root_path: Path) -> List[Dict[str, Any]]:
    runs: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root_path, followlinks=True):
        current_dir = Path(dirpath)
        if current_dir.name == "work":
            dirnames[:] = []
            continue

        # Skip directories that are inside batches subdirectories of nf-binder-design runs
        path_parts = current_dir.parts
        if "batches" in path_parts:
            # Check if this is inside an nf-binder-design run by looking for the pattern
            # {run_name}/results/bindcraft/batches/{n}/...
            try:
                batches_index = path_parts.index("batches")
                if (
                    batches_index >= 2
                    and path_parts[batches_index - 1] == "bindcraft"
                    and path_parts[batches_index - 2] == "results"
                ):
                    # This is inside a batches directory of an nf-binder-design run, skip it
                    dirnames[:] = []
                    continue
            except ValueError:
                pass  # "batches" not found in path_parts

        # Use declarative detection
        detected_run = detect_run_type(current_dir)
        if detected_run:
            run_id = str(uuid.uuid4())
            guessed_project_id = guess_project_id(current_dir)
            run_name = detected_run["run_name"]

            # Use the results table and PDB pattern directly from the signature
            results_table = detected_run["results_table"]
            pdb_pattern = detected_run["pdb_pattern"]

            # Find PDB files using the pattern
            pdb_files = [str(p) for p in current_dir.glob(pdb_pattern)]

            # Determine if this is an nf-binder-design run
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
                    "signature": detected_run,  # Store the full signature for use in parse_designs_from_run
                    "metadata": {
                        "name": run_name,
                        "original_name": current_dir.name,
                        "parent_path": str(current_dir.parent),
                        "pdb_count": len(pdb_files),
                    },
                }
            )

            # Handle directory skipping based on signature
            if "skip_dirs" in detected_run and detected_run["skip_dirs"]:
                # Remove directories that should be skipped from dirnames
                skip_dir_names = []
                for skip_path_str in detected_run["skip_dirs"]:
                    skip_path = current_dir / skip_path_str
                    if skip_path.is_dir():
                        skip_dir_names.append(skip_path.name)
                dirnames[:] = [d for d in dirnames if d not in skip_dir_names]
            else:
                # Stop walking this directory tree since we found a run
                dirnames[:] = []
    return runs


def load_run_table(run_metadata: Dict[str, Any]) -> Optional[pd.DataFrame]:
    try:
        merged_paths = run_metadata.get("merged_paths", [run_metadata["path"]])
        results_table = run_metadata.get("results_table")
        if not results_table:
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
                # Coerce numeric-like object columns to numeric dtype where fully parseable
                # This avoids returning numbers as strings, without forcing partial coercion.
                for col in df.columns:
                    if df[col].dtype == object:
                        df[col] = pd.to_numeric(df[col], errors="ignore")
                df = _standardise_dataframe_columns(df, run_metadata.get("method", ""))
                df["source_path"] = str(path)
                all_dfs.append(df)
            except Exception as e:
                logger.error(f"Error loading table from {table_path}: {str(e)}")
                continue
        if not all_dfs:
            logger.warning(
                f"No valid tables found for run: {run_metadata.get('path', 'unknown')}"
            )
            return None
        if len(all_dfs) == 1:
            return all_dfs[0]
        else:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            logger.info(
                f"Combined {len(all_dfs)} tables for merged run, total rows: {len(combined_df)}"
            )
            return combined_df
    except Exception as e:
        logger.error(f"Error loading run table: {str(e)}")
        return None


def _standardise_dataframe_columns(df: pd.DataFrame, method: str) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    canonical_groups: Dict[str, List[str]] = {
        "Sequence": [
            "Sequence",
            "sequence",
            "AA_sequence",
            "aa_sequence",
            "binder_sequence",
            "binder_seq",
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


def parse_designs_from_run(run_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        df = load_run_table(run_metadata)
        if df is None or df.empty:
            return []

        designs: List[Dict[str, Any]] = []
        run_path = run_metadata["path"]
        run_name = run_metadata["metadata"]["name"]
        signature = run_metadata.get("signature", {})

        # Get configuration from signature
        design_id_columns = signature.get("design_id_columns", [])
        primary_score_columns = signature.get("primary_score_columns", [])
        sort_ascending = signature.get("sort_ascending", True)
        pdb_search_patterns = signature.get("pdb_search_patterns", ["{design_id}.pdb"])

        # Find design ID column
        design_id_col = None
        for col_name in design_id_columns:
            if col_name in df.columns:
                design_id_col = col_name
                break

        # Fallback: look for common design ID column names
        if not design_id_col:
            for col in df.columns:
                if col.lower() in ["design", "description", "name", "id"]:
                    design_id_col = col
                    break

        # Find primary score column
        primary_score_col = None
        for col_name in primary_score_columns:
            if col_name in df.columns:
                primary_score_col = col_name
                break

        # Fallback: use first numeric column
        if not primary_score_col:
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if numeric_cols:
                primary_score_col = numeric_cols[0]

        # Sort by primary score if available
        if primary_score_col and primary_score_col in df.columns:
            df = df.sort_values(
                primary_score_col, ascending=sort_ascending
            ).reset_index(drop=True)

        # Determine PDB base directory from the pdb_pattern
        pdb_pattern = signature.get("pdb_pattern", "")
        pdb_base_dir = pdb_pattern.split("/*.pdb")[0] if "/*.pdb" in pdb_pattern else ""

        for index, row in df.iterrows():
            design_id = (
                str(row.get(design_id_col, f"design_{index}"))
                if design_id_col
                else f"design_{index}"
            )

            # Find PDB file using signature configuration
            pdb_file = _find_pdb_file_for_design(
                Path(run_path), design_id, pdb_search_patterns, pdb_base_dir
            )

            # Extract backbone_id for MPNN filtering
            backbone_id = extract_backbone_id(design_id, run_metadata["method"])

            design: Dict[str, Any] = {
                "design_id": design_id,
                "backbone_id": backbone_id,
                "run_id": run_metadata["run_id"],
                "project_id": run_metadata.get("project_id", ""),
                "run_name": run_name,
                "method": run_metadata["method"],
                "run_path": run_path,
                "pdb_file": pdb_file,
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
            designs.append(design)
        return designs
    except Exception as e:
        logger.error(
            f"Error parsing designs from run {run_metadata['run_id']}: {str(e)}"
        )
        return []
