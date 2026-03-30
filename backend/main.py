import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .auth import CSRF_COOKIE_NAME
from .routers import auth as auth_routes
from .routers import designs as designs_routes
from .routers import files as files_routes
from .routers import plots as plots_routes
from .routers import runs as runs_routes
from .settings import CORS_ALLOWED_ORIGINS, settings


_root_level = getattr(logging, settings.log_level, logging.INFO)
logging.basicConfig(
    level=_root_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger().setLevel(_root_level)
logger = logging.getLogger(__name__)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return await call_next(request)
    if request.url.path in ["/api/auth/login", "/api/auth/logout", "/api/auth/status"]:
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


app.mount("/assets", StaticFiles(directory="backend/static/assets"), name="assets")
app.mount("/static", StaticFiles(directory="backend/static"), name="static")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/favicon.ico")
async def get_favicon():
    return FileResponse("backend/static/favicon.ico")


@app.get("/")
async def serve_frontend():
    return FileResponse("backend/static/index.html")


app.include_router(auth_routes.router)
app.include_router(runs_routes.router)
app.include_router(designs_routes.router)
app.include_router(files_routes.router)
app.include_router(files_routes.pdbs_router)
app.include_router(files_routes.tree_router)
app.include_router(plots_routes.router)
