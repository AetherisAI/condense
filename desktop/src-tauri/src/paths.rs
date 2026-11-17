// App data-dir layout, shared by `provisioning`, `backend`, and `agent`.
//
// Data dir (Tauri path API, `app.path().app_data_dir()`; Linux:
// `~/.local/share/ai.aetheris.condense/`):
//   runtime/engine/     unpacked engine bundle (PyInstaller onedir)
//   runtime/embedder/   unpacked llama-server release
//   models/             *.gguf embedder weights
//   data/               the engine's `file:` libsql DB lives here
//   hf-cache/           HF_HOME for the chunker tokenizer (kept out of the user's real HF cache)
//   logs/               engine.log / embedder.log
//   tmp/                scratch space for in-flight downloads + archive extraction

use std::path::PathBuf;

use tauri::{AppHandle, Manager};

// These are pure path builders — no filesystem I/O, no side effects. Call `ensure_dir()`
// explicitly at the point a caller is about to write into one (status/read checks should NOT
// have the side effect of creating directories that don't exist yet).

pub fn app_data_dir(app: &AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_data_dir()
        .map_err(|e| format!("resolving app data dir: {e}"))
}

/// Ensure `dir` exists (and all parents), returning it back for chaining.
pub fn ensure_dir(dir: PathBuf) -> Result<PathBuf, String> {
    std::fs::create_dir_all(&dir).map_err(|e| format!("creating {}: {e}", dir.display()))?;
    Ok(dir)
}

pub fn runtime_engine_dir(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app_data_dir(app)?.join("runtime").join("engine"))
}

pub fn runtime_embedder_dir(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app_data_dir(app)?.join("runtime").join("embedder"))
}

pub fn models_dir(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app_data_dir(app)?.join("models"))
}

pub fn data_subdir(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app_data_dir(app)?.join("data"))
}

pub fn hf_cache_dir(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app_data_dir(app)?.join("hf-cache"))
}

pub fn logs_dir(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app_data_dir(app)?.join("logs"))
}

pub fn tmp_dir(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app_data_dir(app)?.join("tmp"))
}

/// Compile-time target triple — matches the manifest's per-target key. Only the three triples
/// tonight's manifest actually lists are wired up (D62); an unrecognized host falls back to a
/// sentinel that reliably fails provisioning lookups with a clear error rather than guessing.
#[cfg(all(target_arch = "x86_64", target_os = "linux"))]
pub const TARGET_TRIPLE: &str = "x86_64-unknown-linux-gnu";
#[cfg(all(target_arch = "aarch64", target_os = "macos"))]
pub const TARGET_TRIPLE: &str = "aarch64-apple-darwin";
#[cfg(all(target_arch = "x86_64", target_os = "windows"))]
pub const TARGET_TRIPLE: &str = "x86_64-pc-windows-msvc";
#[cfg(not(any(
    all(target_arch = "x86_64", target_os = "linux"),
    all(target_arch = "aarch64", target_os = "macos"),
    all(target_arch = "x86_64", target_os = "windows"),
)))]
pub const TARGET_TRIPLE: &str = "unsupported-target";
