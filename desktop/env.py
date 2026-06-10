import os

from .config import DesktopConfig, load_config
from .paths import repo_root, sqlite_database_url, static_root


def apply_desktop_env(port: int, config: DesktopConfig | None = None) -> DesktopConfig:
    """Set process env for desktop mode before importing backend.settings."""
    cfg = config or load_config()

    os.environ["BINDERDASH_DESKTOP"] = "true"
    os.environ["DISABLE_AUTHENTICATION"] = "true"
    os.environ.setdefault("LOG_LEVEL", "INFO")

    db_url = sqlite_database_url()
    os.environ.setdefault("DATABASE", db_url)

    os.environ["RUN_BASE_DIRS"] = (
        ",".join(cfg.run_base_dirs) if cfg.run_base_dirs else ""
    )

    os.environ["CORS_ALLOWED_ORIGINS"] = f"http://127.0.0.1:{port}"
    os.environ["BINDERDASH_STATIC_ROOT"] = str(static_root())

    return cfg
