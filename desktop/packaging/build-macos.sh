#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VERSION="$(grep -E '^version = ' backend/pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')"
ARCH="$(uname -m)"
ZIP_NAME="Binderdash-${VERSION}-macos-${ARCH}.zip"

bash desktop/packaging/build-common.sh

STAGING="$ROOT/dist/macos-staging"
rm -rf "$STAGING"
mkdir -p "$STAGING"

if [[ -d dist/Binderdash.app ]]; then
  cp -R dist/Binderdash.app "$STAGING/"
else
  echo "Expected dist/Binderdash.app after PyInstaller build on macOS"
  exit 1
fi

cat > "$STAGING/README.txt" <<'EOF'
Binderdash (macOS)

1. Unzip this archive.
2. Double-click Binderdash.app.

If macOS blocks the app (unsigned build):
   Right-click Binderdash.app → Open, or run:
   xattr -cr Binderdash.app
EOF

(
  cd "$STAGING"
  zip -r "../${ZIP_NAME}" Binderdash.app README.txt
)

echo "Created $ROOT/dist/${ZIP_NAME}"
