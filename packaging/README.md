# Packaging — the Sift agent, two targets

Two PyInstaller specs build the same `agent/` package for two different consumers (DECISIONS.md
D54) — they are **not** interchangeable, so pick the row that matches what you're building:

| Target | Spec | Shape | Consumer |
|--------|------|-------|----------|
| Desktop GUI download | `sift-agent.spec` | onedir, `console=False`, own Tkinter window, no stdout | a human double-clicking a download (this file, below) |
| Headless CLI sidecar | `sift-agent-cli.spec` | **onefile**, **`console=True`** | Tauri desktop shell (`bundle.externalBin`) — see "Second target" below — or any script/systemd unit |

## Target 1: the Tkinter desktop download

Builds the `agent/` Tkinter watcher into self-contained, ready-to-run downloads (no Python/pip on
the user's machine) and drops them into `web/public/downloads/`, where the web UI's **Agent** panel
links to them (served same-origin by Vite in dev / nginx in prod).

| OS | Artifact | How the user runs it |
|----|----------|----------------------|
| macOS | `sift-agent-macos.zip` (a `.app`) | unzip → right-click **Open** (unsigned, first launch only) |
| Ubuntu/Linux | `sift-agent-ubuntu.AppImage` | `chmod +x` → run — no install |
| Windows | — | coming soon |

## Prerequisites
- **macOS build:** the project `.venv` (Python 3.12) with Tkinter — `brew install python-tk@3.12` if `python -c "import tkinter"` fails. PyInstaller is auto-installed by the script.
- **Linux build:** **Docker Desktop running** (PyInstaller can't cross-compile, so the Ubuntu binary is built in an `ubuntu:24.04` container). First run downloads the base image + `appimagetool`.

## Build
```bash
# both (mac locally + linux in Docker)
bash packaging/build_all.sh

# or individually
bash packaging/build_macos.sh
bash packaging/build_linux.sh
```

Outputs land in `web/public/downloads/` (gitignored — never committed; ~20–40 MB each).

## How it works
- `sift-agent.spec` — one PyInstaller spec, branches on `sys.platform` (macOS → `.app` BUNDLE; Linux → onedir). `sift_agent_entry.py` is the entry (`from agent.app import main`). The agent never imports `sift`, so the engine/ML stack is excluded → small bundle.
- `build_macos.sh` — PyInstaller → `dist/Sift Agent.app` → `ditto` zip.
- `Dockerfile.linux` + `build_linux_in_container.sh` — PyInstaller onedir → AppDir (AppRun + `.desktop` + a stdlib-generated icon) → `appimagetool --appimage-extract-and-run` (no FUSE needed in-container).

## Windows & CI builds (`.github/workflows/build-agent.yml`)
PyInstaller can't cross-compile, and there's no local Windows environment — so **Windows** (and native **x86_64 Linux**, which the arm64-on-Colima local build can't produce) are built in CI. The `build-agent` workflow runs the *same* `sift-agent.spec` on `windows-latest` / `macos-latest` / `ubuntu-latest`, does an import + best-effort GUI-launch smoke, and uploads each artifact. On a `v*` **tag** it attaches them to a **GitHub Release**; the web UI's Windows row links to `releases/latest/download/sift-agent-windows.zip`.
- Trigger manually: `gh workflow run build-agent.yml --ref <branch>` (build smoke, no release).
- Publish: push a `v*` tag → the `release` job creates/updates the Release with all three artifacts.
- **GUI launch is not click-tested** — CI has no reliable desktop; the launch smoke is best-effort (`continue-on-error`). Real GUI verification needs a human on each OS.

## Notes / caveats
- **Unsigned macOS app** → Gatekeeper blocks double-click on first launch; right-click → Open (the Agent panel shows this). Future: `codesign` + notarize.
- **AppImage fallback:** if `appimagetool` misbehaves in your Docker setup, tar the onedir (`dist/sift-agent/`) as `sift-agent-ubuntu.tar.gz` instead and point the UI link at it.
- Artifacts are versioned by rebuilding, not committed. For public distribution, consider attaching them to a GitHub Release instead.

## Target 2: the headless CLI sidecar (`sift-agent-cli.spec`)

`agent/cli.py` (`--json` NDJSON events + SIGTERM handling, D54) frozen as a single-file, console
binary — the shape a supervising process (Tauri's `plugin-shell` sidecar) needs: a real,
line-readable stdout, one file, no window. It is **not** a replacement for Target 1 — the Tkinter
build has no stdout worth reading and isn't supervisable; this build has no window and isn't
meant to be double-clicked.

### Build
```bash
pyinstaller packaging/sift-agent-cli.spec
# → dist/sift-agent-cli  (single executable; add .exe on Windows)
```
Same excludes as `sift-agent.spec` (`sift`, `torch`, `numpy`, `markitdown`, `tokenizers`,
`libsql` — the agent never imports the engine/ML stack) and the same per-OS `watchdog` observer
hidden-import, since `--watch` uses it exactly like the Tkinter app does. Entry point is
`sift_agent_cli_entry.py` (`from agent.cli import main`), mirroring `sift_agent_entry.py`'s
convention.

### Smoke-test after a build
```bash
./dist/sift-agent-cli --help                                    # exit 0
./dist/sift-agent-cli --json --dry-run /some/scratch/dir --server http://x --token y   # valid NDJSON
```
A `--watch` run should also stop cleanly (exit 0) on SIGTERM, not just Ctrl-C — that's the whole
point of D54's SIGTERM handler; a Tauri `kill()` never sends SIGINT.

### Tauri target-triple naming (`bundle.externalBin`)
Tauri expects each platform's sidecar binary named `<name>-<target-triple>[.exe]` — e.g.
```
sift-agent-cli-x86_64-unknown-linux-gnu
sift-agent-cli-aarch64-apple-darwin
sift-agent-cli-x86_64-pc-windows-msvc.exe
```
so after building on each OS, rename the raw `dist/sift-agent-cli` output before dropping it into
`desktop/src-tauri/binaries/` (see the `desktop/` WP's CI, `build-desktop.yml`):
`mv dist/sift-agent-cli dist/sift-agent-cli-$(rustc --print host-tuple)` (append `.exe` on
Windows). `rustc --print host-tuple` is the simplest way to get the exact triple Tauri expects
for the machine currently building.
