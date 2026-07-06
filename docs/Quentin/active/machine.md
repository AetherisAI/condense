# Desktop Standalone Launcher (Tauri) — Machine Doc

> Full design + plan + implementation record. Paired with `human.md` (never one without the other).

**Status:** COMPLETE — T1–T8 all done, awaiting Quentin's review + merge word · **Branch:** `feat/desktop-standalone` @ 8e4577d (from main @ b8331c9; supersedes the archived `feat/tauri-shell` plan @ ab5978b) · **Updated:** 2026-07-06 05:25

**Goal:** Ship Condense as an LM-Studio-like standalone desktop app: a small Tauri 2 installer that, on first run, **downloads and supervises its own backend** (PyInstaller engine bundle + `llama-server` + bge-m3 GGUF), takes an LLM API key (Mistral/OpenAI/Anthropic auto-detect), and lands the user in the chat — while remaining fully usable as a **pure client** (base URL + token) via a settings mode switch. Cross-OS (Ubuntu/macOS/Windows). The backend bundle is a **separable, individually downloadable artifact** so Arthur's landing page can offer "API only" installs.

**Architecture:** Two modes behind ONE seam (`AppConfig.mode`): **local** — the Rust shell provisions components from a config-driven download manifest into the app data dir and supervises three children (engine on `127.0.0.1:8801`, llama-server embeddings on `127.0.0.1:8802`, optional ingest agent), assembling the engine's env (file: libsql DB, local embedder URL, user's LLM key, generated bearer token); **client** — exactly v0.3.0's behavior (api.ts base URL + token, CORS already live, D55). One React codebase, `isTauri` gated. All ML inference stays external-over-HTTP (README rule intact — llama-server is a child *process*, not an in-app library; no torch anywhere).

**Tech stack:** Tauri 2.x (Rust ≥1.77) · @tauri-apps/plugin-shell + plugin-dialog · reqwest/rustls + tar/flate2/zip (provisioning) · PyInstaller onedir (engine) + onefile (agent, exists since v0.3.0) · llama.cpp prebuilt `llama-server` (official releases) · bge-m3 GGUF (Q8_0) · existing Vite 7 + React TS `web/` · GitHub Actions tauri-action matrix. **Local builds run in Docker** (`condense-tauri-builder` image) because this host lacks webkit2gtk dev headers and sudo is unavailable overnight (D64); the host runs the built bundles natively (runtime libs present).

## Global Constraints (every task)
- P1/P2: ports & adapters, config-driven; new engine config only via typed `Settings` + `.env.example` + compose parity (D45). Dependency rule unchanged; `tenant` threads through.
- Ownership: `packaging/` is **Arthur's** — every touch channel-flagged in `docs/channel/from-quentin.md`. `web/`, `desktop/` (new), `config.py`, CI are ours. No `core/` changes.
- RAM containment: every pytest/engine/pyinstaller/llama run RAM-capped in a transient systemd **service** (never nohup/--scope/MemoryHigh): `systemd-run --user --pipe --wait -p MemoryMax=2G -p MemorySwapMax=0 -p OOMScoreAdjust=1000 --working-directory="$PWD" --collect <cmd>` (3G for model loads). Docker builds: `--memory=5g -e CARGO_BUILD_JOBS=2`. Host has ~2.2G free — stagger heavy phases.
- Secrets: never print `.env` values; never `docker compose config`. The E2E may pipe `LLM_API_KEY` from `.env` into the app config without displaying it.
- Gates: Python → `ruff check` + `ruff format --check` + `pyright` (0 errors) + full `pytest` (RAM-capped); web → `npm run build` + `npm run lint` (zero warnings); Rust → `cargo check` (+ `cargo fmt --check`) in the builder image.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Push tracks to origin regularly. **No merge to main without Quentin's explicit word** — morning deliverable is the branch + installed app.
- Production stays up: engine :8000, web :5173, TEI :8082 docker, `sift-agent-watch`. Local-mode testing uses ports 8801/8802 (and 18xxx for scratch). If RAM forces it, TEI + agent-watch may be stopped TEMPORARILY and MUST be restored and verified before the run ends.

## Design

### Decisions (full rationale in DECISIONS.md)
- **D60** — WP scope = standalone dual-mode launcher; supersedes D53's connect-first. New branch `feat/desktop-standalone`; `feat/tauri-shell` archived on origin.
- **D61** — Local embeddings = `llama-server` sidecar serving bge-m3 GGUF over OpenAI-compat `/v1/embeddings`. TEI stays the server-deployment option. Cross-runtime cosine vs TEI validated empirically (scout).
- **D62** — Backend distribution = manifest-driven first-run download (engine = PyInstaller **onedir** bundle per OS, sha256-verified, config-driven manifest URL with baked default); data dir owns `file:` libsql DB; AppConfig JSON stores mode/ports/LLM key/ingest token (plaintext v1, keyring deferred); local ports **8801** (engine) / **8802** (embedder).
- **D63** — CI publishes `condense-server-<triple>` (engine + agent CLI + run script + .env template) as its OWN release asset = the "API only" download for Arthur's landing page.
- **D64** — Local Tauri builds in Docker; CI via tauri-action matrix; tonight's Ubuntu install = AppImage + user-level `.desktop` + icon (no sudo required); `.deb` also produced for a proper system install by Quentin.

### App directories (Tauri path API)
- Config: `<config_dir>/config.json` (Linux `~/.config/ai.aetheris.condense/`).
- Data: `<data_dir>` (Linux `~/.local/share/ai.aetheris.condense/`): `data/sift.db` · `runtime/engine/` (unpacked bundle) · `runtime/embedder/` (llama-server) · `models/*.gguf` · `hf-cache/` (HF_HOME for the chunker tokenizer) · `logs/`.

### AppConfig (config.json, schema 1)
```json
{ "schema": 1, "mode": "local|client|null", "engine_port": 8801, "embedder_port": 8802,
  "ingest_token": "<generated once>", "llm": {"base_url": "", "model": "", "api_key": ""},
  "manifest_url": null, "agent": {"paths": [], "delete_removed": false} }
```
`mode: null` ⇒ first run ⇒ SetupWizard. `manifest_url: null` ⇒ baked default (raw.githubusercontent.com main manifest); overridable (P2 — also how tonight's E2E points at locally built artifacts).

### Tauri command contract (Rust ⇄ TS — the seam both tracks build against)
```
app_config_get() -> AppConfig
app_config_set(config: AppConfig) -> Result<AppConfig, String>
provisioning_status() -> { components: [{id: "engine"|"embedder"|"model", name, installed: bool, version?, size_bytes?}], manifest_url }
provision_start(ids: string[]) -> Result<(), String>   // async; events below
provision_cancel() -> Result<(), String>
backend_start() -> Result<(), String>                   // embedder first, then engine; health-polls
backend_stop() -> Result<(), String>
backend_status() -> { mode, engine: {state, port, pid?}, embedder: {state, port, pid?} }  // state: "stopped"|"starting"|"running"|"error:<msg>"
agent_start(cfg: {paths: string[], delete_removed: bool}) -> Result<(), String>
agent_stop() -> Result<(), String>
agent_status() -> { running: bool, user_stopped: bool, restarts: number }
```
Events: `provision-progress {id, phase: "downloading"|"verifying"|"unpacking"|"done", downloaded, total}` · `provision-error {id, error}` · `backend-state {component, state, detail?}` · `agent-event {line}` (NDJSON passthrough) · `agent-terminated {code, will_restart}`.

### Engine env assembled by the launcher (local mode)
`STORE_BACKEND=libsql · TURSO_DATABASE_URL=file:<data>/data/sift.db · EMBED_BASE_URL=http://127.0.0.1:8802/v1 · EMBED_MODEL=bge-m3 · EMBED_DIM=1024 · RERANK_STRATEGY=llm · LLM_BASE_URL/LLM_MODEL/LLM_API_KEY=<AppConfig.llm> · INGEST_TOKEN=<AppConfig.ingest_token> · API_BIND=127.0.0.1 · API_PORT=8801 · HF_HOME=<data>/hf-cache` (+ existing defaults). llama-server: `llama-server -m <gguf> --embedding --pooling <scout-verified> -c 8192 --host 127.0.0.1 --port 8802`.

### Provisioning manifest (`desktop/provisioning/manifest.json`, schema 1)
```json
{ "schema": 1,
  "engine":   {"version": "0.4.0", "targets": {"<triple>": {"url", "sha256", "size"}}},
  "embedder": {"name": "llama-server", "build": "<bNNNN>", "targets": {"<triple>": {"url", "sha256", "size", "binary_path"}}},
  "model":    {"name": "bge-m3", "file": "bge-m3-Q8_0.gguf", "url", "sha256", "size"} }
```
llama.cpp + HF URLs are real today; engine URLs point at our release naming (`condense-server-<triple>.tar.gz`/`.zip`) and go live at the first tagged release. Web wizard shows honest sizes from the manifest.

### Web (Tauri-gated, one codebase)
- `web/src/platform.ts`: `isTauri` = `'__TAURI_INTERNALS__' in window` OR localStorage `forceTauri==='1'` (dev/QA seam).
- `web/src/tauri.ts`: typed wrappers for the command contract; when `forceTauri` without real Tauri → deterministic in-memory mocks (lets the coordinator QA the wizard in Chrome).
- `web/src/SetupWizard.tsx`: full-screen first-run overlay (design language: existing tokens, mouse-follow background stays). Step 1 choose **Run locally (recommended)** | **Connect to a server**. Local → component list with real sizes + LLM key input (reuse `provider.ts` auto-detect; skippable "add later") → progress (logo-as-status, `provision-progress`) → `backend_start` → chat. Client → base URL + token + Test (`/healthz`) → save → chat.
- `web/src/SystemMenu.tsx`: new Tauri-only **Desktop** section on top: mode switch (local ⇄ client), backend status + Start/Stop, component versions + re-download; **Folder agent** section upgrades from download links to live controls in Tauri (folder picker via plugin-dialog, Start/Stop, status line, failures list, log tail — v0.3.0 `--json` events).
- Local mode wiring: apiBase → `http://127.0.0.1:<engine_port>`, token → `ingest_token`, both auto-set from AppConfig (user never types them).

## Plan (tracks = one Sonnet agent each; coordinator QAs between)

### T0: branch setup — DONE 02:26 (`feat/desktop-standalone` @ b8331c9 pushed; `feat/tauri-shell` archived untouched)
### Scout A: llama-server + bge-m3 validation — IN FLIGHT (assets → `~/.cache/condense-desktop-assets/`; verifies /v1/embeddings dim=1024, pooling flags, TEI-vs-llama cosine, engine adapter path-join; collects mac/win asset URLs)
### Scout B: Docker builder image — IN FLIGHT (`condense-tauri-builder`; proves an end-to-end throwaway Tauri build → deb+AppImage inside Docker, non-root, RAM-capped)

### T1: engine bundle + server-only artifact (branch `feat/desktop-engine-bundle`)
**Files:** Create `packaging/sift_engine_entry.py`, `packaging/sift-engine.spec` (onedir), `packaging/server-bundle/` (README.md, run.sh, run.bat, env.example), `scripts/build-server-bundle.sh`; Modify `packaging/README.md`, `src/sift/config.py` (+`api_port` if absent) + `.env.example` + compose parity.
- [x] Entry: `from sift.api.main import app; uvicorn.run(app, host=settings.api_bind, port=settings.api_port)`; hidden imports for tiktoken_ext, markitdown converters, libsql + tokenizers native libs.
- [x] Local build (RAM-capped) → `dist/sift-engine/`; smoke: boots with `TURSO_DATABASE_URL=file:/tmp-scratch/sift.db`, `/healthz` 200, `/docs` served, ingest+search of one txt with FAKE embedder... (real-embedder E2E happens in T7 with llama-server).
- [x] `build-server-bundle.sh` → `condense-server-x86_64-unknown-linux-gnu.tar.gz` (bin layout per D63: `engine/`, `bin/sift-agent-cli`, `run.sh`, `env.example`, `README.md`).
- [x] Gates + commit + channel-flag (packaging/ = Arthur's).

### T2: setup wizard + desktop settings UI (branch `feat/desktop-wizard-ui`)
**Files:** Create `web/src/platform.ts`, `web/src/tauri.ts`, `web/src/SetupWizard.tsx`; Modify `web/src/App.tsx`, `web/src/SystemMenu.tsx`, `web/src/App.css` (+ index.css tokens only if strictly needed).
- [x] Contract types + mocks (`tauri.ts`) exactly per the command contract above.
- [x] Wizard + Desktop settings section + agent live controls, all behind `isTauri`; browser bundle byte-behavior unchanged (`forceTauri` off ⇒ zero new UI).
- [x] Gates (`npm run build`+`lint` zero warnings); coordinator Chrome QA on :5176 with `forceTauri` mocks; commit.

### T3: CI (branch `feat/desktop-ci`)
**Files:** Create `.github/workflows/build-desktop.yml`.
- [x] Job `server-bundle` (matrix ubuntu-22.04/macos-latest/windows-latest): pyinstaller engine + agent → `condense-server-<triple>` artifact; on `v*` tag → release asset.
- [x] Job `desktop` (same matrix): agent binary → `desktop/src-tauri/binaries/<triple>`, web build, tauri-action → deb/AppImage/dmg/nsis artifacts (+release on tag). Unsigned v1.
- [x] Triggers: `workflow_dispatch` + push to `feat/desktop-standalone` (temporary, removed at merge) + `v*` tags. Commit.

### T4: Tauri scaffold + icon + Linux bundle (trunk worktree, after Scout B)
**Files:** Create `desktop/package.json`, `desktop/src-tauri/{tauri.conf.json,Cargo.toml,build.rs,src/main.rs,src/lib.rs,capabilities/default.json,icons/*}`, `desktop/Dockerfile.builder` (from Scout B), `desktop/README.md`, `desktop/provisioning/manifest.json`; Modify `.gitignore`.
- [x] Icon: brand SVG → 1024 PNG → `tauri icon`; coordinator visually approves the PNG.
- [x] `tauri.conf.json`: identifier `ai.aetheris.condense`, productName `Condense`, frontendDist `../../web/dist`, externalBin `binaries/sift-agent-cli`, targets deb+appimage (linux).
- [x] Docker build (image from Scout B) → deb + AppImage that open the current workbench UI. `cargo check`/`fmt` clean. Commit.

### T5: Rust provisioning + supervision (trunk, after T4; uses Scout A facts)
**Files:** Modify `desktop/src-tauri/src/lib.rs` (split modules: `config.rs`, `provisioning.rs`, `backend.rs`, `agent.rs`), `capabilities/default.json`, `Cargo.toml` (reqwest/rustls, tar, flate2, zip, sha2, serde).
- [x] AppConfig load/save + full command contract + events; download w/ resume-less retry, sha256 verify, unpack; backend lifecycle (embedder→engine order, health poll `/healthz`, kill on exit via RunEvent::ExitRequested, bounded restart); agent supervision (v0.3.0 `--json` sidecar).
- [x] `cargo check` + docker rebuild → new AppImage. Commit.

### T6: integration (trunk)
- [x] Merge T1/T2/T3 branches into `feat/desktop-standalone`; full Python+web gates on the merged tree; docker rebuild. Commit + push.

### T7: E2E + install QA on this machine (the morning deliverable)
- [x] Local manifest override → locally built engine bundle + scout's llama-server/GGUF; first-run wizard → local mode → provisions → backend up (8801/8802) → LLM key injected from `.env` (never printed) → chat answers + ingest works + Find works.
- [x] User-level install: AppImage → `~/.local/bin` + `.desktop` + icon in `~/.local/share` → visible in GNOME app grid. Native window screenshot via Xvfb (builder image) for coordinator visual pass. No orphans after quit (pgrep). Relaunch restores config/state.
- [x] Restore any temporarily-stopped production services; verify engine :8000 + web :5173 + TEI + agent-watch all healthy.

### T8: close-out (coordinator)
- [x] DECISIONS.md log entries updated with outcomes; human.md status; channel update 30→31 (Arthur: API-only artifact + landing-page download shapes); push; memory handoff note. NO main merge (Quentin's word required).

### T9: laptop test kit (repo-private workaround) + real-public-URL verification (D66)
- [x] `scripts/build-desktop-test-kit.sh` + `scripts/test-kit/*` + `desktop/TESTING.md`: one-tarball, one-script kit for testing on a machine without repo access — engine ships as a local `file://` manifest entry, embedder+model keep real public URLs.
- [x] Built the kit, verified end-to-end in a fresh-HOME container: found + fixed a real provisioning-race bug in `SetupWizard.tsx` (see D66) that every prior all-`file://` E2E had masked; rebuilt, refreshed both AppImage copies, re-verified clean (real ~620MB public download, live progress UI, zero manual intervention, workbench reached, `/healthz`+`/health` both 200).
- [x] `uninstall-test.sh` verified (full removal + separate `.bak`-restore test). Production confirmed healthy throughout; no stray processes on the host.

## Test strategy
- Python: existing suite (500 green baseline) + new tests only where seams exist (config `api_port`); engine-bundle smoke is a scripted boot test, not pytest (frozen binary ≠ venv).
- Web: build+lint gates + coordinator Chrome QA (mocked Tauri layer) — no new test infra (repo convention).
- Rust: `cargo check`/`fmt` + live E2E (T7); no Rust unit-test infra in v1 (logged as debt).
- Cross-runtime embeddings: empirical cosine TEI↔llama-server (Scout A) — the compatibility fact gets recorded here + DECISIONS.

## Implementation log
| Date | Commit | Change |
|------|--------|--------|
| 2026-07-06 02:26 | — | `feat/desktop-standalone` branched from main b8331c9; scouts A (llama/GGUF) + B (docker builder) dispatched |
| 2026-07-06 ~03:30 | 542e779/424a419/a7fd361/756d374 | T3 CI + T1 engine bundle (250MB onedir, 128MB tar.gz, smoke 4/4) + T2 wizard UI (QA'd in Chrome, 3 design fixes) + T4 scaffold/icon/manifest/Linux bundle (deb 14.8MB, AppImage 89MB, xvfb boot-smoke OK) |
| 2026-07-06 | 8a4f973 | T5 Rust provisioning + backend/agent supervision (this entry) |
| 2026-07-06 | c26f98f/1c855b5/d0ccb03/c643e9d/2916464 | T6 integration: T1+T2+T3 merged, agent server/token wiring, full gates green (pytest 503, web clean, cargo clean), bundle rebuilt |
| 2026-07-06 | bc748cb | T0/T7: auto-start local backend on launch when already provisioned (`lib.rs` setup hook + `provisioning::all_installed`); `backend_start`'s already-starting/running guard changed from error to silent no-op. `cargo fmt`/`check` clean, full `tauri build` green (AppImage 91.5MB, deb 17.5MB). |
| 2026-07-06 | 9258a85 | T7: **real E2E found a shipping-blocker on the FIRST real wizard run** — `backend_start`'s mode guard required `cfg.mode == Some("local")` already, but the wizard deliberately calls `backend_start` BEFORE persisting `mode:'local'` (only commits once the backend is confirmed healthy). Fixed to reject only explicit `"client"` mode (D65). Rebuilt, re-verified — see next row. |
| 2026-07-06 | — (E2E run, no further code changes) | **T7 containerized real E2E, full result:** `condense-tauri-builder` image + Xvfb `:99` + `xdotool` (installed at runtime, container run as root) + a local `manifest-local.json` (`file://` URLs: engine = T1's real artifact fresh-sha256'd `9e3e6642a3…`, embedder/model = repo manifest's already-verified b9878/bge-m3 assets) + a pre-seeded `config.json` (mode:null, ports 8801/8802, generated ingest_token, `llm` piped from prod `.env` — base_url/model logged, api_key never printed). Real wizard walkthrough (screenshots `e2e-01-choice.png`…`e2e-06-relaunch.png`, `~/.cache/condense-desktop-assets/e2e/shots/`): Run locally → checklist showed real sizes (127.5/15.1/605.2 MB) → Download & start → provisioned all 3 in ~36s (file:// copies) → embedder+engine started for real (llama-server RSS ~752MB, sift-engine RSS ~463MB) → wizard closed into the workbench. Verified via curl: `/healthz` 200, `/health` 200, `POST /v1/documents` indexed a test fact, `POST /v1/tools/search` retrieved it (real llama-server embeddings + file libsql), ONE `POST /v1/answer` (`grounding:"strict"`) call to real Mistral answered correctly with `sources:[{"path":"zephyrium.txt","page":1}]` and `from_general_knowledge:false` (1/3 LLM-call budget used). **Lifecycle QA:** relaunch with `mode:"local"` already persisted → T0's auto-start brought engine+embedder up with ZERO clicks, `/healthz` 200 immediately, previously-ingested doc still searchable (full data-dir persistence confirmed). **Orphan check: FAILED, flagged (D65, not fixed tonight)** — neither a clean single-window `xdotool windowclose` (confirmed via `WM_CLASS` = `"Condense"`) nor a plain `SIGTERM` to the main process runs the `RunEvent`-based `kill_backend`/`kill_agent` cleanup; `engine`/`llama-server` are left running as orphans in both cases (reproduced twice each, on two separate app instances). Window-close additionally hit a fatal GDK `BadDrawable` X error (assessed likely-Xvfb/no-GPU-only, unconfirmed on a real desktop); the `SIGTERM` gap is platform-independent (no signal handler installed). All orphans manually cleaned up before container teardown; host confirmed clean throughout (never touched). |
| 2026-07-06 | — | T7 install: AppImage → `~/.local/bin/Condense.AppImage` (chmod +x); icon → `~/.local/share/icons/hicolor/{32x32,128x128,256x256}/apps/condense.png`; `~/.local/share/applications/condense.desktop` (`StartupWMClass=Condense`, confirmed empirically via `xprop WM_CLASS` on a throwaway container launch). `desktop-file-validate` passed (one non-fatal hint about multi-category `Categories=`); `update-desktop-database` OK; `gtk-update-icon-cache` failed ("No theme index file" — expected/harmless for a user-local hicolor override, no system `index.theme` present; ignored per instructions). Host `~/.config/ai.aetheris.condense` and `~/.local/share/ai.aetheris.condense` left ABSENT (no host-display smoke test run — `DISPLAY=:1` is the owner's live GNOME session, judged too intrusive to pop a window on while asleep, and the container E2E already proves function) — pristine first-run wizard preserved for the morning. Production (`:8000`/`:5173`/`:8082`/`sift-agent-watch`) never stopped, confirmed healthy throughout and at sign-off. |
| 2026-07-06 | (T7 round 2) | **Exit-orphan gap FIXED belt-and-braces, coordinator-directed (D65 amendment).** `backend.rs`: `set_parent_death_signal()` — `pre_exec` + `prctl(PR_SET_PDEATHSIG, SIGTERM)` on both engine and embedder spawns (`cfg(target_os="linux")`; `libc` dep scoped to that target so mac/win builds still compile — kqueue/Job-object equivalents = later WP, in-code comment). `lib.rs`: `#[cfg(unix)]` tokio-`signal` task (SIGTERM+SIGINT → `kill_backend`+`kill_agent` → `app_handle.exit(0)`); RunEvent cleanup unchanged (double-run idempotent). Gates green (`cargo fmt`/`check` + full `tauri build`). **Lifecycle retest, new AppImage, fresh healthy launch each: (a) windowclose → GDK BadDrawable still crashes under Xvfb but pdeathsig reaps both children — pgrep EMPTY; (b) SIGTERM → clean handler exit (no crash in app log) — pgrep EMPTY; (c) SIGKILL -9 → pgrep EMPTY, engine log shows graceful uvicorn shutdown from pdeathsig's SIGTERM. 3/3 zero orphans.** Installed copy refreshed, sha256 `3e42c92d07db…` verified identical at `~/.local/bin` and the bundle path; host config/data dirs still absent. Honest caveat (D65): the agent sidecar (spawned via `tauri_plugin_shell`, no `pre_exec` seam) is reaped on every clean/signalled quit but would still be orphaned by SIGKILL/hard-crash while a folder watch is running — verified by reading `agent/cli.py::_watch` (blocks on `stop_event.wait()`; a BrokenPipe on parent death raises only in the Watcher callback thread). Two candidate fixes logged in D65 for a later WP. |
| 2026-07-06 | (T9, test kit) | **T9: laptop test kit built + verified end-to-end (D66).** New `scripts/build-desktop-test-kit.sh` + `scripts/test-kit/{setup-test.sh,uninstall-test.sh,README.txt,manifest.template.json}` + `desktop/TESTING.md`: assembles `~/condense-desktop-testkit/` (215MB, tar.gz 214MB) so the private repo's engine bundle ships as a local `file://` manifest entry while the embedder (llama.cpp GitHub release) + model (bge-m3 HuggingFace) keep their real public URLs verbatim. **Containerized verify (fresh HOME, `condense-tauri-builder` image) found a real bug on the FIRST attempt with real public URLs** (every prior E2E had used an all-`file://` manifest, masking it): `SetupWizard.tsx`'s 'provisioning' step treated the fire-and-forget `provision_start` Tauri command's (instant) return as "provisioning done" and immediately called `backend_start`, which failed with "embedder binary not found" because the real download was still in flight — a manual Retry always "fixed" it once the download had actually finished, confirming a race, not a download failure. **Fixed** (`SetupWizard.tsx` only, no Rust change needed): the 'provisioning' effect now waits for every requested id to reach a terminal `provision-progress`(`done`)/`provision-error` state before advancing to 'starting'. Rebuilt in the same Docker builder (~7min, cold cargo cache this run), refreshed both the kit's AppImage and `~/.local/bin/Condense.AppImage` (sha256 `aba46dbb7405…`), re-verified in a fresh container: real ~620MB public download completed with live progress UI the whole time (screenshots `progress-01`…`progress-04`), zero manual intervention, workbench reached, `curl` confirmed engine `/healthz` 200 (`:8801`) + llama-server `/health` 200 (`:8802`). Window-close reproduced the already-known D65 Xvfb-only GDK crash with pdeathsig still reaping both children (zombie state — the container's own `sleep infinity` PID 1 not reaping is a harness artifact, not an app regression). `uninstall-test.sh` verified to fully remove the AppImage/`.desktop`/icon/config/data dirs, plus a separate synthetic test of its `config.json.bak` restore path (byte-identical restore). Web gates clean (`tsc -b && vite build`, `oxlint`). Production (`:8000`/`:5173`/`:8082`/`sift-agent-watch`) confirmed healthy throughout and at sign-off; no stray `sift-engine`/`llama-server` on the host. |

## Decisions
- D60–D66 (this WP) — see `docs/Quentin/DECISIONS.md`.

## Changelog
- (pending) v0.4.0 — standalone desktop launcher
