import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import config_path

logger = logging.getLogger(__name__)


@dataclass
class WindowConfig:
    width: int = 1400
    height: int = 900
    x: int | None = None
    y: int | None = None


@dataclass
class DesktopConfig:
    run_base_dirs: list[str] = field(default_factory=list)
    window: WindowConfig = field(default_factory=WindowConfig)


def _window_from_dict(data: dict[str, Any] | None) -> WindowConfig:
    if not data:
        return WindowConfig()
    return WindowConfig(
        width=int(data.get("width", 1400)),
        height=int(data.get("height", 900)),
        x=data.get("x"),
        y=data.get("y"),
    )


def load_config(path: Path | None = None) -> DesktopConfig:
    cfg_path = path or config_path()
    if not cfg_path.is_file():
        return DesktopConfig()
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to load desktop config from %s: %s", cfg_path, e)
        return DesktopConfig()
    dirs = raw.get("run_base_dirs") or []
    if not isinstance(dirs, list):
        dirs = []
    run_base_dirs = [str(d).strip() for d in dirs if str(d).strip()]
    window = _window_from_dict(raw.get("window"))
    return DesktopConfig(run_base_dirs=run_base_dirs, window=window)


def save_config(config: DesktopConfig, path: Path | None = None) -> None:
    cfg_path = path or config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_base_dirs": config.run_base_dirs,
        "window": {
            "width": config.window.width,
            "height": config.window.height,
            "x": config.window.x,
            "y": config.window.y,
        },
    }
    cfg_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def update_run_base_dirs_in_file(dirs: list[str], path: Path | None = None) -> None:
    config = load_config(path)
    config.run_base_dirs = [d.strip() for d in dirs if d.strip()]
    save_config(config, path)
