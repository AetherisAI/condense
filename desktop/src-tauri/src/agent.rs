// Ingest agent sidecar supervision — wraps the `sift-agent-cli` binary (bundled as a Tauri
// `externalBin`, see `tauri.conf.json`'s `bundle.externalBin` + `capabilities/default.json`'s
// scoped `shell:allow-spawn`), the headless twin of this desktop app's folder watcher
// (agent/cli.py's `--watch --json`, D54).
//
// `AgentConfig` is the one approved contract extension (machine.md): `server`/`token` are
// optional — when absent, local-mode values (`http://127.0.0.1:{engine_port}` + the app's
// `ingest_token`) are substituted here, so a caller that doesn't yet know about client-mode
// nuances can just pass `{paths, delete_removed}` and get local-mode behavior for free.

use std::sync::Mutex;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

use crate::config::ConfigState;

const SIDECAR_NAME: &str = "sift-agent-cli";
const MAX_RESTARTS: u32 = 5;
const RESTART_BACKOFF: Duration = Duration::from_secs(2);
/// Bounded ring buffer size for `AgentInner.log` — mirrors the frontend's own `.slice(-199)` cap
/// on `agentLog` (`SystemMenu.tsx`) so the two never disagree about "how much history is kept".
const MAX_LOG_LINES: usize = 200;

#[derive(Debug, Clone, Default, Deserialize)]
pub struct AgentConfig {
    #[serde(default)]
    pub paths: Vec<String>,
    #[serde(default)]
    pub delete_removed: bool,
    #[serde(default)]
    pub server: Option<String>,
    #[serde(default)]
    pub token: Option<String>,
    /// Per-file size guard (MB) forwarded as `--max-file-size-mb`; `None` lets the sidecar use
    /// its own default (100MB, `agent.sync.DEFAULT_MAX_FILE_SIZE_MB`).
    #[serde(default)]
    pub max_file_size_mb: Option<u32>,
    /// EXTRA directory names forwarded as repeated `--exclude-dir`, merged by the sidecar with
    /// its own built-in vendored/tooling set — never replaces it.
    #[serde(default)]
    pub exclude_dirs: Vec<String>,
}

#[derive(Default)]
pub struct AgentInner {
    child: Option<CommandChild>,
    running: bool,
    user_stopped: bool,
    restarts: u32,
    /// The exact argv used to spawn — replayed verbatim on an unexpected-termination restart.
    args: Vec<String>,
    /// Bounded ring buffer of recent raw stdout/stderr lines from EITHER the continuous agent or
    /// a one-shot `agent_sync_once` run. This is what lets a freshly-(re)opened System drawer (or
    /// a fresh app launch while the agent is already running) show real history instead of "Log
    /// (0)" — `agent_status` returns it below, so the frontend can hydrate before it even starts
    /// listening for live `agent-event`s, closing the gap where a sync that fired while the
    /// drawer was closed used to vanish with no listener ever having been attached to see it.
    log: Vec<String>,
    /// In-flight one-shot `agent_sync_once` children, keyed by pid — reaped by `kill_agent`
    /// (app-exit and `agent_stop`) alongside the continuous agent, so a manual "Sync now" run
    /// can never outlive the app. Independent of `running`/`restarts`, which describe only the
    /// continuous `--watch` agent.
    one_shot: Vec<(u32, CommandChild)>,
}

#[derive(Default)]
pub struct AgentState(pub Mutex<AgentInner>);

#[derive(Debug, Clone, Serialize)]
pub struct AgentStatusResponse {
    pub running: bool,
    pub user_stopped: bool,
    pub restarts: u32,
    pub log: Vec<String>,
}

#[tauri::command]
pub fn agent_status(agent_state: State<AgentState>) -> AgentStatusResponse {
    let inner = agent_state.0.lock().expect("agent mutex poisoned");
    AgentStatusResponse {
        running: inner.running,
        user_stopped: inner.user_stopped,
        restarts: inner.restarts,
        log: inner.log.clone(),
    }
}

/// Record one raw stdout/stderr line into the bounded log buffer, then emit it live as
/// `agent-event` — the single funnel both `spawn_agent` (continuous) and `spawn_one_shot` (manual
/// "Sync now") push through, so a subscriber never has to special-case which process a line came
/// from.
fn push_log_line(app: &AppHandle, line: String) {
    {
        let agent_state = app.state::<AgentState>();
        let mut inner = agent_state.0.lock().expect("agent mutex poisoned");
        inner.log.push(line.clone());
        if inner.log.len() > MAX_LOG_LINES {
            let excess = inner.log.len() - MAX_LOG_LINES;
            inner.log.drain(0..excess);
        }
    }
    let _ = app.emit("agent-event", serde_json::json!({ "line": line }));
}

/// `watch=true` builds the continuous `--watch --json` argv `agent_start` has always used;
/// `watch=false` (the one-shot "Sync now" path) omits `--watch`/`--delete-removed` (a no-op in
/// one-shot mode anyway — only `_watch()` in `agent/cli.py` reads that flag) so the sidecar runs
/// a single collect→diff→upload pass and exits. The granularity knobs (`max_file_size_mb`,
/// `exclude_dirs`) apply identically either way.
fn build_args(
    cfg: &AgentConfig,
    fallback_server: String,
    fallback_token: String,
    watch: bool,
) -> Vec<String> {
    let mut args: Vec<String> = cfg.paths.clone();
    args.push("--server".to_string());
    args.push(cfg.server.clone().unwrap_or(fallback_server));
    args.push("--token".to_string());
    args.push(cfg.token.clone().unwrap_or(fallback_token));
    args.push("--json".to_string());
    if watch {
        args.push("--watch".to_string());
        if cfg.delete_removed {
            args.push("--delete-removed".to_string());
        }
    }
    if let Some(mb) = cfg.max_file_size_mb {
        args.push("--max-file-size-mb".to_string());
        args.push(mb.to_string());
    }
    if !cfg.exclude_dirs.is_empty() {
        args.push("--exclude-dir".to_string());
        args.extend(cfg.exclude_dirs.clone());
    }
    args
}

#[tauri::command]
pub fn agent_start(
    app: AppHandle,
    config_state: State<ConfigState>,
    agent_state: State<AgentState>,
    cfg: AgentConfig,
) -> Result<(), String> {
    let (fallback_server, fallback_token) = {
        let app_cfg = config_state.0.lock().expect("config mutex poisoned");
        (
            format!("http://127.0.0.1:{}", app_cfg.engine_port),
            app_cfg.ingest_token.clone(),
        )
    };
    let args = build_args(&cfg, fallback_server, fallback_token, true);

    {
        let mut inner = agent_state.0.lock().expect("agent mutex poisoned");
        if inner.running {
            return Err("agent already running".to_string());
        }
        inner.user_stopped = false;
        inner.restarts = 0;
        inner.args = args.clone();
    }

    spawn_agent(app, args)
}

/// One-shot "Sync now": runs a single collect→diff→upload pass (no `--watch`) independent of the
/// continuous agent's own running/stopped state — safe to call whether or not `agent_start` was
/// ever called, and never disturbs its restart bookkeeping.
#[tauri::command]
pub fn agent_sync_once(
    app: AppHandle,
    config_state: State<ConfigState>,
    cfg: AgentConfig,
) -> Result<(), String> {
    let (fallback_server, fallback_token) = {
        let app_cfg = config_state.0.lock().expect("config mutex poisoned");
        (
            format!("http://127.0.0.1:{}", app_cfg.engine_port),
            app_cfg.ingest_token.clone(),
        )
    };
    let args = build_args(&cfg, fallback_server, fallback_token, false);
    spawn_one_shot(app, args)
}

/// Spawn the sidecar and hand its event stream off to a background task that forwards
/// stdout/stderr lines as `agent-event` and reacts to `Terminated` (restart-with-backoff unless
/// the user explicitly stopped it or the retry budget is exhausted).
fn spawn_agent(app: AppHandle, args: Vec<String>) -> Result<(), String> {
    let (mut rx, child) = app
        .shell()
        .sidecar(SIDECAR_NAME)
        .map_err(|e| format!("locating {SIDECAR_NAME} sidecar: {e}"))?
        .args(args)
        .spawn()
        .map_err(|e| format!("spawning {SIDECAR_NAME}: {e}"))?;

    {
        let agent_state = app.state::<AgentState>();
        let mut inner = agent_state.0.lock().expect("agent mutex poisoned");
        inner.child = Some(child);
        inner.running = true;
    }

    let app_for_task = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) | CommandEvent::Stderr(bytes) => {
                    let line = String::from_utf8_lossy(&bytes).into_owned();
                    push_log_line(&app_for_task, line);
                }
                CommandEvent::Error(err) => {
                    push_log_line(&app_for_task, format!("[error] {err}"));
                }
                CommandEvent::Terminated(payload) => {
                    on_terminated(&app_for_task, payload.code).await;
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(())
}

/// Spawn a single-pass (no `--watch`) sidecar run — the "Sync now" button. Forwards output
/// through the SAME `push_log_line` path `spawn_agent` uses (so the UI's existing per-line
/// handling needs no special case for where a line came from), then emits a distinct
/// `agent-sync-once-done` (never `agent-terminated`, which is the continuous agent's own
/// lifecycle signal) when the run exits. Tracked in `AgentInner.one_shot` purely so
/// `kill_agent` can reap it if the app quits mid-run.
fn spawn_one_shot(app: AppHandle, args: Vec<String>) -> Result<(), String> {
    let (mut rx, child) = app
        .shell()
        .sidecar(SIDECAR_NAME)
        .map_err(|e| format!("locating {SIDECAR_NAME} sidecar: {e}"))?
        .args(args)
        .spawn()
        .map_err(|e| format!("spawning {SIDECAR_NAME}: {e}"))?;

    let pid = child.pid();
    {
        let agent_state = app.state::<AgentState>();
        let mut inner = agent_state.0.lock().expect("agent mutex poisoned");
        inner.one_shot.push((pid, child));
    }

    let app_for_task = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) | CommandEvent::Stderr(bytes) => {
                    let line = String::from_utf8_lossy(&bytes).into_owned();
                    push_log_line(&app_for_task, line);
                }
                CommandEvent::Error(err) => {
                    push_log_line(&app_for_task, format!("[error] {err}"));
                }
                CommandEvent::Terminated(payload) => {
                    let agent_state = app_for_task.state::<AgentState>();
                    let mut inner = agent_state.0.lock().expect("agent mutex poisoned");
                    inner.one_shot.retain(|(p, _)| *p != pid);
                    drop(inner);
                    let _ = app_for_task.emit(
                        "agent-sync-once-done",
                        serde_json::json!({ "code": payload.code }),
                    );
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(())
}

async fn on_terminated(app: &AppHandle, code: Option<i32>) {
    let agent_state = app.state::<AgentState>();
    let (should_restart, args) = {
        let mut inner = agent_state.0.lock().expect("agent mutex poisoned");
        inner.child = None;
        inner.running = false;
        if inner.user_stopped || inner.restarts >= MAX_RESTARTS {
            (false, Vec::new())
        } else {
            inner.restarts += 1;
            (true, inner.args.clone())
        }
    };

    let _ = app.emit(
        "agent-terminated",
        serde_json::json!({ "code": code, "will_restart": should_restart }),
    );

    if !should_restart {
        return;
    }
    tokio::time::sleep(RESTART_BACKOFF).await;
    // Re-check: `agent_stop` may have raced in during the backoff sleep.
    let still_wanted = !agent_state
        .0
        .lock()
        .expect("agent mutex poisoned")
        .user_stopped;
    if still_wanted {
        if let Err(e) = spawn_agent(app.clone(), args) {
            let _ = app.emit(
                "agent-event",
                serde_json::json!({ "line": format!("[error] agent restart failed: {e}") }),
            );
        }
    }
}

#[tauri::command]
pub async fn agent_stop(app: AppHandle) -> Result<(), String> {
    kill_agent(&app).await;
    Ok(())
}

/// Best-effort synchronous-from-the-caller's-perspective kill, shared by `agent_stop` and the
/// app-exit handler in `lib.rs`. Always marks `user_stopped` so an in-flight `Terminated` event
/// (the process dying as a direct result of this kill) never triggers a restart. Also reaps any
/// in-flight one-shot `agent_sync_once` run(s) — a manual "Sync now" click must never outlive
/// either an explicit Stop or the app itself.
pub async fn kill_agent(app: &AppHandle) {
    let agent_state = app.state::<AgentState>();
    let (child, one_shot) = {
        let mut inner = agent_state.0.lock().expect("agent mutex poisoned");
        inner.user_stopped = true;
        inner.running = false;
        (inner.child.take(), std::mem::take(&mut inner.one_shot))
    };
    if let Some(child) = child {
        let _ = child.kill();
    }
    for (_pid, child) in one_shot {
        let _ = child.kill();
    }
}
