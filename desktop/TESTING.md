# Testing the Condense desktop app

This is the "how do I actually test this" doc for a human — laptop recipe first, then the
honest caveats about what is and isn't hardware-verified tonight.

## Linux: the one-file, one-script test kit

Because this repo is **private**, a laptop that has never cloned it cannot have the app fetch
the engine bundle from a GitHub release URL the way the real default manifest
(`desktop/provisioning/manifest.json`) does. `scripts/build-desktop-test-kit.sh` builds
`~/condense-desktop-testkit/` to work around exactly that: the engine tarball ships **inside**
the kit and is wired up via a `file://` manifest entry rendered at install time, while the
embedder (`llama-server`, public GitHub release) and the model (`bge-m3` GGUF, public
HuggingFace) keep their **real public URLs** — those two download over the network for real,
exercising the same code path a real user hits.

**On the dev machine:**
```bash
scripts/build-desktop-test-kit.sh
tar -czf ~/condense-desktop-testkit.tar.gz -C ~ condense-desktop-testkit
```
Copy `~/condense-desktop-testkit.tar.gz` to the laptop (USB stick, `scp`, cloud drive — one
file transfer).

**On the laptop:**
```bash
tar -xzf condense-desktop-testkit.tar.gz
cd condense-desktop-testkit
./setup-test.sh          # one script, no sudo
```
Then launch **Condense** from the app grid (or `~/.local/bin/Condense.AppImage` directly),
work through the first-run wizard, choose **Run locally**. Expect ~750MB of real downloads
(embedder + model); the engine itself is instant since it's local to the kit. Paste an LLM key
or hit Skip — without a key, Ask/chat answers fail but Find/search still works fully.
Uninstall any time with `./uninstall-test.sh` (prompts before deleting the data dir).

Full details, including exactly what's inside the kit and how `manifest.template.json` is
rendered: `scripts/test-kit/README.txt` (in-kit) and `scripts/build-desktop-test-kit.sh`
(source of truth for how the kit is assembled).

### Why this workaround exists (and when it goes away)
This is a repo-privacy workaround, not the shipped design. At public launch, once
`desktop/provisioning/manifest.json`'s `engine.targets.*.url` fields point at a real tagged
GitHub release (they're `sha256: null` placeholders until then), `AppConfig.manifest_url: null`
resolves straight to that repo-default manifest and **every** component — engine included —
downloads over the network like the embedder/model already do here. The test kit's `file://`
override and this whole doc's Linux section stop being necessary; only the CI-artifact
approach below (or the real installer, once released) will matter.

## macOS / Windows: CI artifacts only, not hardware-verified

No test-kit script exists for these yet. If the `build-desktop` GitHub Actions workflow is
green for this branch (check the Actions tab, `feat/desktop-standalone`), grab:
- The installer: artifact `condense-desktop-aarch64-apple-darwin` (`.dmg`) or
  `condense-desktop-x86_64-pc-windows-msvc` (`.exe`, NSIS).
- The engine bundle: artifact `condense-server-aarch64-apple-darwin` or
  `condense-server-x86_64-pc-windows-msvc`.

These builds are **unsigned** (v1, no code-signing/notarization) — expect Gatekeeper/SmartScreen
warnings, and **nobody has run either on real hardware yet**; `binary_path` inside their
manifest entries is inferred by analogy to the Linux layout, not verified (see
`desktop/provisioning/manifest.json`'s `_notes`). Repo-private + no macOS/Windows machine
available tonight means there's no equivalent of the Linux test kit for them — the private-repo
constraint doesn't even apply here since these are downloaded straight from the Actions run,
not built locally, so a manual **3-line** override is the only path to test with a locally
built engine bundle instead of a public release: open the app's `config.json`
(macOS: `~/Library/Application Support/ai.aetheris.condense/config.json`; Windows:
`%APPDATA%\ai.aetheris.condense\config.json`), set `"manifest_url"` to a `file://` (or `http://`
pointing at a temporary local file server) path to a hand-edited manifest whose engine `url`
points at the downloaded `condense-server-<triple>` artifact, then launch the app.

## Client-mode: zero-download test

Skip provisioning entirely — in the first-run wizard choose **Connect to a server** instead of
**Run locally**, point it at any reachable Condense API (base URL + token, e.g. this repo's own
`:8000` deployment with its ingest token), and hit Test. This is exactly v0.3.0's browser-client
behavior (D55) reused verbatim; no engine/embedder/model download happens at all, so it's the
fastest way to confirm the UI itself without touching provisioning.

## D65 real-desktop check (orphan processes on quit)

T7's containerized E2E (Xvfb, no real X server) found and fixed an orphan-process gap: neither
window-close nor `SIGTERM` was reaping the `sift-engine`/`llama-server` children. The fix
(`PR_SET_PDEATHSIG` on both spawns + a `SIGTERM`/`SIGINT` handler, `backend.rs`/`lib.rs`) was
verified 3/3 clean under Xvfb, but **never on a real desktop window manager** — the Xvfb runs
also hit a `GDK BadDrawable` X error on window-close that's suspected Xvfb/no-GPU-only and
stayed unconfirmed either way. On the laptop, after quitting the app normally (window close,
not `kill -9`), run:
```bash
pgrep -f 'sift-engine|llama-server'
```
It should print **nothing**. If it prints PIDs, that's a real regression worth reporting —
the fix was only proven inside a headless container.

## AppImage notes

The bundled AppImage is a type-2, statically-linked (`static-pie`) ELF — no bundled runtime
libs beyond what the binary itself needs, but **AppImages in general need FUSE** (`libfuse2` on
Ubuntu) to mount and run directly; some distros/minimal installs don't have it by default. If
double-clicking or running the AppImage does nothing or errors about FUSE, run it with:
```bash
~/.local/bin/Condense.AppImage --appimage-extract-and-run
```
which bypasses FUSE entirely (extracts to a temp dir and runs from there) — the exact mechanism
this WP's own container verification uses, since containers have no FUSE either.
