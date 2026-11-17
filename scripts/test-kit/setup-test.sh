#!/usr/bin/env bash
# Condense desktop test kit — installer.
#
# Idempotent, no sudo required. Safe to re-run: re-installs the AppImage/icon/.desktop file
# in place, and regenerates manifest.json from manifest.template.json every time (so re-running
# after moving the kit folder re-resolves the file:// path correctly).
#
# Usage: ./setup-test.sh   (run from anywhere -- it resolves its own directory)
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Condense test kit installer"
echo "    kit dir: $KIT_DIR"
echo

# --- (a)/(b): render manifest.json from the template, resolving __KIT_DIR__ to this exact path.
if [[ ! -f "$KIT_DIR/manifest.template.json" ]]; then
  echo "ERROR: $KIT_DIR/manifest.template.json not found -- did you copy the WHOLE kit folder?" >&2
  exit 1
fi
sed "s#__KIT_DIR__#${KIT_DIR}#g" "$KIT_DIR/manifest.template.json" > "$KIT_DIR/manifest.json"
echo "==> [1/4] wrote $KIT_DIR/manifest.json"
echo "    (engine: local file:// from this kit -- embedder + model: real public URLs)"

# --- (c): install AppImage + icon + .desktop, GNOME/freedesktop app-grid convention. -------------
BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/128x128/apps"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$BIN_DIR" "$ICON_DIR" "$APPS_DIR"

if [[ ! -f "$KIT_DIR/Condense.AppImage" ]]; then
  echo "ERROR: $KIT_DIR/Condense.AppImage not found -- did you copy the WHOLE kit folder?" >&2
  exit 1
fi
cp -f "$KIT_DIR/Condense.AppImage" "$BIN_DIR/Condense.AppImage"
chmod +x "$BIN_DIR/Condense.AppImage"
cp -f "$KIT_DIR/condense.png" "$ICON_DIR/condense.png"

cat > "$APPS_DIR/condense.desktop" <<EOF
[Desktop Entry]
Name=Condense
Comment=Local-first document chat & search
Exec=$BIN_DIR/Condense.AppImage
Icon=condense
Terminal=false
Type=Application
Categories=Office;Utility;
StartupWMClass=Condense
EOF

echo "==> [2/4] installed:"
echo "      $BIN_DIR/Condense.AppImage"
echo "      $ICON_DIR/condense.png"
echo "      $APPS_DIR/condense.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 \
    && echo "    update-desktop-database: OK" \
    || echo "    update-desktop-database: reported an issue (non-fatal)"
fi
if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "$APPS_DIR/condense.desktop" \
    && echo "    desktop-file-validate: OK" \
    || echo "    desktop-file-validate: reported an issue (non-fatal)"
fi

# --- (d): config.json -- back up any existing one, then write a fresh first-run config. ---------
CONFIG_DIR="$HOME/.config/ai.aetheris.condense"
mkdir -p "$CONFIG_DIR"
CONFIG_FILE="$CONFIG_DIR/config.json"

if [[ -f "$CONFIG_FILE" ]]; then
  cp -f "$CONFIG_FILE" "$CONFIG_FILE.bak"
  echo "==> [3/4] existing config.json found -- backed up to $CONFIG_FILE.bak"
else
  echo "==> [3/4] no existing config.json -- writing a fresh one"
fi

if command -v openssl >/dev/null 2>&1; then
  INGEST_TOKEN="$(openssl rand -hex 16)"
else
  INGEST_TOKEN="$(head -c16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi

cat > "$CONFIG_FILE" <<EOF
{
  "schema": 1,
  "mode": null,
  "engine_port": 8801,
  "embedder_port": 8802,
  "ingest_token": "$INGEST_TOKEN",
  "llm": {
    "base_url": "",
    "model": "",
    "api_key": ""
  },
  "manifest_url": "file://$KIT_DIR/manifest.json",
  "agent": {
    "paths": [],
    "delete_removed": false
  }
}
EOF
echo "    wrote $CONFIG_FILE (fresh ingest_token, manifest_url -> this kit, mode: null = first run)"

echo
echo "==> [4/4] done."
echo
echo "Next steps:"
echo "  1. Launch \"Condense\" from your application grid, or directly:"
echo "       $BIN_DIR/Condense.AppImage"
echo "  2. First-run wizard -> choose \"Run locally\"."
echo "  3. It downloads ~750MB total (embedder + bge-m3 model -- both public); the engine itself"
echo "     comes from this kit INSTANTLY, no download, no GitHub access needed."
echo "  4. When asked for an LLM key: paste one (Mistral/OpenAI/Anthropic auto-detected) or hit"
echo "     Skip -- without a key, Ask/chat answers will fail but Find/search still works fully."
echo
echo "Uninstall any time with: $KIT_DIR/uninstall-test.sh"
