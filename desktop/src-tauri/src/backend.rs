// Local-mode backend supervision: embedder (llama-server serving bge-m3) then engine
// (the frozen FastAPI app), in that order — the engine's adapter dials the embedder over HTTP,
// so it must already be listening. Client mode has no backend to manage here at all.
//
// `binary_path` (where the executable lives inside an unpacked component directory) comes
// straight from the provisioning manifest, re-fetched at `backend_start` time — see
// `provisioning.rs`'s module doc for why there's no separate cached copy of that fact.

use std::collections::HashMap;
use std::path::Path;
use std::process::Stdio;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{AppHandle, Emitter, State};
use tokio::process::{Child, Command};

use crate::config::{AppConfig, ConfigState};
use crate::paths;
use crate::provisioning::{self, Manifest};

#[derive(Debug, Clone, Serialize)]
pub struct ProcState {
    pub state: String, // "stopped" | "starting" | "running" | "error:<msg>"
    pub port: u16,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pid: Option<u32>,
}

impl ProcState {
    fn stopped(port: u16) -> Self {
        Self {
            state: "stopped".to_string(),
            port,
            pid: None,
        }
    }
}

pub struct BackendInner {
    pub engine: ProcState,
    pub embedder: ProcState,
    engine_child: Option<Child>,
    embedder_child: Option<Child>,
}

impl Default for BackendInner {
    fn default() -> Self {
        Self {
            engine: ProcState::stopped(8801),
            embedder: ProcState::stopped(8802),
            engine_child: None,
            embedder_child: None,
        }
    }
}

#[derive(Default)]
pub struct BackendState(pub Mutex<BackendInner>);

#[derive(Debug, Clone, Serialize)]
pub struct BackendStatusResponse {
    pub mode: Option<String>,
    pub engine: ProcState,
    pub embedder: ProcState,
}

#[tauri::command]
pub fn backend_status(
    config_state: State<ConfigState>,
    backend_state: State<BackendState>,
) -> BackendStatusResponse {
    let mode = config_state
        .0
        .lock()
        .expect("config mutex poisoned")
        .mode
        .clone();
    let inner = backend_state.0.lock().expect("backend mutex poisoned");
    BackendStatusResponse {
        mode,
        engine: inner.engine.clone(),
        embedder: inner.embedder.clone(),
    }
}

fn emit_state(app: &AppHandle, component: &str, state: &str, detail: Option<&str>) {
    let _ = app.emit(
        "backend-state",
        serde_json::json!({ "component": component, "state": state, "detail": detail }),
    );
}

fn port_available(port: u16) -> bool {
    std::net::TcpListener::bind(("127.0.0.1", port)).is_ok()
}

#[tauri::command]
pub async fn backend_start(
    app: AppHandle,
    config_state: State<'_, ConfigState>,
    backend_state: State<'_, BackendState>,
) -> Result<(), String> {
    let cfg = {
        config_state
            .0
            .lock()
            .expect("config mutex poisoned")
            .clone()
    };
    if cfg.mode.as_deref() != Some("local") {
        return Err("backend is managed only in local mode".to_string());
    }

    {
        let inner = backend_state.0.lock().expect("backend mutex poisoned");
        if matches!(inner.engine.state.as_str(), "starting" | "running")
            || matches!(inner.embedder.state.as_str(), "starting" | "running")
        {
            // No-op, not an error: both the wizard's explicit `backend_start` call and the
            // setup-time auto-start (`lib.rs`, when `mode == "local"` and everything is already
            // provisioned) can reach here in either order — whichever wins the race starts the
            // backend, the other just finds it already starting/running and does nothing.
            return Ok(());
        }
    }

    if !port_available(cfg.embedder_port) {
        return Err(format!(
            "port {} (embedder) is already in use",
            cfg.embedder_port
        ));
    }
    if !port_available(cfg.engine_port) {
        return Err(format!(
            "port {} (engine) is already in use",
            cfg.engine_port
        ));
    }

    let manifest = provisioning::resolve_manifest(&cfg)
        .await
        .map_err(|e| format!("resolving provisioning manifest: {e}"))?;

    // --- Embedder first: the engine's embedding adapter dials it over HTTP.
    set_state(&backend_state, false, "starting", cfg.embedder_port, None);
    emit_state(&app, "embedder", "starting", None);
    let embedder_child = match start_embedder(&app, &cfg, &manifest).await {
        Ok(child) => child,
        Err(e) => {
            set_state(
                &backend_state,
                false,
                &format!("error:{e}"),
                cfg.embedder_port,
                None,
            );
            emit_state(&app, "embedder", "error", Some(&e));
            return Err(e);
        }
    };
    let embedder_pid = embedder_child.id();
    {
        let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
        inner.embedder_child = Some(embedder_child);
    }
    set_state(
        &backend_state,
        false,
        "running",
        cfg.embedder_port,
        embedder_pid,
    );
    emit_state(&app, "embedder", "running", None);

    // --- Then the engine.
    set_state(&backend_state, true, "starting", cfg.engine_port, None);
    emit_state(&app, "engine", "starting", None);
    let engine_child = match start_engine(&app, &cfg, &manifest).await {
        Ok(child) => child,
        Err(e) => {
            // Don't leave a half-started backend behind — roll the embedder back too.
            let embedder_child = {
                let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
                inner.embedder_child.take()
            };
            if let Some(mut child) = embedder_child {
                let _ = child.kill().await;
            }
            set_state(
                &backend_state,
                true,
                &format!("error:{e}"),
                cfg.engine_port,
                None,
            );
            set_state(&backend_state, false, "stopped", cfg.embedder_port, None);
            emit_state(&app, "engine", "error", Some(&e));
            emit_state(&app, "embedder", "stopped", None);
            return Err(e);
        }
    };
    let engine_pid = engine_child.id();
    {
        let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
        inner.engine_child = Some(engine_child);
    }
    set_state(&backend_state, true, "running", cfg.engine_port, engine_pid);
    emit_state(&app, "engine", "running", None);

    Ok(())
}

fn set_state(
    backend_state: &State<'_, BackendState>,
    is_engine: bool,
    state: &str,
    port: u16,
    pid: Option<u32>,
) {
    let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
    let target = if is_engine {
        &mut inner.engine
    } else {
        &mut inner.embedder
    };
    *target = ProcState {
        state: state.to_string(),
        port,
        pid,
    };
}

#[tauri::command]
pub async fn backend_stop(
    app: AppHandle,
    backend_state: State<'_, BackendState>,
) -> Result<(), String> {
    kill_backend(&app, &backend_state).await;
    Ok(())
}

/// Kill engine first, then embedder (mirrors start order, reversed); shared by `backend_stop`
/// and the app-exit handler in `lib.rs`.
pub async fn kill_backend(app: &AppHandle, backend_state: &State<'_, BackendState>) {
    let engine_child = {
        let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
        inner.engine_child.take()
    };
    if let Some(mut child) = engine_child {
        let _ = child.kill().await;
    }
    let embedder_child = {
        let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
        inner.embedder_child.take()
    };
    if let Some(mut child) = embedder_child {
        let _ = child.kill().await;
    }
    {
        let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
        inner.engine = ProcState::stopped(inner.engine.port);
        inner.embedder = ProcState::stopped(inner.embedder.port);
    }
    emit_state(app, "engine", "stopped", None);
    emit_state(app, "embedder", "stopped", None);
}

// ---------------------------------------------------------------------------------------------
// Spawning
// ---------------------------------------------------------------------------------------------

fn open_log(path: &Path) -> Result<std::fs::File, String> {
    std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|e| format!("opening log {}: {e}", path.display()))
}

async fn wait_for_health(
    child: &mut Child,
    port: u16,
    path: &str,
    timeout: Duration,
) -> Result<(), String> {
    let url = format!("http://127.0.0.1:{port}{path}");
    let client = reqwest::Client::new();
    let start = Instant::now();
    loop {
        if let Some(status) = child
            .try_wait()
            .map_err(|e| format!("checking child process status: {e}"))?
        {
            return Err(format!("process exited before becoming healthy ({status})"));
        }
        if let Ok(resp) = client
            .get(&url)
            .timeout(Duration::from_secs(2))
            .send()
            .await
        {
            if resp.status().is_success() {
                return Ok(());
            }
        }
        if start.elapsed() >= timeout {
            let _ = child.start_kill();
            return Err(format!(
                "timed out after {:?} waiting for {url} to become healthy",
                timeout
            ));
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
}

async fn start_embedder(
    app: &AppHandle,
    cfg: &AppConfig,
    manifest: &Manifest,
) -> Result<Child, String> {
    let target = manifest
        .embedder
        .targets
        .get(paths::TARGET_TRIPLE)
        .ok_or_else(|| format!("no embedder build for target '{}'", paths::TARGET_TRIPLE))?;
    let binary_path = target
        .binary_path
        .as_ref()
        .ok_or_else(|| "embedder manifest target is missing binary_path".to_string())?;
    let bin = paths::runtime_embedder_dir(app)?.join(binary_path);
    if !bin.exists() {
        return Err(format!(
            "embedder binary not found at {} — provision it first",
            bin.display()
        ));
    }
    let model_path = paths::models_dir(app)?.join(&manifest.model.file);
    if !model_path.exists() {
        return Err(format!(
            "embedder model not found at {} — provision it first",
            model_path.display()
        ));
    }
    let model_path_str = model_path
        .to_str()
        .ok_or_else(|| "model path is not valid UTF-8".to_string())?
        .to_string();

    let log_path = paths::ensure_dir(paths::logs_dir(app)?)?.join("embedder.log");
    let stdout_file = open_log(&log_path)?;
    let stderr_file = open_log(&log_path)?;

    // Flags verified empirically against llama.cpp b9878 tonight (D61): OpenAI-compat
    // /v1/embeddings, dim 1024, L2-normalized, ~342MB RSS.
    let args: Vec<String> = vec![
        "-m".into(),
        model_path_str,
        "--embedding".into(),
        "--pooling".into(),
        "cls".into(),
        "-c".into(),
        "8192".into(),
        "--host".into(),
        "127.0.0.1".into(),
        "--port".into(),
        cfg.embedder_port.to_string(),
    ];

    let mut cmd = Command::new(&bin);
    cmd.args(args)
        .stdout(Stdio::from(stdout_file))
        .stderr(Stdio::from(stderr_file))
        .kill_on_drop(true);
    let mut child = cmd.spawn().map_err(|e| format!("spawning embedder: {e}"))?;

    wait_for_health(
        &mut child,
        cfg.embedder_port,
        "/health",
        Duration::from_secs(90),
    )
    .await?;
    Ok(child)
}

async fn start_engine(
    app: &AppHandle,
    cfg: &AppConfig,
    manifest: &Manifest,
) -> Result<Child, String> {
    let target = manifest
        .engine
        .targets
        .get(paths::TARGET_TRIPLE)
        .ok_or_else(|| format!("no engine build for target '{}'", paths::TARGET_TRIPLE))?;
    let binary_path = target
        .binary_path
        .as_ref()
        .ok_or_else(|| "engine manifest target is missing binary_path".to_string())?;
    let bin = paths::runtime_engine_dir(app)?.join(binary_path);
    if !bin.exists() {
        return Err(format!(
            "engine binary not found at {} — provision it first",
            bin.display()
        ));
    }

    let data_dir = paths::ensure_dir(paths::data_subdir(app)?)?;
    let hf_cache = paths::ensure_dir(paths::hf_cache_dir(app)?)?;
    let db_path = data_dir.join("sift.db");

    // A fresh, minimal env — deliberately NOT inheriting the parent process's env wholesale.
    let mut env: HashMap<String, String> = HashMap::new();
    env.insert("STORE_BACKEND".into(), "libsql".into());
    env.insert(
        "TURSO_DATABASE_URL".into(),
        format!("file:{}", db_path.display()),
    );
    env.insert(
        "EMBED_BASE_URL".into(),
        format!("http://127.0.0.1:{}/v1", cfg.embedder_port),
    );
    env.insert("EMBED_MODEL".into(), "bge-m3".into());
    env.insert("EMBED_DIM".into(), "1024".into());
    env.insert("RERANK_STRATEGY".into(), "llm".into());
    env.insert("LLM_BASE_URL".into(), cfg.llm.base_url.clone());
    env.insert("LLM_MODEL".into(), cfg.llm.model.clone());
    env.insert("LLM_API_KEY".into(), cfg.llm.api_key.clone());
    env.insert("INGEST_TOKEN".into(), cfg.ingest_token.clone());
    env.insert("API_BIND".into(), "127.0.0.1".into());
    env.insert("API_PORT".into(), cfg.engine_port.to_string());
    env.insert("HF_HOME".into(), hf_cache.display().to_string());
    if let Ok(path_var) = std::env::var("PATH") {
        env.insert("PATH".into(), path_var);
    }
    if let Ok(home_var) = std::env::var("HOME") {
        env.insert("HOME".into(), home_var);
    }

    let log_path = paths::ensure_dir(paths::logs_dir(app)?)?.join("engine.log");
    let stdout_file = open_log(&log_path)?;
    let stderr_file = open_log(&log_path)?;

    let mut cmd = Command::new(&bin);
    cmd.env_clear()
        .envs(env)
        .stdout(Stdio::from(stdout_file))
        .stderr(Stdio::from(stderr_file))
        .kill_on_drop(true);
    let mut child = cmd.spawn().map_err(|e| format!("spawning engine: {e}"))?;

    wait_for_health(
        &mut child,
        cfg.engine_port,
        "/healthz",
        Duration::from_secs(60),
    )
    .await?;
    Ok(child)
}
