# PyInstaller spec — headless CLI target of the ingestion agent (agent/cli.py).
#
# Onefile, console=True: the Tauri desktop shell supervises this as an external sidecar binary
# (tauri.conf.json `bundle.externalBin`) — it needs a real, readable stdout (NDJSON `--json`
# events) and a single file, renamed per Tauri's target-triple convention
# (`sift-agent-cli-x86_64-unknown-linux-gnu` etc. — see packaging/README.md). This is the
# "wrong shape for a sidecar" twin of `sift-agent.spec` (onedir, `console=False`, its own Tkinter
# window, no usable stdout) — that one is untouched and stays the standalone GUI download
# (DECISIONS.md D54).
#
# Same exclusions as sift-agent.spec: the agent never imports `sift`, torch, or the
# parsing/embedding stack, so the bundle stays small. watchdog picks its platform observer at
# import time, so the right one is pinned as a hidden import — needed here too, since `--watch`
# uses it exactly like the Tkinter app does.

import os
import sys

# SPECPATH is the packaging/ dir; the repo root (one up) is where the `agent` package lives.
repo_root = os.path.abspath(os.path.join(SPECPATH, ".."))
entry = os.path.join(SPECPATH, "sift_agent_cli_entry.py")

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
    a.binaries,
    a.datas,
    [],
    name="sift-agent-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # the sidecar's whole contract is real stdout (NDJSON `--json` events)
)
