#!/bin/sh
# Condense one-click installer -- Linux + macOS, POSIX sh, no sudo anywhere.
#
#   curl -fsSL https://raw.githubusercontent.com/AetherisAI/condense/main/scripts/install.sh | sh
#
# Detects the OS, then installs either:
#   - (default)     the desktop app        -- AppImage/.deb on Linux, .dmg on macOS
#   - --server-only  the headless server bundle (engine + agent CLI, no UI, no Docker)
#
# Resolution order for the artifact:
#   1. --file <path>   use this local artifact directly (e.g. something built by hand, or
#                      downloaded from a CI run -- see the "no release yet" message below).
#   2. the newest GitHub Release asset for AetherisAI/condense, via the public,
#      unauthenticated Releases API (plain curl -- no `gh` CLI or token required).
#   3. neither found -> print a clear, friendly message pointing at CI artifacts and the repo,
#      and exit non-zero. This script never half-installs: if it can't find or fetch a real
#      artifact, it does nothing to your machine.
#
# Install layout:
#   Linux:   ~/Applications/Condense.AppImage                       (AppImage path)
#            ~/.local/opt/condense/                                 (.deb path -- dpkg -x, no root)
#            ~/.local/share/applications/condense.desktop
#            ~/.local/share/icons/hicolor/256x256/apps/condense.png  (best-effort)
#   macOS:   ~/Applications/Condense.app                             *** UNTESTED -- see below ***
#   --server-only (either OS): ~/.local/opt/condense-server/
#
# macOS support is UNTESTED: there is no macOS hardware in the environment that wrote this
# script. The mount/copy/detach sequence is written against the documented .dmg shape the
# project's release automation produces, but has never been run on real hardware. It prints a
# runtime warning before touching anything. Please report back anything that doesn't match
# reality (volume name, .app name, etc.).
#
# Usage:
#   install.sh                       install the desktop app (AppImage on Linux, .dmg on macOS)
#   install.sh --server-only         install the headless server bundle only (no UI)
#   install.sh --file <path>         use a local artifact instead of downloading one
#   install.sh --uninstall           remove a previous install (add --server-only to remove that)
#   install.sh -h | --help           show this help
#
# Windows is not supported by this script -- use scripts/install-windows.ps1 instead.
set -eu

REPO_SLUG="AetherisAI/condense"
APP_DIR="$HOME/Applications"
APPIMAGE_DEST="$APP_DIR/Condense.AppImage"
DEB_INSTALL_DIR="$HOME/.local/opt/condense"
APPS_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APPS_DIR/condense.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON_DEST="$ICON_DIR/condense.png"
MACOS_APP_DEST="$HOME/Applications/Condense.app"
SERVER_DIR="$HOME/.local/opt/condense-server"

usage() {
  sed -n '2,32p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//' || cat <<'EOF'
Condense installer -- see scripts/install.sh for the full header.
Usage: install.sh [--file <path>] [--server-only] [--uninstall] [-h|--help]
EOF
}

FILE_ARG=""
UNINSTALL=0
SERVER_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --file)
      [ $# -ge 2 ] || { echo "error: --file needs a path" >&2; exit 1; }
      FILE_ARG="$2"
      shift 2
      ;;
    --file=*)
      FILE_ARG="${1#--file=}"
      shift
      ;;
    --server-only)
      SERVER_ONLY=1
      shift
      ;;
    --uninstall)
      UNINSTALL=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

OS_NAME="$(uname -s)"
case "$OS_NAME" in
  Linux) PLATFORM="linux" ;;
  Darwin) PLATFORM="macos" ;;
  *)
    echo "error: unsupported OS '$OS_NAME' -- Condense's installer supports Linux and macOS." >&2
    echo "       For Windows, use scripts\\install-windows.ps1 instead." >&2
    exit 1
    ;;
esac

# --- uninstall --------------------------------------------------------------------------------
if [ "$UNINSTALL" = "1" ]; then
  echo "==> Condense uninstaller"
  removed=0

  if [ "$SERVER_ONLY" = "1" ]; then
    if [ -d "$SERVER_DIR" ]; then
      rm -rf "$SERVER_DIR"
      echo "    removed $SERVER_DIR"
      removed=1
    fi
  else
    for p in "$APPIMAGE_DEST" "$DESKTOP_FILE" "$ICON_DEST" "$MACOS_APP_DEST"; do
      if [ -e "$p" ]; then
        rm -rf "$p"
        echo "    removed $p"
        removed=1
      fi
    done
    if [ -d "$DEB_INSTALL_DIR" ]; then
      rm -rf "$DEB_INSTALL_DIR"
      echo "    removed $DEB_INSTALL_DIR"
      removed=1
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
      update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
    fi
  fi

  if [ "$removed" = "0" ]; then
    echo "    nothing installed."
  fi
  echo "done. (config/data under ~/.config/ai.aetheris.condense and"
  echo "      ~/.local/share/ai.aetheris.condense are left in place -- remove by hand if wanted.)"
  exit 0
fi

mkdir -p "$APP_DIR" "$APPS_DIR" "$ICON_DIR"

TMP_DOWNLOAD=""
TMP_EXTRACT=""
MOUNT_POINT=""
cleanup() {
  if [ -n "$MOUNT_POINT" ] && [ -d "$MOUNT_POINT" ] && command -v hdiutil >/dev/null 2>&1; then
    hdiutil detach "$MOUNT_POINT" -quiet 2>/dev/null || true
  fi
  [ -n "$TMP_DOWNLOAD" ] && [ -f "$TMP_DOWNLOAD" ] && rm -f "$TMP_DOWNLOAD"
  [ -n "$TMP_EXTRACT" ] && [ -d "$TMP_EXTRACT" ] && rm -rf "$TMP_EXTRACT"
}
trap cleanup EXIT INT TERM

# --- pick the asset pattern for this OS + mode ------------------------------------------------
if [ "$SERVER_ONLY" = "1" ]; then
  KIND="server bundle"
  case "$PLATFORM" in
    linux) ASSET_REGEX='condense-server-.*linux.*\.tar\.gz$' ;;
    macos) ASSET_REGEX='condense-server-.*apple-darwin.*\.tar\.gz$' ;;
  esac
else
  # Matched against the full asset URL, strictly requiring the "Condense_*" desktop-app naming
  # convention as the filename (last path segment) -- not just any .AppImage/.deb/.dmg anywhere
  # in the release -- so this never mistakes an unrelated or legacy asset (e.g. the old v0.3.0
  # sift-agent-*.AppImage bundles) for the actual desktop app.
  KIND="desktop app"
  case "$PLATFORM" in
    linux) ASSET_REGEX='/Condense[_-][^/]*\.(AppImage|deb)$' ;;
    macos) ASSET_REGEX='/Condense[_-][^/]*\.dmg$' ;;
  esac
fi

# --- resolve the artifact: --file, then the latest GitHub Release ----------------------------
ASSET_URL=""
ORIGINAL_NAME=""

if [ -n "$FILE_ARG" ]; then
  [ -f "$FILE_ARG" ] || { echo "error: --file $FILE_ARG not found" >&2; exit 1; }
  SRC_ARTIFACT="$(cd "$(dirname "$FILE_ARG")" && pwd)/$(basename "$FILE_ARG")"
  ORIGINAL_NAME="$(basename "$FILE_ARG")"
  echo "==> using local artifact: $SRC_ARTIFACT"
else
  echo "==> looking for the newest GitHub Release $KIND asset ($REPO_SLUG)"
  TMP_JSON="$(mktemp)"
  HTTP_STATUS="$(curl -sS -o "$TMP_JSON" -w '%{http_code}' \
    "https://api.github.com/repos/$REPO_SLUG/releases/latest" 2>/dev/null || echo "000")"
  if [ "$HTTP_STATUS" = "200" ]; then
    ASSET_URL="$(grep -o '"browser_download_url": *"[^"]*"' "$TMP_JSON" \
      | sed -E 's/.*"(https:[^"]+)"/\1/' \
      | grep -E "$ASSET_REGEX" | head -1 || true)"
  fi
  rm -f "$TMP_JSON"

  if [ -z "$ASSET_URL" ]; then
    cat >&2 <<EOF

No published $KIND release found yet for $REPO_SLUG.

Condense's install artifacts (Condense_*.AppImage/.deb/.dmg/.exe and condense-server-*.tar.gz/.zip)
ship starting with the v0.4.0 release. Until the first tagged release lands, you have two options:

  1. Grab a build from CI:
       https://github.com/$REPO_SLUG/actions

  2. Build it yourself (see packaging/README.md and desktop/README.md in the repo):
       https://github.com/$REPO_SLUG

Then install the local file directly:
  ./install.sh --file <path-to-artifact>$( [ "$SERVER_ONLY" = "1" ] && printf -- ' --server-only' || true )

Nothing was installed.
EOF
    exit 1
  fi

  ORIGINAL_NAME="$(basename "$ASSET_URL")"
  echo "    downloading $ORIGINAL_NAME"
  TMP_DOWNLOAD="$(mktemp)"
  curl -fsSL "$ASSET_URL" -o "$TMP_DOWNLOAD"
  SRC_ARTIFACT="$TMP_DOWNLOAD"
fi

# --- server-only: unpack the tarball and stop ------------------------------------------------
if [ "$SERVER_ONLY" = "1" ]; then
  echo "==> installing server bundle to $SERVER_DIR"
  rm -rf "$SERVER_DIR"
  mkdir -p "$SERVER_DIR"
  tar -xzf "$SRC_ARTIFACT" -C "$SERVER_DIR" --strip-components=1
  echo
  echo "done. condense-server installed to $SERVER_DIR"
  if [ -f "$SERVER_DIR/run.sh" ]; then
    chmod +x "$SERVER_DIR/run.sh" 2>/dev/null || true
    echo "Run it with:"
    echo "  $SERVER_DIR/run.sh"
  else
    echo "See $SERVER_DIR/README.md to run the engine directly."
  fi
  exit 0
fi

# --- Linux: AppImage or .deb, plus a launcher + icon ------------------------------------------
if [ "$PLATFORM" = "linux" ]; then
  IS_DEB=0
  case "$ORIGINAL_NAME" in *.deb) IS_DEB=1 ;; esac

  ICON_FOUND=""
  if [ "$IS_DEB" = "1" ]; then
    echo "==> extracting .deb into $DEB_INSTALL_DIR (dpkg -x, no root)"
    command -v dpkg >/dev/null 2>&1 || { echo "error: dpkg not found -- cannot extract a .deb without it" >&2; exit 1; }
    rm -rf "$DEB_INSTALL_DIR"
    mkdir -p "$DEB_INSTALL_DIR"
    dpkg -x "$SRC_ARTIFACT" "$DEB_INSTALL_DIR"
    EXEC_PATH="$(find "$DEB_INSTALL_DIR/usr/bin" -maxdepth 1 -type f 2>/dev/null | head -1 || true)"
    if [ -z "$EXEC_PATH" ]; then
      echo "error: no executable found under $DEB_INSTALL_DIR/usr/bin after extraction" >&2
      exit 1
    fi
    chmod +x "$EXEC_PATH"
    ICON_FOUND="$(find "$DEB_INSTALL_DIR/usr/share/icons" -type f -name '*.png' 2>/dev/null \
      | sed -E 's#.*/([0-9]+)x[0-9]+(@[0-9]+)?/apps/.*#\1 &#' \
      | sort -rn | head -1 | cut -d' ' -f2- || true)"
    echo "    binary: $EXEC_PATH"
  else
    echo "==> installing AppImage to $APPIMAGE_DEST"
    cp -f "$SRC_ARTIFACT" "$APPIMAGE_DEST"
    chmod +x "$APPIMAGE_DEST"
    EXEC_PATH="$APPIMAGE_DEST"

    echo "==> extracting icon from the AppImage"
    TMP_EXTRACT="$(mktemp -d)"
    if (cd "$TMP_EXTRACT" && "$APPIMAGE_DEST" --appimage-extract >/dev/null 2>&1); then
      ICON_FOUND="$(find "$TMP_EXTRACT/squashfs-root" -path '*icons*' -name '*.png' 2>/dev/null \
        | sed -E 's#.*/([0-9]+)x[0-9]+(@[0-9]+)?/apps/.*#\1 &#' \
        | sort -rn | head -1 | cut -d' ' -f2- || true)"
      if [ -z "$ICON_FOUND" ]; then
        ICON_FOUND="$(find "$TMP_EXTRACT/squashfs-root" -maxdepth 1 -name '*.png' 2>/dev/null | head -1 || true)"
      fi
    else
      echo "    WARNING: --appimage-extract failed (FUSE/exec issue?) -- continuing without an icon"
    fi
  fi

  # Fallback: the repo's own logo, if we happen to be running from inside a checkout.
  if [ -z "$ICON_FOUND" ]; then
    REPO_ROOT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd || true)"
    if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/docs/assets/logo-256.png" ]; then
      ICON_FOUND="$REPO_ROOT/docs/assets/logo-256.png"
    fi
  fi

  if [ -n "$ICON_FOUND" ]; then
    cp -f "$ICON_FOUND" "$ICON_DEST"
    echo "    icon: $ICON_DEST (from $ICON_FOUND)"
  else
    echo "    WARNING: no icon found -- .desktop entry will use a generic fallback icon name"
    ICON_DEST="condense"
  fi

  echo "==> writing $DESKTOP_FILE"
  cat > "$DESKTOP_FILE" <<DESKTOPEOF
[Desktop Entry]
Name=Condense
Comment=Local document search & chat
Exec=$EXEC_PATH
Icon=$ICON_DEST
Terminal=false
Type=Application
Categories=Utility;Office;
StartupWMClass=Condense
DESKTOPEOF

  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 \
      && echo "    update-desktop-database: OK" \
      || echo "    update-desktop-database: reported an issue (non-fatal)"
  fi
  if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$DESKTOP_FILE" \
      && echo "    desktop-file-validate: OK" \
      || echo "    desktop-file-validate: reported an issue (non-fatal)"
  fi

  echo
  echo "done. Launch \"Condense\" from your application grid, or directly:"
  echo "  $EXEC_PATH"
  exit 0
fi

# --- macOS: mount the .dmg, copy the .app, detach --- *** UNTESTED, see header *** ------------
if [ "$PLATFORM" = "macos" ]; then
  echo "==> WARNING: macOS support is UNTESTED on real hardware (see this script's header)."
  echo "    Proceeding, but please report anything that looks wrong."

  command -v hdiutil >/dev/null 2>&1 || { echo "error: hdiutil not found -- is this really macOS?" >&2; exit 1; }

  echo "==> mounting $SRC_ARTIFACT"
  ATTACH_OUTPUT="$(hdiutil attach "$SRC_ARTIFACT" -nobrowse -readonly -noautoopen 2>&1)"
  echo "$ATTACH_OUTPUT"
  MOUNT_POINT="$(printf '%s\n' "$ATTACH_OUTPUT" | awk -F'\t' '/\/Volumes\// {print $NF}' | tail -1)"
  if [ -z "$MOUNT_POINT" ] || [ ! -d "$MOUNT_POINT" ]; then
    echo "error: could not determine mount point from hdiutil output above" >&2
    exit 1
  fi

  SRC_APP="$(find "$MOUNT_POINT" -maxdepth 1 -name '*.app' | head -1 || true)"
  if [ -z "$SRC_APP" ]; then
    echo "error: no .app bundle found in $MOUNT_POINT" >&2
    exit 1
  fi

  echo "==> copying $(basename "$SRC_APP") -> $MACOS_APP_DEST"
  rm -rf "$MACOS_APP_DEST"
  cp -R "$SRC_APP" "$MACOS_APP_DEST"

  echo "==> detaching $MOUNT_POINT"
  hdiutil detach "$MOUNT_POINT" -quiet
  MOUNT_POINT=""

  echo
  echo "done. Launch \"Condense\" from Launchpad/Spotlight, or directly:"
  echo "  open \"$MACOS_APP_DEST\""
  echo
  echo "First launch: right-click -> Open (unsigned build, Gatekeeper will otherwise refuse it)."
  exit 0
fi
