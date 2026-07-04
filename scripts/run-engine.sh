#!/usr/bin/env bash
# Launch the Sift engine in a memory-capped, OOM-isolated, detached systemd --user unit.
#
# WHY (DECISIONS.md D29): a runaway ingest — or any engine memory spike — must NEVER trigger the
# *system* OOM killer. On a typical dev box VS Code is the OOM killer's first target (it sets its
# own oom_score_adj=100, giving it an oom_score of ~700+), so a global OOM event takes down the
# editor and any Claude Code session living in its integrated terminal. Running the engine as a
# transient --user unit with MemoryMax puts it in its own cgroup v2: if it exceeds the cap, the
# *cgroup* OOM killer reaps only the engine, the system as a whole never runs out, and VS Code is
# never touched. The unit is also detached from the launching shell, so the engine no longer
# appears under (or dies with) the VS Code process tree, and a profiler no longer mis-attributes
# its memory to "code".
#
# WHY NO MemoryHigh (DECISIONS.md D34): a prior version of this script also set a soft
# `MemoryHigh` throttle band below `MemoryMax`. A real E2E run hit it: the engine's memory was
# 100% anonymous (no reclaimable page cache) and the unit already had `MemorySwapMax=0`, so once
# usage crossed `MemoryHigh` the kernel's `memory.high` throttling (`memory.events high=150789+`,
# every allocating thread parked in `mem_cgroup_handle_over_high`) stalled EVERY thread in the
# cgroup — the event loop, signal handling, all of it. `/healthz` was dead for 690+ seconds,
# SIGTERM was ignored, and only a SIGKILL from systemd ended it; because usage never crossed
# `MemoryMax`, the *OOM killer* never fired either — this was a livelock, not a crash. A cgroup
# with `MemoryMax` only, and no `MemoryHigh` band, has no soft-throttle purgatory to livelock in:
# an overrun crosses `MemoryMax` directly and the cgroup OOM killer reaps it fast and clean. Every
# systemd unit in this repo (this script, test/ingest runs) follows the same rule: `MemoryMax` +
# `MemorySwapMax=0` + `OOMScoreAdjust=1000` + `OOMPolicy=kill`, and NEVER `MemoryHigh`.
#
# Usage:
#   scripts/run-engine.sh                 # start (or restart) the engine, capped at 2G
#   ENGINE_MEM_MAX=3G scripts/run-engine.sh
#   systemctl --user status sift-engine
#   journalctl --user -u sift-engine -f
#   systemctl --user stop sift-engine
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CAP="${ENGINE_MEM_MAX:-2G}" # hard ceiling only: exceed it -> cgroup OOM kills the engine, fast
PORT="${ENGINE_PORT:-8000}"

# Replace any prior instance cleanly (idempotent restart).
systemctl --user stop sift-engine 2>/dev/null || true
systemctl --user reset-failed sift-engine 2>/dev/null || true

systemd-run --user \
  --unit=sift-engine \
  --description="Sift engine (memory-capped, OOM-isolated from VS Code)" \
  --working-directory="$REPO" \
  -p MemoryMax="$CAP" \
  -p MemorySwapMax=0 \
  -p OOMScoreAdjust=1000 \
  -p OOMPolicy=kill \
  --collect \
  "$REPO/.venv/bin/python" -m uvicorn sift.api.main:app --host 127.0.0.1 --port "$PORT"

echo "sift-engine started — MemoryMax=$CAP (no MemoryHigh) MemorySwapMax=0 OOMScoreAdjust=1000 port=$PORT"
echo "  the engine is now isolated: a runaway kills ONLY this unit, never VS Code / the session"
echo "  status: systemctl --user status sift-engine | logs: journalctl --user -u sift-engine -f"
