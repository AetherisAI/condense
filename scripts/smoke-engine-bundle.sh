#!/usr/bin/env bash
# Smoke-test the frozen `dist/sift-engine/sift-engine` PyInstaller onedir bundle (D62/D63):
# boots it in a memory-capped, OOM-isolated, detached systemd --user unit against a fully
# scratch env (a throwaway file: libsql DB, a dead embedder URL so ingest/search adapters never
# reach a real network dependency), waits for /healthz, and asserts a handful of black-box HTTP
# behaviors any real deployment (docker, the desktop launcher's local mode) depends on.
#
# WHY the same cgroup posture as scripts/run-engine.sh (DECISIONS.md D29/D34): MemoryMax +
# MemorySwapMax=0 + OOMScoreAdjust=1000, NO MemoryHigh (a soft-throttle band can livelock every
# thread in the cgroup without ever crossing MemoryMax — see run-engine.sh's comment) — a runaway
# frozen-binary boot must die fast and clean, never take this session down with it.
#
# Usage:
#   scripts/smoke-engine-bundle.sh                       # build must already exist at dist/sift-engine
#   BUNDLE_DIR=dist/sift-engine SMOKE_PORT=18801 scripts/smoke-engine-bundle.sh
set -uo pipefail  # NOT -e: every assertion below is hand-checked so a failure still stops the unit

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="${BUNDLE_DIR:-$REPO/dist/sift-engine}"
BUNDLE_EXE="$BUNDLE_DIR/sift-engine"
UNIT="${SMOKE_UNIT:-sift-engine-smoke}"
PORT="${SMOKE_PORT:-18801}"
CAP="${SMOKE_MEM_MAX:-2G}"
SCRATCH_DIR="$(mktemp -d /tmp/sift-engine-smoke.XXXXXX)"
DB_PATH="$SCRATCH_DIR/sift.db"

FAILED=0
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; FAILED=1; }

cleanup() {
  systemctl --user stop "$UNIT" >/dev/null 2>&1 || true
  systemctl --user reset-failed "$UNIT" >/dev/null 2>&1 || true
  rm -rf "$SCRATCH_DIR"
}
trap cleanup EXIT

if [[ ! -x "$BUNDLE_EXE" ]]; then
  fail "bundle executable not found or not executable: $BUNDLE_EXE (run pyinstaller packaging/sift-engine.spec first)"
  exit 1
fi

# Replace any stale instance cleanly (idempotent re-run), same pattern as run-engine.sh.
systemctl --user stop "$UNIT" >/dev/null 2>&1 || true
systemctl --user reset-failed "$UNIT" >/dev/null 2>&1 || true

echo "booting $BUNDLE_EXE on 127.0.0.1:$PORT (unit=$UNIT, MemoryMax=$CAP, scratch db=$DB_PATH)..."
BOOT_START=$(date +%s.%N)

systemd-run --user \
  --unit="$UNIT" \
  --description="sift-engine bundle smoke test" \
  --working-directory="$BUNDLE_DIR" \
  -p MemoryMax="$CAP" \
  -p MemorySwapMax=0 \
  -p OOMScoreAdjust=1000 \
  -p OOMPolicy=kill \
  --collect \
  -E TURSO_DATABASE_URL="file:$DB_PATH" \
  -E INGEST_TOKEN=smoke-token \
  -E EMBED_BASE_URL="http://127.0.0.1:1/v1" \
  -E EMBED_MODEL=bge-m3 \
  -E STORE_BACKEND=libsql \
  -E API_BIND=127.0.0.1 \
  -E API_PORT="$PORT" \
  "$BUNDLE_EXE" >/dev/null

# Poll /healthz instead of a fixed sleep — the bge-m3 tokenizer's first `from_pretrained` call
# fetches tokenizer.json from the HF Hub over the network (uncached on a clean box), so
# cold-boot-to-healthz varies with network latency, not just process start time.
HEALTHY=0
for _ in $(seq 1 60); do
  if [[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/healthz" 2>/dev/null)" == "200" ]]; then
    HEALTHY=1
    break
  fi
  if ! systemctl --user is-active --quiet "$UNIT"; then
    fail "unit exited before becoming healthy — see: journalctl --user -u $UNIT"
    break
  fi
  sleep 0.5
done
BOOT_END=$(date +%s.%N)
BOOT_S=$(awk -v a="$BOOT_START" -v b="$BOOT_END" 'BEGIN { printf "%.2f", b - a }')

if [[ "$HEALTHY" == "1" ]]; then
  pass "/healthz became 200 in ${BOOT_S}s (cold boot, incl. any first-run HF Hub tokenizer fetch)"
else
  fail "/healthz never returned 200 within 30s"
fi

if [[ "$HEALTHY" == "1" ]]; then
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/openapi.json")
  [[ "$code" == "200" ]] && pass "GET /openapi.json -> 200" || fail "GET /openapi.json -> $code (expected 200)"

  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$PORT/v1/tools/search" \
    -H 'Content-Type: application/json' -d '{"query":"smoke"}')
  [[ "$code" == "401" ]] && pass "POST /v1/tools/search WITHOUT bearer token -> 401" \
    || fail "POST /v1/tools/search WITHOUT bearer token -> $code (expected 401)"

  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$PORT/v1/tools/search" \
    -H 'Content-Type: application/json' -H 'Authorization: Bearer smoke-token' -d '{"query":"smoke"}')
  # The embedder URL is deliberately dead (127.0.0.1:1) — anything OTHER than 401 proves the
  # token was accepted; a 4xx/5xx from the dead downstream embedder is expected and fine.
  if [[ "$code" != "401" ]]; then
    pass "POST /v1/tools/search WITH bearer token -> $code (not 401 -- token accepted)"
  else
    fail "POST /v1/tools/search WITH bearer token -> 401 (token should have been accepted)"
  fi
fi

echo
if [[ "$FAILED" == "0" ]]; then
  echo "SMOKE RESULT: PASS"
else
  echo "SMOKE RESULT: FAIL"
fi
exit "$FAILED"
