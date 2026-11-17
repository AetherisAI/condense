// Local-mode backend supervision: embedder (llama-server serving bge-m3), then reranker (a
// second llama-server serving bge-reranker-v2-m3), then engine (the frozen FastAPI app), in
// that order — the engine's adapters dial both over HTTP, so they should already be listening.
// Client mode has no backend to manage here at all.
//
// The reranker is optional: if its model isn't downloaded yet (an install that predates the reranker —
// `provisioning::install_missing_in_background` fetches it) or its sidecar fails to start, the
// backend still comes up, and the engine's cross-encoder adapter keeps the retrieval order while
// nothing listens on the reranker port. `ensure_reranker_running` starts the sidecar later
// once the model lands, with no engine restart: the engine is always pointed at its port.
//
// `binary_path` (where the executable lives inside an unpacked component directory) comes
// straight from the provisioning manifest, re-fetched at `backend_start` time — see
// `provisioning.rs`'s module doc for why there's no separate cached copy of that fact.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, State};
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

    fn is_live(&self) -> bool {
        matches!(self.state.as_str(), "starting" | "running")
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Component {
    Engine,
    Embedder,
    Reranker,
}

impl Component {
    fn name(self) -> &'static str {
        match self {
            Component::Engine => "engine",
            Component::Embedder => "embedder",
            Component::Reranker => "reranker",
        }
    }
}

pub struct BackendInner {
    pub engine: ProcState,
    pub embedder: ProcState,
    pub reranker: ProcState,
    engine_child: Option<Child>,
    embedder_child: Option<Child>,
    reranker_child: Option<Child>,
}

impl Default for BackendInner {
    fn default() -> Self {
        Self {
            engine: ProcState::stopped(8801),
            embedder: ProcState::stopped(8802),
            reranker: ProcState::stopped(8803),
            engine_child: None,
            embedder_child: None,
            reranker_child: None,
        }
    }
}

impl BackendInner {
    fn proc_mut(&mut self, component: Component) -> &mut ProcState {
        match component {
            Component::Engine => &mut self.engine,
            Component::Embedder => &mut self.embedder,
            Component::Reranker => &mut self.reranker,
        }
    }

    fn child_slot(&mut self, component: Component) -> &mut Option<Child> {
        match component {
            Component::Engine => &mut self.engine_child,
            Component::Embedder => &mut self.embedder_child,
            Component::Reranker => &mut self.reranker_child,
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
    pub reranker: ProcState,
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
        reranker: inner.reranker.clone(),
    }
}

fn emit_state(app: &AppHandle, component: Component, state: &str, detail: Option<&str>) {
    let _ = app.emit(
        "backend-state",
        serde_json::json!({ "component": component.name(), "state": state, "detail": detail }),
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
    // Reject only an explicit "client" mode — NOT `None`. The first-run wizard's "starting"
    // step (`SetupWizard.tsx`) deliberately calls `backend_start` BEFORE persisting
    // `mode: 'local'` via `app_config_set`: it only commits that choice (and lets the wizard
    // overlay hand off to the workbench) once the backend is confirmed healthy, so a failed
    // first attempt never leaves the user stranded in a half-configured "local" mode with no
    // running backend and no wizard left to retry from. Requiring `mode == Some("local")`
    // already here made every real first run fail this guard before it could ever succeed
    // (only caught by real end-to-end testing — a mocked-Tauri browser run never calls into this
    // command at all, so it couldn't have caught it).
    if cfg.mode.as_deref() == Some("client") {
        return Err("backend is managed only in local mode".to_string());
    }

    {
        let inner = backend_state.0.lock().expect("backend mutex poisoned");
        if inner.engine.is_live() || inner.embedder.is_live() {
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
    set_state(
        &backend_state,
        Component::Embedder,
        "starting",
        cfg.embedder_port,
        None,
    );
    emit_state(&app, Component::Embedder, "starting", None);
    let embedder_child = match start_embedder(&app, &cfg, &manifest).await {
        Ok(child) => child,
        Err(e) => {
            set_state(
                &backend_state,
                Component::Embedder,
                &format!("error:{e}"),
                cfg.embedder_port,
                None,
            );
            emit_state(&app, Component::Embedder, "error", Some(&e));
            return Err(e);
        }
    };
    let embedder_pid = embedder_child.id();
    store_child(&backend_state, Component::Embedder, embedder_child);
    set_state(
        &backend_state,
        Component::Embedder,
        "running",
        cfg.embedder_port,
        embedder_pid,
    );
    emit_state(&app, Component::Embedder, "running", None);

    // --- Then the reranker, when its model is installed. Never fatal (see the module doc).
    start_reranker_if_installed(&app, &backend_state, &cfg, &manifest).await;

    // --- Then the engine.
    set_state(
        &backend_state,
        Component::Engine,
        "starting",
        cfg.engine_port,
        None,
    );
    emit_state(&app, Component::Engine, "starting", None);
    let engine_child = match start_engine(&app, &cfg, &manifest).await {
        Ok(child) => child,
        Err(e) => {
            // Don't leave a half-started backend behind — roll the sidecars back too.
            for sidecar in [Component::Reranker, Component::Embedder] {
                let child = {
                    let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
                    inner.child_slot(sidecar).take()
                };
                if let Some(mut child) = child {
                    let _ = child.kill().await;
                }
            }
            set_state(
                &backend_state,
                Component::Engine,
                &format!("error:{e}"),
                cfg.engine_port,
                None,
            );
            set_state(
                &backend_state,
                Component::Embedder,
                "stopped",
                cfg.embedder_port,
                None,
            );
            set_state(
                &backend_state,
                Component::Reranker,
                "stopped",
                cfg.reranker_port,
                None,
            );
            emit_state(&app, Component::Engine, "error", Some(&e));
            emit_state(&app, Component::Embedder, "stopped", None);
            emit_state(&app, Component::Reranker, "stopped", None);
            return Err(e);
        }
    };
    let engine_pid = engine_child.id();
    store_child(&backend_state, Component::Engine, engine_child);
    set_state(
        &backend_state,
        Component::Engine,
        "running",
        cfg.engine_port,
        engine_pid,
    );
    emit_state(&app, Component::Engine, "running", None);

    Ok(())
}

fn set_state(
    backend_state: &State<'_, BackendState>,
    component: Component,
    state: &str,
    port: u16,
    pid: Option<u32>,
) {
    let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
    *inner.proc_mut(component) = ProcState {
        state: state.to_string(),
        port,
        pid,
    };
}

fn store_child(backend_state: &State<'_, BackendState>, component: Component, child: Child) {
    let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
    *inner.child_slot(component) = Some(child);
}

/// Start the reranker sidecar if the manifest lists one and its model is on disk. Claims the
/// "starting" state under the lock first, so `backend_start` and a just-finished background
/// download (`ensure_reranker_running`) can't both spawn it. Failure leaves an `error:` state
/// and a log line; the backend runs on without a reranker.
async fn start_reranker_if_installed(
    app: &AppHandle,
    backend_state: &State<'_, BackendState>,
    cfg: &AppConfig,
    manifest: &Manifest,
) {
    match provisioning::reranker_installed(app, manifest) {
        Ok(true) => {}
        Ok(false) => {
            let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
            if !inner.reranker.is_live() {
                inner.reranker = ProcState::stopped(cfg.reranker_port);
            }
            return;
        }
        Err(e) => {
            eprintln!("backend: checking the reranker model failed: {e}");
            return;
        }
    }
    {
        let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
        if inner.reranker.is_live() {
            return;
        }
        inner.reranker = ProcState {
            state: "starting".to_string(),
            port: cfg.reranker_port,
            pid: None,
        };
    }
    emit_state(app, Component::Reranker, "starting", None);
    let started = if port_available(cfg.reranker_port) {
        start_reranker(app, cfg, manifest).await
    } else {
        Err(format!(
            "port {} (reranker) is already in use",
            cfg.reranker_port
        ))
    };
    match started {
        Ok(child) => {
            let pid = child.id();
            store_child(backend_state, Component::Reranker, child);
            set_state(
                backend_state,
                Component::Reranker,
                "running",
                cfg.reranker_port,
                pid,
            );
            emit_state(app, Component::Reranker, "running", None);
        }
        Err(e) => {
            eprintln!("backend: reranker failed to start, continuing without it: {e}");
            set_state(
                backend_state,
                Component::Reranker,
                &format!("error:{e}"),
                cfg.reranker_port,
                None,
            );
            emit_state(app, Component::Reranker, "error", Some(&e));
        }
    }
}

/// Start the reranker sidecar now if the backend runs in local mode without it — called once its
/// model finishes downloading (background install or the System menu's Download button). The
/// engine needs no restart: it already points at the reranker port.
pub async fn ensure_reranker_running(app: &AppHandle) {
    let cfg = app
        .state::<ConfigState>()
        .0
        .lock()
        .expect("config mutex poisoned")
        .clone();
    if cfg.mode.as_deref() != Some("local") {
        return;
    }
    let backend_state = app.state::<BackendState>();
    {
        let inner = backend_state.0.lock().expect("backend mutex poisoned");
        if !inner.embedder.is_live() || inner.reranker.is_live() {
            // Backend stopped: the next `backend_start` starts the reranker with everything else.
            return;
        }
    }
    match provisioning::resolve_manifest(&cfg).await {
        Ok(manifest) => start_reranker_if_installed(app, &backend_state, &cfg, &manifest).await,
        Err(e) => eprintln!("backend: can't start the reranker, manifest unavailable: {e}"),
    }
}

#[tauri::command]
pub async fn backend_stop(
    app: AppHandle,
    backend_state: State<'_, BackendState>,
) -> Result<(), String> {
    kill_backend(&app, &backend_state).await;
    Ok(())
}

/// Kill engine first, then the sidecars (mirrors start order, reversed); shared by
/// `backend_stop` and the app-exit handler in `lib.rs`.
pub async fn kill_backend(app: &AppHandle, backend_state: &State<'_, BackendState>) {
    for component in [Component::Engine, Component::Reranker, Component::Embedder] {
        let child = {
            let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
            inner.child_slot(component).take()
        };
        if let Some(mut child) = child {
            let _ = child.kill().await;
        }
    }
    {
        let mut inner = backend_state.0.lock().expect("backend mutex poisoned");
        inner.engine = ProcState::stopped(inner.engine.port);
        inner.embedder = ProcState::stopped(inner.embedder.port);
        inner.reranker = ProcState::stopped(inner.reranker.port);
    }
    emit_state(app, Component::Engine, "stopped", None);
    emit_state(app, Component::Reranker, "stopped", None);
    emit_state(app, Component::Embedder, "stopped", None);
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

/// Belt-and-braces child reaping: on Linux, ask the kernel to SIGTERM this child the
/// moment its parent dies — for ANY reason, including SIGKILL or a hard crash, which no
/// in-process cleanup (`RunEvent` handler, signal handler) can ever cover. Both llama-server
/// and the engine (uvicorn) exit cleanly on SIGTERM.
///
/// Platform notes: `PR_SET_PDEATHSIG` is Linux-only — macOS (kqueue `NOTE_EXIT`) and Windows
/// (Job objects) equivalents are not implemented yet; on those platforms the cleanup handlers remain the
/// only mechanism, so this compiles to a no-op there. Kernel gotcha, deliberate: the signal
/// fires on the death of the spawning *thread*, not the process — safe here because tokio's
/// core worker threads (where `Command::spawn` runs) live until runtime shutdown, i.e. app
/// exit, which is exactly the event we want to propagate.
fn set_parent_death_signal(cmd: &mut Command) {
    #[cfg(target_os = "linux")]
    // SAFETY: the pre_exec closure runs post-fork/pre-exec in the child and calls only the
    // async-signal-safe prctl(2) — no allocation, no locks.
    unsafe {
        cmd.pre_exec(|| {
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGTERM) != 0 {
                return Err(std::io::Error::last_os_error());
            }
            Ok(())
        });
    }
    #[cfg(not(target_os = "linux"))]
    {
        let _ = cmd;
    }
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

/// The llama-server executable from the unpacked `embedder` component — the embedder AND the
/// reranker sidecar both run it, each with its own model.
fn llama_server_bin(app: &AppHandle, manifest: &Manifest) -> Result<PathBuf, String> {
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
            "llama-server binary not found at {} — provision the embedder first",
            bin.display()
        ));
    }
    Ok(bin)
}

fn model_path_string(app: &AppHandle, file: &str, what: &str) -> Result<String, String> {
    let model_path = paths::models_dir(app)?.join(file);
    if !model_path.exists() {
        return Err(format!(
            "{what} model not found at {} — provision it first",
            model_path.display()
        ));
    }
    model_path
        .to_str()
        .map(str::to_string)
        .ok_or_else(|| "model path is not valid UTF-8".to_string())
}

/// Spawn a llama-server child logging to `logs/<log_name>` and wait for its `/health`.
async fn spawn_llama_server(
    app: &AppHandle,
    bin: &Path,
    args: Vec<String>,
    port: u16,
    log_name: &str,
    what: &str,
) -> Result<Child, String> {
    let log_path = paths::ensure_dir(paths::logs_dir(app)?)?.join(log_name);
    let stdout_file = open_log(&log_path)?;
    let stderr_file = open_log(&log_path)?;

    let mut cmd = Command::new(bin);
    cmd.args(args)
        .stdout(Stdio::from(stdout_file))
        .stderr(Stdio::from(stderr_file))
        .kill_on_drop(true);
    set_parent_death_signal(&mut cmd);
    let mut child = cmd.spawn().map_err(|e| format!("spawning {what}: {e}"))?;

    wait_for_health(&mut child, port, "/health", Duration::from_secs(90)).await?;
    Ok(child)
}

async fn start_embedder(
    app: &AppHandle,
    cfg: &AppConfig,
    manifest: &Manifest,
) -> Result<Child, String> {
    let bin = llama_server_bin(app, manifest)?;
    let model_path = model_path_string(app, &manifest.model.file, "embedder")?;
    spawn_llama_server(
        app,
        &bin,
        embedder_args(&model_path, cfg.embedder_port),
        cfg.embedder_port,
        "embedder.log",
        "embedder",
    )
    .await
}

async fn start_reranker(
    app: &AppHandle,
    cfg: &AppConfig,
    manifest: &Manifest,
) -> Result<Child, String> {
    let reranker = manifest
        .reranker
        .as_ref()
        .ok_or_else(|| "this manifest lists no reranker".to_string())?;
    let bin = llama_server_bin(app, manifest)?;
    let model_path = model_path_string(app, &reranker.file, "reranker")?;
    spawn_llama_server(
        app,
        &bin,
        reranker_args(&model_path, cfg.reranker_port),
        cfg.reranker_port,
        "reranker.log",
        "reranker",
    )
    .await
}

/// Flags verified empirically against llama.cpp b9878: OpenAI-compat /v1/embeddings,
/// dim 1024, L2-normalized, ~342MB RSS.
fn embedder_args(model_path: &str, port: u16) -> Vec<String> {
    [
        "-m",
        model_path,
        "--embedding",
        "--pooling",
        "cls",
        "-c",
        "8192",
        "--host",
        "127.0.0.1",
        "--port",
        &port.to_string(),
    ]
    .iter()
    .map(|s| s.to_string())
    .collect()
}

/// bge-reranker-v2-m3 as a cross-encoder, verified against llama.cpp b9878: `--reranking`
/// serves `/rerank` in TEI's `{query, texts}` → `[{index, score}]` shape (raw logits; the
/// engine's adapter applies the sigmoid). A query+passage pair must fit one micro-batch, so
/// `-ub`/`-b` equal the per-slot context (4096 / 4 slots = 1024 tokens): a 512-token chunk plus a
/// query of up to ~500 tokens; a longer pair gets a 500. Measured on an M5 with Metal: ~2.7 s
/// for 30 ~500-token passages, 864 MB footprint (`-c 8192 -ub 2048`: 3.0 s, 2.2 GB).
fn reranker_args(model_path: &str, port: u16) -> Vec<String> {
    [
        "-m",
        model_path,
        "--reranking",
        "-c",
        "4096",
        "-ub",
        "1024",
        "-b",
        "1024",
        "--parallel",
        "4",
        "--host",
        "127.0.0.1",
        "--port",
        &port.to_string(),
    ]
    .iter()
    .map(|s| s.to_string())
    .collect()
}

/// The engine's rerank settings. With a reranker in the manifest the engine always
/// uses the cross-encoder at the sidecar's port, even while its model is still downloading: the
/// adapter keeps the retrieval order until the sidecar answers. Without one, no reranking — the
/// LLM judge it replaces made top-1 worse with the default Mistral Small (MITRE eval: 0.69 →
/// 0.63), and it fails outright with no LLM key.
fn rerank_env(manifest: &Manifest, reranker_port: u16) -> Vec<(&'static str, String)> {
    match &manifest.reranker {
        Some(reranker) => vec![
            ("RERANK_STRATEGY", "crossencoder".to_string()),
            (
                "RERANK_BASE_URL",
                format!("http://127.0.0.1:{reranker_port}"),
            ),
            ("RERANK_MODEL", reranker.name.clone()),
        ],
        None => vec![("RERANK_STRATEGY", "none".to_string())],
    }
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
    for (key, value) in rerank_env(manifest, cfg.reranker_port) {
        env.insert(key.into(), value);
    }
    env.insert(
        "TOOLS_SEARCH_RERANK".into(),
        cfg.tools_search_rerank.to_string(),
    );
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
    set_parent_death_signal(&mut cmd);
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

#[cfg(test)]
mod tests {
    use super::*;

    fn manifest(with_reranker: bool) -> Manifest {
        let mut value: serde_json::Value =
            serde_json::from_str(include_str!("../../provisioning/manifest.json"))
                .expect("manifest is JSON");
        if !with_reranker {
            value.as_object_mut().unwrap().remove("reranker");
        }
        serde_json::from_value(value).expect("manifest parses")
    }

    fn env_map(manifest: &Manifest, port: u16) -> HashMap<&'static str, String> {
        rerank_env(manifest, port).into_iter().collect()
    }

    #[test]
    fn engine_uses_the_cross_encoder_sidecar_when_the_manifest_has_a_reranker() {
        let env = env_map(&manifest(true), 8803);
        assert_eq!(env["RERANK_STRATEGY"], "crossencoder");
        assert_eq!(env["RERANK_BASE_URL"], "http://127.0.0.1:8803");
        assert_eq!(env["RERANK_MODEL"], "bge-reranker-v2-m3");
    }

    #[test]
    fn engine_skips_reranking_without_a_reranker_in_the_manifest() {
        let env = env_map(&manifest(false), 8803);
        assert_eq!(env["RERANK_STRATEGY"], "none");
        assert!(!env.contains_key("RERANK_BASE_URL"));
    }

    #[test]
    fn reranker_sidecar_serves_rerank_on_loopback_at_its_port() {
        let args = reranker_args("/models/r.gguf", 8813);
        let joined = args.join(" ");
        assert!(joined.starts_with("-m /models/r.gguf --reranking"));
        assert!(joined.contains("--host 127.0.0.1 --port 8813"));
        assert!(!args.iter().any(|a| a == "--embedding"));
        // A pair must fit one micro-batch: -ub covers the per-slot context.
        let ub = args.iter().position(|a| a == "-ub").unwrap();
        let ctx = args.iter().position(|a| a == "-c").unwrap();
        let slots = args.iter().position(|a| a == "--parallel").unwrap();
        let per_slot: u32 =
            args[ctx + 1].parse::<u32>().unwrap() / args[slots + 1].parse::<u32>().unwrap();
        assert_eq!(args[ub + 1].parse::<u32>().unwrap(), per_slot);
    }

    #[test]
    fn embedder_args_are_unchanged_by_the_reranker() {
        let joined = embedder_args("/models/e.gguf", 8802).join(" ");
        assert_eq!(
            joined,
            "-m /models/e.gguf --embedding --pooling cls -c 8192 --host 127.0.0.1 --port 8802"
        );
    }
}
