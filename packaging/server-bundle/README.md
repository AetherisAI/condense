# Condense server bundle — API only, no frontend

This is Condense's engine (the FastAPI API — ingest, search, `/v1/tools/*`, `/v1/answer`) frozen
into a self-contained download: no Python, no Docker, no `pip install`. It is the artifact
Arthur's landing page offers as the **"API only"** download, next to the full desktop app
installer (DECISIONS.md D63) — for anyone who wants Condense as a backend behind their own
frontend or another product (e.g. WorkyTalky) rather than the bundled chat UI. It is also
exactly what the desktop launcher itself downloads and supervises in local mode (D62) — one
build, two consumption paths, so the two can never drift apart.

## Quickstart

```bash
tar xzf condense-server-<target-triple>.tar.gz
cd condense-server-<target-triple>
cp env.example .env    # edit INGEST_TOKEN + your embed/LLM provider before real use
./run.sh                # Linux/macOS
# run.bat                 # Windows (best-effort, untested — see run.bat's own comment)
```

`run.sh` cd's into the bundle directory first (so the default `file:./data/sift.db` resolves
against the bundle root, not wherever you invoked it from), sources `.env` if present (else
`env.example` as-is, so it boots with zero setup for a quick try), exports every value, and
`exec`s `engine/sift-engine`. Ctrl-C stops it; there is no background/daemon mode built in here
— wrap it in your own process supervisor (systemd, a Docker `ENTRYPOINT`, `pm2`, ...) for anything
long-running.

Once it's up (default `http://127.0.0.1:8801`):
```bash
curl http://127.0.0.1:8801/healthz
curl http://127.0.0.1:8801/openapi.json | jq .info   # full API surface
```

## Layout

```
condense-server-<target-triple>/
├── engine/            the frozen FastAPI app (PyInstaller onedir, packaging/sift-engine.spec)
│   └── sift-engine    the executable — the whole engine, no interpreter needed on the host
├── bin/
│   └── sift-agent-cli one-shot / --watch headless ingestion client (packaging/sift-agent-cli.spec)
├── run.sh             quickstart launcher (Linux/macOS)
├── run.bat            quickstart launcher (Windows, best-effort — see its own header comment)
├── env.example         minimal config template — copy to .env and edit
└── README.md          this file
```

`bin/sift-agent-cli` talks to `engine/sift-engine` over HTTP exactly like any other client —
point it at this bundle's own `API_BIND:API_PORT` with `--token` set to your `INGEST_TOKEN`:
```bash
bin/sift-agent-cli /path/to/a/folder --server http://127.0.0.1:8801 --token <your INGEST_TOKEN>
```

## Config

`env.example` covers the minimum to get a working local instance (store path, embeddings
backend, LLM key, the auth token, bind/port). The full set of tunable knobs (rerank strategy,
chunk sizes, grounding mode, OCR, ...) is documented in the main repo's `.env.example` — every
`Settings` field (`src/sift/config.py`) can be set here the same way; unset ones just use the
engine's built-in default.

**Auth (CLAUDE.md §3):** the upload/ingest endpoint is not meant to face the public internet.
`API_BIND=127.0.0.1` (this bundle's default) keeps it local-only regardless of `INGEST_TOKEN`; if
you do bind it wider, treat `INGEST_TOKEN` as a real secret (`env.example` ships a `CHANGE-ME`
placeholder on purpose — the bundle refuses to start with no token at all, since `Settings`
requires one, but will happily start with the literal placeholder if you forget to change it).

## How this bundle is built

`scripts/build-server-bundle.sh` runs both PyInstaller specs (`packaging/sift-engine.spec`
onedir, `packaging/sift-agent-cli.spec` onefile) and assembles this directory's shape from the
source files under `packaging/server-bundle/` (this README, `run.sh`, `run.bat`, `env.example`)
plus the two frozen builds, then tars the result. See `packaging/README.md` for the engine
target's own packaging details (hidden imports, native-lib landmines, etc.) and CI
(`build-desktop.yml`, D63) for how the triple-named per-OS archives get published as release
assets.
