#!/usr/bin/env bash
# Assemble a PyInstaller onedir bundle into an AppImage.
#   usage: make_appimage.sh <dist_onedir> <out.AppImage>
# Requires `appimagetool` on PATH. Used by the CI build (native x86_64) and reusable locally.
set -euo pipefail

BUNDLE="${1:?usage: make_appimage.sh <dist_onedir> <out.AppImage>}"
OUT="${2:?usage: make_appimage.sh <dist_onedir> <out.AppImage>}"
[ -d "$BUNDLE" ] || { echo "error: onedir bundle '$BUNDLE' not found" >&2; exit 1; }

WORK="$(mktemp -d)"
APPDIR="$WORK/AppDir"
mkdir -p "$APPDIR/usr/bin"
cp -a "$BUNDLE/." "$APPDIR/usr/bin/"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/sift-agent" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/sift-agent.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Sift Agent
Exec=sift-agent
Icon=sift-agent
Categories=Utility;
Terminal=false
EOF

# Minimal 256x256 solid-accent PNG icon (pure stdlib — no ImageMagick/PIL needed).
python3 - "$APPDIR/sift-agent.png" <<'PY'
import sys, struct, zlib
w = h = 256
r, g, b = 0x7c, 0x5c, 0xff  # accent purple
row = b"\x00" + bytes([r, g, b]) * w
raw = row * h
def chunk(tag, data):
    c = tag + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
png = b"\x89PNG\r\n\x1a\n"
png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
png += chunk(b"IDAT", zlib.compress(raw, 9))
png += chunk(b"IEND", b"")
open(sys.argv[1], "wb").write(png)
PY
cp "$APPDIR/sift-agent.png" "$APPDIR/.DirIcon"

export ARCH="$(uname -m)"
rm -f "$OUT"
appimagetool --appimage-extract-and-run "$APPDIR" "$OUT"
chmod +x "$OUT"
rm -rf "$WORK"
echo "built $OUT"
