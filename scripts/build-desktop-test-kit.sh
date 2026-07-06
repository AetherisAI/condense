#!/usr/bin/env bash
# Assemble ~/condense-desktop-testkit/ — a self-contained folder the owner can copy (or tar up)
# to another Linux machine and stand up the desktop app there with ONE script (setup-test.sh),
# without that machine needing access to this PRIVATE repo. The engine bundle ships INSIDE the
# kit and is wired up via a file:// manifest entry rendered at install time; the embedder
# (llama-server, public GitHub release) and model (bge-m3 GGUF, public HuggingFace) keep their
# real public URLs, unchanged from desktop/provisioning/manifest.json, so the app exercises a
# real network download for those two.
#
# Usage: scripts/build-desktop-test-kit.sh
#
# Env overrides:
#   TAURI_WORKTREE   worktree containing the built AppImage + icon (default: this repo)
#   ENGINE_WORKTREE  worktree containing dist/<engine tarball>, rebuilt via its own
#                    scripts/build-server-bundle.sh (RAM-capped) if missing
#                    (default: ~/.cache/condense-wt-engine)
#   KIT_DIR          output directory (default: ~/condense-desktop-testkit)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_WORKTREE="${TAURI_WORKTREE:-$REPO}"
ENGINE_WORKTREE="${ENGINE_WORKTREE:-$HOME/.cache/condense-wt-engine}"
KIT_DIR="${KIT_DIR:-$HOME/condense-desktop-testkit}"
TEMPLATE_DIR="$REPO/scripts/test-kit"

APPIMAGE_NAME="Condense_0.4.0_amd64.AppImage"
APPIMAGE_SRC="$TAURI_WORKTREE/desktop/src-tauri/target/release/bundle/appimage/$APPIMAGE_NAME"
ENGINE_TARBALL_NAME="condense-server-x86_64-unknown-linux-gnu.tar.gz"
ENGINE_TARBALL_SRC="$ENGINE_WORKTREE/dist/$ENGINE_TARBALL_NAME"
ICON_SRC="$TAURI_WORKTREE/desktop/src-tauri/icons/128x128.png"

echo "==> [1/6] verifying AppImage"
if [[ ! -f "$APPIMAGE_SRC" ]]; then
  echo "ERROR: AppImage not found at $APPIMAGE_SRC" >&2
  echo "       Build it first -- see desktop/README.md's Docker build section." >&2
  exit 1
fi
INSTALLED_APPIMAGE="$HOME/.local/bin/Condense.AppImage"
BUILT_APPIMAGE_SHA="$(sha256sum "$APPIMAGE_SRC" | cut -d' ' -f1)"
if [[ -f "$INSTALLED_APPIMAGE" ]]; then
  INSTALLED_SHA="$(sha256sum "$INSTALLED_APPIMAGE" | cut -d' ' -f1)"
  if [[ "$BUILT_APPIMAGE_SHA" != "$INSTALLED_SHA" ]]; then
    echo "    WARNING: built AppImage ($BUILT_APPIMAGE_SHA) != installed ~/.local/bin/Condense.AppImage ($INSTALLED_SHA)" >&2
    echo "             the installed copy on this host is stale relative to the just-built bundle." >&2
  else
    echo "    OK -- matches installed ~/.local/bin/Condense.AppImage ($BUILT_APPIMAGE_SHA)"
  fi
else
  echo "    NOTE: no installed ~/.local/bin/Condense.AppImage on this host to compare against."
fi

echo "==> [2/6] verifying engine tarball"
if [[ ! -f "$ENGINE_TARBALL_SRC" ]]; then
  echo "    missing -- rebuilding via $ENGINE_WORKTREE/scripts/build-server-bundle.sh (RAM-capped)"
  systemd-run --user --pipe --wait -p MemoryMax=3G -p MemorySwapMax=0 -p OOMScoreAdjust=1000 \
    --working-directory="$ENGINE_WORKTREE" --collect \
    "$ENGINE_WORKTREE/scripts/build-server-bundle.sh"
  if [[ ! -f "$ENGINE_TARBALL_SRC" ]]; then
    echo "ERROR: engine tarball still missing after rebuild attempt: $ENGINE_TARBALL_SRC" >&2
    exit 1
  fi
fi
ENGINE_SHA256="$(sha256sum "$ENGINE_TARBALL_SRC" | cut -d' ' -f1)"
ENGINE_SIZE="$(stat -c '%s' "$ENGINE_TARBALL_SRC")"
echo "    OK -- $ENGINE_TARBALL_SRC ($ENGINE_SIZE bytes, sha256 $ENGINE_SHA256)"

echo "==> [3/6] verifying icon"
if [[ ! -f "$ICON_SRC" ]]; then
  echo "ERROR: icon not found at $ICON_SRC" >&2
  exit 1
fi
echo "    OK -- $ICON_SRC"

echo "==> [4/6] assembling $KIT_DIR"
mkdir -p "$KIT_DIR"
cp -f "$APPIMAGE_SRC" "$KIT_DIR/Condense.AppImage"
chmod +x "$KIT_DIR/Condense.AppImage"
cp -f "$ENGINE_TARBALL_SRC" "$KIT_DIR/$ENGINE_TARBALL_NAME"
cp -f "$ICON_SRC" "$KIT_DIR/condense.png"

echo "==> [5/6] rendering manifest.template.json (engine sha256/size baked in; __KIT_DIR__ left for setup-test.sh)"
sed \
  -e "s#__ENGINE_SHA256__#$ENGINE_SHA256#g" \
  -e "s#__ENGINE_SIZE__#$ENGINE_SIZE#g" \
  "$TEMPLATE_DIR/manifest.template.json" > "$KIT_DIR/manifest.template.json"

echo "==> [6/6] copying setup-test.sh / uninstall-test.sh / README.txt"
cp -f "$TEMPLATE_DIR/setup-test.sh" "$KIT_DIR/setup-test.sh"
cp -f "$TEMPLATE_DIR/uninstall-test.sh" "$KIT_DIR/uninstall-test.sh"
cp -f "$TEMPLATE_DIR/README.txt" "$KIT_DIR/README.txt"
chmod +x "$KIT_DIR/setup-test.sh" "$KIT_DIR/uninstall-test.sh"

echo
echo "done. Kit contents:"
ls -la "$KIT_DIR"
echo
echo "Next:"
echo "  tar -czf ~/condense-desktop-testkit.tar.gz -C \"$HOME\" \"$(basename "$KIT_DIR")\""
