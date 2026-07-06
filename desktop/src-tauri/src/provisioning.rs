// Manifest-driven provisioning: download → sha256-verify → unpack, for the three components
// (`engine`, `embedder`, `model`) named in `desktop/provisioning/manifest.json` (schema 1).
//
// `manifest_url: null` in AppConfig resolves to `DEFAULT_MANIFEST_URL`; both the manifest URL
// and each component's own `url` field may be `file://` (tonight's E2E points at locally built
// artifacts) as well as `http(s)://`.
//
// `backend.rs` re-resolves the manifest at `backend_start` time to read `binary_path` — the
// manifest is the single source of truth for where the executable lives inside an unpacked
// archive, so there's no separate copy of that fact to keep in sync.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, OnceLock};
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, State};
use tokio::io::AsyncWriteExt;

use crate::config::{AppConfig, ConfigState};
use crate::paths;

pub const DEFAULT_MANIFEST_URL: &str =
    "https://raw.githubusercontent.com/AetherisAI/condense/main/desktop/provisioning/manifest.json";

/// The only manifest schema this build understands (`desktop/provisioning/manifest.json`'s own
/// `"schema": 1`). Bumped in lockstep if the shape ever changes incompatibly.
const SUPPORTED_MANIFEST_SCHEMA: u32 = 1;

/// The repo's own `desktop/provisioning/manifest.json`, frozen into the binary at compile time —
/// the resilience fallback `resolve_manifest_with_source` reaches for when `DEFAULT_MANIFEST_URL`
/// can't be fetched (e.g. a laptop that never cloned the — private — repo gets a fast 404 from
/// `raw.githubusercontent.com`, found 2026-07-06 chasing the first-run "stuck on the loading logo"
/// bug: `provisioning_status` rejected almost immediately, but nothing ever caught the rejection).
/// The embedder/model URLs in this frozen copy are public (llama.cpp GitHub release, HuggingFace)
/// so those two components install for real off this fallback alone; only `engine` still needs a
/// real tagged release/manifest override, and its own per-component error+Retry (already wired in
/// `provision_component`) covers that honestly if its download 404s.
const EMBEDDED_MANIFEST_JSON: &str = include_str!("../../provisioning/manifest.json");

/// Shared client for every manifest/download request in this module — built once so its
/// connection pool is reused rather than rebuilt per call. `connect_timeout` bounds only the TCP
/// (+TLS) handshake: a silently-dropped SYN or a hung proxy fails fast instead of hanging forever
/// (found in the same investigation: neither `reqwest::get` call in this file had ANY timeout set
/// — fine against a live server that answers fast either way, as `raw.githubusercontent.com` did
/// here, but a real hang-until-the-user-gives-up risk on a flaky network). Deliberately does NOT
/// set a client-wide total `.timeout()` — component archives/models can legitimately take minutes
/// to download; only the (small, JSON) manifest fetch gets a total-duration cap, applied per
/// request in `fetch_manifest` below.
fn http_client() -> &'static reqwest::Client {
    static CLIENT: OnceLock<reqwest::Client> = OnceLock::new();
    CLIENT.get_or_init(|| {
        reqwest::Client::builder()
            .connect_timeout(Duration::from_secs(10))
            .build()
            .expect("building shared reqwest client")
    })
}

/// Where a successfully resolved `Manifest` came from — surfaced to the wizard (`provisioning_status`'s
/// `source` field) as a notice rather than a silent substitution.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum ManifestSource {
    Remote,
    EmbeddedFallback,
}

// ---------------------------------------------------------------------------------------------
// Manifest shape
// ---------------------------------------------------------------------------------------------

#[derive(Debug, Clone, Deserialize)]
pub struct ManifestTarget {
    pub url: String,
    #[serde(default)]
    pub sha256: Option<String>,
    #[serde(default)]
    pub size: Option<u64>,
    /// Path to the executable, relative to the component's unpacked directory (e.g.
    /// `"llama-b9878/llama-server"`) — present for `engine`/`embedder` targets.
    #[serde(default)]
    pub binary_path: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct EngineManifest {
    pub version: String,
    pub targets: HashMap<String, ManifestTarget>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct EmbedderManifest {
    pub name: String,
    pub build: String,
    pub targets: HashMap<String, ManifestTarget>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ModelManifest {
    pub name: String,
    pub file: String,
    pub url: String,
    #[serde(default)]
    pub sha256: Option<String>,
    #[serde(default)]
    pub size: Option<u64>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Manifest {
    pub schema: u32,
    pub engine: EngineManifest,
    pub embedder: EmbedderManifest,
    pub model: ModelManifest,
}

pub fn resolve_manifest_url(cfg: &AppConfig) -> String {
    cfg.manifest_url
        .clone()
        .unwrap_or_else(|| DEFAULT_MANIFEST_URL.to_string())
}

/// Fetch + parse the manifest. Supports `file://` (read straight off disk — tonight's E2E and
/// any offline override) and `http(s)://` (the shipped default).
pub async fn fetch_manifest(url: &str) -> Result<Manifest, String> {
    let body = if let Some(path) = url.strip_prefix("file://") {
        tokio::fs::read_to_string(path)
            .await
            .map_err(|e| format!("reading manifest at {path}: {e}"))?
    } else {
        // Total-duration cap on top of the client's `connect_timeout` — the manifest is a small
        // JSON file, so 30s total (connect + transfer) is generous without risking an indefinite
        // hang if the connection stalls mid-response.
        let resp = http_client()
            .get(url)
            .timeout(Duration::from_secs(30))
            .send()
            .await
            .map_err(|e| format!("fetching manifest {url}: {e}"))?;
        if !resp.status().is_success() {
            return Err(format!("fetching manifest {url}: HTTP {}", resp.status()));
        }
        resp.text()
            .await
            .map_err(|e| format!("reading manifest response from {url}: {e}"))?
    };
    let manifest: Manifest =
        serde_json::from_str(&body).map_err(|e| format!("parsing manifest from {url}: {e}"))?;
    if manifest.schema != SUPPORTED_MANIFEST_SCHEMA {
        return Err(format!(
            "manifest at {url} has schema {} — this build only understands schema {}",
            manifest.schema, SUPPORTED_MANIFEST_SCHEMA
        ));
    }
    Ok(manifest)
}

fn parse_embedded_manifest() -> Result<Manifest, String> {
    let manifest: Manifest = serde_json::from_str(EMBEDDED_MANIFEST_JSON)
        .map_err(|e| format!("parsing embedded manifest: {e}"))?;
    if manifest.schema != SUPPORTED_MANIFEST_SCHEMA {
        return Err(format!(
            "embedded manifest has schema {} — this build only understands schema {}",
            manifest.schema, SUPPORTED_MANIFEST_SCHEMA
        ));
    }
    Ok(manifest)
}

/// Resolve `AppConfig.manifest_url` and fetch it, falling back to the manifest embedded at build
/// time (see `EMBEDDED_MANIFEST_JSON`) if that fetch fails AND the config is still on the baked
/// default (`cfg.manifest_url.is_none()`) — an explicit override (a hand-set `file://`/`http(s)://`
/// URL, e.g. local E2E or a manual laptop workaround) failing is the user's own configuration, so
/// silently swapping in the repo default there would hide a real misconfiguration instead of
/// surfacing it.
pub async fn resolve_manifest_with_source(
    cfg: &AppConfig,
) -> Result<(Manifest, ManifestSource), String> {
    let url = resolve_manifest_url(cfg);
    match fetch_manifest(&url).await {
        Ok(manifest) => Ok((manifest, ManifestSource::Remote)),
        Err(fetch_err) => {
            if cfg.manifest_url.is_some() {
                return Err(fetch_err);
            }
            eprintln!(
                "provisioning: remote manifest fetch failed ({fetch_err}) — falling back to the \
                 manifest embedded at build time"
            );
            let manifest = parse_embedded_manifest().map_err(|embed_err| {
                format!("{fetch_err}; embedded fallback also failed: {embed_err}")
            })?;
            Ok((manifest, ManifestSource::EmbeddedFallback))
        }
    }
}

/// Convenience: resolve `AppConfig.manifest_url` and fetch it in one call, discarding which
/// source it came from. Used by `provision_start` here and by `backend::backend_start` (which
/// needs `binary_path` for the current target) — neither needs to report the fallback notice, only
/// `provisioning_status` (the wizard-facing one) does.
pub async fn resolve_manifest(cfg: &AppConfig) -> Result<Manifest, String> {
    resolve_manifest_with_source(cfg).await.map(|(m, _)| m)
}

// ---------------------------------------------------------------------------------------------
// Installed marker (`.installed.json`, written after a successful archive unpack)
// ---------------------------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
struct InstalledMarker {
    version: String,
}

fn read_marker_version(dir: &Path) -> Option<String> {
    let data = std::fs::read_to_string(dir.join(".installed.json")).ok()?;
    serde_json::from_str::<InstalledMarker>(&data)
        .ok()
        .map(|m| m.version)
}

// ---------------------------------------------------------------------------------------------
// Installed checks — shared by `provisioning_status` (per-component detail for the wizard) and
// `all_installed` (the aggregate gate `lib.rs`'s auto-start-on-launch setup hook uses).
// ---------------------------------------------------------------------------------------------

struct InstalledFlags {
    engine: bool,
    embedder: bool,
    model: bool,
}

fn installed_flags(app: &AppHandle, manifest: &Manifest) -> Result<InstalledFlags, String> {
    let engine_dir = paths::runtime_engine_dir(app)?;
    let embedder_dir = paths::runtime_embedder_dir(app)?;
    let model_path = paths::models_dir(app)?.join(&manifest.model.file);

    let engine = engine_dir.join(".installed.json").exists();
    let embedder = embedder_dir.join(".installed.json").exists();
    let model = model_path.exists()
        && match manifest.model.size {
            Some(expected) => std::fs::metadata(&model_path)
                .map(|m| m.len() == expected)
                .unwrap_or(false),
            None => true,
        };
    Ok(InstalledFlags {
        engine,
        embedder,
        model,
    })
}

/// Whether engine, embedder, and model are all fully installed for `cfg`'s resolved manifest.
/// Used by `lib.rs`'s `.setup()` to decide whether it's safe to auto-start the backend
/// unattended on launch, without re-provisioning or prompting.
pub async fn all_installed(app: &AppHandle, cfg: &AppConfig) -> Result<bool, String> {
    let manifest = resolve_manifest(cfg).await?;
    let flags = installed_flags(app, &manifest)?;
    Ok(flags.engine && flags.embedder && flags.model)
}

// ---------------------------------------------------------------------------------------------
// provisioning_status
// ---------------------------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize)]
pub struct ComponentStatus {
    pub id: String,
    pub name: String,
    pub installed: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size_bytes: Option<u64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProvisioningStatusResponse {
    pub components: Vec<ComponentStatus>,
    pub manifest_url: String,
    pub source: ManifestSource,
}

#[tauri::command]
pub async fn provisioning_status(
    app: AppHandle,
    config_state: State<'_, ConfigState>,
) -> Result<ProvisioningStatusResponse, String> {
    let cfg = {
        config_state
            .0
            .lock()
            .expect("config mutex poisoned")
            .clone()
    };
    let manifest_url = resolve_manifest_url(&cfg);
    let (manifest, source) = resolve_manifest_with_source(&cfg).await?;

    let engine_dir = paths::runtime_engine_dir(&app)?;
    let embedder_dir = paths::runtime_embedder_dir(&app)?;

    let engine_target = manifest.engine.targets.get(paths::TARGET_TRIPLE);
    let embedder_target = manifest.embedder.targets.get(paths::TARGET_TRIPLE);

    let flags = installed_flags(&app, &manifest)?;

    let components = vec![
        ComponentStatus {
            id: "engine".to_string(),
            name: "Condense Engine".to_string(),
            installed: flags.engine,
            version: if flags.engine {
                read_marker_version(&engine_dir)
            } else {
                Some(manifest.engine.version.clone())
            },
            size_bytes: engine_target.and_then(|t| t.size),
        },
        ComponentStatus {
            id: "embedder".to_string(),
            name: manifest.embedder.name.clone(),
            installed: flags.embedder,
            version: if flags.embedder {
                read_marker_version(&embedder_dir)
            } else {
                Some(manifest.embedder.build.clone())
            },
            size_bytes: embedder_target.and_then(|t| t.size),
        },
        ComponentStatus {
            id: "model".to_string(),
            name: manifest.model.name.clone(),
            installed: flags.model,
            version: None,
            size_bytes: manifest.model.size,
        },
    ];

    Ok(ProvisioningStatusResponse {
        components,
        manifest_url,
        source,
    })
}

// ---------------------------------------------------------------------------------------------
// provision_start / provision_cancel
// ---------------------------------------------------------------------------------------------

#[derive(Default)]
pub struct ProvisionState {
    pub cancel_flag: Arc<AtomicBool>,
}

#[derive(Debug, Clone, Serialize)]
struct ProgressEvent<'a> {
    id: &'a str,
    phase: &'a str,
    downloaded: u64,
    total: u64,
}

fn emit_progress(app: &AppHandle, id: &str, phase: &str, downloaded: u64, total: u64) {
    let _ = app.emit(
        "provision-progress",
        ProgressEvent {
            id,
            phase,
            downloaded,
            total,
        },
    );
}

#[derive(Debug, Clone, Serialize)]
struct ErrorEvent<'a> {
    id: &'a str,
    error: &'a str,
}

fn emit_error(app: &AppHandle, id: &str, error: &str) {
    let _ = app.emit("provision-error", ErrorEvent { id, error });
}

#[tauri::command]
pub async fn provision_start(
    app: AppHandle,
    config_state: State<'_, ConfigState>,
    provision_state: State<'_, ProvisionState>,
    ids: Vec<String>,
) -> Result<(), String> {
    let cfg = {
        config_state
            .0
            .lock()
            .expect("config mutex poisoned")
            .clone()
    };
    let manifest = resolve_manifest(&cfg).await?;

    provision_state.cancel_flag.store(false, Ordering::SeqCst);
    let cancel_flag = provision_state.cancel_flag.clone();
    let app_for_task = app.clone();

    tauri::async_runtime::spawn(async move {
        for id in ids {
            if cancel_flag.load(Ordering::SeqCst) {
                break;
            }
            match provision_component(&app_for_task, &manifest, &id, cancel_flag.clone()).await {
                Ok(()) => {}
                Err(e) if e == "cancelled" => break,
                Err(e) => {
                    emit_error(&app_for_task, &id, &e);
                    // Keep going with the remaining requested ids rather than aborting the whole
                    // batch on one component's failure — each id reports its own error event.
                }
            }
        }
    });

    Ok(())
}

#[tauri::command]
pub fn provision_cancel(provision_state: State<ProvisionState>) -> Result<(), String> {
    provision_state.cancel_flag.store(true, Ordering::SeqCst);
    Ok(())
}

// ---------------------------------------------------------------------------------------------
// Per-component provisioning
// ---------------------------------------------------------------------------------------------

async fn provision_component(
    app: &AppHandle,
    manifest: &Manifest,
    id: &str,
    cancel_flag: Arc<AtomicBool>,
) -> Result<(), String> {
    match id {
        "engine" => {
            let target = manifest
                .engine
                .targets
                .get(paths::TARGET_TRIPLE)
                .ok_or_else(|| format!("no engine build for target '{}'", paths::TARGET_TRIPLE))?;
            provision_archive_component(
                app,
                ArchiveComponent {
                    id: "engine",
                    version: manifest.engine.version.clone(),
                    url: target.url.clone(),
                    sha256: target.sha256.clone(),
                    size: target.size,
                    dest_dir: paths::runtime_engine_dir(app)?,
                },
                cancel_flag,
            )
            .await
        }
        "embedder" => {
            let target = manifest
                .embedder
                .targets
                .get(paths::TARGET_TRIPLE)
                .ok_or_else(|| {
                    format!("no embedder build for target '{}'", paths::TARGET_TRIPLE)
                })?;
            provision_archive_component(
                app,
                ArchiveComponent {
                    id: "embedder",
                    version: manifest.embedder.build.clone(),
                    url: target.url.clone(),
                    sha256: target.sha256.clone(),
                    size: target.size,
                    dest_dir: paths::runtime_embedder_dir(app)?,
                },
                cancel_flag,
            )
            .await
        }
        "model" => provision_model(app, manifest, cancel_flag).await,
        other => Err(format!("unknown component id '{other}'")),
    }
}

struct ArchiveComponent {
    id: &'static str,
    version: String,
    url: String,
    sha256: Option<String>,
    size: Option<u64>,
    dest_dir: PathBuf,
}

async fn provision_archive_component(
    app: &AppHandle,
    comp: ArchiveComponent,
    cancel_flag: Arc<AtomicBool>,
) -> Result<(), String> {
    let tmp = paths::ensure_dir(paths::tmp_dir(app)?)?;
    let archive_path = tmp.join(format!("{}.download.partial", comp.id));

    download(
        app,
        comp.id,
        &comp.url,
        &archive_path,
        comp.size,
        &cancel_flag,
    )
    .await?;
    if cancel_flag.load(Ordering::SeqCst) {
        let _ = tokio::fs::remove_file(&archive_path).await;
        return Err("cancelled".to_string());
    }

    let total = comp.size.unwrap_or(0);
    emit_progress(app, comp.id, "verifying", total, total);
    match &comp.sha256 {
        Some(expected) => verify_sha256(archive_path.clone(), expected.clone()).await?,
        None => eprintln!(
            "provisioning: manifest has no sha256 for '{}' — skipping verification",
            comp.id
        ),
    }

    emit_progress(app, comp.id, "unpacking", total, total);
    let kind = archive_kind_from_url(&comp.url)?;
    let extract_dir = tmp.join(format!("{}-extract", comp.id));
    if extract_dir.exists() {
        tokio::fs::remove_dir_all(&extract_dir)
            .await
            .map_err(|e| format!("clearing {}: {e}", extract_dir.display()))?;
    }
    tokio::fs::create_dir_all(&extract_dir)
        .await
        .map_err(|e| format!("creating {}: {e}", extract_dir.display()))?;
    unpack_archive(kind, archive_path.clone(), extract_dir.clone()).await?;
    let _ = tokio::fs::remove_file(&archive_path).await;

    if comp.dest_dir.exists() {
        tokio::fs::remove_dir_all(&comp.dest_dir)
            .await
            .map_err(|e| format!("clearing {}: {e}", comp.dest_dir.display()))?;
    }
    if let Some(parent) = comp.dest_dir.parent() {
        tokio::fs::create_dir_all(parent)
            .await
            .map_err(|e| format!("creating {}: {e}", parent.display()))?;
    }
    tokio::fs::rename(&extract_dir, &comp.dest_dir)
        .await
        .map_err(|e| format!("moving {} into place: {e}", comp.dest_dir.display()))?;

    let marker = InstalledMarker {
        version: comp.version,
    };
    let marker_json =
        serde_json::to_string_pretty(&marker).map_err(|e| format!("serializing marker: {e}"))?;
    tokio::fs::write(comp.dest_dir.join(".installed.json"), marker_json)
        .await
        .map_err(|e| format!("writing installed marker: {e}"))?;

    emit_progress(app, comp.id, "done", total, total);
    Ok(())
}

async fn provision_model(
    app: &AppHandle,
    manifest: &Manifest,
    cancel_flag: Arc<AtomicBool>,
) -> Result<(), String> {
    let id = "model";
    let dest = paths::models_dir(app)?.join(&manifest.model.file);
    let tmp = paths::ensure_dir(paths::tmp_dir(app)?)?;
    let partial = tmp.join(format!("{id}.download.partial"));

    download(
        app,
        id,
        &manifest.model.url,
        &partial,
        manifest.model.size,
        &cancel_flag,
    )
    .await?;
    if cancel_flag.load(Ordering::SeqCst) {
        let _ = tokio::fs::remove_file(&partial).await;
        return Err("cancelled".to_string());
    }

    let total = manifest.model.size.unwrap_or(0);
    emit_progress(app, id, "verifying", total, total);
    match &manifest.model.sha256 {
        Some(expected) => verify_sha256(partial.clone(), expected.clone()).await?,
        None => {
            eprintln!("provisioning: manifest has no sha256 for 'model' — skipping verification")
        }
    }

    if let Some(parent) = dest.parent() {
        tokio::fs::create_dir_all(parent)
            .await
            .map_err(|e| format!("creating {}: {e}", parent.display()))?;
    }
    tokio::fs::rename(&partial, &dest)
        .await
        .map_err(|e| format!("moving {} into place: {e}", dest.display()))?;

    emit_progress(app, id, "done", total, total);
    Ok(())
}

// ---------------------------------------------------------------------------------------------
// Download (http/https via reqwest, file:// via a plain copy) + sha256 + unpack primitives
// ---------------------------------------------------------------------------------------------

async fn download(
    app: &AppHandle,
    id: &str,
    url: &str,
    dest: &Path,
    expected_size: Option<u64>,
    cancel_flag: &Arc<AtomicBool>,
) -> Result<(), String> {
    if let Some(local_path) = url.strip_prefix("file://") {
        // Local artifact (tonight's E2E uses locally built bundles) — no real "downloading" to
        // stream, but still emit progress so the UI has something honest to show.
        let size = tokio::fs::metadata(local_path)
            .await
            .map(|m| m.len())
            .unwrap_or(0);
        let total = expected_size.unwrap_or(size);
        emit_progress(app, id, "downloading", 0, total);
        tokio::fs::copy(local_path, dest)
            .await
            .map_err(|e| format!("copying {local_path}: {e}"))?;
        emit_progress(app, id, "downloading", size, total);
        return Ok(());
    }

    // No total `.timeout()` here on purpose (see `http_client`'s doc comment) — a multi-hundred-MB
    // component download can legitimately run for minutes; only the connect phase is bounded.
    let mut resp = http_client()
        .get(url)
        .send()
        .await
        .map_err(|e| format!("requesting {url}: {e}"))?;
    if !resp.status().is_success() {
        return Err(format!("downloading {url}: HTTP {}", resp.status()));
    }
    let total = resp.content_length().or(expected_size).unwrap_or(0);

    let mut file = tokio::fs::File::create(dest)
        .await
        .map_err(|e| format!("creating {}: {e}", dest.display()))?;
    let mut downloaded: u64 = 0;
    let mut last_emit = Instant::now();
    emit_progress(app, id, "downloading", 0, total);

    loop {
        if cancel_flag.load(Ordering::SeqCst) {
            drop(file);
            let _ = tokio::fs::remove_file(dest).await;
            return Err("cancelled".to_string());
        }
        match resp
            .chunk()
            .await
            .map_err(|e| format!("reading response from {url}: {e}"))?
        {
            Some(chunk) => {
                file.write_all(&chunk)
                    .await
                    .map_err(|e| format!("writing {}: {e}", dest.display()))?;
                downloaded += chunk.len() as u64;
                if last_emit.elapsed() >= Duration::from_millis(250) {
                    emit_progress(app, id, "downloading", downloaded, total);
                    last_emit = Instant::now();
                }
            }
            None => break,
        }
    }
    file.flush()
        .await
        .map_err(|e| format!("flushing {}: {e}", dest.display()))?;
    emit_progress(app, id, "downloading", downloaded, total.max(downloaded));
    Ok(())
}

async fn verify_sha256(path: PathBuf, expected: String) -> Result<(), String> {
    let path_for_error = path.clone();
    let actual = tokio::task::spawn_blocking(move || sha256_hex(&path))
        .await
        .map_err(|e| format!("hashing task panicked: {e}"))??;
    if actual != expected {
        return Err(format!(
            "sha256 mismatch for {}: expected {expected}, got {actual}",
            path_for_error.display()
        ));
    }
    Ok(())
}

fn sha256_hex(path: &Path) -> Result<String, String> {
    use sha2::{Digest, Sha256};
    use std::io::Read;

    let mut file =
        std::fs::File::open(path).map_err(|e| format!("opening {}: {e}", path.display()))?;
    let mut hasher = Sha256::new();
    let mut buf = [0u8; 65536];
    loop {
        let n = file
            .read(&mut buf)
            .map_err(|e| format!("reading {}: {e}", path.display()))?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(hasher
        .finalize()
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect())
}

enum ArchiveKind {
    TarGz,
    Zip,
}

fn archive_kind_from_url(url: &str) -> Result<ArchiveKind, String> {
    let path = url.split(['?', '#']).next().unwrap_or(url);
    if path.ends_with(".zip") {
        Ok(ArchiveKind::Zip)
    } else if path.ends_with(".tar.gz") || path.ends_with(".tgz") {
        Ok(ArchiveKind::TarGz)
    } else {
        Err(format!("unrecognized archive extension in url: {url}"))
    }
}

async fn unpack_archive(
    kind: ArchiveKind,
    archive_path: PathBuf,
    dest_dir: PathBuf,
) -> Result<(), String> {
    tokio::task::spawn_blocking(move || match kind {
        ArchiveKind::TarGz => unpack_tar_gz(&archive_path, &dest_dir),
        ArchiveKind::Zip => unpack_zip(&archive_path, &dest_dir),
    })
    .await
    .map_err(|e| format!("unpack task panicked: {e}"))?
}

fn unpack_tar_gz(archive_path: &Path, dest_dir: &Path) -> Result<(), String> {
    let file = std::fs::File::open(archive_path)
        .map_err(|e| format!("opening {}: {e}", archive_path.display()))?;
    let decoder = flate2::read::GzDecoder::new(file);
    let mut archive = tar::Archive::new(decoder);
    archive
        .unpack(dest_dir)
        .map_err(|e| format!("unpacking {}: {e}", archive_path.display()))
}

fn unpack_zip(archive_path: &Path, dest_dir: &Path) -> Result<(), String> {
    let file = std::fs::File::open(archive_path)
        .map_err(|e| format!("opening {}: {e}", archive_path.display()))?;
    let mut archive = zip::ZipArchive::new(file)
        .map_err(|e| format!("reading zip {}: {e}", archive_path.display()))?;
    archive
        .extract(dest_dir)
        .map_err(|e| format!("unpacking {}: {e}", archive_path.display()))
}
