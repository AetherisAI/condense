#!/usr/bin/env bash
# Launch the Condense engine from this bundle — the quickstart path for the "API only" download
# (D63): no Python, no Docker, no pip install. Usage: ./run.sh (from anywhere; it cd's here
# first so relative paths in .env, like the default file: DB, resolve against the bundle root
# and not whatever directory you happened to invoke this from).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f .env ]]; then
  ENV_FILE=.env
else
  ENV_FILE=env.example
  echo "no .env found — using env.example as-is (INGEST_TOKEN=CHANGE-ME; copy env.example to" >&2
  echo ".env and edit it before exposing this to anything but your own machine)" >&2
fi

set -a # export every var sourced below, same as a real deployment's .env
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

mkdir -p data # the default TURSO_DATABASE_URL (file:./data/sift.db) needs the dir to pre-exist

exec "$SCRIPT_DIR/engine/sift-engine"
