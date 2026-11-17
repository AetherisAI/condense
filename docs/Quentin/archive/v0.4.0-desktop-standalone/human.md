# Desktop Standalone Launcher (Tauri) — Human Doc

> **≤500 words. Decision-first.** Fast-read companion to `machine.md`.

**Status:** COMPLETE — awaiting Quentin's review + merge word · **Branch:** `feat/desktop-standalone` · **Updated:** 2026-07-06 10:25

## What & why
Condense becomes an **LM-Studio-like standalone desktop app**: a small Tauri installer that on first run **downloads and runs its own backend** — PyInstaller engine bundle + `llama-server` with a local bge-m3 GGUF — takes an LLM API key (auto-detected), and lands in the chat. A settings mode-switch keeps it usable as a **pure client** against any Condense server. Ubuntu/macOS/Windows. The backend is also a **separable "API only" download** for Arthur's landing page.

## Key decisions
- **D60** — dual-mode launcher (local = provisions + supervises backend; client = v0.3.0 connect). Supersedes D53.
- **D61** — local embeddings via **llama-server sidecar + bge-m3 GGUF**; cosine vs production TEI > 0.999 — interchangeable.
- **D62** — backend **downloaded at first run** from a sha256-verified, config-driven manifest; ports 8801/8802; config JSON plaintext v1.
- **D63** — CI publishes `condense-server-<os>` as its own release asset = Arthur's "API only" download button.
- **D64** — local builds **in Docker**; install = AppImage + user-level `.desktop` + icon; `.deb` also produced.
- **D65–D67** — three real shipping blockers found by real-environment testing, all **fixed + retested same day**: a first-run mode-gate bug and an exit-cleanup gap (D65: `PR_SET_PDEATHSIG` + signal handler → zero orphans 3/3); a provisioning race the all-`file://` E2Es had masked (D66, caught by the first true public-URL download); and the pristine-install infinite spinner Quentin hit (D67: unhandled `provisioning_status` rejection when the default manifest URL 404s on the private repo — wizard no longer gates on the manifest fetch, embedded-manifest fallback with visible notice, reqwest timeouts, editable manifest URL in System ▸ Desktop).

## Ports / interfaces touched
- No `core/` changes. `packaging/` (Arthur's) touched, channel-flagged (updates 30–31). New seam: the Tauri command contract, pinned in `machine.md`.

## Risks / open questions
- macOS/Windows legs are CI-built, **not hardware-QA'd**. Chunker tokenizer needs one HF download on first ingest.
- Engine component downloads 404 honestly until a `v0.4.0` release exists — the test kit is the interim path.
- Real-desktop sanity check pending: quit the app → `pgrep -f 'sift-engine|llama-server'` (Xvfb showed a GDK crash on window-close, reaped by pdeathsig). Agent-sidecar hard-crash edge case logged in D65.

## Status / next action
- T1–T9 done: full E2E PASS (real wizard → provision → backend → cited Mistral answer; persistence + auto-start on relaunch), app installed in the GNOME app grid, **laptop test kit** at `~/condense-desktop-testkit.tar.gz` (`setup-test.sh` / `uninstall-test.sh`, no sudo) — full recipe + mac/win + client-mode notes in `desktop/TESTING.md`.
- Quentin's stale config/data dirs wiped — next launch is a pristine first-run on the fixed build.
- **No merge to main** — Quentin's word required.

## Pointer
- Full design, contract, tasks, log: [`./machine.md`](./machine.md)
