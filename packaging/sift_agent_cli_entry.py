"""PyInstaller entry point for the headless ingestion-agent CLI (Tauri sidecar target).

A thin wrapper so PyInstaller has a concrete script to analyze; the real CLI lives in
``agent.cli``. Kept out of ``agent/`` so it never ships in the wheel — mirrors
``sift_agent_entry.py``'s convention for the Tkinter desktop app.
"""

from agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
