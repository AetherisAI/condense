#!/usr/bin/env bash
# Build the macOS agent app and drop the zipped bundle into the web download dir.
# Runs locally (PyInstaller can't cross-compile). Requires the project .venv with Tkinter.
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root
VENV="${VENV:-.venv}"
PY="$VENV/bin/python"

if [ ! -x "$PY" ]; then
  echo "error: $PY not found — create the venv first (python3.12 -m venv .venv)" >&2
  exit 1
fi

echo "==> ensuring PyInstaller is installed"
"$PY" -m pip install --quiet --disable-pip-version-check pyinstaller

echo "==> checking Tkinter is available (required in the build interpreter)"
"$PY" -c "import tkinter" || { echo "error: Tkinter missing — brew install python-tk@3.12" >&2; exit 1; }

echo "==> building Sift Agent.app"
rm -rf build/sift-agent "dist/Sift Agent.app" "dist/sift-agent"
"$PY" -m PyInstaller packaging/sift-agent.spec --noconfirm \
  --distpath dist --workpath build/pyi-macos

APP="dist/Sift Agent.app"
[ -d "$APP" ] || { echo "error: $APP was not produced" >&2; exit 1; }

echo "==> zipping to web/public/downloads/sift-agent-macos.zip"
mkdir -p web/public/downloads
rm -f web/public/downloads/sift-agent-macos.zip
ditto -c -k --keepParent "$APP" web/public/downloads/sift-agent-macos.zip

echo "==> done: $(du -h web/public/downloads/sift-agent-macos.zip | cut -f1)  web/public/downloads/sift-agent-macos.zip"
