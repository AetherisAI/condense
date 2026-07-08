import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import AccessTokens from './AccessTokens'
import AgentDownloads from './AgentDownloads'
import { apiFetch, apiUrl, getApiBase, setApiBase } from './api'
import { detectProvider } from './provider'
import { isTauri } from './platform'
import {
  agentStart,
  agentStatus,
  agentStop,
  agentSyncOnce,
  appConfigGet,
  appConfigSet,
  backendStart,
  backendStateError,
  backendStateKind,
  backendStatus,
  backendStop,
  DEFAULT_EXCLUDE_DIRS_SUMMARY,
  DEFAULT_INCLUDE_EXTENSIONS_SUMMARY,
  listenEvent,
  parseAgentLine,
  pickFolders,
  provisionStart,
  provisioningStatus,
  type AgentConfig,
  type AgentEventPayload,
  type AgentLine,
  type AgentStatus,
  type AgentSyncOnceDoneEvent,
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

/** Human copy for one `SkipDetail.reason` (agent/sync.py) — a short, plain-English "why". */
function skipReasonLabel(reason: string): string {
  switch (reason) {
    case 'oversized':
      return 'too large (over the max file size)'
    case 'excluded_dir':
      return 'inside an excluded directory'
    case 'excluded_file':
      return 'excluded filename'
    case 'unsupported_extension':
      return 'unsupported file type'
    default:
      return reason
  }
}

/** One `Log` entry: a raw NDJSON line from the sidecar, rendered structured when it parses as a
 * known `AgentLine` shape (a `sync` event becomes a one-line tally plus a named line per failure
 * and per local skip decision — the whole point of this WP's per-file visibility) or as plain
 * text otherwise (a stray non-JSON line, e.g. a Python traceback, must still be visible, not
 * swallowed). */
function AgentLogEntry({ line }: { line: string }) {
  const parsed = parseAgentLine(line)
  if (!parsed) return <li className="agent-log-line agent-log-raw">{line}</li>

  if (parsed.event === 'sync') {
    return (
      <li className="agent-log-line agent-log-sync">
        <div className="agent-log-sync-summary">
          {`+${parsed.indexed} indexed · ${parsed.replaced} replaced · ${parsed.deleted} deleted · ` +
            `${parsed.skipped} skipped · ${parsed.failed} failed`}
        </div>
        {parsed.error && <div className="sys-error">{parsed.error}</div>}
        {parsed.failures.map((f, i) => (
          <div className="agent-log-detail agent-log-failure" key={`f-${i}`}>
            ! {f.path} — {f.error}
          </div>
        ))}
        {parsed.skipped_details.map((s, i) => (
          <div className="agent-log-detail agent-log-skip" key={`s-${i}`}>
            – {s.path} — {skipReasonLabel(s.reason)}
          </div>
        ))}
      </li>
    )
  }
  if (parsed.event === 'watch_started') {
    return (
      <li className="agent-log-line">
        Watching {parsed.paths.join(', ')}
        {parsed.delete_removed ? ' (delete-removed on)' : ''}
      </li>
    )
  }
  if (parsed.event === 'fatal') {
    return <li className="agent-log-line sys-error">Fatal: {parsed.error}</li>
  }
  return <li className="agent-log-line">Stopped</li>
}

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
  // Manifest URL editor (D67) — the escape hatch the wizard's manifest-failure copy points at
  // ("set a manifest URL in System ▸ Desktop"). Draft holds the CONFIGURED value (empty = use the
  // baked default), not the effective URL; seeded once per drawer-open like the agent editor so a
  // config refresh (mode switch, save) never clobbers in-progress edits.
  const [manifestUrlDraft, setManifestUrlDraft] = useState('')
  const [manifestSaving, setManifestSaving] = useState(false)
  const manifestSeededRef = useRef(false)

  // ---- Folder agent live controls (Tauri-only) -----------------------------------------------
  const [agentPaths, setAgentPaths] = useState<string[]>([])
  const [agentDeleteRemoved, setAgentDeleteRemoved] = useState(false)
  // Granularity knobs (this WP): per-file size guard + EXTRA excluded directories, on top of the
  // sidecar's own built-ins (`DEFAULT_EXCLUDE_DIRS_SUMMARY`, view-only below).
  const [agentMaxFileSizeMb, setAgentMaxFileSizeMb] = useState(100)
  const [agentExcludeDirs, setAgentExcludeDirs] = useState<string[]>([])
  const [agentExcludeDirDraft, setAgentExcludeDirDraft] = useState('')
  const [agentStatusState, setAgentStatusState] = useState<AgentStatus | null>(null)
  const [agentLastSync, setAgentLastSync] = useState<AgentSyncLine | null>(null)
  const [agentLog, setAgentLog] = useState<string[]>([])
  const [agentBusy, setAgentBusy] = useState(false)
  const [agentSyncOnceBusy, setAgentSyncOnceBusy] = useState(false)
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
  // live via `backend-state` events for as long as the drawer stays open. `provisioning_status`
  // loads SEPARATELY from config/backend (D67): it fetches a manifest and can fail (e.g. a broken
  // user-set manifest URL, where the Rust embedded fallback deliberately doesn't apply) — coupling
  // them in one Promise.all left this whole section stuck on "Loading…" in exactly the state where
  // the user needs the manifest-URL field below to fix things.
  useEffect(() => {
    if (!isTauri || !open) return
    let cancelled = false
    async function load() {
      try {
        const [cfg, status] = await Promise.all([appConfigGet(), backendStatus()])
        if (cancelled) return
        setDesktopConfig(cfg)
        setBackend(status)
      } catch (err) {
        if (!cancelled) setDesktopError(err instanceof Error ? err.message : String(err))
        return
      }
      try {
        const prov = await provisioningStatus()
        if (!cancelled) setProvisioning(prov)
      } catch (err) {
        if (!cancelled) setDesktopError(err instanceof Error ? err.message : String(err))
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [open])

  // Seed the manifest-URL draft once per drawer-open session (same pattern as the agent editor
  // below) — empty string means "no override configured, use the baked default".
  useEffect(() => {
    if (!open) manifestSeededRef.current = false
  }, [open])

  useEffect(() => {
    if (!desktopConfig || manifestSeededRef.current) return
    setManifestUrlDraft(desktopConfig.manifest_url ?? '')
    manifestSeededRef.current = true
  }, [desktopConfig])

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
    setAgentMaxFileSizeMb(desktopConfig.agent.max_file_size_mb)
    setAgentExcludeDirs(desktopConfig.agent.exclude_dirs)
    agentSeededRef.current = true
  }, [desktopConfig])

  // Folder agent: status once (hydrating BOTH the running/restarts state AND the log from the
  // Rust side's own bounded buffer, see `AgentStatus.log`), then live NDJSON lines + termination
  // notices for the REST OF THE APP'S LIFETIME — deliberately NOT gated on `open` (unlike most
  // other Tauri-only effects in this file, which reconnect each time the drawer opens). Gating
  // this one on `open` was the root cause of the "Log (0)" bug: a sync that fired while the
  // drawer happened to be closed had no listener attached to see it, so it just vanished — this
  // subscribes once on mount (`SystemMenu` itself is always mounted, per `App.tsx`) and never
  // misses an event again, regardless of whether the drawer is open when it arrives.
  useEffect(() => {
    if (!isTauri) return
    let disposed = false
    const disposers: Unlisten[] = []
    async function subscribe() {
      try {
        const status = await agentStatus()
        if (disposed) return
        setAgentStatusState(status)
        setAgentLog(status.log)
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
      const unSyncOnce = await listenEvent<AgentSyncOnceDoneEvent>('agent-sync-once-done', () => {
        setAgentSyncOnceBusy(false)
      })
      if (disposed) {
        unSyncOnce()
        return
      }
      disposers.push(unSyncOnce)
    }
    void subscribe()
    return () => {
      disposed = true
      disposers.forEach((fn) => fn())
    }
  }, [])

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

  async function handleSaveManifestUrl() {
    if (!desktopConfig || manifestSaving) return
    setManifestSaving(true)
    setDesktopError(null)
    try {
      const trimmed = manifestUrlDraft.trim()
      const saved = await appConfigSet({ ...desktopConfig, manifest_url: trimmed === '' ? null : trimmed })
      setDesktopConfig(saved)
      // Re-check immediately against the new URL so the components list + effective-URL line
      // reflect the change (and a bad URL surfaces its error right here, next to the field).
      setProvisioning(await provisioningStatus())
    } catch (err) {
      setDesktopError(err instanceof Error ? err.message : String(err))
    } finally {
      setManifestSaving(false)
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

  async function persistAgentConfig(
    paths: string[],
    deleteRemoved: boolean,
    maxFileSizeMb: number,
    excludeDirs: string[],
  ) {
    if (!desktopConfig) return
    try {
      const saved = await appConfigSet({
        ...desktopConfig,
        agent: {
          paths,
          delete_removed: deleteRemoved,
          max_file_size_mb: maxFileSizeMb,
          exclude_dirs: excludeDirs,
        },
      })
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
    void persistAgentConfig(next, agentDeleteRemoved, agentMaxFileSizeMb, agentExcludeDirs)
  }

  function handleRemoveFolder(path: string) {
    const next = agentPaths.filter((p) => p !== path)
    setAgentPaths(next)
    void persistAgentConfig(next, agentDeleteRemoved, agentMaxFileSizeMb, agentExcludeDirs)
  }

  function handleDeleteRemovedChange(checked: boolean) {
    setAgentDeleteRemoved(checked)
    void persistAgentConfig(agentPaths, checked, agentMaxFileSizeMb, agentExcludeDirs)
  }

  function handleMaxFileSizeChange(raw: string) {
    const mb = Number(raw)
    if (!Number.isFinite(mb) || mb <= 0) return
    setAgentMaxFileSizeMb(mb)
    void persistAgentConfig(agentPaths, agentDeleteRemoved, mb, agentExcludeDirs)
  }

  function handleAddExcludeDir() {
    const dir = agentExcludeDirDraft.trim()
    if (!dir || agentExcludeDirs.includes(dir)) {
      setAgentExcludeDirDraft('')
      return
    }
    const next = [...agentExcludeDirs, dir]
    setAgentExcludeDirs(next)
    setAgentExcludeDirDraft('')
    void persistAgentConfig(agentPaths, agentDeleteRemoved, agentMaxFileSizeMb, next)
  }

  function handleRemoveExcludeDir(dir: string) {
    const next = agentExcludeDirs.filter((d) => d !== dir)
    setAgentExcludeDirs(next)
    void persistAgentConfig(agentPaths, agentDeleteRemoved, agentMaxFileSizeMb, next)
  }

  /** Shared by `handleAgentStart` (continuous `--watch`) and `handleSyncNow` (one-shot) so both
   * resolve the server/token the exact same way (T6): local mode points the sidecar at the
   * supervised engine with the app's generated ingest token; client mode points it at whatever
   * server/bearer token this drawer is currently connected with. */
  function buildAgentConfig(): AgentConfig {
    const cfg: AgentConfig = {
      paths: agentPaths,
      delete_removed: agentDeleteRemoved,
      max_file_size_mb: agentMaxFileSizeMb,
      exclude_dirs: agentExcludeDirs,
    }
    if (desktopConfig?.mode === 'local') {
      cfg.server = `http://127.0.0.1:${desktopConfig.engine_port}`
      cfg.token = desktopConfig.ingest_token
    } else {
      cfg.server = getApiBase()
      cfg.token = token
    }
    return cfg
  }

  async function handleAgentStart() {
    setAgentBusy(true)
    setAgentError(null)
    try {
      await agentStart(buildAgentConfig())
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

  /** One-shot "Sync now" — runs a single collect→diff→upload pass independent of the continuous
   * agent's own running/stopped state (works whether or not Start was ever clicked). Its own
   * "busy" clears on the `agent-sync-once-done` event (see the subscription effect above) rather
   * than immediately after the `agentSyncOnce` call returns, since that call only confirms the
   * sidecar was SPAWNED, not that the pass finished. */
  async function handleSyncNow() {
    if (agentPaths.length === 0) return
    setAgentSyncOnceBusy(true)
    setAgentError(null)
    try {
      await agentSyncOnce(buildAgentConfig())
    } catch (err) {
      setAgentError(err instanceof Error ? err.message : String(err))
      setAgentSyncOnceBusy(false)
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

                  <div className="sys-token">
                    <label className="sys-label" htmlFor="manifest-url">
                      Manifest URL
                    </label>
                    <input
                      id="manifest-url"
                      className="sys-token-input"
                      type="text"
                      value={manifestUrlDraft}
                      placeholder="leave empty for default"
                      autoComplete="off"
                      spellCheck={false}
                      onChange={(e) => setManifestUrlDraft(e.target.value)}
                    />
                    {provisioning?.source === 'embedded-fallback' && (
                      <p className="sys-muted">
                        The default manifest couldn't be reached online — using the component list
                        bundled with this app. Set a reachable URL here to override it.
                      </p>
                    )}
                    <div className="wizard-actions">
                      <button
                        type="button"
                        className="wizard-secondary-btn"
                        onClick={() => void handleSaveManifestUrl()}
                        disabled={manifestSaving || (desktopConfig.manifest_url ?? '') === manifestUrlDraft.trim()}
                      >
                        {manifestSaving ? 'Saving…' : 'Save'}
                      </button>
                    </div>
                  </div>

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

          {/* ---- Access tokens: mint/list/revoke per-consumer bearer tokens (master-gated) - */}
          <AccessTokens token={token} open={open} />

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
                 controls replace the download links in Tauri (D60/T2). Granularity knobs +
                 per-event log (this WP) close the "Log (0)" gap and expose why a file was
                 skipped/excluded, not just that something was. ------------------------------- */}
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
                  <button
                    type="button"
                    className="wizard-secondary-btn"
                    onClick={() => void handleSyncNow()}
                    disabled={agentSyncOnceBusy || agentPaths.length === 0}
                    title="Run one collect→diff→upload pass right now, independent of Start/Stop"
                  >
                    {agentSyncOnceBusy ? 'Syncing…' : 'Sync now'}
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

                {agentLastSync && agentLastSync.skipped_details.length > 0 && (
                  <ul className="doc-list agent-skipped-details">
                    {agentLastSync.skipped_details.map((s, i) => (
                      <li className="doc-item" key={`${s.path}-${i}`}>
                        <span className="doc-badge doc-badge-skip">–</span>
                        <span className="doc-meta">
                          <span className="doc-name">{s.path}</span>
                          <span className="doc-sub">{skipReasonLabel(s.reason)}</span>
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
                    Granularity
                  </summary>
                  <div className="sys-advanced-body">
                    <div className="sys-token">
                      <label className="sys-label" htmlFor="agent-max-file-size">
                        Max file size (MB)
                      </label>
                      <input
                        id="agent-max-file-size"
                        type="number"
                        min={1}
                        className="sys-token-input"
                        defaultValue={agentMaxFileSizeMb}
                        key={agentMaxFileSizeMb}
                        onBlur={(e) => handleMaxFileSizeChange(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleMaxFileSizeChange(e.currentTarget.value)
                        }}
                      />
                    </div>
                    <p className="agent-note">
                      A file larger than this is skipped entirely — never hashed, never uploaded.
                    </p>

                    <div className="sys-label">Excluded directories</div>
                    <p className="agent-note">
                      Always pruned: {DEFAULT_EXCLUDE_DIRS_SUMMARY.join(', ')}
                    </p>
                    {agentExcludeDirs.length > 0 && (
                      <ul className="agent-folder-list">
                        {agentExcludeDirs.map((dir) => (
                          <li className="agent-folder-row" key={dir}>
                            <span className="agent-folder-path">{dir}</span>
                            <button
                              type="button"
                              className="drawer-del"
                              onClick={() => handleRemoveExcludeDir(dir)}
                              aria-label={`Stop excluding ${dir}`}
                            >
                              ✕
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                    <div className="agent-exclude-dir-add">
                      <input
                        type="text"
                        className="sys-token-input"
                        placeholder="e.g. Drafts"
                        value={agentExcludeDirDraft}
                        onChange={(e) => setAgentExcludeDirDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleAddExcludeDir()
                        }}
                      />
                      <button type="button" className="wizard-secondary-btn" onClick={handleAddExcludeDir}>
                        Add
                      </button>
                    </div>

                    <div className="sys-label">Included file types</div>
                    <p className="agent-note">{DEFAULT_INCLUDE_EXTENSIONS_SUMMARY.join(', ')}</p>
                  </div>
                </details>

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
                      <ul className="agent-log-entries">
                        {agentLog.map((line, i) => (
                          <AgentLogEntry line={line} key={i} />
                        ))}
                      </ul>
                    )}
                  </div>
                </details>
              </>
            ) : (
              <p className="agent-intro">
                Run the ingestion agent on your machine — point it at folders and it keeps them
                indexed in Condense, automatically. Grab a standalone build below.
              </p>
            )}
          </div>

          <AgentDownloads />

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
