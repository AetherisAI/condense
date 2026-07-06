# Packaging — three PyInstaller targets

Three specs freeze two different packages for three different consumers — they are **not**
interchangeable, so pick the row that matches what you're building. The first two freeze `agent/`
(DECISIONS.md D54); the third (D62/D63, added by the `feat/desktop-standalone` WP's engine track —
CROSS-BOUNDARY touch on this dir, flagged in `docs/channel/from-quentin.md` update 30) freezes
`sift` itself — the opposite of the first two's "never import the engine/ML stack" rule:

| Target | Spec | Shape | Consumer |
|--------|------|-------|----------|
| Desktop GUI download | `sift-agent.spec` | onedir, `console=False`, own Tkinter window, no stdout | a human double-clicking a download (this file, below) |
| Headless CLI sidecar | `sift-agent-cli.spec` | **onefile**, **`console=True`** | Tauri desktop shell (`bundle.externalBin`) — see "Second target" below — or any script/systemd unit |
| **The FastAPI engine** | `sift-engine.spec` | **onedir**, `console=True` | the desktop launcher's local mode (downloads + supervises it, D62) and the standalone "API only" server bundle (D63) — see "Target 3" below |

## Target 1: the Tkinter desktop download

Builds the `agent/` Tkinter watcher into self-contained, ready-to-run downloads (no Python/pip on
the user's machine) and drops them into `web/public/downloads/`, where the web UI's **Agent** panel
links to them (served same-origin by Vite in dev / nginx in prod).

| OS | Artifact | How the user runs it |
|----|----------|----------------------|
| macOS | `sift-agent-macos.zip` (a `.app`) | unzip → right-click **Open** (unsigned, first launch only) |
| Ubuntu/Linux | `sift-agent-ubuntu.AppImage` | `chmod +x` → run — no install |
| Windows | — | coming soon |

## Prerequisites
- **macOS build:** the project `.venv` (Python 3.12) with Tkinter — `brew install python-tk@3.12` if `python -c "import tkinter"` fails. PyInstaller is auto-installed by the script.
- **Linux build:** **Docker Desktop running** (PyInstaller can't cross-compile, so the Ubuntu binary is built in an `ubuntu:24.04` container). First run downloads the base image + `appimagetool`.

## Build
```bash
# both (mac locally + linux in Docker)
bash packaging/build_all.sh

# or individually
bash packaging/build_macos.sh
bash packaging/build_linux.sh
```

Outputs land in `web/public/downloads/` (gitignored — never committed; ~20–40 MB each).

## How it works
- `sift-agent.spec` — one PyInstaller spec, branches on `sys.platform` (macOS → `.app` BUNDLE; Linux → onedir). `sift_agent_entry.py` is the entry (`from agent.app import main`). The agent never imports `sift`, so the engine/ML stack is excluded → small bundle.
- `build_macos.sh` — PyInstaller → `dist/Sift Agent.app` → `ditto` zip.
- `Dockerfile.linux` + `build_linux_in_container.sh` — PyInstaller onedir → AppDir (AppRun + `.desktop` + a stdlib-generated icon) → `appimagetool --appimage-extract-and-run` (no FUSE needed in-container).

## Windows & CI builds (`.github/workflows/build-agent.yml`)
PyInstaller can't cross-compile, and there's no local Windows environment — so **Windows** (and native **x86_64 Linux**, which the arm64-on-Colima local build can't produce) are built in CI. The `build-agent` workflow runs the *same* `sift-agent.spec` on `windows-latest` / `macos-latest` / `ubuntu-latest`, does an import + best-effort GUI-launch smoke, and uploads each artifact. On a `v*` **tag** it attaches them to a **GitHub Release**; the web UI's Windows row links to `releases/latest/download/sift-agent-windows.zip`.
- Trigger manually: `gh workflow run build-agent.yml --ref <branch>` (build smoke, no release).
- Publish: push a `v*` tag → the `release` job creates/updates the Release with all three artifacts.
- **GUI launch is not click-tested** — CI has no reliable desktop; the launch smoke is best-effort (`continue-on-error`). Real GUI verification needs a human on each OS.

## Notes / caveats
- **Unsigned macOS app** → Gatekeeper blocks double-click on first launch; right-click → Open (the Agent panel shows this). Future: `codesign` + notarize.
- **AppImage fallback:** if `appimagetool` misbehaves in your Docker setup, tar the onedir (`dist/sift-agent/`) as `sift-agent-ubuntu.tar.gz` instead and point the UI link at it.
- Artifacts are versioned by rebuilding, not committed. For public distribution, consider attaching them to a GitHub Release instead.

## Target 2: the headless CLI sidecar (`sift-agent-cli.spec`)

`agent/cli.py` (`--json` NDJSON events + SIGTERM handling, D54) frozen as a single-file, console
binary — the shape a supervising process (Tauri's `plugin-shell` sidecar) needs: a real,
line-readable stdout, one file, no window. It is **not** a replacement for Target 1 — the Tkinter
build has no stdout worth reading and isn't supervisable; this build has no window and isn't
meant to be double-clicked.

### Build
```bash
pyinstaller packaging/sift-agent-cli.spec
# → dist/sift-agent-cli  (single executable; add .exe on Windows)
```
Same excludes as `sift-agent.spec` (`sift`, `torch`, `numpy`, `markitdown`, `tokenizers`,
`libsql` — the agent never imports the engine/ML stack) and the same per-OS `watchdog` observer
hidden-import, since `--watch` uses it exactly like the Tkinter app does. Entry point is
`sift_agent_cli_entry.py` (`from agent.cli import main`), mirroring `sift_agent_entry.py`'s
convention.

### Smoke-test after a build
```bash
./dist/sift-agent-cli --help                                    # exit 0
./dist/sift-agent-cli --json --dry-run /some/scratch/dir --server http://x --token y   # valid NDJSON
```
A `--watch` run should also stop cleanly (exit 0) on SIGTERM, not just Ctrl-C — that's the whole
point of D54's SIGTERM handler; a Tauri `kill()` never sends SIGINT.

### Tauri target-triple naming (`bundle.externalBin`)
Tauri expects each platform's sidecar binary named `<name>-<target-triple>[.exe]` — e.g.
```
sift-agent-cli-x86_64-unknown-linux-gnu
sift-agent-cli-aarch64-apple-darwin
sift-agent-cli-x86_64-pc-windows-msvc.exe
```
so after building on each OS, rename the raw `dist/sift-agent-cli` output before dropping it into
`desktop/src-tauri/binaries/` (see the `desktop/` WP's CI, `build-desktop.yml`):
`mv dist/sift-agent-cli dist/sift-agent-cli-$(rustc --print host-tuple)` (append `.exe` on
Windows). `rustc --print host-tuple` is the simplest way to get the exact triple Tauri expects
for the machine currently building.

## Target 3: the frozen engine (`sift-engine.spec`) + the standalone server bundle

`sift-engine.spec` freezes the FastAPI app (`src/sift/api/main.py`'s `app` object) plus its full
runtime dependency stack — store (libsql), parsing (markitdown), chunking (tokenizers/tiktoken),
inference (httpx) — into an **onedir** bundle. Onedir, not onefile (D62): a onefile build
self-extracts to a temp dir on *every* boot, which is both a slow-start tax and Windows AV-scan
bait for a process that gets started/stopped routinely — neither the desktop launcher's
supervised local-mode engine nor a human running the server bundle wants that. This is also why,
unlike both `sift-agent*.spec` files above, this spec **includes** (does not exclude) `sift` and
everything it imports — the engine's whole job here is serving the app, so none of it can be
excluded for weight the way the standalone agent's excludes work. `torch` is not a dependency
anywhere in this tree (README's "all ML inference external over HTTP" rule, CLAUDE.md §3), so
there is nothing equivalent to exclude for size either.

### Entry point (`sift_engine_entry.py`)
```python
from sift.api.main import app
from sift.config import get_settings
uvicorn.run(app, host=settings.api_bind, port=settings.api_port)
```
Imports the already-built `app` object and calls `uvicorn.run()` on it directly — **not** the
string form `uvicorn.run("sift.api.main:app", ...)` that `api.Dockerfile`'s CMD uses for the
containerized deployment. The string form makes uvicorn re-import the module by dotted path at
runtime (relevant for `--reload`/multi-worker, irrelevant here) — which doesn't work once frozen,
since a PyInstaller bundle has no real on-disk package tree for that dotted import to resolve
against, only the bytecode the bootloader already loaded once. `api_bind`/`api_port` are real
typed `Settings` fields (promoted from compose-only host-mapping vars for exactly this entry
point — see `src/sift/config.py` and DECISIONS.md D62), so both the container and the frozen
engine drive off the one config source.

### Known landmines (all handled in `sift-engine.spec`, verified empirically by actually booting
the frozen binary against real, non-fake adapters — a clean `pyinstaller` exit does NOT mean the
binary runs; several of these only surface as a runtime `ModuleNotFoundError`/`KeyError` the
first time the relevant code path executes):
- **`tiktoken_ext` plugin discovery** — tiktoken's registry finds encodings by
  `pkgutil.iter_modules()`-walking the `tiktoken_ext` namespace package's `__path__` at runtime;
  a namespace package has no `__init__.py` for static analysis to follow, AND a PyZ-archived
  namespace package has no real directory for the runtime walk to find at all. Fixed with an
  explicit `tiktoken_ext.openai_public` hidden import **plus**
  `module_collection_mode={"tiktoken_ext": "py"}` (collects it as real on-disk `.py` files
  instead of zipping it into the PYZ archive) — the hidden import alone was not sufficient;
  without the collection-mode override, `tiktoken.get_encoding(...)` raised `KeyError` (zero
  plugins found) even though `import tiktoken` itself succeeded.
- **`huggingface_hub`, reached from `tokenizers`' Rust extension** — booting the frozen binary
  raised `ModuleNotFoundError: No module named 'huggingface_hub'` from
  `tokenizers.Tokenizer.from_pretrained("BAAI/bge-m3")` (the chunker's system-default tokenizer,
  `sift.adapters.chunking.token._BgeM3Tokenizer`). `from_pretrained`'s HTTP download path is
  implemented inside `tokenizers.abi3.so` (compiled Rust), which reaches `huggingface_hub` via
  the Python C API directly — invisible to modulegraph's static bytecode analysis since there is
  no Python-level `import huggingface_hub` anywhere for it to find. Fixed with an explicit
  `huggingface_hub` hidden import. `huggingface_hub/__init__.py` *also* uses a custom
  `_attach()`-based lazy `__getattr__` mechanism for its own submodules (the same
  "invisible to static analysis" shape as tiktoken_ext) — `collect_submodules("huggingface_hub")`
  covers that half.
- **magika's bundled ONNX model** — markitdown uses `magika` for content-type sniffing; magika
  ships its classifier as non-Python data (`models/standard_v3_3/model.onnx` + JSON config), which
  PyInstaller's default analysis does not collect (only `.py`/`.pyc` and directly-imported
  extension modules are followed automatically). Fixed with `collect_data_files("magika")`.
- **`libsql`/`tokenizers` native libraries** — both ship as a single self-contained compiled
  extension module (`libsql.cpython-*.so`, `tokenizers.abi3.so`) that ordinary import-following
  already bundles; `collect_dynamic_libs()` for both is in the spec as a defensive belt-and-braces
  call (PyInstaller's own documented pattern for "a native lib inside a package") even though no
  *second*, not-directly-imported shared object was found empirically for either.
- **markitdown converters** — all built-in converters are directly imported by
  `markitdown/_markitdown.py`, so ordinary static analysis already follows them;
  `collect_submodules("markitdown")` is belt-and-braces for the handful that gate their own
  sub-imports behind a try/except (docx/pptx/xlsx do, for their optional-dependency error
  messages), which can otherwise confuse modulegraph.
- **`python-multipart`** — starlette's multipart form parser does `import python_multipart as
  multipart` at module level (inside a try/except compatibility fallback, but still a real static
  import PyInstaller finds unaided); named as a hidden import anyway since a missing multipart
  parser is a silent 422 on every `/ingest` upload, not an import crash — easy to miss in a quick
  smoke that never actually POSTs a file.
- **uvicorn loops/protocols** — already handled by `_pyinstaller_hooks_contrib`'s own
  `hook-uvicorn.py` (`collect_submodules("uvicorn")`), no action needed in this spec.

### Build + smoke
```bash
pyinstaller packaging/sift-engine.spec
# → dist/sift-engine/  (onedir; dist/sift-engine/sift-engine is the executable)

scripts/smoke-engine-bundle.sh   # boots it in a scratch, RAM-capped systemd --user unit; asserts
                                  # /healthz, /openapi.json, and auth (401 without a bearer token,
                                  # not-401 with one); always stops the unit, PASS/FAIL lines.
```

### The server bundle (`scripts/build-server-bundle.sh`, D63)
Assembles the standalone "API only" download: the frozen engine (above) + `sift-agent-cli`
(Target 2, onefile) + quickstart scripts/config from `packaging/server-bundle/` (`README.md`,
`run.sh`/`run.bat`, `env.example`), tarred as `dist/condense-server-<target-triple>.tar.gz`. This
is the SAME artifact CI publishes as its own release asset (next to the desktop installers) and
the one the desktop launcher's local mode downloads and supervises — one build, both consumption
paths, so they can't drift apart. See `packaging/server-bundle/README.md` for the end-user-facing
quickstart and layout.
