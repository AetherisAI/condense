// AppConfig — `config.json` in `app.path().app_config_dir()` (Linux:
// `~/.config/ai.aetheris.condense/config.json`). Schema 1.
// `mode: null` means "first run" (SetupWizard); `manifest_url: null` resolves to the baked
// default in `provisioning.rs`. Never log `llm.api_key` or `ingest_token`.

use std::path::PathBuf;
use std::sync::Mutex;

use rand::rngs::OsRng;
use rand::RngCore;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, State};

pub const CONFIG_SCHEMA: u32 = 1;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LlmConfig {
    #[serde(default)]
    pub base_url: String,
    #[serde(default)]
    pub model: String,
    #[serde(default)]
    pub api_key: String,
}

impl Default for LlmConfig {
    fn default() -> Self {
        Self {
            base_url: String::new(),
            model: String::new(),
            api_key: String::new(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AgentSettings {
    #[serde(default)]
    pub paths: Vec<String>,
    #[serde(default)]
    pub delete_removed: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub schema: u32,
    /// "local" | "client" | null (null = first run, not yet configured)
    pub mode: Option<String>,
    pub engine_port: u16,
    pub embedder_port: u16,
    /// The bge-reranker-v2-m3 llama-server sidecar. `serde(default)` so a `config.json`
    /// written before the reranker existed still loads, and picks up 8803.
    #[serde(default = "default_reranker_port")]
    pub reranker_port: u16,
    /// Generated once on first read; a 32-hex-char CSPRNG token (never logged).
    pub ingest_token: String,
    #[serde(default)]
    pub llm: LlmConfig,
    /// null resolves to the baked default manifest URL (see `provisioning::DEFAULT_MANIFEST_URL`).
    pub manifest_url: Option<String>,
    #[serde(default)]
    pub agent: AgentSettings,
    /// The System drawer's "Rerank Find & Ask" switch, passed to the engine as
    /// `TOOLS_SEARCH_RERANK` at start so it survives restarts (the drawer's `PATCH /settings`
    /// alone is in-memory). Off by default.
    #[serde(default)]
    pub tools_search_rerank: bool,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            schema: CONFIG_SCHEMA,
            mode: None,
            engine_port: 8801,
            embedder_port: 8802,
            reranker_port: default_reranker_port(),
            ingest_token: generate_token(),
            llm: LlmConfig::default(),
            manifest_url: None,
            agent: AgentSettings::default(),
            tools_search_rerank: false,
        }
    }
}

fn default_reranker_port() -> u16 {
    8803
}

/// 32 hex chars from a CSPRNG (rand's `OsRng`, backed by the `getrandom` crate) — 16 random
/// bytes, hex-encoded.
fn generate_token() -> String {
    let mut bytes = [0u8; 16];
    OsRng.fill_bytes(&mut bytes);
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

pub struct ConfigState(pub Mutex<AppConfig>);

fn config_path(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_config_dir()
        .map_err(|e| format!("resolving app config dir: {e}"))?;
    std::fs::create_dir_all(&dir).map_err(|e| format!("creating {}: {e}", dir.display()))?;
    Ok(dir.join("config.json"))
}

fn write_config(path: &PathBuf, cfg: &AppConfig) -> Result<(), String> {
    let data = serde_json::to_string_pretty(cfg).map_err(|e| format!("serializing config: {e}"))?;
    std::fs::write(path, data).map_err(|e| format!("writing {}: {e}", path.display()))
}

/// Load `config.json`, creating it with defaults (including a freshly generated `ingest_token`)
/// on first run. Called once from `lib.rs`'s `.setup()` to seed the managed `ConfigState`.
pub fn load_or_init(app: &AppHandle) -> Result<AppConfig, String> {
    let path = config_path(app)?;
    if path.exists() {
        let data = std::fs::read_to_string(&path)
            .map_err(|e| format!("reading {}: {e}", path.display()))?;
        serde_json::from_str(&data).map_err(|e| format!("parsing {}: {e}", path.display()))
    } else {
        let cfg = AppConfig::default();
        write_config(&path, &cfg)?;
        Ok(cfg)
    }
}

#[tauri::command]
pub fn app_config_get(state: State<ConfigState>) -> AppConfig {
    state.0.lock().expect("config mutex poisoned").clone()
}

#[tauri::command]
pub fn app_config_set(
    app: AppHandle,
    state: State<ConfigState>,
    config: AppConfig,
) -> Result<AppConfig, String> {
    let path = config_path(&app)?;
    write_config(&path, &config)?;
    *state.0.lock().expect("config mutex poisoned") = config.clone();
    Ok(config)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn config_written_before_the_reranker_loads_with_its_default_port() {
        let pre_d89 = r#"{"schema":1,"mode":"local","engine_port":8801,"embedder_port":8802,
            "ingest_token":"abc","llm":{"base_url":"","model":"","api_key":""},
            "manifest_url":null,"agent":{"paths":[],"delete_removed":false}}"#;
        let cfg: AppConfig = serde_json::from_str(pre_d89).expect("old config parses");
        assert_eq!(cfg.reranker_port, 8803);
        assert_eq!(cfg.embedder_port, 8802);
        assert!(!cfg.tools_search_rerank);
    }
}
