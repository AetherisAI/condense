import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { apiFetch, apiUrl, getApiBase, setApiBase } from './api'
import { detectProvider } from './provider'
import { isTauri } from './platform'
import {
  agentStart,
  agentStatus,
  agentStop,
  appConfigGet,
  appConfigSet,
  backendStart,
  backendStateError,
  backendStateKind,
  backendStatus,
  backendStop,
  listenEvent,
  parseAgentLine,
  pickFolders,
  provisionStart,
  provisioningStatus,
  type AgentEventPayload,
  type AgentLine,
  type AgentStatus,
  type AgentTerminatedEvent,
  type AppConfig,
  type BackendStateEvent,
  type BackendStatus,
  type ComponentId,
  type ProvisioningStatus,
  type Unlisten,
} from './tauri'

/** The `sync` variant of `AgentLine` — narrowed via its `event` discriminant below. */
type AgentSyncLine = Extract<AgentLine, { event: 'sync' }>

/** One dependency's reachability (mirrors api.schemas.ComponentHealth). */
type ComponentHealth = {
  status: string // "ok" | "down" | "not_configured"
  model?: string | null
  detail?: string | null
}

/** Mirrors api.schemas.StatusResponse — health + components + the config (secrets redacted). */
type StatusResponse = {
  status: string
  embed_model: string | null
  components: Record<string, ComponentHealth>
  settings: Record<string, unknown>
}

type Health = 'up' | 'down' | 'unknown'

function fmt(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'boolean') return v ? 'true' : 'false'
  return String(v)
}

/** Map a component status onto a status-dot modifier (no green — bluish-purple = ok). */
function dotFor(status: string): string {
  if (status === 'ok') return 'sys-dot-up'
  if (status === 'down') return 'sys-dot-down'
  return '' // not_configured → neutral grey
}

/** Settings editable on the fly — must match api.schemas.SettingsPatch. */
const EDITABLE = new Set([
  'recap_enabled',
  'recap_context_k',
  'recap_max_tokens',
  'recap_temperature',
  'source_snippet_chars',
  'retrieve_k',
  'final_k',
  'chunk_size',
  'chunk_overlap',
  'rerank_strategy',
])

/** Model pins / base URLs / store backend / tokens — baked into the container at startup, so
 * changing one has no effect until the engine restarts. Shown read-only + greyed with a hint,
 * never inline-editable (distinct from the smaller `EDITABLE` whitelist above). `llm_api_key`
 * living here (confirmed against `SettingsPatch`/`_SECRET_KEYS` on the backend, D57/Task U6) is
 * exactly why the Model section's key field below is local-preview-only, never PATCHed. */
const RESTART_REQUIRED = new Set([
  'store_backend',
  'turso_database_url',
  'turso_auth_token',
  'embed_base_url',
  'embed_model',
  'embed_api_key',
  'rerank_base_url',
  'rerank_model',
  'llm_base_url',
  'llm_model',
  'llm_api_key',
  'ocr_enabled',
  'ocr_base_url',
  'ocr_model',
  'ocr_api_key',
  'ingest_token',
  'auth_tokens',
])

/** One-line explanation per settings key — shown on hover via the same info-tooltip pattern
 * the Search panel's mode switch already uses. Keys absent here just render without a tip. */
const EXPLANATIONS: Record<string, string> = {
  store_backend: 'Which vector store backend is active — libSQL (Turso) or the in-memory fake.',
  turso_database_url: 'Turso/libSQL database URL — where vectors, chunks, and metadata live.',
  turso_auth_token: 'Auth token for the Turso database connection.',
  embed_base_url: 'OpenAI-compatible base URL for the embedding backend.',
  embed_model: 'The pinned embedding model — every ingest/search checks this against the stored pin.',
  embed_dim: 'Vector dimensionality the embedding model produces.',
  embed_api_key: 'API key for the embedding backend, if it requires one.',
  embed_batch_size: 'How many texts go out per embeddings HTTP call.',
  embed_timeout_s: 'Read/write timeout for an embeddings call once connected.',
  embed_connect_timeout_s: 'Connect timeout for the embeddings backend — fails fast if unreachable.',
  embed_retry_attempts: 'How many times a rate-limited (429) embeddings call is retried.',
  rerank_strategy: 'How retrieved passages are reranked before the top result is chosen.',
  rerank_base_url: 'Base URL for the cross-encoder reranker (e.g. TEI), when strategy=crossencoder.',
  rerank_model: 'The reranker model name.',
  retrieve_k: 'How many candidates are retrieved before reranking.',
  final_k: 'How many top results reranking keeps.',
  version_collapse_enabled:
    'Fold near-duplicate passages (typo fixes, re-exports) into their newest copy before ranking.',
  version_similarity_threshold:
    'Token-shingle similarity above which two passages are treated as the same version.',
  recap_enabled: 'Whether search returns an AI-written recap, or just the raw source passages.',
  recap_context_k: 'How many top passages feed the recap prompt.',
  recap_max_tokens: 'Max tokens the recap completion may generate.',
  recap_temperature: 'Sampling temperature for the recap completion.',
  source_snippet_chars: 'How many characters of a matched passage are shown per source.',
  llm_base_url: 'OpenAI-compatible base URL for chat/recap/answer completions.',
  llm_model: 'The chat/completion model used for recaps and /v1/answer.',
  llm_api_key: 'API key for the LLM backend, if it requires one.',
  ocr_enabled: 'Whether scanned/image files fall back to OCR when text extraction finds nothing.',
  ocr_base_url: 'Base URL for the OCR backend (Mistral OCR).',
  ocr_model: 'The OCR model name.',
  ocr_api_key: 'API key for the OCR backend.',
  ocr_timeout_s: 'Read/write timeout for an OCR call once connected.',
  ocr_connect_timeout_s: 'Connect timeout for the OCR backend.',
  parse_max_xlsx_cells: 'Reject a spreadsheet whose declared used-range implies more cells than this.',
  chunk_size: 'Target tokens per chunk when splitting a document for embedding.',
  chunk_overlap: 'Tokens of overlap between consecutive chunks.',
  ingest_token: 'Bearer token required to upload documents.',
  parse_max_chars: "Reject a parsed document whose extracted text exceeds this many characters.",
  parse_timeout_s: 'Wall-clock timeout for parsing a single file.',
  tools_search_k: 'Default number of hits POST /v1/tools/search returns.',
  tools_search_max_k: 'Hard cap on how many hits a caller may request from /v1/tools/search.',
  auth_tokens: 'Named per-consumer bearer tokens (beyond the ingest token) that resolve to this tenant.',
  answer_tool_mode: "How /v1/answer drives tool-calling: native function-calling, a prompted fallback, or auto.",
  answer_max_tool_calls: 'Max tool executions one /v1/answer call may make before stopping gracefully.',
  answer_timeout_s: 'Whole-loop wall-clock ceiling for one /v1/answer call.',
  answer_max_tokens: 'Max tokens the final answer completion may generate.',
  answer_history_max_turns: "How many of a conversation's most recent turns are kept.",
  answer_history_ttl_days: 'How long an idle conversation survives before it can be pruned.',
}

/** Grouped rendering order — mirrors .env.example's section headings (CLAUDE.md §7/§9). */
const GROUPS: { label: string; keys: string[] }[] = [
  { label: 'Store', keys: ['store_backend', 'turso_database_url', 'turso_auth_token'] },
  {
    label: 'Embedding',
    keys: [
      'embed_base_url',
      'embed_model',
      'embed_dim',
      'embed_api_key',
      'embed_batch_size',
      'embed_timeout_s',
      'embed_connect_timeout_s',
      'embed_retry_attempts',
    ],
  },
  { label: 'Rerank', keys: ['rerank_strategy', 'rerank_base_url', 'rerank_model'] },
  {
    label: 'Retrieval & recap',
    keys: [
      'retrieve_k',
      'final_k',
      'version_collapse_enabled',
      'version_similarity_threshold',
      'recap_enabled',
      'recap_context_k',
      'recap_max_tokens',
      'recap_temperature',
      'source_snippet_chars',
    ],
  },
  {
    label: 'LLM & answer',
    keys: [
      'llm_base_url',
      'llm_model',
      'llm_api_key',
      'answer_tool_mode',
      'answer_max_tool_calls',
      'answer_timeout_s',
      'answer_max_tokens',
      'answer_history_max_turns',
      'answer_history_ttl_days',
    ],
  },
  {
    label: 'OCR',
    keys: ['ocr_enabled', 'ocr_base_url', 'ocr_model', 'ocr_api_key', 'ocr_timeout_s', 'ocr_connect_timeout_s'],
  },
  {
    label: 'Parsing guards',
    keys: ['parse_max_xlsx_cells', 'parse_max_chars', 'parse_timeout_s', 'chunk_size', 'chunk_overlap'],
  },
  {
    label: 'Ingest & auth',
    keys: ['ingest_token', 'auth_tokens', 'tools_search_k', 'tools_search_max_k'],
  },
]

/** Coerce a raw input string into the JSON value PATCH /settings expects for that key. */
function coerce(key: string, raw: string): unknown {
  if (key === 'recap_enabled') return raw.trim().toLowerCase() === 'true'
  if (key === 'rerank_strategy') return raw.trim()
  return Number(raw)
}

/** One downloadable build of the desktop ingestion agent (absorbed from the retired
 * `AgentMenu.tsx`, D57/Task U6 — its own topbar chip/drawer are gone, these rows now live in the
 * System drawer's "Folder agent" section, styling untouched). */
type Build = {
  os: string
  hint: string
  href?: string // absent → "coming soon"
  note?: string // extra line under the row (e.g. the unsigned-app caveat)
  icon: React.ReactNode
}

const APPLE = (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
    <path d="M16.365 12.9c.02 2.16 1.9 2.88 1.92 2.89-.015.05-.3 1.03-.99 2.04-.6.88-1.22 1.75-2.2 1.77-.96.02-1.27-.57-2.37-.57-1.1 0-1.45.55-2.36.59-.95.03-1.67-.95-2.27-1.83-1.24-1.8-2.18-5.08-.91-7.3.63-1.1 1.76-1.8 2.98-1.82.93-.02 1.81.63 2.38.63.57 0 1.64-.78 2.76-.66.47.02 1.79.19 2.63 1.43-.07.04-1.57.92-1.55 2.73M14.6 6.3c.5-.6.84-1.45.75-2.3-.72.03-1.6.48-2.12 1.08-.47.53-.88 1.4-.77 2.22.8.06 1.63-.41 2.14-1"/>
  </svg>
)

const UBUNTU = (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
    <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20m0 3.2a6.8 6.8 0 0 1 6.06 3.72 2.02 2.02 0 0 0-.4 3.03 6.8 6.8 0 0 1 0 .1 2.02 2.02 0 0 0 .4 3.03 6.8 6.8 0 0 1-11.03 1.9 2.02 2.02 0 0 0-2.5-1.72A6.8 6.8 0 0 1 4 12a6.8 6.8 0 0 1 .53-2.65 2.02 2.02 0 0 0 2.5-1.72A6.77 6.77 0 0 1 12 5.2m0 3.1a3.7 3.7 0 1 0 0 7.4 3.7 3.7 0 0 0 0-7.4"/>
  </svg>
)

const WINDOWS = (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
    <path d="M3 5.4 10.5 4.3v7.2H3zM11.5 4.15 21 2.8v8.7h-9.5zM3 12.5h7.5v7.2L3 18.6zM11.5 12.5H21v8.7l-9.5-1.35z"/>
  </svg>
)

const BUILDS: Build[] = [
  {
    os: 'macOS',
    hint: 'Apple silicon & Intel · unzip and open',
    href: '/downloads/sift-agent-macos.zip',
    note: 'Unsigned build — first launch: right-click the app → Open.',
    icon: APPLE,
  },
  {
    os: 'Ubuntu / Linux',
    hint: 'AppImage · chmod +x, then run — no install',
    href: '/downloads/sift-agent-ubuntu.AppImage',
    icon: UBUNTU,
  },
  {
    os: 'Windows',
    hint: 'unzip and run',
    href: 'https://github.com/AetherisAI/condense/releases/latest/download/sift-agent-windows.zip',
    note: 'Published to the latest GitHub release (built by the build-agent workflow).',
    icon: WINDOWS,
  },
]

/** Imperative surface exposed to the workbench shell (`App.tsx`, D57/Task U6) — the empty-corpus
 * nudge's "Get the agent" button lives in `Chat.tsx`, outside this drawer's own tree, so it opens
 * the drawer AND scrolls to the Folder agent section through a ref, the same pattern `ChatHandle`
 * already uses for the topbar's "New chat" button. */
export type SystemMenuHandle = { scrollToAgent: () => void }

/**
 * A drawer showing API health + the effective config (from the auth'd /status, secrets already
 * redacted server-side), simple-first (D57/Task U6): Connection (token/base URL/compact health),
 * Model (LLM summary + a local-only provider-detect preview), Folder agent (the desktop ingestion
 * agent downloads, absorbed from the retired `AgentMenu.tsx`), then the entire original raw
 * settings table demoted into a collapsed "Advanced" accordion, unchanged. Its own top-right
 * status chip trigger is gone (D57/Task U1) — `open` is controlled from the workbench topbar's
 * "System" button. Closes on backdrop-click/Esc.
 */
const SystemMenu = forwardRef<
  SystemMenuHandle,
  {
    token: string
    setToken: (t: string) => void
    open: boolean
    onOpenChange: (open: boolean) => void
  }
>(function SystemMenu({ token, setToken, open, onOpenChange }, ref) {
  const [apiBase, setApiBaseInput] = useState(() => getApiBase())
  const [health, setHealth] = useState<Health>('unknown')
  const [data, setData] = useState<StatusResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  // Keys with a just-saved PATCH — a "Saved ✓" fades in for a beat as optimistic feedback.
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set())
  // Model section's LLM API key preview (D57/Task U6) — LOCAL-ONLY, never sent anywhere: typed
  // purely so `detectProvider` can render a live provider badge. `llm_api_key` is restart-only
  // (see `RESTART_REQUIRED`/backend `_SECRET_KEYS`+`SettingsPatch`, confirmed not PATCHable), so
  // there is no save path here to fake — the copy under the field says so plainly.
  const [llmKeyDraft, setLlmKeyDraft] = useState('')
  const agentSectionRef = useRef<HTMLDivElement>(null)

  // ---- Desktop (Tauri-only, D60/T2): mode switch + backend supervision + component checks ----
  const [desktopConfig, setDesktopConfig] = useState<AppConfig | null>(null)
  const [backend, setBackend] = useState<BackendStatus | null>(null)
  const [provisioning, setProvisioning] = useState<ProvisioningStatus | null>(null)
  const [desktopError, setDesktopError] = useState<string | null>(null)
  const [modeSwitching, setModeSwitching] = useState(false)
  const [backendBusy, setBackendBusy] = useState(false)

  // ---- Folder agent live controls (Tauri-only) -----------------------------------------------
  const [agentPaths, setAgentPaths] = useState<string[]>([])
  const [agentDeleteRemoved, setAgentDeleteRemoved] = useState(false)
  const [agentStatusState, setAgentStatusState] = useState<AgentStatus | null>(null)
  const [agentLastSync, setAgentLastSync] = useState<AgentSyncLine | null>(null)
  const [agentLog, setAgentLog] = useState<string[]>([])
  const [agentBusy, setAgentBusy] = useState(false)
  const [agentError, setAgentError] = useState<string | null>(null)
  const agentSeededRef = useRef(false)

  useImperativeHandle(ref, () => ({
    scrollToAgent: () => {
      agentSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    },
  }))

  // At-a-glance health: ping the open /healthz once on mount.
  useEffect(() => {
    let alive = true
    apiFetch('/healthz', '')
      .then((r) => alive && setHealth(r.ok ? 'up' : 'down'))
      .catch(() => alive && setHealth('down'))
    return () => {
      alive = false
    }
  }, [])

  // Dismiss on Escape while open — outside clicks are caught by the drawer backdrop.
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onOpenChange(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  // (Re)load status when the panel opens or the token changes — so entering the token right here
  // immediately populates components + settings. `cancelled` guards against a stale response
  // winning a race against a fresher one: typing a token character-by-character re-fires this on
  // every keystroke, and an earlier (now-stale) 401 rejection landing AFTER a later, valid
  // request's success used to leave "Enter a valid token…" stuck on screen even though the good
  // data had already loaded (the bug this fixes). Folding `load` into the effect itself (rather
  // than a function declared outside it) also resolves the effect's own exhaustive-deps warning —
  // `token`/`open` are its only real dependencies now.
  useEffect(() => {
    if (!open) return
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const resp = await apiFetch('/status', token)
        if (cancelled) return
        if (!resp.ok) {
          throw new Error(resp.status === 401 ? 'Enter a valid token to view settings' : `Status ${resp.status}`)
        }
        const json = (await resp.json()) as StatusResponse
        if (cancelled) return
        setData(json)
        setHealth('up')
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [open, token])

  // Desktop section: config + backend status + provisioning, loaded once per drawer-open, kept
  // live via `backend-state` events for as long as the drawer stays open.
  useEffect(() => {
    if (!isTauri || !open) return
    let cancelled = false
    async function load() {
      try {
        const [cfg, status, prov] = await Promise.all([appConfigGet(), backendStatus(), provisioningStatus()])
        if (cancelled) return
        setDesktopConfig(cfg)
        setBackend(status)
        setProvisioning(prov)
      } catch (err) {
        if (!cancelled) setDesktopError(err instanceof Error ? err.message : String(err))
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [open])

  useEffect(() => {
    if (!isTauri || !open) return
    let disposed = false
    const disposers: Unlisten[] = []
    async function subscribe() {
      const un = await listenEvent<BackendStateEvent>('backend-state', (e) => {
        setBackend((prev) =>
          prev ? { ...prev, [e.component]: { ...prev[e.component], state: e.state } } : prev,
        )
      })
      if (disposed) {
        un()
        return
      }
      disposers.push(un)
    }
    void subscribe()
    return () => {
      disposed = true
      disposers.forEach((fn) => fn())
    }
  }, [open])

  // Seed the folder-agent editor from the loaded config exactly once per drawer-open session, so
  // a later config refresh (e.g. after a mode switch) never clobbers in-progress edits.
  useEffect(() => {
    if (!open) agentSeededRef.current = false
  }, [open])

  useEffect(() => {
    if (!desktopConfig || agentSeededRef.current) return
    setAgentPaths(desktopConfig.agent.paths)
    setAgentDeleteRemoved(desktopConfig.agent.delete_removed)
    agentSeededRef.current = true
  }, [desktopConfig])

  // Folder agent: status once, then live NDJSON lines + termination notices for as long as the
  // drawer stays open.
  useEffect(() => {
    if (!isTauri || !open) return
    let disposed = false
    const disposers: Unlisten[] = []
    async function subscribe() {
      try {
        setAgentStatusState(await agentStatus())
      } catch {
        // best-effort — the live event stream below is the real source of truth
      }
      const unEvent = await listenEvent<AgentEventPayload>('agent-event', (e) => {
        setAgentLog((prev) => [...prev.slice(-199), e.line])
        const parsed = parseAgentLine(e.line)
        if (parsed && parsed.event === 'sync') setAgentLastSync(parsed)
      })
      if (disposed) {
        unEvent()
        return
      }
      disposers.push(unEvent)
      const unTerm = await listenEvent<AgentTerminatedEvent>('agent-terminated', () => {
        void agentStatus()
          .then(setAgentStatusState)
          .catch(() => {})
      })
      if (disposed) {
        unTerm()
        return
      }
      disposers.push(unTerm)
    }
    void subscribe()
    return () => {
      disposed = true
      disposers.forEach((fn) => fn())
    }
  }, [open])

  async function handleModeSwitch(mode: 'local' | 'client') {
    if (!desktopConfig || desktopConfig.mode === mode || modeSwitching) return
    setModeSwitching(true)
    setDesktopError(null)
    try {
      const saved = await appConfigSet({ ...desktopConfig, mode })
      setDesktopConfig(saved)
    } catch (err) {
      setDesktopError(err instanceof Error ? err.message : String(err))
    } finally {
      setModeSwitching(false)
    }
  }

  async function handleBackendStart() {
    setBackendBusy(true)
    setDesktopError(null)
    try {
      await backendStart()
      setBackend(await backendStatus())
    } catch (err) {
      setDesktopError(err instanceof Error ? err.message : String(err))
    } finally {
      setBackendBusy(false)
    }
  }

  async function handleBackendStop() {
    setBackendBusy(true)
    setDesktopError(null)
    try {
      await backendStop()
      setBackend(await backendStatus())
    } catch (err) {
      setDesktopError(err instanceof Error ? err.message : String(err))
    } finally {
      setBackendBusy(false)
    }
  }

  async function handleCheckDownloads() {
    setDesktopError(null)
    try {
      setProvisioning(await provisioningStatus())
    } catch (err) {
      setDesktopError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleDownloadComponent(id: ComponentId) {
    setDesktopError(null)
    try {
      await provisionStart([id])
      setProvisioning(await provisioningStatus())
    } catch (err) {
      setDesktopError(err instanceof Error ? err.message : String(err))
    }
  }

  async function persistAgentConfig(paths: string[], deleteRemoved: boolean) {
    if (!desktopConfig) return
    try {
      const saved = await appConfigSet({ ...desktopConfig, agent: { paths, delete_removed: deleteRemoved } })
      setDesktopConfig(saved)
    } catch (err) {
      setAgentError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleAddFolder() {
    const picked = await pickFolders()
    if (picked.length === 0) return
    const next = [...new Set([...agentPaths, ...picked])]
    setAgentPaths(next)
    void persistAgentConfig(next, agentDeleteRemoved)
  }

  function handleRemoveFolder(path: string) {
    const next = agentPaths.filter((p) => p !== path)
    setAgentPaths(next)
    void persistAgentConfig(next, agentDeleteRemoved)
  }

  function handleDeleteRemovedChange(checked: boolean) {
    setAgentDeleteRemoved(checked)
    void persistAgentConfig(agentPaths, checked)
  }

  async function handleAgentStart() {
    setAgentBusy(true)
    setAgentError(null)
    try {
      await agentStart({ paths: agentPaths, delete_removed: agentDeleteRemoved })
      setAgentStatusState(await agentStatus())
    } catch (err) {
      setAgentError(err instanceof Error ? err.message : String(err))
    } finally {
      setAgentBusy(false)
    }
  }

  async function handleAgentStop() {
    setAgentBusy(true)
    setAgentError(null)
    try {
      await agentStop()
      setAgentStatusState(await agentStatus())
    } catch (err) {
      setAgentError(err instanceof Error ? err.message : String(err))
    } finally {
      setAgentBusy(false)
    }
  }

  async function patchSetting(key: string, raw: string) {
    const value = coerce(key, raw)
    if (typeof value === 'number' && Number.isNaN(value)) {
      setError(`Invalid number for ${key}`)
      return
    }
    setError(null)
    try {
      const resp = await apiFetch('/settings', token, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value }),
      })
      if (!resp.ok) throw new Error(`Update failed: ${resp.status}`)
      setData((await resp.json()) as StatusResponse)
      setSavedKeys((prev) => new Set(prev).add(key))
      setTimeout(() => {
        setSavedKeys((prev) => {
          const next = new Set(prev)
          next.delete(key)
          return next
        })
      }, 1500)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const detectedProvider = detectProvider(llmKeyDraft)

  return (
    <>
      {open && <div className="drawer-backdrop" onClick={() => onOpenChange(false)} />}

      <aside
        className={`drawer${open ? ' open' : ''}`}
        role="dialog"
        aria-label="System status"
        aria-hidden={!open}
      >
        <div className="drawer-head">
          <h2>System</h2>
          <span
            className={`sys-dot ${dotFor(health === 'up' ? 'ok' : health === 'down' ? 'down' : '')}`}
            title={`API ${health}`}
            aria-hidden="true"
          />
          <button
            type="button"
            className="drawer-close"
            onClick={() => onOpenChange(false)}
            aria-label="Close system panel"
          >
            ✕
          </button>
        </div>

        <div className="drawer-body">
          {/* ---- Desktop (Tauri-only, D60/T2): mode switch + backend + component checks --- */}
          {isTauri && (
            <div className="sys-section">
              <h3 className="sys-heading">Desktop</h3>

              {!desktopConfig ? (
                <p className="sys-muted">Loading…</p>
              ) : (
                <>
                  <div className="sys-mode-row">
                    <span className="sys-label">Mode</span>
                    <div className="grounding-select">
                      <button
                        type="button"
                        className={`grounding-btn${desktopConfig.mode === 'local' ? ' active' : ''}`}
                        onClick={() => handleModeSwitch('local')}
                        disabled={modeSwitching}
                      >
                        Local
                      </button>
                      <button
                        type="button"
                        className={`grounding-btn${desktopConfig.mode === 'client' ? ' active' : ''}`}
                        onClick={() => handleModeSwitch('client')}
                        disabled={modeSwitching}
                      >
                        Client
                      </button>
                    </div>
                  </div>

                  {desktopConfig.mode === 'local' && backend && (
                    <div className="sys-backend-rows">
                      {(['embedder', 'engine'] as const).map((component) => {
                        const status = backend[component]
                        const kind = backendStateKind(status.state)
                        return (
                          <div className="sys-row" key={component}>
                            <span className="sys-key">
                              {component === 'embedder' ? 'Embedding server' : 'Engine'}
                            </span>
                            <span className="sys-row-right">
                              <span className={`wizard-state-badge is-${kind}`}>
                                {kind === 'error' ? `error: ${backendStateError(status.state)}` : kind}
                              </span>
                              <span className="sys-val">:{status.port}</span>
                            </span>
                          </div>
                        )
                      })}
                      <div className="wizard-actions">
                        <button
                          type="button"
                          className="wizard-secondary-btn"
                          onClick={() => void handleBackendStart()}
                          disabled={backendBusy}
                        >
                          Start
                        </button>
                        <button
                          type="button"
                          className="wizard-secondary-btn"
                          onClick={() => void handleBackendStop()}
                          disabled={backendBusy}
                        >
                          Stop
                        </button>
                      </div>
                    </div>
                  )}

                  <div className="sys-provisioning">
                    <div className="sys-provisioning-head">
                      <span className="sys-label">Components</span>
                      <button type="button" className="wizard-skip-link" onClick={() => void handleCheckDownloads()}>
                        Check downloads
                      </button>
                    </div>
                    {provisioning?.components.map((c) => (
                      <div className="sys-row" key={c.id}>
                        <span className="sys-key">{c.name}</span>
                        <span className="sys-row-right">
                          {c.installed ? (
                            <span className="sys-val">{c.version ?? 'installed'}</span>
                          ) : (
                            <button
                              type="button"
                              className="wizard-retry"
                              onClick={() => void handleDownloadComponent(c.id)}
                            >
                              Download
                            </button>
                          )}
                        </span>
                      </div>
                    ))}
                  </div>

                  {(() => {
                    const manifestUrl =
                      provisioning?.manifest_url ?? desktopConfig.manifest_url ?? 'default'
                    return (
                      <div className="sys-row">
                        <span className="sys-key">Manifest URL</span>
                        <span className="sys-val sys-val-trunc" title={manifestUrl}>
                          {manifestUrl}
                        </span>
                      </div>
                    )
                  })()}

                  {desktopError && <p className="sys-error">{desktopError}</p>}
                </>
              )}
            </div>
          )}

          {/* ---- Connection: token + base URL + condensed health ------------------------- */}
          <div className="sys-section">
            <h3 className="sys-heading">Connection</h3>

            {(!isTauri || desktopConfig?.mode !== 'local') && (
              <>
                <div className="sys-token">
                  <label className="sys-label" htmlFor="bearer-token">
                    Bearer token
                  </label>
                  <input
                    id="bearer-token"
                    className="sys-token-input"
                    type="password"
                    value={token}
                    placeholder="paste your token"
                    autoComplete="off"
                    spellCheck={false}
                    onChange={(e) => setToken(e.target.value)}
                  />
                </div>

                <div className="sys-token">
                  <label className="sys-label" htmlFor="api-base-url">
                    API base URL
                  </label>
                  <input
                    id="api-base-url"
                    className="sys-token-input"
                    type="text"
                    value={apiBase}
                    placeholder="same origin (default)"
                    autoComplete="off"
                    spellCheck={false}
                    onChange={(e) => {
                      setApiBaseInput(e.target.value)
                      setApiBase(e.target.value)
                    }}
                  />
                </div>
              </>
            )}

            {isTauri && desktopConfig?.mode === 'local' && (
              <p className="sys-muted">
                Connected automatically to the local backend on 127.0.0.1:{desktopConfig.engine_port}. Switch
                to Client mode above to enter a base URL/token by hand.
              </p>
            )}

            {error && <p className="sys-error">{error}</p>}
            {loading && <p className="sys-muted">Loading…</p>}

            {data && (
              <div className="sys-health-row">
                {Object.entries(data.components).map(([name, c]) => (
                  <span className="sys-health-chip" key={name}>
                    <span className={`sys-dot ${dotFor(c.status)}`} aria-hidden="true" />
                    <span className="sys-health-name">{name}</span>
                    <span className="sys-health-detail">
                      {c.status === 'not_configured' ? 'off' : (c.model ?? c.detail ?? 'ok')}
                    </span>
                  </span>
                ))}
              </div>
            )}

            <a className="sys-docs" href={apiUrl('/docs')} target="_blank" rel="noreferrer">
              API documentation
              <span aria-hidden="true">↗</span>
            </a>
          </div>

          {/* ---- Model: LLM summary + provider auto-detect preview ------------------------ */}
          <div className="sys-section">
            <h3 className="sys-heading">Model</h3>

            {data ? (
              <>
                <div className="sys-row">
                  <span className="sys-key">LLM_MODEL</span>
                  <span className={`sys-val${data.settings.llm_model == null ? ' sys-null' : ''}`}>
                    {fmt(data.settings.llm_model)}
                  </span>
                </div>

                <div className="sys-row sys-row-restart">
                  <span className="sys-key">
                    LLM_API_KEY
                    <span
                      className="mode-info sys-info"
                      tabIndex={0}
                      role="note"
                      aria-label="Baked in at container startup — restart-only, never editable here."
                    >
                      ⓘ
                      <span className="mode-tip sys-tip" role="tooltip">
                        Baked in at container startup — restart-only, never editable here.
                      </span>
                    </span>
                  </span>
                  <span className="sys-row-right">
                    <span className="sys-restart-badge" title="Requires an engine restart to change">
                      restart
                    </span>
                    <span className={`sys-val${data.settings.llm_api_key == null ? ' sys-null' : ''}`}>
                      {fmt(data.settings.llm_api_key)}
                    </span>
                  </span>
                </div>

                <div className="sys-model-key">
                  <label className="sys-label" htmlFor="llm-api-key-preview">
                    LLM API key
                  </label>
                  <div className="sys-model-key-row">
                    <input
                      id="llm-api-key-preview"
                      className="sys-token-input"
                      type="password"
                      value={llmKeyDraft}
                      placeholder="paste to preview the provider — never saved"
                      autoComplete="off"
                      spellCheck={false}
                      onChange={(e) => setLlmKeyDraft(e.target.value)}
                    />
                    {detectedProvider && <span className="sys-provider-badge">{detectedProvider}</span>}
                  </div>
                  <p className="sys-model-hint">
                    Applies after backend restart — set LLM_API_KEY in .env.
                  </p>
                </div>
              </>
            ) : (
              <p className="sys-muted">Loading…</p>
            )}
          </div>

          {/* ---- Folder agent: absorbed from the retired AgentMenu.tsx (D57/Task U6); live
                 controls replace the download links in Tauri (D60/T2) ----------------------- */}
          <div className="sys-section" ref={agentSectionRef}>
            <h3 className="sys-heading">Folder agent</h3>

            {isTauri ? (
              <>
                <p className="agent-intro">
                  Point the agent at folders on this machine — it keeps them indexed in Condense,
                  automatically.
                </p>

                <ul className="agent-folder-list">
                  {agentPaths.length === 0 && <li className="sys-muted">No folders yet.</li>}
                  {agentPaths.map((path) => (
                    <li className="agent-folder-row" key={path}>
                      <span className="agent-folder-path">{path}</span>
                      <button
                        type="button"
                        className="drawer-del"
                        onClick={() => handleRemoveFolder(path)}
                        aria-label={`Remove ${path}`}
                      >
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>

                <button type="button" className="wizard-secondary-btn" onClick={() => void handleAddFolder()}>
                  Add folder…
                </button>

                <label className="agent-delete-removed">
                  <input
                    type="checkbox"
                    checked={agentDeleteRemoved}
                    onChange={(e) => handleDeleteRemovedChange(e.target.checked)}
                  />
                  Delete documents whose files leave disk
                </label>
                <p className="agent-note">
                  When on, removing a watched file also removes it from the index — off keeps it
                  searchable even after the file itself is gone.
                </p>

                <div className="wizard-actions">
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => void handleAgentStart()}
                    disabled={agentBusy || agentPaths.length === 0 || (agentStatusState?.running ?? false)}
                  >
                    Start
                  </button>
                  <button
                    type="button"
                    className="wizard-secondary-btn"
                    onClick={() => void handleAgentStop()}
                    disabled={agentBusy || !(agentStatusState?.running ?? false)}
                  >
                    Stop
                  </button>
                </div>

                {agentStatusState && (
                  <p className="agent-status-line">
                    {agentStatusState.running ? 'Running' : 'Stopped'}
                    {agentStatusState.restarts > 0 &&
                      ` · ${agentStatusState.restarts} restart${agentStatusState.restarts === 1 ? '' : 's'}`}
                  </p>
                )}

                {agentLastSync && (
                  <div className="agent-sync-summary">
                    <span>{agentLastSync.indexed} indexed</span>
                    <span>{agentLastSync.replaced} replaced</span>
                    <span>{agentLastSync.deleted} deleted</span>
                    <span>{agentLastSync.skipped} skipped</span>
                    <span className={agentLastSync.failed > 0 ? 'agent-sync-failed' : ''}>
                      {agentLastSync.failed} failed
                    </span>
                  </div>
                )}

                {agentLastSync && agentLastSync.failures.length > 0 && (
                  <ul className="doc-list agent-failures">
                    {agentLastSync.failures.map((f, i) => (
                      <li className="doc-item doc-failed" key={`${f.path}-${i}`}>
                        <span className="doc-badge">!</span>
                        <span className="doc-meta">
                          <span className="doc-name">{f.path}</span>
                          <span className="doc-sub">{f.error}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}

                {agentError && <p className="sys-error">{agentError}</p>}

                <details className="sys-advanced">
                  <summary className="sys-advanced-summary">
                    <span className="sys-advanced-chevron" aria-hidden="true">
                      ▸
                    </span>
                    Log ({agentLog.length})
                  </summary>
                  <div className="sys-advanced-body agent-log-tail">
                    {agentLog.length === 0 ? (
                      <p className="sys-muted">No log lines yet.</p>
                    ) : (
                      <pre className="agent-log-pre">{agentLog.join('\n')}</pre>
                    )}
                  </div>
                </details>
              </>
            ) : (
              <>
                <p className="agent-intro">
                  Run the ingestion agent on your machine — point it at folders and it keeps them
                  indexed in Condense, automatically.
                </p>

                {BUILDS.map((b) => (
                  <div className="agent-dl-row" key={b.os}>
                    <span className="agent-dl-icon">{b.icon}</span>
                    <span className="agent-dl-meta">
                      <span className="agent-dl-os">{b.os}</span>
                      <span className="agent-dl-hint">{b.hint}</span>
                      {b.note && <span className="agent-note">{b.note}</span>}
                    </span>
                    {b.href ? (
                      <a className="agent-dl-btn" href={b.href} download>
                        Download
                      </a>
                    ) : (
                      <span className="agent-dl-btn is-soon" aria-disabled="true">
                        Soon
                      </span>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>

          {/* ---- Advanced: the ENTIRE original raw settings table, unchanged, just demoted -- */}
          {data &&
            (() => {
              const grouped = new Set(GROUPS.flatMap((g) => g.keys))
              const leftover = Object.keys(data.settings).filter((k) => !grouped.has(k))
              return (
                <details className="sys-advanced">
                  <summary className="sys-advanced-summary">
                    <span className="sys-advanced-chevron" aria-hidden="true">
                      ▸
                    </span>
                    Advanced
                  </summary>
                  <div className="sys-advanced-body">
                    <div className="sys-label">Settings</div>
                    {GROUPS.map((group) => {
                      const keys = group.keys.filter((k) => k in data.settings)
                      if (keys.length === 0) return null
                      return (
                        <div className="sys-group" key={group.label}>
                          <div className="sys-group-label">{group.label}</div>
                          {keys.map((k) => {
                            const v = data.settings[k]
                            const editable = EDITABLE.has(k)
                            const restart = RESTART_REQUIRED.has(k)
                            const explanation = EXPLANATIONS[k]
                            return (
                              <div className={`sys-row${restart ? ' sys-row-restart' : ''}`} key={k}>
                                <span className="sys-key">
                                  {k.toUpperCase()}
                                  {editable && (
                                    <span
                                      className="sys-pencil"
                                      title="Editable — change and press Enter"
                                    >
                                      ✎
                                    </span>
                                  )}
                                  {explanation && (
                                    <span
                                      className="mode-info sys-info"
                                      tabIndex={0}
                                      role="note"
                                      aria-label={explanation}
                                    >
                                      ⓘ
                                      <span className="mode-tip sys-tip" role="tooltip">
                                        {explanation}
                                      </span>
                                    </span>
                                  )}
                                </span>
                                <span className="sys-row-right">
                                  {editable ? (
                                    <>
                                      {savedKeys.has(k) && <span className="sys-saved">Saved ✓</span>}
                                      <input
                                        className="sys-edit"
                                        defaultValue={fmt(v)}
                                        spellCheck={false}
                                        aria-label={`Edit ${k}`}
                                        onKeyDown={(e) => {
                                          if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
                                        }}
                                        onBlur={(e) => {
                                          if (e.target.value !== fmt(v)) patchSetting(k, e.target.value)
                                        }}
                                      />
                                    </>
                                  ) : (
                                    <>
                                      {restart && (
                                        <span
                                          className="sys-restart-badge"
                                          title="Requires an engine restart to change"
                                        >
                                          restart
                                        </span>
                                      )}
                                      <span className={`sys-val${v === null ? ' sys-null' : ''}`}>
                                        {fmt(v)}
                                      </span>
                                    </>
                                  )}
                                </span>
                              </div>
                            )
                          })}
                        </div>
                      )
                    })}
                    {leftover.length > 0 && (
                      <div className="sys-group">
                        <div className="sys-group-label">Other</div>
                        {leftover.map((k) => {
                          const v = data.settings[k]
                          return (
                            <div className="sys-row" key={k}>
                              <span className="sys-key">{k.toUpperCase()}</span>
                              <span className={`sys-val${v === null ? ' sys-null' : ''}`}>{fmt(v)}</span>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                </details>
              )
            })()}
        </div>
      </aside>
    </>
  )
})

export default SystemMenu
