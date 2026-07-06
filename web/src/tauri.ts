/**
 * Typed wrappers for the Tauri command contract pinned in `docs/Quentin/active/machine.md`
 * (D60/T2 — the seam both the Rust and React tracks build against; names/shapes here must never
 * drift from that doc without updating it too). Every export delegates to the real
 * `@tauri-apps/api` bridge when `isRealTauri`, else to a deterministic in-memory mock — the
 * `forceTauri` dev/QA seam (`platform.ts`) lets the whole wizard + desktop settings surface be
 * exercised in an ordinary browser tab against these mocks, with no Tauri build involved.
 *
 * Mock state lives in module-level variables only — it resets on every page reload, which is
 * exactly the "cleared mock state" QA seam: reload the tab to get a fresh first-run config.
 */

import { invoke } from '@tauri-apps/api/core'
import { listen as tauriListen, type Event as TauriEvent } from '@tauri-apps/api/event'
import { open as tauriOpenDialog } from '@tauri-apps/plugin-dialog'
import { isRealTauri } from './platform'

// ---- Wire types (mirror the command contract exactly) -----------------------------------------

export type AppMode = 'local' | 'client' | null

export type AppConfig = {
  schema: 1
  mode: AppMode
  engine_port: number
  embedder_port: number
  ingest_token: string
  llm: { base_url: string; model: string; api_key: string }
  manifest_url: string | null
  agent: { paths: string[]; delete_removed: boolean }
}

export type ComponentId = 'engine' | 'embedder' | 'model'

export type ProvisioningComponent = {
  id: ComponentId
  name: string
  installed: boolean
  version?: string
  size_bytes?: number
}

export type ProvisioningStatus = {
  components: ProvisioningComponent[]
  manifest_url: string
  /** `'embedded-fallback'` when the remote manifest fetch failed and the Rust side fell back to
   * the copy baked into the binary at build time (`provisioning.rs`'s `include_str!`) — surfaced
   * so the wizard can show a non-blocking notice instead of silently substituting data. */
  source: 'remote' | 'embedded-fallback'
}

/** `'stopped'|'starting'|'running'|'error:<msg>'` — the leading token before any `:` is the
 * state; use `backendStateKind` below rather than comparing this raw string directly. */
export type BackendStateString = string

export type BackendComponentStatus = { state: BackendStateString; port: number; pid?: number }

export type BackendStatus = {
  mode: string
  engine: BackendComponentStatus
  embedder: BackendComponentStatus
}

export type AgentStatus = { running: boolean; user_stopped: boolean; restarts: number }

/** Mirrors the Rust `AgentConfig` (desktop/src-tauri/src/agent.rs) — `server`/`token` are optional
 * there (the Rust side falls back to local-mode values when absent), but every caller in this
 * codebase passes them explicitly per-mode (T6) so the sidecar is never accidentally pointed at
 * the wrong backend. */
export type AgentConfig = {
  paths: string[]
  delete_removed: boolean
  server?: string
  token?: string
}

// ---- Event payloads -----------------------------------------------------------------------

export type ProvisionProgressEvent = {
  id: ComponentId
  phase: 'downloading' | 'verifying' | 'unpacking' | 'done'
  downloaded: number
  total: number
}

export type ProvisionErrorEvent = { id: ComponentId; error: string }

export type BackendStateEvent = { component: 'engine' | 'embedder'; state: BackendStateString; detail?: string }

export type AgentEventPayload = { line: string }

export type AgentTerminatedEvent = { code: number | null; will_restart: boolean }

/** One parsed NDJSON line from the agent CLI's `--json` mode (`agent/cli.py`, D54) — the exact
 * shapes `emit()` prints there. `dry_run` is real but never emitted in `--watch` mode (which is
 * all the desktop supervisor ever runs), so it's omitted from this union on purpose. */
export type AgentLine =
  | {
      event: 'sync'
      indexed: number
      replaced: number
      deleted: number
      skipped: number
      failed: number
      failures: { path: string; error: string }[]
      error?: string
    }
  | { event: 'watch_started'; paths: string[]; delete_removed: boolean }
  | { event: 'fatal'; error: string }
  | { event: 'stopped' }

/** Best-effort parse of one `agent-event` line — never throws; returns `null` on anything that
 * isn't the JSON object shape above (a stray non-JSON line should never crash the UI). */
export function parseAgentLine(line: string): AgentLine | null {
  try {
    const parsed: unknown = JSON.parse(line)
    if (typeof parsed === 'object' && parsed !== null && 'event' in parsed) {
      return parsed as AgentLine
    }
    return null
  } catch {
    return null
  }
}

/** The leading state token of a `BackendStateString`, e.g. `'error:connection refused'` -> `'error'`. */
export function backendStateKind(state: BackendStateString): 'stopped' | 'starting' | 'running' | 'error' {
  const kind = state.split(':', 1)[0]
  if (kind === 'starting' || kind === 'running' || kind === 'error') return kind
  return 'stopped'
}

/** The `<msg>` portion of an `error:<msg>` state string, or `null` if not in an error state. */
export function backendStateError(state: BackendStateString): string | null {
  if (backendStateKind(state) !== 'error') return null
  const idx = state.indexOf(':')
  return idx === -1 ? '' : state.slice(idx + 1)
}

// ---- listen: real Tauri events, or the mock bus below ----------------------------------------

export type Unlisten = () => void

const mockListeners = new Map<string, Set<(payload: unknown) => void>>()

function mockEmit<T>(event: string, payload: T): void {
  const set = mockListeners.get(event)
  if (!set) return
  // Copy first — a handler unlistening itself mid-dispatch must not perturb this iteration.
  for (const fn of [...set]) fn(payload)
}

function mockListen<T>(event: string, handler: (payload: T) => void): Unlisten {
  let set = mockListeners.get(event)
  if (!set) {
    set = new Set()
    mockListeners.set(event, set)
  }
  const wrapped = handler as (payload: unknown) => void
  set.add(wrapped)
  return () => set.delete(wrapped)
}

/** Subscribe to a Tauri event (real bridge) or the in-memory mock bus. Returns an unlisten fn,
 * mirroring `@tauri-apps/api/event`'s own `listen()` (which resolves to its unlisten function). */
export async function listenEvent<T>(event: string, handler: (payload: T) => void): Promise<Unlisten> {
  if (isRealTauri) {
    return tauriListen<T>(event, (e: TauriEvent<T>) => handler(e.payload))
  }
  return mockListen(event, handler)
}

// ---- Mock provisioning/backend/agent/config state ---------------------------------------------

function freshConfig(): AppConfig {
  return {
    schema: 1,
    mode: null,
    engine_port: 8801,
    embedder_port: 8802,
    ingest_token: crypto.randomUUID().replace(/-/g, ''),
    llm: { base_url: '', model: '', api_key: '' },
    manifest_url: null,
    agent: { paths: [], delete_removed: false },
  }
}

let mockConfig: AppConfig = freshConfig()

const MOCK_COMPONENTS: Record<ComponentId, { name: string; version: string; size_bytes: number }> = {
  engine: { name: 'Condense engine', version: '0.4.0', size_bytes: 150_000_000 },
  embedder: { name: 'Embedding server (llama-server)', version: 'b9878', size_bytes: 15_000_000 },
  model: { name: 'bge-m3 embedding model', version: 'Q8_0', size_bytes: 605_000_000 },
}

const mockInstalled: Record<ComponentId, boolean> = { engine: false, embedder: false, model: false }

let mockProvisionCancelled = false

let mockBackendState: { engine: BackendStateString; embedder: BackendStateString } = {
  engine: 'stopped',
  embedder: 'stopped',
}

let mockAgentStatus: AgentStatus = { running: false, user_stopped: false, restarts: 0 }
let mockFolderCounter = 0

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// ---- app_config_get / app_config_set ------------------------------------------------------

export async function appConfigGet(): Promise<AppConfig> {
  if (isRealTauri) return invoke<AppConfig>('app_config_get')
  return structuredClone(mockConfig)
}

export async function appConfigSet(config: AppConfig): Promise<AppConfig> {
  if (isRealTauri) return invoke<AppConfig>('app_config_set', { config })
  mockConfig = structuredClone(config)
  return structuredClone(mockConfig)
}

// ---- provisioning_status / provision_start / provision_cancel -----------------------------

export async function provisioningStatus(): Promise<ProvisioningStatus> {
  if (isRealTauri) return invoke<ProvisioningStatus>('provisioning_status')
  // QA seam (D67): `localStorage.setItem('mockManifestFail', '1')` makes this mock reject the way
  // the real command does when the manifest is unreachable. The mock never failing is exactly why
  // the first-run spinner hang (an unhandled provisioning_status rejection) survived browser QA —
  // this makes that whole class of bug reproducible in an ordinary Chrome tab.
  if (localStorage.getItem('mockManifestFail') === '1') {
    throw new Error(
      'fetching manifest https://raw.githubusercontent.com/AetherisAI/condense/main/desktop/provisioning/manifest.json: HTTP 404 Not Found (mocked)',
    )
  }
  return {
    manifest_url: mockConfig.manifest_url ?? 'https://raw.githubusercontent.com/AetherisAI/condense/main/desktop/provisioning/manifest.json',
    source: 'remote',
    components: (Object.keys(MOCK_COMPONENTS) as ComponentId[]).map((id) => ({
      id,
      name: MOCK_COMPONENTS[id].name,
      installed: mockInstalled[id],
      version: mockInstalled[id] ? MOCK_COMPONENTS[id].version : undefined,
      size_bytes: MOCK_COMPONENTS[id].size_bytes,
    })),
  }
}

/** Simulates one component's download → verify → unpack → done over ~2-3s, emitting
 * `provision-progress` (and `provision-error`, never in this deterministic mock) along the way. */
async function mockProvisionOne(id: ComponentId): Promise<void> {
  const total = MOCK_COMPONENTS[id].size_bytes
  const steps = 7
  for (let i = 1; i <= steps; i++) {
    if (mockProvisionCancelled) return
    await sleep(220)
    mockEmit<ProvisionProgressEvent>('provision-progress', {
      id,
      phase: 'downloading',
      downloaded: Math.round((total * i) / steps),
      total,
    })
  }
  if (mockProvisionCancelled) return
  await sleep(180)
  mockEmit<ProvisionProgressEvent>('provision-progress', { id, phase: 'verifying', downloaded: total, total })
  if (mockProvisionCancelled) return
  await sleep(180)
  mockEmit<ProvisionProgressEvent>('provision-progress', { id, phase: 'unpacking', downloaded: total, total })
  if (mockProvisionCancelled) return
  await sleep(150)
  mockInstalled[id] = true
  mockEmit<ProvisionProgressEvent>('provision-progress', { id, phase: 'done', downloaded: total, total })
}

export async function provisionStart(ids: ComponentId[]): Promise<void> {
  if (isRealTauri) {
    await invoke('provision_start', { ids })
    return
  }
  mockProvisionCancelled = false
  // Real provisioning downloads are network-bound and run concurrently per component; the mock
  // mirrors that rather than serializing, so the wizard's aggregate progress behaves the same way.
  await Promise.all(ids.map((id) => mockProvisionOne(id)))
}

export async function provisionCancel(): Promise<void> {
  if (isRealTauri) {
    await invoke('provision_cancel')
    return
  }
  mockProvisionCancelled = true
}

// ---- backend_start / backend_stop / backend_status -----------------------------------------

export async function backendStart(): Promise<void> {
  if (isRealTauri) {
    await invoke('backend_start')
    return
  }
  // Real order: embedder first, then engine, health-polling each before moving on.
  for (const component of ['embedder', 'engine'] as const) {
    mockBackendState[component] = 'starting'
    mockEmit<BackendStateEvent>('backend-state', { component, state: 'starting' })
    await sleep(1500)
    mockBackendState[component] = 'running'
    mockEmit<BackendStateEvent>('backend-state', { component, state: 'running' })
  }
}

export async function backendStop(): Promise<void> {
  if (isRealTauri) {
    await invoke('backend_stop')
    return
  }
  for (const component of ['engine', 'embedder'] as const) {
    mockBackendState[component] = 'stopped'
    mockEmit<BackendStateEvent>('backend-state', { component, state: 'stopped' })
  }
}

export async function backendStatus(): Promise<BackendStatus> {
  if (isRealTauri) return invoke<BackendStatus>('backend_status')
  return {
    mode: mockConfig.mode ?? 'local',
    engine: { state: mockBackendState.engine, port: mockConfig.engine_port },
    embedder: { state: mockBackendState.embedder, port: mockConfig.embedder_port },
  }
}

// ---- agent_start / agent_stop / agent_status -----------------------------------------------

export async function agentStart(cfg: AgentConfig): Promise<void> {
  if (isRealTauri) {
    await invoke('agent_start', { cfg })
    return
  }
  mockAgentStatus = { running: true, user_stopped: false, restarts: mockAgentStatus.restarts }
  void mockAgentRun(cfg)
}

async function mockAgentRun(cfg: AgentConfig): Promise<void> {
  await sleep(400)
  if (!mockAgentStatus.running) return
  mockEmit<AgentEventPayload>('agent-event', {
    line: JSON.stringify({ event: 'watch_started', paths: cfg.paths, delete_removed: cfg.delete_removed }),
  })
  await sleep(900)
  if (!mockAgentStatus.running) return
  mockEmit<AgentEventPayload>('agent-event', {
    line: JSON.stringify({
      event: 'sync',
      indexed: 3,
      replaced: 0,
      deleted: 0,
      skipped: 1,
      failed: 0,
      failures: [],
    }),
  })
  await sleep(900)
  if (!mockAgentStatus.running) return
  // One failure entry on purpose (D60/T2 spec) — exercises the failures-list UI without a real backend.
  mockEmit<AgentEventPayload>('agent-event', {
    line: JSON.stringify({
      event: 'sync',
      indexed: 1,
      replaced: 0,
      deleted: 0,
      skipped: 0,
      failed: 1,
      failures: [{ path: 'notes/broken-scan.pdf', error: 'unsupported or corrupt file' }],
    }),
  })
}

export async function agentStop(): Promise<void> {
  if (isRealTauri) {
    await invoke('agent_stop')
    return
  }
  mockAgentStatus = { running: false, user_stopped: true, restarts: mockAgentStatus.restarts }
  mockEmit<AgentEventPayload>('agent-event', { line: JSON.stringify({ event: 'stopped' }) })
  mockEmit<AgentTerminatedEvent>('agent-terminated', { code: 0, will_restart: false })
}

export async function agentStatus(): Promise<AgentStatus> {
  if (isRealTauri) return invoke<AgentStatus>('agent_status')
  return { ...mockAgentStatus }
}

// ---- Folder picker (plugin-dialog on real Tauri, a fake path in mock mode) ------------------

export async function pickFolders(): Promise<string[]> {
  if (isRealTauri) {
    const result = await tauriOpenDialog({ directory: true, multiple: true })
    if (result === null) return []
    return Array.isArray(result) ? result : [result]
  }
  mockFolderCounter += 1
  return [`/home/demo/mock-folder-${mockFolderCounter}`]
}
