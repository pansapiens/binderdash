# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Binderdash desktop. Run from repository root."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
_spec_path = Path(SPECPATH).resolve()
desktop_dir = _spec_path.parent if _spec_path.suffix == ".spec" else _spec_path
repo_root = desktop_dir.parent
static_dir = repo_root / "backend" / "static"

if not static_dir.is_dir():
    raise SystemExit(
        f"Frontend bundle missing at {static_dir}. "
        "Run: cd frontend && pnpm run build"
    )

datas = [
    (str(static_dir), "backend/static"),
]

def _add_package_datas(import_name: str, subpath: str, dest: str) -> None:
    try:
        import importlib

        mod = importlib.import_module(import_name)
        src = Path(mod.__file__).resolve().parent / subpath
        if src.is_dir():
            datas.append((str(src), dest))
    except ImportError:
        pass


_add_package_datas("python_codon_tables", ".", "python_codon_tables")
_add_package_datas("dnachisel", "biotools/data", "dnachisel/biotools/data")

hiddenimports = [
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "multipart",
    "httptools",
    "websockets",
    "websockets.legacy",
    "websockets.legacy.server",
    "anyio",
    "anyio._backends",
    "anyio._backends._asyncio",
    "pandas",
    "dnachisel",
    "Bio",
    "Bio.PDB",
    "python_codon_tables",
    "desktop",
    "desktop.config",
    "desktop.paths",
    "desktop.env",
    "backend",
    "backend.main",
    "backend.routers.desktop",
    "backend.runtime_paths",
    "backend.persistence.sqlite_repo",
    "backend.util.codon_tables",
    "jose",
    "bcrypt",
    "starlette.middleware.sessions",
    "itsdangerous",
]

binaries: list = []
pathex = [str(repo_root)]
hooksconfig: dict = {}

if sys.platform == "linux":
    # pywebview on Linux needs PyGObject (gi). Ubuntu/Debian ship it for system Python
    # under dist-packages; include it in the frozen bundle.
    _dist_packages = Path("/usr/lib/python3/dist-packages")
    if _dist_packages.is_dir():
        sys.path.insert(0, str(_dist_packages))
        pathex.append(str(_dist_packages))

    for _pkg in ("gi", "cairo"):
        try:
            _d, _b, _h = collect_all(_pkg)
            datas += _d
            binaries += _b
            hiddenimports += _h
        except Exception:
            pass

    hiddenimports += collect_submodules("gi")
    hiddenimports += [
        "gi._gi",
        "gi.repository.Gtk",
        "gi.repository.Gdk",
        "gi.repository.GLib",
        "gi.repository.GObject",
        "gi.repository.Gio",
        "gi.repository.GModule",
        "gi.repository.WebKit2",
        "gi.repository.Soup",
        "webview.platforms.gtk",
    ]
    hooksconfig = {
        "gi": {
            "icons": ["Adwaita"],
            "themes": ["Adwaita"],
            "languages": ["en_US", "en_GB"],
            "module-versions": {"Gtk": "3.0"},
        },
    }

a = Analysis(
    [str(desktop_dir / "main.py")],
    pathex=pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(desktop_dir / "hooks")],
    hooksconfig=hooksconfig,
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon_arg = {}
assets = desktop_dir / "assets"
if sys.platform == "win32":
    ico = assets / "binderdash.ico"
    if ico.is_file():
        icon_arg["icon"] = str(ico)
elif sys.platform == "darwin":
    icns = assets / "binderdash.icns"
    if icns.is_file():
        icon_arg["icon"] = str(icns)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Binderdash",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=sys.platform == "linux",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    **icon_arg,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Binderdash",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Binderdash.app",
        icon=str(assets / "binderdash.icns") if (assets / "binderdash.icns").is_file() else None,
        bundle_identifier="edu.unimelb.knottlab.binderdash",
    )
