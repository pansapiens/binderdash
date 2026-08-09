import logging
from pathlib import Path
from typing import Any, Optional

from .noop_repo import NoopDesignsRepository
from .sqlite_repo import SqliteDesignsRepository

logger = logging.getLogger(__name__)

_repo: Optional[Any] = None


def default_sqlite_url() -> str:
    base = Path(__file__).resolve().parent.parent
    data_dir = base / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = (data_dir / "binderdash.sqlite").resolve()
    return f"sqlite:///{path}"


def _normalize_database_url(raw: str) -> str:
    s = raw.strip()
    if s.startswith("file:"):
        from urllib.parse import urlparse, unquote

        p = urlparse(s)
        path = unquote(p.path or "")
        if path.startswith("//"):
            path = path[1:]
        return f"sqlite:///{path}"
    return s


def create_repository(database_url: Optional[str]) -> Any:
    raw_in = (database_url or "").strip()
    if not raw_in:
        logger.info("DATABASE unset; persistence disabled (noop repository)")
        return NoopDesignsRepository()
    raw = _normalize_database_url(raw_in)
    scheme = raw.split(":", 1)[0].lower()
    if scheme == "sqlite":
        repo = SqliteDesignsRepository(raw)
        repo.init_schema()
        return repo
    # A *misconfigured* DATABASE must not degrade quietly. Falling back to the
    # noop repository here would silently discard designs, login history, and
    # every API key while the app looked healthy. Leaving DATABASE unset is the
    # supported way to run without persistence; a URL we cannot honour is a
    # configuration error and should stop the process.
    if scheme in ("postgresql", "postgres"):
        raise RuntimeError(
            f"DATABASE URL uses {scheme!r}, but the Postgres repository is not "
            "implemented. Use a sqlite:/// URL, or unset DATABASE to run "
            "without persistence (this disables API keys)."
        )
    raise RuntimeError(
        f"Unknown DATABASE scheme {scheme!r}. Use a sqlite:/// URL, or unset "
        "DATABASE to run without persistence (this disables API keys)."
    )


def get_designs_repository() -> Any:
    global _repo
    if _repo is None:
        raise RuntimeError("Designs repository not initialised; call set_designs_repository first")
    return _repo


def set_designs_repository(repo: Any) -> None:
    global _repo
    _repo = repo


def init_designs_repository_from_url(database_url: Optional[str]) -> Any:
    repo = create_repository(database_url)
    set_designs_repository(repo)
    return repo
