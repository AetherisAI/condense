# Desktop Standalone Launcher (Tauri) — Human Doc

> **≤500 words. Decision-first.** Fast-read companion to `machine.md`.

**Status:** in-progress (autonomous overnight run, 2026-07-06) · **Branch:** `feat/desktop-standalone` · **Updated:** 2026-07-06 05:05

## What & why
Condense becomes an **LM-Studio-like standalone desktop app**: a small Tauri installer that on first run **downloads and runs its own backend** — PyInstaller engine bundle + `llama-server` with a local bge-m3 GGUF — takes an LLM API key (auto-detected), and lands in the chat. A settings mode-switch keeps the app usable as a **pure client** against any Condense server. Ubuntu/macOS/Windows. The backend is also a **separable "API only" download** for Arthur's landing page (engine + agent CLI, no UI).

## Key decisions
- **D60** — dual-mode launcher (local = app provisions + supervises backend; client = v0.3.0 connect behavior). Supersedes D53. New branch `feat/desktop-standalone`; old `feat/tauri-shell` archived.
- **D61** — local embeddings via **llama-server sidecar + bge-m3 GGUF**. Verified: cosine vs production TEI > 0.999 — interchangeable, engine adapter unchanged.
- **D62** — backend **downloaded at first run** from a sha256-verified, config-driven manifest; data in the OS app-data dir (`file:` libsql DB); local ports 8801/8802; config JSON plaintext v1 (keyring deferred).
- **D63** — CI publishes `condense-server-<os>` as its own release asset = Arthur's "API only" download button.
- **D64** — local builds **in Docker** (no webkit dev headers/sudo overnight); install = **AppImage + user-level .desktop + icon**; `.deb` also produced.
- **D65** — T7 real E2E found + fixed a shipping-blocker AND an exit-cleanup gap (both fixed same night; see below).

## Ports / interfaces touched
- No `core/` changes. `packaging/` (Arthur's) touches channel-flagged (update 30). New seam: the Tauri command contract (config/provision/backend/agent) pinned in `machine.md`.

## Risks / open questions
- macOS/Windows legs are CI-built but **not hardware-QA'd tonight**. Chunker tokenizer needs one HF download on first ingest.
- **D65 orphan gap — found, then FIXED same night** (round 2): T7 caught that neither window-close nor `SIGTERM` reaped `engine`/`llama-server`. Fixed belt-and-braces — kernel `PR_SET_PDEATHSIG` on both spawns (covers even SIGKILL/crash) + a SIGTERM/SIGINT handler running the normal cleanup. Retested: windowclose / SIGTERM / SIGKILL all end with **zero orphans (3/3)**. Remaining: the Xvfb-only GDK crash on window-close deserves a 10s real-desktop sanity check; the agent sidecar (plugin-spawned, no pdeathsig seam) would still orphan on a hard app crash while folder-watching — narrow exposure, follow-ups logged in D65.

## Status / next action
- Done: T1–T6, and now **T7 real E2E + install, PASS** — real AppImage under Xvfb, real xdotool-driven wizard, provisioned + started the backend from a local manifest, ran a full ingest→search→answer loop for real (1 Mistral call, correctly cited). Auto-start-on-relaunch (T7's Rust addition) and full data persistence across relaunch both verified.
- **T7 also found + fixed a shipping-blocker** (D65): the first-run wizard was broken for every real user — `backend_start`'s guard rejected the wizard's own deliberate call order. Fixed, rebuilt, verified; never caught by T2's mocked-Tauri Chrome QA.
- AppImage installed user-level (`~/.local/bin` + `.desktop` + icon, GNOME app grid). Host app dirs left absent — pristine first-run for Quentin.
- Now: T8 close-out. **No merge to main** — Quentin's word required.

## Pointer
- Full design, contract, tasks, log: [`./machine.md`](./machine.md)
