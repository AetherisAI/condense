#!/usr/bin/env bash
# Runs INSIDE the Ubuntu build container (see Dockerfile.linux).
# Reads the repo from /src (ro), writes sift-agent-ubuntu.AppImage to /out.
set -euo pipefail

SRC=/src
OUT=/out
WORK=/build
VENV=/venv
export ARCH="$(uname -m)"   # appimagetool names the runtime by this; match the actual build arch

mkdir -p "$WORK" "$OUT"

echo "==> sanity: Tkinter in the build interpreter"
"$VENV/bin/python" -c "import tkinter; print('tk', tkinter.TkVersion)"

echo "==> PyInstaller onedir build"
"$VENV/bin/python" -m PyInstaller "$SRC/packaging/sift-agent.spec" --noconfirm \
  --distpath "$WORK/dist" --workpath "$WORK/pyi"

BUNDLE="$WORK/dist/sift-agent"
[ -d "$BUNDLE" ] || { echo "error: onedir bundle $BUNDLE missing" >&2; exit 1; }

echo "==> assembling AppDir"
APPDIR="$WORK/AppDir"
rm -rf "$APPDIR"
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

# Minimal 256x256 solid-accent PNG icon (pure stdlib — no ImageMagick/PIL in the image).
"$VENV/bin/python" - "$APPDIR/sift-agent.png" <<'PY'
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

echo "==> appimagetool → $OUT/sift-agent-ubuntu.AppImage"
rm -f "$OUT/sift-agent-ubuntu.AppImage"
appimagetool --appimage-extract-and-run "$APPDIR" "$OUT/sift-agent-ubuntu.AppImage"
chmod +x "$OUT/sift-agent-ubuntu.AppImage"
ls -lh "$OUT/sift-agent-ubuntu.AppImage"
echo "==> done"
