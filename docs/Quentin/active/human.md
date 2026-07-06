# Desktop Standalone Launcher (Tauri) — Human Doc

> **≤500 words. Decision-first.** Fast-read companion to `machine.md`.

**Status:** COMPLETE — awaiting Quentin's review + merge word · **Branch:** `feat/desktop-standalone` · **Updated:** 2026-07-06 09:45

## What & why
Condense becomes an **LM-Studio-like standalone desktop app**: a small Tauri installer that on first run **downloads and runs its own backend** — PyInstaller engine bundle + `llama-server` with a local bge-m3 GGUF — takes an LLM API key (auto-detected), and lands in the chat. A settings mode-switch keeps the app usable as a **pure client** against any Condense server. Ubuntu/macOS/Windows. The backend is also a **separable "API only" download** for Arthur's landing page.

## Key decisions
- **D60** — dual-mode launcher (local = provisions + supervises backend; client = v0.3.0 connect behavior). Supersedes D53.
- **D61** — local embeddings via **llama-server sidecar + bge-m3 GGUF**. Verified: cosine vs production TEI > 0.999.
- **D62** — backend **downloaded at first run** from a sha256-verified, config-driven manifest; local ports 8801/8802; config JSON plaintext v1.
- **D63** — CI publishes `condense-server-<os>` as its own release asset = Arthur's "API only" download button.
- **D64** — local builds **in Docker**; install = **AppImage + user-level .desktop + icon**; `.deb` also produced.
- **D65** — T7 real E2E found + fixed a first-run shipping-blocker AND an exit-cleanup gap (both fixed same night).
- **D66** — T9's laptop test kit (repo-private workaround: engine via local `file://`, embedder+model on real public URLs) found + fixed ANOTHER shipping-blocker: a provisioning race in `SetupWizard.tsx` that every prior all-`file://` E2E had masked.

## Ports / interfaces touched
- No `core/` changes. `packaging/` (Arthur's) touched, channel-flagged. New seam: the Tauri command contract, pinned in `machine.md`.

## Risks / open questions
- macOS/Windows legs are CI-built but **not hardware-QA'd**. Chunker tokenizer needs one HF download on first ingest.
- **D65 orphan gap — FIXED**: kernel `PR_SET_PDEATHSIG` + a SIGTERM/SIGINT handler; windowclose/SIGTERM/SIGKILL retested to zero orphans. Remaining: a 10s real-desktop sanity check on the Xvfb-only GDK crash; agent sidecar narrow-case exposure logged in D65.
- **D66 provisioning race — FIXED**: the wizard called `backend_start` the instant the fire-and-forget `provision_start` command returned, not once downloads finished, so any real download raced it (masked until now by all-`file://` E2Es). Fixed in `SetupWizard.tsx` alone; re-verified clean with real ~620MB public downloads.

## Status / next action
- T1–T7 done (real E2E + install PASS, D65's blocker + orphan gap fixed and retested). T8 close-out done. **No merge to main** — Quentin's word required.
- **T9 (new): laptop test kit built + verified** (D66) — `~/condense-desktop-testkit.tar.gz` + `./setup-test.sh` (one file, one script, no sudo) is the whole recipe for the work laptop; found + fixed D66 along the way; `uninstall-test.sh` also verified. Caveats (macOS/Windows CI-only, client-mode zero-download test, D65 pgrep check): `desktop/TESTING.md`.
- Morning checklist: (1) copy the tar.gz to the laptop, `tar -xzf`, `./setup-test.sh`, launch **Condense** → Run locally; (2) after quitting, `pgrep -f 'sift-engine|llama-server'` should be empty; (3) `sudo dpkg -i` the `.deb` later if preferred over the AppImage here.

## Pointer
- Full design, contract, tasks, log: [`./machine.md`](./machine.md)
