import os
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def user_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", "")
        if not base:
            base = str(Path.home() / "AppData" / "Local")
        path = Path(base) / "Binderdash"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "Binderdash"
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "")
        if xdg:
            path = Path(xdg) / "binderdash"
        else:
            path = Path.home() / ".local" / "share" / "binderdash"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    override = os.environ.get("BINDERDASH_DESKTOP_CONFIG", "").strip()
    if override:
        return Path(override)
    return user_data_dir() / "desktop.json"


def resource_root() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS) / "backend"
    return repo_root() / "backend"


def static_root() -> Path:
    return resource_root() / "static"


def sqlite_database_url() -> str:
    db_path = (user_data_dir() / "binderdash.sqlite").resolve()
    return f"sqlite:///{db_path}"
