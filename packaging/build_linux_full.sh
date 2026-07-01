#!/usr/bin/env bash
# Full bootstrap build inside a STOCK ubuntu:24.04 container (no prebuilt image, no buildx).
# `docker run --platform linux/amd64` emulates amd64 via QEMU even where the legacy builder
# cannot, so this yields a correct x86_64 AppImage on an Apple-silicon host. Reads the repo from
# /src (ro), writes the AppImage to /out.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "==> arch: $(uname -m)"
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  python3 python3-venv python3-tk python3-dev \
  binutils file wget ca-certificates desktop-file-utils >/dev/null

case "$(uname -m)" in
  x86_64)  tool=appimagetool-x86_64.AppImage ;;
  aarch64) tool=appimagetool-aarch64.AppImage ;;
  *) echo "unsupported arch: $(uname -m)" >&2; exit 1 ;;
esac
wget -q -O /usr/local/bin/appimagetool \
  "https://github.com/AppImage/AppImageKit/releases/download/continuous/$tool"
chmod +x /usr/local/bin/appimagetool

python3 -m venv /venv
/venv/bin/pip install --quiet --upgrade pip
/venv/bin/pip install --quiet httpx watchdog platformdirs pyinstaller

# Hand off to the shared PyInstaller + AppImage assembly step.
exec bash /src/packaging/build_linux_in_container.sh
