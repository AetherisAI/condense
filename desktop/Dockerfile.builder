# condense-tauri-builder
#
# Purpose: self-contained image to compile Tauri 2.x desktop apps (Linux
# targets: .deb + .AppImage) without needing webkit2gtk-dev / rustup / node
# installed on the host. Designed to be run with an ARBITRARY, NON-ROOT uid
# (e.g. `docker run --user $(id -u):$(id -g)`) so build artifacts on bind
# mounts come out owned by the host user, not root.
#
# Key design decisions (documented inline so this can live in the repo as-is):
#   1. Rust toolchain lives in /opt/rustup (RUSTUP_HOME) + /opt/cargo
#      (CARGO_HOME), both chmod'd a+rwX so an arbitrary uid at runtime can
#      still write to $CARGO_HOME/registry (dependency cache) and can run
#      `rustup` subcommands if ever needed. The toolchain binaries themselves
#      are installed by root at build time and are world-readable+executable.
#   2. Node.js 22.x is installed via the NodeSource setup script (deb repo),
#      simplest to keep patched and it matches how most CI images do it.
#   3. AppImage tooling (linuxdeploy, appimagetool, used internally by
#      tauri-bundler) cannot use FUSE inside a container -> we set
#      APPIMAGE_EXTRACT_AND_RUN=1 globally so it falls back to extract+run.
#   4. NO_STRIP=true is exported because linuxdeploy's default strip pass has
#      been known to choke inside minimal containers / on some Rust binaries;
#      harmless to leave on for a dev builder image.
#   5. We do NOT create/switch to a fixed non-root user in the image itself
#      (no adduser). Instead we rely on `docker run --user $(id -u):$(id -g)`
#      at run time, which only works because every directory the build needs
#      to write to (CARGO_HOME, npm cache via $HOME, target dir under
#      /work) is either world-writable or bind-mounted from the host with
#      host-user ownership already. See runbook comment at bottom.
#   6. QA tooling (xvfb + dbus + fonts + x11 utils) added for T4/T7: webkit
#      renders no text at all without a font package present, and the
#      boot-smoke screenshot needs a virtual X server + window manager-free
#      root-window capture (`import -display :99 -window root`). CAVEAT
#      (found during T4's boot-smoke): `xvfb-run` and `dbus-run-session`
#      both HANG in this image when they are the container's own PID 1 (no
#      init process) — their internal readiness handshakes rely on signal
#      delivery semantics PID 1 doesn't get without an init. Don't wrap the
#      launch command in either; start `Xvfb :99 ... &` yourself and `sleep`
#      briefly instead (see desktop/README.md's boot-smoke section) — the
#      app tolerates a missing D-Bus session bus fine (one harmless AT-SPI
#      warning on stderr).
#   7. librsvg2-bin (rsvg-convert CLI) added alongside the existing
#      librsvg2-dev (headers only, used by the Tauri/linuxdeploy build) so
#      the icon pipeline has a first-class, no-network SVG rasterizer
#      in-container (preferred over the sharp/imagemagick fallbacks).

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# ---------------------------------------------------------------------------
# 1. System packages: build toolchain + Tauri/webkit2gtk runtime deps +
#    bundler deps (fakeroot/dpkg-dev for .deb, file for AppImage detection)
#    + QA tooling (xvfb/dbus/fonts/x11 utils) for boot-smoke screenshots.
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    file \
    git \
    pkg-config \
    libssl-dev \
    libgtk-3-dev \
    libwebkit2gtk-4.1-dev \
    libayatana-appindicator3-dev \
    librsvg2-dev \
    librsvg2-bin \
    libxdo-dev \
    libsoup-3.0-dev \
    libjavascriptcoregtk-4.1-dev \
    fakeroot \
    dpkg-dev \
    python3 \
    python3-pip \
    ca-certificates \
    xz-utils \
    zip \
    unzip \
    patchelf \
    imagemagick \
    xvfb \
    x11-utils \
    x11-apps \
    dbus \
    dbus-x11 \
    fonts-dejavu-core \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

# python3-pillow: used to synthesize a placeholder PNG for `tauri icon` when
# no source icon is supplied yet (smoke test + early app bootstrap).
RUN apt-get update && apt-get install -y --no-install-recommends python3-pil \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# 2. Node.js 22 via NodeSource
# ---------------------------------------------------------------------------
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npm --version

# ---------------------------------------------------------------------------
# 3. Rust stable via rustup, installed to a shared, world-writable location
#    so containers started with an arbitrary --user can still use cargo's
#    registry cache and (if ever needed) rustup itself.
# ---------------------------------------------------------------------------
ENV RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/opt/cargo \
    PATH=/opt/cargo/bin:$PATH

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rustup-init.sh \
    && sh /tmp/rustup-init.sh -y --default-toolchain stable --profile minimal --no-modify-path \
    && rm /tmp/rustup-init.sh \
    && rustup component add rustfmt clippy \
    && chmod -R a+rwX "$RUSTUP_HOME" "$CARGO_HOME" \
    && rustc --version && cargo --version && cargo fmt --version && cargo clippy --version

# tauri-cli is invoked via `npx @tauri-apps/cli` from each project's own
# package.json devDependency, so no global cargo install is needed here.
# This keeps the image decoupled from any one app's Tauri version pin.

# ---------------------------------------------------------------------------
# 4. AppImage / linuxdeploy runtime quirks inside containers (no FUSE).
# ---------------------------------------------------------------------------
ENV APPIMAGE_EXTRACT_AND_RUN=1 \
    NO_STRIP=true

# ---------------------------------------------------------------------------
# 5. Writable HOME for arbitrary-uid runs (npm/electron/etc look at $HOME for
#    caches like ~/.npm, ~/.cache). /tmp is already world-writable in the
#    base image; we point HOME there by default. Callers can override HOME
#    via `-e HOME=/work/.home` + a mounted dir if they want a persistent npm
#    cache across runs (recommended for repeated builds).
# ---------------------------------------------------------------------------
ENV HOME=/tmp

WORKDIR /work

# ---------------------------------------------------------------------------
# Runbook (documented, not executed here):
#
#   docker run --rm \
#     --memory=5g --memory-swap=5g \
#     -e CARGO_BUILD_JOBS=2 \
#     -e CARGO_HOME=/work/.cargo-home \
#     -e HOME=/work/.home \
#     --user "$(id -u):$(id -g)" \
#     -v /path/to/repo-worktree:/work \
#     -v /path/to/persistent-cargo-cache:/work/.cargo-home \
#     -w /work/desktop \
#     condense-tauri-builder \
#     bash -lc "npm install && npx tauri build"
#
# Notes:
#   - CARGO_HOME is redirected to a writable, bind-mounted path under /work
#     so the registry/git checkout cache persists across container runs
#     (huge speedup on rebuilds) instead of living in the throwaway /opt
#     cache baked into the image (which is read-only-by-convention once a
#     non-root uid tries to `cargo install` something new into it, though
#     writing registry cache entries works fine since /opt/cargo is a+rwX).
#   - HOME is redirected similarly so `npm install` cache + electron-builder
#     style caches don't vanish between runs and don't try to write into a
#     root-owned /root.
#   - Boot-smoke screenshots: `xvfb-run -a --server-args="-screen 0 1280x800x24"
#     bash -lc "dbus-run-session -- bash -lc '<launch appimage>; sleep 8;
#     import -display \$DISPLAY -window root qa-boot.png; <kill appimage>'"`
# ---------------------------------------------------------------------------
