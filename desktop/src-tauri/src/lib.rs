// Condense desktop shell — Tauri 2 application entry.
//
// `run()` is the single composition root the mobile entry point and the desktop `main.rs` both
// call into. T5 (Rust provisioning + supervision) adds four modules, each a managed `State`:
// `config` (AppConfig load/save), `provisioning` (manifest-driven download/verify/unpack),
// `backend` (engine + embedder process supervision), `agent` (the ingest sidecar). See
// `docs/Quentin/active/machine.md` for the full command contract these wire up to.

mod agent;
mod backend;
mod config;
mod paths;
mod provisioning;

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(agent::AgentState::default())
        .manage(backend::BackendState::default())
        .manage(provisioning::ProvisionState::default())
        .setup(|app| {
            let initial_config = config::load_or_init(&app.handle())?;
            let mode = initial_config.mode.clone();
            app.manage(config::ConfigState(std::sync::Mutex::new(initial_config)));

            // SIGTERM/SIGINT → the same cleanup as a normal quit, then exit (T7/D65). tao/Tauri
            // installs no signal handlers of its own, so without this a terminal `kill`, a
            // session-logout script, or any supervisor's stop would terminate the app with the
            // OS default action — no RunEvent, no destructors — orphaning the engine/embedder/
            // agent children (found by T7's real lifecycle QA). `app_handle.exit(0)` fires
            // `RunEvent::Exit`, whose handler below runs `kill_backend`/`kill_agent` again —
            // both are idempotent, so the double call is harmless (same reasoning as handling
            // both `ExitRequested` and `Exit` there). PR_SET_PDEATHSIG on the spawned children
            // (backend.rs) remains the last-resort backstop for SIGKILL/crashes, which no
            // in-process handler can ever observe.
            #[cfg(unix)]
            {
                let app_handle = app.handle().clone();
                tauri::async_runtime::spawn(async move {
                    use tokio::signal::unix::{signal, SignalKind};
                    let mut sigterm = match signal(SignalKind::terminate()) {
                        Ok(stream) => stream,
                        Err(e) => {
                            eprintln!("signal handler: installing SIGTERM listener failed: {e}");
                            return;
                        }
                    };
                    let mut sigint = match signal(SignalKind::interrupt()) {
                        Ok(stream) => stream,
                        Err(e) => {
                            eprintln!("signal handler: installing SIGINT listener failed: {e}");
                            return;
                        }
                    };
                    tokio::select! {
                        _ = sigterm.recv() => {}
                        _ = sigint.recv() => {}
                    }
                    let backend_state = app_handle.state::<backend::BackendState>();
                    backend::kill_backend(&app_handle, &backend_state).await;
                    agent::kill_agent(&app_handle).await;
                    app_handle.exit(0);
                });
            }

            // Auto-start the local backend on launch when this install is already provisioned —
            // so returning to "local" mode lands straight in a working workbench instead of
            // requiring the user to re-click through the wizard/settings every time. Only
            // applies when `mode == "local"` (client mode has no backend to manage) and only
            // when engine+embedder+model are all installed already; otherwise this silently
            // does nothing and the wizard/settings Start button remains the only way in.
            // `backend_start`'s own already-starting/running guard (backend.rs) is a no-op, so
            // this can never race a subsequent explicit `backend_start` call into a double-spawn.
            if mode.as_deref() == Some("local") {
                let app_handle = app.handle().clone();
                tauri::async_runtime::spawn(async move {
                    let cfg = app_handle
                        .state::<config::ConfigState>()
                        .0
                        .lock()
                        .expect("config mutex poisoned")
                        .clone();
                    match provisioning::all_installed(&app_handle, &cfg).await {
                        Ok(true) => {
                            let config_state = app_handle.state::<config::ConfigState>();
                            let backend_state = app_handle.state::<backend::BackendState>();
                            if let Err(e) = backend::backend_start(
                                app_handle.clone(),
                                config_state,
                                backend_state,
                            )
                            .await
                            {
                                eprintln!("auto-start: backend_start failed: {e}");
                            }
                        }
                        Ok(false) => {
                            eprintln!(
                                "auto-start: skipping — components not fully provisioned yet"
                            );
                        }
                        Err(e) => {
                            eprintln!("auto-start: checking installed components failed: {e}");
                        }
                    }
                });
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            config::app_config_get,
            config::app_config_set,
            provisioning::provisioning_status,
            provisioning::provision_start,
            provisioning::provision_cancel,
            backend::backend_start,
            backend::backend_stop,
            backend::backend_status,
            agent::agent_start,
            agent::agent_stop,
            agent::agent_status,
            agent::agent_sync_once,
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            // Best-effort, synchronous-from-here cleanup so quitting the app never leaves an
            // orphaned engine/embedder/agent process behind. Both `ExitRequested` (the normal
            // "last window closed" / quit path) and `Exit` (belt-and-suspenders — e.g. a
            // programmatic `app.exit()`) run it; `kill_backend`/`kill_agent` are idempotent (a
            // second call finds nothing left to kill), so handling both is harmless.
            if matches!(
                event,
                tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
            ) {
                let backend_state = app_handle.state::<backend::BackendState>();
                tauri::async_runtime::block_on(async {
                    backend::kill_backend(app_handle, &backend_state).await;
                    agent::kill_agent(app_handle).await;
                });
            }
        });
}
