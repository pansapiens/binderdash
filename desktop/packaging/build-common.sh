#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VERSION="$(grep -E '^version = ' backend/pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')"

if [[ ! -d backend/static ]]; then
  echo "Building frontend..."
  (cd frontend && pnpm install && pnpm run build)
fi

if [[ "$(uname -s)" == "Linux" ]]; then
  if ! /usr/bin/python3 -c "import gi" 2>/dev/null; then
    echo "ERROR: python3-gi is required to build the Linux desktop bundle."
    echo "Install: sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1"
    exit 1
  fi
fi

echo "Installing backend + desktop dependencies..."
uv pip install -r backend/requirements.txt
uv pip install -e backend 2>/dev/null || uv pip install -r backend/requirements.txt
uv pip install "pywebview[gtk]" pyinstaller

echo "Running PyInstaller..."
pyinstaller --noconfirm desktop/binderdash.spec

echo "Build complete (version ${VERSION}). Output under dist/"
