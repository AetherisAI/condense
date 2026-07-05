import { useEffect, useState } from 'react'
import { apiFetch } from './api'
import { fetchDocuments, type DocumentSummary } from './documents'

function fileName(path: string): string {
  const parts = path.split(/[/\\]/)
  return parts[parts.length - 1] || path
}

function extOf(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
}

const TINTS: Record<string, string> = {
  pdf: '#e5484d',
  doc: '#3b82f6',
  docx: '#3b82f6',
  ppt: '#e8833a',
  pptx: '#e8833a',
  xls: '#22a06b',
  xlsx: '#22a06b',
  csv: '#22a06b',
  md: '#7c5cff',
  markdown: '#7c5cff',
  json: '#8f1fe6',
  yaml: '#8f1fe6',
  yml: '#8f1fe6',
  html: '#e8833a',
  htm: '#e8833a',
  txt: '#8b8794',
  rtf: '#8b8794',
}

function tintFor(name: string): string {
  return TINTS[extOf(name)] ?? '#6b6770'
}

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
 * Library drawer: a slide-out panel listing every document indexed in the libSQL store, with a
 * per-document delete. Opens on demand and fetches ``GET /documents``; ``DELETE /documents/{hash}``
 * removes one. If the configured store doesn't support listing yet (``supported: false``) it says
 * so plainly rather than erroring — the engine gains those two methods and this lights up. Its
 * own floating FAB trigger is gone (D57/Task U1) — `open` is controlled from the workbench
 * topbar's "Library" button. Slides in from the LEFT (`.drawer-left`, D57/Task U5) — every other
 * drawer opens from the right; open state persists across reloads (`App.tsx`, `libraryOpen` in
 * localStorage). Closes on backdrop-click or Escape, same as System/Agent.
 */
export default function Library({
  token,
  open,
  onOpenChange,
}: {
  token: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null)
  const [supported, setSupported] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  // Dismiss on Escape while open — outside clicks are caught by the drawer backdrop. Mirrors
  // System/Agent's exact pattern; unlike History (the one drawer that can share the screen with
  // several others stacked behind it), Library — now the sole LEFT-hand drawer, structurally last
  // in the DOM among the four — never has anything else painting in front of it, so it always
  // closes unconditionally on Escape (see ChatHistory.tsx for the yield-to-others nuance).
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onOpenChange(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    async function load() {
      setError(null)
      setLoading(true)
      try {
        const data = await fetchDocuments(token)
        if (cancelled) return
        setDocs(data.documents)
        setSupported(data.supported)
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

  async function remove(hash: string) {
    setBusy(hash)
    setError(null)
    try {
      const resp = await apiFetch(`/documents/${encodeURIComponent(hash)}`, token, {
        method: 'DELETE',
      })
      if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
      setDocs((prev) => (prev ? prev.filter((d) => d.source_hash !== hash) : prev))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const count = docs?.length ?? 0

  return (
    <>
      {open && <div className="drawer-backdrop" onClick={() => onOpenChange(false)} />}

      <aside
        className={`drawer drawer-left${open ? ' open' : ''}`}
        role="dialog"
        aria-label="Library"
        aria-hidden={!open}
      >
        <div className="drawer-head">
          <h2>Library</h2>
          {supported && count > 0 && <span className="drawer-count">{count}</span>}
          <button
            type="button"
            className="drawer-close"
            onClick={() => onOpenChange(false)}
            aria-label="Close library"
          >
            ✕
          </button>
        </div>

        <div className="drawer-body">
          {loading && <p className="drawer-muted">Loading…</p>}
          {error && <p className="error">{error}</p>}

          {!loading && !error && !supported && (
            <p className="drawer-muted">
              Document listing isn't available on the configured store yet — waiting on the engine
              to add it. Your documents are still indexed and searchable.
            </p>
          )}

          {!loading && !error && supported && docs && docs.length === 0 && (
            <p className="drawer-muted">No documents indexed yet. Drop files into the Documents panel.</p>
          )}

          {supported && docs && docs.length > 0 && (
            <ul className="drawer-list">
              {docs.map((d) => (
                <li className="drawer-item" key={d.source_hash}>
                  <span className="doc-icon" style={{ background: tintFor(d.path) }}>
                    {(extOf(d.path) || 'file').slice(0, 4).toUpperCase()}
                  </span>
                  <span className="doc-meta">
                    <span className="doc-name" title={d.path}>
                      {fileName(d.path)}
                    </span>
                    <span className="doc-sub">{d.chunks} chunks</span>
                  </span>
                  <button
                    type="button"
                    className="drawer-del"
                    disabled={busy === d.source_hash}
                    onClick={() => remove(d.source_hash)}
                    aria-label={`Delete ${fileName(d.path)} from the index`}
                    title="Delete from index"
                  >
                    {busy === d.source_hash ? '…' : <TrashIcon />}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </>
  )
}
