import { useEffect, useState } from 'react'

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
export default function SystemMenu({ token }: { token: string }) {
  const [open, setOpen] = useState(false)
  const [health, setHealth] = useState<Health>('unknown')
  const [data, setData] = useState<StatusResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // At-a-glance health: ping the open /healthz once on mount.
  useEffect(() => {
    let alive = true
    fetch('/healthz')
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

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch('/status', { headers: { Authorization: `Bearer ${token}` } })
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
      const resp = await fetch('/settings', {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value }),
      })
      if (!resp.ok) throw new Error(`Update failed: ${resp.status}`)
      setData((await resp.json()) as StatusResponse)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  function toggle() {
    const next = !open
    setOpen(next)
    if (next) load()
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
          <a className="sys-docs" href="/docs" target="_blank" rel="noreferrer">
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

          {data && (
            <div className="sys-section">
              <div className="sys-label">Settings</div>
              {Object.entries(data.settings).map(([k, v]) => {
                const editable = EDITABLE.has(k)
                return (
                  <div className="sys-row" key={k}>
                    <span className="sys-key">
                      {k.toUpperCase()}
                      {editable && (
                        <span className="sys-pencil" title="Editable — change and press Enter">
                          ✎
                        </span>
                      )}
                    </span>
                    {editable ? (
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
                    ) : (
                      <span className={`sys-val${v === null ? ' sys-null' : ''}`}>{fmt(v)}</span>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </aside>
    </>
  )
}
