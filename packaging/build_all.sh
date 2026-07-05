#!/usr/bin/env bash
# Build every available agent artifact into web/public/downloads/.
# macOS runs locally; Linux runs in Docker. Each step is independent — a failure in one
# (e.g. Docker not running) doesn't abort the other.
set -uo pipefail

here="$(dirname "$0")"

echo "############## macOS ##############"
if [ "$(uname -s)" = "Darwin" ]; then
  bash "$here/build_macos.sh" || echo "!! macOS build failed"
else
  echo "skipped (not on macOS)"
fi

echo "############## Linux (Docker) ##############"
bash "$here/build_linux.sh" || echo "!! Linux build failed (is Docker running?)"

echo "############## artifacts ##############"
ls -lh "$here/../web/public/downloads/" 2>/dev/null || echo "(none)"
