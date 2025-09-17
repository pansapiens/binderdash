import logging
import os
import stat
import tarfile
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from ..auth import (
    get_current_user_optional,
    get_current_user_optional_with_query,
)
from ..cache import get_run_metadata
from ..settings import LocalUser, settings
from ..schemas import PdbTarRequest


# Router for run file endpoints
router = APIRouter(prefix="/api/runs", tags=["files"])


@router.get("/{run_id}/files/pdb/{filename}")
async def get_pdb_file(
    run_id: str,
    filename: str,
    current_user: Optional[LocalUser] = Depends(get_current_user_optional_with_query),
):
    try:
        run_metadata = get_run_metadata(run_id)
        if not run_metadata:
            raise HTTPException(status_code=404, detail="Run not found")

        pdb_files = run_metadata.get("pdb_files", [])
        if not any(Path(pdb_file).name == filename for pdb_file in pdb_files):
            raise HTTPException(status_code=404, detail="PDB file not found in run")

        pdb_path: Optional[Path] = None
        for pdb_file in pdb_files:
            if Path(pdb_file).name == filename:
                pdb_path = Path(pdb_file)
                break

        if not pdb_path or not pdb_path.exists():
            raise HTTPException(status_code=404, detail="PDB file not found on disk")

        return FileResponse(
            str(pdb_path), media_type="chemical/x-pdb", filename=filename
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        getLogger(__name__).error(f"Error in get_pdb_file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Router for PDB tar streaming
pdbs_router = APIRouter(prefix="/api/pdbs", tags=["pdbs"])


def stream_tar_archive(file_entries: List[Tuple[str, Path]]):
    for arcname, fpath in file_entries:
        try:
            fstat = fpath.stat()
            if not stat.S_ISREG(fstat.st_mode):
                logging.getLogger(__name__).warning(
                    f"Skipping non-regular file: {fpath}"
                )
                continue
            tarinfo = tarfile.TarInfo(name=arcname)
            tarinfo.size = fstat.st_size
            tarinfo.mtime = int(fstat.st_mtime)
            tarinfo.mode = fstat.st_mode
            tarinfo.type = tarfile.REGTYPE
            yield tarinfo.tobuf()
            with fpath.open("rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    yield chunk
            padding_size = (512 - (fstat.st_size % 512)) % 512
            if padding_size > 0:
                yield b"\0" * padding_size
        except FileNotFoundError:
            logging.getLogger(__name__).warning(
                f"File not found for tar archive: {fpath}"
            )
            continue
        except Exception as e:
            logging.getLogger(__name__).error(
                f"Error processing file {fpath} for tar: {e}"
            )
            continue
    yield b"\0" * 1024


@pdbs_router.post("/tar")
async def download_pdbs_tar(
    request: PdbTarRequest,
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    try:
        if not request.items:
            raise HTTPException(status_code=400, detail="No items provided")
        file_entries: List[Tuple[str, Path]] = []
        for item in request.items:
            run = get_run_metadata(item.run_id)
            if not run:
                logging.getLogger(__name__).warning(
                    f"Run not found for tar request: {item.run_id}"
                )
                continue
            pdb_paths = run.get("pdb_files", [])
            matched = None
            for p in pdb_paths:
                if Path(p).name == item.filename:
                    matched = Path(p)
                    break
            if matched and matched.exists():
                project_id = run.get("project_id", "project") or "project"
                run_name = run.get("metadata", {}).get("name", "run") or "run"
                arcname = f"{project_id}/{run_name}/{item.filename}"
                file_entries.append((arcname, matched))
            else:
                logging.getLogger(__name__).warning(
                    f"Requested PDB not found in run {item.run_id}: {item.filename}"
                )
        if not file_entries:
            raise HTTPException(status_code=404, detail="No valid PDB files found")
        headers = {"Content-Disposition": "attachment; filename=designs_pdbs.tar"}
        return StreamingResponse(
            stream_tar_archive(file_entries),
            media_type="application/x-tar",
            headers=headers,
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger(__name__).error(f"Error creating PDBs tar: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Router for directory tree browsing
tree_router = APIRouter(tags=["tree"])


@tree_router.get("/api/tree")
async def get_tree(
    path: str = "",
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    logging.getLogger(__name__).info(
        f"get_tree called with path: '{path}', run_base_dirs: {settings.run_base_dirs}"
    )
    try:
        if not path:
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
            if not folders:
                logging.getLogger(__name__).warning(
                    "No base directories configured in RUN_BASE_DIRS"
                )
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
            if not os.path.exists(path) or not os.path.isdir(path):
                raise ValueError(f"Path does not exist or is not a directory: {path}")

            if settings.run_base_dirs:
                is_allowed = any(
                    path.startswith(base_dir) for base_dir in settings.run_base_dirs
                )
                if not is_allowed:
                    raise ValueError(
                        f"Path not within allowed base directories: {path}"
                    )
            else:
                logging.getLogger(__name__).warning(
                    f"No base directories configured, allowing access to: {path}"
                )

            folders = []
            logging.getLogger(__name__).info(f"Listing contents of directory: {path}")
            try:
                items = os.listdir(path)
                logging.getLogger(__name__).info(
                    f"Found {len(items)} items in {path}: {items[:10]}..."
                )
                for item in items:
                    item_path = os.path.join(path, item)
                    if os.path.isdir(item_path) or os.path.islink(item_path):
                        has_children = False
                        try:
                            if os.path.islink(item_path):
                                target_path = os.path.realpath(item_path)
                                if os.path.isdir(target_path):
                                    has_children = any(
                                        os.path.isdir(
                                            os.path.join(target_path, subitem)
                                        )
                                        for subitem in os.listdir(target_path)
                                    )
                            else:
                                has_children = any(
                                    os.path.isdir(os.path.join(item_path, subitem))
                                    for subitem in os.listdir(item_path)
                                )
                        except (PermissionError, OSError):
                            has_children = True

                        folders.append(
                            {
                                "name": item,
                                "path": item_path,
                                "has_children": has_children,
                            }
                        )
            except PermissionError:
                logging.getLogger(__name__).warning(
                    f"Permission denied accessing directory: {path}"
                )
                return {"folders": []}

            return {"folders": folders}
    except Exception as e:
        logging.getLogger(__name__).error(f"Error in get_tree: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
