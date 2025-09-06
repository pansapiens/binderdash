from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel
import logging
from typing import List, Optional, Dict, Any
from fastapi import HTTPException
from pathlib import Path
import pandas as pd
import uuid
import io
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RawSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    run_base_dirs: str = ""
    allowed_users: str = ""
    local_users: str = ""


class AppSettings(BaseModel):
    run_base_dirs: List[str] = []
    allowed_users: List[str] = []
    local_users: List[str] = []


class ScanRequest(BaseModel):
    folders: List[str]


class RunMetadata(BaseModel):
    run_id: str
    project_id: str
    path: str
    run_type: str  # "bindcraft" or "rfd"
    results_table: Optional[str] = None
    pdb_files: List[str] = []
    metadata: Dict[str, Any] = {}


raw_settings = RawSettings()
settings = AppSettings(
    run_base_dirs=(
        [item.strip() for item in raw_settings.run_base_dirs.split(",")]
        if raw_settings.run_base_dirs
        else []
    ),
    allowed_users=(
        [item.strip() for item in raw_settings.allowed_users.split(",")]
        if raw_settings.allowed_users
        else []
    ),
    local_users=(
        [item.strip() for item in raw_settings.local_users.split(",")]
        if raw_settings.local_users
        else []
    ),
)

app = FastAPI()

# Mount the frontend static files
app.mount("/assets", StaticFiles(directory="backend/static/assets"), name="assets")
app.mount("/static", StaticFiles(directory="backend/static"), name="static")


@app.get("/favicon.ico")
async def get_favicon():
    """Serve the favicon."""
    return FileResponse("backend/static/favicon.ico")


# In-memory cache for run metadata
run_cache: Dict[str, Dict[str, Any]] = {}

# In-memory cache for designs
designs_cache: List[Dict[str, Any]] = []


def guess_project_id(path: Path) -> str:
    """
    Guess the project ID based on the path, avoiding disallowed names.
    First finds the run name, then looks for a valid project name below it in the tree.

    Args:
        path: Path to the run directory

    Returns:
        Guessed project ID
    """
    # First, find the run name using the existing function
    run_name = guess_run_name(path)

    # Regex patterns for disallowed names
    disallowed_patterns = [
        r"^runs$",  # exact match for runs
        r"^results.*$",  # results, results_1, results_final, etc.
        r"^batch.*$",  # batch, batch_1, batch_final, etc.
        r"^bindcraft$",  # exact match for bindcraft
        r"^rfd$",  # exact match for rfd
        r"^\d+$",  # numeric-only names
    ]

    # Start from the current directory and work up the path
    current_path = path
    found_run_name = False

    while current_path != current_path.parent:  # Stop at root
        name = current_path.name

        # Check if we've found the run name
        if name == run_name:
            found_run_name = True
            # Move up one level to start looking for project ID below the run name
            current_path = current_path.parent
            continue

        # Only start looking for project ID after we've found the run name
        if found_run_name:
            # Check if name matches any disallowed pattern
            is_disallowed = any(
                re.match(pattern, name) for pattern in disallowed_patterns
            )

            if not is_disallowed:
                return name

        # Move up one level
        current_path = current_path.parent

    # If we can't find a good name, return empty string
    return ""


def guess_run_name(path: Path) -> str:
    """
    Guess the run name based on the path, avoiding disallowed names.

    Args:
        path: Path to the run directory

    Returns:
        Guessed run name
    """
    # Regex patterns for disallowed names
    disallowed_patterns = [
        r"^results.*$",  # results, results_1, results_final, etc.
        r"^bindcraft$",  # exact match for bindcraft
        r"^batches$",  # exact match for batches
        r"^\d+$",  # numeric-only names
    ]

    # Start from the current directory and work up the path
    current_path = path

    while current_path != current_path.parent:  # Stop at root
        name = current_path.name

        # Check if name matches any disallowed pattern
        is_disallowed = any(re.match(pattern, name) for pattern in disallowed_patterns)

        if not is_disallowed:
            return name

        # Move up one level
        current_path = current_path.parent

    # If we can't find a good name, use the original directory name
    return path.name


def is_bindcraft_results(path: Path) -> bool:
    """Check if a directory contains BindCraft results (final_design_stats.csv and Accepted/ folder)."""
    if not path.is_dir():
        return False
    stats_file = path / "final_design_stats.csv"
    accepted_folder = path / "Accepted"
    return stats_file.is_file() and accepted_folder.is_dir()


def is_rfd_results(path: Path) -> bool:
    """Check if a directory contains RFD results (combined_scores.tsv or .cs files)."""
    if not path.is_dir():
        return False

    # Check for combined_scores.tsv first
    combined_file = path / "combined_scores.tsv"
    if combined_file.is_file():
        return True

    # Check for .cs files in af2_initial_guess/scores/
    cs_files = list((path / "af2_initial_guess" / "scores").glob("*.cs"))
    if cs_files:
        return True

    # Check for .cs files in af2_initial_guess/ (deprecated location)
    cs_files = list((path / "af2_initial_guess").glob("*.cs"))
    return len(cs_files) > 0


def find_runs_recursive(root_path: Path) -> List[Dict[str, Any]]:
    """Recursively find all valid run directories within root_path."""
    runs = []

    for dirpath, dirnames, filenames in os.walk(root_path, followlinks=True):
        current_dir = Path(dirpath)

        # Skip 'work' directories
        if current_dir.name == "work":
            dirnames[:] = []  # Stop recursion into work directories
            continue

        # Check if this directory is a valid run
        run_type = None
        results_table = None
        pdb_files = []

        if is_bindcraft_results(current_dir):
            run_type = "bindcraft"
            results_table = "final_design_stats.csv"

            # Find PDB files in Accepted/ directory
            accepted_dir = current_dir / "Accepted"
            if accepted_dir.is_dir():
                pdb_files = [str(p) for p in accepted_dir.glob("*.pdb")]

        elif is_rfd_results(current_dir):
            run_type = "rfd"

            # Determine results table path
            combined_file = current_dir / "combined_scores.tsv"
            if combined_file.is_file():
                results_table = "combined_scores.tsv"

            # Find PDB files in af2_initial_guess/pdbs/
            pdbs_dir = current_dir / "af2_initial_guess" / "pdbs"
            if pdbs_dir.is_dir():
                pdb_files = [str(p) for p in pdbs_dir.glob("*.pdb")]

        if run_type:
            # Create unique run ID
            run_id = str(uuid.uuid4())

            # Guess project ID and run name using the new functions
            guessed_project_id = guess_project_id(current_dir)
            guessed_name = guess_run_name(current_dir)

            runs.append(
                {
                    "run_id": run_id,
                    "project_id": guessed_project_id,
                    "path": str(current_dir),
                    "run_type": run_type,
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

            # Stop recursion into this directory to avoid nested runs
            dirnames[:] = []

    return runs


def get_run_metadata(run_id: str) -> Optional[Dict[str, Any]]:
    """Get run metadata from cache."""
    return run_cache.get(run_id)


def load_run_table(run_metadata: Dict[str, Any]) -> Optional[pd.DataFrame]:
    """Load and parse the results table for a run."""
    try:
        run_path = Path(run_metadata["path"])
        results_table = run_metadata.get("results_table")

        if not results_table:
            return None

        table_path = run_path / results_table

        if not table_path.exists():
            logger.warning(f"Results table not found: {table_path}")
            return None

        # Load based on file extension
        if table_path.suffix.lower() == ".csv":
            df = pd.read_csv(table_path)
        elif table_path.suffix.lower() == ".tsv":
            df = pd.read_csv(table_path, sep="\t")
        else:
            logger.warning(f"Unsupported table format: {table_path}")
            return None

        return df

    except Exception as e:
        logger.error(f"Error loading run table: {str(e)}")
        return None


def parse_designs_from_run(run_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse designs from a run's results table."""
    try:
        df = load_run_table(run_metadata)
        if df is None or df.empty:
            return []

        designs = []
        run_type = run_metadata["run_type"]
        run_path = run_metadata["path"]
        run_name = run_metadata["metadata"]["name"]

        # Determine the design ID column and primary score column based on run type
        if run_type == "bindcraft":
            design_id_col = "Design" if "Design" in df.columns else None
            primary_score_col = (
                "Average_i_pTM" if "Average_i_pTM" in df.columns else None
            )
            # Sort by primary score descending (higher is better for i_pTM)
            sort_ascending = False
        elif run_type == "rfd":
            design_id_col = "description" if "description" in df.columns else None
            primary_score_col = (
                "pae_interaction" if "pae_interaction" in df.columns else None
            )
            # Sort by primary score ascending (lower is better for pae_interaction)
            sort_ascending = True
        else:
            # Unknown run type, try to guess columns
            design_id_col = None
            primary_score_col = None
            sort_ascending = True

        # Find design ID column if not found
        if not design_id_col:
            for col in df.columns:
                if col.lower() in ["design", "description", "name", "id"]:
                    design_id_col = col
                    break

        # Find primary score column if not found
        if not primary_score_col:
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if numeric_cols:
                primary_score_col = numeric_cols[0]

        # Sort by primary score if available
        if primary_score_col and primary_score_col in df.columns:
            df = df.sort_values(
                primary_score_col, ascending=sort_ascending
            ).reset_index(drop=True)

        # Create design objects
        for index, row in df.iterrows():
            design_id = (
                str(row.get(design_id_col, f"design_{index}"))
                if design_id_col
                else f"design_{index}"
            )

            # Note: Score columns are now handled as regular columns in the frontend

            # Find PDB file for this design
            pdb_file = None
            if run_type == "bindcraft":
                # For bindcraft, look for PDB in Accepted/ directory
                accepted_dir = Path(run_path) / "Accepted"
                if accepted_dir.exists():
                    # Try exact match first
                    exact_pdb = accepted_dir / f"{design_id}.pdb"
                    if exact_pdb.exists():
                        pdb_file = str(exact_pdb)
                    else:
                        # Try pattern matching
                        potential_pdbs = list(accepted_dir.glob(f"{design_id}_*.pdb"))
                        if potential_pdbs:
                            pdb_file = str(potential_pdbs[0])
                        else:
                            # Last resort: any PDB starting with design_id
                            potential_pdbs = list(
                                accepted_dir.glob(f"{design_id}*.pdb")
                            )
                            if potential_pdbs:
                                pdb_file = str(potential_pdbs[0])

            elif run_type == "rfd":
                # For RFD, look for PDB in af2_initial_guess/pdbs/
                pdbs_dir = Path(run_path) / "af2_initial_guess" / "pdbs"
                if pdbs_dir.exists():
                    pdb_path = pdbs_dir / f"{design_id}.pdb"
                    if pdb_path.exists():
                        pdb_file = str(pdb_path)

            # Create design object with all available columns
            design = {
                "design_id": design_id,
                "run_id": run_metadata["run_id"],
                "project_id": run_metadata.get("project_id", ""),
                "run_name": run_name,
                "run_type": run_type,
                "run_path": run_path,
                "pdb_file": pdb_file,
                # Include all other columns from the source table
                **{
                    col: row[col]
                    for col in df.columns
                    if col != design_id_col and pd.notna(row[col])
                },
            }

            designs.append(design)

        return designs

    except Exception as e:
        logger.error(
            f"Error parsing designs from run {run_metadata['run_id']}: {str(e)}"
        )
        return []


def refresh_designs_cache():
    """Refresh the designs cache by parsing all cached runs."""
    global designs_cache

    try:
        designs_cache.clear()

        for run in run_cache.values():
            run_designs = parse_designs_from_run(run)
            designs_cache.extend(run_designs)

            # Sort all designs by score (if available)
        designs_with_score = []
        designs_without_score = []

        for design in designs_cache:
            has_score = False
            if design["run_type"] == "rfd" and "pae_interaction" in design:
                has_score = True
            elif design["run_type"] == "bindcraft" and "Average_i_pTM" in design:
                has_score = True

            if has_score:
                designs_with_score.append(design)
            else:
                designs_without_score.append(design)

        # Sort by score, handling different run types
        def sort_key(design):
            if design["run_type"] == "rfd":
                score = design.get("pae_interaction")
                if score is None:
                    return float("inf")  # Put designs without scores at the end
                return score  # Lower is better for pae_interaction
            else:  # bindcraft
                score = design.get("Average_i_pTM")
                if score is None:
                    return float("inf")  # Put designs without scores at the end
                return -score  # Higher is better for i_pTM, so invert

        designs_with_score.sort(key=sort_key)

        # Combine sorted designs with those without scores
        designs_cache = designs_with_score + designs_without_score

        logger.info(
            f"Refreshed designs cache: {len(designs_cache)} designs from {len(run_cache)} runs"
        )

    except Exception as e:
        logger.error(f"Error refreshing designs cache: {str(e)}")
        designs_cache = []


@app.get("/")
async def serve_frontend():
    """Serve the frontend index.html file."""
    return FileResponse("backend/static/index.html")


@app.get("/api/tree")
async def get_tree(path: str = ""):
    """
    Return folder structure for the file browser.

    Args:
        path: Optional path parameter to get children of a specific directory

    Returns:
        List of folder objects with name, path, and has_children flag
    """
    logger.info(
        f"get_tree called with path: '{path}', run_base_dirs: {settings.run_base_dirs}"
    )
    try:
        if not path:
            # Return base directories
            folders = []
            for base_dir in settings.run_base_dirs:
                if os.path.exists(base_dir) and os.path.isdir(base_dir):
                    folders.append(
                        {
                            "name": os.path.basename(base_dir),
                            "path": base_dir,
                            "has_children": True,
                        }
                    )

            # If no base directories are configured, provide a fallback
            if not folders:
                logger.warning("No base directories configured in RUN_BASE_DIRS")
                # For development, allow browsing from current working directory
                current_dir = os.getcwd()
                if os.path.exists(current_dir) and os.path.isdir(current_dir):
                    folders.append(
                        {
                            "name": "Current Directory",
                            "path": current_dir,
                            "has_children": True,
                        }
                    )

            return {"folders": folders}
        else:
            # Return children of the specified path
            if not os.path.exists(path) or not os.path.isdir(path):
                raise ValueError(f"Path does not exist or is not a directory: {path}")

            # Validate path is within allowed base directories (only if base directories are configured)
            if settings.run_base_dirs:
                is_allowed = any(
                    path.startswith(base_dir) for base_dir in settings.run_base_dirs
                )
                if not is_allowed:
                    raise ValueError(
                        f"Path not within allowed base directories: {path}"
                    )
            else:
                # If no base directories configured, allow any path for development
                logger.warning(
                    f"No base directories configured, allowing access to: {path}"
                )

            folders = []
            logger.info(f"Listing contents of directory: {path}")
            try:
                items = os.listdir(path)
                logger.info(
                    f"Found {len(items)} items in {path}: {items[:10]}..."
                )  # Log first 10 items
                for item in items:
                    item_path = os.path.join(path, item)
                    if os.path.isdir(item_path) or os.path.islink(item_path):
                        # Check if directory or symlink has subdirectories
                        has_children = False
                        try:
                            if os.path.islink(item_path):
                                # For symlinks, check the target
                                target_path = os.path.realpath(item_path)
                                if os.path.isdir(target_path):
                                    has_children = any(
                                        os.path.isdir(
                                            os.path.join(target_path, subitem)
                                        )
                                        for subitem in os.listdir(target_path)
                                    )
                            else:
                                # For regular directories
                                has_children = any(
                                    os.path.isdir(os.path.join(item_path, subitem))
                                    for subitem in os.listdir(item_path)
                                )
                        except (PermissionError, OSError):
                            # If we can't access the directory, assume it has children
                            has_children = True

                        folders.append(
                            {
                                "name": item,
                                "path": item_path,
                                "has_children": has_children,
                            }
                        )
            except PermissionError:
                logger.warning(f"Permission denied accessing directory: {path}")
                return {"folders": []}

            return {"folders": folders}

    except Exception as e:
        logger.error(f"Error in get_tree: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/runs/scan")
async def scan_runs(request: ScanRequest):
    """
    Scan selected folders for valid run directories.

    Args:
        request: ScanRequest containing list of folder paths to scan

    Returns:
        List of run metadata objects
    """
    try:
        runs = []

        for folder_path in request.folders:
            # Validate path is within allowed base directories
            is_allowed = any(
                folder_path.startswith(base_dir) for base_dir in settings.run_base_dirs
            )
            if not is_allowed:
                logger.warning(
                    f"Skipping path not within allowed base directories: {folder_path}"
                )
                continue

            path = Path(folder_path)
            if not path.exists() or not path.is_dir():
                logger.warning(
                    f"Skipping non-existent or non-directory path: {folder_path}"
                )
                continue

            # Find runs in this folder
            folder_runs = find_runs_recursive(path)
            runs.extend(folder_runs)

            logger.info(f"Found {len(folder_runs)} runs in {folder_path}")

        # Cache the run metadata
        for run in runs:
            run_cache[run["run_id"]] = run

        # Refresh designs cache with new runs
        refresh_designs_cache()

        return {"runs": runs}

    except Exception as e:
        logger.error(f"Error in scan_runs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs/{run_id}/table")
async def get_run_table(run_id: str):
    """
    Get the results table data for a specific run.

    Args:
        run_id: Unique identifier for the run

    Returns:
        Table data as JSON
    """
    try:
        run_metadata = get_run_metadata(run_id)
        if not run_metadata:
            raise HTTPException(status_code=404, detail="Run not found")

        df = load_run_table(run_metadata)
        if df is None:
            raise HTTPException(
                status_code=404, detail="Results table not found or could not be loaded"
            )

        # Convert DataFrame to JSON
        return {
            "columns": df.columns.tolist(),
            "data": df.to_dict(orient="records"),
            "total_rows": len(df),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_run_table: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs/{run_id}/files/pdb/{filename}")
async def get_pdb_file(run_id: str, filename: str):
    """
    Stream PDB file for a specific run.

    Args:
        run_id: Unique identifier for the run
        filename: Name of the PDB file

    Returns:
        PDB file content
    """
    try:
        run_metadata = get_run_metadata(run_id)
        if not run_metadata:
            raise HTTPException(status_code=404, detail="Run not found")

        # Validate filename is in the run's PDB files
        pdb_files = run_metadata.get("pdb_files", [])
        if not any(Path(pdb_file).name == filename for pdb_file in pdb_files):
            raise HTTPException(status_code=404, detail="PDB file not found in run")

        # Find the full path to the PDB file
        pdb_path = None
        for pdb_file in pdb_files:
            if Path(pdb_file).name == filename:
                pdb_path = Path(pdb_file)
                break

        if not pdb_path or not pdb_path.exists():
            raise HTTPException(status_code=404, detail="PDB file not found on disk")

        # Stream the file
        return FileResponse(
            str(pdb_path), media_type="chemical/x-pdb", filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_pdb_file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs")
async def list_runs():
    """
    List all cached runs.

    Returns:
        List of run metadata objects
    """
    return {"runs": list(run_cache.values())}


@app.delete("/api/runs/{run_id}")
async def delete_run(run_id: str):
    """
    Remove a run from the cache.

    Args:
        run_id: Unique identifier for the run

    Returns:
        Success message
    """
    if run_id in run_cache:
        del run_cache[run_id]
        return {"message": "Run removed from cache"}
    else:
        raise HTTPException(status_code=404, detail="Run not found")


@app.delete("/api/runs")
async def clear_runs():
    """
    Clear all runs from the cache.

    Returns:
        Success message
    """
    run_cache.clear()
    return {"message": "All runs cleared from cache"}


@app.get("/api/designs")
async def list_designs():
    """
    List all designs from all cached runs.

    Returns:
        List of design objects
    """
    try:
        # Refresh designs cache if it's empty
        if not designs_cache:
            refresh_designs_cache()

        return {"designs": designs_cache}

    except Exception as e:
        logger.error(f"Error in list_designs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/designs")
async def clear_designs():
    """
    Clear all designs from the cache.

    Returns:
        Success message
    """
    try:
        designs_cache.clear()
        return {"message": "All designs cleared from cache"}

    except Exception as e:
        logger.error(f"Error in clear_designs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
