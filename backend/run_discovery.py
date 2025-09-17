import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


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


def is_bindcraft_results(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (path / "final_design_stats.csv").is_file() and (path / "Accepted").is_dir()


def is_rfd_results(path: Path) -> bool:
    if not path.is_dir():
        return False
    combined_file = path / "combined_scores.tsv"
    if combined_file.is_file():
        return True
    cs_files = list((path / "af2_initial_guess" / "scores").glob("*.cs"))
    if cs_files:
        return True
    cs_files = list((path / "af2_initial_guess").glob("*.cs"))
    return len(cs_files) > 0


def find_runs_recursive(root_path: Path) -> List[Dict[str, Any]]:
    runs: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root_path, followlinks=True):
        current_dir = Path(dirpath)
        if current_dir.name == "work":
            dirnames[:] = []
            continue

        method: Optional[str] = None
        results_table: Optional[str] = None
        pdb_files: List[str] = []

        if is_bindcraft_results(current_dir):
            method = "bindcraft"
            results_table = "final_design_stats.csv"
            accepted_dir = current_dir / "Accepted"
            if accepted_dir.is_dir():
                pdb_files = [str(p) for p in accepted_dir.glob("*.pdb")]
        elif is_rfd_results(current_dir):
            method = "rfd"
            combined_file = current_dir / "combined_scores.tsv"
            if combined_file.is_file():
                results_table = "combined_scores.tsv"
            pdbs_dir = current_dir / "af2_initial_guess" / "pdbs"
            if pdbs_dir.is_dir():
                pdb_files = [str(p) for p in pdbs_dir.glob("*.pdb")]

        if method:
            run_id = str(uuid.uuid4())
            guessed_project_id = guess_project_id(current_dir)
            guessed_name = guess_run_name(current_dir)
            runs.append(
                {
                    "run_id": run_id,
                    "project_id": guessed_project_id,
                    "path": str(current_dir),
                    "method": method,
                    "results_table": results_table,
                    "pdb_files": pdb_files,
                    "metadata": {
                        "name": guessed_name,
                        "original_name": current_dir.name,
                        "parent_path": str(current_dir.parent),
                        "pdb_count": len(pdb_files),
                    },
                }
            )
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
        method = run_metadata["method"]
        run_path = run_metadata["path"]
        run_name = run_metadata["metadata"]["name"]

        if method == "bindcraft":
            design_id_col = "Design" if "Design" in df.columns else None
            primary_score_col = (
                "Average_i_pTM" if "Average_i_pTM" in df.columns else None
            )
            sort_ascending = False
        elif method == "rfd":
            design_id_col = "description" if "description" in df.columns else None
            primary_score_col = (
                "pae_interaction" if "pae_interaction" in df.columns else None
            )
            sort_ascending = True
        else:
            design_id_col = None
            primary_score_col = None
            sort_ascending = True

        if not design_id_col:
            for col in df.columns:
                if col.lower() in ["design", "description", "name", "id"]:
                    design_id_col = col
                    break

        if not primary_score_col:
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if numeric_cols:
                primary_score_col = numeric_cols[0]

        if primary_score_col and primary_score_col in df.columns:
            df = df.sort_values(
                primary_score_col, ascending=sort_ascending
            ).reset_index(drop=True)

        for index, row in df.iterrows():
            design_id = (
                str(row.get(design_id_col, f"design_{index}"))
                if design_id_col
                else f"design_{index}"
            )
            pdb_file: Optional[str] = None
            if method == "bindcraft":
                accepted_dir = Path(run_path) / "Accepted"
                if accepted_dir.exists():
                    exact_pdb = accepted_dir / f"{design_id}.pdb"
                    if exact_pdb.exists():
                        pdb_file = str(exact_pdb)
                    else:
                        potential_pdbs = list(accepted_dir.glob(f"{design_id}_*.pdb"))
                        if potential_pdbs:
                            pdb_file = str(potential_pdbs[0])
                        else:
                            potential_pdbs = list(
                                accepted_dir.glob(f"{design_id}*.pdb")
                            )
                            if potential_pdbs:
                                pdb_file = str(potential_pdbs[0])
            elif method == "rfd":
                pdbs_dir = Path(run_path) / "af2_initial_guess" / "pdbs"
                if pdbs_dir.exists():
                    pdb_path = pdbs_dir / f"{design_id}.pdb"
                    if pdb_path.exists():
                        pdb_file = str(pdb_path)

            design: Dict[str, Any] = {
                "design_id": design_id,
                "run_id": run_metadata["run_id"],
                "project_id": run_metadata.get("project_id", ""),
                "run_name": run_name,
                "method": method,
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
