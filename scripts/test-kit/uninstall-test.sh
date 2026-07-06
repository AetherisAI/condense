#!/usr/bin/env bash
# Condense desktop test kit — uninstaller. Removes everything setup-test.sh installed.
#
# Usage: ./uninstall-test.sh [-y|--yes]
#   -y/--yes   skip the confirmation prompt before deleting the data dir (downloaded model +
#              local database) -- for scripted/CI use only; a human should get the prompt.
set -euo pipefail

AUTO_YES=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes) AUTO_YES=1 ;;
  esac
done

BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
CONFIG_DIR="$HOME/.config/ai.aetheris.condense"
DATA_DIR="$HOME/.local/share/ai.aetheris.condense"

echo "==> Condense test kit uninstaller"

# --- AppImage -------------------------------------------------------------------------------
if [[ -f "$BIN_DIR/Condense.AppImage" ]]; then
  rm -f "$BIN_DIR/Condense.AppImage"
  echo "==> [1/5] removed $BIN_DIR/Condense.AppImage"
else
  echo "==> [1/5] $BIN_DIR/Condense.AppImage already absent"
fi

# --- .desktop file ----------------------------------------------------------------------------
if [[ -f "$APPS_DIR/condense.desktop" ]]; then
  rm -f "$APPS_DIR/condense.desktop"
  echo "==> [2/5] removed $APPS_DIR/condense.desktop"
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
  fi
else
  echo "==> [2/5] $APPS_DIR/condense.desktop already absent"
fi

# --- icon(s) ------------------------------------------------------------------------------------
removed_icon=0
for f in "$HOME"/.local/share/icons/hicolor/*/apps/condense.png; do
  [[ -e "$f" ]] || continue
  rm -f "$f"
  removed_icon=1
  echo "==> [3/5] removed $f"
done
[[ "$removed_icon" == "0" ]] && echo "==> [3/5] no condense.png icons found"

# --- config dir: restore a pre-existing config if setup-test.sh backed one up, else wipe --------
if [[ -f "$CONFIG_DIR/config.json.bak" ]]; then
  mv -f "$CONFIG_DIR/config.json.bak" "$CONFIG_DIR/config.json"
  echo "==> [4/5] restored pre-existing config.json from config.json.bak (config dir kept)"
elif [[ -d "$CONFIG_DIR" ]]; then
  rm -rf "$CONFIG_DIR"
  echo "==> [4/5] removed $CONFIG_DIR (no prior config to restore)"
else
  echo "==> [4/5] $CONFIG_DIR already absent"
fi

# --- data dir: confirm first -- can hold the downloaded model + local sqlite db (~1GB+) ----------
if [[ -d "$DATA_DIR" ]]; then
  SIZE="$(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)"
  if [[ "$AUTO_YES" == "1" ]]; then
    rm -rf "$DATA_DIR"
    echo "==> [5/5] removed $DATA_DIR ($SIZE, -y passed)"
  else
    read -r -p "Remove data dir $DATA_DIR ($SIZE -- downloaded model + local database)? [y/N] " reply
    case "$reply" in
      [yY]|[yY][eE][sS])
        rm -rf "$DATA_DIR"
        echo "==> [5/5] removed $DATA_DIR"
        ;;
      *)
        echo "==> [5/5] left $DATA_DIR in place"
        ;;
    esac
  fi
else
  echo "==> [5/5] $DATA_DIR already absent"
fi

echo
echo "done."
