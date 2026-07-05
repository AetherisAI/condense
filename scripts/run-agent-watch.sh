#!/usr/bin/env bash
# Launch the Condense ingestion agent in ``--watch --delete-removed`` mode as a memory-capped,
# OOM-isolated, detached systemd --user unit. The headless twin of the desktop app (agent/app.py):
# no Tk window, just a folder watched continuously and reconciled against the engine.
#
# WHY the same cgroup posture as scripts/run-engine.sh (DECISIONS.md D29/D34): a runaway walk
# (a huge tree, a pathological symlink loop, a giant batch held in memory) must never trigger the
# *system* OOM killer and take VS Code / this session down with it. `MemoryMax` + `MemorySwapMax=0`
# puts the agent in its own cgroup v2 — an overrun is reaped by the *cgroup* OOM killer, and
# nothing else on the box is touched. No `MemoryHigh` band, same reasoning as run-engine.sh: a
# soft-throttle purgatory can livelock every thread in the cgroup without ever crossing
# `MemoryMax`, which is worse than a clean, fast OOM-kill-and-restart.
#
# WHY Restart=always (same D39/engine precedent): a clean external SIGTERM (not a `systemctl
# stop`) must not leave the watcher silently dead — `Restart=always` restarts on ANY exit, clean
# or OOM-killed, while `systemctl stop sift-agent-watch` remains the sanctioned way to actually
# stop it (a manual stop masks Restart by design).
#
# WHY --setenv=PYTHONUNBUFFERED=1 (a real incident, not theoretical): stdout is LINE-buffered when
# attached to a terminal but BLOCK-buffered (usually 4-8 KiB) when redirected to a file/pipe — which
# `StandardOutput=append:$LOG_FILE` always is. Without this, `[sync] ...`/`[watch] ...` lines sit in
# Python's internal buffer and don't reach the log file until the buffer fills or the process
# exits — in practice the log appeared to "lag minutes" behind what the agent was actually doing,
# making `tail -f`/live debugging useless right when you need it most. `PYTHONUNBUFFERED=1` forces
# stdout/stderr unbuffered so every `print()` lands in the log the instant it's written.
#
# Usage:
#   scripts/run-agent-watch.sh                              # start (or restart), Acme, :8001
#   SIFT_TOKEN=condense-dev scripts/run-agent-watch.sh
#   WATCH_DIR=/path/to/folder SERVER=http://127.0.0.1:8000 SIFT_TOKEN=... scripts/run-agent-watch.sh
#   AGENT_MEM_MAX=2G scripts/run-agent-watch.sh
#   systemctl --user status sift-agent-watch
#   journalctl --user -u sift-agent-watch -f          # (StandardOutput is a file, not the journal
#   tail -f "$LOG_FILE"                                #  by default — tail the log file instead)
#   systemctl --user stop sift-agent-watch             # the sanctioned way to actually stop it
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WATCH_DIR="${WATCH_DIR:-/home/quentinlatimier/Documents/Acme}"
SERVER="${SERVER:-http://127.0.0.1:8001}"
TOKEN="${SIFT_TOKEN:?set SIFT_TOKEN to the engine bearer token}"
CAP="${AGENT_MEM_MAX:-1G}" # hard ceiling only: exceed it -> cgroup OOM kills the agent, fast
LOG_FILE="${LOG_FILE:-$HOME/.local/state/condense/agent-watch.log}"

mkdir -p "$(dirname "$LOG_FILE")"

# Replace any prior instance cleanly (idempotent restart) — mirrors run-engine.sh.
systemctl --user stop sift-agent-watch 2>/dev/null || true
systemctl --user reset-failed sift-agent-watch 2>/dev/null || true

systemd-run --user \
  --unit=sift-agent-watch \
  --description="Condense ingestion agent (watch mode, memory-capped, OOM-isolated)" \
  --working-directory="$REPO" \
  -p MemoryMax="$CAP" \
  -p MemorySwapMax=0 \
  -p OOMPolicy=kill \
  -p Restart=always \
  -p RestartSec=3 \
  --collect \
  --setenv=PYTHONUNBUFFERED=1 \
  -p StandardOutput=append:"$LOG_FILE" \
  -p StandardError=append:"$LOG_FILE" \
  "$REPO/.venv/bin/python" -m agent.cli "$WATCH_DIR" \
    --server "$SERVER" \
    --token "$TOKEN" \
    --tenant default \
    --watch \
    --delete-removed

echo "sift-agent-watch started — watching $WATCH_DIR -> $SERVER"
echo "  MemoryMax=$CAP (no MemoryHigh) MemorySwapMax=0 Restart=always RestartSec=3"
echo "  log: $LOG_FILE (tail -f it — PYTHONUNBUFFERED=1 keeps it live, no minutes-long lag)"
echo "  status: systemctl --user status sift-agent-watch | stop: systemctl --user stop sift-agent-watch"
