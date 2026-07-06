#!/usr/bin/env bash
# Build the standalone "server bundle" (D62/D63): both PyInstaller targets this needs --
# `packaging/sift-engine.spec` (the frozen FastAPI engine, onedir) and
# `packaging/sift-agent-cli.spec` (the headless ingestion CLI, onefile, already exists since
# v0.3.0) -- then assembles `dist/condense-server-<target-triple>/` from the frozen builds plus
# the source files under `packaging/server-bundle/` (README/run.sh/run.bat/env.example), and tars
# the result. This is the SAME artifact the desktop launcher downloads in local mode and Arthur's
# landing page offers as the "API only" install (D63) -- one build, two consumption paths.
#
# This script does its own RAM accounting deliberately lightly (no systemd-run baked in) so it
# stays portable to CI runners that don't have a systemd --user session bus (GitHub Actions
# ubuntu-latest does not, by default); when running it BY HAND on a memory-constrained dev box,
# wrap the whole invocation the same way every other pyinstaller/pytest run in this repo is
# wrapped (DECISIONS.md D29/D34):
#   systemd-run --user --pipe --wait -p MemoryMax=3G -p MemorySwapMax=0 -p OOMScoreAdjust=1000 \
#     --working-directory="$PWD" --collect scripts/build-server-bundle.sh
#
# Usage:
#   scripts/build-server-bundle.sh
#   TARGET_TRIPLE=x86_64-unknown-linux-gnu scripts/build-server-bundle.sh   # skip rustc detection
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# The triple names the archive/directory the same way Tauri's `bundle.externalBin` naming
# convention does (packaging/README.md) -- `rustc --print host-tuple` is the simplest way to get
# the exact triple for the machine currently building. Hardcoded fallback below is a TODO: this
# repo's build hosts are Linux x86_64 today; a real cross-OS release needs each OS's own CI leg
# (native, not cross-compiled -- PyInstaller can't cross-compile) to report its own triple.
if [[ -n "${TARGET_TRIPLE:-}" ]]; then
  TRIPLE="$TARGET_TRIPLE"
elif command -v rustc >/dev/null 2>&1; then
  TRIPLE="$(rustc --print host-tuple)"
else
  # TODO: no rustc on this build host to ask -- x86_64-unknown-linux-gnu is this repo's only
  # verified build target tonight (D64); a macOS/Windows/arm64 build MUST override via
  # TARGET_TRIPLE rather than trust this fallback.
  TRIPLE="x86_64-unknown-linux-gnu"
fi

BUNDLE_NAME="condense-server-$TRIPLE"
BUNDLE_DIR="$REPO/dist/$BUNDLE_NAME"
TARBALL="$REPO/dist/$BUNDLE_NAME.tar.gz"

echo "==> building server bundle for $TRIPLE"

echo "==> [1/4] pyinstaller: engine (onedir, packaging/sift-engine.spec)"
.venv/bin/pyinstaller --noconfirm --clean packaging/sift-engine.spec

echo "==> [2/4] pyinstaller: sift-agent-cli (onefile, packaging/sift-agent-cli.spec)"
.venv/bin/pyinstaller --noconfirm --clean packaging/sift-agent-cli.spec

echo "==> [3/4] assembling $BUNDLE_DIR"
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR/engine" "$BUNDLE_DIR/bin"

# The onedir engine build IS the directory contents (executable + _internal/), not a single file.
cp -a dist/sift-engine/. "$BUNDLE_DIR/engine/"
# The onefile agent-cli build is a single executable.
cp dist/sift-agent-cli "$BUNDLE_DIR/bin/sift-agent-cli"
chmod +x "$BUNDLE_DIR/bin/sift-agent-cli" "$BUNDLE_DIR/engine/sift-engine"

cp packaging/server-bundle/README.md "$BUNDLE_DIR/README.md"
cp packaging/server-bundle/run.sh "$BUNDLE_DIR/run.sh"
cp packaging/server-bundle/run.bat "$BUNDLE_DIR/run.bat"
cp packaging/server-bundle/env.example "$BUNDLE_DIR/env.example"
chmod +x "$BUNDLE_DIR/run.sh"

echo "==> [4/4] tarring -> $TARBALL"
tar czf "$TARBALL" -C "$REPO/dist" "$BUNDLE_NAME"

echo
echo "done."
echo "  bundle: $BUNDLE_DIR ($(du -sh "$BUNDLE_DIR" | cut -f1))"
echo "  tarball: $TARBALL ($(du -sh "$TARBALL" | cut -f1))"
