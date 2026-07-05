import { useEffect, useState } from 'react'
import { apiFetch, apiUrl, getApiBase, setApiBase } from './api'

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
 * never inline-editable (distinct from the smaller `EDITABLE` whitelist above). */
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

/**
 * A subtle top-right status chip with a live health dot (pings the open /healthz). Click to
 * open a clean popover showing API health + the effective config (from the auth'd /status,
 * secrets already redacted server-side), rendered like a .env file. Closes on outside-click/Esc.
 */
export default function SystemMenu({
  token,
  setToken,
}: {
  token: string
  setToken: (t: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [apiBase, setApiBaseInput] = useState(() => getApiBase())
  const [health, setHealth] = useState<Health>('unknown')
  const [data, setData] = useState<StatusResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  // Keys with a just-saved PATCH — a "Saved ✓" fades in for a beat as optimistic feedback.
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set())

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
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  // (Re)load status when the panel opens or the token changes — so entering the token right
  // here immediately populates components + settings.
  useEffect(() => {
    if (open) void load()
  }, [open, token])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const resp = await apiFetch('/status', token)
      if (!resp.ok) {
        throw new Error(resp.status === 401 ? 'Enter a valid token to view settings' : `Status ${resp.status}`)
      }
      const json = (await resp.json()) as StatusResponse
      setData(json)
      setHealth('up')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
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

  function toggle() {
    setOpen((o) => !o)
  }

  return (
    <>
      <div className="sys">
        <button type="button" className="sys-chip" onClick={toggle} aria-expanded={open}>
          <svg
            className={`sys-gear sys-gear-${health}`}
            viewBox="0 0 24 24"
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
          System
        </button>
      </div>

      {open && <div className="drawer-backdrop" onClick={() => setOpen(false)} />}

      <aside
        className={`drawer${open ? ' open' : ''}`}
        role="dialog"
        aria-label="System status"
        aria-hidden={!open}
      >
        <div className="drawer-head">
          <h2>System</h2>
          <button
            type="button"
            className="drawer-close"
            onClick={() => setOpen(false)}
            aria-label="Close system panel"
          >
            ✕
          </button>
        </div>

        <div className="drawer-body">
          <div className="sys-section sys-token">
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

          <div className="sys-section sys-token">
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

          <a className="sys-docs" href={apiUrl('/docs')} target="_blank" rel="noreferrer">
            API documentation
            <span aria-hidden="true">↗</span>
          </a>

          {error && <p className="sys-error">{error}</p>}
          {loading && <p className="sys-muted">Loading…</p>}

          {data && (
            <div className="sys-section">
              <div className="sys-label">Components</div>
              {Object.entries(data.components).map(([name, c]) => (
                <div className="sys-comp" key={name}>
                  <span className={`sys-dot ${dotFor(c.status)}`} />
                  <span className="sys-comp-name">{name}</span>
                  <span className="sys-comp-detail">
                    {c.status === 'not_configured' ? 'off' : (c.model ?? c.detail ?? 'ok')}
                  </span>
                </div>
              ))}
            </div>
          )}

          {data &&
            (() => {
              const grouped = new Set(GROUPS.flatMap((g) => g.keys))
              const leftover = Object.keys(data.settings).filter((k) => !grouped.has(k))
              return (
                <div className="sys-section">
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
                                      <span className="sys-restart-badge" title="Requires an engine restart to change">
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
              )
            })()}
        </div>
      </aside>
    </>
  )
}
