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

# Pinned to a numbered release (AppImage/appimagetool — the maintained successor to the archived
# AppImageKit's rolling "continuous" tag) and verified by sha256 before it's ever executed.
APPIMAGETOOL_VERSION=1.9.1
case "$(uname -m)" in
  x86_64)  tool=appimagetool-x86_64.AppImage;  sha256=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0 ;;
  aarch64) tool=appimagetool-aarch64.AppImage; sha256=f0837e7448a0c1e4e650a93bb3e85802546e60654ef287576f46c71c126a9158 ;;
  *) echo "unsupported arch: $(uname -m)" >&2; exit 1 ;;
esac
wget -q -O /usr/local/bin/appimagetool \
  "https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/${tool}"
echo "${sha256}  /usr/local/bin/appimagetool" | sha256sum -c -
chmod +x /usr/local/bin/appimagetool

python3 -m venv /venv
/venv/bin/pip install --quiet --upgrade pip
/venv/bin/pip install --quiet 'httpx>=0.28,<1' 'watchdog>=6,<7' 'platformdirs>=4.10,<5' 'pyinstaller>=6.21,<7'

# Hand off to the shared PyInstaller + AppImage assembly step.
exec bash /src/packaging/build_linux_in_container.sh
