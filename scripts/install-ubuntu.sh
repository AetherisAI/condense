#!/usr/bin/env bash
# Install (or uninstall) the Condense desktop app on Ubuntu/Linux -- idempotent, no sudo required.
#
# The Tauri shell ships as an AppImage (preferred -- no privileged unpack) or a .deb (extracted
# with `dpkg -x`, never `dpkg -i`, so no root is ever needed). Either way this script only ever
# touches paths under $HOME.
#
# Resolution order for the artifact:
#   1. --file <path>   use this local .AppImage or .deb directly (e.g. a Docker-built bundle, or
#                       a `gh run download` from .github/workflows/build-desktop.yml).
#   2. the newest GitHub Release asset for AetherisAI/condense (`gh release download` if `gh` is
#      on PATH and authenticated, else a plain `curl` against the public releases API).
#   3. neither found -> print a clear message pointing at CI artifacts and exit non-zero. This
#      script never half-installs: if it can't find or fetch a real artifact, it does nothing.
#
# Install layout:
#   ~/Applications/Condense.AppImage                                (AppImage path)
#   ~/.local/opt/condense/                                          (.deb path -- dpkg -x target)
#   ~/.local/share/applications/condense.desktop
#   ~/.local/share/icons/hicolor/256x256/apps/condense.png          (best-effort)
#
# Usage:
#   scripts/install-ubuntu.sh                        # install from the latest GitHub Release
#   scripts/install-ubuntu.sh --file ./Condense.AppImage
#   scripts/install-ubuntu.sh --file ./Condense_0.4.0_amd64.deb
#   scripts/install-ubuntu.sh --uninstall
set -euo pipefail

REPO_SLUG="AetherisAI/condense"
APP_DIR="$HOME/Applications"
APPIMAGE_DEST="$APP_DIR/Condense.AppImage"
DEB_INSTALL_DIR="$HOME/.local/opt/condense"
APPS_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APPS_DIR/condense.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON_DEST="$ICON_DIR/condense.png"

usage() {
  sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
}

FILE_ARG=""
UNINSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)
      FILE_ARG="${2:-}"
      [[ -n "$FILE_ARG" ]] || { echo "error: --file needs a path" >&2; exit 1; }
      shift 2
      ;;
    --file=*)
      FILE_ARG="${1#--file=}"
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

# --- uninstall ------------------------------------------------------------------------------
if [[ "$UNINSTALL" == "1" ]]; then
  echo "==> Condense uninstaller"
  removed=0
  for p in "$APPIMAGE_DEST" "$DESKTOP_FILE" "$ICON_DEST"; do
    if [[ -e "$p" ]]; then
      rm -f "$p"
      echo "    removed $p"
      removed=1
    fi
  done
  if [[ -d "$DEB_INSTALL_DIR" ]]; then
    rm -rf "$DEB_INSTALL_DIR"
    echo "    removed $DEB_INSTALL_DIR"
    removed=1
  fi
  if [[ "$removed" == "0" ]]; then
    echo "    nothing installed."
  fi
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
  fi
  echo "done. (config/data under ~/.config/ai.aetheris.condense and"
  echo "      ~/.local/share/ai.aetheris.condense are left in place -- remove by hand if wanted.)"
  exit 0
fi

mkdir -p "$APP_DIR" "$APPS_DIR" "$ICON_DIR"

TMP_DOWNLOAD=""
TMP_EXTRACT=""
cleanup() {
  [[ -n "$TMP_DOWNLOAD" && -f "$TMP_DOWNLOAD" ]] && rm -f "$TMP_DOWNLOAD"
  [[ -n "$TMP_EXTRACT" && -d "$TMP_EXTRACT" ]] && rm -rf "$TMP_EXTRACT"
}
trap cleanup EXIT

SRC_ARTIFACT=""

if [[ -n "$FILE_ARG" ]]; then
  [[ -f "$FILE_ARG" ]] || { echo "error: --file $FILE_ARG not found" >&2; exit 1; }
  SRC_ARTIFACT="$(cd "$(dirname "$FILE_ARG")" && pwd)/$(basename "$FILE_ARG")"
  echo "==> using local artifact: $SRC_ARTIFACT"
else
  echo "==> looking for the newest GitHub Release asset ($REPO_SLUG)"
  ASSET_URL=""
  ASSET_NAME=""

  if command -v gh >/dev/null 2>&1; then
    ASSET_LINE="$(gh release view --repo "$REPO_SLUG" --json assets \
      -q '.assets[] | select(.name | test("\\.(AppImage|deb)$")) | "\(.name)\t\(.url)"' 2>/dev/null \
      | sort | head -1 || true)"
    if [[ -n "$ASSET_LINE" ]]; then
      ASSET_NAME="${ASSET_LINE%%$'\t'*}"
      ASSET_URL="${ASSET_LINE#*$'\t'}"
    fi
  fi

  if [[ -z "$ASSET_URL" ]]; then
    API_JSON="$(curl -fsSL "https://api.github.com/repos/$REPO_SLUG/releases/latest" 2>/dev/null || true)"
    if [[ -n "$API_JSON" ]]; then
      ASSET_URL="$(printf '%s' "$API_JSON" \
        | grep -o '"browser_download_url": *"[^"]*\.\(AppImage\|deb\)"' \
        | head -1 | sed -E 's/.*"(https:[^"]+)"/\1/' || true)"
      [[ -n "$ASSET_URL" ]] && ASSET_NAME="$(basename "$ASSET_URL")"
    fi
  fi

  if [[ -z "$ASSET_URL" ]]; then
    cat >&2 <<EOF
error: no .AppImage/.deb asset found on a GitHub Release for $REPO_SLUG yet.

The desktop app may not be tagged/released yet. Grab a build from CI instead:
    gh run list --repo $REPO_SLUG --workflow build-desktop.yml --branch feat/desktop-standalone
    gh run download <run-id> --repo $REPO_SLUG --name condense-desktop-x86_64-unknown-linux-gnu

...or build it locally (see desktop/README.md's Docker build section), then re-run:
    scripts/install-ubuntu.sh --file <path-to-.AppImage-or-.deb>
EOF
    exit 1
  fi

  echo "    downloading $ASSET_NAME"
  SUFFIX=".AppImage"
  [[ "$ASSET_NAME" == *.deb ]] && SUFFIX=".deb"
  TMP_DOWNLOAD="$(mktemp --suffix="$SUFFIX")"
  if command -v gh >/dev/null 2>&1 && [[ "$ASSET_URL" == https://api.github.com/* ]]; then
    gh api "$ASSET_URL" -H "Accept: application/octet-stream" > "$TMP_DOWNLOAD"
  else
    curl -fsSL "$ASSET_URL" -o "$TMP_DOWNLOAD"
  fi
  SRC_ARTIFACT="$TMP_DOWNLOAD"
fi

# --- install ---------------------------------------------------------------------------------
EXEC_PATH=""
ICON_FOUND=""

if [[ "$SRC_ARTIFACT" == *.deb ]]; then
  echo "==> extracting .deb into $DEB_INSTALL_DIR (dpkg -x, no root)"
  rm -rf "$DEB_INSTALL_DIR"
  mkdir -p "$DEB_INSTALL_DIR"
  dpkg -x "$SRC_ARTIFACT" "$DEB_INSTALL_DIR"
  EXEC_PATH="$(find "$DEB_INSTALL_DIR/usr/bin" -maxdepth 1 -type f 2>/dev/null | head -1 || true)"
  if [[ -z "$EXEC_PATH" ]]; then
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
    # hicolor icon dirs are named WxH[@scale]/apps/*.png -- sort by the numeric width descending
    # so we pick the highest-resolution icon rather than whatever order `find` happens to return.
    ICON_FOUND="$(find "$TMP_EXTRACT/squashfs-root" -path '*icons*' -name '*.png' 2>/dev/null \
      | sed -E 's#.*/([0-9]+)x[0-9]+(@[0-9]+)?/apps/.*#\1 &#' \
      | sort -rn | head -1 | cut -d' ' -f2- || true)"
    if [[ -z "$ICON_FOUND" ]]; then
      ICON_FOUND="$(find "$TMP_EXTRACT/squashfs-root" -maxdepth 1 -name '*.png' 2>/dev/null | head -1 || true)"
    fi
  else
    echo "    WARNING: --appimage-extract failed (FUSE/exec issue?) -- falling back to repo asset"
  fi
fi

# Fallback: the repo's own logo, if we're running from inside a checkout and extraction found nothing.
if [[ -z "$ICON_FOUND" ]]; then
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  if [[ -f "$REPO_ROOT/docs/assets/logo-256.png" ]]; then
    ICON_FOUND="$REPO_ROOT/docs/assets/logo-256.png"
  fi
fi

if [[ -n "$ICON_FOUND" ]]; then
  cp -f "$ICON_FOUND" "$ICON_DEST"
  echo "    icon: $ICON_DEST (from $ICON_FOUND)"
else
  echo "    WARNING: no icon found -- .desktop entry will use a generic fallback icon name"
  ICON_DEST="condense"
fi

echo "==> writing $DESKTOP_FILE"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=Condense
Comment=Local document search & chat
Exec=$EXEC_PATH
Icon=$ICON_DEST
Terminal=false
Type=Application
Categories=Utility;Office;
StartupWMClass=Condense
EOF

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
