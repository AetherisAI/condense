# Desktop Standalone Launcher (Tauri) — Human Doc

> **≤500 words. Decision-first.** Fast-read companion to `machine.md`.

**Status:** in-progress (autonomous overnight run, 2026-07-06) · **Branch:** `feat/desktop-standalone` · **Updated:** 2026-07-06 02:30

## What & why
Condense becomes an **LM-Studio-like standalone desktop app**: a small Tauri installer that on first run **downloads and runs its own backend** — PyInstaller engine bundle + `llama-server` with a local bge-m3 GGUF — takes an LLM API key (Mistral/OpenAI/Anthropic auto-detected), and lands in the chat. A settings mode-switch keeps the app usable as a **pure client** against any Condense server. Ubuntu/macOS/Windows. Per Arthur's landing-page ask, the backend is a **separable "API only" download** (engine + agent CLI, no UI).

## Key decisions
- **D60** — dual-mode launcher (local = app provisions + supervises backend; client = v0.3.0 connect behavior). Supersedes D53 connect-first. New branch `feat/desktop-standalone`; old `feat/tauri-shell` plan archived on origin.
- **D61** — local embeddings via **llama-server sidecar + bge-m3 GGUF** (OpenAI-compat). **Verified tonight:** cosine vs production TEI > 0.999 on all probes — the two runtimes are interchangeable; engine adapter works unchanged (`EMBED_BASE_URL=http://127.0.0.1:8802/v1`). ~342MB RSS, 605MB download.
- **D62** — backend is **downloaded at first run** from a sha256-verified, config-driven manifest (installer stays small); data in the OS app-data dir (`file:` libsql DB); local ports 8801/8802; app config JSON holds mode/key/token (plaintext v1, keyring deferred).
- **D63** — CI publishes `condense-server-<os>` as its own release asset = Arthur's "API only" download button.
- **D64** — local builds happen **in Docker** (host lacks webkit dev headers; no sudo overnight); tonight's install = **AppImage + user-level .desktop + icon** (no sudo needed); a `.deb` is also produced.

## Ports / interfaces touched
- No `core/` changes. Engine untouched except possibly `Settings.api_port` (+ env parity).
- `packaging/` (Arthur's): new `sift-engine.spec` + entry — channel-flagged (update 30).
- New seam: the Tauri command contract (config/provision/backend/agent) pinned in `machine.md` — both the Rust and React tracks build against it.

## Risks / open questions
- Engine PyInstaller freeze (markitdown/tokenizers/libsql hidden imports) — riskiest packaging item; smoke-tested tonight.
- macOS/Windows legs are CI-built but **not hardware-QA'd tonight** (marked honestly).
- Chunker tokenizer downloads from HF on first ingest (needs internet once; `HF_HOME` in app data). Pre-fetch = later polish.
- RAM: 15G host, ~2.2G free with production up — heavy phases staggered; production restored + verified before morning.

## Status / next action
- Done: branch from main b8331c9; llama/GGUF validation (D61 proven); docker builder image in flight.
- Now: T1 engine bundle · T2 wizard UI · T3 CI (parallel) → T4 shell+icon → T5 Rust provisioning/supervision → T6 integrate → T7 E2E + user-level install → T8 close-out.
- **No merge to main** — Quentin's word required (morning review).

## Pointer
- Full design, contract, tasks, log: [`./machine.md`](./machine.md)
