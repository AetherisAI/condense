import { useRef, useState } from 'react'
import { makeThumbnail } from './thumbnail'
import { postIngest, fmtSize, type IngestResponse } from './ingestClient'

/** A file's lifecycle in the panel: queued+uploading → its engine outcome (or a client error). */
type ItemStatus = 'uploading' | 'indexed' | 'skipped_dedup' | 'failed'

type UploadItem = {
  id: string
  name: string
  size: number
  status: ItemStatus
  chunks?: number | null
  detail?: string | null
  thumb?: string | null
}

/** Extension → a coloured type-chip, so the list shows *what* each file is at a glance. */
const FILE_TINTS: Record<string, string> = {
  pdf: '#e5484d',
  doc: '#3b82f6',
  docx: '#3b82f6',
  ppt: '#e8833a',
  pptx: '#e8833a',
  xls: '#22a06b',
  xlsx: '#22a06b',
  csv: '#22a06b',
  md: 'var(--accent-ui)',
  markdown: 'var(--accent-ui)',
  json: '#8f1fe6',
  yaml: '#8f1fe6',
  yml: '#8f1fe6',
  html: '#e8833a',
  htm: '#e8833a',
  txt: '#8b8794',
  rtf: '#8b8794',
}

function extOf(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
}

function tintFor(name: string): string {
  return FILE_TINTS[extOf(name)] ?? '#6b6770'
}

/** The right-hand status line for an item. */
function statusLine(it: UploadItem): string {
  switch (it.status) {
    case 'uploading':
      return 'Indexing…'
    case 'indexed':
      return it.chunks != null ? `Indexed · ${it.chunks} chunks` : 'Indexed'
    case 'skipped_dedup':
      return 'Already indexed'
    case 'failed':
      return it.detail ? `Failed · ${it.detail}` : 'Failed'
  }
}

/**
 * Documents panel: drop (or click to browse) one or more files into the dashed zone and they
 * **ingest automatically** — no button. Each file shows a type icon, name + size, and a live
 * status (Indexing… → Indexed · N chunks / Already indexed / Failed) as the engine answers.
 * Files post as multipart/form-data under "files" with the bearer token (the browser sets the
 * multipart boundary, so we never set Content-Type by hand).
 */
export default function Ingest({ token }: { token: string }) {
  const [items, setItems] = useState<UploadItem[]>([])
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  async function ingestFiles(picked: File[]) {
    if (picked.length === 0) return
    if (!token) {
      setError('Enter your token above first.')
      return
    }
    setError(null)
    // Queue every picked file as "uploading"; keep the batch so we can map results back by order.
    const batch: UploadItem[] = picked.map((f) => ({
      id: crypto.randomUUID(),
      name: f.name,
      size: f.size,
      status: 'uploading',
    }))
    setItems((prev) => [...batch, ...prev]) // newest on top
    const ids = new Set(batch.map((b) => b.id))

    // Thumbnails render in-browser, independent of upload — fill each in as it resolves.
    batch.forEach((b, i) => {
      void makeThumbnail(picked[i]).then((thumb) => {
        if (!thumb) return
        setItems((prev) => prev.map((it) => (it.id === b.id ? { ...it, thumb } : it)))
      })
    })

    try {
      const data: IngestResponse = await postIngest(token, picked)
      // The route returns one result per input file, in order — map batch[i] → results[i].
      setItems((prev) =>
        prev.map((it) => {
          if (!ids.has(it.id)) return it
          const i = batch.findIndex((b) => b.id === it.id)
          const r = data.results[i]
          if (!r) return { ...it, status: 'failed', detail: 'no result returned' }
          return {
            ...it,
            status: (r.status as ItemStatus) ?? 'failed',
            chunks: r.chunks,
            detail: r.detail,
          }
        }),
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(`Ingest failed: ${msg}`)
      setItems((prev) =>
        prev.map((it) => (ids.has(it.id) ? { ...it, status: 'failed', detail: msg } : it)),
      )
    }
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    void ingestFiles(Array.from(e.target.files ?? []))
    e.target.value = '' // let the same file be re-picked later
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    void ingestFiles(Array.from(e.dataTransfer.files))
  }

  function openPicker() {
    inputRef.current?.click()
  }

  const indexed = items.filter((it) => it.status === 'indexed').length

  return (
    <section className="panel ingest">
      <div className="ingest-head">
        <h2>Documents</h2>
        {items.length > 0 && (
          <span className="ingest-count">
            {indexed}/{items.length} indexed
          </span>
        )}
      </div>

      <div
        className={`dropzone${dragging ? ' dragging' : ''}`}
        role="button"
        tabIndex={0}
        aria-label="Drop files to ingest, or click to browse"
        onClick={openPicker}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            openPicker()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input ref={inputRef} type="file" multiple hidden onChange={onPick} />
        <span className="dropzone-plus" aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
          >
            <line x1="12" y1="6" x2="12" y2="18" />
            <line x1="6" y1="12" x2="18" y2="12" />
          </svg>
        </span>
        <span className="dropzone-text">
          Drop files to ingest
          <span className="dropzone-sub">or click to browse — they index automatically</span>
        </span>
      </div>

      {error && <p className="error">{error}</p>}

      {items.length > 0 && (
        <ul className="doc-list">
          {items.map((it) => (
            <li className={`doc-item doc-${it.status}`} key={it.id}>
              {it.thumb ? (
                <img className="doc-thumb" src={it.thumb} alt="" />
              ) : (
                <span className="doc-icon" style={{ background: tintFor(it.name) }}>
                  {(extOf(it.name) || 'file').slice(0, 4).toUpperCase()}
                </span>
              )}
              <span className="doc-meta">
                <span className="doc-name" title={it.name}>
                  {it.name}
                </span>
                <span className="doc-sub">
                  {fmtSize(it.size)} · {statusLine(it)}
                </span>
              </span>
              <span className="doc-badge" aria-hidden="true">
                {it.status === 'uploading' && <span className="doc-spinner" />}
                {it.status === 'indexed' && '✓'}
                {it.status === 'skipped_dedup' && '⊘'}
                {it.status === 'failed' && '✕'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
