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
            app.manage(config::ConfigState(std::sync::Mutex::new(initial_config)));
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
