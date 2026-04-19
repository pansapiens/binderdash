import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .auth import CSRF_COOKIE_NAME
from .routers import auth as auth_routes
from .routers import designs as designs_routes
from .routers import files as files_routes
from .routers import plots as plots_routes
from .routers import runs as runs_routes
from .routers import sequences as sequences_routes
from .persistence.factory import default_sqlite_url, init_designs_repository_from_url
from .settings import CORS_ALLOWED_ORIGINS, SECRET_KEY, raw_settings, settings


_root_level = getattr(logging, settings.log_level, logging.INFO)
logging.basicConfig(
    level=_root_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger().setLevel(_root_level)
logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent
_STATIC_ROOT = _BACKEND_ROOT / "static"
_STATIC_ASSETS = _STATIC_ROOT / "assets"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url = (raw_settings.database or "").strip() or default_sqlite_url()
    init_designs_repository_from_url(db_url)
    from .cache import hydrate_caches_from_repository

    hydrate_caches_from_repository()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=False,
)


@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return await call_next(request)
    if request.url.path in [
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/status",
        "/api/auth/google/login",
        "/api/auth/google/callback",
    ]:
        return await call_next(request)
    if settings.auth_disabled:
        return await call_next(request)
    csrf_token = request.headers.get("X-CSRF-Token")
    if not csrf_token:
        return Response(
            content="CSRF token missing",
            status_code=403,
            headers={"Content-Type": "text/plain"},
        )
    cookie_csrf_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_csrf_token or csrf_token != cookie_csrf_token:
        return Response(
            content="CSRF token mismatch",
            status_code=403,
            headers={"Content-Type": "text/plain"},
        )
    return await call_next(request)


if _STATIC_ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_STATIC_ASSETS)), name="assets")
else:
    logger.warning(
        "Static assets directory missing at %s — run `pnpm run build` in frontend/ "
        "(or build the image with BUILD_FRONTEND=true).",
        _STATIC_ASSETS,
    )

if _STATIC_ROOT.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_ROOT)), name="static")
else:
    logger.warning(
        "Static directory missing at %s — run `pnpm run build` in frontend/.",
        _STATIC_ROOT,
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/favicon.ico")
async def get_favicon():
    path = _STATIC_ROOT / "favicon.ico"
    if not path.is_file():
        return Response(status_code=404)
    return FileResponse(str(path))


@app.get("/")
async def serve_frontend():
    path = _STATIC_ROOT / "index.html"
    if not path.is_file():
        return Response(
            content=(
                "Frontend bundle not found. Build the SPA (e.g. `cd frontend && pnpm run build`) "
                f"so files exist under {_STATIC_ROOT}."
            ),
            media_type="text/plain",
            status_code=503,
        )
    return FileResponse(str(path))


app.include_router(auth_routes.router)
app.include_router(runs_routes.router)
app.include_router(designs_routes.router)
app.include_router(files_routes.router)
app.include_router(files_routes.pdbs_router)
app.include_router(files_routes.tree_router)
app.include_router(plots_routes.router)
app.include_router(sequences_routes.router)
