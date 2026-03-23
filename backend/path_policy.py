from pathlib import Path
from typing import List


def resolved_base_dirs(base_dirs: List[str]) -> List[Path]:
    out: List[Path] = []
    for raw in base_dirs:
        s = raw.strip()
        if not s:
            continue
        try:
            out.append(Path(s).expanduser().resolve())
        except (OSError, RuntimeError):
            continue
    return out


def is_under_any_base(candidate: Path, bases: List[Path]) -> bool:
    for base in bases:
        if candidate == base:
            return True
        try:
            candidate.relative_to(base)
            return True
        except ValueError:
            continue
    return False


def is_allowed_path(path_str: str, base_dir_strings: List[str]) -> bool:
    if not base_dir_strings:
        return True
    try:
        candidate = Path(path_str).expanduser().resolve()
    except (OSError, RuntimeError):
        return False
    bases = resolved_base_dirs(base_dir_strings)
    if not bases:
        return True
    return is_under_any_base(candidate, bases)
