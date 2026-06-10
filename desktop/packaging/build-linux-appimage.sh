#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VERSION="$(grep -E '^version = ' backend/pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')"
ARCH="$(uname -m)"
APPIMAGE_NAME="Binderdash-${VERSION}-${ARCH}.AppImage"

bash desktop/packaging/build-common.sh

DIST_DIR="$ROOT/dist/Binderdash"
APPDIR="$ROOT/dist/Binderdash.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

cp -a "$DIST_DIR/." "$APPDIR/usr/bin/"

ICON_SRC="$ROOT/desktop/assets/binderdash.png"
APPDIR_ICON="$APPDIR/binderdash.png"
if [[ -f "$ICON_SRC" ]]; then
  cp "$ICON_SRC" "$APPDIR_ICON"
elif [[ ! -f "$APPDIR_ICON" ]]; then
  python3 - <<'PY'
import struct, zlib
from pathlib import Path

def png(w, h, rgb):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(rgb[i : i + w * 3]) for i in range(0, w * h * 3, w * 3))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )

w = h = 256
px = []
for y in range(h):
    for x in range(w):
        px.extend([102, 51, 153] if 48 <= x <= 208 and 48 <= y <= 208 else [118, 75, 162])
Path("dist/Binderdash.AppDir/binderdash.png").write_bytes(png(w, h, bytes(px)))
PY
fi

cat > "$APPDIR/binderdash.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Binderdash
Comment=De novo protein binder design results viewer
Exec=Binderdash
Icon=binderdash
Categories=Science;
Terminal=false
EOF

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="$HERE/usr/bin:${LD_LIBRARY_PATH:-}"
exec "$HERE/usr/bin/Binderdash" "$@"
EOF
chmod +x "$APPDIR/AppRun"

APPIMAGETOOL="${APPIMAGETOOL:-appimagetool}"
if ! command -v "$APPIMAGETOOL" >/dev/null 2>&1; then
  APPIMAGETOOL="/tmp/appimagetool"
  if [[ ! -x "$APPIMAGETOOL" ]]; then
    wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage -O "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
  fi
fi

ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$ROOT/dist/$APPIMAGE_NAME"
echo "Created $ROOT/dist/$APPIMAGE_NAME"
