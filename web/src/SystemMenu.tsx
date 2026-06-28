import { useEffect, useRef, useState } from 'react'

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
  const ref = useRef<HTMLDivElement>(null)

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

  // Dismiss on outside click / Escape while open.
  useEffect(() => {
    if (!open) return
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
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

  function toggle() {
    const next = !open
    setOpen(next)
    if (next) load()
  }

  return (
    <div className="sys" ref={ref}>
      <button type="button" className="sys-chip" onClick={toggle} aria-expanded={open}>
        <span className={`sys-dot sys-dot-${health}`} />
        System
        <span className={`sys-caret${open ? ' open' : ''}`} aria-hidden="true">
          ⌄
        </span>
      </button>

      {open && (
        <div className="sys-pop" role="dialog" aria-label="System status">
          <div className="sys-pop-head">
            <span className={`sys-dot sys-dot-${health}`} />
            <strong>{health === 'down' ? 'Unreachable' : 'Healthy'}</strong>
            {data?.embed_model && <span className="sys-muted">· {data.embed_model}</span>}
          </div>

          <div className="sys-divider" />

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
              {Object.entries(data.settings).map(([k, v]) => (
                <div className="sys-row" key={k}>
                  <span className="sys-key">{k.toUpperCase()}</span>
                  <span className={`sys-val${v === null ? ' sys-null' : ''}`}>{fmt(v)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
