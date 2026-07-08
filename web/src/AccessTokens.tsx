import { useEffect, useState } from 'react'
import { apiFetch } from './api'

/** One named consumer token, as listed by GET /v1/tokens — the name only, never the value
 * (mirrors api.schemas.TokenInfo). */
type TokenInfo = { name: string }

/** Mirrors api.schemas.TokenCreateResponse — the ONE response that ever carries a token value. */
type TokenCreateResponse = { name: string; token: string; env_line: string }

function TrashIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      <path
        d="M5.5 2.5h5M2.5 4.5h11M4 4.5l.6 8a1 1 0 0 0 1 1h4.8a1 1 0 0 0 1-1l.6-8M6.5 7v4M9.5 7v4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/**
 * "Access tokens" section of the System drawer — mint/list/revoke per-consumer bearer tokens
 * against `api/tokens.py`. Every route behind this UI is gated to the master `INGEST_TOKEN`
 * (`require_master`): a per-consumer token gets a plain "requires the master token" message
 * instead of the list, never a raw 403 in the console. A freshly generated token's VALUE is
 * shown exactly once, alongside the complete `AUTH_TOKENS=...` line the operator must paste into
 * `.env` for it to survive a restart — the server itself never writes that file (see
 * `api/tokens.py`'s module docstring for the full persistence model).
 */
export default function AccessTokens({ token, open }: { token: string; open: boolean }) {
  const [tokens, setTokens] = useState<TokenInfo[] | null>(null)
  // Which auth failure (if any) the list load hit — 403 (a real but non-master token) gets a
  // different message than 401 (no/invalid token at all).
  const [denied, setDenied] = useState<401 | 403 | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [generated, setGenerated] = useState<TokenCreateResponse | null>(null)
  const [copied, setCopied] = useState<'token' | 'env' | null>(null)

  // (Re)load the list whenever the drawer opens or the token changes — same open/token-keyed,
  // race-guarded effect SystemMenu's own /status load already uses.
  useEffect(() => {
    if (!open) return
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const resp = await apiFetch('/v1/tokens', token)
        if (cancelled) return
        if (resp.status === 401 || resp.status === 403) {
          setDenied(resp.status)
          setTokens(null)
          return
        }
        setDenied(null)
        if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
        const json = (await resp.json()) as { tokens: TokenInfo[] }
        if (cancelled) return
        setTokens(json.tokens)
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

  async function generate() {
    const trimmed = name.trim()
    if (!trimmed) return
    setCreating(true)
    setError(null)
    try {
      const resp = await apiFetch('/v1/tokens', token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmed }),
      })
      if (resp.status === 401 || resp.status === 403) {
        setDenied(resp.status)
        return
      }
      if (!resp.ok) {
        const body = (await resp.json().catch(() => null)) as { detail?: string } | null
        throw new Error(body?.detail ?? `${resp.status} ${resp.statusText}`)
      }
      const created = (await resp.json()) as TokenCreateResponse
      setGenerated(created)
      setTokens((prev) =>
        [...(prev ?? []), { name: created.name }].sort((a, b) => a.name.localeCompare(b.name)),
      )
      setName('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setCreating(false)
    }
  }

  async function revoke(consumerName: string) {
    setBusy(consumerName)
    setError(null)
    try {
      const resp = await apiFetch(`/v1/tokens/${encodeURIComponent(consumerName)}`, token, {
        method: 'DELETE',
      })
      if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
      setTokens((prev) => (prev ? prev.filter((t) => t.name !== consumerName) : prev))
      setGenerated((prev) => (prev?.name === consumerName ? null : prev))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  function copy(value: string, which: 'token' | 'env') {
    void navigator.clipboard.writeText(value).then(() => {
      setCopied(which)
      setTimeout(() => setCopied(null), 1500)
    })
  }

  return (
    <>
      {denied === 403 && <p className="sys-muted">Requires the master (ingest) token.</p>}
      {denied === 401 && (
        <p className="sys-muted">
          Enter the master (ingest) token above to manage access tokens.
        </p>
      )}

      {denied === null && (
        <>
          {loading && <p className="sys-muted">Loading…</p>}
          {error && <p className="sys-error">{error}</p>}

          {!loading && tokens && tokens.length === 0 && (
            <p className="sys-muted">No named tokens yet.</p>
          )}

          {tokens && tokens.length > 0 && (
            <ul className="drawer-list">
              {tokens.map((t) => (
                <li className="drawer-item" key={t.name}>
                  <span className="doc-meta">
                    <span className="doc-name">{t.name}</span>
                  </span>
                  <button
                    type="button"
                    className="drawer-del"
                    disabled={busy === t.name}
                    onClick={() => void revoke(t.name)}
                    aria-label={`Revoke ${t.name}`}
                    title="Revoke token"
                  >
                    {busy === t.name ? '…' : <TrashIcon />}
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="sys-token">
            <label className="sys-label" htmlFor="new-token-name">
              New consumer name
            </label>
            <div className="sys-model-key-row">
              <input
                id="new-token-name"
                className="sys-token-input"
                type="text"
                value={name}
                placeholder="e.g. worktalky"
                autoComplete="off"
                spellCheck={false}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void generate()
                }}
              />
              <button
                type="button"
                className="agent-dl-btn"
                disabled={creating || !name.trim()}
                onClick={() => void generate()}
              >
                {creating ? 'Generating…' : 'Generate'}
              </button>
            </div>
          </div>

          {generated && (
            <div className="sys-token">
              <label className="sys-label">Token for “{generated.name}” — shown once</label>
              <div className="sys-model-key-row">
                <input
                  className="sys-token-input"
                  readOnly
                  value={generated.token}
                  spellCheck={false}
                  onFocus={(e) => e.target.select()}
                />
                <button
                  type="button"
                  className="copy-btn"
                  onClick={() => copy(generated.token, 'token')}
                >
                  {copied === 'token' ? 'Copied ✓' : 'Copy'}
                </button>
              </div>
              <div className="sys-model-key-row">
                <input
                  className="sys-token-input"
                  readOnly
                  value={generated.env_line}
                  spellCheck={false}
                  onFocus={(e) => e.target.select()}
                />
                <button
                  type="button"
                  className="copy-btn"
                  onClick={() => copy(generated.env_line, 'env')}
                >
                  {copied === 'env' ? 'Copied ✓' : 'Copy'}
                </button>
              </div>
              <p className="agent-note">
                Add this line to your .env — generated tokens live until the server restarts.
              </p>
            </div>
          )}
        </>
      )}
    </>
  )
}
