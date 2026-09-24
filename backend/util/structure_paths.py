"""Resolve a structure-file basename to its path within a run's discovered files.

Extracted from routers/files.py so non-router code (the bundle builder) can resolve
structure paths without importing a router. files.py re-exports it under its original
private name, so existing callers are unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..config.method_paths import structure_resolve_uses_strip_after_first_underscore


def resolve_structure_path(
    structure_files: List[str], filename: str, method: Optional[str]
) -> Optional[Path]:
    basename_to_path: dict[str, Path] = {Path(p).name: Path(p) for p in structure_files}
    if filename in basename_to_path:
        return basename_to_path[filename]
    if structure_resolve_uses_strip_after_first_underscore(method):
        for p in structure_files:
            name = Path(p).name
            if "_" in name:
                rest = name.split("_", 1)[1]
                if rest == filename:
                    return Path(p)
    if not filename.endswith(".gz"):
        gz_name = f"{filename}.gz"
        if gz_name in basename_to_path:
            return basename_to_path[gz_name]
    return None
