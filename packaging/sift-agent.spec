# PyInstaller spec — Sift desktop ingestion agent (agent/app.py).
#
# One spec, both targets (branch on sys.platform):
#   macOS → a .app bundle (later zipped by build_macos.sh)
#   Linux → a onedir bundle under dist/sift-agent/ (fed to appimagetool by build_linux.sh)
#
# The agent is standalone: it never imports `sift`, torch, or the parsing/embedding stack, so we
# exclude those to keep the bundle small. watchdog picks its platform observer at import time, so
# the right one is pinned as a hidden import.

import os
import sys

is_mac = sys.platform == "darwin"

# SPECPATH is the packaging/ dir; the repo root (one up) is where the `agent` package lives.
repo_root = os.path.abspath(os.path.join(SPECPATH, ".."))
entry = os.path.join(SPECPATH, "sift_agent_entry.py")

# watchdog picks its platform observer at import time — pin the one this OS uses.
hidden = ["platformdirs", "httpx"]
if sys.platform == "darwin":
    hidden += ["watchdog.observers.fsevents"]
elif sys.platform == "win32":
    hidden += ["watchdog.observers.read_directory_changes"]
else:
    hidden += ["watchdog.observers.inotify", "watchdog.observers.inotify_buffer"]

a = Analysis(
    [entry],
    pathex=[repo_root],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["sift", "torch", "numpy", "markitdown", "tokenizers", "libsql"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sift-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app — no terminal window
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="sift-agent",
)

if is_mac:
    app = BUNDLE(
        coll,
        name="Sift Agent.app",
        bundle_identifier="ai.aetheris.sift-agent",
        info_plist={
            "CFBundleName": "Sift Agent",
            "CFBundleDisplayName": "Sift Agent",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
