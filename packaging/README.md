# Packaging — the Sift desktop agent

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

## Notes / caveats
- **Unsigned macOS app** → Gatekeeper blocks double-click on first launch; right-click → Open (the Agent panel shows this). Future: `codesign` + notarize.
- **AppImage fallback:** if `appimagetool` misbehaves in your Docker setup, tar the onedir (`dist/sift-agent/`) as `sift-agent-ubuntu.tar.gz` instead and point the UI link at it.
- Artifacts are versioned by rebuilding, not committed. For public distribution, consider attaching them to a GitHub Release instead.
