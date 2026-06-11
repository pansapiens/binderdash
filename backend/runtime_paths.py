import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def backend_root() -> Path:
    return Path(__file__).resolve().parent


def static_root() -> Path:
    override = (os.environ.get("BINDERDASH_STATIC_ROOT") or "").strip()
    if override:
        return Path(override)
    if is_frozen():
        return Path(sys._MEIPASS) / "backend" / "static"
    return backend_root() / "static"
