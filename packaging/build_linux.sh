#!/usr/bin/env bash
# Build the Ubuntu AppImage in a Linux container (PyInstaller can't cross-compile).
# Output: web/public/downloads/sift-agent-ubuntu.AppImage
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root

if ! docker info >/dev/null 2>&1; then
  echo "error: Docker daemon not running — start Docker Desktop and retry." >&2
  exit 1
fi

# Builds inside a stock ubuntu:24.04 container. By default targets the host's NATIVE arch — fast and
# reliable. To produce an x86_64 AppImage for the common Ubuntu desktop, run on a native amd64 host
# or in CI (a GitHub Actions ubuntu runner is amd64): set SIFT_LINUX_PLATFORM=linux/amd64. NOTE:
# emulated amd64 on an Apple-silicon (arm64) Colima is unreliable — the legacy builder has no buildx
# and QEMU dpkg fails mid-install — so cross-arch here is best left to CI.
PLATFORM_FLAG=""
if [ -n "${SIFT_LINUX_PLATFORM:-}" ]; then
  PLATFORM_FLAG="--platform ${SIFT_LINUX_PLATFORM}"
  echo "==> platform override: ${SIFT_LINUX_PLATFORM} (emulated if non-native — may be slow/flaky)"
else
  echo "==> platform: native ($(docker version --format '{{.Server.Arch}}' 2>/dev/null || echo host))"
fi

mkdir -p web/public/downloads

# shellcheck disable=SC2086
docker run --rm $PLATFORM_FLAG \
  -v "$PWD:/src:ro" \
  -v "$PWD/web/public/downloads:/out" \
  ubuntu:24.04 bash /src/packaging/build_linux_full.sh

echo "==> done: web/public/downloads/sift-agent-ubuntu.AppImage"
