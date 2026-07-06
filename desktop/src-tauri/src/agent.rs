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
}

#[derive(Default)]
pub struct AgentInner {
    child: Option<CommandChild>,
    running: bool,
    user_stopped: bool,
    restarts: u32,
    /// The exact argv used to spawn — replayed verbatim on an unexpected-termination restart.
    args: Vec<String>,
}

#[derive(Default)]
pub struct AgentState(pub Mutex<AgentInner>);

#[derive(Debug, Clone, Serialize)]
pub struct AgentStatusResponse {
    pub running: bool,
    pub user_stopped: bool,
    pub restarts: u32,
}

#[tauri::command]
pub fn agent_status(agent_state: State<AgentState>) -> AgentStatusResponse {
    let inner = agent_state.0.lock().expect("agent mutex poisoned");
    AgentStatusResponse {
        running: inner.running,
        user_stopped: inner.user_stopped,
        restarts: inner.restarts,
    }
}

fn build_args(cfg: &AgentConfig, fallback_server: String, fallback_token: String) -> Vec<String> {
    let mut args: Vec<String> = cfg.paths.clone();
    args.push("--server".to_string());
    args.push(cfg.server.clone().unwrap_or(fallback_server));
    args.push("--token".to_string());
    args.push(cfg.token.clone().unwrap_or(fallback_token));
    args.push("--json".to_string());
    args.push("--watch".to_string());
    if cfg.delete_removed {
        args.push("--delete-removed".to_string());
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
    let args = build_args(&cfg, fallback_server, fallback_token);

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
                    let _ = app_for_task.emit("agent-event", serde_json::json!({ "line": line }));
                }
                CommandEvent::Error(err) => {
                    let _ = app_for_task.emit(
                        "agent-event",
                        serde_json::json!({ "line": format!("[error] {err}") }),
                    );
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
/// (the process dying as a direct result of this kill) never triggers a restart.
pub async fn kill_agent(app: &AppHandle) {
    let agent_state = app.state::<AgentState>();
    let child = {
        let mut inner = agent_state.0.lock().expect("agent mutex poisoned");
        inner.user_stopped = true;
        inner.running = false;
        inner.child.take()
    };
    if let Some(child) = child {
        let _ = child.kill();
    }
}
