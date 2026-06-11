#!/usr/bin/env python3
"""Binderdash desktop entry: embedded uvicorn + pywebview window."""

from __future__ import annotations

import logging
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# Ensure repo root is on sys.path before local imports when run as script.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from desktop.config import DesktopConfig, load_config, save_config
from desktop.env import apply_desktop_env
from desktop.paths import is_frozen, repo_root, user_data_dir

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8765
HEALTH_TIMEOUT_S = 10.0
HEALTH_POLL_INTERVAL_S = 0.2


def _pick_port(preferred: int = DEFAULT_PORT) -> int:
    for port in (preferred, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
                return sock.getsockname()[1]
        except OSError:
            continue
    raise RuntimeError("Could not bind a localhost port for Binderdash")


def _wait_for_health(port: int, timeout: float = HEALTH_TIMEOUT_S) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(HEALTH_POLL_INTERVAL_S)
    return False


def _start_uvicorn(port: int) -> threading.Thread:
    import uvicorn

    config = uvicorn.Config(
        "backend.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)

    def run() -> None:
        server.run()

    thread = threading.Thread(target=run, name="binderdash-uvicorn", daemon=True)
    thread.start()
    return thread


def _show_startup_error(message: str) -> None:
    try:
        import webview

        webview.create_window("Binderdash — startup error", html=f"<pre>{message}</pre>")
        webview.start()
    except Exception:
        print(message, file=sys.stderr)


class DesktopApi:
    """JS bridge exposed to the SPA via pywebview."""

    def select_run_base_dir(self) -> str | None:
        import webview

        if not webview.windows:
            return None
        result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return None
        if isinstance(result, (list, tuple)):
            return str(result[0]) if result else None
        return str(result)


def _persist_window_geometry(config: DesktopConfig) -> None:
    try:
        import webview

        if not webview.windows:
            return
        win = webview.windows[0]
        config.window.width = int(win.width or config.window.width)
        config.window.height = int(win.height or config.window.height)
        save_config(config)
    except Exception as e:
        logger.debug("Could not persist window geometry: %s", e)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    port = _pick_port()
    config = apply_desktop_env(port)

    log_file = user_data_dir() / "binderdash.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logging.getLogger().addHandler(file_handler)

    logger.info(
        "Starting Binderdash desktop (frozen=%s, port=%s, data_dir=%s)",
        is_frozen(),
        port,
        user_data_dir(),
    )

    _start_uvicorn(port)

    if not _wait_for_health(port):
        msg = (
            f"Binderdash backend did not start within {HEALTH_TIMEOUT_S}s on "
            f"http://127.0.0.1:{port}/health\n"
            f"See log: {log_file}"
        )
        logger.error(msg)
        _show_startup_error(msg)
        return 1

    import webview

    url = f"http://127.0.0.1:{port}/"
    window = webview.create_window(
        "Binderdash",
        url,
        width=config.window.width,
        height=config.window.height,
        min_size=(900, 600),
        js_api=DesktopApi(),
    )

    def on_closed() -> None:
        _persist_window_geometry(config)

    window.events.closed += on_closed
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
