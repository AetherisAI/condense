// Condense desktop shell — Tauri 2 application entry.
//
// `run()` is the single composition root the Tauri mobile entry point and the
// desktop `main.rs` both call into. Tonight's scope (T4) is scaffold-only: the
// window, the shell + dialog plugins, no custom commands yet. T5 (Rust
// provisioning + supervision) adds `config`, `provisioning`, `backend`, and
// `agent` modules here — keep this function a plain builder chain so those
// modules slot in as `.manage(...)` state and `.invoke_handler(...)` additions
// without restructuring it.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
