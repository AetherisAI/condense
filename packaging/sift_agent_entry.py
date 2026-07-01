"""PyInstaller entry point for the Sift desktop ingestion agent.

A thin wrapper so PyInstaller has a concrete script to analyze; the real app lives in
``agent.app``. Kept out of ``agent/`` so it never ships in the wheel.
"""

from agent.app import main

if __name__ == "__main__":
    raise SystemExit(main())
