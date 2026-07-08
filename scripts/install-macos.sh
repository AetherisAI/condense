#!/usr/bin/env bash
# UNTESTED -- no macOS hardware available to this WP. Written against the documented .dmg shape
# tauri-action / build-desktop.yml produces (desktop/src-tauri/target/release/bundle/dmg/*.dmg),
# but never actually run on a Mac. Sanity-check the mount/copy/detach sequence by hand the first
# time before trusting it unattended, and please report back anything that doesn't match reality
# (dmg volume name, .app name, etc. are all best-guess from tauri.conf.json's productName).
#
# Install (or uninstall) the Condense desktop app on macOS -- no sudo required.
#
# Resolution order for the .dmg:
#   1. --file <path>   use this local .dmg directly.
#   2. the newest GitHub Release asset for AetherisAI/condense (`gh release download` if `gh` is
#      on PATH and authenticated, else a plain `curl` against the public releases API).
#   3. neither found -> print a clear message pointing at CI artifacts and exit non-zero.
#
# Install layout:
#   ~/Applications/Condense.app
#
# Usage:
#   scripts/install-macos.sh                    # install from the latest GitHub Release
#   scripts/install-macos.sh --file ./Condense_0.4.0_aarch64.dmg
#   scripts/install-macos.sh --uninstall
set -euo pipefail

REPO_SLUG="AetherisAI/condense"
APP_NAME="Condense.app"
APP_DEST="$HOME/Applications/$APP_NAME"

usage() {
  sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
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

if [[ "$UNINSTALL" == "1" ]]; then
  echo "==> Condense uninstaller"
  if [[ -d "$APP_DEST" ]]; then
    rm -rf "$APP_DEST"
    echo "    removed $APP_DEST"
  else
    echo "    $APP_DEST already absent"
  fi
  echo "done. (~/Library/Application Support/ai.aetheris.condense is left in place -- remove by"
  echo "      hand if you also want the downloaded engine/embedder/model + local database gone.)"
  exit 0
fi

mkdir -p "$HOME/Applications"

TMP_DOWNLOAD=""
MOUNT_POINT=""
cleanup() {
  if [[ -n "$MOUNT_POINT" && -d "$MOUNT_POINT" ]]; then
    hdiutil detach "$MOUNT_POINT" -quiet 2>/dev/null || true
  fi
  [[ -n "$TMP_DOWNLOAD" && -f "$TMP_DOWNLOAD" ]] && rm -f "$TMP_DOWNLOAD"
}
trap cleanup EXIT

SRC_DMG=""

if [[ -n "$FILE_ARG" ]]; then
  [[ -f "$FILE_ARG" ]] || { echo "error: --file $FILE_ARG not found" >&2; exit 1; }
  SRC_DMG="$FILE_ARG"
  echo "==> using local artifact: $SRC_DMG"
else
  echo "==> looking for the newest GitHub Release .dmg asset ($REPO_SLUG)"
  ASSET_URL=""
  ASSET_NAME=""

  if command -v gh >/dev/null 2>&1; then
    ASSET_LINE="$(gh release view --repo "$REPO_SLUG" --json assets \
      -q '.assets[] | select(.name | test("\\.dmg$")) | "\(.name)\t\(.url)"' 2>/dev/null \
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
        | grep -o '"browser_download_url": *"[^"]*\.dmg"' \
        | head -1 | sed -E 's/.*"(https:[^"]+)"/\1/' || true)"
      [[ -n "$ASSET_URL" ]] && ASSET_NAME="$(basename "$ASSET_URL")"
    fi
  fi

  if [[ -z "$ASSET_URL" ]]; then
    cat >&2 <<EOF
error: no .dmg asset found on a GitHub Release for $REPO_SLUG yet.

The desktop app may not be tagged/released yet. Grab a build from CI instead (Actions ->
build-desktop -> feat/desktop-standalone -> artifact condense-desktop-aarch64-apple-darwin),
then re-run:
    scripts/install-macos.sh --file <path-to-.dmg>
EOF
    exit 1
  fi

  echo "    downloading $ASSET_NAME"
  TMP_DOWNLOAD="$(mktemp -t condense-dmg).dmg"
  if command -v gh >/dev/null 2>&1 && [[ "$ASSET_URL" == https://api.github.com/* ]]; then
    gh api "$ASSET_URL" -H "Accept: application/octet-stream" > "$TMP_DOWNLOAD"
  else
    curl -fsSL "$ASSET_URL" -o "$TMP_DOWNLOAD"
  fi
  SRC_DMG="$TMP_DOWNLOAD"
fi

echo "==> mounting $SRC_DMG"
ATTACH_OUTPUT="$(hdiutil attach "$SRC_DMG" -nobrowse -readonly -noautoopen 2>&1)"
echo "$ATTACH_OUTPUT"
MOUNT_POINT="$(printf '%s\n' "$ATTACH_OUTPUT" | awk -F'\t' '/\/Volumes\// {print $NF}' | tail -1)"
if [[ -z "$MOUNT_POINT" || ! -d "$MOUNT_POINT" ]]; then
  echo "error: could not determine mount point from hdiutil output above" >&2
  exit 1
fi

SRC_APP="$(find "$MOUNT_POINT" -maxdepth 1 -name '*.app' | head -1 || true)"
if [[ -z "$SRC_APP" ]]; then
  echo "error: no .app bundle found in $MOUNT_POINT" >&2
  exit 1
fi

echo "==> copying $(basename "$SRC_APP") -> $APP_DEST"
rm -rf "$APP_DEST"
cp -R "$SRC_APP" "$APP_DEST"

echo "==> detaching $MOUNT_POINT"
hdiutil detach "$MOUNT_POINT" -quiet
MOUNT_POINT=""

echo
echo "done. Launch \"Condense\" from Launchpad/Spotlight, or directly:"
echo "  open \"$APP_DEST\""
echo
echo "First launch: right-click -> Open (unsigned build, Gatekeeper will otherwise refuse it)."
