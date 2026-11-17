# PyInstaller spec — the frozen Sift **engine** (FastAPI API, D62): the "server-only" artifact
# CI publishes standalone (D63) and the desktop launcher downloads + supervises in local mode.
#
# Onedir (not onefile, D62): PyInstaller's onefile self-extracts to a temp dir on every single
# boot, which is both a slow-start tax and AV-scan bait on Windows — neither is acceptable for a
# process a user (or the launcher) starts and stops routinely. This is the OPPOSITE shape from
# `sift-agent-cli.spec` (onefile — that one is a Tauri sidecar that only ever starts once per
# app launch and needs a single relocatable file for `bundle.externalBin`).
#
# Unlike both `sift-agent*.spec` files, this one INCLUDES (does not exclude) `sift` and its
# runtime deps: the engine's whole job is serving the FastAPI app, so `sift`, the store/parsing/
# chunking/inference adapter stacks, and their transitive deps (libsql, tokenizers, markitdown,
# tiktoken, pandas/numpy/onnxruntime pulled in by markitdown's converters, magika, cryptography,
# httpx, uvicorn) all need to freeze in. torch is NOT a dependency anywhere in this tree (README's
# "all ML inference external over HTTP" rule — see CLAUDE.md §3) so there is nothing to exclude
# for weight the way the agent specs do.

import os

# SPECPATH is the packaging/ dir; the repo root (one up) is where `src/sift` lives.
repo_root = os.path.abspath(os.path.join(SPECPATH, ".."))
src_root = os.path.join(repo_root, "src")
entry = os.path.join(SPECPATH, "sift_engine_entry.py")

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

hidden = [
    # --- tiktoken plugin discovery (D62 landmine #1) ---------------------------------------
    # tiktoken's `registry.py` finds encodings by `pkgutil.iter_modules()`-walking the
    # `tiktoken_ext` namespace package's `__path__` at *runtime* looking for real directory
    # entries — a namespace package has no `__init__.py` of its own, so PyInstaller's default
    # static-import analysis has nothing to statically follow into `tiktoken_ext.openai_public`
    # unless it's named explicitly here. Verified empirically: without this, `import tiktoken;
    # tiktoken.get_encoding("cl100k_base")` raises `KeyError` in the frozen binary (the registry
    # walk finds zero plugins) even though `import tiktoken` alone succeeds.
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
    # --- markitdown converters (D62 landmine #2) --------------------------------------------
    # All built-in converters are directly imported by `markitdown/_markitdown.py`, so normal
    # static analysis already follows them — `collect_submodules` here is belt-and-braces for
    # any converter that gates its own sub-imports behind a try/except (docx/pptx/xlsx do, for
    # their optional-dependency error messages) which can otherwise confuse modulegraph.
    *collect_submodules("markitdown"),
    # --- huggingface_hub, reached from tokenizers' Rust extension (D62 landmine #6) ---------
    # Empirically confirmed the hard way: booting the frozen binary raised `ModuleNotFoundError:
    # No module named 'huggingface_hub'` from `tokenizers.Tokenizer.from_pretrained` (used by
    # `sift.adapters.chunking.token._BgeM3Tokenizer` for the system-default bge-m3 tokenizer) —
    # `from_pretrained`'s download path is implemented in `tokenizers`' compiled Rust extension
    # (`tokenizers.abi3.so`), which reaches back into `huggingface_hub` via the Python C API
    # directly. That call is invisible to modulegraph's static bytecode analysis (there is no
    # Python-level `import huggingface_hub` statement anywhere for it to find), so it must be
    # named explicitly. `huggingface_hub/__init__.py` ALSO uses a custom `_attach()`
    # `__getattr__`-based lazy-submodule mechanism (`importlib.import_module` at attribute-access
    # time, not at import time) — the same "invisible to static analysis" shape as tiktoken_ext,
    # so its submodules need `collect_submodules` too, not just the top-level hidden import.
    "huggingface_hub",
    *collect_submodules("huggingface_hub"),
    # --- python-multipart (explicitly called out in the brief) ------------------------------
    # starlette's multipart form parser does `import python_multipart as multipart` at module
    # level inside a try/except fallback chain — real static imports, so PyInstaller normally
    # finds them unaided; named here defensively since a missing multipart parser is a silent
    # 422 on every /ingest upload, not an import crash, and thus easy to miss in a quick smoke.
    "python_multipart",
    "multipart",
]

binaries = [
    # --- libsql / tokenizers native libraries (D62 landmines #3/#4) -------------------------
    # Both ship a single self-contained compiled extension module (`libsql.cpython-*.so`,
    # `tokenizers.abi3.so`) that normal import-following already bundles — `collect_dynamic_libs`
    # is belt-and-braces in case either links a *second*, not-directly-imported shared object
    # PyInstaller's binary dependency scan wouldn't otherwise discover as a distinct package
    # asset (there was none found empirically for either at time of writing, but this is the
    # standard defensive call for "a native lib inside a package" per PyInstaller's own docs).
    *collect_dynamic_libs("libsql"),
    *collect_dynamic_libs("tokenizers"),
]

datas = [
    # --- magika's bundled ONNX model + config (D62 landmine #5) -----------------------------
    # markitdown uses `magika` for content-type sniffing; magika ships its classifier as a
    # non-Python data file (`models/standard_v3_3/model.onnx` + config/metadata JSON) that
    # PyInstaller's default source-following analysis does NOT collect (only .py/.pyc + directly
    # -imported extension modules are followed automatically) — without this, magika's model
    # load raises `FileNotFoundError` for `model.onnx` the first time any file is ingested.
    *collect_data_files("magika"),
]

# tiktoken_ext must be collected as real on-disk .py files (not zipped into the PYZ archive) --
# pkgutil.iter_modules() needs an actual filesystem directory to list; a PYZ-archived namespace
# package has no such directory once frozen (PyInstaller's documented fix for this exact
# tiktoken pattern, mirrored in tiktoken's own PyInstaller FAQ entry).
module_collection_mode = {
    "tiktoken_ext": "py",
}

a = Analysis(
    [entry],
    pathex=[repo_root, src_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    module_collection_mode=module_collection_mode,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sift-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # the whole point is a real, log-readable stdout for a server process
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="sift-engine",
)
